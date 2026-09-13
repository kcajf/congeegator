"""Reviewed source regressions, plus counterexamples to excessive filtering."""
import json
from pathlib import Path

import msgspec
import pytest

from pipeline.audit_forms import BASELINE, inventory
from pipeline.dictionary import DICT_CONFIGS, process_dict_entry
from pipeline.form_quality import FormDiagnostics, greek_variants, reading_tags, source_forms
from pipeline.wiktionary import Entry, Form, Sense

ENTRIES = [msgspec.json.decode(line, type=Entry) for line in
           (Path(__file__).parent / 'fixtures/forms_quality_audit.jsonl').read_bytes().splitlines()]
CONFIGS = {c.code: c for c in DICT_CONFIGS}


def records(code, word):
    return [process_dict_entry(CONFIGS[code], e) for e in ENTRIES if e.lang_code == code and e.word == word]


def forms(code, word):
    return {f for r in records(code, word) for f in r.get('forms', [])}


def details(code, word, spelling):
    return [d for r in records(code, word) for d in r.get('formDetails', []) if d['form'] == spelling]


@pytest.mark.parametrize('code,word,bad', [
    ('fi', 'beige', 'Rare. Only used with substantive adjectives.'),
    ('it', 'essere', 'infinitive'), ('it', 'essere', 'imperative'),
    ('nl', 'no.', '[please provide]'), ('fr', 'passer', 'present indicative of avoir'),
    ('fr', 'absenter', 'ayant'), ('fr', 'passer', 'ayant'),
    ('sv', 'sparka på någon som ligger', 'kick someone who lies (down)'),
    ('ru', 'азбука Брайля', 'Comma (, )'), ('id', 'tonton', 'or'),
    ('id', 'Afganistan', 'nonstandard or standard Indonesian'),
])
def test_confirmed_nonforms_are_removed(code, word, bad):
    assert records(code, word)
    assert any(f.form == bad for e in ENTRIES if e.lang_code == code and e.word == word for f in e.forms)
    assert bad not in forms(code, word)


def test_hungarian_readings_do_not_transfer_formality():
    assert 'lennék' in forms('hu', 'van')
    assert 'lennék or' not in forms('hu', 'van')
    readings = details('hu', 'van', 'lenne')[0]['readings']
    assert any('second person' in r['grammar'] and 'formal' in r.get('qualifiers', []) for r in readings)
    assert any('third person' in r['grammar'] and 'formal' not in r.get('qualifiers', []) for r in readings)
    assert not any('concomitant' in f for f in forms('hu', 'ad'))
    assert not any('}' in f for f in forms('hu', 'ellenőriz'))


def test_turkish_reviewed_columns_and_uncertain_rows():
    e = next(e for e in ENTRIES if e.lang_code == 'tr' and e.word == 'gitmek')
    assert 'third-person' in next(f for f in e.forms if f.form == 'gitmişim').tags
    fixed = next(f for f in source_forms(e) if f.form == 'gitmişim')
    assert {'first-person', 'singular', 'inferential'} <= fixed.tags
    assert 'third-person' not in fixed.tags
    incomplete = msgspec.structs.replace(e, forms=(next(f for f in e.forms if f.form == 'gitmişim'),))
    retained = next(source_forms(incomplete))
    assert retained.form == 'gitmişim' and retained.tags == {'inferential'}
    # No changes to unrelated templates or a table whose provenance is absent.
    unrelated = msgspec.structs.replace(incomplete, inflection_templates=())
    assert next(source_forms(unrelated)).tags == incomplete.forms[0].tags


def test_roles_and_missing_grammar_survive():
    assert any('preterite' in r['grammar'] for d in details('es', 'absolver', 'absolví') for r in d['readings'])
    me = details('es', 'absolver', 'absolverme')[0]['readings']
    nos = details('es', 'absolver', 'absolvernos')[0]['readings']
    assert any('object: first person singular' in r['grammar'] for r in me)
    assert any('object: first person plural' in r['grammar'] for r in nos)
    for tag in ('strong', 'weak', 'mixed', 'prepositional', 'construct', 'middle-voice',
                'singular-possessive', 'plural-possessive', 'superessive', 'oblique'):
        assert reading_tags((tag,))[0]


def test_bracket_scope_particles_and_optional_letters():
    assert list(greek_variants('θα απαντιέμαι - {απαντώμαι}')) == [
        ('θα απαντιέμαι', []), ('θα απαντώμαι', ['learned', 'archaic'])]
    assert list(greek_variants('[ευχαριστούμουν]')) == [('ευχαριστούμουν', ['rare'])]
    assert list(greek_variants('(‑ούσαστε)]')) == []
    assert list(greek_variants('λύουσι(ν)')) == [('λύουσι(ν)', [])]


def test_auxiliary_note_is_not_part_of_spelling():
    assert 'googlet' in forms('da', 'google')
    assert any('auxiliary:' in q for d in details('da', 'google', 'googlet')
               for r in d['readings'] for q in r.get('qualifiers', []))


