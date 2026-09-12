"""SQLite database generation for Lexicoff dictionary data.

Produces a single .sqlite file per language with FTS5 full-text search.
"""

import logging
import os
import sqlite3
import unicodedata
from typing import Any, Callable

import orjson

log = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE entries (
    id          INTEGER PRIMARY KEY,
    word        TEXT NOT NULL,
    word_key    TEXT NOT NULL,
    pos         TEXT NOT NULL,
    senses      TEXT NOT NULL,
    freq        REAL NOT NULL,
    gender      TEXT,
    forms       TEXT,
    pronunciation TEXT,
    etymology   TEXT
);

CREATE INDEX idx_word ON entries(word COLLATE NOCASE);
CREATE INDEX idx_word_key ON entries(word_key);
CREATE INDEX idx_freq ON entries(freq DESC);

CREATE VIRTUAL TABLE entries_fts USING fts5(
    word,
    forms_text,
    gloss_text,
    phonetic,
    content='',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2',
    detail='column'
);

CREATE VIRTUAL TABLE fuzzy USING fts5(
    word,
    phonetic,
    content='',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TABLE metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

BATCH_SIZE = 5000


def dictionary_word_key(text: str, lang_code: str) -> str:
    """Match the browser's NFC + language-aware lowercase exact-lookup key.

    SQLite NOCASE handles ASCII only. Turkish additionally needs I→ı and İ→i;
    apply this only to target-language words/forms, never to English glosses.
    """
    text = unicodedata.normalize("NFC", text)
    if lang_code == "tr":
        text = text.replace("I", "ı").replace("İ", "i")
    return unicodedata.normalize("NFC", text.lower())


def write_sqlite_database(
    entries: list[dict[str, Any]],
    lang_code: str,
    phonetic_fn: Callable[[str], str] | None,
    output_path: str,
) -> None:
    """Build a complete, indexed, FTS5-populated SQLite database for one language."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Remove existing file if present
    if os.path.exists(output_path):
        os.remove(output_path)

    conn = sqlite3.connect(output_path)
    try:
        conn.executescript(SCHEMA_SQL)

        # Insert entries in batches
        entry_rows = []
        fts_rows = []
        fuzzy_rows = []

        for i, entry in enumerate(entries):
            senses_json = orjson.dumps(entry["senses"]).decode()
            forms = entry.get("forms")
            forms_json = orjson.dumps(forms).decode() if forms else None

            entry_rows.append((
                i,
                entry["word"],
                dictionary_word_key(entry["word"], lang_code),
                entry["pos"],
                senses_json,
                entry.get("freq", 0.0),
                entry.get("gender"),
                forms_json,
                entry.get("pronunciation"),
                entry.get("etymology"),
            ))

            # FTS columns
            forms_text = " ".join(forms) if forms else ""
            gloss_text = " ".join(
                s.get("gloss", "") for s in entry["senses"]
            )
            phonetic = ""
            if phonetic_fn:
                parts = [phonetic_fn(entry["word"])]
                for form in (forms or []):
                    parts.append(phonetic_fn(form))
                phonetic = " ".join(parts)

            word_key = dictionary_word_key(entry["word"], lang_code)
            fts_rows.append((
                i, word_key, dictionary_word_key(forms_text, lang_code),
                dictionary_word_key(gloss_text, "en"), phonetic,
            ))
            fuzzy_rows.append((i, word_key, phonetic))

            if len(entry_rows) >= BATCH_SIZE:
                _flush_batch(conn, entry_rows, fts_rows, fuzzy_rows)
                entry_rows = []
                fts_rows = []
                fuzzy_rows = []

        # Flush remaining
        if entry_rows:
            _flush_batch(conn, entry_rows, fts_rows, fuzzy_rows)

        # Insert metadata
        conn.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", ("lang", lang_code))

        conn.execute("PRAGMA journal_mode=DELETE")
        conn.commit()

        # Merge all FTS5 b-tree segments into one
        conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('optimize')")
        conn.execute("INSERT INTO fuzzy(fuzzy) VALUES('optimize')")
        conn.commit()

        conn.execute("VACUUM")
        conn.execute("PRAGMA optimize")

        log.info(f"Wrote {output_path} ({len(entries)} entries, {os.path.getsize(output_path)} bytes)")
    finally:
        conn.close()


def _flush_batch(
    conn: sqlite3.Connection,
    entry_rows: list[tuple],
    fts_rows: list[tuple],
    fuzzy_rows: list[tuple],
) -> None:
    conn.executemany(
        "INSERT INTO entries (id, word, word_key, pos, senses, freq, gender, forms, pronunciation, etymology) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        entry_rows,
    )
    conn.executemany(
        "INSERT INTO entries_fts (rowid, word, forms_text, gloss_text, phonetic) "
        "VALUES (?, ?, ?, ?, ?)",
        fts_rows,
    )
    conn.executemany(
        "INSERT INTO fuzzy (rowid, word, phonetic) "
        "VALUES (?, ?, ?)",
        fuzzy_rows,
    )
    conn.commit()
