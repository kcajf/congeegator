#!/usr/bin/env python3
"""Upload filtered source data to R2 at a date-stamped path and update SOURCE_DATA_VERSION.

Usage:
    pixi run update-source-data

Steps:
1. Ensures filtered .zst files exist in cache/ (downloads + filters from kaikki.org if needed)
2. Uploads them to R2 at source-data/<date>/
3. Updates SOURCE_DATA_VERSION in data_processing.py
4. Runs the full pipeline to regenerate r2_data/ and data-manifest.json

After running, review golden test diffs (pixi run test), then commit.
"""

import datetime
import logging
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

from data_processing import CONFIG, CacheManager

log = logging.getLogger(__name__)

R2_BUCKET = "r2-congeegator:congeegator"


def ensure_filtered_data():
    """Make sure filtered .zst files exist in cache (downloads from kaikki.org if needed)."""
    cache = CacheManager()
    for config in CONFIG:
        wiki_lang = "en"
        cache_path = os.path.join(
            CacheManager.CACHE_DIR, f"{wiki_lang}-{config.code}-filtered.jsonl.zst"
        )
        if os.path.exists(cache_path):
            log.info(f"Found existing: {cache_path}")
        else:
            log.info(f"Generating filtered data for {config.code}...")
            # This triggers download + filtering
            list(cache.get_lang_filtered_raw_data(wiki_lang, config.code))
            assert os.path.exists(cache_path), f"Expected {cache_path} to exist after filtering"


def upload_to_r2(date_str: str):
    """Upload filtered .zst files to R2."""
    for config in CONFIG:
        wiki_lang = "en"
        local_path = os.path.join(
            CacheManager.CACHE_DIR, f"{wiki_lang}-{config.code}-filtered.jsonl.zst"
        )
        r2_path = f"{R2_BUCKET}/source-data/{date_str}/{wiki_lang}-{config.code}-filtered.jsonl.zst"
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


def update_version_in_source(date_str: str):
    """Update SOURCE_DATA_VERSION in data_processing.py."""
    dp_path = os.path.join(os.path.dirname(__file__), "data_processing.py")
    with open(dp_path, "r") as f:
        content = f.read()

    new_content = re.sub(
        r'SOURCE_DATA_VERSION = "[^"]*"',
        f'SOURCE_DATA_VERSION = "{date_str}"',
        content,
    )
    assert new_content != content, "Failed to find SOURCE_DATA_VERSION to update"

    with open(dp_path, "w") as f:
        f.write(new_content)
    log.info(f"Updated SOURCE_DATA_VERSION to {date_str}")


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

    date_str = datetime.date.today().isoformat()
    log.info(f"Source data version: {date_str}")

    ensure_filtered_data()
    upload_to_r2(date_str)
    update_version_in_source(date_str)
    run_pipeline()

    print(f"\nDone! SOURCE_DATA_VERSION updated to {date_str}")
    print("Next steps:")
    print("  1. Review golden test diffs: pixi run test")
    print("  2. Update golden files if needed: pixi run pytest tests/ --update-golden")
    print("  3. Commit: data_processing.py, src/lib/data-manifest.json, tests/golden/")


if __name__ == "__main__":
    main()
