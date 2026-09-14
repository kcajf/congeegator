import type { WordLink } from './types';

/** Use the same exact-headword lookup as Forms, batching by destination language. */
export async function verifiedLocalLinks(
	links: WordLink[],
	localLanguage: (link: WordLink) => string | undefined,
	exactHeadwords: (lang: string, words: string[]) => Promise<string[]>
): Promise<WordLink[]> {
	const groups = new Map<string, WordLink[]>();
	for (const link of links) {
		const lang = localLanguage(link);
		if (lang) groups.set(lang, [...(groups.get(lang) ?? []), link]);
	}
	const results = await Promise.all(
		[...groups].map(async ([lang, group]) => {
			try {
				const found = new Set(await exactHeadwords(lang, [...new Set(group.map((l) => l.word))]));
				return group.filter((link) => found.has(link.word));
			} catch {
				// Unverified destinations remain readable plain text, as in Forms.
				return [];
			}
		})
	);
	return results.flat();
}
