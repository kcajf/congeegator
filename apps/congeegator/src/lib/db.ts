import { Dexie, type Table } from 'dexie';
import type { CachedVerb, DatasetVersion, VersionIndex } from './types';
import { manifest } from './dataUtils';
import { datasetKey, validateDownload } from './datasets';

export class ConjugationDatabase extends Dexie {
	versionVerbs!: Table<CachedVerb>;
	versions!: Table<DatasetVersion>;
	versionIndices!: Table<VersionIndex>;

	constructor(name = 'ConjugationDB') {
		super(name);
		this.version(2).stores({
			verbs: '[lang+id], [lang+name]',
			metadata: 'lang'
		});
		this.version(3)
			.stores({
				verbs: '[lang+id], [lang+name]',
				metadata: 'lang',
				searchIndices: 'lang'
			})
			.upgrade(async (tx) => {
				const oldMeta = await tx.table('metadata').toArray();
				for (const row of oldMeta) {
					if (row.searchIndex) {
						await tx.table('searchIndices').put({ lang: row.lang, searchIndex: row.searchIndex });
						await tx.table('metadata').put({ lang: row.lang, hash: row.hash });
					}
				}
			});
		this.version(4)
			.stores({
				versionVerbs: '[key+id], [key+name], key',
				versions: 'key, lang',
				versionIndices: 'key'
			})
			.upgrade(async (tx) => {
				// Legacy caches did not store their tense layout. Only migrate data
				// whose hash matches the bundled definition; never guess its schema.
				for (const meta of await tx.table('metadata').toArray()) {
					const definition = manifest.languages[meta.lang];
					if (!definition || definition.dataHash !== meta.hash) continue;
					const verbs = await tx
						.table('verbs')
						.where('[lang+id]')
						.between([meta.lang, Dexie.minKey], [meta.lang, Dexie.maxKey])
						.toArray();
					if (!verbs.every((verb, id) => verb.id === id)) continue;
					const index = await tx.table('searchIndices').get(meta.lang);
					const data = { verbs, searchIndex: index?.searchIndex };
					try {
						validateDownload(data, definition);
					} catch {
						continue;
					}
					const key = datasetKey(meta.lang, meta.hash);
					await tx.table('versionVerbs').bulkPut(verbs.map((verb) => ({ ...verb, key })));
					await tx.table('versionIndices').put({ key, searchIndex: data.searchIndex });
					await tx.table('versions').put({
						key,
						lang: meta.lang,
						hash: meta.hash,
						entryCount: verbs.length,
						installedAt: Date.now(),
						tenses: definition
					});
				}
			});
		this.version(5).stores({ verbs: null, metadata: null, searchIndices: null });
	}
}

export const db = new ConjugationDatabase();

export async function getInstalledVersion(lang: string): Promise<DatasetVersion | undefined> {
	const hash = manifest.languages[lang]?.dataHash;
	if (!hash) return undefined;
	const current = await db.versions.get(datasetKey(lang, hash));
	if (current) return current;
	const versions = await db.versions.where('lang').equals(lang).toArray();
	return versions.sort((a, b) => b.installedAt - a.installedAt)[0];
}
