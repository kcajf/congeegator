import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ init: vi.fn() }));
vi.mock('@sqlite.org/sqlite-wasm', () => ({ default: mocks.init }));

function setup() {
	const files = new Set<string>();
	const raw = new Map<string, Blob>();
	const databases: { filename: string; close: ReturnType<typeof vi.fn> }[] = [];
	const pool = {
		getFileNames: () => [...files],
		getFileCount: () => files.size,
		reserveMinimumCapacity: vi.fn(async () => {}),
		importDb: vi.fn(async (name: string, read: () => Promise<Uint8Array | undefined>) => {
			while (await read()) {
				/* consume the input */
			}
			files.add(name);
		}),
		unlink: vi.fn((name: string) => files.delete(name)),
		removeVfs: vi.fn(),
		OpfsSAHPoolDb: class {
			close = vi.fn();
			exec = vi.fn();
			constructor(public filename: string) {
				databases.push(this);
			}
			selectValue(sql: string) {
				return sql === 'PRAGMA quick_check' ? 'ok' : this.filename.slice(1, 3);
			}
		}
	};
	const dir = {
		getFileHandle: vi.fn(async (name: string) => {
			if (!raw.has(name)) throw new DOMException('Missing download', 'NotFoundError');
			return { getFile: async () => raw.get(name)! };
		}),
		removeEntry: vi.fn(async (name: string) => {
			raw.delete(name);
		}),
		async *entries() {
			for (const name of raw.keys()) yield [name, {}];
		}
	};
	const postMessage = vi.fn();
	const worker = {
		postMessage,
		onmessage: undefined as unknown as (e: MessageEvent) => Promise<void>
	};
	const locks = { request: vi.fn((_name: string, run: () => Promise<void>) => run()) };
	vi.stubGlobal('self', worker);
	vi.stubGlobal('navigator', {
		locks,
		storage: { getDirectory: async () => ({ getDirectoryHandle: async () => dir }) }
	});
	mocks.init.mockResolvedValue({ installOpfsSAHPoolVfs: async () => pool });
	let id = 0;
	async function send(type: string, lang = 'fr', query = 'aaaaaaaa') {
		const current = id++;
		await worker.onmessage({
			data: { id: current, type, lang, query, hash: query }
		} as MessageEvent);
		return postMessage.mock.calls.map(([m]) => m).find((m) => m.id === current);
	}
	async function start() {
		await import('./sqlite.worker');
		await vi.waitFor(() =>
			expect(postMessage).toHaveBeenCalledWith({ type: 'READY', sahPoolAvailable: true })
		);
	}
	return { files, raw, databases, pool, dir, worker, locks, postMessage, send, start };
}

beforeEach(() => {
	vi.resetModules();
	vi.clearAllMocks();
});
afterEach(() => vi.unstubAllGlobals());

