"""Headword inflections retain their meanings without needing separate pages."""
import json
from pathlib import Path
import sqlite3

import msgspec
import pytest

from pipeline.dictionary import DICT_CONFIGS, DictLanguageConfig, process_dict_entry
from pipeline.dictionary_quality import form_grammar
from pipeline.sqlite_output import write_sqlite_database
from pipeline.wiktionary import Entry, Form, Sense


def test_azerbaijani_head_forms_and_synonym_survive_database_output(tmp_path):
    source = (Path(__file__).parent / 'fixtures/dictionary_az_flag.jsonl').read_bytes()
    entry = msgspec.json.decode(source, type=Entry)
    record = process_dict_entry(DictLanguageConfig('az', 'az', 'Azerbaijani'), entry)
    expected = [
        {'form': 'flağı', 'kind': 'inflection', 'readings': [{'grammar': ['definite', 'accusative']}]},
        {'form': 'flağlar', 'kind': 'inflection', 'readings': [{'grammar': ['plural']}]},
    ]
    assert record['forms'] == ['flağı', 'flağlar']
    assert record['formDetails'] == expected
    record['freq'] = 0
    path = tmp_path / 'az.sqlite'
    write_sqlite_database([record], 'az', None, str(path))
    with sqlite3.connect(path) as conn:
        senses, details = conn.execute('SELECT senses, form_details FROM entries').fetchone()
    assert json.loads(details) == expected
    assert json.loads(senses)[0]['synonyms'] == [{'word': 'bayraq', 'lang': 'az'}]


def test_form_grammar_excludes_extractor_metadata_and_does_not_guess():
    assert form_grammar({'plural', 'error-unrecognized-form', 'noun', 'canonical'}) == ['plural']
    assert form_grammar({'rare', 'table-tags'}) == []
    assert form_grammar({'past', 'participle', 'passive'}) == ['passive past participle']


@pytest.mark.parametrize('config', DICT_CONFIGS, ids=lambda c: c.code)
def test_every_dictionary_stores_grammatical_form_labels(config, tmp_path):
    # No language-specific spelling repair or pronunciation assumptions needed.
    spelling = {'el': 'λόγοι', 'grc': 'λόγοι', 'fa': 'کتابها', 'hi': 'घर', 'sa': 'गृहाणि'}.get(config.code, 'forms')
    entry = Entry(word='lemma', lang=config.english_wiktionary_name,
                  lang_code=config.code, pos='noun',
                  senses=(Sense(glosses=('test',)),),
                  forms=(Form(form=spelling, tags={'plural'}),))
    record = process_dict_entry(config, entry)
    assert record['formDetails'] == [{'form': spelling, 'kind': 'inflection', 'readings': [{'grammar': ['plural']}]}]
    path = tmp_path / 'dictionary.sqlite'
    write_sqlite_database([record], config.code, None, str(path))
    with sqlite3.connect(path) as conn:
        stored = json.loads(conn.execute('SELECT form_details FROM entries').fetchone()[0])
    assert stored == record['formDetails']


def test_modern_greek_source_forms_keep_labels_and_exclude_table_instructions(tmp_path):
    source = (Path(__file__).parent / 'fixtures/dictionary_el_apantao.jsonl').read_bytes()
    entry = msgspec.json.decode(source, type=Entry)
    record = process_dict_entry(next(c for c in DICT_CONFIGS if c.code == 'el'), entry)
    details = {f['form']: reading_labels(f) for f in record['formDetails']}
    assert any('past' in label for label in details['απάντησα'])
    assert any('second person active present indicative singular' in label for label in details['απαντάς'])
    assert any('imperfective' in label for label in details['απαντάς'])
    assert 'απαντιέμαι' in details and 'απαντώμαι' in details
    assert 'θα απαντώμαι' in details
    assert not any('future' in tag for tag in details['απαντώμαι'])
    assert 'active aorist infinitive' in details['απαντήσει']
    assert any('dependent' in tag for tag in details['απαντήσω'])
    assert 'απαντάτο' in details
    assert 'απαντώμενος' in details
    assert 'έχοντας απαντήσει' in details
    assert not any(' - ' in f or 'Formed' in f or 'from above' in f for f in record['forms'])
    assert not {'- —', '‑η', '‑ο', 'η', 'ο'} & set(record['forms'])
    path = tmp_path / 'el.sqlite'
    write_sqlite_database([record], 'el', None, str(path))
    with sqlite3.connect(path) as conn:
        assert json.loads(conn.execute('SELECT form_details FROM entries').fetchone()[0]) == record['formDetails']
        assert conn.execute('SELECT COUNT(*) FROM form_lookup WHERE form_key = ?', ('απαντώμαι',)).fetchone()[0] == 1


def reading_labels(detail):
    return [label for reading in detail.get('readings', [])
            for label in ([' '.join(reading.get('grammar', []))] + reading.get('qualifiers', [])) if label]
