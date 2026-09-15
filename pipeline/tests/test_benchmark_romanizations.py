import sqlite3

from pipeline.benchmark_romanizations import readings, variant
from pipeline.entry_json import decode_entry_json
from pipeline.sqlite_output import write_sqlite_database


def test_headwords_include_standalone_inflected_entries():
    record = {'word': 'собаки', 'forms': []}
    raw = {'forms': [{'form': 'sobaki', 'tags': ['romanization']}],
           'senses': [{'form_of': [{'word': 'собака'}]}]}
    assert readings(raw, record) == (['sobaki'], {}, 0)


def test_no_metadata_duplication_or_guessed_form_alignment():
    record = {'word': 'собака', 'forms': ['собаки']}
    raw = {'forms': [
        {'form': 'sobaka', 'tags': ['romanization']},
        {'form': 'собаки', 'roman': 'sobaki', 'tags': ['plural'], 'source': 'declension'},
        {'form': 'собаки', 'roman': 'sobaki', 'tags': ['genitive'], 'source': 'declension'},
        {'form': 'a / b', 'roman': 'x / y'},
        {'form': 'unaccepted', 'roman': 'unaccepted'},
    ]}
    assert readings(raw, record) == (['sobaka'], {'собаки': ['sobaki']}, 2)


def test_optional_fields_and_corrupt_readings():
    assert readings({'forms': []}, {'word': 'a'}) == ([], {}, 0)
    assert readings({'forms': [{'form': '{{bad}}', 'tags': ['romanization']}]},
                    {'word': 'a'}) == ([], {}, 0)


def test_variants_retain_display_strings_and_separate_search_keys(tmp_path):
    rows = [{'word': 'собака', 'pos': 'noun', 'senses': [{'gloss': 'dog'}],
             'forms': ['собаки'], 'formDetails': [{'form': 'собаки', 'kind': 'inflection'}]}]
    extracted = [(['sobáka'], {'собаки': ['sobáki']}, 0)]
    baseline = tmp_path / 'base.sqlite'
    write_sqlite_database(rows, 'ru', None, str(baseline))
    for mode in ('headwords', 'all_forms'):
        target = tmp_path / f'{mode}.sqlite'
        result = variant(baseline, target, rows, extracted, mode, True)
        assert result['index_rows'] == (1 if mode == 'headwords' else 2)
        with sqlite3.connect(target) as db:
            heads, details = db.execute('SELECT romanizations, form_details FROM entries').fetchone()
            assert decode_entry_json(heads) == ['sobáka']
            form = decode_entry_json(details)[0]
            assert form.get('romanizations') == (['sobáki'] if mode == 'all_forms' else None)
            assert db.execute('SELECT key FROM romanized_lookup WHERE kind=0').fetchone()[0] == 'sobáka'
