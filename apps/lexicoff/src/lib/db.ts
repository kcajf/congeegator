import { Dexie, type Table } from 'dexie';
import type { MetaEntry, DictRecord } from './types';

export class DictionaryDatabase extends Dexie {
	entries!: Table<DictRecord>;
	metadata!: Table<MetaEntry>;

	constructor() {
		super('LexicoffDB', { chromeTransactionDurability: 'relaxed' });
		this.version(1).stores({
			entries: '[lang+id], [lang+word]',
			metadata: 'lang'
		});
	}
}

export const db = new DictionaryDatabase();
