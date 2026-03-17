#!/usr/bin/env python3
"""Unified data generation pipeline.

Generates conjugation data for Congeegator and dictionary data for Lexicoff
in a single pass over the source data.
"""
import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from typing import Any

import msgspec
from wordfreq import zipf_frequency

from .cache import CacheManager
from .conjugation import CONFIG, LanguageConfig, extract_conjugation, make_language_static_metadata
from .dictionary import DICT_CONFIGS, DictLanguageConfig, process_dict_entry, make_dict_language_static_metadata
from .gloss import extract_gloss
from .output import generate_sitemaps, write_data_manifest, write_language_data
from .search import build_search_index, GLOSS_STOP_WORDS, MIN_GLOSS_WORD_LENGTH
from .utils import log_timing, strip_diacritics
from .wiktionary import Entry, EntryJustPos

log = logging.getLogger(__name__)


def build_dict_search_index(
    entries: list[dict[str, Any]],
    phonetic_fn=None,
) -> dict[str, list[int]]:
    """Build a prefix search index for dictionary entries.

    Indexes entry words, their diacritics-stripped forms, phonetic forms,
    inflected forms, and gloss words.
    """
    from .gloss import _is_junk_gloss

    log.info("generating dict search index")
    searchable_words = defaultdict[str, set[int]](lambda: set())

    for i, entry in enumerate(entries):
        word = entry["word"]
        searchable_words[word].add(i)
        stripped = strip_diacritics(word)
        searchable_words[stripped].add(i)
        if phonetic_fn:
            phonetic = phonetic_fn(word)
            if phonetic != word and phonetic != stripped:
                searchable_words[phonetic].add(i)

        # Index inflected forms
        for form in entry.get("forms", []):
            if not form or form == "-":
                continue
            searchable_words[form].add(i)
            searchable_words[strip_diacritics(form)].add(i)
            if phonetic_fn:
                phonetic = phonetic_fn(form)
                if phonetic != form and phonetic != strip_diacritics(form):
                    searchable_words[phonetic].add(i)

    # Collect gloss words (English definitions) with prefix range 3-6
    gloss_words = defaultdict[str, set[int]](lambda: set())
    for i, entry in enumerate(entries):
        for sense in entry.get("senses", []):
            gloss = sense.get("gloss", "")
            if not gloss:
                continue
            for clause in gloss.split("; "):
                if clause == "...":
                    continue
                if _is_junk_gloss(clause):
                    continue
                clause = re.sub(r"\s*\[.*?\]", "", clause)
                for token in re.split(r"[\s,;]+", clause.lower()):
                    word = token.strip("().[]'\"")
                    if len(word) >= MIN_GLOSS_WORD_LENGTH and word not in GLOSS_STOP_WORDS:
                        gloss_words[word].add(i)

    index = defaultdict[str, set[int]](lambda: set())

    MIN_PREFIX = 1
    MAX_PREFIX = 4
    MAX_PREFIX_IDS = 200

    for word, indices in searchable_words.items():
        for prefix_len in range(MIN_PREFIX, MAX_PREFIX + 1):
            word_prefix = word[:prefix_len].lower()
            for i in indices:
                index[word_prefix].add(i)

    # Gloss words use prefix range 3-6
    MIN_GLOSS_PREFIX = 3
    MAX_GLOSS_PREFIX = 6
    for word, ids in gloss_words.items():
        for prefix_len in range(MIN_GLOSS_PREFIX, MAX_GLOSS_PREFIX + 1):
            prefix = word[:prefix_len].lower()
            index[prefix].update(ids)

    ret = {k: sorted(v)[:MAX_PREFIX_IDS] for k, v in index.items()}

    max_hits = 0
    max_key = None
    for k, v in ret.items():
        if len(v) > max_hits:
            max_hits = len(v)
            max_key = k

    log.info(f"Longest dict index entry: '{max_key}', {max_hits} hits")

    return ret


