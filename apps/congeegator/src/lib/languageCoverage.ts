export const languageCoverage: Record<string, string> = {
	pt: 'Main paradigm, with regional and historical variants labelled where identified. Compound tenses and attached pronouns are not included.',
	ca: 'Main Central Catalan paradigm, including the periphrastic past. Other compound tenses and attached pronouns are not included.',
	nl: 'Simple tenses and participles. Compound tenses are not included. The jij row includes both ordinary and inverted word order.',
	sv: 'Finite forms apply to all persons. The s-forms include both passives and deponent verbs.',
	fi: 'Main finite forms with selected infinitives and participles. Pronouns are row guides; impersonal verbs use different subject constructions.',
	la: 'Deponent verbs appear under active meaning. In compound forms, the participle agrees with the subject’s gender and number.'
};

export const verbCoverage: Record<string, Record<string, string>> = {
	la: {
		odi: 'Here, tense labels follow meaning: ōdī has present meaning but is perfect in form.',
		memini: 'Here, tense labels follow meaning: meminī has present meaning but is perfect in form.'
	}
};
