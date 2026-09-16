import { afterEach, beforeEach, expect, it, vi } from 'vitest';

vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('./dataUtils', () => ({
	manifest: {
		languages: {
			fr: { dataHash: 'bbbbbbbb' },
			de: { dataHash: 'cccccccc' },
			en: { dataHash: 'dddddddd' }
		}
	}
}));

class DownloadWorker extends EventTarget {
	static instances: DownloadWorker[] = [];
	postMessage = vi.fn();
	terminate = vi.fn();
	constructor() {
		super();
		DownloadWorker.instances.push(this);
	}
	message(data: object) {
		this.dispatchEvent(new MessageEvent('message', { data }));
	}
}

let client: ReturnType<typeof setupClient>;
function setupClient() {
	const languages: Record<string, { hash: string; status: 'ready' }> = {};
	return {
		languages,
		hasDownload: vi.fn().mockResolvedValue(false),
		connect: vi.fn().mockResolvedValue(undefined),
		openDb: vi.fn(async (lang: string, hash: string) => {
			languages[lang] = { hash, status: 'ready' };
		}),
		removeDb: vi.fn(async (lang: string) => {
			delete languages[lang];
		}),
		restart: vi.fn()
	};
}

beforeEach(() => {
	vi.resetModules();
	DownloadWorker.instances = [];
	client = setupClient();
	vi.doMock('./sqliteClient.svelte', () => ({ storage: client }));
	vi.stubGlobal('Worker', DownloadWorker);
});
afterEach(() => vi.unstubAllGlobals());

async function start() {
	const sync = await import('./syncManager.svelte');
	return sync;
}
async function worker() {
	await vi.waitFor(() => expect(DownloadWorker.instances).toHaveLength(1));
	return DownloadWorker.instances[0];
}

it('waits for discovery and ignores duplicate install requests', async () => {
	let discovered!: () => void;
	client.connect.mockReturnValue(
		new Promise<void>((resolve) => {
			discovered = resolve;
		})
	);
	const sync = await import('./syncManager.svelte');
	const first = sync.triggerLangSync('fr');
	const duplicate = sync.triggerLangSync('fr');
	expect(DownloadWorker.instances).toHaveLength(0);
	await vi.waitFor(() => expect(client.connect).toHaveBeenCalledOnce());
	discovered();
	const w = await worker();
	expect(sync.globalSync.map.fr.status).toBe('syncing');
	expect(w.postMessage).toHaveBeenCalledOnce();
	w.message({ type: 'COMPLETE', lang: 'fr', hash: 'bbbbbbbb' });
	await Promise.all([first, duplicate]);
	expect(sync.globalSync.map.fr).toBeUndefined();
	expect(client.languages.fr.status).toBe('ready');
});

it('turns an import rejection into an error and lets Retry succeed', async () => {
	const sync = await start();
	client.openDb.mockRejectedValueOnce(new Error('Quota exceeded'));
	const first = sync.triggerLangSync('fr');
	const w = await worker();
	w.message({ type: 'COMPLETE', lang: 'fr', hash: 'bbbbbbbb' });
	await first;
	expect(sync.globalSync.map.fr).toMatchObject({
		status: 'error',
		errorMessage: expect.stringContaining('Not enough browser storage')
	});
	const retry = sync.triggerLangSync('fr');
	await vi.waitFor(() => expect(w.postMessage).toHaveBeenCalledTimes(2));
	w.message({ type: 'COMPLETE', lang: 'fr', hash: 'bbbbbbbb' });
	await retry;
	expect(sync.globalSync.map.fr).toBeUndefined();
	expect(client.languages.fr.status).toBe('ready');
});

it('retains a working installation and exposes the update error', async () => {
	client.languages.fr = { hash: 'aaaaaaaa', status: 'ready' };
	const sync = await start();
	const updating = sync.triggerLangSync('fr');
	const w = await worker();
	w.message({ type: 'ERROR', lang: 'fr', error: 'offline' });
	await updating;
	expect(sync.globalSync.map.fr).toMatchObject({
		status: 'ready',
		hash: 'aaaaaaaa',
		errorMessage: 'Offline'
	});
});

