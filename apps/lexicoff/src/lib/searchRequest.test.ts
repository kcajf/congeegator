import { describe, expect, it } from 'vitest';
import { prepareSearchRequest } from './searchRequest';
import { dictionaryWordKey } from './searchNormalization';

describe('main-thread search request preparation', () => {
	it.each([
		['IŞIK', 'ışık'],
		['İSTANBUL', 'istanbul'],
		['ISPARTA', 'ısparta']
	])('preserves %s through the caller-to-worker normalization boundary', (input, expected) => {
		const request = prepareSearchRequest('tr', ` ${input} `);
		expect(request.query).toBe(input);
		expect(dictionaryWordKey(request.query, 'tr')).toBe(expected);
		expect(request.phoneticQuery).toBe('');
	});

	it('keeps distinct Turkish I and i request identities for stale-result checks', () => {
		expect(prepareSearchRequest('tr', 'I').query).not.toBe(prepareSearchRequest('tr', 'i').query);
	});

	it('keeps the original input available for English gloss casing', () => {
		const request = prepareSearchRequest('tr', 'I');
		expect(dictionaryWordKey(request.query, 'tr')).toBe('ı');
		expect(dictionaryWordKey(request.query, 'en')).toBe('i');
	});

	it('preserves Greek spelling while providing its lowercase phonetic query', () => {
		expect(prepareSearchRequest('el', ' ΣΠΊΤΙ ')).toEqual({
			query: 'ΣΠΊΤΙ',
			phoneticQuery: 'spiti'
		});
		expect(prepareSearchRequest('el', 'SPITI').phoneticQuery).toBe('spiti');
	});

	it.each(['fr', 'ru', 'ar', 'he', 'unknown'])(
		'does not enable phonetic search for %s before an index is supported',
		(lang) => {
			expect(prepareSearchRequest(lang, 'spiti').phoneticQuery).toBe('');
		}
	);

	it('preserves decomposed Vietnamese input without generating a Greek phonetic query', () => {
		const input = 'NƯỚC'.normalize('NFD');
		const request = prepareSearchRequest('vi', input);
		expect(request).toEqual({ query: input, phoneticQuery: '' });
		expect(dictionaryWordKey(request.query, 'vi')).toBe('nước');
	});
});
