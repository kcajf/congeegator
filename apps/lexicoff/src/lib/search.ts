import type { Id, SearchIndex, DictRecord } from './types';

export const MAX_PREFIX_IDS = 200;
export const MAX_SEARCH_RESULTS = 50;

export type SearchResult = {
	word: string;
	pos: string;
	matched: string;
	quality: number; // 0 = exact, 1 = diacritics-stripped, 2 = phonetic, 3 = gloss
	freq: number;
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

export function toPhoneticEl(s: string): string {
	s = stripDiacritics(s).toLowerCase();

	s = s.replace(/μπ/g, 'b');
	s = s.replace(/ντ/g, 'd');
	s = s.replace(/γκ/g, 'g');
	s = s.replace(/γγ/g, 'ng');
	s = s.replace(/τσ/g, 'ts');
	s = s.replace(/τζ/g, 'dz');

	const voiceless = new Set('πτκθσφχξψ');
	let result = '';
	let i = 0;
	while (i < s.length) {
		if (i + 1 < s.length && (s[i] === 'α' || s[i] === 'ε') && s[i + 1] === 'υ') {
			const vowelPart = s[i] === 'α' ? 'a' : 'e';
			const nextAfter = i + 2 < s.length ? s[i + 2] : null;
			if (nextAfter === null || voiceless.has(nextAfter)) {
				result += vowelPart + 'f';
			} else {
				result += vowelPart + 'v';
			}
			i += 2;
			continue;
		}
		result += s[i];
		i++;
	}
	s = result;

	s = s.replace(/αι/g, 'e');
	s = s.replace(/ει/g, 'i');
	s = s.replace(/οι/g, 'i');
	s = s.replace(/ου/g, 'U');
	s = s.replace(/υι/g, 'i');

	s = s.replace(/η/g, 'i');
	s = s.replace(/ω/g, 'o');
	s = s.replace(/υ/g, 'i');
	s = s.replace(/α/g, 'a');
	s = s.replace(/ε/g, 'e');
	s = s.replace(/ι/g, 'i');
	s = s.replace(/ο/g, 'o');

	s = s.replace(/β/g, 'v');
	s = s.replace(/γ/g, 'g');
	s = s.replace(/δ/g, 'd');
	s = s.replace(/ζ/g, 'z');
	s = s.replace(/θ/g, 'th');
	s = s.replace(/κ/g, 'k');
	s = s.replace(/λ/g, 'l');
	s = s.replace(/μ/g, 'm');
	s = s.replace(/ν/g, 'n');
	s = s.replace(/ξ/g, 'ks');
	s = s.replace(/π/g, 'p');
	s = s.replace(/ρ/g, 'r');
	s = s.replace(/σ/g, 's');
	s = s.replace(/ς/g, 's');
	s = s.replace(/τ/g, 't');
	s = s.replace(/φ/g, 'f');
	s = s.replace(/χ/g, 'ch');
	s = s.replace(/ψ/g, 'ps');

	s = s.replace(/mp/g, 'b');
	s = s.replace(/nt/g, 'd');
	s = s.replace(/gk/g, 'g');

	s = s.replace(/ph/g, 'f');
	s = s.replace(/c(?!h)/g, 'k');
	s = s.replace(/q/g, 'k');
	s = s.replace(/w/g, 'o');
	s = s.replace(/x/g, 'ch');
	s = s.replace(/(?<![ctk])h/g, 'ch');
	s = s.replace(/y/g, 'i');

	const latinVoiceless = new Set('ptksfc');
	result = '';
	i = 0;
	while (i < s.length) {
		if (i + 1 < s.length && (s[i] === 'a' || s[i] === 'e') && s[i + 1] === 'u') {
			const nextAfter = i + 2 < s.length ? s[i + 2] : null;
			if (nextAfter === null || latinVoiceless.has(nextAfter)) {
				result += s[i] + 'f';
			} else {
				result += s[i] + 'v';
			}
			i += 2;
			continue;
		}
		result += s[i];
		i++;
	}
	s = result;

	s = s.replace(/ei/g, 'i');
	s = s.replace(/ai/g, 'e');
	s = s.replace(/oi/g, 'i');
	s = s.replace(/ou/g, 'U');
	s = s.replace(/u/g, 'i');
	s = s.replace(/U/g, 'u');

	return s;
}

export function toPhonetic(lang: string, s: string): string {
	if (lang === 'el') return toPhoneticEl(s);
	return s;
}

function matchQuality(
	form: string,
	originalQuery: string,
	phoneticQuery: string,
	lang: string
): number | null {
	if (form.toLowerCase().includes(originalQuery)) return 0;
	const strippedForm = stripDiacritics(form).toLowerCase();
	const strippedQuery = stripDiacritics(originalQuery);
	if (strippedForm.includes(strippedQuery)) return 1;
	if (toPhonetic(lang, strippedForm).includes(phoneticQuery)) return 2;
	return null;
}

export function findMatches(
	entry: DictRecord,
	originalQuery: string,
	phoneticQuery: string,
	lang: string
): SearchResult[] {
	const seen = new Map<string, SearchResult>();

	const consider = (form: string) => {
		const quality = matchQuality(form, originalQuery, phoneticQuery, lang);
		if (quality === null) return;
		const key = entry.word + ':' + entry.pos;
		const existing = seen.get(key);
		if (!existing || quality < existing.quality) {
			seen.set(key, {
				word: entry.word,
				pos: entry.pos,
				matched: form,
				quality,
				freq: entry.freq
			});
		}
	};

	consider(entry.word);
	for (const form of entry.forms ?? []) {
		consider(form);
	}

	return [...seen.values()];
}

export function findGlossMatch(entry: DictRecord, glossQuery: string): SearchResult | null {
	for (const sense of entry.senses) {
		if (!sense.gloss) continue;
		const escaped = glossQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
		if (new RegExp(`(?<!\\p{L})${escaped}`, 'u').test(sense.gloss.toLowerCase())) {
			return {
				word: entry.word,
				pos: entry.pos,
				matched: sense.gloss,
				quality: 3,
				freq: entry.freq
			};
		}
	}
	return null;
}
