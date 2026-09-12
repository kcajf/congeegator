"""Common function words and legitimate lexical categories must survive extraction."""

import pytest

from pipeline.dictionary import DICT_CONFIGS, process_dict_entry
from pipeline.wiktionary import Entry, Sense


@pytest.mark.parametrize(("code", "word", "pos", "gloss"), [
    ("pt", "o", "article", "the"),
    ("pt", "do", "contraction", "of the"),
    ("hu", "alatt", "postp", "under"),
    ("fi", "lähellä", "ambiposition", "near"),
    ("vi", "cái", "classifier", "classifier for inanimate objects"),
    ("id", "-el-", "infix", "infix forming nouns"),
    ("nl", "-s-", "interfix", "linking element in compounds"),
    ("id", "ke- -an", "circumfix", "forms abstract nouns"),
    ("pt", "em vez de", "prep_phrase", "instead of"),
    ("la", "veni, vidi, vici", "proverb", "I came, I saw, I conquered"),
])
def test_preserve_lexical_categories(code, word, pos, gloss):
    config = next(config for config in DICT_CONFIGS if config.code == code)
    entry = Entry(word=word, lang_code=code, lang=config.english_wiktionary_name,
                  pos=pos, senses=(Sense(glosses=(gloss,)),))
    result = process_dict_entry(config, entry)
    assert result is not None
    assert result["word"] == word
    assert result["pos"] == pos
    assert result["senses"] == [{"gloss": gloss}]


@pytest.mark.parametrize("pos", ["character", "symbol", "punct", "hard-redirect", "soft-redirect", "unknown"])
def test_continue_rejecting_nonlexical_categories(pos):
    config = next(config for config in DICT_CONFIGS if config.code == "pt")
    entry = Entry(word="example", lang_code="pt", lang="Portuguese", pos=pos,
                  senses=(Sense(glosses=("example gloss",)),))
    assert process_dict_entry(config, entry) is None
