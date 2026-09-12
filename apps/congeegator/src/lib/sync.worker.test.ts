import 'fake-indexeddb/auto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { db } from './db';
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
	expect(await db.versionIndices.get(key())).toMatchObject({ searchIndex: { m: [0] } });
	expect(await db.versionVerbs.get([key(), 0])).toMatchObject({ name: 'manger' });
});
it('does not overwrite newer data when an older app downloads its version', async () => {
	await sync();
	const newerKey = key();
	manifest.languages.fr.dataHash = 'older-build';
	await sync();
	expect(await db.versions.count()).toBe(2);
	expect(await db.versionVerbs.get([newerKey, 0])).toMatchObject({ name: 'manger' });
	expect(await db.versionIndices.get(newerKey)).toMatchObject({ searchIndex: { m: [0] } });
});
it('rejects malformed downloads without marking them installed', async () => {
	fetcher.mockResolvedValueOnce(Response.json({ verbs: payload().verbs }));
	await sync();
	expect(worker.postMessage).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'ERROR' }));
	expect(await db.versions.count()).toBe(0);
	expect(await db.versionVerbs.count()).toBe(0);
});
it('rolls back failed installation and retains the previous version', async () => {
	await sync();
	const previousKey = key();
	manifest.languages.fr.dataHash = 'new-version';
	vi.spyOn(db.versionIndices, 'put').mockRejectedValueOnce(
		new DOMException('Quota full', 'QuotaExceededError')
	);
	await sync();
	expect(worker.postMessage).toHaveBeenLastCalledWith(expect.objectContaining({ type: 'ERROR' }));
	expect(await db.versions.get(key())).toBeUndefined();
	expect(await db.versionVerbs.where('key').equals(key()).count()).toBe(0);
	expect(await db.versionVerbs.get([previousKey, 0])).toBeDefined();
});
it('repairs a same-version cache whose search index is missing', async () => {
	await sync();
	await db.versionIndices.delete(key());
	await sync();
	expect(fetcher).toHaveBeenCalledTimes(2);
	expect(await db.versionIndices.get(key())).toBeDefined();
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
