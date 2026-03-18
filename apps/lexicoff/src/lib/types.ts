export interface DataManifest {
	languages: {
		[key: string]: {
			dataHash: string;
			dataSize: number;
			code: string;
			name: string;
			englishWiktionaryName: string;
		};
	};
}

export type Id = number;

export interface DictSense {
	gloss: string;
	examples?: string[];
	tags?: string[];
}

export interface DictRecord {
	id: Id;
	word: string;
	wordNoDiacritics: string;
	lang: string;
	pos: string;
	senses: DictSense[];
	freq: number;
	gender?: string;
	forms?: string[];
	pronunciation?: string;
	etymology?: string;
}

export interface SearchPrefixEntry {
	lang: string;
	prefix: string;
	ids: Id[];
}

export interface MetaEntry {
	lang: string;
	hash: string;
}
