import { describe, expect, it } from 'vitest';
import {
	dictionarySearchKey,
	dictionaryWordKey,
	prefixMatch,
	searchTokens
} from './searchNormalization';

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
		['tr', 'İSTANBUL'.normalize('NFD'), 'istanbul'],
		['az', 'IŞIQ', 'ışıq'],
		['az', 'İŞIQ', 'işıq']
	])('normalizes %s input %s', (lang, input, expected) => {
		expect(dictionaryWordKey(input, lang)).toBe(expected);
	});

	it.each([
		['ar', 'كِتَـاب', 'كتاب'],
		['ar', 'آب', 'آب'],
		['ur', 'كِتاب', 'کتاب'],
		['ja', 'タベル', 'たべる'],
		['ja', 'ﾀﾍﾞﾙ', 'たべる'],
		['bn', 'পানি', 'পানি'],
		['pa', 'ਪਾਣੀ', 'ਪਾਣੀ'],
		['te', 'నీరు', 'నీరు'],
		['ta', 'நீர்', 'நீர்'],
		['th', 'น้ำ', 'น้ำ'],
		['grc', 'ὝΔΩΡ', 'υδωρ'],
		['grc', 'ΛΌΓΟΣ', 'λογοσ'],
		['he', 'שָׁלוֹם', 'שלום'],
		['fa', 'كِتاب', 'کتاب'],
		['fa', 'خانه‌ها', 'خانهها'],
		['fa', 'آب', 'آب'],
		['hi', 'पानी', 'पानी'],
		['sa', 'कर्म', 'कर्म'],
		['uk', 'ЇСТИ', 'їсти'],
		['el', 'ΝΕΡΌ', 'νερό']
	])('normalizes only intended %s search aliases', (lang, word, expected) => {
		expect(dictionarySearchKey(word.normalize('NFD'), lang)).toBe(expected);
	});

	it('keeps exact Greek homographs and pointed Hebrew display keys distinct', () => {
		expect(dictionaryWordKey('ἄλλα', 'grc')).not.toBe(dictionaryWordKey('ἀλλά', 'grc'));
		expect(dictionarySearchKey('ἄλλα', 'grc')).toBe(dictionarySearchKey('ἀλλά', 'grc'));
		expect(dictionaryWordKey('שָׁלוֹם', 'he')).toBe('שָׁלוֹם');
	});

	it('preserves Indic marks and splits ZWNJ into separate FTS terms', () => {
		expect(prefixMatch(searchTokens('पानी'))).toBe('"पानी"*');
		expect(prefixMatch(searchTokens('घर में'))).toBe('"घर" "में"*');
		expect(prefixMatch(searchTokens('خانه‌ها'))).toBe('"خانه" "ها"*');
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
