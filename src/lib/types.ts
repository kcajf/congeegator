export interface DataManifest {
  languages: {
    [key: string]: {
      hash: string;
      name: string;
    };
  };
}

export type ConjugationForms = string | string[];

export interface VerbData {
  // Keyed by tense: e.g., "present", "imperfect"
  [tense: string]: ConjugationForms;
}

export interface VerbRecord {
  name: string;      // "manger"
  lang: string;      // "fr" (the "partition" key)
  conjugations: VerbData;
}