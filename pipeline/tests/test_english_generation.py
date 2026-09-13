"""Production-loop regressions for English headword forms and homographs."""
import json

import msgspec

from pipeline import generate
from pipeline.conjugation_english import EN_CONFIG
from pipeline.output import write_language_data
from pipeline.wiktionary import Entry, Form, HeadTemplate, Sense


def headword(word, third, present_participle, past, past_participle, gloss):
    # Current Wiktextract headword principal parts have no source field and
    # no infinitive or person-by-person table. Preserve that essential shape.
    return Entry(
        'verb', 'en', 'English', word,
        head_templates=(HeadTemplate('en-verb'),),
        senses=(Sense(glosses=(gloss,)),),
        forms=(
            Form(third, {'present', 'singular', 'third-person'}),
            Form(present_participle, {'present', 'participle'}),
            Form(past, {'past'}),
            Form(past_participle, {'past', 'participle'}),
        ),
    )


def test_production_loop_keeps_both_meanings_of_lie(monkeypatch):
    reclining = headword('lie', 'lies', 'lying', 'lay', 'lain', 'To rest horizontally.')
    untruth = headword('lie', 'lies', 'lying', 'lied', 'lied', 'To tell an untruth.')
    walk = headword('walk', 'walks', 'walking', 'walked', 'walked', 'To move on foot.')

    class Cache:
        def get_lang_filtered_raw_data(self, *args):
            # A repeated source entry must not duplicate its alternatives.
            return iter(msgspec.json.encode(entry) for entry in (reclining, walk, untruth, reclining))

    monkeypatch.setattr(generate, 'CacheManager', Cache)
    monkeypatch.setattr(generate, 'zipf_frequency', lambda *args: 3.0)
    data, dictionary = generate.generate_data_for_lang('en', EN_CONFIG, None, False)
    assert dictionary is None
    records = {record['name']: record for record in data['verbs']}
    assert set(records) == {'lie', 'walk'}
    rows = dict(zip((tense.name for tense in EN_CONFIG.tenses), records['lie']['conjugation']))
    assert rows['en_indic_past'][0] == 'lay (reclining)/lied (telling untruths)'
    assert rows['en_impers_past_partic'] == 'lain (reclining)/lied (telling untruths)'
    assert rows['en_indic_pres'][2] == 'lies'
    lie_id = data['verbs'].index(records['lie'])
    assert lie_id in data['searchIndex']['lied']
    assert lie_id in data['searchIndex']['lain']


def test_initialism_does_not_inherit_function_word_frequency(monkeypatch):
    organizer = headword('TO', 'TOs', 'TOing', 'TOed', 'TOed', 'To act as a tournament organizer.')
    walk = headword('walk', 'walks', 'walking', 'walked', 'walked', 'To move on foot.')

    class Cache:
        def get_lang_filtered_raw_data(self, *args):
            return iter(msgspec.json.encode(entry) for entry in (organizer, walk))

    monkeypatch.setattr(generate, 'CacheManager', Cache)
    monkeypatch.setattr(generate, 'zipf_frequency', lambda *args: 7.43)
    data, _ = generate.generate_data_for_lang('en', EN_CONFIG, None, False)
    frequencies = {record['name']: record['freq'] for record in data['verbs']}
    assert frequencies == {'TO': 0.0, 'walk': 7.43}


def test_case_distinct_english_lemmas_survive_ssr_chunks(tmp_path):
    records = [
        {'name': 'AIM', 'conjugation': ['AIMed']},
        {'name': 'aim', 'conjugation': ['aimed']},
        {'name': 'AirDrop', 'conjugation': ['AirDropped']},
        {'name': 'airdrop', 'conjugation': ['airdropped']},
    ]
    write_language_data({'verbs': records, 'searchIndex': {}}, str(tmp_path), case_sensitive_names=True)
    chunk = json.loads((tmp_path / 'chunks/a.json').read_text())
    assert chunk == {record['name']: record for record in records}
    assert json.loads((tmp_path / 'index.json').read_text()) == [record['name'] for record in records]
