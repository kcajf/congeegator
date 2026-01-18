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
    this.version(1).stores({
      verbs: '[lang+name], lang', // Compound index for fast lookup
      metadata: 'lang'
    });
  }
}

export const db = new ConjugationDatabase();
