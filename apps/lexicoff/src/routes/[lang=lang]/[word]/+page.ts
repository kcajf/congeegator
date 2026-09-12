import { storage as sqliteClient } from '$lib/sqliteClient.svelte';
import { manifest } from '$lib/dataUtils';
import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	const { lang, word } = params;

	if (!(lang in manifest.languages)) {
		error(404, { message: `Language ${lang} not supported` });
	}

	const entries = await sqliteClient.getWord(lang, word);

	return {
		lang,
		word,
		entries
	};
};
