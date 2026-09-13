"""Independent semantic checks against pinned raw English headword records.

Expected meaning distinctions were reviewed in rendered Wiktionary and Cambridge
English Grammar Today (not inferred by regenerating snapshots).
"""
from collections import defaultdict
from pathlib import Path
import re

import msgspec
import pytest

from pipeline.conjugation import extract_conjugation
from pipeline.conjugation_english import EN_CONFIG, merge_english_records
from pipeline.wiktionary import Entry


@pytest.fixture(scope='module')
def paradigms():
    records = defaultdict(list)
    path = Path(__file__).parent / 'fixtures' / 'english_head_verbs.jsonl'
    for line in path.read_bytes().splitlines():
        entry = msgspec.json.decode(line, type=Entry)
        record = extract_conjugation(EN_CONFIG, entry)
        if record:
            records[entry.word].append(record)
    return records


def merged(records):
    result = records[0]
    for record in records[1:]:
        result = merge_english_records(result, record)
    return result


def variants(record, tense=4):
    row = record['conjugation'][tense]
    return (row if isinstance(row, str) else row[0]).split('/')


@pytest.mark.parametrize('word,form,meaning', [
    ('lead', 'leaded', 'lead'), ('lead', 'led', 'guide'),
    ('wind', 'wound', 'coils'),
    ('ring', 'ringed', 'surround'), ('ring', 'rang', 'resonant sound'),
    ('stick', 'sticked', 'wood'), ('stick', 'stuck', 'attached'),
    ('bear', 'beared', 'finance'), ('bear', 'bore', 'carrying'),
    ('spit', 'spitted', 'impale'), ('spit', 'spat', 'mouth'),
    ('fly', 'flew', 'air'), ('fly', 'flied', 'fly ball'),
    ('tear', 'tore', 'pulling apart'), ('tear', 'teared', 'tears'),
    ('pay', 'payed', 'tar'),
    ('lie', 'lay', 'reclining'), ('lie', 'lied', 'untruths'),
])
def test_differing_forms_keep_their_source_meaning(paradigms, word, form, meaning):
    forms = variants(merged(paradigms[word]))
    assert any(value.startswith(form + ' (') and meaning in value for value in forms), forms


@pytest.mark.parametrize('word', ['lead', 'wind', 'ring', 'stick', 'bear', 'spit', 'spell', 'fly', 'tear', 'pay', 'lie', 'leave'])
def test_repeated_raw_homographs_do_not_duplicate_meaning_variants(paradigms, word):
    result = merged(paradigms[word])
    repeated = result
    for record in paradigms[word]:
        repeated = merge_english_records(repeated, record)
    assert repeated == result


def test_third_spell_homograph_retains_its_own_meaning_and_regional_scope(paradigms):
    forms = variants(merged(paradigms['spell']))
    letters = [form for form in forms if form.startswith('spelt ') and 'letters' in form]
    work = [form for form in forms if form.startswith('spelt ') and 'work in place of' in form]
    assert len(letters) == len(work) == 1
    assert 'UK' in letters[0]
    assert 'UK' not in work[0]


def test_third_leave_homograph_retains_rare_foliage_meaning(paradigms):
    forms = variants(merged(paradigms['leave']))
    assert any(form.startswith('leaved ') and 'give leave' in form for form in forms)
    assert any(form.startswith('leaved ') and 'rare' in form and 'foliage' in form for form in forms)


def test_whole_entry_historical_tags_do_not_become_unmarked_modern_forms(paradigms):
    assert variants(merged(paradigms['let'])) == ['let']
    ken = merged(paradigms['ken'])
    assert 'give birth' not in ken['gloss']
    assert all('Scotland' in form for form in variants(ken))


def test_bear_active_perfect_uses_borne_not_birth_passive_born(paradigms):
    # https://dictionary.cambridge.org/grammar/british-grammar/born-or-borne
    record = merged(paradigms['bear'])
    assert any(form.startswith('have borne ') for form in variants(record, 5))
    assert not any(re.match(r'have born(?: |$)', form) for form in variants(record, 5))


def test_put_dialect_participle_is_identified(paradigms):
    forms = variants(merged(paradigms['put']), 2)
    assert 'put' in forms
    assert all('dialectal' in form for form in forms if form.startswith('putten'))


def test_must_has_no_ordinary_simple_past(paradigms):
    # Cambridge Must: past obligation uses had to, not a past inflection must.
    record = merged(paradigms['must'])
    assert record['conjugation'][4] == ('',) * 6
    assert not any(record['conjugation'][i] for i in (0, 1, 2))


def test_dirty_head_notes_do_not_become_forms(paradigms):
    assert 'partial' not in paradigms
    record = merged(paradigms['parallel'])
    assert variants(record) == ['paralleled']
    assert variants(record, 2) == ['paralleled']


def test_standard_petted_survives_known_pinned_qualifier_error(paradigms):
    # Current rendered Wiktionary and Cambridge pet both attest standard petted;
    # the pinned source incorrectly labels that past-tense variant childish.
    assert 'petted' in variants(merged(paradigms['pet']))


def test_two_initially_identical_homographs_keep_both_meanings_when_third_differs():
    path = Path(__file__).parent / 'fixtures' / 'english_homograph_edge.jsonl'
    records = [extract_conjugation(EN_CONFIG, msgspec.json.decode(line, type=Entry))
               for line in path.read_bytes().splitlines()]
    assert len(records) == 3 and all(records)
    result = merged(records)
    forms = variants(result, 1)
    shared = next(form for form in forms if form.startswith('hockling '))
    assert 'cordage' in shared and 'tendons' in shared
    assert any(form.startswith('hocklin ') and 'Geordie' in form and 'spit' in form for form in forms)
    for record in records:
        assert merge_english_records(result, record) == result


def test_source_compound_only_usage_context_is_preserved():
    path = Path(__file__).parent / 'fixtures' / 'english_head_qualifiers.jsonl'
    for line in path.read_bytes().splitlines():
        entry = msgspec.json.decode(line, type=Entry)
        record = extract_conjugation(EN_CONFIG, entry)
        assert record is not None
        assert any('fretten (usually in compounds)' in form for form in variants(record, 2))
