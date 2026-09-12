// Keep this normalization aligned with dictionary_word_key in pipeline/sqlite_output.py.
// NFC joins decomposed keyboard input without removing letters' distinguishing accents.
export function dictionaryWordKey(text: string, lang: string): string {
	const composed = text.normalize('NFC');
	return (lang === 'tr' ? composed.toLocaleLowerCase('tr') : composed.toLowerCase()).normalize(
		'NFC'
	);
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
