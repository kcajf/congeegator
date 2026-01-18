import { loadVerbIndex } from '$lib/dataManager';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params , fetch}) => {
    try {
        const verbs = await loadVerbIndex(params.lang, fetch);
        return {
            lang: params.lang,
            verbs: verbs // Array of strings: ['manger', 'finir', ...]
        };
    } catch (e) {
        console.error("DEBUG: loadVerbIndex failed because:", e);
        throw error(404, `Language ${params.lang} not supported`);
    }
};