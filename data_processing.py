#!/usr/bin/env python3
import argparse
import gzip
import io
import json
import logging
import os
import shutil
import sys
import tempfile
from typing import Optional

import msgspec
import orjson
import polars as pl
import requests
import zstandard
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
    tags: tuple[str, ...] = ()
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


# msgspec.json.decode(line, type=Target)
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
    i = 0

    from pprint import pprint

    for line in data:
        # pprint(orjson.loads(line))
        try:
            obj = msgspec.json.decode(line, type=Entry)
        except Exception:
            pprint(orjson.loads(line))
            raise

        if obj.pos == "hard-redirect":
            continue

        assert obj.lang_code == lang
        # if obj.lang_code != lang:
        #     continue

        if obj.pos != "verb":
            continue

        i += 1
        if i % 1000 == 0:
            # print(f"{i:,}")
            pass
            # print(line)
            # pprint(obj)

        WORDS = (
            # "χωράω",
            # "χωρώ",
            # "δανείζω",
            # "ταξιδεύω",
            "πλένω",
            # "είμαι",
            "comer",
            "manger",
        )
        # WORDS = ('comer',)
        # match = False
        is_root = True
        for s in obj.senses:
            if "form-of" in s.tags:
                is_root = False
            if "alt-of" in s.tags:
                is_root = False

        if is_root and obj.word in WORDS:
            pprint(orjson.loads(line))
            # print(obj)
            print("---")

            # tag_set = obj.

            rows = []

            for form in obj.forms:
                if form.source != 'conjugation':
                    continue
                form_tag_set = set(form.tags)
                plurality = find_in_tags(form_tag_set, ("singular", "plural"))
                person = find_in_tags(
                    form_tag_set, ("first-person", "second-person", "third-person")
                )
                mood = find_in_tags(form_tag_set, ("indicative", 'imperative', 'subjunctive'))
                voice = find_in_tags(form_tag_set, ("active", "passive"))
                aspect = find_in_tags(form_tag_set, ("perfective", "imperfective"))
                tense = find_in_tags(form_tag_set, ("present", 'dependent', 'imperfect', 'past', 'future'))

                rows.append(
                    {
                        'form': form.form,
                        "plurality": plurality,
                        "person": person,
                        "mood": mood,
                        "voice": voice,
                        "aspect": aspect,
                        "tense": tense,
                        'tags': form.tags,
                        'source': form.source,
                    }
                )
            
            with pl.Config(tbl_rows=1000, fmt_str_lengths=1000, fmt_table_cell_list_len=1000):
                print(pl.from_records(rows))

        # pprint(orjson.loads(line))
        # pprint(obj)
        # raise

        # pprint(obj)

        # if obj['word'] == 'μιλάω' or obj['word'] == 'μιλώ':
        # # if obj['word'] == 'parler':
        #     # pprint(obj)
        #     print('---')

    print(i)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    main()
