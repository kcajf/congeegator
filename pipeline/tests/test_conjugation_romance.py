"""Portuguese/Catalan regressions checked against source and grammar references."""
import json
from pathlib import Path

import msgspec
import pytest

from pipeline.conjugation import extract_conjugation, make_language_static_metadata
from pipeline.conjugation_romance import CA_CONFIG, PT_CONFIG, preprocess_ca_forms, romance_form_filter
from pipeline.wiktionary import Entry, Form

FIXTURES = Path(__file__).parent / 'fixtures'
GOLDEN = Path(__file__).parent / 'golden' / 'conj'
CONFIGS = {'pt': PT_CONFIG, 'ca': CA_CONFIG}
ENTRIES = {
    lang: {entry.word: entry for line in (FIXTURES / f'{lang}_verbs.jsonl').read_bytes().splitlines()
           if (entry := msgspec.json.decode(line, type=Entry))}
    for lang in CONFIGS
}


def table(lang, word):
    config = CONFIGS[lang]
    result = extract_conjugation(config, ENTRIES[lang][word])
    assert result is not None
    return dict(zip((t.name for t in config.tenses), result['conjugation']))


@pytest.mark.parametrize('lang,word', [(lang,word) for lang,entries in ENTRIES.items() for word in entries])
def test_reviewed_romance_golden(lang, word, update_golden):
    result = extract_conjugation(CONFIGS[lang], ENTRIES[lang][word])
    path = GOLDEN / f'{lang}_{word}.json'
    if update_golden:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    assert json.loads(msgspec.json.encode(result)) == json.loads(path.read_text())


def test_portuguese_personal_infinitive_is_not_future_subjunctive():
    # Independent irregular probe: ser -> seres vs fores; pôr -> pores vs puseres.
    assert table('pt','ser')['pt_inf_personal'] == ('ser','seres','ser','sermos','serdes','serem')
    assert table('pt','ser')['pt_subj_fut'] == ('for','fores','for','formos','fordes','forem')
    assert table('pt','pôr')['pt_inf_personal'][1] == 'pores'
    assert table('pt','pôr')['pt_subj_fut'][1] == 'puseres'


def test_portuguese_three_regular_classes_and_irregular_principal_parts():
    for verb,present,preterite,participle in [('falar','falo','falei','falado'),('comer','como','comi','comido'),('partir','parto','parti','partido'),('pôr','ponho','pus','posto')]:
        result=table('pt',verb)
        assert (result['pt_indic_pres'][0],result['pt_indic_pret'][0],result['pt_impers_partic']) == (present,preterite,participle)


def test_portuguese_region_and_historical_labels_survive():
    assert table('pt','falar')['pt_indic_pret'][3] == 'falamos (Brazil)/falámos (Portugal)'
    assert table('pt','abolir')['pt_indic_pres'][0] == 'abulo (Portugal)'
    assert table('pt','abolir')['pt_subj_pres'][3] == 'abulamos (Portugal)'
    assert 'adeqüei (Brazil, pre-reform)' in table('pt','adequar')['pt_indic_pret'][0]
    assert 'adeqúe (pre-reform)' in table('pt','adequar')['pt_subj_pres'][0]


def test_portuguese_defective_cells_and_contracted_second_table():
    assert table('pt','reaver')['pt_indic_pres'] == ('','','','reavemos','reaveis','')
    assert table('pt','reaver')['pt_subj_pres'] == ('',)*6
    assert table('pt','reaver')['pt_imper'] == ('','','','reavei','')
    assert table('pt','estar')['pt_indic_pres'] == ('estou','estás','está','estamos','estais','estão')


def test_catalan_lexical_anar_is_separate_from_the_past_auxiliary():
    result=table('ca','anar')
    assert result['ca_indic_pres'] == ('vaig','vas','va','anem','aneu','van')
    assert result['ca_indic_periphrastic'] == ('vaig anar','vas anar/vares anar','va anar','vam anar/vàrem anar','vau anar/vàreu anar','van anar/varen anar')
    assert result['ca_subj_pres'][3:5] == ('anem','aneu')


def test_catalan_imperative_missing_singular_tag_and_formal_person():
    assert table('ca','cantar')['ca_imper'] == ('canta','canti','cantem','canteu','cantin')
    assert table('ca','dir')['ca_imper'] == ('digues','digui','diguem','digueu','diguin')


