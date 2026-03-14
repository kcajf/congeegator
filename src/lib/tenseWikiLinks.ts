const WIKI = 'https://en.wikipedia.org/wiki/';

const tenseWikiLinks: Record<string, string> = {
	// French — groups
	fr_indic: `${WIKI}Indicative_mood`,
	fr_subj: `${WIKI}Subjunctive_mood`,
	fr_cond: `${WIKI}Conditional_mood`,
	fr_imper: `${WIKI}Imperative_mood`,
	fr_impers: `${WIKI}Non-finite_verb`,
	// French — tenses
	fr_indic_pres: `${WIKI}Present_tense`,
	fr_indic_imperf: `${WIKI}Imperfect`,
	fr_indic_past_hist: `${WIKI}Passé_simple`,
	fr_indic_fut: `${WIKI}Future_tense`,
	fr_cond_pres: `${WIKI}Conditional_mood`,
	fr_subj_pres: `${WIKI}Subjunctive_mood`,
	fr_subj_imperf: `${WIKI}French_subjunctive`,
	fr_imper_pres: `${WIKI}Imperative_mood`,
	fr_impers_pres_partic: `${WIKI}Present_participle`,
	fr_impers_past_partic: `${WIKI}Past_participle`,
	fr_indic_pres_perf: `${WIKI}Passé_composé`,
	fr_indic_pluperf: `${WIKI}Pluperfect`,
	fr_indic_past_ant: `${WIKI}Past_anterior`,
	fr_indic_fut_perf: `${WIKI}Future_perfect`,

	// Greek — groups
	el_indic: `${WIKI}Indicative_mood`,
	el_subj: `${WIKI}Subjunctive_mood`,
	el_imper: `${WIKI}Imperative_mood`,
	el_impers: `${WIKI}Non-finite_verb`,
	// Greek — tenses
	el_indic_pres_active: `${WIKI}Present_tense`,
	el_indic_pres_passive: `${WIKI}Passive_voice`,
	el_indic_imperf_active: `${WIKI}Imperfect`,
	el_indic_imperf_passive: `${WIKI}Imperfect`,
	el_indic_aorist_active: `${WIKI}Aorist`,
	el_indic_aorist_passive: `${WIKI}Aorist`,
	el_indic_fut_cont_active: `${WIKI}Future_tense`,
	el_indic_fut_cont_passive: `${WIKI}Future_tense`,
	el_indic_fut_simple_active: `${WIKI}Future_tense`,
	el_indic_fut_simple_passive: `${WIKI}Future_tense`,
	el_subj_perf_active: `${WIKI}Subjunctive_mood`,
	el_subj_perf_passive: `${WIKI}Subjunctive_mood`,
	el_imper_imperf_active: `${WIKI}Imperative_mood`,
	el_imper_perf_active: `${WIKI}Imperative_mood`,
	el_imper_imperf_passive: `${WIKI}Imperative_mood`,
	el_imper_perf_passive: `${WIKI}Imperative_mood`,
	el_impers_pres_parti_active: `${WIKI}Participle`,
	el_impers_past_parti_passive: `${WIKI}Participle`,
	el_impers_pres_parti_passive: `${WIKI}Participle`,
	el_impers_inf_aorist_active: `${WIKI}Infinitive`,
	el_impers_inf_aorist_passive: `${WIKI}Infinitive`,

	// German — groups
	de_indic: `${WIKI}Indicative_mood`,
	de_subj_i_grp: `${WIKI}Subjunctive_mood`,
	de_subj_ii_grp: `${WIKI}Subjunctive_mood`,
	de_impers: `${WIKI}Non-finite_verb`,
	// German — tenses
	de_indic_pres: `${WIKI}Present_tense`,
	de_indic_preterite: `${WIKI}Preterite`,
	de_indic_perfect: `${WIKI}Perfect_(grammar)`,
	de_indic_pluperfect: `${WIKI}Pluperfect`,
	de_indic_fut_i: `${WIKI}Future_tense`,
	de_indic_fut_ii: `${WIKI}Future_perfect`,
	de_subj_i: `${WIKI}Subjunctive_mood`,
	de_subj_i_perfect: `${WIKI}Subjunctive_mood`,
	de_subj_i_fut_i: `${WIKI}Subjunctive_mood`,
	de_subj_i_fut_ii: `${WIKI}Subjunctive_mood`,
	de_subj_ii: `${WIKI}Subjunctive_mood`,
	de_subj_ii_pluperfect: `${WIKI}Subjunctive_mood`,
	de_subj_ii_fut_i: `${WIKI}Subjunctive_mood`,
	de_subj_ii_fut_ii: `${WIKI}Subjunctive_mood`,
	de_impers_infinitive: `${WIKI}Infinitive`,
	de_impers_pres_partic: `${WIKI}Present_participle`,
	de_impers_past_partic: `${WIKI}Past_participle`,

	// Spanish — groups
	es_indic: `${WIKI}Indicative_mood`,
	es_subj: `${WIKI}Subjunctive_mood`,
	es_cond: `${WIKI}Conditional_mood`,
	es_imper: `${WIKI}Imperative_mood`,
	es_impers: `${WIKI}Non-finite_verb`,
	// Spanish — tenses
	es_indic_pres: `${WIKI}Present_tense`,
	es_indic_pret: `${WIKI}Preterite`,
	es_indic_imperf: `${WIKI}Imperfect`,
	es_indic_fut: `${WIKI}Future_tense`,
	es_cond_pres: `${WIKI}Conditional_mood`,
	es_subj_pres: `${WIKI}Subjunctive_mood`,
	es_subj_imperf: `${WIKI}Subjunctive_mood`,
	es_indic_pres_perf: `${WIKI}Perfect_(grammar)`,
	es_indic_pluperf: `${WIKI}Pluperfect`,
	es_impers_inf: `${WIKI}Infinitive`,
	es_impers_gerund: `${WIKI}Gerund`,
	es_impers_past_partic: `${WIKI}Past_participle`
};

export function getTenseWikiLink(tenseCode: string): string | undefined {
	return tenseWikiLinks[tenseCode];
}
