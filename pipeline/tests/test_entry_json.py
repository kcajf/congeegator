"""Lossless, bounded JSON storage shared with the browser query worker."""
import base64
import json
from pathlib import Path
import random
import sqlite3

import orjson
import pytest
import zstandard

from pipeline.entry_json import encode_entry_json, decode_entry_json, MAGIC, MAX_COMPRESS_BYTES, ROW_COMPRESSION_LEVEL
from pipeline.sqlite_output import write_sqlite_database
from pipeline.audit_dictionary import audit_sqlite


def test_text_null_and_incompressible_fields():
    compressor = zstandard.ZstdCompressor(level=6, write_checksum=True)
    assert encode_entry_json(None, compressor) is None
    assert encode_entry_json([], compressor) is None
    assert encode_entry_json(['talossa'], compressor) == '["talossa"]'
    rng = random.Random(42)
    # Random Unicode has enough UTF-8 redundancy to compress; use a compressor
    # returning a larger frame to exercise the size decision deterministically.
    class LargerFrame:
        def compress(self, raw):
            return b'x' * len(raw)
    value = [str(rng.random()) for _ in range(100)]
    assert encode_entry_json(value, LargerFrame()) == orjson.dumps(value).decode()


def test_cross_language_fixture_roundtrip():
    path = Path(__file__).resolve().parents[2] / 'apps/lexicoff/src/lib/fixtures/entry-json.json'
    fixture = json.loads(path.read_text())
    for case in fixture:
        stored = base64.b64decode(case['encoded'])
        assert decode_entry_json(stored) == case['value']
        raw = orjson.dumps(case['value'])
        assert stored[:4] == MAGIC
        assert int.from_bytes(stored[4:8], 'little') == len(raw)


def test_rejects_corrupt_unknown_and_mismatched_frames():
    blob = encode_entry_json(['ä' * 80] * 50, zstandard.ZstdCompressor(level=6, write_checksum=True))
    assert isinstance(blob, bytes)
    for bad in (b'bad', b'LZJ2' + blob[4:], blob[:4] + (MAX_COMPRESS_BYTES + 1).to_bytes(4, 'little') + blob[8:],
                blob[:4] + (12345).to_bytes(4, 'little') + blob[8:], blob[:-1], blob[:-1] + bytes([blob[-1] ^ 1])):
        with pytest.raises((ValueError, zstandard.ZstdError)):
            decode_entry_json(bad)


def test_compressed_database_keeps_search_and_audit_working(tmp_path):
    forms = [f'talossa-{i}' for i in range(100)]
    details = [{'form': f, 'kind': 'inflection', 'readings': [{'grammar': ['inessive', 'singular']}]} for f in forms]
    entry = dict(word='talo', pos='noun', senses=[{'gloss': 'house'}], forms=forms, formDetails=details, freq=5)
    path = tmp_path / 'fi.sqlite'
    write_sqlite_database([entry], 'fi', None, str(path))
    with sqlite3.connect(path) as conn:
        row = conn.execute('SELECT forms,form_details,typeof(senses) FROM entries').fetchone()
        assert isinstance(row[0], bytes) and isinstance(row[1], bytes)
        assert decode_entry_json(row[0]) == forms
        assert decode_entry_json(row[1]) == details
        assert row[2] == 'text'
        assert conn.execute("SELECT entry_id FROM form_lookup WHERE form_key='talossa-99'").fetchall() == [(0,)]
        assert conn.execute("SELECT rowid FROM entries_fts WHERE forms_text MATCH 'talossa'").fetchall() == [(0,)]
        assert conn.execute("SELECT rowid FROM entries_fts WHERE gloss_text MATCH 'house'").fetchall() == [(0,)]
        assert conn.execute("PRAGMA integrity_check").fetchone() == ('ok',)

    report = audit_sqlite(path, 'fi')
    assert report['records'] == 1
    assert report['integrity_check'] == ['ok']
    assert report['fts_integrity'] == {'entries_fts': 'ok', 'fuzzy': 'ok'}
    assert report['form_lookup_orphans'] == 0


@pytest.mark.parametrize('value', [None, [], {}, ['talossa'], ['ä' * 80] * 50,
    [{'form': 'talossa', 'kind': 'inflection', 'readings': [{'grammar': ['inessive', 'singular']}]}] * 50])
def test_completed_raw_json_uses_identical_storage_without_parsing(value):
    import msgspec
    compressor = zstandard.ZstdCompressor(level=ROW_COMPRESSION_LEVEL, write_checksum=True)
    assert encode_entry_json(msgspec.Raw(msgspec.json.encode(value)), compressor) == encode_entry_json(value, compressor)
