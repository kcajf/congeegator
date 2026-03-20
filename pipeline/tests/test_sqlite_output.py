"""Tests for SQLite database generation (Lexicoff)."""

import json
import os
import sqlite3
import tempfile

import pytest
import zstandard

from pipeline.sqlite_output import write_sqlite_database
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
        """Hyphenated words must be searchable — both per-token and phrase queries work with detail='full'."""
        entries = sample_entries + [
            {"word": "self-service", "pos": "noun", "senses": [{"gloss": "serve yourself"}], "freq": 3.0},
        ]
        path = _make_db(entries)
        try:
            conn = sqlite3.connect(path)
            # Per-token AND with prefix
            rows = conn.execute(FTS_WORD_QUERY.format(col="word"), ('"self" "serv"*',)).fetchall()
            assert any(r[0] == "self-service" for r in rows)
            # Phrase queries now work with detail='full'
            rows = conn.execute(FTS_WORD_QUERY.format(col="word"), ('"self service"*',)).fetchall()
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

    def test_fts_detail_full(self, sample_entries):
        path = _make_db(sample_entries)
        try:
            conn = sqlite3.connect(path)
            sql = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'entries_fts'"
            ).fetchone()[0]
            assert "detail='full'" in sql
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
