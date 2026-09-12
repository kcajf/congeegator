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
const checkReady = vi.fn<(lang?: string) => Promise<void>>().mockResolvedValue(undefined);
function setupClient() {
	let resolveDbsReady!: () => void;
	const dbsReady = new Promise<void>((r) => {
		resolveDbsReady = r;
	});
	return {
		dbsReady,
		resolveDbsReady,
		sqliteReady: Promise.resolve(),
		isSahPoolAvailable: () => true,
		listOpfsFiles: vi.fn<() => Promise<[string, string][]>>().mockResolvedValue([]),
		openDb: vi.fn<(lang: string, hash: string) => Promise<boolean>>().mockResolvedValue(true),
		closeDb: vi.fn<(lang: string) => Promise<void>>().mockResolvedValue(undefined),
		deleteFromPool: vi
			.fn<(lang: string, hash: string) => Promise<void>>()
			.mockResolvedValue(undefined),
		isInstalled: vi.fn<(lang: string) => Promise<boolean>>().mockResolvedValue(false)
	};
}

beforeEach(() => {
	vi.resetModules();
	checkReady.mockClear();
	DownloadWorker.instances = [];
	client = setupClient();
	vi.doMock('./sqliteClient', () => client);
	vi.doMock('./searchLang.svelte', () => ({ searchLangState: { checkReady } }));
	vi.stubGlobal('Worker', DownloadWorker);
});
afterEach(() => vi.unstubAllGlobals());

async function start() {
	const sync = await import('./syncManager.svelte');
	await client.dbsReady;
	return sync;
}
async function worker() {
	await vi.waitFor(() => expect(DownloadWorker.instances).toHaveLength(1));
	return DownloadWorker.instances[0];
}

it('discovers healthy languages even if another dictionary cannot open', async () => {
	client.listOpfsFiles.mockResolvedValue([
		['fr', 'aaaaaaaa'],
		['de', 'cccccccc'],
		['en', 'dddddddd']
	]);
	client.openDb.mockImplementation(async (lang) => {
		if (lang === 'de') throw new Error('damaged');
		return true;
	});
	const { globalSync } = await start();
	expect(globalSync.map.fr.status).toBe('ready');
	expect(globalSync.map.de.status).toBe('error');
	expect(globalSync.map.en.status).toBe('ready');
});

it('prefers the current dictionary and falls back to the old version on error', async () => {
	client.listOpfsFiles.mockResolvedValue([
		['fr', 'aaaaaaaa'],
		['fr', 'bbbbbbbb']
	]);
	client.openDb.mockImplementation(async (_lang, hash) => {
		if (hash === 'bbbbbbbb') throw new Error('damaged');
		return true;
	});
	const { globalSync } = await start();
	expect(client.openDb.mock.calls).toEqual([
		['fr', 'bbbbbbbb'],
		['fr', 'aaaaaaaa']
	]);
	expect(globalSync.map.fr).toMatchObject({ status: 'ready', hash: 'aaaaaaaa' });
});

it('waits for discovery and ignores duplicate install requests', async () => {
	let discovered!: (files: [string, string][]) => void;
	client.listOpfsFiles.mockReturnValue(
		new Promise((r) => {
			discovered = r;
		})
	);
	const sync = await import('./syncManager.svelte');
	const first = sync.triggerLangSync('fr');
	const duplicate = sync.triggerLangSync('fr');
	expect(DownloadWorker.instances).toHaveLength(0);
	discovered([]);
	const w = await worker();
	expect(sync.globalSync.map.fr.status).toBe('syncing');
	expect(w.postMessage).toHaveBeenCalledOnce();
	w.message({ type: 'COMPLETE', lang: 'fr', hash: 'bbbbbbbb' });
	await Promise.all([first, duplicate]);
	expect(sync.globalSync.map.fr.status).toBe('ready');
});

it('turns an import rejection into an error and lets Retry succeed', async () => {
	const sync = await start();
	client.openDb.mockRejectedValueOnce(new Error('Quota exceeded'));
	const first = sync.triggerLangSync('fr');
	const w = await worker();
	w.message({ type: 'COMPLETE', lang: 'fr', hash: 'bbbbbbbb' });
	await first;
	expect(sync.globalSync.map.fr).toMatchObject({ status: 'error', errorMessage: 'Quota exceeded' });
	const retry = sync.triggerLangSync('fr');
	await vi.waitFor(() => expect(w.postMessage).toHaveBeenCalledTimes(2));
	w.message({ type: 'COMPLETE', lang: 'fr', hash: 'bbbbbbbb' });
	await retry;
	expect(sync.globalSync.map.fr.status).toBe('ready');
});

it('retains a working installation and exposes the update error', async () => {
	client.listOpfsFiles.mockResolvedValue([['fr', 'aaaaaaaa']]);
	const sync = await start();
	client.isInstalled.mockResolvedValue(true);
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

it('waits for deletion acknowledgement and refreshes search readiness', async () => {
	client.listOpfsFiles.mockResolvedValue([['fr', 'aaaaaaaa']]);
	const sync = await start();
	checkReady.mockClear();
	const deleting = sync.deleteLang('fr');
	const w = await worker();
	expect(checkReady).toHaveBeenCalledWith('fr');
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
	expect(sync.globalSync.map.fr.status).toBe('ready');
});
