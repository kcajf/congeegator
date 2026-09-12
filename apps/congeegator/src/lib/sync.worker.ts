import { pruneVersions } from './cacheRetention';
import { getLangDataUrl, manifest } from './dataUtils';
import { db, recordsFor } from './db';
import { datasetKey, validateDownload } from './datasets';

async function syncLanguage(lang: string) {
	const remote = manifest.languages[lang];
	if (!remote) throw new Error(`Unknown language ${lang}`);
	const key = datasetKey(lang, remote.dataHash);
	const local = await db.versions.get(key);
	if (local) {
		await pruneVersions(local).catch(console.warn);
		return;
	}
	if (!navigator.onLine) throw new Error('Offline. Reconnect to download this language.');

	self.postMessage({ type: 'PROGRESS', lang, phase: 'downloading', percent: null });
	const response = await fetch(`${getLangDataUrl(lang)}/data.json`);
	if (!response.ok) throw new Error(`Download failed (HTTP ${response.status})`);
	// The JSON parser rejects interrupted responses before any stored data changes.
	const raw: unknown = await response.json();
	validateDownload(raw, remote);
	const records = raw.verbs.map((verb, id) => ({ ...verb, id, lang, version: key }));

	const version = {
		key,
		lang,
		hash: remote.dataHash,
		entryCount: records.length,
		installedAt: Date.now(),
		tenses: remote
	};

	// Commit the replacement before reclaiming any previous version.
	await db.transaction('rw', [db.verbs, db.versions, db.indices], async () => {
		await recordsFor(key).delete();
		for (let i = 0; i < records.length; i += 500) {
			await db.verbs.bulkPut(records.slice(i, i + 500));
			self.postMessage({
				type: 'PROGRESS',
				lang,
				phase: 'installing',
				percent: Math.min(100, Math.round(((i + 500) / records.length) * 100))
			});
		}
		await db.indices.put({ key, searchIndex: raw.searchIndex });
		await db.versions.put(version);
	});
	// Cleanup is optional; an installed dictionary remains usable if it fails.
	await pruneVersions(version).catch(console.warn);
}

self.onmessage = async (event: MessageEvent<{ lang: string }>) => {
	const { lang } = event.data;
	try {
		// A waiting tab must observe completion, not abandon its request.
		if (navigator.locks) await navigator.locks.request(`sync-${lang}`, () => syncLanguage(lang));
		else await syncLanguage(lang);
		self.postMessage({ type: 'COMPLETE', lang });
	} catch (error) {
		self.postMessage({
			type: 'ERROR',
			lang,
			error: error instanceof Error ? error.message : String(error)
		});
	}
};
