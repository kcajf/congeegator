import { describe, expect, it } from 'vitest';
import {
	addRecentWord,
	emptyTrail,
	readRecentWords,
	readTrail,
	recordNavigation,
	type HistoryEntry,
	type RecentWord
} from './navigationHistory';

const home: HistoryEntry = { id: 'home', url: '/', label: 'Home' };
const a: HistoryEntry = { id: 'a', url: '/en/wander', label: 'wander' };
const b: HistoryEntry = { id: 'b', url: '/en/wonder', label: 'wonder' };
const c: HistoryEntry = { id: 'c', url: '/en/serene', label: 'serene' };

describe('native navigation trail', () => {
	it('starts at a safe boundary on a direct word launch', () => {
		expect(recordNavigation(emptyTrail(), a, 'restore')).toEqual({ entries: [a], cursor: 0 });
	});

	it('supports home, back, forward, and reload without adding entries', () => {
		let trail = recordNavigation(emptyTrail(), home, 'restore');
		trail = recordNavigation(trail, a, 'push');
		trail = recordNavigation(trail, b, 'push');
		trail = recordNavigation(trail, a, 'restore');
		expect(trail).toEqual({ entries: [home, a, b], cursor: 1 });
		trail = recordNavigation(readTrail(JSON.stringify(trail)), a, 'restore');
		expect(trail).toEqual({ entries: [home, a, b], cursor: 1 });
		expect(recordNavigation(trail, b, 'restore').cursor).toBe(2);
		expect(recordNavigation(trail, home, 'restore').cursor).toBe(0);
	});

	it('discards the forward branch after a new lookup', () => {
		let trail = recordNavigation(emptyTrail(), a, 'restore');
		trail = recordNavigation(trail, b, 'push');
		trail = recordNavigation(trail, a, 'restore');
		expect(recordNavigation(trail, c, 'push')).toEqual({ entries: [a, c], cursor: 1 });
	});

	it('identifies repeated visits by entry ID, not URL', () => {
		let trail = recordNavigation(emptyTrail(), a, 'restore');
		trail = recordNavigation(trail, b, 'push');
		const revisit = { ...a, id: 'a-again' };
		trail = recordNavigation(trail, revisit, 'push');
		expect(recordNavigation(trail, a, 'restore').cursor).toBe(0);
		expect(recordNavigation(trail, revisit, 'restore').cursor).toBe(2);
	});

	it('resets on unknown entries or a URL that no longer matches', () => {
		const trail = recordNavigation(emptyTrail(), a, 'restore');
		expect(recordNavigation(trail, c, 'restore')).toEqual({ entries: [c], cursor: 0 });
		const changed = { ...a, url: '/en/elsewhere' };
		expect(recordNavigation(trail, changed, 'restore')).toEqual({ entries: [changed], cursor: 0 });
	});

	it('bounds storage while retaining a contiguous traversable path', () => {
		let trail = emptyTrail();
		for (let i = 0; i < 120; i++) {
			trail = recordNavigation(trail, { ...a, id: String(i) }, 'push');
		}
		expect(trail.entries).toHaveLength(100);
		expect(trail.entries[0].id).toBe('20');
		expect(trail.cursor).toBe(99);
	});

	it.each([
		null,
		'{broken',
		JSON.stringify({ entries: [null], cursor: 0 }),
		JSON.stringify({ entries: [a], cursor: 2 }),
		JSON.stringify({ entries: [a, a], cursor: 0 }),
		JSON.stringify({ entries: [{ ...a, url: '//outside.test' }], cursor: 0 })
	])('ignores invalid saved trails: %s', (raw) => {
		expect(readTrail(raw)).toEqual(emptyTrail());
	});
});

describe('recent words', () => {
	it('deduplicates words within a language, retaining other languages', () => {
		let recent = addRecentWord([], { lang: 'en', word: 'chat', viewedAt: 1 });
		recent = addRecentWord(recent, { lang: 'fr', word: 'chat', viewedAt: 2 });
		recent = addRecentWord(recent, { lang: 'en', word: 'chat', viewedAt: 3 });
		expect(recent).toEqual([
			{ lang: 'en', word: 'chat', viewedAt: 3 },
			{ lang: 'fr', word: 'chat', viewedAt: 2 }
		]);
	});

	it('retains the last 30 distinct words independently of navigation branches', () => {
		let recent: RecentWord[] = [];
		for (let i = 0; i < 35; i++) {
			recent = addRecentWord(recent, { lang: 'en', word: String(i), viewedAt: i });
		}
		expect(recent).toHaveLength(30);
		expect(recent[0].word).toBe('34');
		expect(recent[29].word).toBe('5');
		expect(readRecentWords(JSON.stringify(recent), ['en'])).toEqual(recent);
	});

	it('ignores corrupted, duplicate, and unsupported saved words', () => {
		const word = { lang: 'en', word: 'wonder', viewedAt: 1 };
		expect(readRecentWords('{broken', ['en'])).toEqual([]);
		expect(readRecentWords(null, ['en'])).toEqual([]);
		expect(
			readRecentWords(JSON.stringify([null, {}, word, word, { ...word, lang: 'xx' }]), ['en'])
		).toEqual([word]);
	});
});
