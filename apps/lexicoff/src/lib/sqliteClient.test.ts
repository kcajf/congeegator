import { afterEach, beforeEach, expect, it, vi } from 'vitest';
vi.mock('./dataUtils', () => ({
	manifest: { languages: { fr: { dataHash: 'current' }, de: { dataHash: 'german' } } }
}));

class FakeWorker {
	static instances: FakeWorker[] = [];
	static files: [string, string, boolean?][] = [];
	static damaged = new Set<string>();
	holdOpen = false;
	holdList = false;
	postMessage = vi.fn(({ id, type, query }) => {
		if (type === 'list' && !this.holdList)
			queueMicrotask(() => this.reply(FakeWorker.files, undefined, id));
		if (type === 'open' && !this.holdOpen)
			queueMicrotask(() =>
				this.reply(true, FakeWorker.damaged.has(query) ? 'damaged' : undefined, id)
			);
	});
	terminate = vi.fn();
	onerror?: () => void;
	onmessage?: (event: MessageEvent) => void;
	constructor() {
		FakeWorker.instances.push(this);
	}
	ready(available = true) {
		this.onmessage?.(
			new MessageEvent('message', { data: { type: 'READY', sahPoolAvailable: available } })
		);
	}
	reply(result: unknown, error?: string, id = this.postMessage.mock.lastCall![0].id) {
		this.onmessage?.(new MessageEvent('message', { data: { id, result, error } }));
	}
}
beforeEach(() => {
	vi.resetModules();
	vi.useFakeTimers();
	FakeWorker.instances = [];
	FakeWorker.files = [];
	FakeWorker.damaged.clear();
	vi.stubGlobal('Worker', FakeWorker);
});
afterEach(() => {
	vi.useRealTimers();
	vi.unstubAllGlobals();
});
async function start() {
	const { storage } = await import('./sqliteClient.svelte');
	const opened = storage.connect();
	FakeWorker.instances[0].ready();
	await opened;
	return storage;
}

it('rejects pending requests on failure and rediscovers downloads with a fresh worker', async () => {
	FakeWorker.files = [['fr', 'current']];
	const storage = await start();
	const first = FakeWorker.instances[0];
	const rejected = expect(storage.getWord('fr', 'manger')).rejects.toThrow('stopped');
	await vi.advanceTimersByTimeAsync(0);
	first.onerror?.();
	await rejected;
	expect(storage.phase).toBe('error');
	const restarted = storage.restart();
	FakeWorker.instances[1].ready();
	await restarted;
	first.onerror?.();
	expect(storage.phase).toBe('ready');
	expect(storage.languages.fr).toEqual({ hash: 'current', status: 'ready' });
});
it('bounds a hung query and rejects queued requests too', async () => {
	const storage = await start();
	const rejected = expect(storage.getWord('fr', 'manger')).rejects.toThrow('timed out');
	const queued = expect(storage.search('fr', 'm')).rejects.toThrow('timed out');
	await vi.advanceTimersByTimeAsync(30_000);
	await Promise.all([rejected, queued]);
	expect(FakeWorker.instances[0].terminate).toHaveBeenCalledOnce();
});
it('starts a query timeout only after the preceding import completes', async () => {
	const storage = await start();
	const worker = FakeWorker.instances[0];
	worker.holdOpen = true;
	const install = storage.openDb('fr', 'current');
	await vi.advanceTimersByTimeAsync(0);
	const query = storage.getWord('fr', 'manger');
	await vi.advanceTimersByTimeAsync(60_000);
	expect(worker.postMessage.mock.lastCall![0].type).toBe('open');
	expect(worker.terminate).not.toHaveBeenCalled();
	worker.reply(true);
	await install;
	await vi.advanceTimersByTimeAsync(0);
	expect(worker.postMessage.mock.lastCall![0].type).toBe('getWord');
	worker.reply([]);
	expect(await query).toEqual([]);
});
it('allows retrying before READY and ignores late discovery replies', async () => {
	const { storage } = await import('./sqliteClient.svelte');
	const rejected = expect(storage.connect()).rejects.toThrow('restarted');
	const first = FakeWorker.instances[0];
	const retry = storage.restart();
	FakeWorker.instances[1].ready();
	await Promise.all([rejected, retry]);
	first.ready();
	first.reply([['fr', 'obsolete']], undefined, 0);
	expect(storage.phase).toBe('ready');
	expect(storage.languages).toEqual({});
});
it('falls back after a failed update and still opens other languages', async () => {
	FakeWorker.files = [
		['fr', 'previous'],
		['fr', 'current'],
		['de', 'german']
	];
	FakeWorker.damaged.add('current');
	const storage = await start();
	expect(storage.languages.fr).toEqual({ status: 'ready', hash: 'previous' });
	expect(storage.languages.de.status).toBe('ready');
	expect(
		FakeWorker.instances[0].postMessage.mock.calls
			.filter(([m]) => m.type === 'open')
			.map(([m]) => m.query)
	).toEqual(['current', 'previous', 'german']);
});
it('shows a failed language without blocking healthy downloads', async () => {
	FakeWorker.files = [
		['fr', 'current'],
		['de', 'german']
	];
	FakeWorker.damaged.add('current');
	const storage = await start();
	expect(storage.phase).toBe('ready');
	expect(storage.languages.fr.status).toBe('error');
	expect(storage.languages.de.status).toBe('ready');
});
it('makes startup failure visible and retryable', async () => {
	const { storage } = await import('./sqliteClient.svelte');
	const rejected = expect(storage.connect()).rejects.toThrow('could not be opened');
	FakeWorker.instances[0].ready(false);
	await rejected;
	expect(storage.phase).toBe('error');
	const retry = storage.restart();
	FakeWorker.instances[1].ready();
	await retry;
	expect(storage.phase).toBe('ready');
});
it('reports discovery errors instead of leaving opening pending', async () => {
	const { storage } = await import('./sqliteClient.svelte');
	const rejected = expect(storage.connect()).rejects.toThrow('Cannot list files');
	const worker = FakeWorker.instances[0];
	worker.holdList = true;
	worker.ready();
	await vi.advanceTimersByTimeAsync(0);
	worker.reply(undefined, 'Cannot list files');
	await rejected;
	expect(storage.phase).toBe('error');
});

