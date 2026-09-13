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

export interface WordLink {
	word: string;
	lang: string;
	label?: string;
	anchor?: string;
	sense?: string;
	tags?: string[];
}

export interface DictExample {
	text: string;
	translation?: string;
	roman?: string;
	ref?: string;
	type?: 'quotation';
	bold?: [number, number][];
	translationBold?: [number, number][];
}

export interface EntryDetails {
	etymologyLinks?: WordLink[];
	synonyms?: WordLink[];
	antonyms?: WordLink[];
	related?: WordLink[];
	derived?: WordLink[];
}

export interface DictSense {
	gloss: string;
	examples?: (string | DictExample)[];
	tags?: string[];
	links?: WordLink[];
	formOf?: WordLink[];
	altOf?: WordLink[];
	synonyms?: WordLink[];
	antonyms?: WordLink[];
	topics?: string[];
	qualifier?: string;
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
	details?: EntryDetails;
	matchedForm?: string;
}
