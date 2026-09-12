import { Dexie, type Table } from 'dexie';
import type { CachedVerb, DatasetVersion, VersionIndex } from './types';
import { manifest } from './dataUtils';
import { validateDownload } from './datasets';

export class ConjugationDatabase extends Dexie {
	get versionVerbs(): Table<CachedVerb> {
		return this.table('verbs');
	}
	versions!: Table<DatasetVersion>;
	get versionIndices(): Table<VersionIndex> {
		return this.table('searchIndices');
	}

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
				versions: 'key, lang'
			})
			.upgrade(async (tx) => {
				// Legacy caches did not store their tense layout. Only migrate data
				// whose hash matches the bundled definition; never guess its schema.
				for (const meta of await tx.table('metadata').toArray()) {
					const definition = manifest.languages[meta.lang];
					const discard = async () => {
						await tx
							.table('verbs')
							.where('[lang+id]')
							.between([meta.lang, Dexie.minKey], [meta.lang, Dexie.maxKey])
							.delete();
						await tx.table('searchIndices').delete(meta.lang);
					};
					if (!definition || definition.dataHash !== meta.hash) {
						await discard();
						continue;
					}
					const verbs = await tx
						.table('verbs')
						.where('[lang+id]')
						.between([meta.lang, Dexie.minKey], [meta.lang, Dexie.maxKey])
						.toArray();
					if (!verbs.every((verb, id) => verb.id === id)) {
						await discard();
						continue;
					}
					const index = await tx.table('searchIndices').get(meta.lang);
					const data = { verbs, searchIndex: index?.searchIndex };
					try {
						validateDownload(data, definition);
					} catch {
						await discard();
						continue;
					}
					// Keep legacy records and their index in place. Migrating only this
					// small descriptor avoids needing space for a second dictionary.
					const key = meta.lang;
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
	}
}

export const db = new ConjugationDatabase();

export async function getInstalledVersion(lang: string): Promise<DatasetVersion | undefined> {
	const hash = manifest.languages[lang]?.dataHash;
	if (!hash) return undefined;
	const versions = await db.versions.where('lang').equals(lang).toArray();
	return (
		versions.find((version) => version.hash === hash) ??
		versions.sort((a, b) => b.installedAt - a.installedAt)[0]
	);
}

export function recordsFor(key: string) {
	return db.versionVerbs.where('[lang+id]').between([key, 0], [key, Infinity]);
}
