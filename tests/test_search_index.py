"""Tests for build_search_index: verifies key verbs appear under expected prefixes,
including diacritic-stripped and phonetic variants."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data_processing import (
    EL_CONFIG,
    ES_CONFIG,
    FR_CONFIG,
    build_search_index,
    to_phonetic_el,
)
from test_data_processing import CONFIGS, FIXTURE_VERBS, load_fixture_entries, process_entry


def _build_index_for_lang(lang: str) -> tuple[dict[str, list[int]], list[str]]:
    """Process fixture verbs and build a search index. Returns (index, verb_names)."""
    config = CONFIGS[lang]
    entries = load_fixture_entries(lang)
    verbs = []
    for verb_name in FIXTURE_VERBS[lang]:
        result = process_entry(config, entries[verb_name])
        assert result is not None
        verbs.append(result)
    # Sort by nameNoDiacritics to match production ordering
    verbs.sort(key=lambda x: x["nameNoDiacritics"])
    index = build_search_index(verbs, phonetic_fn=config.phonetic_fn)
    verb_names = [v["name"] for v in verbs]
    return index, verb_names


def _idx(verb_names: list[str], name: str) -> int:
    return verb_names.index(name)


# -- French ------------------------------------------------------------------


class TestFrenchSearchIndex:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.index, self.names = _build_index_for_lang("fr")

    def test_etre_found_by_diacritic_stripped_prefix(self):
        """'être' should be findable via 'etr' (diacritic-stripped)."""
        idx = _idx(self.names, "être")
        assert idx in self.index["etr"]
        assert idx in self.index["etre"]

    def test_etre_found_by_exact_prefix(self):
        """'être' should be findable via its exact accented prefix."""
        idx = _idx(self.names, "être")
        assert idx in self.index["êtr"]
        assert idx in self.index["être"]

    def test_manger_conjugation_prefix(self):
        """'manger' conjugation 'mange' should be indexed."""
        idx = _idx(self.names, "manger")
        assert idx in self.index["mang"]
        assert idx in self.index["man"]

    def test_avoir_single_letter(self):
        """Single-letter prefix 'a' should include 'avoir' and 'aller'."""
        avoir_idx = _idx(self.names, "avoir")
        aller_idx = _idx(self.names, "aller")
        assert avoir_idx in self.index["a"]
        assert aller_idx in self.index["a"]

    def test_finir_prefixes(self):
        idx = _idx(self.names, "finir")
        assert idx in self.index["f"]
        assert idx in self.index["fi"]
        assert idx in self.index["fin"]
        assert idx in self.index["fini"]


# -- Greek -------------------------------------------------------------------


class TestGreekSearchIndex:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.index, self.names = _build_index_for_lang("el")

    def test_echo_phonetic_prefix(self):
        """'έχω' should be findable via phonetic 'echo'."""
        idx = _idx(self.names, "έχω")
        # Phonetic: έχω → echo
        assert idx in self.index["echo"]
        assert idx in self.index["ech"]

    def test_echo_greek_prefix(self):
        """'έχω' should be findable via Greek script prefixes."""
        idx = _idx(self.names, "έχω")
        assert idx in self.index["έχω"]
        # Diacritic-stripped
        assert idx in self.index["εχω"]

    def test_kano_phonetic_prefix(self):
        """'κάνω' should be findable via phonetic 'kano'."""
        idx = _idx(self.names, "κάνω")
        assert idx in self.index["kano"]
        assert idx in self.index["kan"]

    def test_emai_phonetic_prefix(self):
        """'είμαι' phonetic is 'ime' — should be indexed."""
        idx = _idx(self.names, "είμαι")
        assert idx in self.index["ime"]

    def test_greek_single_letter(self):
        """Single Greek letter prefixes should work."""
        idx = _idx(self.names, "έχω")
        # Diacritic-stripped single letter
        assert idx in self.index["ε"]


# -- Spanish -----------------------------------------------------------------


class TestSpanishSearchIndex:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.index, self.names = _build_index_for_lang("es")

    def test_hablar_prefixes(self):
        idx = _idx(self.names, "hablar")
        assert idx in self.index["h"]
        assert idx in self.index["ha"]
        assert idx in self.index["hab"]
        assert idx in self.index["habl"]

    def test_hacer_conjugation_overlap(self):
        """'hacer' and 'hablar' should both appear under 'ha'."""
        hacer_idx = _idx(self.names, "hacer")
        hablar_idx = _idx(self.names, "hablar")
        assert hacer_idx in self.index["ha"]
        assert hablar_idx in self.index["ha"]

    def test_ir_short_verb(self):
        """Very short verb 'ir' should be indexed at all prefix lengths."""
        idx = _idx(self.names, "ir")
        assert idx in self.index["i"]
        assert idx in self.index["ir"]


# -- Truncation --------------------------------------------------------------


class TestIndexTruncation:
    def test_entries_capped_at_max_prefix_ids(self):
        """No index entry should exceed MAX_PREFIX_IDS (200)."""
        # Use a large enough set — the fixture set is small, but verify the invariant
        for lang in FIXTURE_VERBS:
            index, _ = _build_index_for_lang(lang)
            for prefix, ids in index.items():
                assert len(ids) <= 200, f"{lang} prefix '{prefix}' has {len(ids)} entries"
