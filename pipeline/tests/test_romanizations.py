import json
from pathlib import Path
import sqlite3

import msgspec
import pytest

from pipeline.dictionary import DICT_CONFIGS, process_dict_entry
from pipeline.packed_entries import PackedDictionaryEntries
from pipeline.romanizations import romanization_keys
from pipeline.sqlite_output import write_sqlite_database
from pipeline.wiktionary import Entry

FIXTURES = json.loads((Path(__file__).resolve().parents[2] / 'shared/romanization-fixtures.json').read_text())
CONFIGS = {c.code: c for c in DICT_CONFIGS}


def record(lang, forms, word='word'):
    entry = msgspec.convert({'lang_code': lang, 'lang': CONFIGS[lang].english_wiktionary_name,
        'word': word, 'pos': 'noun', 'senses': [{'glosses': ['example'], 'form_of': [{'word': 'base'}]}],
        'forms': forms}, type=Entry)
    return process_dict_entry(CONFIGS[lang], entry)


@pytest.mark.parametrize('fixture', FIXTURES)
def test_shared_language_keyboard_rules(fixture):
    keys = dict(romanization_keys(fixture['lang'], fixture['reading']))
    assert fixture['key'] in keys
    assert romanization_keys(fixture['lang'], fixture['key']) == [(fixture['key'], 5)]
    assert keys[fixture['key']] == 5
    assert dict(romanization_keys(fixture['lang'], fixture['reading'].upper())) == keys


def test_headword_only_and_standalone_inflected_entries():
    output = record('ru', [
        {'form': 'sobáki', 'tags': ['romanization']},
        {'form': 'sobáki', 'tags': ['transliteration']},
        {'form': 'собак', 'roman': 'sobak', 'source': 'declension'},
        {'form': 'other', 'roman': 'other'},
        {'form': '{{broken}}', 'tags': ['romanization']},
        {'form': 'one / two', 'tags': ['romanization']},
    ], 'собаки')
    assert output['romanizations'] == ['sobáki']
    assert all('romanizations' not in f for f in output.get('formDetails', []))
    assert 'sobáki' not in output.get('forms', [])
    assert output['senses'][0]['formOf']


def test_missing_or_unsupported_readings_are_omitted():
    assert 'romanizations' not in record('he', [])
    assert 'romanizations' not in record('fr', [{'form': 'dog', 'tags': ['romanization']}])


@pytest.mark.parametrize('packed', [False, True])
@pytest.mark.parametrize('lang', ['ru', 'he'])
def test_readings_and_keys_survive_both_database_generation_paths(tmp_path, packed, lang):
    entry = record(lang, [{'form': 'šalóm', 'tags': ['romanization']}])
    entries = PackedDictionaryEntries() if packed else []
    entries.append(entry)
    path = tmp_path / 'readings.sqlite'
    write_sqlite_database(entries, lang, None, str(path))
    with sqlite3.connect(path) as db:
        assert json.loads(db.execute('SELECT romanizations FROM entries').fetchone()[0]) == ['šalóm']
        assert db.execute("SELECT value FROM metadata WHERE key='romanization_version'").fetchone()[0] == '1'
        assert db.execute("SELECT entry_id FROM romanized_lookup WHERE key='shalom'").fetchall() == [(0,)]
        assert db.execute('SELECT COUNT(*) FROM romanized_lookup').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM form_lookup').fetchone()[0] == 0
