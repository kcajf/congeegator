import { loadVerbIndexServer, manifest } from '$lib/dataManager';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, platform }) => {
    const verbs = await loadVerbIndexServer(params.lang, platform);
    return {
        lang: params.lang,
        verbs: verbs,
        langName: manifest.languages[params.lang].name
    };
};