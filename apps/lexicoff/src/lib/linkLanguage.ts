import registry from './etymologyLanguages.json';
import type { WordLink } from './types';

const aliases = new Map<string, string>(Object.entries(registry.aliases));
const varieties = new Map<string, string[]>(Object.entries(registry.varieties));
const terminals = new Map<string, string[]>(Object.entries(registry.terminals));

/** Follow Wiktionary's entry containment, never ancestry or code prefixes. */
export function linkLanguage(code: string) {
	let current = aliases.get(code) ?? code;
	const name = varieties.get(current)?.[0] ?? terminals.get(current)?.[0];
	const seen = new Set<string>();
	while (varieties.has(current) || aliases.has(current)) {
		if (seen.has(current)) return { code, name, section: undefined, kind: 'unknown' };
		seen.add(current);
		current = aliases.get(current) ?? varieties.get(current)![1];
	}
	return {
		code: current,
		name,
		section: current === 'und' ? undefined : terminals.get(current)?.[0],
		kind: terminals.get(current)?.[1] ?? 'unknown'
	};
}

/** A missing dictionary stays external; a reconstruction never becomes a lemma. */
export function localLinkLanguage(
	link: WordLink,
	isInstalled: (code: string) => boolean
): string | undefined {
	const language = linkLanguage(link.lang);
	if (
		!link.word.startsWith('*') &&
		!link.word.includes(':') &&
		!['family', 'reconstructed', 'special'].includes(language.kind) &&
		isInstalled(language.code)
	) {
		return language.code;
	}
}
