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

/** Complete readings keep qualifiers attached; legacy labels remain one reading. */
export function formReadings(entry: DictRecord): Map<string, string[]> {
	const result = new Map<string, string[]>();
	const legacy = formUsageLabels(entry);
	for (const detail of entry.formDetails ?? []) {
		const readings = result.get(detail.form) ?? [];
		for (const reading of detail.readings ?? []) {
			const grammar = (reading.grammar ?? []).map(formatUsageLabel).join(' ');
			const qualifiers = (reading.qualifiers ?? []).map(formatUsageLabel).join(', ');
			const text = [grammar, qualifiers].filter(Boolean).join(' · ');
			if (text && !readings.includes(text)) readings.push(text);
		}
		result.set(detail.form, readings);
	}
	for (const [form, label] of legacy) {
		if (!result.get(form)?.length && label) result.set(form, [label]);
	}
	return result;
}

export function formGroups(entry: DictRecord, forms: string[]) {
	const kinds = new Map((entry.formDetails ?? []).map((detail) => [detail.form, detail.kind]));
	const groups = [
		{ kind: 'inflection', label: 'Inflections' },
		{ kind: 'variant', label: 'Spelling variants' },
		{ kind: 'related', label: 'Related formations' },
		{ kind: 'other', label: 'Other forms' }
	];
	return groups
		.map(({ kind, label }) => ({
			label,
			forms: forms.filter((form) => (kinds.get(form) ?? 'other') === kind)
		}))
		.filter((group) => group.forms.length);
}
