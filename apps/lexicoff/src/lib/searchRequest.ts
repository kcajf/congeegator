import { toPhoneticEl } from './phonetic';

export function prepareSearchRequest(lang: string, text: string) {
	// Preserve casing until the worker applies target-language and English-gloss
	// normalization separately. Lowercasing I here would irreversibly break Turkish.
	const query = text.trim();
	return { query, phoneticQuery: lang === 'el' ? toPhoneticEl(query) : '' };
}
