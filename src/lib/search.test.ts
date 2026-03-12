import { describe, expect, it } from 'vitest';
import { findBestMatch, prefixLookup, stripDiacritics, toPhoneticEl } from './search';
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

describe('findBestMatch', () => {
	it('matches the verb name exactly', () => {
		const verb = makeVerb({ name: 'manger' });
		expect(findBestMatch(verb, 'manger', 'fr')).toEqual({ root: 'manger', matched: 'manger' });
	});

	it('prefers a shorter conjugation over a longer name', () => {
		const verb = makeVerb({
			name: 'manger',
			conjugation: ['mange', 'mangeons']
		});
		expect(findBestMatch(verb, 'man', 'fr')).toEqual({ root: 'manger', matched: 'mange' });
	});

	it('handles array conjugation forms', () => {
		const verb = makeVerb({
			name: 'aller',
			conjugation: [['va', 'vas'], 'allons']
		});
		expect(findBestMatch(verb, 'va', 'fr')).toEqual({ root: 'aller', matched: 'va' });
	});

	it('returns null when nothing matches', () => {
		const verb = makeVerb({ name: 'manger', conjugation: ['mange'] });
		expect(findBestMatch(verb, 'xyz', 'fr')).toBeNull();
	});

	it('is case insensitive', () => {
		const verb = makeVerb({ name: 'Manger', conjugation: ['Mange'] });
		expect(findBestMatch(verb, 'man', 'fr')).toEqual({ root: 'Manger', matched: 'Mange' });
	});

	it('matches accented verb name with stripped query', () => {
		const verb = makeVerb({ name: 'être', nameNoDiacritics: 'etre', conjugation: ['suis'] });
		expect(findBestMatch(verb, 'etre', 'fr')).toEqual({ root: 'être', matched: 'être' });
	});

	it('matches accented conjugation form with stripped query', () => {
		const verb = makeVerb({
			name: 'préférer',
			nameNoDiacritics: 'preferer',
			conjugation: ['préfère', 'préférons']
		});
		expect(findBestMatch(verb, 'prefere', 'fr')).toEqual({
			root: 'préférer',
			matched: 'préfère'
		});
	});

	it('matches Greek verb via phonetic Latin query', () => {
		const verb = makeVerb({ name: 'κάνω', lang: 'el', conjugation: ['κάνεις', 'κάνει'] });
		expect(findBestMatch(verb, 'kano', 'el')).toEqual({ root: 'κάνω', matched: 'κάνω' });
	});

	it('matches Greek verb via approximate Greek query', () => {
		const verb = makeVerb({ name: 'κάνω', lang: 'el', conjugation: ['κάνεις'] });
		// query with wrong omega/omicron should still match via phonetic
		expect(findBestMatch(verb, 'κανο', 'el')).toEqual({ root: 'κάνω', matched: 'κάνω' });
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
		expect(toPhoneticEl('kueri')).toBe('kueri');
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
