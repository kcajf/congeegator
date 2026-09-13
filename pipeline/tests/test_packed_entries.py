import sqlite3

import msgspec
import pytest

from pipeline.packed_entries import PackedDictionaryEntries
from pipeline.sqlite_output import write_sqlite_database


def records():
    return [
        {"word": word, "pos": "noun", "senses": [{"gloss": gloss}],
         "forms": [f"{word}{i}" for i in range(size)],
         "formDetails": [{"form": f"{word}{i}", "kind": "inflection",
                          "readings": [{"grammar": ["genitive", "plural"],
                                        "qualifiers": ["rare"]}]} for i in range(size)]}
        for word, gloss, size in [("talo", "house", 120), ("x", "one", 0), ("talo", "building", 2)]
    ]


def packed(source):
    result = PackedDictionaryEntries()
    for entry in source:
        result.append(entry, msgspec.json.encode(entry))
    result.sort_by_frequency(lambda word: 4.5 if word == "talo" else 0.0)
    return result


def test_lossless_stable_ranking_and_repeatable_independent_snapshots():
    source = records()
    result = packed(source)
    expected = [{**source[i], "freq": 4.5 if i != 1 else 0.0} for i in [0, 2, 1]]
    assert len(result) == 3
    assert list(result) == expected
    assert list(result) == expected
    assert result[-1] == expected[-1]
    assert result[:2] == expected[:2]
    assert result[0]["formDetails"][0]["form"] == "talo0"
    changed = result[0]
    changed["formDetails"][0]["readings"][0]["grammar"].append("changed")
    assert result[0] == expected[0]
    source[0]["forms"].append("changed")
    assert result[0]["forms"][-1] == "talo119"


@pytest.mark.parametrize("lang", ["fi", "grc"])
def test_packed_records_produce_identical_database_and_search_indexes(tmp_path, lang):
    source = records()
    compact = packed(source)
    plain = sorted([{**e, "freq": 4.5 if e["word"] == "talo" else 0.0} for e in source],
                   key=lambda e: -e["freq"])
    paths = [tmp_path / "plain.sqlite", tmp_path / "packed.sqlite"]
    for entries, path in zip([plain, compact], paths):
        write_sqlite_database(entries, lang, None, str(path))
    with sqlite3.connect(paths[0]) as a, sqlite3.connect(paths[1]) as b:
        for table in ("entries", "form_lookup", "metadata"):
            assert a.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall() == b.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()
        for table in ("entries_fts", "fuzzy"):
            for conn in (a, b):
                conn.execute(f"CREATE VIRTUAL TABLE {table}_vocab USING fts5vocab({table}, 'instance')")
            assert a.execute(f"SELECT * FROM {table}_vocab ORDER BY 1, 2, 3, 4").fetchall() == b.execute(f"SELECT * FROM {table}_vocab ORDER BY 1, 2, 3, 4").fetchall()


def test_sqlite_iteration_keeps_completed_json_unparsed():
    source = records()
    result = packed(source)
    entry = next(result.iter_for_sqlite())
    assert isinstance(entry['formDetails'], msgspec.Raw)
    assert msgspec.json.decode(entry['formDetails']) == source[0]['formDetails']
    assert isinstance(entry['forms'], list)
    assert isinstance(entry['senses'], list)
