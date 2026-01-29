import { browser } from '$app/environment';
import { PUBLIC_R2_URL } from '$env/static/public';
import manifestRaw from '$lib/data-manifest.json';
import { error } from '@sveltejs/kit';
import { db } from "./db";
import type { DataManifest, VerbRecord } from "./types";

export const manifest = manifestRaw as DataManifest;

const DATA_VERSION = 1;

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

        if (!local || local.hash !== remote.hash) {
            const url = `${PUBLIC_R2_URL}/data/v${DATA_VERSION}/${lang}/data.json`;
            // console.log(`Fetching ${url}`)
            const raw = await fetch(url).then(r => r.json());
            const records: VerbRecord[] = raw.map((item: any) => ({
                ...item,
                lang: lang
            }));

            await db.transaction('rw', [db.verbs, db.metadata], async () => {
                await db.verbs.where({ lang: lang }).delete();
                await db.verbs.bulkPut(records);
                await db.metadata.put({ lang: lang, hash: remote.hash });
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
    const url = `${PUBLIC_R2_URL}/data/v${DATA_VERSION}/${lang}/verbs/${verb.toLowerCase()}.json`;
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
