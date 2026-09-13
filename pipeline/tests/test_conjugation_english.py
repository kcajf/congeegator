"""Current-source English headword adapter and its grammatical row contract."""
import json
from pathlib import Path

import msgspec
import pytest

from pipeline.conjugation import EN_CONFIG, extract_conjugation
from pipeline.conjugation_english import merge_english_records, preprocess_en_forms
from pipeline.wiktionary import Entry, Form, HeadTemplate, Sense

ROOT = Path(__file__).parent
ENTRIES = [msgspec.json.decode(line,type=Entry) for line in (ROOT/'fixtures/english_head_verbs.jsonl').read_bytes().splitlines()]


def record(word):
    result = None
    for entry in ENTRIES:
        if entry.word == word and (current := extract_conjugation(EN_CONFIG,entry)):
            result = merge_english_records(result,current) if result else current
    return result


GOLDEN_WORDS = 'be have do go walk make get read run cut put set can may might must shall should will beware need dare lie bear lead wind ring stick spit spell learn hang'.split() + ['get up','look up','look after','take off','fine-tune']


@pytest.mark.parametrize('word',GOLDEN_WORDS)
def test_current_source_english_golden(word,update_golden):
    result=record(word)
    assert result is not None
    path=ROOT/'golden/conj'/f"en_head_{word.replace(' ','_')}.json"
    if update_golden:path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert json.loads(msgspec.json.encode(result)) == json.loads(path.read_text())


@pytest.mark.parametrize('word,third,past,pp',[('have','has','had','had'),('do','does','did','done'),('go','goes','went','gone'),('make','makes','made','made'),('read','reads','read','read'),('run','runs','ran','run'),('cut','cuts','cut','cut')])
def test_principal_parts_supply_person_rows_without_suffix_generation(word,third,past,pp):
    rows=record(word)['conjugation']
    assert rows[3] == (word,word,third,word,word,word)
    assert rows[4] == (past,)*6
    assert rows[2] == pp
    assert rows[5][2] == f'has {pp}'


def test_modern_be_uses_attested_person_specific_table():
    rows=record('be')['conjugation']
    assert rows[3] == ('am','are','is','are','are','are')
    assert rows[4] == ('was','were','was','were','were','were')


@pytest.mark.parametrize('word,past',[('can','could'),('may','might'),('shall','should'),('will','would'),('must',''),('might',''),('should','')])
def test_modals_have_only_reviewed_attested_finite_forms(word,past):
    rows=record(word)['conjugation']
    assert rows[:3] == ['','','']
    assert rows[3] == (word,)*6
    assert rows[4] == (past,)*6
    assert rows[5:] == [('',)*6]*3


@pytest.mark.parametrize('word',['met','contra','consarn','unbe','partial','baby-sit','kick the bucket'])
def test_partial_malformed_and_form_of_entries_are_not_completed_by_guessing(word):
    assert record(word) is None


def test_unidentified_source_none_forms_are_not_accepted():
    forms=tuple(Form(text,tags) for text,tags in [('tests',{'present','singular','third-person'}),('testing',{'participle','present'}),('tested',{'past'}),('tested',{'participle','past'})])
    entry=Entry('verb','en','English','test',forms=forms)
    assert preprocess_en_forms(entry) == []
    trusted=msgspec.structs.replace(entry,head_templates=(HeadTemplate('en-verb'),))
    assert extract_conjugation(EN_CONFIG,trusted) is not None
    form_of=msgspec.structs.replace(trusted,senses=(Sense(tags=('form-of',)),))
    assert extract_conjugation(EN_CONFIG,form_of) is None


def test_attested_phrase_forms_keep_particle_and_reject_truncated_head_parts():
    rows=record('get up')['conjugation']
    assert rows[3][2] == 'gets up'
    assert rows[4][0] == 'got up'
    assert 'have gotten up (US)' in rows[5][0]
    base=next(e for e in ENTRIES if e.word=='walk')
    truncated=msgspec.structs.replace(base,word='walk away')
    assert preprocess_en_forms(truncated) == []


def test_modern_may_gloss_excludes_historical_strength_and_ability():
    entry = next(e for e in ENTRIES if e.word == 'may' and any('modal' in s.tags for s in e.senses))
    original_senses = entry.senses
    result = extract_conjugation(EN_CONFIG, entry)
    assert 'permission' in result['gloss']
    assert 'strong' not in result['gloss']
    assert 'have power' not in result['gloss']
    assert entry.senses == original_senses


def test_drink_shared_historical_qualifier_and_regional_past():
    rows = record('drink')['conjugation']
    assert rows[4][0] == 'drank/drunk (Southern US)'
    assert rows[2] == 'drunk/drank (dialectal)'
    assert rows[5][0] == 'have drunk/have drank (dialectal)'
