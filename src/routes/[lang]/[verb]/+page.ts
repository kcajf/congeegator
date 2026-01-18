import { loadSingleVerb } from '$lib/dataManager';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
    try {
        // We 'await' the data manager here
        const verbData = await loadSingleVerb(params.lang, params.verb);
        
        return {
            verb: verbData
        };
    } catch (e) {
        // If the data manager throws an error (like a 404), 
        // SvelteKit will show the nearest +error.svelte page.
        throw error(404, 'Verb not found');
    }
};