import { Dexie, type Table } from 'dexie';
import type { MetaEntry, VerbRecord, SearchIndexEntry } from './types';

export class ConjugationDatabase extends Dexie {
	verbs!: Table<VerbRecord>;
	metadata!: Table<MetaEntry>;
	searchIndices!: Table<SearchIndexEntry>;

	constructor() {
		super('ConjugationDB');
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
	}
}

export const db = new ConjugationDatabase();
