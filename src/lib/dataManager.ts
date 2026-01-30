import { browser } from '$app/environment';
import { PUBLIC_R2_URL } from '$env/static/public';
import manifestRaw from '$lib/data-manifest.json';
import { error } from '@sveltejs/kit';
import Dexie from 'dexie';
import { db } from "./db";
import type { DataManifest, VerbRecord } from "./types";

export const manifest = manifestRaw as DataManifest;

const DATA_VERSION = 1;

export function getLangDataUrl(langCode: string) {
    return `${PUBLIC_R2_URL}/data/v${DATA_VERSION}/${langCode}-${manifest.languages[langCode].dataHash}`
}

export function langName(langCode: string) {
    return manifest.languages[langCode].name;
}

let worker_: Worker | undefined;

export const getWorker = (): Worker | undefined => {
    if (!browser) {
        return;
    }

    if (worker_) return worker_;

    // The 'new URL' syntax is recognized by Vite to bundle the worker file separately
    worker_ = new Worker(new URL('./sync.worker.ts', import.meta.url), {
        type: 'module'
    });

    worker_.onmessage = (e) => {
        // Handle messages...
        const { type, lang, percent, error } = e.data;

        if (type === 'PROGRESS') {
            console.log(`${lang} loading: ${percent}%`)
        }

        if (type === 'COMPLETE') {
            console.log(`${lang} loading: complete`)
        }

        if (type === 'ERROR') {
            console.log(`${lang} loading: error ${error}`)
        }
    };
    
    return worker_;
}

// initialise it early
getWorker();

export function triggerLangSync(lang: string) {
    const worker = getWorker();
    if (!worker) {
        console.warn('Worker not initialized. Are you on the server?');
        return;
    }
    console.log("Trigger language sync " + lang);
    worker.postMessage({ lang });
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
