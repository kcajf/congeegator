import 'fake-indexeddb/auto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { db, recordsFor } from './db';
import { manifest } from './dataUtils';
import { datasetKey } from './datasets';
const worker = {
	postMessage: vi.fn(),
	onmessage: undefined as unknown as (event: MessageEvent) => Promise<void>
};
const fetcher = vi.fn();
const originalHash = manifest.languages.fr.dataHash;
const key = () => datasetKey('fr', manifest.languages.fr.dataHash);
const payload = () => ({
	verbs: [
		{
			name: 'manger',
			nameNoDiacritics: 'manger',
			freq: 1,
			conjugation: manifest.languages.fr.tenseNames.map(() => '')
		}
	],
	searchIndex: { m: [0] }
});
async function sync() {
	await worker.onmessage({ data: { lang: 'fr' } } as MessageEvent);
}
beforeEach(async () => {
	vi.stubGlobal('self', worker);
	vi.stubGlobal('navigator', { onLine: true });
	vi.stubGlobal('fetch', fetcher);
	worker.postMessage.mockClear();
	fetcher.mockReset().mockImplementation(async () => Response.json(payload()));
	await db.open();
	await import('./sync.worker');
});
afterEach(async () => {
	manifest.languages.fr.dataHash = originalHash;
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	await db.delete();
});
it('commits verbs, index, and their tense layout together', async () => {
	await sync();
	expect(worker.postMessage).toHaveBeenLastCalledWith({ type: 'COMPLETE', lang: 'fr' });
	expect(await db.versions.get(key())).toMatchObject({
		entryCount: 1,
		tenses: { tenseNames: manifest.languages.fr.tenseNames }
	});
	expect(await db.indices.get(key())).toMatchObject({ searchIndex: { m: [0] } });
	expect(await db.verbs.get([key(), 0])).toMatchObject({ name: 'manger' });
});
it('does not overwrite newer data when an older app downloads its version', async () => {
	await sync();
	const newerKey = key();
	manifest.languages.fr.dataHash = 'older-build';
	await sync();
	expect(await db.versions.count()).toBe(2);
	expect(await db.verbs.get([newerKey, 0])).toMatchObject({ name: 'manger' });
	expect(await db.indices.get(newerKey)).toMatchObject({ searchIndex: { m: [0] } });
});
it('rejects malformed downloads without marking them installed', async () => {
	fetcher.mockResolvedValueOnce(Response.json({ verbs: payload().verbs }));
	await sync();
	expect(worker.postMessage).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'ERROR' }));
	expect(await db.versions.count()).toBe(0);
	expect(await db.verbs.count()).toBe(0);
});
it('rolls back failed installation and retains the previous version', async () => {
	await sync();
	const previousKey = key();
	manifest.languages.fr.dataHash = 'new-version';
	vi.spyOn(db.indices, 'put').mockRejectedValueOnce(
		new DOMException('Quota full', 'QuotaExceededError')
	);
	await sync();
	expect(worker.postMessage).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'ERROR' }));
	expect(await db.versions.get(key())).toBeUndefined();
	expect(await recordsFor(key()).count()).toBe(0);
	expect(await db.verbs.get([previousKey, 0])).toBeDefined();
});
it('reports success even if obsolete-version cleanup fails', async () => {
	const request = vi.fn(async (_name, ...args) => {
		if (args.length === 1) return args[0]();
		throw new Error('Cleanup unavailable');
	});
	vi.stubGlobal('navigator', { onLine: true, locks: { request } });
	await sync();
	manifest.languages.fr.dataHash = 'new-version';
	await sync();
	expect(worker.postMessage).toHaveBeenLastCalledWith({ type: 'COMPLETE', lang: 'fr' });
	expect(await db.verbs.get([key(), 0])).toBeDefined();
	await sync();
	expect(fetcher).toHaveBeenCalledTimes(2);
	expect(worker.postMessage).toHaveBeenLastCalledWith({ type: 'COMPLETE', lang: 'fr' });
});
it('reuses a complete installation without network access', async () => {
	await sync();
	vi.stubGlobal('navigator', { onLine: false });
	await sync();
	expect(fetcher).toHaveBeenCalledTimes(1);
	expect(worker.postMessage).toHaveBeenLastCalledWith({ type: 'COMPLETE', lang: 'fr' });
});
it('waits for another tab then reports completion instead of skipping', async () => {
	let release!: () => Promise<void>;
	const request = vi.fn(
		(_name, run) =>
			new Promise<void>((resolve, reject) => {
				release = async () => {
					try {
						await run();
						resolve();
					} catch (error) {
						reject(error);
					}
				};
			})
	);
	vi.stubGlobal('navigator', { onLine: true, locks: { request } });
	const pending = sync();
	expect(fetcher).not.toHaveBeenCalled();
	await release();
	await pending;
	expect(request).toHaveBeenCalledWith('sync-fr', expect.any(Function));
	expect(worker.postMessage).toHaveBeenLastCalledWith({ type: 'COMPLETE', lang: 'fr' });
});
