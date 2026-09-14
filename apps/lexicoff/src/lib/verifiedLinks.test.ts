import { expect, it, vi } from 'vitest';
import { verifiedLocalLinks } from './verifiedLinks';
import { localLinkLanguage } from './linkLanguage';
import { linkedText } from './entryText';

it('leaves missing Greek etymology terms plain and retains exact headword links', async () => {
	const links = [
		{ word: 'σπίτιν', lang: 'gkm' },
		{ word: 'ὁσπίτιον', lang: 'grc' },
		{ word: 'οικία', lang: 'el' }
	];
	const lookup = vi.fn<(lang: string, words: string[]) => Promise<string[]>>(async (lang) =>
		lang === 'grc' ? ['ὁσπίτιον'] : ['οικία']
	);
	const verified = await verifiedLocalLinks(
		links,
		(link) => localLinkLanguage(link, (code) => ['grc', 'el'].includes(code)),
		lookup
	);
	expect(lookup.mock.calls).toEqual([
		['grc', ['σπίτιν', 'ὁσπίτιον']],
		['el', ['οικία']]
	]);
	const parts = linkedText('From σπίτιν, from ὁσπίτιον; modern οικία.', verified, true);
	expect(parts.map((part) => part.text).join('')).toBe('From σπίτιν, from ὁσπίτιον; modern οικία.');
	expect(parts.filter((part) => part.link).map((part) => part.link?.word)).toEqual([
		'ὁσπίτιον',
		'οικία'
	]);
});

it('keeps failed lookups unlinked without dropping verified links in another language', async () => {
	const links = [
		{ word: 'house', lang: 'en' },
		{ word: 'maison', lang: 'fr' }
	];
	const verified = await verifiedLocalLinks(
		links,
		(link) => link.lang,
		async (lang) => {
			if (lang === 'en') throw new Error('Database unavailable');
			return ['maison'];
		}
	);
	expect(verified).toEqual([links[1]]);
});

it('does not query external targets and deduplicates local lookup words', async () => {
	const links = [
		{ word: 'house', lang: 'en' },
		{ word: 'house', lang: 'en', label: 'houses' },
		{ word: 'maison', lang: 'fr' }
	];
	const lookup = vi.fn<(lang: string, words: string[]) => Promise<string[]>>(async () => ['house']);
	expect(
		await verifiedLocalLinks(links, (link) => (link.lang === 'en' ? 'en' : undefined), lookup)
	).toEqual(links.slice(0, 2));
	expect(lookup.mock.calls).toEqual([['en', ['house']]]);
});
