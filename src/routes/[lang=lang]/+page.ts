import { loadVerbIndexBrowser, manifest } from "$lib/dataManager";
import type { PageLoad } from "./$types";

export const load: PageLoad = async ({ data, params}) => {
    // 'data' here is what was returned from +page.server.ts
    const verbs = await loadVerbIndexBrowser(params.lang, data.verbs);
    return {
        lang: params.lang,
        verbs: verbs,
        langName: manifest.languages[params.lang].name
    };
}