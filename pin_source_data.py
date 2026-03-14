#!/usr/bin/env python3
"""Download latest source data from kaikki.org, filter, upload to R2, and update SOURCE_DATA_VERSION.

Usage:
    pixi run pin-source-data                  # Full re-pin (all languages, new version)
    python pin_source_data.py --add-lang it   # Add one language to existing version

Steps (full re-pin):
1. Downloads raw Wiktionary data from kaikki.org and filters to relevant languages
2. Uploads filtered .zst files to R2 at source-data/<timestamp>/
3. Updates SOURCE_DATA_VERSION in data_processing.py
4. Runs the full pipeline to regenerate r2_data/ and data-manifest.json

After running, review golden test diffs (pixi run test), then commit.

--add-lang <code>:
    Uploads source data for a single language to the CURRENT SOURCE_DATA_VERSION in R2.
    Use this when a new language is added after the last full pin run.
    Does not change SOURCE_DATA_VERSION or regenerate data.
"""

import argparse
import datetime
import gzip
import logging
import os
import re
import subprocess
import sys
import tempfile

import msgspec
import requests
import zstandard
from tqdm import tqdm

from data_processing import CONFIG

log = logging.getLogger(__name__)

R2_BUCKET = "r2-congeegator:congeegator"


class LangCode(msgspec.Struct):
    lang_code: str | None = None


def _raw_data_url(wiki_lang: str) -> str:
    if wiki_lang == "en":
        return "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl"
    return f"https://kaikki.org/dictionary/downloads/{wiki_lang}/{wiki_lang}-extract.jsonl.gz"


def _filename(wiki_lang: str, lang: str) -> str:
    return f"{wiki_lang}-{lang}-filtered.jsonl.zst"


def _download_and_filter(wiki_lang: str, lang: str, output_path: str):
    """Download raw data from kaikki.org, filter to a single language, and save as .zst."""
    url = _raw_data_url(wiki_lang)
    log.info(f"Downloading {url}")

    response = requests.get(url, stream=True)
    response.raise_for_status()
    total_size = int(response.headers.get("content-length", 0))

    is_tty = sys.stderr.isatty()
    progress_bar = tqdm(
        total=total_size,
        unit="B",
        unit_scale=True,
        desc=f"Downloading ({lang})",
        disable=not is_tty,
    )

    class ProgressWrapper:
        def __init__(self, obj):
            self.obj = obj
            self.bytes_read = 0
            self._last_logged_mb = 0

        def read(self, n):
            chunk = self.obj.read(n)
            self.bytes_read += len(chunk)
            progress_bar.update(len(chunk))
            # In CI (non-TTY), log progress every 50 MB
            if not is_tty:
                current_mb = self.bytes_read // (50 * 1024 * 1024)
                if current_mb > self._last_logged_mb:
                    self._last_logged_mb = current_mb
                    mb_read = self.bytes_read / (1024 * 1024)
                    if total_size:
                        pct = self.bytes_read * 100 / total_size
                        log.info(f"Downloading ({lang}): {mb_read:.0f} MB ({pct:.0f}%)")
                    else:
                        log.info(f"Downloading ({lang}): {mb_read:.0f} MB")
            return chunk

    output_dir = os.path.dirname(output_path)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as temp_file:
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


def _upload_to_r2(local_path: str, r2_path: str):
    log.info(f"Uploading {local_path} -> {r2_path}")
    result = subprocess.run(
        ["rclone", "copyto", local_path, r2_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"rclone error: {result.stderr}", file=sys.stderr)
        sys.exit(1)


def _update_version_in_source(version: str):
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


def _run_pipeline():
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


def _add_lang(lang_code: str):
    """Upload source data for a single language to the current SOURCE_DATA_VERSION in R2.

    Use this when a new language is added to CONFIG but its source data was not included
    in the original pin. Does not change SOURCE_DATA_VERSION or re-run the pipeline.

    After running, re-run the full pipeline and commit updated outputs:
        pixi run python data_processing.py
        git add src/lib/data-manifest.json r2_data/
    """
    from data_processing import SOURCE_DATA_VERSION

    log.info(f"Adding lang '{lang_code}' to existing version {SOURCE_DATA_VERSION}")

    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_lang = "en"
        name = _filename(wiki_lang, lang_code)
        local_path = os.path.join(tmpdir, name)

        _download_and_filter(wiki_lang, lang_code, local_path)
        _upload_to_r2(local_path, f"{R2_BUCKET}/source-data/{SOURCE_DATA_VERSION}/{name}")

    print(f"\nDone! Uploaded {name} to source-data/{SOURCE_DATA_VERSION}/")
    print("Next steps:")
    print("  1. Re-run the pipeline: pixi run python data_processing.py")
    print("  2. Commit updated outputs: src/lib/data-manifest.json, r2_data/")


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Pin source data for all languages or add a single language to an existing version."
    )
    parser.add_argument(
        "--add-lang",
        metavar="CODE",
        help=(
            "Upload source data for a single language code (e.g. 'it') to the current "
            "SOURCE_DATA_VERSION without creating a new version. Use when a language was "
            "added after the last full pin run."
        ),
    )
    args = parser.parse_args()

    if args.add_lang:
        _add_lang(args.add_lang)
        return

    version = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H%M%SZ")
    log.info(f"Source data version: {version}")

    with tempfile.TemporaryDirectory() as tmpdir:
        for config in CONFIG:
            wiki_lang = "en"
            name = _filename(wiki_lang, config.code)
            local_path = os.path.join(tmpdir, name)

            _download_and_filter(wiki_lang, config.code, local_path)
            _upload_to_r2(local_path, f"{R2_BUCKET}/source-data/{version}/{name}")

    _update_version_in_source(version)
    _run_pipeline()

    print(f"\nDone! SOURCE_DATA_VERSION updated to {version}")
    print("Next steps:")
    print("  1. Review golden test diffs: pixi run test")
    print("  2. Update golden files if needed: pixi run pytest tests/ --update-golden")
    print("  3. Commit: data_processing.py, src/lib/data-manifest.json, tests/golden/")


if __name__ == "__main__":
    main()
