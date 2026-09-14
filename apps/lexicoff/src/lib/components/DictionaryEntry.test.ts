import { render } from 'svelte/server';
import { describe, expect, it, vi } from 'vitest';
import DictionaryEntry from './DictionaryEntry.svelte';
import type { DictRecord } from '../types';

vi.mock('$lib/sqliteClient.svelte', () => ({
	storage: { languages: { grc: { status: 'ready' } } }
}));

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

	it('renders labelled pronunciations and isolates mixed-direction examples', () => {
		const { body } = render(DictionaryEntry, { props: { entry, lang: 'he' } });
		expect(body).toContain('Biblical Hebrew');
		expect(body).toContain('Modern Hebrew');
		expect(body).toContain('dir="ltr"');
		expect(body).toMatch(/lang="he" dir="auto"/);
	});

	it('leaves large form lists unrendered until opened', () => {
		const forms = Array.from({ length: 2000 }, (_, i) => `large-form-${i}`);
		const { body } = render(DictionaryEntry, {
			props: { entry: { ...entry, forms }, lang: 'he' }
		});
		expect(body).toMatch(/Forms <span[^>]*>2000<\/span>/);
		expect(body).not.toContain('large-form-');
		expect(body).not.toContain('Show 40 more');
		expect(body).not.toContain('Filter forms');
		expect(body).not.toMatch(/<details[^>]*\sopen(?:\s|>|=)/);
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

	it('preserves linked senses, structured RTL examples, and collapsed rich details', () => {
		const rich: DictRecord = {
			...entry,
			matchedForm: 'אבות',
			senses: [
				{
					gloss: 'father',
					links: [{ word: 'father', lang: 'en' }],
					tags: ['rare'],
					topics: ['kinship'],
					qualifier: 'Biblical Hebrew',
					synonyms: [{ word: 'אבא', lang: 'he' }],
					examples: [
						{
							text: 'אב ובנו',
							translation: 'a father and his son',
							bold: [[0, 2]],
							translationBold: [[2, 8]]
						},
						'אב אחר'
					]
				}
			],
			etymology: 'Related to abba.',
			details: {
				etymologyLinks: [{ word: 'abba', lang: 'en' }],
				related: [{ word: 'אבא', lang: 'he' }],
				derived: [{ word: 'אבהות', lang: 'he' }]
			}
		};
		const { body } = render(DictionaryEntry, {
			props: { entry: rich, lang: 'he', label: 'Noun 2' }
		});
		expect(body).toContain('id="entry-1"');
		expect(body).toContain('Noun 2');
		expect(body).toContain('Found under');
		expect(body).toContain('https://en.wiktionary.org/wiki/father');
		expect(body).toContain('rare, kinship, Biblical Hebrew');
		expect(body).toMatch(/<strong[^>]*>אב<\/strong>/);
		expect(body).toMatch(/<strong[^>]*>father<\/strong>/);
		expect(body).toMatch(/class="original[^"]*" lang="he" dir="auto"/);
		expect(body).toMatch(/class="translation[^"]*" lang="en" dir="auto"/);
		expect(body).toContain('1 more example');
		expect(body).toContain('Related words');
		expect(body).toContain('Derived words');
		expect(body).toContain('https://en.wiktionary.org/wiki/abba');
		expect(body).not.toMatch(/<details[^>]*\sopen(?:\s|>|=)/);
		expect(body).not.toContain('Filter forms');
		expect(body).not.toContain('[object Object]');
	});
});

it('keeps unverified local etymology destinations plain while preserving external links', () => {
	const { body } = render(DictionaryEntry, {
		props: {
			entry: {
				...entry,
				etymology: 'From σπίτιν, ultimately hospitium.',
				details: {
					etymologyLinks: [
						{ word: 'σπίτιν', lang: 'gkm' },
						{ word: 'hospitium', lang: 'la' }
					]
				}
			},
			lang: 'el'
		}
	});
	expect(body.replace(/<!--.*?-->/g, '')).toContain('From σπίτιν, ultimately');
	expect(body).not.toContain(encodeURIComponent('σπίτιν'));
	expect(body).toContain('https://en.wiktionary.org/wiki/hospitium');
});
