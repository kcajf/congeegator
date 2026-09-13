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

# Existing downloads retain their schema and search semantics. New dictionaries
# carry usage labels and a separate lookup alias without changing display words.
EXTENDED_LANGUAGES = frozenset({
    "grc", "az", "eu", "br", "et", "ka", "he", "hi", "is", "ga",
    "ko", "lt", "mk", "ms", "oc", "fa", "sa", "sh", "sk", "cy",
})
EXTENDED_SCHEMA_SQL = SCHEMA_SQL.replace(
    "etymology   TEXT\n", "etymology   TEXT,\n    search_key TEXT NOT NULL,\n    form_details TEXT,\n    pronunciations TEXT\n"
).replace(
    "CREATE INDEX idx_freq", "CREATE INDEX idx_search_key ON entries(search_key);\nCREATE INDEX idx_freq"
).replace(
    "tokenize='unicode61 remove_diacritics 2'",
    "tokenize=\"unicode61 remove_diacritics 2 categories 'L* N* Co M*'\"",
)


def dictionary_word_key(text: str, lang_code: str) -> str:
    """Match the browser's NFC + language-aware lowercase exact-lookup key.

    SQLite NOCASE handles ASCII only. Turkish additionally needs I→ı and İ→i;
    apply this only to target-language words/forms, never to English glosses.
    """
    text = unicodedata.normalize("NFC", text)
    if lang_code in {"tr", "az"}:
        text = text.replace("I", "ı").replace("İ", "i")
    return unicodedata.normalize("NFC", text.lower())


def dictionary_search_key(text: str, lang_code: str) -> str:
    """Language-specific query aliases; never use these to merge records.

    Keep in sync with dictionarySearchKey in searchNormalization.ts. Indic vowel
    signs and virama are letters' meaningful components and must be preserved.
    Persian normalizes Arabic keyboard variants, optional short-vowel marks and
    ZWNJ; hamza and madda remain significant. Original spellings are also indexed.
    """
    text = dictionary_word_key(text, lang_code)
    if lang_code in {"grc", "he"}:
        text = "".join(c for c in unicodedata.normalize("NFD", text)
                       if unicodedata.category(c) != "Mn")
    if lang_code == "grc":
        text = text.replace("ς", "σ")
    if lang_code == "fa":
        text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", "")
        text = "".join(c for c in text if not ("\u064b" <= c <= "\u0652" or c == "\u0670"))
    return unicodedata.normalize("NFC", text)


def _search_text(text: str, lang_code: str) -> str:
    key = dictionary_word_key(text, lang_code)
    alias = dictionary_search_key(text, lang_code)
    return key if alias == key else f"{key} {alias}"


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
        extended = lang_code in EXTENDED_LANGUAGES
        conn.executescript(EXTENDED_SCHEMA_SQL if extended else SCHEMA_SQL)

        # Insert entries in batches
        entry_rows = []
        fts_rows = []
        fuzzy_rows = []

        for i, entry in enumerate(entries):
            senses_json = orjson.dumps(entry["senses"]).decode()
            forms = entry.get("forms")
            forms_json = orjson.dumps(forms).decode() if forms else None

            row = (
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
            )
            if extended:
                row += (
                    dictionary_search_key(entry["word"], lang_code),
                    orjson.dumps(entry["formDetails"]).decode() if entry.get("formDetails") else None,
                    orjson.dumps(entry["pronunciations"]).decode() if entry.get("pronunciations") else None,
                )
            entry_rows.append(row)

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

            word_key = (_search_text(entry["word"], lang_code) if extended
                        else dictionary_word_key(entry["word"], lang_code))
            forms_key = (_search_text(forms_text, lang_code) if extended
                         else dictionary_word_key(forms_text, lang_code))
            fts_rows.append((
                i, word_key, forms_key,
                dictionary_word_key(gloss_text, "en"), phonetic,
            ))
            fuzzy_rows.append((i, word_key, phonetic))

            if len(entry_rows) >= BATCH_SIZE:
                _flush_batch(conn, entry_rows, fts_rows, fuzzy_rows, extended)
                entry_rows = []
                fts_rows = []
                fuzzy_rows = []

        # Flush remaining
        if entry_rows:
            _flush_batch(conn, entry_rows, fts_rows, fuzzy_rows, extended)

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
    extended: bool = False,
) -> None:
    columns = "id, word, word_key, pos, senses, freq, gender, forms, pronunciation, etymology"
    if extended:
        columns += ", search_key, form_details, pronunciations"
    placeholders = ", ".join("?" for _ in range(13 if extended else 10))
    conn.executemany(
        f"INSERT INTO entries ({columns}) VALUES ({placeholders})",
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
