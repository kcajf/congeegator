export interface DataManifest {
  languages: {
    [key: string]: {
      dataHash: string;
      code: string;
      name: string;
      tenseNames: string[];
      tensePronouns: string[][];
      tenseGroups: {
        name: string,
        tenseIndices: number[]
      }[]
    };
  };
}

export type ConjugationForms = string | string[];

export interface VerbRecord {
  id: number; // 0-indexed within lang
  name: string;      // "manger"
  nameNoDiacritics: string;      // "manger"
  lang: string;      // "fr" (the "partition" key)
  conjugation: ConjugationForms[];
  frIsAspirated: boolean | null;
}