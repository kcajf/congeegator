export interface DataManifest {
	languages: {
		[key: string]: {
			dataHash: string;
			dataSize: number;
			code: string;
			name: string;
			englishWiktionaryName: string;
			tenseNames: string[];
			tensePronouns: string[][];
			tenseGroups: {
				name: string;
				tenseIndices: number[];
			}[];
		};
	};
}

export type ConjugationForms = string | string[];

export type Id = number;

export interface VerbRecord {
	tenses?: TenseMetadata;
	id: Id; // 0-indexed within lang
	name: string; // "manger"
	nameNoDiacritics: string; // "manger"
	lang: string; // "fr" (the "partition" key)
	conjugation: ConjugationForms[];
	freq: number;
	frIsAspirated: boolean | null;
	gloss?: string;
}

export type SearchIndex = Map<string, Id[]>;
export type SearchIndexStorage = Record<string, Id[]>;

export type TenseMetadata = Pick<
	DataManifest['languages'][string],
	'tenseNames' | 'tensePronouns' | 'tenseGroups'
>;

export interface DatasetVersion {
	key: string;
	lang: string;
	hash: string;
	entryCount: number;
	installedAt: number;
	tenses: TenseMetadata;
}

export type CachedVerb = VerbRecord;
export type VersionIndex = { lang: string; searchIndex: SearchIndexStorage };
