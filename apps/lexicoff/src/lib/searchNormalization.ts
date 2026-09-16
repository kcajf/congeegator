// Keep this normalization aligned with dictionary_word_key in pipeline/sqlite_output.py.
// NFC joins decomposed keyboard input without removing letters' distinguishing accents.
export function dictionaryWordKey(text: string, lang: string): string {
	const composed = text.normalize('NFC');
	return (
		lang === 'tr' || lang === 'az' ? composed.toLocaleLowerCase(lang) : composed.toLowerCase()
	).normalize('NFC');
}

// Search aliases never replace display spellings or exact-match keys. Keep this
// aligned with dictionary_search_key in pipeline/sqlite_output.py.
export function dictionarySearchKey(text: string, lang: string): string {
	let key = dictionaryWordKey(text, lang);
	if (lang === 'grc' || lang === 'he') key = key.normalize('NFD').replace(/\p{Mn}/gu, '');
	if (lang === 'grc') key = key.replace(/ς/g, 'σ');
	if (lang === 'fa') {
		key = key
			.replace(/ي/g, 'ی')
			.replace(/ك/g, 'ک')
			.replace(/\u200c/g, '');
		// Optional short vowels; retain hamza and madda.
		key = key.replace(/[\u064b-\u0652\u0670]/g, '');
	}
	if (lang === 'ar' || lang === 'ur') key = key.replace(/[\u064b-\u0652\u0670\u0640]/g, '');
	if (lang === 'ur') key = key.replace(/ك/g, 'ک').replace(/ي/g, 'ی');
	if (lang === 'ja') {
		key = key
			.normalize('NFKC')
			.replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60));
	}
	return key.normalize('NFC');
}

export function searchTokens(text: string): string[] {
	// Preserve combining marks: replacing them with spaces splits a single word.
	return text
		.normalize('NFC')
		.replace(/[^\p{L}\p{M}\p{N}\s]/gu, ' ')
		.trim()
		.split(/\s+/)
		.filter((token) => /[\p{L}\p{N}]/u.test(token));
}

export function prefixMatch(tokens: string[]): string {
	// detail=column supports token conjunctions, not multi-token phrases.
	return tokens.map((token) => `"${token}"`).join(' ') + '*';
}
