import { loadSingleVerb } from '$lib/dataManager';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
    // We 'await' the data manager here
    const verbData = await loadSingleVerb(params.lang, params.verb, fetch);

    console.log(`verbData: ${verbData}`);
    return { verb: verbData };
};