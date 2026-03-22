"""Tests for pipeline/dictionary.py — entry validation and sense extraction."""

import pytest

from pipeline.dictionary import DICT_CONFIGS, entry_is_valid, extract_senses, process_dict_entry
from pipeline.wiktionary import Entry, FormOf, Sense


def _make_entry(word="manchen", pos="det", senses=(), lang="German", lang_code="de", categories=()):
    return Entry(pos=pos, lang_code=lang_code, lang=lang, word=word, senses=senses, categories=categories)


def _form_of_sense(gloss, tags=("form-of",)):
    return Sense(
        form_of=(FormOf(word="manch"),),
        glosses=(gloss,),
        tags=tuple(tags),
    )


def _alt_of_sense(gloss, tags=("alt-of",)):
    return Sense(
        alt_of=(FormOf(word="manch"),),
        glosses=(gloss,),
        tags=tuple(tags),
    )


def _regular_sense(gloss):
    return Sense(glosses=(gloss,))


class TestEntryIsValid:
    def test_form_of_only_entry_is_valid(self):
        """Entries whose every sense is form-of should be allowed (fixes missing inflections)."""
        entry = _make_entry(senses=(
            _form_of_sense("genitive masculine/neuter singular of manch"),
            _form_of_sense("accusative masculine singular of manch"),
        ))
        assert entry_is_valid(entry) is True

    def test_alt_of_only_entry_is_excluded(self):
        """Entries whose every sense is alt-of should still be excluded."""
        entry = _make_entry(senses=(
            _alt_of_sense("alternative form of manch"),
        ))
        assert entry_is_valid(entry) is False

    def test_regular_entry_is_valid(self):
        entry = _make_entry(senses=(_regular_sense("some determiner"),))
        assert entry_is_valid(entry) is True

    def test_excluded_pos(self):
        entry = _make_entry(pos="hard-redirect", senses=(_regular_sense("x"),))
        assert entry_is_valid(entry) is False

    def test_unknown_pos(self):
        entry = _make_entry(pos="unknown-pos", senses=(_regular_sense("x"),))
        assert entry_is_valid(entry) is False


class TestExtractSenses:
    def test_form_of_senses_included(self):
        """form_of senses should now produce gloss entries."""
        entry = _make_entry(senses=(
            _form_of_sense("genitive masculine/neuter singular of manch"),
            _form_of_sense("accusative masculine singular of manch"),
            _form_of_sense("dative plural of manch"),
        ))
        senses = extract_senses(entry)
        assert len(senses) == 3
        glosses = [s["gloss"] for s in senses]
        assert "genitive masculine/neuter singular of manch" in glosses
        assert "accusative masculine singular of manch" in glosses
        assert "dative plural of manch" in glosses

    def test_alt_of_senses_excluded(self):
        """alt_of senses should still be skipped."""
        entry = _make_entry(senses=(
            _alt_of_sense("alternative form of manch"),
        ))
        senses = extract_senses(entry)
        assert senses == []

    def test_regular_senses_still_work(self):
        entry = _make_entry(senses=(_regular_sense("some determiner"),))
        senses = extract_senses(entry)
        assert len(senses) == 1
        assert senses[0]["gloss"] == "some determiner"


class TestProcessDictEntry:
    def test_form_of_entry_is_processed(self):
        """process_dict_entry should return a record for a pure form-of entry."""
        de_config = next(c for c in DICT_CONFIGS if c.code == "de")
        entry = _make_entry(
            word="manchen",
            pos="det",
            senses=(
                _form_of_sense("genitive masculine/neuter singular of manch"),
                _form_of_sense("accusative masculine singular of manch"),
                _form_of_sense("dative plural of manch"),
            ),
        )
        result = process_dict_entry(de_config, entry)
        assert result is not None
        assert result["word"] == "manchen"
        assert result["pos"] == "det"
        assert len(result["senses"]) == 3

    def test_alt_of_only_entry_returns_none(self):
        """process_dict_entry should return None for an alt-of-only entry."""
        de_config = next(c for c in DICT_CONFIGS if c.code == "de")
        entry = _make_entry(
            word="manch",
            pos="det",
            senses=(_alt_of_sense("alternative form of manch"),),
        )
        result = process_dict_entry(de_config, entry)
        assert result is None
