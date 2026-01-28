#!/usr/bin/env python3
import argparse
import gzip
import hashlib
import io
import json
import logging
import os
import shutil
import sys
import tempfile
from typing import Any, Optional

import msgspec
import orjson
import polars as pl
import requests
import zstandard
from rich.pretty import pprint
from tqdm import tqdm

log = logging.getLogger(__name__)


class CacheManager:
    CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

    def __init__(self):
        os.makedirs(CacheManager.CACHE_DIR, exist_ok=True)

    @staticmethod
    def _raw_data_url(wiki_lang: str) -> str:
        if wiki_lang == "en":
            return "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl"
        return f"https://kaikki.org/dictionary/downloads/{wiki_lang}/{wiki_lang}-extract.jsonl.gz"

    def _get_zstd_file_stream(self, path: str, chunk_size: int = 128 * 1024):
        dctx = zstandard.ZstdDecompressor()

        with open(path, "rb") as f:
            with dctx.stream_reader(f) as reader:
                buffer = b""
                while True:
                    chunk = reader.read(chunk_size)
                    if not chunk:
                        if buffer:
                            yield buffer
                        break

                    buffer += chunk
                    lines = buffer.split(b"\n")
                    # The last element is either an incomplete line or empty
                    buffer = lines.pop()

                    for line in lines:
                        if line:
                            yield line

    def get_raw_data(self, wiki_lang: str):
        cache_path = os.path.join(CacheManager.CACHE_DIR, f"{wiki_lang}-raw.jsonl.zst")

        if os.path.exists(cache_path):
            log.info(f"Found {cache_path}")
            return self._get_zstd_file_stream(cache_path)

        url = self._raw_data_url(wiki_lang)
        log.info(f"requesting {url}")

        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))

        progress_bar = tqdm(
            total=total_size, unit="B", unit_scale=True, desc="Downloading"
        )

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                dir=CacheManager.CACHE_DIR, delete=False
            ) as temp_file:
                temp_path = temp_file.name

                class ProgressWrapper:
                    def __init__(self, obj):
                        self.obj = obj

                    def read(self, n):
                        chunk = self.obj.read(n)
                        progress_bar.update(len(chunk))
                        return chunk

                wrapped_stream = ProgressWrapper(response.raw)

                # Remote -> Progress -> Gzip -> Zstd -> Disk
                with gzip.GzipFile(fileobj=wrapped_stream) as decompressor:  # type: ignore
                    cctx = zstandard.ZstdCompressor(level=3)
                    with cctx.stream_writer(temp_file) as compressor:
                        shutil.copyfileobj(decompressor, compressor)

                os.rename(temp_file.name, cache_path)
                log.info(f"saved to {cache_path}")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
                print(f"Cleaned up {temp_path}")

        return self._get_zstd_file_stream(cache_path)

    def get_lang_filtered_raw_data(self, wiki_lang: str, lang: str):
        cache_path = os.path.join(
            CacheManager.CACHE_DIR, f"{wiki_lang}-{lang}-filtered.jsonl.zst"
        )
        if os.path.exists(cache_path):
            log.info(f"Found {cache_path}")
            return self._get_zstd_file_stream(cache_path)

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                dir=CacheManager.CACHE_DIR, delete=False
            ) as temp_file:
                temp_path = temp_file.name

                all_lines = self.get_raw_data(wiki_lang)
                log.info(
                    f"filtering {lang} entries, saving to {cache_path} (may take minutes)..."
                )

                with open(temp_path, "wb"):
                    cctx = zstandard.ZstdCompressor(level=3)

                    class LangCode(msgspec.Struct):
                        lang_code: Optional[str] = None

                    with cctx.stream_writer(temp_file) as compressor:
                        for line in all_lines:
                            obj = msgspec.json.decode(line, type=LangCode)
                            if obj.lang_code != lang:
                                continue
                            compressor.write(line)
                            compressor.write(b"\n")

                os.rename(temp_file.name, cache_path)
                log.info(f"saved to {cache_path}")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
                print(f"Cleaned up {temp_path}")

        return self._get_zstd_file_stream(cache_path)


class Form(msgspec.Struct, frozen=True):
    form: Optional[str] = None
    tags: set[str] = set()
    source: Optional[str] = None


