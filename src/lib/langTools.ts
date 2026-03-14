export type MarkerType = 'deprecated' | 'rare' | 'formal';

export interface FormSegment {
	text: string;
	markers: MarkerType[];
	separator?: '/' | ' - ';
}

const OPENER_TO_MARKER: Record<string, MarkerType> = {
	'(': 'deprecated',
	'[': 'rare',
	'{': 'formal'
};

const CLOSER_TO_OPENER: Record<string, string> = { '}': '{', ']': '[', ')': '(' };

function stripMarkersRaw(s: string): { text: string; openers: string; closers: string } {
	let openers = '';
	let closers = '';
	while (s.length > 0 && '([{'.includes(s[0])) {
		openers += s[0];
		s = s.slice(1);
	}
	while (s.length > 0 && '}])'.includes(s[s.length - 1])) {
		closers = s[s.length - 1] + closers;
		s = s.slice(0, -1);
	}
	return { text: s, openers, closers };
}

function matchClosers(openers: string, closers: string): string {
	const remaining = [...openers];
	for (const c of closers) {
		const match = CLOSER_TO_OPENER[c];
		const idx = remaining.lastIndexOf(match);
		if (idx !== -1) remaining.splice(idx, 1);
	}
	return remaining.join('');
}

function openersToMarkers(openers: string): MarkerType[] {
	const markers: MarkerType[] = [];
	const seen = new Set<MarkerType>();
	for (const c of openers) {
		const m = OPENER_TO_MARKER[c];
		if (m && !seen.has(m)) {
			markers.push(m);
			seen.add(m);
		}
	}
	return markers;
}

function longestCommonPrefix(a: string, b: string): string {
	const len = Math.min(a.length, b.length);
	let i = 0;
	while (i < len && a[i] === b[i]) i++;
	return a.slice(0, i);
}

export function abbreviateVariants(parts: string[]): { prefix: string; parts: string[] } {
	if (parts.length <= 1) return { prefix: '', parts: [...parts] };

	// Factor out common whole-word prefix across ALL parts
	const wordArrays = parts.map((p) => p.split(' '));
	let commonWordCount = 0;
	outer: while (commonWordCount < wordArrays[0].length) {
		const word = wordArrays[0][commonWordCount];
		for (let i = 1; i < wordArrays.length; i++) {
			if (commonWordCount >= wordArrays[i].length || wordArrays[i][commonWordCount] !== word) {
				break outer;
			}
		}
		commonWordCount++;
	}

	let prefix = '';
	let effectiveParts = parts;
	if (commonWordCount > 0) {
		prefix = wordArrays[0].slice(0, commonWordCount).join(' ') + ' ';
		effectiveParts = parts.map((p) => p.slice(prefix.length));
	}

	// Apply per-pair abbreviation to stripped parts
	const result = [effectiveParts[0]];
	for (let i = 1; i < effectiveParts.length; i++) {
		const lcp = longestCommonPrefix(effectiveParts[0], effectiveParts[i]);
		const suffix = effectiveParts[i].slice(lcp.length);
		if (lcp.length >= 4 && !effectiveParts[0].endsWith(suffix)) {
			result.push('-' + suffix);
		} else {
			result.push(effectiveParts[i]);
		}
	}
	return { prefix, parts: result };
}

export function formatForm(form: string): string {
	const parts = form.split('/');
	if (parts.length <= 1) return form;
	const { prefix, parts: abbrevParts } = abbreviateVariants(parts);
	return prefix + abbrevParts.join('/');
}

