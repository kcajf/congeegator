"""Regressions for source notation leaks found in the full artifact audit."""
from pathlib import Path

import msgspec
import pytest

from pipeline.conjugation import EL_CONFIG, FR_CONFIG, extract_conjugation, form_is_clean_conjugation
from pipeline.search import build_search_index
from pipeline.wiktionary import Entry, Form

ENTRIES = {
    entry.word: entry
    for line in (Path(__file__).parent / 'fixtures/conjugation_source_hygiene.jsonl').read_bytes().splitlines()
    if (entry := msgspec.json.decode(line, type=Entry))
}


def test_french_ascii_ipa_is_not_a_conjugated_form():
    result = extract_conjugation(FR_CONFIG, ENTRIES['asseoir'])
    rows = dict(zip((t.name for t in FR_CONFIG.tenses), result['conjugation']))
    assert rows['fr_indic_pres'][4] == 'assoyez/asseyez'
    assert rows['fr_imper_pres'][2] == 'assoyez/asseyez'
    index = build_search_index([result], lang='fr')
    assert '' not in index
    assert 'a.swa.' not in index
    assert index['asseye'] == [0]


@pytest.mark.parametrize('phonetic', ['/a.swa.je/', '/a.se.je/', '/ɛtʁ/'])
def test_delimited_ipa_is_excluded_even_without_special_ipa_letters(phonetic):
    assert not form_is_clean_conjugation(Form(phonetic, {'present'}, 'conjugation'))
    assert form_is_clean_conjugation(Form('assoyez/asseyez', {'present'}, 'conjugation'))


@pytest.mark.parametrize('word,stem', [('αρνούμαι','αρν'),('απολογούμαι','απολογ'),('ασχολούμαι','ασχολ')])
def test_greek_malformed_source_brackets_preserve_usage_and_suffix_variants(word,stem):
    # Rendered Wiktionary has "[...ούσασταν, [-ούσαστε] - ...ιόσασταν, (-ιόσαστε)".
    # Its legend labels [] rare and () optional/informal. Expand the written
    # suffixes only, retaining these distinctions rather than dropping the cell.
    result = extract_conjugation(EL_CONFIG, ENTRIES[word])
    matches = [cell for row in result['conjugation'] for cell in ([row] if isinstance(row,str) else row)
               if f'{stem}ούσασταν' in cell]
    assert matches == [f'[{stem}ούσασταν]/[{stem}ούσαστε]/{stem}ιόσασταν/({stem}ιόσαστε)']


@pytest.mark.parametrize('lang', ['fr','ca'])
def test_search_never_emits_an_empty_variant_prefix(lang):
    index = build_search_index([{'name':'test', 'conjugation':['foo//bar/', '[]', '()']}], lang=lang)
    assert '' not in index
    assert index['foo'] == index['bar'] == [0]
