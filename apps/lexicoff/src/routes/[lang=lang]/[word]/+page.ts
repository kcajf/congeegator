import * as sqliteClient from '$lib/sqliteClient';
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

	if (entries.length === 0) {
		error(404, {
			message: `Word "${word}" not found. Is ${manifest.languages[lang].name} installed?`
		});
	}

	return {
		lang,
		word,
		entries
	};
};
