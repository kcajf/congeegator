function longestCommonPrefix(a: string, b: string): string {
	const len = Math.min(a.length, b.length);
	let i = 0;
	while (i < len && a[i] === b[i]) i++;
	return a.slice(0, i);
}

export function formatForm(form: string): string {
	const parts = form.split('/');
	if (parts.length <= 1) return form;

	// Factor out common whole-word prefix across ALL parts
	const wordArrays = parts.map((p) => p.split(' '));
	let commonWordCount = 0;
	outer: while (commonWordCount < wordArrays[0].length) {
		const word = wordArrays[0][commonWordCount];
		for (let i = 1; i < wordArrays.length; i++) {
			if (
				commonWordCount >= wordArrays[i].length ||
				wordArrays[i][commonWordCount] !== word
			) {
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
	return prefix + result.join('/');
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
	icon?: string;
};

const WR_LANG_CODES: Record<string, string> = {
	fr: 'fren',
	el: 'gren',
	de: 'deen'
};

export function getExternalLinks(
	lang: string,
	verbName: string,
	wordreferenceLogo: string
): VerbExternalLink[] {
	const links: VerbExternalLink[] = [];

	const wrCode = WR_LANG_CODES[lang];
	if (wrCode) {
		links.push({
			type: 'icon',
			label: 'WordReference',
			href: `https://www.wordreference.com/${wrCode}/${encodeURIComponent(verbName)}`,
			icon: wordreferenceLogo
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
