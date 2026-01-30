import { browser } from '$app/environment';
import { error } from '@sveltejs/kit';
import Dexie from 'dexie';
import { db } from "./db";
import type { VerbRecord } from "./types";
import { getLangDataUrl, manifest } from './dataUtils';

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
    const url = `${getLangDataUrl(lang)}/verbs/${verb.toLowerCase()}.json`;
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
        const names: string[] = [];
        await db.verbs
            .where('[lang+id]')
            .between([lang, Dexie.minKey], [lang, Dexie.maxKey])
            .limit(25)
            .each(verb => {
                names.push(verb.name);
            });

        if (names.length > 0) {
            console.log('Serving from IndexedDB');
            return names;
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
