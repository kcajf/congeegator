import { describe, expect, it } from 'vitest';
import { entryPronunciations, formUsageLabels } from './dictionaryDisplay';
import type { DictRecord } from './types';

const entry: DictRecord = {
	id: 1,
	word: 'λόγος',
	lang: 'grc',
	pos: 'noun',
	senses: [{ gloss: 'word' }],
	freq: 0
};

describe('dictionary usage metadata', () => {
	it('keeps period-specific pronunciations even when their IPA is identical', () => {
		const pronunciations = [
			{ ipa: '/logos/', label: 'Classical Attic' },
			{ ipa: '/logos/', label: 'Koine' }
		];
		expect(entryPronunciations({ ...entry, pronunciation: '/legacy/', pronunciations })).toEqual(
			pronunciations
		);
	});

	it('supports older downloads and leaves missing pronunciation absent', () => {
		expect(entryPronunciations({ ...entry, pronunciation: '/legacy/' })).toEqual([
			{ ipa: '/legacy/' }
		]);
		expect(entryPronunciations(entry)).toEqual([]);
	});

	it('combines usage details without changing lookup spellings or inventing annotations', () => {
		const record = {
			...entry,
			forms: ['λόγου', 'λόγοι'],
			formDetails: [
				{ form: 'λόγου', tags: ['archaic', 'North-Wales'] },
				{ form: 'λόγου', tags: ['archaic', 'literary'] }
			]
		};
		const labels = formUsageLabels(record);
		expect(labels.get('λόγου')).toBe('archaic, North Wales, literary');
		expect(labels.has('λόγοι')).toBe(false);
		expect(record.forms).toEqual(['λόγου', 'λόγοι']);
	});
});