def generate_data_for_lang(
    wiki_lang: str,
    conj_config: LanguageConfig | None,
    dict_config: DictLanguageConfig | None,
    dev: bool,
):
    lang_code = conj_config.code if conj_config else dict_config.code
    log.info(f"generating {lang_code} data")
    cache = CacheManager()

    with log_timing(f"{lang_code} download"):
        data = list(cache.get_lang_filtered_raw_data(wiki_lang, lang_code))

    verbs: list[dict[str, Any]] = []
    seen_verbs: set[str] = set()
    dict_entries: list[dict[str, Any]] = []

    with log_timing(f"{lang_code} process entries"):
        for line in data:
            entry_just_pos = msgspec.json.decode(line, type=EntryJustPos)
            if entry_just_pos.pos == "hard-redirect":
                continue

            entry = msgspec.json.decode(line, type=Entry)
            assert entry.lang_code == lang_code

            # Conjugation processing (verbs only, deduplicated)
            if conj_config is not None:
                if entry.word not in seen_verbs:
                    processed = extract_conjugation(conj_config, entry)
                    if processed is not None:
                        verbs.append(processed)
                        seen_verbs.add(entry.word)

            # Dictionary processing (all POS)
            if dict_config is not None:
                dict_entry = process_dict_entry(dict_config, entry)
                if dict_entry is not None:
                    dict_entries.append(dict_entry)

            if dev and len(seen_verbs) > 20 and len(dict_entries) > 100:
                break

    conj_data = None
    dict_data = None

    # Build conjugation output
    if conj_config is not None and verbs:
        log.info(f"{lang_code} has {len(verbs)} conjugation entries")
        verbs = sorted(verbs, key=lambda x: x["nameNoDiacritics"])

        with log_timing(f"{lang_code} conj word frequencies"):
            for verb in verbs:
                verb["freq"] = round(zipf_frequency(verb["name"], lang_code), 2)

        unique_verbs = {x["name"] for x in verbs}
        if len(unique_verbs) != len(verbs):
            raise ValueError("duplicate conjugation entries")

        with log_timing(f"{lang_code} conj search index"):
            search_index = build_search_index(verbs, phonetic_fn=conj_config.phonetic_fn)

        conj_data = {
            "verbs": verbs,
            "searchIndex": search_index,
        }

    # Build dictionary output
    if dict_config is not None and dict_entries:
        log.info(f"{lang_code} has {len(dict_entries)} dictionary entries")
        dict_entries = sorted(dict_entries, key=lambda x: x.get("wordNoDiacritics", x["word"]))

        with log_timing(f"{lang_code} dict word frequencies"):
            for entry in dict_entries:
                entry["freq"] = round(zipf_frequency(entry["word"], lang_code), 2)

        with log_timing(f"{lang_code} dict search index"):
            dict_search_index = build_dict_search_index(dict_entries, phonetic_fn=dict_config.phonetic_fn)

        dict_data = {
            "entries": dict_entries,
            "searchIndex": dict_search_index,
        }

    return conj_data, dict_data


def generate_data(dev: bool):
    conj_ret: dict[str, dict[str, Any]] = {}
    dict_ret: dict[str, dict[str, Any]] = {}

    # Build lookup maps for configs by language code
    conj_configs = {c.code: c for c in CONFIG}
    dict_configs = {c.code: c for c in DICT_CONFIGS}

    # Union of all language codes
    all_lang_codes = sorted(set(conj_configs.keys()) | set(dict_configs.keys()))

    for lang_code in all_lang_codes:
        wiki_lang = "en"
        conj_config = conj_configs.get(lang_code)
        dict_config = dict_configs.get(lang_code)

        conj_data, dict_data = generate_data_for_lang(
            wiki_lang, conj_config, dict_config, dev=dev,
        )

        if conj_data is not None:
            conj_ret[lang_code] = conj_data
        if dict_data is not None:
            dict_ret[lang_code] = dict_data

    return conj_ret, dict_ret


CONGEEGATOR_BASE_URL = "https://congeegator.com"
LEXICOFF_BASE_URL = "https://lexicoff.com"


def check_conj_manifest_metadata():
    """Verify committed congeegator data-manifest.json structural metadata matches current LanguageConfig definitions."""
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
            log.error(f"Language '{config.code}' missing from congeegator manifest")
            ok = False
            continue

        actual = manifest["languages"][config.code]
        for key in ("tenseNames", "tensePronouns", "tenseGroups"):
            if expected[key] != actual.get(key):
                log.error(
                    f"Mismatch in congeegator {config.code}.{key}:\n"
                    f"  expected: {expected[key]}\n"
                    f"  actual:   {actual.get(key)}"
                )
                ok = False

    if ok:
        log.info("Congeegator manifest metadata matches current configs")
    return ok


