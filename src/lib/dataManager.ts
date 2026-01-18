import { browser } from '$app/environment';
import { db } from "./db";
import type { DataManifest, VerbData, VerbRecord } from "./types";

const DATA_VERSION = 1;

export async function syncLanguage(lang: string) {
    console.log(`starting to syncLanguage ${lang}`)
    if (!navigator.onLine) {
        console.log(`we are offline, can't sync`);
        return;

    };

    try {
        const manifest: DataManifest = await fetch(`/data/v${DATA_VERSION}/data-manifest.json`).then(r => r.json());
        console.log('data manifest', manifest);

        const remote = manifest.languages[lang];
        if (!remote) return 'not-supported';

        const local = await db.metadata.get(lang);

        if (!local || local.hash !== remote.hash) {
            const raw: Record<string, VerbData> = await fetch(`/data/v${DATA_VERSION}/${lang}/data.json`).then(r => r.json());
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
    const url = `/data/v${DATA_VERSION}/${lang}/verbs/${verb.toLowerCase()}.json`;
    const response = await fetcher(url);

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

export async function loadVerbIndex(lang: string, fetcher: typeof fetch): Promise<string[]> {
    // 1. Browser: Try to get all verb names from IndexedDB
    if (browser) {
        const localVerbs = await db.verbs
            .where('lang').equals(lang)
            .primaryKeys(); // Just get the [lang+name] keys to be fast

        if (localVerbs.length > 0) {
            // Extract just the 'name' part from the compound key
            return localVerbs.map(key => (key as string[])[1]);
        }
    }

    // 2. SSR or Cache Miss: Fetch an 'index.json' for that language
    // You should generate this file in your build script (e.g., static/data/v1/fr/index.json)
    const url = `/data/v${DATA_VERSION}/${lang}/index.json`;
    const response = await fetcher(url);

    if (!response.ok) throw new Error(`Index for ${lang} not found`);

    const verbList: string[] = await response.json();

    return verbList;
}