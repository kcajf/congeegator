import { browser } from '$app/environment';
import { error } from '@sveltejs/kit';
import { db, getInstalledVersion, recordsFor } from './db';
import type { VerbRecord } from './types';
import { getLangDataUrl, manifest } from './dataUtils';

export async function loadSingleVerb(
	lang: string,
	verb: string,
	fetcher: typeof fetch
): Promise<VerbRecord> {
	if (!(lang in manifest.languages)) {
		error(404, { message: `Language ${lang} not supported` });
	}
	const verbLower = verb.toLowerCase();
	const lookupNames = lang === 'en' && verb !== verbLower ? [verb, verbLower] : [verbLower];

	// 1. Check IndexedDB first (Browser only)
	if (browser) {
		try {
			const cached = await db.transaction('r', [db.versions, db.verbs], async () => {
				const version = await getInstalledVersion(lang);
				if (!version) return undefined;
				for (const name of lookupNames) {
					const record = await db.verbs.get({ version: version.key, name });
					if (record) return { ...record, lang, tenses: version.tenses };
				}
				return undefined;
			});
			if (cached) return cached;
		} catch (err) {
			console.warn('Could not read cached verb; trying the network:', err);
		}
	}

	// 2. Fetch from Network (SSR or Cache Miss)
	// This works on both Server (Cloudflare Worker) and Browser
	const url = `${getLangDataUrl(lang)}/chunks/${verbLower[0]}.json`;
	const response = await fetcher(url);

	if (!response.ok) {
		error(404, { message: `Verb ${verb} not found` });
	}

	const chunk = await response.json();
	// English can distinguish abbreviation verbs from lowercase homographs
	// (AIM/aim). The fallback also reads older lowercase-keyed English bundles.
	const raw = lookupNames.map((name) => chunk[name]).find(Boolean);
	if (!raw) {
		error(404, { message: `Verb ${verb} not found` });
	}

	return { ...raw, lang, tenses: manifest.languages[lang] } as VerbRecord;
}

export async function loadVerbIndex(lang: string, fetcher: typeof fetch): Promise<string[]> {
	if (!(lang in manifest.languages)) {
		error(404, { message: `Language ${lang} not supported` });
	}

	if (browser) {
		try {
			const names = await db.transaction('r', [db.versions, db.verbs], async () => {
				const version = await getInstalledVersion(lang);
				if (!version) return [];
				return (await recordsFor(version.key).limit(25).toArray()).map((verb) => verb.name);
			});
			if (names.length) return names;
		} catch (err) {
			console.warn('Could not read cached index; trying the network:', err);
		}
	}

	// 2. SSR OR CACHE MISS: Fetch from R2 Public URL
	// This runs on the Cloudflare Worker during the initial page load
	// but runs in the browser if IndexedDB was empty.
	const url = `${getLangDataUrl(lang)}/index.json`;
	// console.log(`Fetching ${url}`)
	const res = await fetcher(url);

	if (!res.ok) throw new Error(`Error loading index for ${lang}`);

	const verbs: string[] = await res.json();
	return verbs;
}
