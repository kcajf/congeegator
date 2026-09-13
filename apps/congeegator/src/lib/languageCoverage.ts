export const languageCoverage: Record<string, string> = {
	pt: 'Compound tenses and attached pronouns are not included.',
	ca: 'Forms follow Central Catalan. Compound tenses other than the periphrastic past and attached pronouns are not included.',
	nl: 'Compound tenses are not included. The jij row includes both ordinary and inverted word order.',
	sv: 'Finite forms apply to all persons. The s-forms include both passives and deponent verbs.',
	fi: 'Pronouns are row guides; impersonal verbs use different subject constructions.',
	la: 'Deponent verbs appear under active meaning. In compound forms, the participle agrees with the subject’s gender and number.'
};

export const verbCoverage: Record<string, Record<string, string>> = {
	la: {
		odi: 'Here, tense labels follow meaning: ōdī has present meaning but is perfect in form.',
		memini: 'Here, tense labels follow meaning: meminī has present meaning but is perfect in form.'
	}
};
