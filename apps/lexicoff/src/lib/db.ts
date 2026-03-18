import { Dexie, type Table } from 'dexie';
import type { MetaEntry, DictRecord, SearchPrefixEntry } from './types';

export class DictionaryDatabase extends Dexie {
	entries!: Table<DictRecord>;
	metadata!: Table<MetaEntry>;
	searchPrefixes!: Table<SearchPrefixEntry>;

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
		this.version(3)
			.stores({
				entries: '[lang+id], [lang+word]',
				metadata: 'lang',
				searchIndices: null,
				searchPrefixes: '[lang+prefix]'
			})
			.upgrade(async (tx) => {
				const oldRows = await tx.table('searchIndices').toArray();
				const prefixTable = tx.table('searchPrefixes');
				for (const row of oldRows) {
					const entries = Object.entries(row.searchIndex as Record<string, number[]>);
					const batch = entries.map(([prefix, ids]) => ({
						lang: row.lang as string,
						prefix,
						ids
					}));
					// Insert in chunks to avoid huge transactions
					const CHUNK = 5000;
					for (let i = 0; i < batch.length; i += CHUNK) {
						await prefixTable.bulkAdd(batch.slice(i, i + CHUNK));
					}
				}
			});
	}
}

export const db = new DictionaryDatabase();
