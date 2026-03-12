#!/usr/bin/env python3
"""Download latest source data from kaikki.org, filter, upload to R2, and update SOURCE_DATA_VERSION.

Usage:
    pixi run pin-source-data

Steps:
1. Downloads raw Wiktionary data from kaikki.org and filters to relevant languages
2. Uploads filtered .zst files to R2 at source-data/<timestamp>/
3. Updates SOURCE_DATA_VERSION in data_processing.py
4. Runs the full pipeline to regenerate r2_data/ and data-manifest.json

After running, review golden test diffs (pixi run test), then commit.
"""

import datetime
import gzip
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

import msgspec
import zstandard
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(__file__))

from data_processing import CONFIG, CacheManager

log = logging.getLogger(__name__)

R2_BUCKET = "r2-congeegator:congeegator"


class LangCode(msgspec.Struct):
    lang_code: str | None = None


def _raw_data_url(wiki_lang: str) -> str:
    if wiki_lang == "en":
        return "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl"
    return f"https://kaikki.org/dictionary/downloads/{wiki_lang}/{wiki_lang}-extract.jsonl.gz"


def _download_and_filter(wiki_lang: str, lang: str, output_path: str):
    """Download raw data from kaikki.org, filter to a single language, and save as .zst."""
    import requests

    url = _raw_data_url(wiki_lang)
    log.info(f"Downloading {url}")

    response = requests.get(url, stream=True)
    response.raise_for_status()
    total_size = int(response.headers.get("content-length", 0))

    progress_bar = tqdm(
        total=total_size, unit="B", unit_scale=True, desc=f"Downloading ({lang})"
    )

    class ProgressWrapper:
        def __init__(self, obj):
            self.obj = obj

        def read(self, n):
            chunk = self.obj.read(n)
            progress_bar.update(len(chunk))
            return chunk

    temp_dir = os.path.dirname(output_path)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(dir=temp_dir, delete=False) as temp_file:
            temp_path = temp_file.name

            wrapped_stream = ProgressWrapper(response.raw)
            cctx = zstandard.ZstdCompressor(level=3)

            with gzip.GzipFile(fileobj=wrapped_stream) as decompressor:  # type: ignore
                with cctx.stream_writer(temp_file) as compressor:
                    buffer = b""
                    while True:
                        chunk = decompressor.read(128 * 1024)
                        if not chunk:
                            if buffer:
                                entry = msgspec.json.decode(buffer, type=LangCode)
                                if entry.lang_code == lang:
                                    compressor.write(buffer)
                                    compressor.write(b"\n")
                            break

                        buffer += chunk
                        lines = buffer.split(b"\n")
                        buffer = lines.pop()

                        for line in lines:
                            if not line:
                                continue
                            entry = msgspec.json.decode(line, type=LangCode)
                            if entry.lang_code == lang:
                                compressor.write(line)
                                compressor.write(b"\n")

        os.rename(temp_path, output_path)
        temp_path = None
        log.info(f"Saved filtered data to {output_path}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def ensure_filtered_data(cache_dir: str):
    """Make sure filtered .zst files exist in cache (downloads from kaikki.org if needed)."""
    os.makedirs(cache_dir, exist_ok=True)
    for config in CONFIG:
        wiki_lang = "en"
        cache_path = os.path.join(
            cache_dir, f"{wiki_lang}-{config.code}-filtered.jsonl.zst"
        )
        if os.path.exists(cache_path):
            log.info(f"Found existing: {cache_path}")
        else:
            log.info(f"Downloading and filtering data for {config.code}...")
            _download_and_filter(wiki_lang, config.code, cache_path)


def upload_to_r2(cache_dir: str, version: str):
    """Upload filtered .zst files to R2."""
    for config in CONFIG:
        wiki_lang = "en"
        local_path = os.path.join(
            cache_dir, f"{wiki_lang}-{config.code}-filtered.jsonl.zst"
        )
        r2_path = f"{R2_BUCKET}/source-data/{version}/{wiki_lang}-{config.code}-filtered.jsonl.zst"
        log.info(f"Uploading {local_path} -> {r2_path}")
        result = subprocess.run(
            ["rclone", "copyto", local_path, r2_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"rclone error: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        log.info(f"Uploaded {config.code}")


def update_version_in_source(version: str):
    """Update SOURCE_DATA_VERSION in data_processing.py."""
    dp_path = os.path.join(os.path.dirname(__file__), "data_processing.py")
    with open(dp_path, "r") as f:
        content = f.read()

    new_content = re.sub(
        r'SOURCE_DATA_VERSION = "[^"]*"',
        f'SOURCE_DATA_VERSION = "{version}"',
        content,
    )
    assert new_content != content, "Failed to find SOURCE_DATA_VERSION to update"

    with open(dp_path, "w") as f:
        f.write(new_content)
    log.info(f"Updated SOURCE_DATA_VERSION to {version}")


def run_pipeline():
    """Run the full data pipeline."""
    log.info("Running full data pipeline...")
    result = subprocess.run(
        [sys.executable, "data_processing.py"],
        cwd=os.path.dirname(__file__) or ".",
    )
    if result.returncode != 0:
        print("Pipeline failed!", file=sys.stderr)
        sys.exit(1)
    log.info("Pipeline completed")


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    version = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H%M%SZ")
    log.info(f"Source data version: {version}")

    # Use a temporary working directory for downloads, separate from the versioned cache
    work_dir = os.path.join(CacheManager.CACHE_DIR, "_pin_working")
    ensure_filtered_data(work_dir)
    upload_to_r2(work_dir, version)
    update_version_in_source(version)

    # Move filtered files into the versioned cache dir so the pipeline finds them
    version_cache_dir = os.path.join(CacheManager.CACHE_DIR, version)
    os.makedirs(version_cache_dir, exist_ok=True)
    for config in CONFIG:
        wiki_lang = "en"
        src = os.path.join(work_dir, f"{wiki_lang}-{config.code}-filtered.jsonl.zst")
        dst = os.path.join(version_cache_dir, f"{wiki_lang}-{config.code}-filtered.jsonl.zst")
        shutil.move(src, dst)
    shutil.rmtree(work_dir, ignore_errors=True)

    run_pipeline()

    print(f"\nDone! SOURCE_DATA_VERSION updated to {version}")
    print("Next steps:")
    print("  1. Review golden test diffs: pixi run test")
    print("  2. Update golden files if needed: pixi run pytest tests/ --update-golden")
    print("  3. Commit: data_processing.py, src/lib/data-manifest.json, tests/golden/")


if __name__ == "__main__":
    main()
