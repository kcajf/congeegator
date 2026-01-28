import { browser } from "$app/environment";
import { PUBLIC_R2_URL } from "$env/static/public";
import { manifest } from "$lib/dataManager";
import { db } from "$lib/db";
import { error } from "@sveltejs/kit";
import type { PageLoad } from "./$types";

export const prerender = true;

async function loadVerbIndex(lang: string, fetcher: typeof fetch): Promise<string[]> {
    if (!(lang in manifest.languages)) {
        error(404, { message: `Language ${lang} not supported` });
    }

    if (browser) {
        const localVerbs = await db.verbs.where('lang').equals(lang).primaryKeys(); // Just get the [lang+name] keys to be fast
        if (localVerbs.length > 0) {
            console.log('Serving from IndexedDB');
            // Extract just the 'name' part from the compound key
            return localVerbs.map(key => (key as string[])[1]).sort();
        }
    }
    
    // 2. SSR OR CACHE MISS: Fetch from R2 Public URL
    // This runs on the Cloudflare Worker during the initial page load
    // but runs in the browser if IndexedDB was empty.
    const url = `${PUBLIC_R2_URL}/data/v1/${lang}/index.json`;
    console.log(`Fetching ${url}`)
    const res = await fetcher(url);
    
    if (!res.ok) throw new Error(`Error loading index for ${lang}`);

    const verbs: string[] = await res.json();
    return verbs;
}

export const load: PageLoad = async ({ params, fetch }) => {
    const lang = params.lang;
    if (!(lang in manifest.languages)) {
        error(404, { message: `Language ${lang} not supported` });
    }

    const verbs = await loadVerbIndex(params.lang, fetch);
    return {
        lang: params.lang,
        verbs: verbs,
        langName: manifest.languages[params.lang].name
    };
}