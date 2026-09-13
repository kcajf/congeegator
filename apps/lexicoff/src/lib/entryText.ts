import type { WordLink } from './types';

export interface TextPart {
	text: string;
	link?: WordLink;
	bold?: boolean;
}

/** Some source alternative labels contain section fragments, not display text. */
export function linkLabel(link: WordLink): string {
	return link.label && !link.label.includes('#') ? link.label : link.word;
}

const isLetter = (text: string) => /[\p{L}\p{M}\p{N}]/u.test(text);

/** Only link complete, source-labelled terms. Ambiguous labels stay plain. */
export function linkedText(text: string, links: WordLink[] = [], uniqueOnly = false): TextPart[] {
	const labels = new Map<string, WordLink | null>();
	for (const link of links) {
		// Older bundles misread surf dispatchers (+suf, +deverbal, …) as languages.
		if (link.lang.startsWith('+')) continue;
		const label = linkLabel(link);
		if (uniqueOnly && label && text.split(label).length > 2) continue;
		const previous = labels.get(label);
		if (previous === null) continue;
		labels.set(
			label,
			previous &&
				(previous.word !== link.word ||
					previous.lang !== link.lang ||
					previous.anchor !== link.anchor)
				? null
				: link
		);
	}
	const candidates = [...labels]
		.filter((pair): pair is [string, WordLink] => !!pair[0] && !!pair[1])
		.sort((a, b) => b[0].length - a[0].length);
	const parts: TextPart[] = [];
	let plain = '';
	for (let i = 0; i < text.length; ) {
		const match = candidates.find(
			([label]) =>
				text.startsWith(label, i) &&
				!(isLetter([...label][0]) && isLetter([...text.slice(0, i)].at(-1) ?? '')) &&
				!(isLetter([...label].at(-1) ?? '') && isLetter([...text.slice(i + label.length)][0] ?? ''))
		);
		if (match) {
			if (plain) parts.push({ text: plain });
			plain = '';
			parts.push({ text: match[0], link: match[1] });
			i += match[0].length;
		} else {
			plain += text[i++];
		}
	}
	if (plain) parts.push({ text: plain });
	return parts;
}

/** Wiktextract uses code point offsets; Array.from also handles astral scripts. */
export function boldText(text: string, ranges: [number, number][] = []): TextPart[] {
	const points = Array.from(text);
	const valid = ranges.filter(
		([start, end]) =>
			Number.isInteger(start) &&
			Number.isInteger(end) &&
			start >= 0 &&
			end > start &&
			end <= points.length
	);
	const parts: TextPart[] = [];
	for (let i = 0; i < points.length; i++) {
		const bold = valid.some(([start, end]) => i >= start && i < end);
		if (parts.length && parts[parts.length - 1].bold === bold)
			parts[parts.length - 1].text += points[i];
		else parts.push({ text: points[i], bold });
	}
	return parts;
}
