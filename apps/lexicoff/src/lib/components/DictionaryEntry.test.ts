import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import DictionaryEntry from './DictionaryEntry.svelte';
import type { DictRecord } from '../types';

const entry: DictRecord = {
	id: 1,
	word: 'אב',
	lang: 'he',
	pos: 'noun',
	senses: [{ gloss: 'father', tags: ['Biblical-Hebrew'], examples: ['אב ובנו'] }],
	freq: 0,
	forms: ['אבות', 'אבי'],
	formDetails: [{ form: 'אבות', tags: ['rare'] }],
	pronunciations: [
		{ ipa: '/ʔav/', label: 'Biblical Hebrew' },
		{ ipa: '/av/', label: 'Modern Hebrew' }
	]
};

describe('dictionary entry display', () => {
	it('separates period labels from IPA and displays ordinary ordinal dates', () => {
		const { body } = render(DictionaryEntry, {
			props: {
				entry: { ...entry, pronunciations: [{ ipa: '/hý.dɔːr/', label: '5ᵗʰ BCE Attic' }] },
				lang: 'grc'
			}
		});
		expect(body).toContain('(5th BCE Attic)');
		expect(body).not.toContain('ᵗʰ');
	});

	it('renders labelled pronunciations and isolates mixed-direction forms', () => {
		const { body } = render(DictionaryEntry, { props: { entry, lang: 'he' } });
		expect(body).toContain('Biblical Hebrew');
		expect(body).toContain('Modern Hebrew');
		expect(body).toContain('dir="ltr"');
		expect(body).toMatch(/<bdi lang="he">אבות<\/bdi>/);
		expect(body).toMatch(/<bdi lang="he">אבי<\/bdi>/);
		expect(body).toContain('(rare)');
		expect(body).toMatch(/lang="he" dir="auto"/);
	});

	it('does not borrow the previous entry pronunciation or etymology for a homograph', () => {
		const other = {
			...entry,
			id: 2,
			pos: 'verb',
			pronunciations: undefined,
			pronunciation: undefined,
			etymology: undefined
		};
		const { body } = render(DictionaryEntry, { props: { entry: other, lang: 'he' } });
		expect(body).not.toContain('aria-label="Pronunciation"');
		expect(body).not.toContain('Etymology');
	});
});
