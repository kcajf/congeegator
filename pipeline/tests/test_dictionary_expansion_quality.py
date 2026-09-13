"""Regressions witnessed in the September 2026 raw Kaikki snapshot."""
import copy
from pathlib import Path

import msgspec
import pytest

from pipeline.dictionary import DictLanguageConfig, process_dict_entry
from pipeline.dictionary_quality import QUALITY_LANGUAGES, enhance_record, trusted_persian_head
from pipeline.wiktionary import Entry

ENTRIES = [msgspec.json.decode(line, type=Entry) for line in
           (Path(__file__).parent / 'fixtures/dictionary_expansion_quality.jsonl').read_bytes().splitlines()]


def records(code, word):
    return [r for e in ENTRIES if e.lang_code == code and e.word == word
            if (r := process_dict_entry(DictLanguageConfig(code, code, code), e))]


def first(code, word):
    return records(code, word)[0]


def test_ancient_greek_gender_periods_and_dialect_forms():
    r = first('grc', 'ὕδωρ')
    assert r['gender'] == 'n'
    assert all('label' in p for p in r['pronunciations'])
    assert any('Attic' in p['label'] for p in r['pronunciations'])
    assert any('Koine' in p['label'] for p in r['pronunciations'])
    assert any('Epic' in f['tags'] for f in r['formDetails'])
    assert not any('hŭ' in f for f in r['forms'])
    assert not {'εἶτον', 'εἴτην', 'εἶμεν', 'εἶτε', 'εἶεν'} & set(first('grc', 'ἄγω')['forms'])
    assert 'εἶτον' in first('grc', 'εἰμί')['forms']


def test_unlabelled_ancient_greek_ipa_does_not_get_guessed_period():
    e = next(e for e in ENTRIES if e.lang_code == 'grc')
    e = msgspec.structs.replace(e, sounds=({'ipa': '/test/'},))
    r = process_dict_entry(DictLanguageConfig('grc', 'Greek', 'Ancient Greek'), e)
    assert 'pronunciation' not in r
    assert 'pronunciations' not in r


@pytest.mark.parametrize('code,word,bad', [
    ('az', 'olmaq', '(mənim +)'), ('mk', 'сум', '+'),
    ('sk', 'dom', 'nominative'), ('sk', 'slzička', 'žena'),
    ('br', 'moan', 'never occurs'), ('is', 'fær', 'declension'),
    ('is', 'þvo', 'conjugation'), ('ga', 'bhfeolta', 'obsolete'),
    ('ka', 'აკეთებს', 'with neutral versioner'), ('he', 'היה', 'Second person future tense'),
    ('ko', '먹다', 'Formal non polite'), ('oc', 'faire', '['),
])
def test_contextual_table_debris_removed(code, word, bad):
    assert records(code, word)
    assert not any(bad in f for r in records(code, word) for f in r.get('forms', []))


def test_hebrew_head_spelling_not_literal_form_annotation_and_labelled_ipa():
    assert not any(f.startswith('form ') for f in first('he', 'בית')['forms'])
    r = first('he', 'שלום')
    assert any('Biblical' in p.get('label', '') for p in r['pronunciations'])
    assert any('Modern Israeli' in p.get('label', '') for p in r['pronunciations'])


def test_hindi_repair_requires_attestation_in_head_expansion():
    r = next(r for r in records('hi', 'पण्डित') if r['pos'] == 'noun')
    assert 'पण्डिता' in r['forms']
    assert 'पण्डित ा' not in r['forms']


def test_korean_counters_are_not_inflections():
    assert '대' not in first('ko', '자동차').get('forms', [])
    assert '권' not in first('ko', '책').get('forms', [])


def test_persian_lexical_heads_recover_and_varieties_stay_labelled():
    assert first('fa', 'بودن')['senses']
    assert first('fa', 'خوردن')['senses']
    r = first('fa', 'خانه')
    assert 'خانهها' in r['forms'] and 'خانها' in r['forms']
    assert not any('(' in f or 'ZWNJ' in f for f in r['forms'])
    assert any('Classical Persian' in p.get('label', '') for p in r['pronunciations'])
    assert any('Iran' in p.get('label', '') for p in r['pronunciations'])
    assert any(f['form'] == 'хона' and 'Tajik' in f['tags'] for f in r['formDetails'])
    e = next(e for e in ENTRIES if e.lang_code == 'fa' and e.word == 'بودن')
    assert not trusted_persian_head(msgspec.structs.replace(e, head_templates=()))
    assert not trusted_persian_head(msgspec.structs.replace(e, word='budan'))


