import { describe, expect, it } from 'vitest';
import { findMatches, prefixLookup, stripDiacritics, toPhoneticEl } from './search';
import type { SearchIndex, VerbRecord } from './types';

function makeVerb(overrides: Partial<VerbRecord> & Pick<VerbRecord, 'name'>): VerbRecord {
	return {
		id: 0,
		lang: 'fr',
		nameNoDiacritics: overrides.name,
		conjugation: [],
		frIsAspirated: null,
		...overrides
	};
}

describe('prefixLookup', () => {
	it('returns [] for an empty index', () => {
		const index: SearchIndex = new Map();
		expect(prefixLookup(index, 'manger')).toEqual([]);
	});

	it('returns [] when no prefix matches', () => {
		const index: SearchIndex = new Map([['z', [1]]]);
		expect(prefixLookup(index, 'manger')).toEqual([]);
	});

	it('returns IDs for an exact match', () => {
		const index: SearchIndex = new Map([['manger', [5, 10]]]);
		expect(prefixLookup(index, 'manger')).toEqual([5, 10]);
	});

	it('returns IDs for the longest matching prefix', () => {
		const index: SearchIndex = new Map([
			['m', [1]],
			['ma', [2]],
			['man', [3, 4]]
		]);
		expect(prefixLookup(index, 'manger')).toEqual([3, 4]);
	});

	it('falls back to a shorter prefix when longest does not match', () => {
		const index: SearchIndex = new Map([
			['m', [1, 2]],
			['man', [3]]
		]);
		expect(prefixLookup(index, 'maz')).toEqual([1, 2]);
	});

	it('returns [] for an empty query', () => {
		const index: SearchIndex = new Map([['m', [1]]]);
		expect(prefixLookup(index, '')).toEqual([]);
	});
});

describe('findMatches', () => {
	it('matches the verb name exactly', () => {
		const verb = makeVerb({ name: 'manger' });
		expect(findMatches(verb, 'manger', 'manger', 'fr')).toEqual([
			{ root: 'manger', matched: 'manger', quality: 0 }
		]);
	});

	it('returns all matching forms', () => {
		const verb = makeVerb({
			name: 'manger',
			conjugation: ['mange', 'mangeons']
		});
		const results = findMatches(verb, 'man', 'man', 'fr');
		expect(results).toContainEqual({ root: 'manger', matched: 'manger', quality: 0 });
		expect(results).toContainEqual({ root: 'manger', matched: 'mange', quality: 0 });
		expect(results).toContainEqual({ root: 'manger', matched: 'mangeons', quality: 0 });
	});

	it('handles array conjugation forms', () => {
		const verb = makeVerb({
			name: 'aller',
			conjugation: [['va', 'vas'], 'allons']
		});
		expect(findMatches(verb, 'va', 'va', 'fr')).toContainEqual({
			root: 'aller',
			matched: 'va',
			quality: 0
		});
	});

	it('returns empty array when nothing matches', () => {
		const verb = makeVerb({ name: 'manger', conjugation: ['mange'] });
		expect(findMatches(verb, 'xyz', 'xyz', 'fr')).toEqual([]);
	});

	it('returns both exact and diacritics-stripped matches', () => {
		const verb = makeVerb({
			name: 'manger',
			conjugation: ['mange', 'mangé']
		});
		const results = findMatches(verb, 'mange', 'mange', 'fr');
		expect(results).toContainEqual({ root: 'manger', matched: 'mange', quality: 0 });
		expect(results).toContainEqual({ root: 'manger', matched: 'mangé', quality: 1 });
	});

	it('matches accented verb name with stripped query', () => {
		const verb = makeVerb({ name: 'être', nameNoDiacritics: 'etre', conjugation: ['suis'] });
		expect(findMatches(verb, 'etre', 'etre', 'fr')).toContainEqual({
			root: 'être',
			matched: 'être',
			quality: 1
		});
	});

	it('matches Greek verb via phonetic Latin query', () => {
		const verb = makeVerb({ name: 'κάνω', lang: 'el', conjugation: ['κάνεις', 'κάνει'] });
		expect(findMatches(verb, 'kano', 'kano', 'el')).toContainEqual({
			root: 'κάνω',
			matched: 'κάνω',
			quality: 2
		});
	});

	it('gives exact diacritic match quality 0 and stripped match quality 1', () => {
		const verbWithDiacritics = makeVerb({ name: 'abändern' });
		const verbWithout = makeVerb({ name: 'abandonnier' });
		// Query "abä" (with diacritic) should give quality 0 for abändern, quality 1 for abandonnier
		expect(findMatches(verbWithDiacritics, 'abä', 'aba', 'fr')).toContainEqual({
			root: 'abändern',
			matched: 'abändern',
			quality: 0
		});
		expect(findMatches(verbWithout, 'abä', 'aba', 'fr')).toContainEqual({
			root: 'abandonnier',
			matched: 'abandonnier',
			quality: 1
		});
	});
});

