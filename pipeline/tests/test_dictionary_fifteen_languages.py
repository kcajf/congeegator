"""Real English Wiktionary source regressions for the fifteen new dictionaries."""
from pathlib import Path
import sqlite3

import msgspec
import pytest

from pipeline.dictionary import DICT_CONFIGS, process_dict_entry
from pipeline.sqlite_output import dictionary_search_key, write_sqlite_database
from pipeline.wiktionary import Entry
from pipeline.packed_entries import PackedDictionaryEntries

CONFIGS = {c.code: c for c in DICT_CONFIGS}
ENTRIES = [msgspec.json.decode(line, type=Entry) for line in
           (Path(__file__).parent / 'fixtures/dictionary_fifteen_languages.jsonl').read_bytes().splitlines()]


def records(code, word):
    return [r for e in ENTRIES if e.lang_code == code and e.word == word
            if (r := process_dict_entry(CONFIGS[code], e))]


@pytest.mark.parametrize('code,word', [
    ('ar', 'ماء'), ('zh', '水'), ('ja', '水'), ('ast', 'agua'), ('nv', 'tó'),
    ('sq', 'ujë'), ('te', 'నీరు'), ('sw', 'maji'), ('hy', 'ջուր'), ('th', 'น้ำ'),
    ('ceb', 'tubig'), ('ta', 'நீர்'), ('bn', 'জল'), ('pa', 'ਪਾਣੀ'), ('ur', 'پانی'),
])
def test_every_dictionary_retains_water_definition(code, word):
    assert any('water' in s['gloss'].lower() for r in records(code, word) for s in r['senses'])


def test_chinese_characters_and_redirects_are_lexical_content():
    assert records('zh', '吃')
    simplified = records('zh', '中国')[0]
    assert simplified['senses'][0]['links'] == [{'word': '中國', 'lang': 'zh'}]
    assert any('中国' in r.get('forms', []) for r in records('zh', '中國'))


def test_japanese_readings_and_clean_conjugations():
    eat = records('ja', '食べる')[0]
    assert {'たべる', 'taberu'} <= {r['text'] for r in eat['details']['readings']}
    assert '食べられる' in eat['forms']
    assert not any('[' in form or 'short form:' in form for form in eat['forms'])
    assert records('ja', 'たべる')[0]['senses'][0]['links'][0]['word'] == '食べる'


@pytest.mark.parametrize('code,word,query', [
    ('ar', 'كتاب', 'كُتُب'), ('ar', 'كتاب', 'كتب'),
    ('ja', '食べる', 'タベル'), ('ja', '食べる', 'ﾀﾍﾞﾙ'),
    ('ja', '食べる', 'taberu'), ('zh', '中國', '中国'),
    ('ur', 'پانی', 'pānī'),
])
def test_readings_and_forms_return_their_entry_from_sqlite(tmp_path, code, word, query):
    path = tmp_path / 'dictionary.sqlite'
    packed = PackedDictionaryEntries()
    for record in records(code, word):
        packed.append(record)
    write_sqlite_database(packed, code, None, str(path))
    with sqlite3.connect(path) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        found = conn.execute('SELECT e.word FROM form_lookup f JOIN entries e ON e.id=f.entry_id '
                             'WHERE f.form_key=?', (dictionary_search_key(query, code),)).fetchall()
        assert (word,) in found


@pytest.mark.parametrize('code,word', [('bn','জল'), ('pa','ਪਾਣੀ'), ('te','నీరు'), ('ta','நீர்'), ('th','น้ำ')])
def test_search_keeps_meaningful_vowel_marks(code, word):
    assert dictionary_search_key(word, code) == word


def test_arabic_search_keeps_hamza_and_display_spelling():
    assert dictionary_search_key('كِتَـاب', 'ar') == 'كتاب'
    assert dictionary_search_key('آب', 'ar') != dictionary_search_key('اب', 'ar')
    assert any('كِتَاب' in r.get('forms', []) for r in records('ar', 'كتاب'))
