import { loadSingleVerb } from '$lib/dataLoading';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
    const verbData = await loadSingleVerb(params.lang, params.verb, fetch);
    return { verb: verbData };
};