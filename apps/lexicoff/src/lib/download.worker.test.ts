import { constants, zstdCompressSync } from 'node:zlib';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const realFetch = globalThis.fetch;
const data = vi.hoisted(() => ({ dataHash: 'aaaaaaaa', dataSize: 0 }));
vi.mock('./dataUtils', () => ({
	manifest: { languages: { fr: data } },
	getLangDataUrl: () => 'https://example.test/fr'
}));

beforeEach(() => {
	vi.resetModules();
});
afterEach(() => vi.unstubAllGlobals());

async function setup(checksum = false) {
	const original = new TextEncoder().encode('dictionary content '.repeat(10000));
	const compressed = zstdCompressSync(original, {
		params: { [constants.ZSTD_c_checksumFlag]: checksum ? 1 : 0 }
	});
	data.dataSize = compressed.length;
	let committed = new Uint8Array();
	let chunks: Uint8Array[] = [];
	const writable = {
		write: vi.fn(async (chunk: Uint8Array) => {
			chunks.push(chunk);
		}),
		close: vi.fn(async () => {
			committed = Buffer.concat(chunks);
		}),
		abort: vi.fn(async () => {})
	};
	const handle = {
		name: 'fr-aaaaaaaa.sqlite.zst',
		getFile: async () => new Blob([committed]),
		createWritable: async () => {
			chunks = [];
			return writable;
		}
	};
	const dir = { getFileHandle: async () => handle, removeEntry: vi.fn(async () => {}) };
	const worker = {
		postMessage: vi.fn(),
		onmessage: undefined as unknown as (event: MessageEvent) => Promise<void>
	};
	const fetchMock = vi.fn(async () => new Response(compressed));
	vi.stubGlobal('fetch', (url: string) => (url.startsWith('data:') ? realFetch(url) : fetchMock()));
	vi.stubGlobal('self', worker);
	vi.stubGlobal('navigator', {
		onLine: true,
		storage: { getDirectory: async () => ({ getDirectoryHandle: async () => dir }) }
	});
	await import('./download.worker');
	const download = () => worker.onmessage({ data: { lang: 'fr' } } as MessageEvent);
	const messages = () => worker.postMessage.mock.calls.map(([message]) => message);
	return {
		original,
		compressed,
		writable,
		dir,
		worker,
		fetchMock,
		download,
		messages,
		bytes: () => committed
	};
}

it('commits a complete stream before reporting success', async () => {
	const s = await setup();
	await s.download();
	expect(s.bytes().length).toBe(s.compressed.length);
	expect(Buffer.from(s.bytes()).equals(s.compressed)).toBe(true);
	expect(s.messages().at(-1)).toMatchObject({ type: 'COMPLETE' });
	expect(s.writable.abort).not.toHaveBeenCalled();
});

it('can retry repeated truncated streams without corrupting the shared decoder', async () => {
	const s = await setup();
	for (let i = 0; i < 5; i++) {
		s.fetchMock.mockResolvedValueOnce(new Response(s.compressed.subarray(0, -1)));
		await s.download();
		expect(s.messages().at(-1)).toMatchObject({ type: 'ERROR' });
	}
	expect(s.writable.close).not.toHaveBeenCalled();
	await s.download();
	expect(s.messages().at(-1)).toMatchObject({ type: 'COMPLETE' });
	expect(s.bytes().length).toBe(s.compressed.length);
	expect(Buffer.from(s.bytes()).equals(s.compressed)).toBe(true);
});

it('preserves a committed file when a replacement fails to close', async () => {
	const s = await setup();
	await s.download();
	s.writable.close.mockRejectedValueOnce(new Error('Quota exceeded'));
	await s.download();
	expect(s.messages().at(-1)).toMatchObject({
		type: 'ERROR',
		error: expect.stringContaining('Not enough browser storage')
	});
	expect(s.bytes().length).toBe(s.compressed.length);
	expect(Buffer.from(s.bytes()).equals(s.compressed)).toBe(true);
	expect(s.dir.removeEntry).not.toHaveBeenCalled();
	await s.download();
	expect(s.messages().at(-1)).toMatchObject({ type: 'COMPLETE' });
});

it('reports the original failure even if abort also fails', async () => {
	const s = await setup();
	s.writable.write.mockRejectedValueOnce(new Error('Storage full'));
	s.writable.abort.mockRejectedValueOnce(new Error('Already closed'));
	await s.download();
	expect(s.messages().at(-1)).toMatchObject({ type: 'ERROR', error: 'Storage full' });
});

it('deduplicates concurrent downloads of the same language', async () => {
	const s = await setup();
	await Promise.all([s.download(), s.download()]);
	expect(s.fetchMock).toHaveBeenCalledOnce();
	expect(s.messages().filter((m) => m.type === 'COMPLETE')).toHaveLength(1);
});
