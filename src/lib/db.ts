import { Dexie, type Table } from "dexie";
import type { VerbRecord } from './types';

export interface MetaEntry {
  lang: string;
  hash: string;
}

export class ConjugationDatabase extends Dexie {
  verbs!: Table<VerbRecord>;
  metadata!: Table<MetaEntry>;

  constructor() {
    super('ConjugationDB');
    this.version(2).stores({
      verbs: '[lang+name], lang, [lang+nameNoDiacritics]', // Compound index for fast lookup
      metadata: 'lang'
    });
  }
}

export const db = new ConjugationDatabase();
