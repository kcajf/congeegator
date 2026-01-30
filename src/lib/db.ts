import { Dexie, type Table } from "dexie";
import type { MetaEntry, VerbRecord } from './types';

export class ConjugationDatabase extends Dexie {
  verbs!: Table<VerbRecord>;
  metadata!: Table<MetaEntry>;

  constructor() {
    super('ConjugationDB');
    this.version(2).stores({
      verbs: '[lang+id], [lang+name]', // Compound index for fast lookup
      metadata: 'lang'
    });
  }
}

export const db = new ConjugationDatabase();
