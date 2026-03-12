import { describe, expect, it } from 'vitest';
import { findBestMatch, prefixLookup, stripDiacritics } from './search';
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
		expect(findBestMatch(verb, 'manger')).toEqual({ root: 'manger', matched: 'manger' });
	});

	it('prefers a shorter conjugation over a longer name', () => {
		const verb = makeVerb({
			name: 'manger',
			conjugation: ['mange', 'mangeons']
		});
		expect(findBestMatch(verb, 'man')).toEqual({ root: 'manger', matched: 'mange' });
	});

	it('handles array conjugation forms', () => {
		const verb = makeVerb({
			name: 'aller',
			conjugation: [['va', 'vas'], 'allons']
		});
		expect(findBestMatch(verb, 'va')).toEqual({ root: 'aller', matched: 'va' });
	});

	it('returns null when nothing matches', () => {
		const verb = makeVerb({ name: 'manger', conjugation: ['mange'] });
		expect(findBestMatch(verb, 'xyz')).toBeNull();
	});

	it('is case insensitive', () => {
		const verb = makeVerb({ name: 'Manger', conjugation: ['Mange'] });
		expect(findBestMatch(verb, 'man')).toEqual({ root: 'Manger', matched: 'Mange' });
	});

	it('matches accented verb name with stripped query', () => {
		const verb = makeVerb({ name: 'être', nameNoDiacritics: 'etre', conjugation: ['suis'] });
		expect(findBestMatch(verb, 'etre')).toEqual({ root: 'être', matched: 'être' });
	});

	it('matches accented conjugation form with stripped query', () => {
		const verb = makeVerb({
			name: 'préférer',
			nameNoDiacritics: 'preferer',
			conjugation: ['préfère', 'préférons']
		});
		expect(findBestMatch(verb, 'prefere')).toEqual({ root: 'préférer', matched: 'préfère' });
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
