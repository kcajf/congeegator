"""Benchmark one complete language without changing application artifacts.

Example: python -m pipeline.benchmark --language fi
For Python call profiles: python -m cProfile -o /tmp/fi.prof -m pipeline.benchmark --language fi
"""

import argparse
import json
import logging
from pathlib import Path
import sqlite3
import resource
import sys
import tempfile
import time

import zstandard

from .conjugation import CONFIG
from .dictionary import DICT_CONFIGS
from .generate import generate_data_for_lang
from .sqlite_output import write_sqlite_database
from .packed_entries import PackedDictionaryEntries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", required=True, choices=sorted(c.code for c in DICT_CONFIGS))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    config = next(c for c in DICT_CONFIGS if c.code == args.language)
    conjugation = next((c for c in CONFIG if c.code == args.language), None)
    start = time.perf_counter()
    _, data = generate_data_for_lang("en", conjugation, config, dev=False)
    processed = time.perf_counter()
    if data is None:
        raise RuntimeError(f"No dictionary entries for {args.language}")
    entries = data["entries"]
    with tempfile.TemporaryDirectory(prefix="dictionary-benchmark-") as directory:
        path = Path(directory) / f"{args.language}.sqlite"
        write_sqlite_database(entries, config.code, config.phonetic_fn, str(path))
        written = time.perf_counter()
        compressed = path.with_suffix(".sqlite.zst")
        with path.open("rb") as source, compressed.open("wb") as target:
            zstandard.ZstdCompressor(level=9, write_checksum=True).copy_stream(source, target)
        finished = time.perf_counter()
        print(json.dumps({
            "language": args.language,
            "sqlite_version": sqlite3.sqlite_version,
            "entries": len(entries),
            "forms": entries.form_count if isinstance(entries, PackedDictionaryEntries) else sum(
                len(entry.get("forms", [])) for entry in entries
            ),
            "packed_payload_bytes": entries.payload_bytes if isinstance(entries, PackedDictionaryEntries) else None,
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
            "processing_seconds": round(processed - start, 3),
            "database_seconds": round(written - processed, 3),
            "compression_seconds": round(finished - written, 3),
            "database_bytes": path.stat().st_size,
            "compressed_bytes": compressed.stat().st_size,
        }, indent=2))


if __name__ == "__main__":
    main()
