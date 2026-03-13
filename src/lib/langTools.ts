function longestCommonPrefix(a: string, b: string): string {
	const len = Math.min(a.length, b.length);
	let i = 0;
	while (i < len && a[i] === b[i]) i++;
	return a.slice(0, i);
}

export function formatForm(form: string): string {
	const parts = form.split('/');
	if (parts.length <= 1) return form;

	const result = [parts[0]];
	for (let i = 1; i < parts.length; i++) {
		const lcp = longestCommonPrefix(parts[0], parts[i]);
		if (lcp.length >= 4) {
			result.push('-' + parts[i].slice(lcp.length));
		} else {
			result.push(parts[i]);
		}
	}
	return result.join('/');
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