def test_sanskrit_gender_and_periods_without_unresolved_footnote_forms():
    assert first('sa', 'गृह')['gender'] == 'm-n'
    assert any(r.get('gender') == 'n' for r in records('sa', 'जल'))
    assert not any(f[-1:].isdigit() for r in records('sa', 'गृह') for f in r.get('forms', []))
    assert {p.get('label') for p in first('sa', 'गृह')['pronunciations']} == {'Vedic', 'Classical Sanskrit'}


def test_genderless_languages_do_not_turn_female_equivalents_into_gender():
    for code, word in [('az', 'müəllimə'), ('ms', 'siswi')]:
        assert 'gender' not in first(code, word)


@pytest.mark.parametrize('code,word,gender', [('mk', 'вода', 'f'), ('sh', 'voda', 'f'), ('sh', 'mlijeko', 'n'), ('lt', 'vanduo', 'm')])
def test_attested_canonical_gender(code, word, gender):
    assert first(code, word)['gender'] == gender


@pytest.mark.parametrize('code,word,label', [('sh', 'mlijeko', 'Ijekavian'), ('sh', 'mleko', 'Ekavian'), ('ms', 'gratis', 'Indonesia'), ('oc', 'ostal', 'Languedoc'), ('cy', 'mi', 'North Wales')])
def test_source_varieties_retained(code, word, label):
    assert any(label in s.get('tags', []) for r in records(code, word) for s in r['senses'])


def test_valid_error_tagged_lithuanian_and_basque_forms_survive():
    assert any('ariù' in r.get('forms', []) for r in records('lt', 'arti'))
    assert 'etxean' in first('eu', 'etxe')['forms']


@pytest.mark.parametrize('code', 'fr el de es it en pt ca ro gl nl sv da nb pl ru uk cs fi hu tr id vi eo la'.split())
def test_existing_25_language_records_are_a_strict_noop(code):
    e = msgspec.structs.replace(ENTRIES[0], lang_code=code)
    r = {'word': 'test', 'pos': 'noun', 'senses': [{'gloss': 'test'}], 'forms': ['never occurs'], 'gender': 'f', 'pronunciation': '/x/'}
    before = copy.deepcopy(r)
    assert code not in QUALITY_LANGUAGES
    assert enhance_record(e, r, str.strip) is r
    assert r == before


def test_every_form_detail_refers_to_a_retained_indexed_form():
    for e in ENTRIES:
        r = process_dict_entry(DictLanguageConfig(e.lang_code, e.lang, e.lang), e)
        if r:
            assert all(f['form'] in r.get('forms', []) and f['tags'] for f in r.get('formDetails', []))


def test_english_looking_serbo_croatian_inflections_are_real_words():
    assert 'nominative' in first('sh', 'nominativ')['forms']
    assert 'dative' in first('sh', 'dativ')['forms']


@pytest.mark.parametrize('code,word', [('lt', 'abelnas'), ('sh', 'karo'), ('sh', 'каро')])
def test_unexpanded_term_placeholder_is_never_a_spelling(code, word):
    assert records(code, word)
    assert all('Term?' not in r.get('forms', []) for r in records(code, word))


def test_raw_period_and_meaning_qualifiers_remain_attached():
    assert any('in Attic prose' in s.get('tags', []) for s in first('grc', 'μῦθος')['senses'])
    assert any('in Koine' in s.get('tags', []) for s in first('grc', 'ὑμέτερος')['senses'])
    kind = {f['form']: f['tags'] for f in first('is', 'kind')['formDetails']}
    assert kind['kindir'] == ['in the meaning race']
    fjandi = {f['form']: f['tags'] for f in first('is', 'fjandi')['formDetails']}
    assert 'in the meaning "devil"' in fjandi['fjandar']
    assert 'in the meaning "enemy"' in fjandi['fjendur']


def test_occitan_compound_instructions_removed_but_attested_compounds_retained():
    forms = first('oc', 'cavar')['forms']
    assert not any(f.startswith('use ') for f in forms)
    assert 'aver cavat' in forms


def test_coordinate_linkage_is_not_a_usage_example():
    assert not any('Coordinate term:' in x for s in first('grc', 'γυνή')['senses'] for x in s.get('examples', []))


def test_water_long_vowel_ipa_retains_verified_epic_condition():
    pronunciations = first('grc', 'ὕδωρ')['pronunciations']
    long_vowel = [p for p in pronunciations if p['ipa'] == '/hy̌ː.dɔːr/']
    assert long_vowel == [{'ipa': '/hy̌ː.dɔːr/',
                           'label': '5ᵗʰ BCE Attic; Epic poetic variant; long υ'}]
    assert {'ipa': '/hý.dɔːr/', 'label': '5ᵗʰ BCE Attic'} in pronunciations
    assert all('Epic poetic variant' not in p.get('label', '')
               for p in pronunciations if p['ipa'] != '/hy̌ː.dɔːr/')
