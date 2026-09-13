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

export interface DictFormDetail {
	form: string;
	tags?: string[];
}

export interface DictPronunciation {
	ipa: string;
	label?: string;
}

export interface DictRecord {
	id: Id;
	word: string;
	lang: string;
	pos: string;
	senses: DictSense[];
	freq: number;
	gender?: string;
	forms?: string[];
	formDetails?: DictFormDetail[];
	pronunciations?: DictPronunciation[];
	pronunciation?: string;
	etymology?: string;
}