@pytest.mark.parametrize('code,spelling,tags', [
    ('fr', '-ables', {'plural'}), ('fr', 'or', {'alternative'}),
    ('en', 'past', {'alternative'}), ('ms', 'abalone²', {'plural'}),
    ('ms', 'کتاب', {'Jawi', 'alternative'}), ('vi', '字', {'alternative'}),
    ('de', 'habe geravt', {'perfect'}), ('el', 'έχοντας απαντήσει', {'perfect'}),
    ('la', 'amīcus', {'canonical'}), ('lt', 'ariù', {'error-unrecognized-form'}),
    ('en', 'to be, or not to be', {'alternative'}),
    ('fr', 'comme ci, comme ça', {'alternative'}),
])
def test_valid_punctuation_scripts_phrases_and_errors_survive(code, spelling, tags):
    e = Entry(word='amicus' if code == 'la' else 'lemma', lang_code=code, lang=code,
              pos='phrase', senses=(Sense(glosses=('test',)),), forms=(Form(form=spelling, tags=tags),))
    assert spelling in process_dict_entry(CONFIGS[code], e)['forms']


def test_reviewed_inventory_baseline():
    assert inventory() == json.loads(BASELINE.read_text())


def test_additional_reviewed_notes_and_instructions():
    assert not any('future tense is a combination' in f for f in forms('cs', 'emigrovat'))
    assert not any('Third-declension noun' in f for f in forms('la', 'quadrupes'))
    assert 'not used' not in forms('ro', 'divide')
    assert 'barnet' in forms('br', 'barn')
    assert {'brautskráði', 'brautskráð'} <= forms('is', 'brautskrá')
    assert 'buaccio' in forms('it', 'bue')
    assert 'ferrùccio' in forms('it', 'ferro')
    assert 'caldétto' in forms('it', 'caldo')
    assert not any('t)' in f or 'ta)' in f for f in forms('ka', 'ჭკვიანი'))


def test_french_multiword_alternatives_keep_commas_even_when_pos_is_adverb():
    e = Entry(word='comme ci comme ça', lang_code='fr', lang='French', pos='adv',
              senses=(Sense(glosses=('so-so',)),),
              forms=(Form(form='comme ci, comme ça', tags={'alternative'}),))
    assert process_dict_entry(CONFIGS['fr'], e)['forms'] == ['comme ci, comme ça']


def test_removed_instruction_never_enters_reverse_search(tmp_path):
    import sqlite3
    from pipeline.sqlite_output import write_sqlite_database
    record = records('fi', 'beige')[0]
    record['freq'] = 0
    database = tmp_path / 'fi.sqlite'
    write_sqlite_database([record], 'fi', None, str(database))
    with sqlite3.connect(database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM form_lookup WHERE form_key LIKE '%substantive%'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH 'substantive'").fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM form_lookup').fetchone()[0] > 0


def test_less_specific_duplicates_only_collapse_with_identical_qualifiers():
    e = Entry(word='lemma', lang_code='en', lang='English', pos='verb',
              senses=(Sense(glosses=('test',)),), forms=(
                  Form(form='x', tags={'past'}),
                  Form(form='x', tags={'past', 'indicative'}),
                  Form(form='x', tags={'past', 'indicative'}),
                  Form(form='x', tags={'past', 'rare'})))
    r = process_dict_entry(CONFIGS['en'], e)
    assert r['formDetails'][0]['readings'] == [
        {'grammar': ['past', 'indicative']}, {'grammar': ['past'], 'qualifiers': ['rare']}]


def test_finnish_person_and_number_belong_to_the_possessor():
    grammar = reading_tags(('first-person', 'singular-possessive', 'plural', 'genitive'))[0]
    assert grammar == ('genitive', 'plural', 'possessor: first person singular')


def test_cached_form_readings_do_not_share_mutable_output():
    e = Entry(word='lemma', lang_code='en', lang='English', pos='noun',
              senses=(Sense(glosses=('test',)),), forms=(
                  Form(form='x', tags={'plural', 'rare'}),
                  Form(form='y', tags={'plural', 'rare'})))
    first = process_dict_entry(CONFIGS['en'], e)
    first['formDetails'][0]['readings'][0]['grammar'].append('changed')
    first['formDetails'][0]['readings'][0]['qualifiers'].append('changed')
    expected = [{'grammar': ['plural'], 'qualifiers': ['rare']}]
    assert first['formDetails'][1]['readings'] == expected
    assert process_dict_entry(CONFIGS['en'], e)['formDetails'][0]['readings'] == expected


def test_raw_form_details_match_object_output_for_all_reviewed_fixtures():
    import msgspec
    from pathlib import Path

    for path in Path(__file__).with_name('fixtures').glob('*.jsonl'):
        for line in path.read_bytes().splitlines():
            entry = msgspec.json.decode(line, type=Entry)
            config = CONFIGS.get(entry.lang_code)
            if config is None:
                continue
            plain = process_dict_entry(config, entry)
            raw = process_dict_entry(config, entry, raw_form_details=True)
            assert msgspec.json.encode(raw) == msgspec.json.encode(plain), (path.name, entry.word)


def test_raw_details_escape_spellings_and_qualifiers():
    import msgspec
    from pipeline.form_quality import build_details

    e = Entry(word='lemma', lang_code='en', lang='English', pos='noun',
              senses=(Sense(glosses=('test',)),))
    items = [('a"b\\c\nä', Form(form='unused', tags={'plural'}), ['quote"\\\n'])]
    plain = build_details(items, e, lambda x: x)
    raw = build_details(items, e, lambda x: x, raw=True)
    assert msgspec.json.decode(raw) == plain
