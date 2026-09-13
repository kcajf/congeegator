"""Tests for SQLite database generation (Lexicoff)."""

import json
import os
import sqlite3
import tempfile
import unicodedata

import pytest
import zstandard

from pipeline.sqlite_output import dictionary_search_key, dictionary_word_key, write_sqlite_database
from pipeline.utils import to_phonetic_el


@pytest.fixture
def sample_entries():
    return [
        {
            "word": "maison",
            "pos": "noun",
            "senses": [{"gloss": "house"}, {"gloss": "home"}],
            "freq": 6.5,
            "gender": "f",
            "forms": ["maisons"],
            "pronunciation": "/mɛ.zɔ̃/",
            "etymology": "From Latin mansionem",
        },
        {
            "word": "parler",
            "pos": "verb",
            "senses": [{"gloss": "to speak"}, {"gloss": "to talk"}],
            "freq": 5.8,
            "forms": ["parle", "parlons", "parlé"],
        },
        {
            "word": "grand",
            "pos": "adj",
            "senses": [{"gloss": "big"}, {"gloss": "tall", "tags": ["informal"]}],
            "freq": 6.2,
            "forms": ["grande", "grands", "grandes"],
        },
    ]


@pytest.fixture
def greek_entries():
    return [
        {
            "word": "σπίτι",
            "pos": "noun",
            "senses": [{"gloss": "house"}, {"gloss": "home"}],
            "freq": 5.0,
            "forms": ["σπίτια"],
        },
        {
            "word": "μιλάω",
            "pos": "verb",
            "senses": [{"gloss": "to speak"}],
            "freq": 4.5,
        },
    ]


# Helper: FTS5 contentless queries return rowids, so join to entries for word names
FTS_WORD_QUERY = """
    SELECT e.word FROM entries e
    JOIN (SELECT rowid FROM entries_fts WHERE {col} MATCH ?) AS fts ON e.id = fts.rowid
"""


def _make_db(entries, lang_code="fr", phonetic_fn=None):
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        path = f.name
    write_sqlite_database(entries, lang_code, phonetic_fn, path)
    return path


