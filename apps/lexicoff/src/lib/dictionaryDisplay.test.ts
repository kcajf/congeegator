import { describe, expect, it } from 'vitest';
import {
	entryPronunciations,
	formUsageLabels,
	formReadings,
	formGroups
} from './dictionaryDisplay';
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

describe('complete form readings', () => {
	it('keeps formality attached to its own reading and removes exact duplicates', () => {
		const record: DictRecord = {
			...entry,
			forms: ['lenne'],
			formDetails: [
				{
					form: 'lenne',
					kind: 'inflection',
					readings: [
						{ grammar: ['second person', 'singular', 'conditional'], qualifiers: ['formal'] },
						{ grammar: ['third person', 'singular', 'conditional'] },
						{ grammar: ['third person', 'singular', 'conditional'] }
					]
				}
			]
		};
		expect(formReadings(record).get('lenne')).toEqual([
			'second person singular conditional · formal',
			'third person singular conditional'
		]);
	});
	it('keeps legacy flattened labels as one reading without guessing their scope', () => {
		expect(
			formReadings({ ...entry, formDetails: [{ form: 'x', tags: ['plural', 'rare'] }] }).get('x')
		).toEqual(['plural, rare']);
	});
	it('groups only visible spellings without discarding unknown or unlabelled forms', () => {
		const record: DictRecord = {
			...entry,
			forms: ['a', 'b', 'c', 'd', 'e'],
			formDetails: [
				{ form: 'a', kind: 'inflection' },
				{ form: 'b', kind: 'variant' },
				{ form: 'c', kind: 'related' }
			]
		};
		expect(formGroups(record, record.forms!.slice(0, 4))).toEqual([
			{ label: 'Inflections', forms: ['a'] },
			{ label: 'Spelling variants', forms: ['b'] },
			{ label: 'Related formations', forms: ['c'] },
			{ label: 'Other forms', forms: ['d'] }
		]);
	});
});
