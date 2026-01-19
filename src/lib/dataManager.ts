import { browser } from '$app/environment';
import { PUBLIC_R2_URL } from '$env/static/public';
import manifestRaw from '$lib/data-manifest.json';
import { error } from '@sveltejs/kit';
import { db } from "./db";
import type { DataManifest, VerbData, VerbRecord } from "./types";

export const manifest = manifestRaw as DataManifest;

const DATA_VERSION = 1;

export async function syncLanguage(lang: string) {
    console.log(`starting to syncLanguage ${lang}`)
    if (!navigator.onLine) {
        console.log(`we are offline, can't sync`);
        return;

    };

    try {
        const remote = manifest.languages[lang];
        if (!remote) return 'not-supported';

        const local = await db.metadata.get(lang);

        if (!local || local.hash !== remote.hash) {
            const url = `${PUBLIC_R2_URL}/data/v${DATA_VERSION}/${lang}/data.json`;
            console.log(`Fetching ${url}`)
            const raw: Record<string, VerbData> = await fetch(url).then(r => r.json());
            const records = Object.entries(raw).map(([name, conjugations]) => ({ name, lang, conjugations }));

            await db.transaction('rw', [db.verbs, db.metadata], async () => {
                await db.verbs.where({ lang }).delete();
                await db.verbs.bulkPut(records);
                await db.metadata.put({ lang, hash: remote.hash });
            });

            console.log(`Inserted ${records.length} ${lang} verbs. sync finished`)
        } else {
            console.log(`${lang} data is already up-to-date (hash: ${local.hash})`)
        }

        return 'updated';
    } catch (e) {
        console.error('Background sync failed', e);
        return 'error';
    }
}

export async function loadSingleVerb(lang: string, verb: string, fetcher: typeof fetch): Promise<VerbRecord> {
    if (!(lang in manifest.languages)) {
        error(404, { message: `Language ${lang} not supported` });
    }

    // 1. Check IndexedDB first (Browser only)
    if (browser) {
        const cached = await db.verbs.get({ lang, name: verb.toLowerCase() });
        if (cached) {
            console.log('Found in IndexedDB');
            return cached;
        }
    }

    // 2. Fetch from Network (SSR or Cache Miss)
    // This works on both Server (Cloudflare Worker) and Browser
    const url = `${PUBLIC_R2_URL}/data/v${DATA_VERSION}/${lang}/verbs/${verb.toLowerCase()}.json`;
    console.log(`Fetching ${url}`)
    const response = await fetcher(url);

    if (response.status == 404) {
        // TODO: just redirect?
        error(404, { message: `Verb ${verb} not found` });
    }

    if (!response.ok) {
        throw new Error(`Verb ${verb} not found`);
    }

    const conjugations = await response.json();
    return {
        name: verb,
        lang,
        conjugations,
    } as VerbRecord;
}

export async function loadVerbIndexServer(lang: string, platform: App.Platform): Promise<string[]> {
    if (!(lang in manifest.languages)) {
        error(404, { message: `Language ${lang} not supported` });
    }

    // 2. SSR or Cache Miss: Fetch an 'index.json' for that language
    // You should generate this file in your build script (e.g., static/data/v1/fr/index.json)
    const key = `data/v${DATA_VERSION}/${lang}/index.json`;
    console.log(`Fetching r2 ${key}`)
    const response = await platform.env.DATA_BUCKET.get(key);

    if (!response) {
        throw new Error(`File ${key} not found in R2`);
    }

    const verbList: string[] = await response.json();
    return verbList;
}

export async function loadVerbIndexBrowser(lang: string, serverVerbs: string[]): Promise<string[]> {
    if (!(lang in manifest.languages)) {
        error(404, { message: `Language ${lang} not supported` });
    }

    // 1. Browser: Try to get all verb names from IndexedDB
    if (browser) {
        const localVerbs = await db.verbs
            .where('lang').equals(lang)
            .primaryKeys(); // Just get the [lang+name] keys to be fast

        if (localVerbs.length > 0) {
            // Extract just the 'name' part from the compound key
            return localVerbs.map(key => (key as string[])[1]).sort();
        }
    }

    // SERVER SIDE (or first load): Return the R2 data
    return serverVerbs;
}