class TestSqliteOutput:
    @pytest.mark.parametrize("lang,word,query,key", [
        ("vi", "tiếng Việt", "TIẾNG VIỆT", "tiếng việt"),
        ("uk", "Їсти", "ЇСТИ", "їсти"),
        ("ru", "Москва", "МОСКВА", "москва"),
        ("pl", "Łódź", "ŁÓDŹ", "łódź"),
        ("la", "āmō", "ĀMŌ", "āmō"),
        ("tr", "Işık", "IŞIK", "ışık"),
        ("tr", "İstanbul", "İSTANBUL", "istanbul"),
    ])
    def test_unicode_exact_prefix_and_form_lookup(self, lang, word, query, key):
        # Decomposed source text and keyboard input must agree, including the
        # letters й/ї whose diacritics cannot safely be stripped in Cyrillic.
        entries = [{"word": unicodedata.normalize("NFD", word), "pos": "noun",
                    "senses": [{"gloss": "I am a test definition"}]},
                   {"word": "other", "pos": "noun", "senses": [{"gloss": "other"}],
                    "forms": [unicodedata.normalize("NFD", word)]}]
        path = _make_db(entries, lang_code=lang)
        try:
            conn = sqlite3.connect(path)
            normalized = dictionary_word_key(unicodedata.normalize("NFD", query), lang)
            assert normalized == key
            exact = conn.execute("SELECT id FROM entries WHERE word_key = ?", (normalized,)).fetchall()
            assert exact == [(0,)]
            plan = conn.execute("EXPLAIN QUERY PLAN SELECT id FROM entries WHERE word_key = ?",
                                (normalized,)).fetchall()
            assert any("idx_word_key" in row[3] for row in plan)
            tokens = normalized.split()
            tokens[-1] = tokens[-1][:-1]  # A partially typed final token.
            prefix = " ".join(f'"{token}"' for token in tokens) + "*"
            for column, expected in [("word", 0), ("forms_text", 1)]:
                rows = conn.execute(f"SELECT rowid FROM entries_fts WHERE {column} MATCH ?",
                                    (prefix,)).fetchall()
                assert (expected,) in rows
            # English glosses use English casing even in a Turkish dictionary.
            assert conn.execute("SELECT rowid FROM entries_fts WHERE gloss_text MATCH '\"i\"'").fetchall() == [(0,)]
            conn.close()
        finally:
            os.unlink(path)

    def test_turkish_dotted_and_dotless_i_remain_distinct(self):
        entries = [{"word": word, "pos": "noun", "senses": [{"gloss": "example"}]}
                   for word in ["İ", "I"]]
        path = _make_db(entries, lang_code="tr")
        try:
            conn = sqlite3.connect(path)
            assert conn.execute("SELECT rowid FROM entries_fts WHERE word MATCH '\"i\"'").fetchall() == [(0,)]
            assert conn.execute("SELECT rowid FROM entries_fts WHERE word MATCH '\"ı\"'").fetchall() == [(1,)]
            conn.close()
        finally:
            os.unlink(path)

    def test_schema_tables(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "entries" in tables
            assert "entries_fts" in tables
            assert "metadata" in tables
            conn.close()
        finally:
            os.unlink(path)

    def test_row_count(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            assert count == 3
            conn.close()
        finally:
            os.unlink(path)

    def test_entry_data(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            row = conn.execute(
                "SELECT word, pos, senses, freq, gender, forms, pronunciation, etymology "
                "FROM entries WHERE word = 'maison'"
            ).fetchone()
            assert row is not None
            word, pos, senses_json, freq, gender, forms_json, pronunciation, etymology = row
            assert word == "maison"
            assert pos == "noun"
            assert freq == 6.5
            assert gender == "f"
            assert pronunciation == "/mɛ.zɔ̃/"
            assert etymology == "From Latin mansionem"

            senses = json.loads(senses_json)
            assert len(senses) == 2
            assert senses[0]["gloss"] == "house"

            forms = json.loads(forms_json)
            assert forms == ["maisons"]
            conn.close()
        finally:
            os.unlink(path)

    def test_null_optional_fields(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            row = conn.execute(
                "SELECT gender, forms, pronunciation, etymology FROM entries WHERE word = 'parler'"
            ).fetchone()
            gender, forms_json, pronunciation, etymology = row
            assert gender is None
            assert pronunciation is None
            assert etymology is None
            # parler has forms
            forms = json.loads(forms_json)
            assert "parlé" in forms
            conn.close()
        finally:
            os.unlink(path)

    def test_metadata(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            lang = conn.execute("SELECT value FROM metadata WHERE key = 'lang'").fetchone()[0]
            assert lang == "fr"
            conn.close()
        finally:
            os.unlink(path)

    def test_fts5_prefix_search(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            rows = conn.execute(
                FTS_WORD_QUERY.format(col="word"), ("par*",)
            ).fetchall()
            words = {r[0] for r in rows}
            assert "parler" in words
            conn.close()
        finally:
            os.unlink(path)

    def test_fts5_hyphenated_word(self, sample_entries):
        """Hyphenated words must be searchable via per-token AND queries (detail='column' does not support phrase queries)."""
        entries = sample_entries + [
            {"word": "self-service", "pos": "noun", "senses": [{"gloss": "serve yourself"}], "freq": 3.0},
        ]
        path = _make_db(entries)
        try:
            conn = sqlite3.connect(path)
            # Per-token AND with prefix
            rows = conn.execute(FTS_WORD_QUERY.format(col="word"), ('"self" "serv"*',)).fetchall()
            assert any(r[0] == "self-service" for r in rows)
            conn.close()
        finally:
            os.unlink(path)

    def test_fts5_diacritics(self, sample_entries):
        """FTS5 unicode61 remove_diacritics 2 should match accent-insensitively."""
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            rows = conn.execute(
                FTS_WORD_QUERY.format(col="forms_text"), ("parle",)
            ).fetchall()
            words = {r[0] for r in rows}
            assert "parler" in words
            conn.close()
        finally:
            os.unlink(path)

    def test_fts5_gloss_search(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            rows = conn.execute(
                FTS_WORD_QUERY.format(col="gloss_text"), ("speak",)
            ).fetchall()
            words = {r[0] for r in rows}
            assert "parler" in words
            conn.close()
        finally:
            os.unlink(path)

    def test_fts5_phonetic_greek(self, greek_entries):
        path = _make_db(greek_entries, lang_code="el", phonetic_fn=to_phonetic_el)
        try:
            conn = sqlite3.connect(path)
            rows = conn.execute(
                FTS_WORD_QUERY.format(col="phonetic"), ("spiti",)
            ).fetchall()
            words = {r[0] for r in rows}
            assert "σπίτι" in words
            conn.close()
        finally:
            os.unlink(path)

    def test_phonetic_empty_for_non_greek(self, sample_entries):
        """Non-Greek languages should have empty phonetic — FTS search returns nothing."""
        path = _make_db(sample_entries, lang_code="fr", phonetic_fn=None)
        try:
            conn = sqlite3.connect(path)
            # With no phonetic data, no matches for any phonetic search
            rows = conn.execute(
                FTS_WORD_QUERY.format(col="phonetic"), ("maison",)
            ).fetchall()
            assert len(rows) == 0
            conn.close()
        finally:
            os.unlink(path)

    def test_word_index_case_insensitive(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            rows = conn.execute(
                "SELECT word FROM entries WHERE word = 'Maison' COLLATE NOCASE"
            ).fetchall()
            assert len(rows) == 1
            assert rows[0][0] == "maison"
            conn.close()
        finally:
            os.unlink(path)

    def test_forms_text_content(self, sample_entries):
        """FTS forms_text should contain inflected forms."""
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            rows = conn.execute(
                FTS_WORD_QUERY.format(col="forms_text"), ("grande",)
            ).fetchall()
            words = {r[0] for r in rows}
            assert "grand" in words
            conn.close()
        finally:
            os.unlink(path)

    def test_fts_detail_column(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'entries_fts'"
            ).fetchone()[0]
            assert "detail='column'" in sql
            conn.close()
        finally:
            os.unlink(path)

    def test_fts_optimize_integrity(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            rows = conn.execute(FTS_WORD_QUERY.format(col="word"), ("par*",)).fetchall()
            assert "parler" in {r[0] for r in rows}
            conn.close()
        finally:
            os.unlink(path)

    def test_fuzzy_trigram_table_exists(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            assert "fuzzy" in tables
            conn.close()
        finally:
            os.unlink(path)

    def test_fuzzy_trigram_search(self, sample_entries):
        """Trigram table should match substring/fuzzy queries."""
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            rows = conn.execute(
                "SELECT e.word FROM entries e "
                "JOIN (SELECT rowid FROM fuzzy WHERE fuzzy MATCH ?) AS t ON e.id = t.rowid",
                ("mais",)
            ).fetchall()
            words = {r[0] for r in rows}
            assert "maison" in words
            conn.close()
        finally:
            os.unlink(path)

    def test_fuzzy_trigram_phonetic(self, greek_entries):
        """Trigram table phonetic column should match romanized Greek."""
        path = _make_db(greek_entries, lang_code="el", phonetic_fn=to_phonetic_el)
        try:
            conn = sqlite3.connect(path)
            rows = conn.execute(
                "SELECT e.word FROM entries e "
                "JOIN (SELECT rowid FROM fuzzy WHERE fuzzy MATCH ?) AS t ON e.id = t.rowid",
                ("spit",)
            ).fetchall()
            words = {r[0] for r in rows}
            assert "σπίτι" in words
            conn.close()
        finally:
            os.unlink(path)

    def test_zstd_roundtrip(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            with open(path, "rb") as f:
                original = f.read()
            compressed = zstandard.ZstdCompressor(level=9).compress(original)
            assert len(compressed) < len(original)
            assert zstandard.ZstdDecompressor().decompress(compressed) == original
        finally:
            os.unlink(path)


class TestExtendedDictionaries:
    @pytest.mark.parametrize("lang,word,query,form,form_query", [
        ("grc", "ὕδωρ", "υδω", "ῠ̔́δᾰτος", "υδατο"),
        ("hi", "पानी", "पान", "पानियों", "पानिय"),
        ("sa", "गृह", "गृ", "गृ॒हेण॑", "गृ॒हे"),
        ("he", "שלום", "שָׁלוֹ", "שְׁלוֹמִי", "שלומי"),
        ("fa", "کتاب", "كتاب", "کتاب‌ها", "کتابها"),
        ("az", "işıq", "İŞ", "işıqlar", "İŞIQL"),
        ("ko", "먹다", "먹", "먹습니다", "먹습"),
        ("ka", "წყალი", "წყა", "წყლები", "წყლე"),
    ])
    def test_real_fts_preserves_scripts_and_matches_prefixes(self, tmp_path, lang, word, query, form, form_query):
        path = str(tmp_path / f"{lang}.sqlite")
        write_sqlite_database([{"word": word, "pos": "noun", "senses": [{"gloss": "water"}],
                                "forms": [form]}], lang, None, path)
        with sqlite3.connect(path) as conn:
            # These are precisely the quoted prefix queries sent by the browser.
            # Default unicode61 split Indic/Hebrew marks and raised phrase errors.
            for column, text in [("word", query), ("forms_text", form_query)]:
                key = dictionary_search_key(unicodedata.normalize("NFD", text), lang)
                assert conn.execute(f"SELECT rowid FROM entries_fts WHERE {column} MATCH ?",
                                    (f'"{key}"*',)).fetchall() == [(0,)]
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    def test_indic_vowels_and_virama_are_not_erased(self, tmp_path):
        path = str(tmp_path / "hi.sqlite")
        words = ["पान", "पानी", "पता", "पिता", "कर्म", "क्रम"]
        write_sqlite_database([{"word": word, "pos": "noun", "senses": [{"gloss": "example"}]}
                               for word in words], "hi", None, path)
        with sqlite3.connect(path) as conn:
            for i, word in enumerate(words):
                assert conn.execute("SELECT rowid FROM entries_fts WHERE word MATCH ?",
                                    (f'"{word}"',)).fetchall() == [(i,)]

    def test_aliases_never_merge_greek_homographs(self, tmp_path):
        path = str(tmp_path / "grc.sqlite")
        words = ["ἄλλα", "ἀλλά"]
        write_sqlite_database([{"word": word, "pos": "adv", "senses": [{"gloss": gloss}]}
                               for word, gloss in zip(words, ["other things", "but"])], "grc", None, path)
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT word FROM entries WHERE search_key = 'αλλα' ORDER BY id").fetchall() == [(w,) for w in words]
            for word in words:
                assert conn.execute("SELECT word FROM entries WHERE word_key = ?", (word,)).fetchall() == [(word,)]
            plan = conn.execute("EXPLAIN QUERY PLAN SELECT id FROM entries WHERE search_key = ?", ("αλλα",)).fetchall()
            assert any("idx_search_key" in row[3] for row in plan)
            assert conn.execute("SELECT rowid FROM entries_fts WHERE phonetic MATCH 'id*'").fetchall() == []

    def test_persian_variants_and_spaced_forms_without_collapsing_madda(self, tmp_path):
        path = str(tmp_path / "fa.sqlite")
        words = ["خانه‌ها", "آب", "اب"]
        write_sqlite_database([{"word": word, "pos": "noun", "senses": [{"gloss": "example"}]}
                               for word in words], "fa", None, path)
        with sqlite3.connect(path) as conn:
            for query in ['"خانهها"*', '"خانه" "ها"*']:
                assert conn.execute("SELECT rowid FROM entries_fts WHERE word MATCH ?", (query,)).fetchall() == [(0,)]
            assert dictionary_search_key("آب", "fa") != dictionary_search_key("اب", "fa")
            assert dictionary_search_key("كِتاب", "fa") == "کتاب"

    def test_optional_labels_round_trip_and_are_not_indexed_as_forms(self, tmp_path):
        path = str(tmp_path / "grc.sqlite")
        entry = {"word": "ὕδωρ", "pos": "noun", "senses": [{"gloss": "water"}],
                 "forms": ["ὕδατος"], "formDetails": [{"form": "ὕδατος", "tags": ["Attic"]}],
                 "pronunciations": [{"ipa": "/hý.dɔːr/", "label": "5th BCE Attic"}]}
        write_sqlite_database([entry], "grc", None, path)
        with sqlite3.connect(path) as conn:
            details, pronunciations = conn.execute("SELECT form_details, pronunciations FROM entries").fetchone()
            assert json.loads(details) == entry["formDetails"]
            assert json.loads(pronunciations) == entry["pronunciations"]
            assert conn.execute("SELECT rowid FROM entries_fts WHERE forms_text MATCH 'Attic'").fetchall() == []

    def test_existing_dictionary_schema_remains_unchanged(self, tmp_path, sample_entries):
        path = str(tmp_path / "fr.sqlite")
        write_sqlite_database(sample_entries, "fr", None, path)
        with sqlite3.connect(path) as conn:
            assert [r[1] for r in conn.execute("PRAGMA table_info(entries)")] == [
                "id", "word", "word_key", "pos", "senses", "freq", "gender", "forms", "pronunciation", "etymology"]
            schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='entries_fts'").fetchone()[0]
            assert "categories" not in schema
