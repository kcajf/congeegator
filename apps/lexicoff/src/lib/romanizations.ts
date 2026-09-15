import profiles from '../../../../shared/romanization-profiles.json';

// Keep normalization aligned with pipeline/romanizations.py and shared fixtures.
export function romanizationKeys(
	lang: string,
	reading: string
): { key: string; quality: number }[] {
	if (!Object.hasOwn(profiles, lang)) return [];
	const strict = reading.trim().toLowerCase().normalize('NFC');
	if (!strict) return [];
	const mapping = profiles[lang as keyof typeof profiles] as Record<string, string>;
	const letters = Object.keys(mapping).sort((a, b) => b.length - a.length);
	let loose = strict;
	let pattern: RegExp | undefined;
	if (letters.length) {
		const source = letters.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
		pattern = new RegExp(source, 'gu');
		loose = loose.replace(pattern, (match) => mapping[match]);
	}
	loose = loose.normalize('NFD').replace(/\p{Mn}/gu, '');
	if (pattern) loose = loose.replace(pattern, (match) => mapping[match]);
	loose = loose
		.replace(/[’'ʼʹʺ]/gu, '')
		.replace(/[\s-]+/gu, ' ')
		.trim();
	return [{ key: loose || strict, quality: 5 }];
}