it('does not import unfinished downloads during startup and opens installed languages first', async () => {
	FakeWorker.files = [
		['fr', 'current', true],
		['fr', 'previous'],
		['de', 'german', true]
	];
	const storage = await start();
	expect(storage.languages.fr).toEqual({ hash: 'previous', status: 'ready' });
	expect(storage.languages.de).toMatchObject({ hash: 'german', status: 'error' });
	expect(
		FakeWorker.instances[0].postMessage.mock.calls
			.filter(([m]) => m.type === 'open')
			.map(([m]) => m.query)
	).toEqual(['previous']);
});
it('closes a failed storage connection instead of repeatedly sending queries to it', async () => {
	FakeWorker.files = [['fr', 'current']];
	const storage = await start();
	const worker = FakeWorker.instances[0];
	const query = expect(storage.search('fr', 'test')).rejects.toThrow('AccessHandle is closed');
	await vi.advanceTimersByTimeAsync(0);
	worker.onmessage?.(
		new MessageEvent('message', {
			data: {
				id: worker.postMessage.mock.lastCall![0].id,
				error: 'AccessHandle is closed',
				fatal: true
			}
		})
	);
	await query;
	expect(storage.phase).toBe('error');
	expect(worker.terminate).toHaveBeenCalledOnce();
	const restarted = storage.restart();
	FakeWorker.instances[1].ready();
	await restarted;
	expect(storage.languages.fr.status).toBe('ready');
});
it('makes a query failure actionable on the affected dictionary', async () => {
	FakeWorker.files = [['fr', 'current']];
	const storage = await start();
	const query = expect(storage.search('fr', 'test')).rejects.toThrow('malformed');
	await vi.advanceTimersByTimeAsync(0);
	FakeWorker.instances[0].reply(undefined, 'database disk image is malformed');
	await query;
	expect(storage.languages.fr.status).toBe('error');
	expect(storage.phase).toBe('ready');
});
it('reports another window immediately and reopens installed dictionaries on retry', async () => {
	FakeWorker.files = [['fr', 'current']];
	const { storage } = await import('./sqliteClient.svelte');
	const opened = expect(storage.connect()).rejects.toThrow(
		'Close other Lexicoff tabs or app windows'
	);
	const worker = FakeWorker.instances[0];
	worker.onmessage?.(
		new MessageEvent('message', {
			data: { type: 'READY', sahPoolAvailable: false, storageBusy: true }
		})
	);
	await opened;
	expect(storage.phase).toBe('error');
	expect(storage.error).toContain('another Lexicoff window');
	expect(worker.terminate).toHaveBeenCalledOnce();
	expect(worker.postMessage).not.toHaveBeenCalled();
	const retry = storage.restart();
	FakeWorker.instances[1].ready();
	await retry;
	expect(storage.phase).toBe('ready');
	expect(storage.languages.fr).toEqual({ hash: 'current', status: 'ready' });
});
it('bounds unresponsive storage startup with a retryable error', async () => {
	const { storage } = await import('./sqliteClient.svelte');
	const opened = expect(storage.connect()).rejects.toThrow('Close other Lexicoff tabs');
	await vi.advanceTimersByTimeAsync(30000);
	await opened;
	expect(storage.phase).toBe('error');
});
it('does not time out an import while it continues reporting progress', async () => {
	const storage = await start();
	const worker = FakeWorker.instances[0];
	worker.holdOpen = true;
	const install = storage.openDb('fr', 'current');
	await vi.advanceTimersByTimeAsync(120000);
	worker.onmessage?.(
		new MessageEvent('message', { data: { type: 'INSTALL_PROGRESS', lang: 'fr' } })
	);
	await vi.advanceTimersByTimeAsync(120000);
	expect(worker.terminate).not.toHaveBeenCalled();
	worker.reply(true);
	await install;
});
