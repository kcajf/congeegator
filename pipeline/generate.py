#!/usr/bin/env python3
"""Unified data generation pipeline.

Currently generates conjugation data for Congeegator.
Phase B will add dictionary data generation for Lexicoff.
"""
import argparse
import json
import logging
import os
import shutil
import sys
import time
from typing import Any

import msgspec
from wordfreq import zipf_frequency

from .cache import CacheManager
from .conjugation import CONFIG, LanguageConfig, extract_conjugation, make_language_static_metadata
from .gloss import extract_gloss
from .output import generate_sitemaps, write_data_manifest, write_language_data
from .search import build_search_index
from .utils import log_timing, strip_diacritics
from .wiktionary import Entry, EntryJustPos

log = logging.getLogger(__name__)


def generate_data_for_lang(wiki_lang: str, lang: LanguageConfig, dev: bool):
    log.info(f"generating {lang.code} data")
    cache = CacheManager()

    with log_timing(f"{lang.code} download"):
        data = list(cache.get_lang_filtered_raw_data(wiki_lang, lang.code))

    verbs: list[dict[str, Any]] = []
    seen_verbs: set[str] = set()

    with log_timing(f"{lang.code} process entries"):
        for line in data:
            entry_just_pos = msgspec.json.decode(line, type=EntryJustPos)
            if entry_just_pos.pos == "hard-redirect":
                continue

            entry = msgspec.json.decode(line, type=Entry)
            assert entry.lang_code == lang.code

            if entry.word in seen_verbs:
                log.debug(f"duplicate: {entry.word}")
                continue

            processed = extract_conjugation(lang, entry)
            if processed is None:
                continue

            verbs.append(processed)
            seen_verbs.add(entry.word)

            if dev and len(seen_verbs) > 20:
                break

    log.info(f"{lang.code} has {len(verbs)} entries")
    verbs = sorted(verbs, key=lambda x: x["nameNoDiacritics"])

    with log_timing(f"{lang.code} word frequencies"):
        for verb in verbs:
            verb["freq"] = round(zipf_frequency(verb["name"], lang.code), 2)

    unique_verbs = {x["name"] for x in verbs}
    if len(unique_verbs) != len(verbs):
        raise ValueError("duplicates")

    with log_timing(f"{lang.code} search index"):
        search_index = build_search_index(verbs, phonetic_fn=lang.phonetic_fn)

    return {
        "verbs": verbs,
        "searchIndex": search_index,
    }


def generate_data(dev: bool):
    ret: dict[str, dict[str, Any]] = {}

    for config in CONFIG:
        wiki_lang = "en"
        ret[config.code] = generate_data_for_lang(wiki_lang, config, dev=dev)

    return ret


BASE_URL = "https://congeegator.com"


def check_manifest_metadata():
    """Verify committed data-manifest.json structural metadata matches current LanguageConfig definitions."""
    manifest_path = os.path.join("apps", "congeegator", "src", "lib", "data-manifest.json")
    if not os.path.exists(manifest_path):
        log.error(f"{manifest_path} not found")
        return False

    with open(manifest_path) as f:
        manifest = json.load(f)

    ok = True
    for config in CONFIG:
        expected = make_language_static_metadata(config)
        if config.code not in manifest.get("languages", {}):
            log.error(f"Language '{config.code}' missing from manifest")
            ok = False
            continue

        actual = manifest["languages"][config.code]
        for key in ("tenseNames", "tensePronouns", "tenseGroups"):
            if expected[key] != actual.get(key):
                log.error(
                    f"Mismatch in {config.code}.{key}:\n"
                    f"  expected: {expected[key]}\n"
                    f"  actual:   {actual.get(key)}"
                )
                ok = False

    if ok:
        log.info("Manifest metadata matches current configs")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )
    parser.add_argument(
        "--check-manifest-metadata",
        action="store_true",
        help="Verify data-manifest.json metadata matches current LanguageConfig definitions",
    )
    args = parser.parse_args()

    if args.check_manifest_metadata:
        ok = check_manifest_metadata()
        sys.exit(0 if ok else 1)

    total_start = time.monotonic()

    with log_timing("generate data (all languages)"):
        data = generate_data(dev=args.dev)

    with log_timing("generate sitemaps"):
        sitemaps_dir = os.path.join("apps", "congeegator", "static")
        generate_sitemaps(data, sitemaps_dir, base_url=BASE_URL, entries_key="verbs")

    DATA_VERSION = "1"

    r2_dir = os.path.join("apps", "congeegator", "r2_data")
    data_dir = os.path.join(r2_dir, "data", f"v{DATA_VERSION}")
    shutil.rmtree(data_dir, ignore_errors=True)

    with log_timing("write output files"):
        for lang in data.keys():
            lang_dir = os.path.join(data_dir, lang)
            log.info(f"Writing {lang_dir}")
            write_language_data(data[lang], lang_dir, entries_key="verbs", pretty=args.pretty)

    manifest_path = os.path.join("apps", "congeegator", "src", "lib", "data-manifest.json")
    write_data_manifest(data_dir, CONFIG, make_language_static_metadata, manifest_path)

    total = time.monotonic() - total_start
    log.info(f"[timing] total: {total:.1f}s")


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    main()
