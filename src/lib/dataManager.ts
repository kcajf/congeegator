import { browser } from '$app/environment';
import { PUBLIC_R2_URL } from '$env/static/public';
import manifestRaw from '$lib/data-manifest.json';
import { error } from '@sveltejs/kit';
import { db } from "./db";
import type { DataManifest, VerbRecord } from "./types";

export const manifest = manifestRaw as DataManifest;

const DATA_VERSION = 1;

function getLangDataRoot(langCode: string) {
    return `${PUBLIC_R2_URL}/data/v${DATA_VERSION}/${langCode}-${manifest.languages[langCode].dataHash}`
}

export function langName(langCode: string) {
    return manifest.languages[langCode].name;
}

export async function syncLanguage(lang: string) {
    console.log(`starting to syncLanguage ${lang}`)
    if (!navigator.onLine) {
        console.log(`we are offline, can't sync`);
        return;
    }

    try {
        const remote = manifest.languages[lang];
        if (!remote) return 'not-supported';

        const local = await db.metadata.get(lang);

        if (!local || local.hash !== remote.dataHash) {
            const url = `${getLangDataRoot(lang)}/data.json`;
            // console.log(`Fetching ${url}`)
            const raw = await fetch(url).then(r => r.json());
            const records: VerbRecord[] = raw.map((item: any) => ({
                ...item,
                lang: lang
            }));

            await db.transaction('rw', [db.verbs, db.metadata], async () => {
                await db.verbs.where({ lang: lang }).delete();
                await db.verbs.bulkPut(records);
                await db.metadata.put({ lang: lang, hash: remote.dataHash });
            });

            console.log(`Inserted ${raw.length} ${lang} verbs. sync finished`)
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
            console.log('Serving from IndexedDB');
            return cached;
        }
    }

    // 2. Fetch from Network (SSR or Cache Miss)
    // This works on both Server (Cloudflare Worker) and Browser
    const url = `${getLangDataRoot(lang)}/verbs/${verb.toLowerCase()}.json`;
    // console.log(`Fetching ${url}`)
    const response = await fetcher(url);

    if (response.status == 404) {
        // TODO: just redirect?
        error(404, { message: `Verb ${verb} not found` });
    }

    if (!response.ok) {
        throw new Error(`Verb ${verb} not found`);
    }

    const raw = await response.json();
    return { ...raw, lang } as VerbRecord;
}

export async function loadVerbIndex(lang: string, fetcher: typeof fetch): Promise<string[]> {
    if (!(lang in manifest.languages)) {
        error(404, { message: `Language ${lang} not supported` });
    }

    if (browser) {
        const localVerbs = await db.verbs
            .where('[lang+nameNoDiacritics]')
            .between([lang, ''], [lang, '\uffff'])
            .primaryKeys(); // Just get the [lang+name] keys to be fast
        if (localVerbs.length > 0) {
            console.log('Serving from IndexedDB');
            // Extract just the 'name' part from the compound key
            return localVerbs.map(key => (key as string[])[1]);
        }
    }

    // 2. SSR OR CACHE MISS: Fetch from R2 Public URL
    // This runs on the Cloudflare Worker during the initial page load
    // but runs in the browser if IndexedDB was empty.
    const url = `${getLangDataRoot(lang)}/index.json`;
    // console.log(`Fetching ${url}`)
    const res = await fetcher(url);

    if (!res.ok) throw new Error(`Error loading index for ${lang}`);

    const verbs: string[] = await res.json();
    return verbs;
}
