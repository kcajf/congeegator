import { Dexie, type Table } from 'dexie';
import type { MetaEntry, DictRecord, SearchIndexEntry } from './types';

export class DictionaryDatabase extends Dexie {
	entries!: Table<DictRecord>;
	metadata!: Table<MetaEntry>;
	searchIndices!: Table<SearchIndexEntry>;

	constructor() {
		super('LexicoffDB', { chromeTransactionDurability: 'relaxed' });
		this.version(1).stores({
			entries: '[lang+id], [lang+word]',
			metadata: 'lang'
		});
		this.version(2)
			.stores({
				entries: '[lang+id], [lang+word]',
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

export const db = new DictionaryDatabase();
