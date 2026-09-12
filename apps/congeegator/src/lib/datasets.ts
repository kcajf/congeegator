import type { DataManifest, SearchIndexStorage, VerbRecord } from './types';

export function datasetKey(lang: string, hash: string) {
	return `${lang}-${hash}`;
}

export function validateDownload(
	raw: unknown,
	definition: DataManifest['languages'][string]
): asserts raw is { verbs: VerbRecord[]; searchIndex: SearchIndexStorage } {
	if (!raw || typeof raw !== 'object') throw new Error('Invalid dictionary download');
	const { verbs, searchIndex } = raw as Record<string, unknown>;
	if (!Array.isArray(verbs) || verbs.length === 0) throw new Error('Download contains no verbs');
	for (const verb of verbs) {
		if (
			!verb ||
			typeof verb.name !== 'string' ||
			!verb.name ||
			typeof verb.nameNoDiacritics !== 'string' ||
			!Number.isFinite(verb.freq) ||
			!Array.isArray(verb.conjugation) ||
			verb.conjugation.length !== definition.tenseNames.length
		) {
			throw new Error('Download has incompatible conjugation data');
		}
		for (const [i, forms] of verb.conjugation.entries()) {
			if (typeof forms === 'string') continue;
			if (
				!Array.isArray(forms) ||
				!forms.every((form) => typeof form === 'string') ||
				forms.length !== definition.tensePronouns[i].length
			) {
				throw new Error('Download has incompatible pronoun data');
			}
		}
		if (verb.gloss !== undefined && typeof verb.gloss !== 'string')
			throw new Error('Invalid gloss');
	}
	if (
		!searchIndex ||
		typeof searchIndex !== 'object' ||
		Array.isArray(searchIndex) ||
		Object.keys(searchIndex).length === 0
	)
		throw new Error('Download has no search index');
	for (const ids of Object.values(searchIndex)) {
		if (
			!Array.isArray(ids) ||
			ids.length === 0 ||
			!ids.every((id) => Number.isInteger(id) && id >= 0 && id < verbs.length)
		)
			throw new Error('Download has invalid search references');
	}
}
