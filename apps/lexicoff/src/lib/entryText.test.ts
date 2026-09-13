import { describe, expect, it } from 'vitest';
import { boldText, linkedText, linkLabel } from './entryText';

describe('linked dictionary text', () => {
	it('leaves misparsed surface-analysis dispatchers plain in existing bundles', () => {
		expect(
			linkedText('From bewegen and ung.', [
				{ word: 'bewegen', lang: '+suf' },
				{ word: 'ung', lang: '+suf' }
			])
		).toEqual([{ text: 'From bewegen and ung.' }]);
	});
	it('uses display labels, longest matches and complete word boundaries', () => {
		const links = [
			{ word: 'house', lang: 'en' },
			{ word: 'house music', lang: 'en' },
			{ word: 'mānsiō', label: 'mānsiōnem', lang: 'la' }
		];
		const parts = linkedText('house music, household, mānsiōnem.', links);
		expect(parts.filter((p) => p.link).map((p) => p.link?.word)).toEqual(['house music', 'mānsiō']);
		expect(parts.map((p) => p.text).join('')).toBe('house music, household, mānsiōnem.');
	});
	it('leaves ambiguous historical spellings and unsafe markup as plain text', () => {
		const text = '<script>alert(1)</script> hūs';
		expect(
			linkedText(text, [
				{ word: 'hūs', lang: 'goh' },
				{ word: 'hūs', lang: 'gmh' }
			])
		).toEqual([{ text }]);
	});
	it('does not link inside Greek or astral-script words', () => {
		expect(
			linkedText('𐌖a a λόγος', [
				{ word: 'a', lang: 'en' },
				{ word: 'λόγ', lang: 'el' }
			])
				.filter((p) => p.link)
				.map((p) => p.text)
		).toEqual(['a']);
	});
	it('keeps apostrophes, hyphens and punctuation in linked terms', () => {
		expect(
			linkedText("s'empiffrer; in-house", [
				{ word: "s'empiffrer", lang: 'fr' },
				{ word: 'in-house', lang: 'en' }
			]).filter((p) => p.link)
		).toHaveLength(2);
	});
});

describe('example emphasis', () => {
	it('uses Unicode code points and merges overlapping ranges', () => {
		expect(
			boldText('𐌖 aqua', [
				[2, 5],
				[4, 6]
			])
		).toEqual([
			{ text: '𐌖 ', bold: false },
			{ text: 'aqua', bold: true }
		]);
	});
	it('ignores invalid offsets and preserves unformatted old examples', () => {
		expect(
			boldText('house', [
				[-1, 2],
				[1, 9]
			])
		).toEqual([{ text: 'house', bold: false }]);
		expect(boldText('house')).toEqual([{ text: 'house', bold: false }]);
	});
});

it('does not assign one language to repeated etymology terms with incomplete source links', () => {
	const text = 'From Hokkien 十分, compare Japanese 十分.';
	expect(linkedText(text, [{ word: '十分', lang: 'ja' }], true)).toEqual([{ text }]);
});

it('uses the source word when alternative display text contains a section fragment', () => {
	expect(linkLabel({ word: 'ψήφος', lang: 'el', label: 'psífos#Related terms' })).toBe('ψήφος');
	expect(linkLabel({ word: 'mānsiō', lang: 'la', label: 'mānsiōnem' })).toBe('mānsiōnem');
});
