import { describe, expect, it } from 'vitest';
import { dictionaryWordKey, prefixMatch, searchTokens } from './searchNormalization';

describe('dictionary query normalization', () => {
	it.each([
		['vi', 'TIẾNG VIỆT', 'tiếng việt'],
		['vi', 'tiếng việt'.normalize('NFD'), 'tiếng việt'],
		['uk', 'ЇСТИ', 'їсти'],
		['ru', 'МОСКВА', 'москва'],
		['pl', 'ŁÓDŹ', 'łódź'],
		['la', 'ĀMŌ', 'āmō'],
		['tr', 'IŞIK', 'ışık'],
		['tr', 'İSTANBUL', 'istanbul'],
		['tr', 'İSTANBUL'.normalize('NFD'), 'istanbul']
	])('normalizes %s input %s', (lang, input, expected) => {
		expect(dictionaryWordKey(input, lang)).toBe(expected);
	});

	it('retains meaningful marks and Cyrillic letters without splitting a word', () => {
		expect(searchTokens('tiếng Việt'.normalize('NFD'))).toEqual(['tiếng', 'Việt']);
		expect(searchTokens('молоко́')).toEqual(['молоко́']);
		expect(searchTokens('їсти'.normalize('NFD'))).toEqual(['їсти']);
	});

	it('keeps distinct Turkish letters and English gloss casing separate', () => {
		expect(dictionaryWordKey('I', 'tr')).toBe('ı');
		expect(dictionaryWordKey('İ', 'tr')).toBe('i');
		expect(dictionaryWordKey('I', 'en')).toBe('i');
	});

	it('quotes FTS keywords and separates punctuation without phrase queries', () => {
		expect(prefixMatch(searchTokens('self-service OR "NEAR"'))).toBe(
			'"self" "service" "OR" "NEAR"*'
		);
		expect(searchTokens('́ — * "')).toEqual([]);
	});
});