def check_dict_manifest_metadata():
    """Verify committed lexicoff data-manifest.json structural metadata matches current DictLanguageConfig definitions."""
    manifest_path = os.path.join("apps", "lexicoff", "src", "lib", "data-manifest.json")
    if not os.path.exists(manifest_path):
        log.error(f"{manifest_path} not found")
        return False

    with open(manifest_path) as f:
        manifest = json.load(f)

    ok = True
    for config in DICT_CONFIGS:
        expected = make_dict_language_static_metadata(config)
        if config.code not in manifest.get("languages", {}):
            log.error(f"Language '{config.code}' missing from lexicoff manifest")
            ok = False
            continue

        actual = manifest["languages"][config.code]
        for key in ("code", "name", "englishWiktionaryName"):
            if expected[key] != actual.get(key):
                log.error(
                    f"Mismatch in lexicoff {config.code}.{key}:\n"
                    f"  expected: {expected[key]}\n"
                    f"  actual:   {actual.get(key)}"
                )
                ok = False

    if ok:
        log.info("Lexicoff manifest metadata matches current configs")
    return ok


def check_manifest_metadata():
    """Check both congeegator and lexicoff manifest metadata."""
    conj_ok = check_conj_manifest_metadata()
    dict_ok = check_dict_manifest_metadata()
    return conj_ok and dict_ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )
    parser.add_argument(
        "--check-manifest-metadata",
        action="store_true",
        help="Verify data-manifest.json metadata matches current config definitions",
    )
    args = parser.parse_args()

    if args.check_manifest_metadata:
        ok = check_manifest_metadata()
        sys.exit(0 if ok else 1)

    total_start = time.monotonic()

    with log_timing("generate data (all languages)"):
        conj_data, dict_data = generate_data(dev=args.dev)

    DATA_VERSION = "1"

    # --- Congeegator output ---
    if conj_data:
        with log_timing("generate congeegator sitemaps"):
            conj_sitemaps_dir = os.path.join("apps", "congeegator", "static")
            generate_sitemaps(conj_data, conj_sitemaps_dir, base_url=CONGEEGATOR_BASE_URL, entries_key="verbs")

        conj_r2_dir = os.path.join("apps", "congeegator", "r2_data")
        conj_data_dir = os.path.join(conj_r2_dir, "data", f"v{DATA_VERSION}")
        shutil.rmtree(conj_data_dir, ignore_errors=True)

        with log_timing("write congeegator output files"):
            for lang in conj_data.keys():
                lang_dir = os.path.join(conj_data_dir, lang)
                log.info(f"Writing congeegator {lang_dir}")
                write_language_data(conj_data[lang], lang_dir, entries_key="verbs", name_key="name", pretty=args.pretty)

        conj_manifest_path = os.path.join("apps", "congeegator", "src", "lib", "data-manifest.json")
        write_data_manifest(conj_data_dir, CONFIG, make_language_static_metadata, conj_manifest_path)

    # --- Lexicoff output ---
    if dict_data:
        with log_timing("generate lexicoff sitemaps"):
            dict_sitemaps_dir = os.path.join("apps", "lexicoff", "static")
            generate_sitemaps(dict_data, dict_sitemaps_dir, base_url=LEXICOFF_BASE_URL, entries_key="entries", name_key="word")

        dict_r2_dir = os.path.join("apps", "lexicoff", "r2_data")
        dict_data_dir = os.path.join(dict_r2_dir, "data", f"v{DATA_VERSION}")
        shutil.rmtree(dict_data_dir, ignore_errors=True)

        with log_timing("write lexicoff output files"):
            for lang in dict_data.keys():
                lang_dir = os.path.join(dict_data_dir, lang)
                log.info(f"Writing lexicoff {lang_dir}")
                write_language_data(dict_data[lang], lang_dir, entries_key="entries", name_key="word", pretty=args.pretty)

        dict_manifest_path = os.path.join("apps", "lexicoff", "src", "lib", "data-manifest.json")
        write_data_manifest(dict_data_dir, DICT_CONFIGS, make_dict_language_static_metadata, dict_manifest_path)

    total = time.monotonic() - total_start
    log.info(f"[timing] total: {total:.1f}s")


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    main()
