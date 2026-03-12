#!/usr/bin/env python3
"""One-time utility to extract raw Wiktionary JSONL entries for key verbs from the cache.

Usage:
    pixi run python tests/extract_fixtures.py

Requires cached filtered data in cache/ (run data_processing.py first to populate).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import msgspec

from data_processing import CacheManager, Entry

FIXTURE_VERBS = {
    "fr": {"être", "avoir", "aller", "manger", "finir"},
    "el": {"έχω", "είμαι", "κάνω", "θέλω", "λέω"},
    "de": {"haben", "sein", "machen", "gehen", "können"},
}

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def extract_fixtures():
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    cache = CacheManager()

    for lang, verbs in FIXTURE_VERBS.items():
        wiki_lang = "en"
        output_path = os.path.join(FIXTURES_DIR, f"{lang}_verbs.jsonl")
        found: set[str] = set()

        with open(output_path, "wb") as out:
            for line in cache.get_lang_filtered_raw_data(wiki_lang, lang):
                entry = msgspec.json.decode(line, type=Entry)
                if entry.pos != "verb":
                    continue
                if entry.word in verbs and entry.word not in found:
                    out.write(line if isinstance(line, bytes) else line.encode())
                    out.write(b"\n")
                    found.add(entry.word)

                if found == verbs:
                    break

        missing = verbs - found
        if missing:
            print(f"WARNING: {lang} - could not find: {missing}")
        else:
            print(f"{lang}: extracted {len(found)} verbs to {output_path}")


if __name__ == "__main__":
    extract_fixtures()
