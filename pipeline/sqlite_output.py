"""SQLite database generation for Lexicoff dictionary data.

Produces a single .sqlite file per language with FTS5 full-text search.
"""

import logging
import os
import sqlite3
import tempfile
import unicodedata
from typing import Any, Callable

import orjson
import zstandard

from .utils import log_timing
from .entry_json import ROW_COMPRESSION_LEVEL, encode_entry_json

log = logging.getLogger(__name__)

SCHEMA_SQL = """
-- forms and form_details accept legacy JSON TEXT or versioned LZJ1 BLOBs.
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
    etymology   TEXT,
    details     TEXT,
    form_details TEXT
);

-- Exact reverse lookup avoids scanning JSON paradigms or broad FTS matches.
CREATE TABLE form_lookup (
    form_key TEXT NOT NULL,
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    PRIMARY KEY (form_key, entry_id)
) WITHOUT ROWID;

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
FORM_BATCH_SIZE = 1000
_FORM_INSERT_PREFIX = "INSERT INTO form_stage (form_key, entry_id) VALUES "
_FORM_INSERT_BATCH = _FORM_INSERT_PREFIX + ",".join(["(?,?)"] * FORM_BATCH_SIZE)
INDEX_STATEMENTS = (
    "CREATE INDEX idx_word ON entries(word COLLATE NOCASE)",
    "CREATE INDEX idx_word_key ON entries(word_key)",
    "CREATE INDEX idx_freq ON entries(freq DESC)",
)

# Form metadata is available in every new download. Only these dictionaries
# use the additional search alias and tokenizer; keep existing search semantics.
EXTENDED_LANGUAGES = frozenset({
    "grc", "az", "eu", "br", "et", "ka", "he", "hi", "is", "ga",
    "ko", "lt", "mk", "ms", "oc", "fa", "sa", "sh", "sk", "cy",
})
EXTENDED_SCHEMA_SQL = SCHEMA_SQL.replace(
    "form_details TEXT\n", "form_details TEXT,\n    search_key TEXT NOT NULL,\n    pronunciations TEXT\n"
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

    # SQLite owns the scratch database and removes it on close. An empty name
    # permits disk spilling, unlike ':memory:', while avoiding permanent-file
    # work for an intermediate database that will never be published directly.
    conn = None
    compact_path = None
    field_compressor = zstandard.ZstdCompressor(level=ROW_COMPRESSION_LEVEL, write_checksum=True)
    try:
        conn = sqlite3.connect("")
        # These settings apply only to this scratch build, not browser storage.
        # Journaling millions of derived rows is unnecessary when any failure
        # discards the whole file. Bound the page cache to approximately 64 MiB.
        conn.execute("PRAGMA page_size=16384")
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA cache_size=-65536")
        conn.execute("PRAGMA temp_store=FILE")
        # Some SQLite builds wipe deleted pages by default. Both databases are
        # disposable; VACUUM INTO publishes only live records in a fresh file.
        conn.execute("PRAGMA secure_delete=OFF")
        conn.execute("PRAGMA temp.secure_delete=OFF")
        conn.execute(f"PRAGMA threads={min(os.process_cpu_count() or 1, 4)}")
        extended = lang_code in EXTENDED_LANGUAGES
        conn.executescript(EXTENDED_SCHEMA_SQL if extended else SCHEMA_SQL)
        # Match FTS leaf blocks to the database pages and merge once after bulk
        # loading. The crisis limit still bounds the number of pending segments.
        for table in ("entries_fts", "fuzzy"):
            conn.execute(f"INSERT INTO {table}({table}, rank) VALUES('pgsz', 16300)")
            conn.execute(f"INSERT INTO {table}({table}, rank) VALUES('automerge', 0)")
            conn.execute(f"INSERT INTO {table}({table}, rank) VALUES('crisismerge', 1024)")
        # Append millions of mappings cheaply, then populate the primary-key
        # b-tree in key order instead of continually touching random pages.
        # SQLite's on-disk temporary table/sorter keeps this memory bounded.
        conn.execute("CREATE TEMP TABLE form_stage (form_key TEXT NOT NULL, entry_id INTEGER NOT NULL)")

        with log_timing(f"{lang_code} sqlite insert rows"):
            # Insert entries in batches
            form_rows = []
            entry_rows = []
            fts_rows = []
            fuzzy_rows = []

            for i, entry in enumerate(entries):
                senses_json = orjson.dumps(entry["senses"]).decode()
                forms = entry.get("forms")
                forms_json = encode_entry_json(forms, field_compressor)

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
                    orjson.dumps(entry["details"]).decode() if entry.get("details") else None,
                    encode_entry_json(entry.get("formDetails"), field_compressor),
                )
                if extended:
                    row += (
                        dictionary_search_key(entry["word"], lang_code),
                        orjson.dumps(entry["pronunciations"]).decode() if entry.get("pronunciations") else None,
                    )
                entry_rows.append(row)

                for form in forms or ():
                    form_rows.extend((dictionary_word_key(form, lang_code), i))
                    if len(form_rows) == 2 * FORM_BATCH_SIZE:
                        _flush_form_rows(conn, form_rows)
                        form_rows.clear()

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
            if form_rows:
                _flush_form_rows(conn, form_rows)

        with log_timing(f"{lang_code} sqlite form lookup"):
            conn.execute(
                "INSERT OR IGNORE INTO form_lookup "
                "SELECT form_key, entry_id FROM form_stage ORDER BY form_key, entry_id"
            )
            conn.execute("DROP TABLE form_stage")

        with log_timing(f"{lang_code} sqlite indexes"):
            for statement in INDEX_STATEMENTS:
                conn.execute(statement)
            if extended:
                conn.execute("CREATE INDEX idx_search_key ON entries(search_key)")

        # Insert metadata
        conn.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", ("lang", lang_code))
        # Compute once for the immutable download, never in the browser search queue.
        word_count = conn.execute("SELECT COUNT(DISTINCT word) FROM entries").fetchone()[0]
        conn.execute("INSERT INTO metadata (key, value) VALUES (?, ?)",
                     ("word_count", str(word_count)))

        conn.commit()

        # Merge all FTS5 b-tree segments into one
        with log_timing(f"{lang_code} sqlite FTS optimize"):
            conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('optimize')")
            conn.execute("INSERT INTO fuzzy(fuzzy) VALUES('optimize')")
            for table in ("entries_fts", "fuzzy"):
                conn.execute(f"INSERT INTO {table}({table}, rank) VALUES('automerge', 4)")
                conn.execute(f"INSERT INTO {table}({table}, rank) VALUES('crisismerge', 16)")
            conn.commit()

        with log_timing(f"{lang_code} sqlite vacuum"):
            # Compact directly into the file we will publish. Plain VACUUM
            # copies a temporary database back over the original, adding a
            # redundant full-file write for these disposable build files.
            fd, compact_path = tempfile.mkstemp(
                prefix=".dictionary-compact-", suffix=".sqlite",
                dir=os.path.dirname(output_path) or ".",
            )
            os.close(fd)
            conn.execute("VACUUM INTO ?", (compact_path,))
            conn.close()
            conn = sqlite3.connect(compact_path)
            conn.execute("PRAGMA cache_size=-65536")
            conn.execute("PRAGMA optimize")
            conn.commit()

        with log_timing(f"{lang_code} sqlite validate"):
            result = conn.execute("PRAGMA quick_check").fetchall()
            if result != [("ok",)]:
                raise RuntimeError(f"Invalid {lang_code} database: {result}")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.close()
        conn = None
        # Pay for durability once, after the complete file passes validation.
        with open(compact_path, "rb") as database:
            os.fsync(database.fileno())
        os.replace(compact_path, output_path)
        log.info(f"Wrote {output_path} ({len(entries)} entries, {os.path.getsize(output_path)} bytes)")
    finally:
        if conn is not None:
            conn.close()
        if compact_path is not None and os.path.exists(compact_path):
            os.remove(compact_path)


def _flush_form_rows(conn: sqlite3.Connection, rows: list) -> None:
    # A multi-row statement avoids resetting SQLite's VM for every individual
    # form. The full batch reuses one prepared statement; only the tail varies.
    sql = (_FORM_INSERT_BATCH if len(rows) == 2 * FORM_BATCH_SIZE else
           _FORM_INSERT_PREFIX + ",".join(["(?,?)"] * (len(rows) // 2)))
    conn.execute(sql, rows)


def _flush_batch(
    conn: sqlite3.Connection,
    entry_rows: list[tuple],
    fts_rows: list[tuple],
    fuzzy_rows: list[tuple],
    extended: bool = False,
) -> None:
    columns = "id, word, word_key, pos, senses, freq, gender, forms, pronunciation, etymology, details, form_details"
    if extended:
        columns += ", search_key, pronunciations"
    placeholders = ", ".join("?" for _ in range(14 if extended else 12))
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
