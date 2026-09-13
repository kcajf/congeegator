import type { DictPronunciation, DictRecord } from './types';

const USAGE_LABELS: Record<string, string> = {
	'North-Wales': 'North Wales',
	'South-Wales': 'South Wales',
	'Classical-Latin': 'Classical Latin',
	'Old-Latin': 'Old Latin',
	'Late-Latin': 'Late Latin',
	'Medieval-Latin': 'Medieval Latin',
	'New-Latin': 'New Latin',
	'Ecclesiastical-Latin': 'Ecclesiastical Latin',
	'Navarro-Lapurdian': 'Navarro-Lapurdian',
	'Vivaro-Alpine': 'Vivaro-Alpine'
};

export function formatUsageLabel(tag: string): string {
	return USAGE_LABELS[tag] ?? tag.replaceAll('-', ' ');
}

export function formatPronunciationLabel(label: string): string {
	return label
		.replaceAll('ˢᵗ', 'st')
		.replaceAll('ⁿᵈ', 'nd')
		.replaceAll('ʳᵈ', 'rd')
		.replaceAll('ᵗʰ', 'th');
}

/** Keep every labelled reading at its own entry, with support for older downloads. */
export function entryPronunciations(entry: DictRecord): DictPronunciation[] {
	if (entry.pronunciations?.length) return entry.pronunciations;
	return entry.pronunciation ? [{ ipa: entry.pronunciation }] : [];
}

/** Annotations never replace the spellings used for lookup or hide unannotated forms. */
export function formUsageLabels(entry: DictRecord): Map<string, string> {
	const labels = new Map<string, Set<string>>();
	for (const detail of entry.formDetails ?? []) {
		const tags = labels.get(detail.form) ?? new Set<string>();
		for (const tag of detail.tags ?? []) tags.add(formatUsageLabel(tag));
		labels.set(detail.form, tags);
	}
	return new Map([...labels].map(([form, tags]) => [form, [...tags].join(', ')]));
}
