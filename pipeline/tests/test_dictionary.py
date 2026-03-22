"""Unit tests for dictionary extraction (gloss, senses, etc.)."""

import pytest

from pipeline.dictionary import extract_senses, process_dict_entry, DICT_CONFIGS
from pipeline.gloss import extract_gloss
from pipeline.wiktionary import Entry, Sense


DE_CONFIG = next(c for c in DICT_CONFIGS if c.code == "de")


def make_entry(word: str, pos: str, glosses: tuple[str, ...], lang: str = "German", lang_code: str = "de") -> Entry:
    sense = Sense(glosses=glosses)
    return Entry(pos=pos, lang_code=lang_code, lang=lang, word=word, senses=(sense,))


class TestExtractSenses:
    def test_loanword_gloss_in_parens(self):
        """Regression test for issue #204: 'Leberkäse' gloss should not be stripped.

        English Wiktionary formats loanword definitions as: "Word (the actual definition)".
        After stripping parentheses, only "Word" would remain — the fix should
        fall back to using the parenthetical content as the gloss.
        """
        entry = make_entry(
            "Leberkäse",
            "noun",
            ("Leberkäse (a dish similar to meat loaf, popular in southern Germany, Austria and parts of Switzerland)",),
        )
        senses = extract_senses(entry)
        assert len(senses) == 1
        assert senses[0]["gloss"] == "a dish similar to meat loaf, popular in southern Germany, Austria and parts of Switzerland"

    def test_short_qualifier_is_stripped(self):
        """Short parenthetical qualifiers like (dialectal) should still be stripped."""
        entry = make_entry("laufen", "verb", ("(dialectal) to run",))
        senses = extract_senses(entry)
        assert len(senses) == 1
        assert senses[0]["gloss"] == "to run"

    def test_trailing_qualifier_is_stripped(self):
        """Short trailing qualifiers like (informal) should be stripped."""
        entry = make_entry("essen", "verb", ("to eat (informal)",))
        senses = extract_senses(entry)
        assert len(senses) == 1
        assert senses[0]["gloss"] == "to eat"

    def test_normal_gloss_unchanged(self):
        """A normal multi-word gloss with no parentheses should pass through unchanged."""
        entry = make_entry("Hund", "noun", ("a domestic dog",))
        senses = extract_senses(entry)
        assert len(senses) == 1
        assert senses[0]["gloss"] == "a domestic dog"


class TestExtractGloss:
    def test_loanword_gloss_in_parens(self):
        """extract_gloss should also handle the loanword pattern."""
        entry = make_entry(
            "Leberkäse",
            "noun",
            ("Leberkäse (a dish similar to meat loaf, popular in southern Germany, Austria and parts of Switzerland)",),
        )
        result = extract_gloss(entry)
        assert result is not None
        assert "meat loaf" in result
