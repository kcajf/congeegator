import 'fake-indexeddb/auto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { db } from './db';
import { pruneVersions } from './cacheRetention';
import { manifest } from './dataUtils';
import type { DatasetVersion } from './types';
const held = new Set<string>();
const version = (key: string): DatasetVersion => ({
	key,
	lang: 'fr',
	hash: key,
	entryCount: 1,
	installedAt: 1,
	tenses: manifest.languages.fr
});
beforeEach(async () => {
	await db.open();
	held.clear();
	vi.stubGlobal('navigator', {
		locks: { request: vi.fn(async (name, _options, run) => run(held.has(name) ? null : { name })) }
	});
	for (const key of ['old', 'current']) {
		await db.versions.put(version(key));
		await db.indices.put({ key, searchIndex: { m: [0] } });
		await db.verbs.put({
			lang: 'fr',
			version: key,
			id: 0,
			name: 'manger',
			nameNoDiacritics: 'manger',
			freq: 1,
			conjugation: [],
			frIsAspirated: null
		});
	}
});
afterEach(async () => {
	await db.delete();
	vi.unstubAllGlobals();
});
it('reclaims obsolete records and indices without clearing the current dictionary', async () => {
	await pruneVersions(version('current'));
	expect(await db.versions.get('old')).toBeUndefined();
	expect(await db.verbs.get(['old', 0])).toBeUndefined();
	expect(await db.indices.get('old')).toBeUndefined();
	expect(await db.verbs.get(['current', 0])).toBeDefined();
});
it('retains versions protected by an open tab, then reclaims them after that tab closes', async () => {
	held.add('congeegator-cache-fr-old');
	await pruneVersions(version('current'));
	expect(await db.verbs.get(['old', 0])).toBeDefined();
	held.clear();
	await pruneVersions(version('current'));
	expect(await db.verbs.get(['old', 0])).toBeUndefined();
});