describe('dictionary storage lifecycle', () => {
	it('preserves installed files when shutting down for an app update', async () => {
		const s = setup();
		s.files.add('/fr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open');
		await s.send('shutdown');
		expect(s.databases[0].close).toHaveBeenCalledOnce();
		expect(s.pool.removeVfs).not.toHaveBeenCalled();
		expect([...s.files]).toEqual(['/fr-aaaaaaaa.sqlite']);
	});

	it('keeps the old dictionary on failure and allows later imports', async () => {
		const s = setup();
		s.files.add('/fr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open');
		s.raw.set('fr-bbbbbbbb.sqlite', new Blob(['replacement']));
		s.pool.reserveMinimumCapacity.mockRejectedValueOnce(new Error('Quota exceeded'));
		expect((await s.send('open', 'fr', 'bbbbbbbb')).error).toBe('Quota exceeded');
		expect(s.databases[0].close).not.toHaveBeenCalled();
		expect(s.files.has('/fr-aaaaaaaa.sqlite')).toBe(true);
		expect((await s.send('isInstalled')).result).toBe(true);
		s.raw.set('de-cccccccc.sqlite', new Blob(['database']));
		expect((await s.send('open', 'de', 'cccccccc')).result).toBe(true);
		s.raw.set('fr-bbbbbbbb.sqlite', new Blob(['replacement']));
		expect((await s.send('open', 'fr', 'bbbbbbbb')).result).toBe(true);
		expect(s.files.has('/fr-aaaaaaaa.sqlite')).toBe(false);
		expect(s.databases[0].close).toHaveBeenCalledOnce();
	});

	it('does not activate a dictionary with the wrong language', async () => {
		const s = setup();
		s.files.add('/fr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open');
		vi.spyOn(s.pool.OpfsSAHPoolDb.prototype, 'selectValue').mockReturnValue('de');
		s.raw.set('fr-bbbbbbbb.sqlite', new Blob(['wrong dictionary']));
		expect((await s.send('open', 'fr', 'bbbbbbbb')).error).toMatch('does not match');
		expect(s.files.has('/fr-aaaaaaaa.sqlite')).toBe(true);
		expect(s.files.has('/fr-bbbbbbbb.sqlite')).toBe(false);
		expect(s.databases[0].close).not.toHaveBeenCalled();
	});

	it('treats raw-file cleanup failure as a successful installation', async () => {
		const s = setup();
		await s.start();
		s.raw.set('fr-aaaaaaaa.sqlite', new Blob(['database']));
		s.dir.removeEntry.mockRejectedValueOnce(new Error('cleanup failed'));
		expect((await s.send('open')).result).toBe(true);
		expect((await s.send('isInstalled')).result).toBe(true);
	});

	it('removes empty interrupted downloads before discovery', async () => {
		const s = setup();
		await s.start();
		s.raw.set('fr-aaaaaaaa.sqlite', new Blob());
		s.raw.set('de-bbbbbbbb.sqlite', new Blob(['complete']));
		expect((await s.send('list')).result).toEqual([['de', 'bbbbbbbb']]);
		expect(s.raw.has('fr-aaaaaaaa.sqlite')).toBe(false);
	});

	it('serializes deletion behind an in-flight import', async () => {
		const s = setup();
		await s.start();
		s.raw.set('fr-aaaaaaaa.sqlite', new Blob(['database']));
		let release!: () => void;
		s.pool.reserveMinimumCapacity.mockImplementationOnce(
			() =>
				new Promise<void>((r) => {
					release = r;
				})
		);
		const opening = s.send('open');
		await vi.waitFor(() => expect(release).toBeDefined());
		const closing = s.send('close');
		release();
		await opening;
		await closing;
		expect((await s.send('isInstalled')).result).toBe(false);
	});

	it('waits for another tab to release ownership instead of deleting its files', async () => {
		const s = setup();
		let acquire!: () => Promise<void>;
		s.locks.request.mockImplementationOnce((_name, run) => {
			acquire = run;
			return new Promise(() => {});
		});
		await import('./sqlite.worker');
		expect(mocks.init).not.toHaveBeenCalled();
		void acquire();
		await vi.waitFor(() =>
			expect(s.postMessage).toHaveBeenCalledWith({ type: 'READY', sahPoolAvailable: true })
		);
		expect(s.pool.removeVfs).not.toHaveBeenCalled();
	});
});

it('does not scan an already-installed dictionary on startup', async () => {
	const s = setup();
	s.files.add('/fr-aaaaaaaa.sqlite');
	const query = vi.spyOn(s.pool.OpfsSAHPoolDb.prototype, 'selectValue');
	await s.start();
	await s.send('open');
	expect(query).not.toHaveBeenCalledWith('PRAGMA quick_check');
});

it('reimports an interrupted installation without a full-database scan', async () => {
	const s = setup();
	s.files.add('/fr-aaaaaaaa.sqlite');
	s.raw.set('fr-aaaaaaaa.sqlite', new Blob(['complete source']));
	const query = vi.spyOn(s.pool.OpfsSAHPoolDb.prototype, 'selectValue');
	await s.start();
	expect((await s.send('open')).result).toBe(true);
	expect(s.pool.importDb).toHaveBeenCalledOnce();
	expect(query).not.toHaveBeenCalledWith('PRAGMA quick_check');
	expect(s.raw.has('fr-aaaaaaaa.sqlite')).toBe(false);
});
