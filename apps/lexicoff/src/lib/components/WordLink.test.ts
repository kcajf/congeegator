import { render } from 'svelte/server';
import { describe, expect, it, vi } from 'vitest';
import WordLink from './WordLink.svelte';

vi.mock('$lib/sqliteClient.svelte', () => ({
	storage: { languages: { fr: { status: 'ready' } } }
}));

describe('dictionary word URLs', () => {
	it.each(['s/', '/s', 'bonjour/hi', 'a#b', 'a?b', '100%', 'été'])(
		'keeps %s in a single encoded route parameter',
		(word) => {
			const { body } = render(WordLink, { props: { link: { word, lang: 'fr' } } });
			expect(body).toContain(`href="/fr/${encodeURIComponent(word)}"`);
		}
	);
});
