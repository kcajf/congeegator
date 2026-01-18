import { browser } from '$app/environment';
import { db } from "./db";
import type { DataManifest, VerbData } from "./types";

const DATA_VERSION = 1;

export async function syncLanguage(lang: string) {
    console.log(`starting to syncLanguage ${lang}`)
    if (!navigator.onLine) {
        console.log(`we are offline, can't sync`);
        return;

    };

    try {
        const manifest: DataManifest = await fetch(`/data/${DATA_VERSION}/data-manifest.json`).then(r => r.json());

        if (manifest.schemaVersion > DATA_VERSION) {
            return 'app-update-required'; // Signal UI to show "Please Refresh App"
        }

        const remote = manifest.languages[lang];
        if (!remote) return 'not-supported';

        const local = await db.metadata.get(lang);

        if (!local || local.hash !== remote.hash) {
            const raw: Record<string, VerbData> = await fetch(remote.path).then(r => r.json());
            const records = Object.entries(raw).map(([name, conjugations]) => ({ name, lang, conjugations }));

            await db.transaction('rw', [db.verbs, db.metadata], async () => {
                await db.verbs.where({ lang }).delete();
                await db.verbs.bulkPut(records);
                await db.metadata.put({ lang, hash: remote.hash });
            });

            return 'updated';
        }

        return 'up-to-date';
    } catch (e) {
        console.error('Background sync failed', e);
        return 'error';
    }
}

export async function loadSingleVerb(lang: string, verb: string) {
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
    const url = `/data/${DATA_VERSION}/${lang}/verbs/${verb.toLowerCase()}.json`;
    const response = await fetch(url);

    if (!response.ok) {
        throw new Error(`Verb ${verb} not found`);
    }

    const verbData = await response.json();

    // // 3. Save to IndexedDB in the background (Don't 'await' this)
    // // This ensures the next time the user views this verb, it's offline-ready.
    // if (browser) {
    //     db.verbs.put({ ...verbData, lang });
    // }

    return verbData;
}

export async function loadVerbIndex(lang: string): Promise<string[]> {
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
    const url = `/data/${DATA_VERSION}/${lang}/index.json`;
    const response = await fetch(url);

    if (!response.ok) throw new Error(`Index for ${lang} not found`);

    const verbList: string[] = await response.json();

    return verbList;
}