#!/usr/bin/env python3
"""Unified data generation pipeline.

Generates conjugation data for Congeegator and dictionary data for Lexicoff
in a single pass over the source data.
"""
import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import time
from typing import Any

import zstandard

import msgspec
from wordfreq import available_languages, get_frequency_dict, get_frequency_list, zipf_frequency

from .cache import CacheManager
from .conjugation import CONFIG, LanguageConfig, extract_conjugation, make_language_static_metadata
from .dictionary import DICT_CONFIGS, DictLanguageConfig, process_dict_entry, make_dict_language_static_metadata
from .gloss import extract_gloss
from .output import generate_sitemaps, write_data_manifest, write_language_data, write_sqlite_manifest
from .search import build_search_index
from .sqlite_output import write_sqlite_database
from .utils import log_timing, strip_diacritics
from .wiktionary import Entry, EntryJustPos

log = logging.getLogger(__name__)


def generate_data_for_lang(
    wiki_lang: str,
    conj_config: LanguageConfig | None,
    dict_config: DictLanguageConfig | None,
    dev: bool,
):
    try:
        return _generate_data_for_lang(wiki_lang, conj_config, dict_config, dev)
    finally:
        # wordfreq retains each loaded corpus in unbounded caches. Release the
        # corpus after both apps have used it so memory does not grow by language.
        get_frequency_dict.cache_clear()
        get_frequency_list.cache_clear()


def _generate_data_for_lang(
    wiki_lang: str,
    conj_config: LanguageConfig | None,
    dict_config: DictLanguageConfig | None,
    dev: bool,
):
    lang_code = conj_config.code if conj_config else dict_config.code
    log.info(f"generating {lang_code} data")
    cache = CacheManager()

    with log_timing(f"{lang_code} download"):
        data = cache.get_lang_filtered_raw_data(wiki_lang, lang_code)

    verbs: list[dict[str, Any]] = []
    seen_verbs: set[str] = set()
    dict_entries: list[dict[str, Any]] = []
    seen_dict_records: set[bytes] = set()
    duplicate_dict_records = 0

    with log_timing(f"{lang_code} process entries"):
        for line in data:
            entry_just_pos = msgspec.json.decode(line, type=EntryJustPos)
            if entry_just_pos.pos == "hard-redirect":
                continue
            # Raw extracts also include thesaurus-only records without a POS or
            # definitions. They are not lexical entries for either application.
            if entry_just_pos.pos is None and entry_just_pos.source == "thesaurus":
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
                    fingerprint = hashlib.sha256(msgspec.json.encode(dict_entry)).digest()
                    if fingerprint not in seen_dict_records:
                        seen_dict_records.add(fingerprint)
                        dict_entries.append(dict_entry)
                    else:
                        duplicate_dict_records += 1

            if dev and (conj_config is None or len(seen_verbs) > 20) and (dict_config is None or len(dict_entries) > 100):
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
        if duplicate_dict_records:
            log.info("%s removed %d identical dictionary records", lang_code, duplicate_dict_records)

        with log_timing(f"{lang_code} dict word frequencies"):
            has_frequency = lang_code in available_languages()
            if not has_frequency:
                log.warning("%s has no wordfreq corpus; using unranked frequency 0", lang_code)
            for entry in dict_entries:
                entry["freq"] = round(zipf_frequency(entry["word"], lang_code), 2) if has_frequency else 0.0

        dict_entries = sorted(dict_entries, key=lambda x: -x["freq"])

        dict_data = {
            "entries": dict_entries,
        }

    return conj_data, dict_data


def iter_language_data(dev: bool, app: str = "all"):
    """Process one language at a time so dictionary expansion stays memory bounded."""
    # Build lookup maps for configs by language code
    conj_configs = {c.code: c for c in CONFIG} if app != "lexicoff" else {}
    dict_configs = {c.code: c for c in DICT_CONFIGS} if app != "congeegator" else {}

    # Union of all language codes
    all_lang_codes = sorted(set(conj_configs.keys()) | set(dict_configs.keys()))

    for lang_code in all_lang_codes:
        wiki_lang = "en"
        conj_config = conj_configs.get(lang_code)
        dict_config = dict_configs.get(lang_code)

        conj_data, dict_data = generate_data_for_lang(
            wiki_lang, conj_config, dict_config, dev=dev,
        )
        if dict_config is not None and dict_data is None:
            raise RuntimeError(f"No dictionary entries generated for {lang_code}; refusing an incomplete catalogue")

        yield lang_code, conj_data, dict_data
        del dict_data


def generate_data(dev: bool, app: str = "all"):
    conj_ret = {}
    dict_ret = {}
    for lang_code, conj_data, dict_data in iter_language_data(dev, app):
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
    parser.add_argument("--app", choices=("all", "lexicoff", "congeegator"), default="all",
                        help="Generate only the selected app, leaving the other app untouched")
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

    DATA_VERSION = "1"

    dict_data_dir = os.path.join("apps", "lexicoff", "r2_data", "data", f"v{DATA_VERSION}")
    if args.app != "congeegator":
        shutil.rmtree(dict_data_dir, ignore_errors=True)
    dict_configs_by_code = {c.code: c for c in DICT_CONFIGS}
    conj_data = {}
    written_dict_languages = set()
    with log_timing("generate data (all languages)"):
        for lang_code, language_conj, language_dict in iter_language_data(args.dev, args.app):
            if language_conj is not None:
                conj_data[lang_code] = language_conj
            if language_dict is not None:
                write_dictionary_language(language_dict["entries"], dict_configs_by_code[lang_code], dict_data_dir)
                written_dict_languages.add(lang_code)
            # Do not retain all languages' dictionary records during generation.
            del language_dict

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

    # --- Lexicoff output (SQLite) ---
    if written_dict_languages:
        dict_manifest_path = os.path.join("apps", "lexicoff", "src", "lib", "data-manifest.json")
        write_sqlite_manifest(dict_data_dir, DICT_CONFIGS, make_dict_language_static_metadata, dict_manifest_path)

    total = time.monotonic() - total_start
    log.info(f"[timing] total: {total:.1f}s")


def write_dictionary_language(entries, config: DictLanguageConfig, data_dir: str):
    lang_dir = os.path.join(data_dir, config.code)
    os.makedirs(lang_dir, exist_ok=True)
    sqlite_path = os.path.join(lang_dir, f"{config.code}.sqlite")
    write_sqlite_database(entries, config.code, phonetic_fn=config.phonetic_fn, output_path=sqlite_path)
    with open(sqlite_path, "rb") as f_in, open(sqlite_path + ".zst", "wb") as f_out:
        zstandard.ZstdCompressor(level=9).copy_stream(f_in, f_out)
    os.remove(sqlite_path)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    main()
