"""Headword inflections retain their meanings without needing separate pages."""
import json
from pathlib import Path
import sqlite3

import msgspec

from pipeline.dictionary import DictLanguageConfig, process_dict_entry
from pipeline.dictionary_quality import form_grammar
from pipeline.sqlite_output import write_sqlite_database
from pipeline.wiktionary import Entry


def test_azerbaijani_head_forms_and_synonym_survive_database_output(tmp_path):
    source = (Path(__file__).parent / 'fixtures/dictionary_az_flag.jsonl').read_bytes()
    entry = msgspec.json.decode(source, type=Entry)
    record = process_dict_entry(DictLanguageConfig('az', 'az', 'Azerbaijani'), entry)
    expected = [
        {'form': 'flağı', 'tags': ['definite accusative']},
        {'form': 'flağlar', 'tags': ['plural']},
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
