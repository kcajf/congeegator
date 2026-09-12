import { getLangDataUrl, manifest } from './dataUtils';
import { db } from './db';
import { datasetKey, validateDownload } from './datasets';

async function syncLanguage(lang: string) {
	const remote = manifest.languages[lang];
	if (!remote) throw new Error(`Unknown language ${lang}`);
	const key = datasetKey(lang, remote.dataHash);
	const local = await db.versions.get(key);
	if (
		local &&
		(await db.versionIndices.where('key').equals(key).count()) &&
		(await db.versionVerbs.where('key').equals(key).count()) === local.entryCount
	)
		return;
	if (!navigator.onLine) throw new Error('Offline. Reconnect to download this language.');

	self.postMessage({ type: 'PROGRESS', lang, phase: 'downloading', percent: null });
	const response = await fetch(`${getLangDataUrl(lang)}/data.json`);
	if (!response.ok) throw new Error(`Download failed (HTTP ${response.status})`);
	// The JSON parser rejects interrupted responses before any stored data changes.
	const raw: unknown = await response.json();
	validateDownload(raw, remote);
	const records = raw.verbs.map((verb, id) => ({ ...verb, id, lang, key }));

	// Retain other versions: an older open tab may still be reading them.
	await db.transaction('rw', [db.versionVerbs, db.versions, db.versionIndices], async () => {
		await db.versionVerbs.where('key').equals(key).delete();
		for (let i = 0; i < records.length; i += 500) {
			await db.versionVerbs.bulkPut(records.slice(i, i + 500));
			self.postMessage({
				type: 'PROGRESS',
				lang,
				phase: 'installing',
				percent: Math.min(100, Math.round(((i + 500) / records.length) * 100))
			});
		}
		await db.versionIndices.put({ key, searchIndex: raw.searchIndex });
		await db.versions.put({
			key,
			lang,
			hash: remote.dataHash,
			entryCount: records.length,
			installedAt: Date.now(),
			tenses: remote
		});
	});
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
