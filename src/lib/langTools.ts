export function formatPronoun(
	langCode: string,
	pronoun: string,
	verbForm: string,
	frIsAspirated: boolean
) {
	if (langCode == 'fr') {
		if (pronoun == 'je') {
			const startsWithVowel = /^[aeiouyéèêëàâîïôûù]/.test(verbForm);
			const startsWithH = verbForm.startsWith('h');

			if ((startsWithVowel || startsWithH) && !frIsAspirated) {
				return "j'";
			}
		}
	}

	return pronoun + ' ';
}