class FormOf(msgspec.Struct, frozen=True):
    word: str
    extra: Optional[str] = None


class Sense(msgspec.Struct, frozen=True):
    form_of: tuple[FormOf, ...] = ()
    alt_of: tuple[FormOf, ...] = ()
    tags: tuple[str, ...] = ()


class Entry(msgspec.Struct, frozen=True):
    pos: str
    forms: tuple[Form, ...] = ()
    senses: tuple[Sense, ...] = ()
    lang_code: Optional[str] = None
    word: Optional[str] = None


def find_in_tags(tags: set[str], values: tuple[str, ...]) -> Optional[str]:
    for v in values:
        if v in tags:
            return v
    return None


def matches_tags(tags: set[str], want_tags: tuple[str, ...]) -> bool:
    for t in want_tags:
        if t not in tags:
            return False
    return True


PERSONS = ("first-person", "second-person", "third-person")
NUMBERS = ("singular", "plural")
PERSONS_NUMBERS = tuple((person, number) for number in NUMBERS for person in PERSONS)


class FormMatcher(msgspec.Struct, frozen=True):
    tags: tuple[str, ...]
    formatter: str = "{}"

    def matches(self, form: Form) -> bool:
        for t in self.tags:
            if t not in form.tags:
                return False
        return True

    def format(self, form: Form) -> str:
        return self.formatter.format(form.form)


LANG_NAMES = {
    "el": "Modern Greek",
    "es": "Spanish",
    "fr": "French",
}


GREEK_CONFIG = {
    "active present": tuple(
        FormMatcher(tags=(*pn, "present", "indicative", "imperfective", "active"))
        for pn in PERSONS_NUMBERS
    ),
    "passive present": tuple(
        FormMatcher(tags=(*pn, "present", "indicative", "imperfective", "passive"))
        for pn in PERSONS_NUMBERS
    ),
    "active imperfect": tuple(
        FormMatcher(tags=(*pn, "imperfect", "indicative", "imperfective", "active"))
        for pn in PERSONS_NUMBERS
    ),
    "passive imperfect": tuple(
        FormMatcher(tags=(*pn, "imperfect", "indicative", "imperfective", "passive"))
        for pn in PERSONS_NUMBERS
    ),
    "active aorist": tuple(
        FormMatcher(tags=(*pn, "past", "indicative", "perfective", "active"))
        for pn in PERSONS_NUMBERS
    ),
    "passive aorist": tuple(
        FormMatcher(tags=(*pn, "past", "indicative", "perfective", "passive"))
        for pn in PERSONS_NUMBERS
    ),
    "active imperative": tuple(
        FormMatcher(tags=("second-person", n, "imperative", "imperfective", "active"))
        for n in NUMBERS
    ),
    "passive imperative": tuple(
        FormMatcher(tags=("second-person", n, "imperative", "imperfective", "passive"))
        for n in NUMBERS
    ),
    "active future continuous": tuple(
        FormMatcher(
            tags=("active", *pn, "present", "indicative", "imperfective"),
            formatter="θα {}",
        )
        for pn in PERSONS_NUMBERS
    ),
    "active present participle": FormMatcher(tags=("active", "present", "participle")),
    "active perfect participle": FormMatcher(tags=("active", "past", "participle")),
    "passive perfect participle": FormMatcher(tags=("passive", "past", "participle")),
    "passive present participle": FormMatcher(
        tags=("passive", "present", "participle")
    ),
    "active infinitive aorist": FormMatcher(tags=("active", "infinitive-aorist")),
    "passive infinitive aorist": FormMatcher(tags=("passive", "infinitive-aorist")),
}


def structure_map(f, s):
    if isinstance(s, list):
        return [structure_map(f, x) for x in s]
    if isinstance(s, tuple):
        return tuple(structure_map(f, x) for x in s)
    if isinstance(s, dict):
        return {k: structure_map(f, v) for k, v in s.items()}
    return f(s)


def extract_one(matcher: FormMatcher, forms: list[Form]) -> str:
    ret = ""
    for form in forms:
        if form.source != "conjugation":
            continue
        assert form.form is not None
        if matcher.matches(form):
            if ret != "":
                ret += "|"
            ret += matcher.format(form)
    return ret


def extract_conjugations_from_forms(config, forms: list[Form]):
    return structure_map(lambda matcher: extract_one(matcher, forms), config)


