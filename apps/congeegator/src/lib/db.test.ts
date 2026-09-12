import 'fake-indexeddb/auto';
import { Dexie } from 'dexie';
import { afterEach, expect, it } from 'vitest';
import { ConjugationDatabase } from './db';
import { manifest } from './dataUtils';
const databases: Dexie[] = [];
afterEach(async () => {
	for (const db of databases.splice(0)) {
		db.close();
		await Dexie.delete(db.name);
	}
});
async function legacy(hash: string, valid = true, schema = 3) {
	const name = `migration-${crypto.randomUUID()}`;
	const old = new Dexie(name);
	old.version(2).stores({ verbs: '[lang+id], [lang+name]', metadata: 'lang' });
	if (schema === 3) old.version(3).stores({ searchIndices: 'lang' });
	const verb = {
		id: 0,
		lang: 'fr',
		name: 'manger',
		nameNoDiacritics: 'manger',
		freq: 1,
		conjugation: manifest.languages.fr.tenseNames.map(() => '')
	};
	await old.table('verbs').put(verb);
	const searchIndex = valid ? { m: [0] } : undefined;
	await old.table('metadata').put({ lang: 'fr', hash, ...(schema === 2 ? { searchIndex } : {}) });
	if (schema === 3 && valid) await old.table('searchIndices').put({ lang: 'fr', searchIndex });
	old.close();
	const db = new ConjugationDatabase(name);
	databases.push(db);
	db.versionVerbs.hook('creating', () => {
		throw new DOMException('No space for a second copy', 'QuotaExceededError');
	});
	await db.open();
	return db;
}
it.each([2, 3])(
	'preserves schema v%i offline caches without copying verb records',
	async (schema) => {
		const hash = manifest.languages.fr.dataHash;
		const db = await legacy(hash, true, schema);
		const key = 'fr';
		expect(await db.versions.get(key)).toMatchObject({
			hash,
			entryCount: 1,
			tenses: { tenseNames: manifest.languages.fr.tenseNames }
		});
		expect(await db.versionVerbs.get([key, 0])).toMatchObject({ name: 'manger' });
		expect(await db.versionIndices.get(key)).toMatchObject({ searchIndex: { m: [0] } });
	}
);
it('does not attach new tense definitions to an unknown legacy version', async () => {
	expect(await (await legacy('old-hash')).versions.count()).toBe(0);
});
it('does not migrate caches that were marked complete without a search index', async () => {
	expect(await (await legacy(manifest.languages.fr.dataHash, false)).versions.count()).toBe(0);
});
