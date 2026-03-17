import { loadWord } from '$lib/dataLoading';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	const entries = await loadWord(params.lang, params.word, fetch);
	return {
		lang: params.lang,
		word: params.word,
		entries
	};
};
