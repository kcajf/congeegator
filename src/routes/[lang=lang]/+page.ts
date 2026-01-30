import { loadVerbIndex, manifest } from "$lib/dataUtils";
import { error } from "@sveltejs/kit";
import type { PageLoad } from "./$types";

export const prerender = true;

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