export function parseAndFormatForm(raw: string): FormSegment[] {
	// Fast path: no marker characters
	if (!/[([{}\])]/.test(raw)) {
		return [{ text: formatForm(raw), markers: [] }];
	}

	// Split on '/' to get variants, then on ' - ' within each variant
	const slashParts = raw.split('/');
	const tokens: { text: string; markers: MarkerType[]; separator?: '/' | ' - ' }[] = [];
	let propagated = '';

	for (let si = 0; si < slashParts.length; si++) {
		const dashParts = slashParts[si].split(' - ');
		for (let di = 0; di < dashParts.length; di++) {
			const { text, openers, closers } = stripMarkersRaw(dashParts[di]);
			const allOpeners = propagated + openers;
			propagated = matchClosers(allOpeners, closers);

			let separator: '/' | ' - ' | undefined;
			if (si > 0 && di === 0) separator = '/';
			else if (di > 0) separator = ' - ';

			tokens.push({ text, markers: openersToMarkers(allOpeners), separator });
		}
	}

	// Group tokens by slash-group for abbreviation
	const slashGroups: number[][] = [[]];
	for (let i = 0; i < tokens.length; i++) {
		if (tokens[i].separator === '/') {
			slashGroups.push([i]);
		} else {
			slashGroups[slashGroups.length - 1].push(i);
		}
	}

	// Build full text per slash-group and abbreviate
	const groupTexts = slashGroups.map((g) => g.map((i) => tokens[i].text).join(' - '));
	const { prefix, parts: abbrevParts } = abbreviateVariants(groupTexts);

	// Map abbreviated texts back to segments
	const segments: FormSegment[] = [];
	for (let gi = 0; gi < slashGroups.length; gi++) {
		const group = slashGroups[gi];
		const abbrevGroupText = (gi === 0 ? prefix : '') + abbrevParts[gi];

		if (group.length === 1) {
			segments.push({
				text: abbrevGroupText,
				markers: tokens[group[0]].markers,
				separator: tokens[group[0]].separator
			});
		} else {
			// Multiple dash-separated tokens — split abbreviated text back
			const subTexts = abbrevGroupText.split(' - ');
			for (let si = 0; si < group.length; si++) {
				segments.push({
					text: subTexts[si] ?? tokens[group[si]].text,
					markers: tokens[group[si]].markers,
					separator: tokens[group[si]].separator
				});
			}
		}
	}

	return segments;
}

export function formatPronoun(
	langCode: string,
	pronoun: string,
	verbForm: string,
	frIsAspirated: boolean
) {
	if (langCode == 'fr') {
		if (pronoun == 'je' || pronoun == 'que je') {
			const startsWithVowel = /^[aeiouyéèêëàâîïôûù]/.test(verbForm);
			const startsWithH = verbForm.startsWith('h');

			if ((startsWithVowel || startsWithH) && !frIsAspirated) {
				return pronoun == 'je' ? "j'" : "que j'";
			}
		}
	}

	return pronoun + ' ';
}

export type VerbExternalLink = {
	type: 'icon' | 'text';
	label: string;
	href: string;
	iconSvg?: string;
};

const WR_LANG_CODES: Record<string, string> = {
	fr: 'fren',
	el: 'gren',
	de: 'deen',
	es: 'esen',
	it: 'iten'
};

export function getExternalLinks(
	lang: string,
	verbName: string,
	wordreferenceLogoSvg: string
): VerbExternalLink[] {
	const links: VerbExternalLink[] = [];

	const wrCode = WR_LANG_CODES[lang];
	if (wrCode) {
		links.push({
			type: 'icon',
			label: 'WordReference',
			href: `https://www.wordreference.com/${wrCode}/${encodeURIComponent(verbName)}`,
			iconSvg: wordreferenceLogoSvg
		});
	}

	if (lang === 'fr') {
		links.push({
			type: 'text',
			label: 'Bescherelle',
			href: `https://conjugaison.bescherelle.com/verbes/${encodeURIComponent(verbName)}`
		});
	} else if (lang === 'el') {
		links.push({
			type: 'text',
			label:
				'\u03A4\u03C1\u03B9\u03B1\u03BD\u03C4\u03B1\u03C6\u03C5\u03BB\u03BB\u03AF\u03B4\u03B7\u03C2',
			href: `https://www.greek-language.gr/greekLang/modern_greek/tools/lexica/triantafyllides/search.html?lq=${encodeURIComponent(verbName)}&dq=`
		});
	}

	return links;
}