def form_is_clean_conjugation(form: Form) -> bool:
    if form.source != "conjugation":
        return False
    if form.form in {
        "Formed using present",
        "dependent (for simple past)",
        "present perfect from above with a particle (να, ας).",
        "no-table-tags",
    }:
        return False
    if "table-tags" in form.tags:
        return False
    if "inflection-template" in form.tags:
        return False
    return True


def count_conjs(thing) -> int:
    n = 0
    if isinstance(thing, str):
        n += thing != ""
    elif isinstance(thing, dict):
        for _, v in thing.items():
            n += count_conjs(v)
    elif isinstance(thing, (tuple, list)):
        for x in thing:
            n += count_conjs(x)
    else:
        raise ValueError(thing)
    return n


def write_language_data(data: dict[str, Any], lang_dir: str):
    shutil.rmtree(lang_dir, ignore_errors=True)
    os.makedirs(lang_dir, exist_ok=True)

    # full data file
    out_path = os.path.join(lang_dir, "data.json")
    with open(out_path, "w") as f:
        log.info(f"Wrote {out_path}")
        json.dump(data, f, indent=2, ensure_ascii=False)

    # single verbs file
    single_verbs_dir = os.path.join(lang_dir, "verbs")
    if os.path.exists(single_verbs_dir):
        shutil.rmtree(single_verbs_dir)
    os.makedirs(single_verbs_dir)
    for verb, verb_data in data.items():
        with open(os.path.join(single_verbs_dir, f"{verb}.json"), "w") as f:
            json.dump(verb_data, f, indent=2, ensure_ascii=False)

    # index file
    with open(os.path.join(lang_dir, "index.json"), "w") as f:
        json.dump(sorted(data.keys()), f, indent=2, ensure_ascii=False)

def write_data_manifest(data_dir: str):
    # write data-manifest.json
    language_hashes = {}
    for path in os.listdir(data_dir):
        data_path = os.path.join(data_dir, path, "data.json")
        if not os.path.exists(data_path):
            continue

        language = path
        with open(data_path, "rb") as f:
            h = hashlib.file_digest(f, "md5").hexdigest()[:8]
        language_hashes[language] = {"hash": h, "name": LANG_NAMES[language]}

    with open(os.path.join("src", "lib", "data-manifest.json"), "w") as f:
        json.dump(
            {
                "languages": language_hashes,
            },
            f,
            indent=2,
        )




# This is significantly faster than general dict parsing.
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki")
    parser.add_argument("--lang")
    args = parser.parse_args()

    wiki_lang = args.wiki
    lang = args.lang
    cache = CacheManager()

    data = cache.get_lang_filtered_raw_data(wiki_lang, lang)

    out = {}

    for line in data:
        obj = msgspec.json.decode(line, type=Entry)

        if obj.pos == "hard-redirect":
            continue

        assert obj.lang_code == lang

        if obj.pos != "verb":
            continue

        if obj.word == "μέλλων":
            pprint(orjson.loads(line))

        is_root = True
        for s in obj.senses:
            if "form-of" in s.tags:
                is_root = False
            if "alt-of" in s.tags:
                is_root = False

        if is_root:
            filtered_forms = [f for f in obj.forms if form_is_clean_conjugation(f)]
            conj = extract_conjugations_from_forms(GREEK_CONFIG, filtered_forms)

            out[obj.word] = conj

    out = {k: out[k] for k in sorted(out.keys())}

    has_conj_count = 0
    for k, v in out.items():
        has_conj_count += count_conjs(v) != 0
        # print(k, count_conjs(v))

    log.info(
        f"{has_conj_count / len(out):.1%} ({has_conj_count}/{len(out)}) of verbs have conjugation data"
    )

    DATA_VERSION = "1"

    static_dir = os.path.join(os.path.dirname(__file__), "r2_data")
    data_dir = os.path.join(static_dir, "data", f"v{DATA_VERSION}")
    lang_dir = os.path.join(data_dir, lang)

    write_language_data(out, lang_dir)

    write_data_manifest(data_dir)
    # shutil.copyfile(os.path.join(data_dir, "data-manifest.json"), os.path.join("src", "lib", "data-manifest.json"))
    log.info("all done")


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    main()
