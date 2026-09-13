import { expect, it } from 'vitest';
import { compareLanguages } from './languageOrder';

it('interleaves native scripts with Latin names by pronunciation', () => {
	const languages = [
		{ code: 'ru', name: 'русский' },
		{ code: 'el', name: 'ελληνικά' },
		{ code: 'he', name: 'עברית' },
		{ code: 'en', name: 'English' },
		{ code: 'et', name: 'eesti' },
		{ code: 'it', name: 'italiano' },
		{ code: 'ro', name: 'română' }
	];
	expect(languages.toSorted(compareLanguages).map((lang) => lang.code)).toEqual([
		'et',
		'el',
		'en',
		'it',
		'he',
		'ro',
		'ru'
	]);
	expect(languages[1].name).toBe('ελληνικά');
});