def test_catalan_regular_and_inchoative_ir_classes():
    assert table('ca','dormir')['ca_indic_pres'] == ('dormo','dorms','dorm','dormim','dormiu','dormen')
    assert table('ca','servir')['ca_indic_pres'] == ('serveixo','serveixes','serveix','servim','serviu','serveixen')
    assert table('ca','ésser')['ca_impers_partic'] == 'estat/sigut'


def test_catalan_synthetic_past_does_not_invent_defective_persons():
    result=table('ca','caldre')
    assert result['ca_indic_pres'] == ('','','cal','','','calen')
    assert result['ca_indic_periphrastic'] == ('','','va caldre','','','van caldre/varen caldre')
    assert result['ca_imper'] == ('',)*5


def test_missing_infinitive_does_not_generate_compounds():
    entry=Entry(pos='verb',lang_code='ca',lang='Catalan',word='test',forms=(Form('testà',{'third-person','singular','indicative','preterite'},'conjugation'),))
    assert not any('periphrastic' in f.tags for f in preprocess_ca_forms(entry))


@pytest.mark.parametrize('text,tags', [('3',{'class'}),('root stress:',{'infinitive'}),('e̞',{'canonical'}),('—',{'present'}),('-',{'present'}),('no cantis',{'negative','imperative'}),('haver + participle',{'multiword-construction'}),('[[canta]]',{'present'})])
def test_romance_filter_rejects_table_metadata_and_unexpanded_text(text,tags):
    assert not romance_form_filter(Form(text,tags,'conjugation'))


@pytest.mark.parametrize('config',[PT_CONFIG,CA_CONFIG])
def test_romance_metadata_has_complete_native_labels_and_person_rows(config):
    messages=json.loads((Path(__file__).parents[2]/'apps/congeegator/src/lib/messages'/f'{config.code}.json').read_text())
    meta=make_language_static_metadata(config)
    assert set(meta['tenseNames']) <= messages.keys()
    assert {g['name'] for g in meta['tenseGroups']} <= messages.keys()
    assert all(len(row) in (0,5,6) for row in meta['tensePronouns'])


def test_weather_verbs_preserve_reviewed_usage_restrictions():
    assert table('pt','chover')['pt_indic_pres'] == ('chovo (figurative)','choves (figurative)','chove','chovemos (figurative)','choveis (figurative)','chovem (figurative)')
    assert all('(figurative)' in f for f in table('pt','chover')['pt_imper'])
    assert table('ca','ploure')['ca_indic_pres'] == ('','','plou','','','plouen')
    assert table('ca','ploure')['ca_indic_periphrastic'] == ('','','va ploure','','','van ploure/varen ploure')
    assert table('ca','ploure')['ca_imper'] == ('',)*5


def test_primary_table_matches_lemma_before_accepting_reflexive_forms():
    assert table('pt','suicidar')['pt_indic_pres'][0] == 'suicido'
    assert table('pt','suicidar')['pt_impers_inf'] == 'suicidar'
    for word in ('arrepender','assoar'):
        assert extract_conjugation(PT_CONFIG,ENTRIES['pt'][word]) is None
    # The first complete primary paradigm is the reviewed Infopedia paradigm.
    assert table('pt','mediar')['pt_indic_pres'][0] == 'medeio'
    assert table('pt','transir')['pt_indic_pres'] == ('','','','transimos','transis','')


@pytest.mark.parametrize('word,present',[('dansar','danso'),('vaporar','vaporo'),('bogejar','bogejo')])
def test_explicit_ca_conj_template_recovers_misclassified_verb_table(word,present):
    assert table('ca',word)['ca_indic_pres'][0] == present


def test_coure_participles_keep_their_independent_meanings():
    assert table('ca','coure')['ca_impers_partic'] == 'cuit (cooking)/cogut (stinging)'


def test_portuguese_old_circumflex_spellings_are_historical():
    assert table('pt','voar')['pt_indic_pres'][0] == 'voo/vôo (Brazil, pre-reform)'
    assert table('pt','ler')['pt_indic_pres'][5] == 'leem/lêem (pre-reform)'
