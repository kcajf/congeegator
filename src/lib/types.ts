export interface DataManifest {
  languages: {
    [key: string]: {
      dataHash: string;
      code: string;
      name: string;
      tenseNames: string[];
      tensePronouns: string[][];
    };
  };
}

export type ConjugationForms = string | string[];

// export interface VerbData {
//   // Keyed by tense: e.g., "present", "imperfect"
//   [tense: string]: ConjugationForms;
// }

export interface VerbRecord {
  name: string;      // "manger"
  nameNoDiacritics: string;      // "manger"
  lang: string;      // "fr" (the "partition" key)
  conjugation: ConjugationForms[];
  frIsAspirated: boolean | null;
}