describe('stripDiacritics', () => {
	it('removes accents from French characters', () => {
		expect(stripDiacritics('être')).toBe('etre');
		expect(stripDiacritics('préféré')).toBe('prefere');
	});

	it('removes accents from Greek characters', () => {
		expect(stripDiacritics('τρώω')).toBe('τρωω');
	});

	it('leaves ASCII strings unchanged', () => {
		expect(stripDiacritics('manger')).toBe('manger');
	});
});

describe('toPhoneticEl', () => {
	it('converts consonant bigrams', () => {
		expect(toPhoneticEl('μπαίνω')).toBe('beno');
		expect(toPhoneticEl('ντύνω')).toBe('dino');
		expect(toPhoneticEl('γκρεμίζω')).toBe('gremizo');
		expect(toPhoneticEl('τσάι')).toBe('tse');
		expect(toPhoneticEl('τζάκι')).toBe('dzaki');
	});

	it('handles αυ/ευ voicing before voiceless consonants', () => {
		expect(toPhoneticEl('αυτός')).toBe('aftos');
		expect(toPhoneticEl('ευτυχία')).toBe('eftichia');
	});

	it('handles αυ/ευ voicing before voiced consonants', () => {
		expect(toPhoneticEl('αυλή')).toBe('avli');
		expect(toPhoneticEl('ευλογώ')).toBe('evlogo');
	});

	it('handles αυ/ευ at end of word', () => {
		expect(toPhoneticEl('ευ')).toBe('ef');
	});

	it('converts vowel digraphs', () => {
		expect(toPhoneticEl('αίμα')).toBe('ema');
		expect(toPhoneticEl('είμαι')).toBe('ime');
		expect(toPhoneticEl('οίκος')).toBe('ikos');
		expect(toPhoneticEl('ούτε')).toBe('ute');
	});

	it('converts single vowels', () => {
		expect(toPhoneticEl('ήμουν')).toBe('imun');
		expect(toPhoneticEl('ώρα')).toBe('ora');
	});

	it('converts real verbs', () => {
		expect(toPhoneticEl('κάνω')).toBe('kano');
		expect(toPhoneticEl('θέλω')).toBe('thelo');
		expect(toPhoneticEl('αγαπώ')).toBe('agapo');
		expect(toPhoneticEl('τρώω')).toBe('troo');
		expect(toPhoneticEl('έχω')).toBe('echo');
		expect(toPhoneticEl('ξέρω')).toBe('ksero');
		expect(toPhoneticEl('ψάχνω')).toBe('psachno');
	});

	it('passes through Latin input', () => {
		expect(toPhoneticEl('kano')).toBe('kano');
		expect(toPhoneticEl('thelo')).toBe('thelo');
	});

	it('normalizes Latin characters', () => {
		expect(toPhoneticEl('cyma')).toBe('kima');
		expect(toPhoneticEl('phyllo')).toBe('fillo');
		expect(toPhoneticEl('kueri')).toBe('kieri');
	});

	it('converts Latin consonant bigrams', () => {
		expect(toPhoneticEl('mpeno')).toBe('beno');
		expect(toPhoneticEl('ntino')).toBe('dino');
		expect(toPhoneticEl('gkremizo')).toBe('gremizo');
	});

	it('treats x, h, and w as chi/omega', () => {
		expect(toPhoneticEl('exo')).toBe('echo');
		expect(toPhoneticEl('psaxno')).toBe('psachno');
		expect(toPhoneticEl('eho')).toBe('echo');
		expect(toPhoneticEl('eiha')).toBe('icha');
		expect(toPhoneticEl('thelo')).toBe('thelo'); // th stays as th
		expect(toPhoneticEl('kanw')).toBe('kano'); // w as omega
	});

	it('converts Latin full words', () => {
		expect(toPhoneticEl('mirizei')).toBe('mirizi');
		expect(toPhoneticEl('milousa')).toBe('milusa');
		expect(toPhoneticEl('upoferame')).toBe('ipoferame');
	});

	it('collapses Latin vowel digraphs', () => {
		expect(toPhoneticEl('eimai')).toBe('ime');
		expect(toPhoneticEl('imai')).toBe('ime');
		expect(toPhoneticEl('oikos')).toBe('ikos');
		expect(toPhoneticEl('oute')).toBe('ute');
	});

	it('applies Latin au/eu voicing', () => {
		expect(toPhoneticEl('autos')).toBe('aftos');
		expect(toPhoneticEl('euro')).toBe('evro');
		expect(toPhoneticEl('eu')).toBe('ef');
		expect(toPhoneticEl('avli')).toBe('avli');
	});

	it('handles empty string', () => {
		expect(toPhoneticEl('')).toBe('');
	});

	it('converts γγ', () => {
		expect(toPhoneticEl('αγγελία')).toBe('angelia');
	});
});
