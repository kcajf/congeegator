import type { Id, SearchIndex, VerbRecord } from './types';

export type SearchResult = {
	root: string;
	matched: string;
};

export function stripDiacritics(s: string): string {
	return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

export function prefixLookup(index: SearchIndex, query: string): Id[] {
	for (let i = query.length; i > 0; i--) {
		const prefix = query.slice(0, i);
		if (index.has(prefix)) {
			return index.get(prefix)!;
		}
	}
	return [];
}

export function findBestMatch(verb: VerbRecord, query: string): SearchResult | null {
	let best: string | null = null;

	if (stripDiacritics(verb.name).toLowerCase().includes(query)) {
		best = verb.name;
	}

	for (const entry of verb.conjugation) {
		const forms = Array.isArray(entry) ? entry : [entry];
		for (const form of forms) {
			if (stripDiacritics(form).toLowerCase().includes(query)) {
				if (!best || form.length < best.length) {
					best = form;
				}
			}
		}
		if (best?.length === query.length) break;
	}

	return best ? { root: verb.name, matched: best } : null;
}
