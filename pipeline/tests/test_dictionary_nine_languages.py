"""Real source regressions from the nine September 14 dictionary additions."""
from pathlib import Path
import sqlite3
import unicodedata

import msgspec
import pytest

from pipeline.dictionary import DICT_CONFIGS, process_dict_entry
from pipeline.entry_json import decode_entry_json
from pipeline.sqlite_output import dictionary_search_key, write_sqlite_database
from pipeline.wiktionary import Entry

CONFIGS = {c.code: c for c in DICT_CONFIGS}
ENTRIES = [msgspec.json.decode(line, type=Entry) for line in
           (Path(__file__).parent / 'fixtures/dictionary_nine_languages.jsonl').read_bytes().splitlines()]


def records(code, word):
    return [r for e in ENTRIES if e.lang_code == code and e.word == word
            if (r := process_dict_entry(CONFIGS[code], e))]


def first(code, word):
    return records(code, word)[0]


def test_nynorsk_mixed_gender_and_usage_notes():
    assert first('nn', 'smell')['gender'] == 'm-n'
    assert all('since 1938' not in r.get('forms', []) for r in records('nn', 'leider'))
    song = first('nn', 'syngja')
    assert 'song' in song['forms']
    assert not any('brackets' in f for f in song['forms'])
    assert 'Blåtann' in first('nn', 'blåtann')['forms']
    assert '(alternative case) Blåtann' not in first('nn', 'blåtann')['forms']


def test_latvian_headers_and_broken_paradigms_not_searchable_as_forms():
    robot = first('lv', 'robot')
    assert 'roboju' in robot['forms']
    assert not {'conjugation', 'es', 'tu', 'mēs', 'jūs'} & set(robot['forms'])
    assert 'declension' not in first('lv', 'trīs').get('forms', [])
    broken = first('lv', 'redzēdamies')
    assert broken['senses']
    assert not broken.get('forms')


def test_bulgarian_gender_and_labelled_dialect_pronunciation():
    water = first('bg', 'вода')
    assert water['gender'] == 'f'
    assert any('Western' in p.get('label', '') for p in water['pronunciations'])
    assert 'води́' in water['forms']
    assert not any('+' in f for f in first('bg', 'палячо')['forms'])


def test_gaelic_archaic_form_label_is_separate_from_spelling():
    bean = first('gd', 'bean')
    assert "(a') mhnaoi" in bean['forms']
    assert "(a') mhnaoi (archaic)" not in bean['forms']
    assert any(f['form'] == "(a') mhnaoi" and any('archaic' in r.get('qualifiers', [])
               for r in f['readings']) for f in bean['formDetails'])


def test_tagalog_script_and_aspect_forms_survive_without_spurious_gender():
    eat = first('tl', 'kumain')
    assert {'kumakain', 'kakain', 'ᜃᜓᜋᜁᜈ᜔'} <= set(eat['forms'])
    assert any('Standard Tagalog' in p.get('label', '') for p in eat['pronunciations'])
    assert 'gender' not in first('tl', 'babae')
    assert not {'superseded', 'pre-2007'} & set(first('tl', 'ganansiya')['forms'])


def test_english_looking_faroese_and_old_english_forms_are_not_headers():
    assert 'strong' in first('fo', 'strongur')['forms']
    assert 'strong' in first('ang', 'strang')['forms']
    assert first('ang', 'hus')['gender'] == 'n'
    assert 'hūs' in first('ang', 'hus')['forms']


@pytest.mark.parametrize('code,word,form', [
    ('lv', 'ūdens', 'ūdeņiem'), ('bg', 'вода', 'води́'),
    ('mt', 'ilma', 'ilmijiet'), ('gd', 'taigh', 'taighean'),
    ('fo', 'strongur', 'strong'), ('ang', 'hus', 'hūs'),
    ('ang', 'beon', 'bēon'), ('non', 'vatn', 'vǫtn'),
    ('tl', 'kumain', 'ᜃᜓᜋᜁᜈ᜔'), ('nn', 'syngja', 'song'),
])
def test_actual_imported_forms_survive_sqlite_and_unicode_lookup(tmp_path, code, word, form):
    entries = [dict(r, freq=0.0) for r in records(code, word)]
    path = tmp_path / 'dictionary.sqlite'
    write_sqlite_database(entries, code, None, str(path))
    query = unicodedata.normalize('NFD', form.upper())
    with sqlite3.connect(path) as conn:
        matches = conn.execute('SELECT e.word FROM form_lookup f JOIN entries e ON e.id=f.entry_id '
                               'WHERE form_key=?', (dictionary_search_key(query, code),)).fetchall()
        stored = conn.execute('SELECT pronunciations FROM entries ORDER BY id').fetchall()
        assert [decode_entry_json(row[0]) if row[0] else None for row in stored] == [
            r.get('pronunciations') for r in entries]
    assert (word,) in matches