it('waits for deletion acknowledgement and prevents a concurrent install', async () => {
	client.languages.fr = { hash: 'aaaaaaaa', status: 'ready' };
	const sync = await start();
	const deleting = sync.deleteLang('fr');
	const w = await worker();
	expect(client.languages.fr).toBeUndefined();
	expect(sync.globalSync.map.fr.status).toBe('syncing');
	await sync.triggerLangSync('fr');
	expect(w.postMessage).toHaveBeenCalledOnce();
	w.message({ type: 'DELETED', lang: 'fr' });
	await deleting;
	expect(sync.globalSync.map.fr).toBeUndefined();
});

it('recreates a crashed download worker on retry', async () => {
	const sync = await start();
	const first = sync.triggerLangSync('fr');
	const w = await worker();
	w.dispatchEvent(new Event('error'));
	await first;
	expect(sync.globalSync.map.fr.status).toBe('error');
	const retry = sync.triggerLangSync('fr');
	await vi.waitFor(() => expect(DownloadWorker.instances).toHaveLength(2));
	DownloadWorker.instances[1].message({ type: 'COMPLETE', lang: 'fr', hash: 'bbbbbbbb' });
	await retry;
	expect(sync.globalSync.map.fr).toBeUndefined();
	expect(client.languages.fr.status).toBe('ready');
});

it('retries a completed download without downloading it again', async () => {
	client.hasDownload.mockResolvedValue(true);
	const sync = await start();
	await sync.triggerLangSync('fr');
	expect(DownloadWorker.instances).toHaveLength(0);
	expect(client.openDb).toHaveBeenCalledWith('fr', 'bbbbbbbb');
	expect(client.languages.fr.status).toBe('ready');
});

it('allows two operations and keeps the next queued until an installation finishes', async () => {
	let finishInstall!: () => void;
	client.openDb.mockImplementationOnce(
		() => new Promise<void>((resolve) => (finishInstall = resolve))
	);
	const sync = await start();
	const first = sync.triggerLangSync('fr');
	const second = sync.triggerLangSync('de');
	const removal = sync.deleteLang('en');
	await sync.deleteLang('en'); // A queued language cannot be queued twice.
	const w = await worker();
	expect(sync.globalSync.map.de.stage).toBe('downloading');
	expect(sync.globalSync.map.en.stage).toBe('queued');
	expect(w.postMessage).toHaveBeenCalledTimes(2);
	w.message({ type: 'COMPLETE', lang: 'fr', hash: 'bbbbbbbb' });
	await vi.waitFor(() => expect(client.openDb).toHaveBeenCalledOnce());
	expect(sync.globalSync.map.fr.stage).toBe('installing');
	expect(w.postMessage).toHaveBeenCalledTimes(2);
	expect(client.removeDb).not.toHaveBeenCalled();
	finishInstall();
	await first;
	await vi.waitFor(() => expect(w.postMessage).toHaveBeenCalledTimes(3));
	expect(w.postMessage).toHaveBeenLastCalledWith({ lang: 'en', type: 'delete' });
	expect(sync.globalSync.map.de.stage).toBe('downloading');
	w.message({ type: 'COMPLETE', lang: 'de', hash: 'cccccccc' });
	await second;
	await vi.waitFor(() => expect(w.postMessage).toHaveBeenCalledTimes(3));
	expect(w.postMessage).toHaveBeenLastCalledWith({ lang: 'en', type: 'delete' });
	w.message({ type: 'DELETED', lang: 'en' });
	await removal;
	expect(sync.globalSync.map).toEqual({});
});

it('continues the queue after an installation fails', async () => {
	client.hasDownload.mockResolvedValue(true);
	client.openDb.mockRejectedValueOnce(new Error('Installation failed'));
	const sync = await start();
	await Promise.all([
		sync.triggerLangSync('fr'),
		sync.triggerLangSync('de'),
		sync.triggerLangSync('en')
	]);
	expect(sync.globalSync.map.fr.errorMessage).toBe('Installation failed');
	expect(client.languages.de.status).toBe('ready');
	expect(sync.globalSync.map.de).toBeUndefined();
	expect(client.languages.en.status).toBe('ready');
});
