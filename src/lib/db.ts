import { Dexie, type Table } from "dexie";
import type { VerbRecord } from './types';

export interface MetaEntry {
  lang: string;
  hash: string;
  searchIndex: Map<string, number[]>;
}

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
