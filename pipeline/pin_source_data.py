#!/usr/bin/env python3
"""Download source data once, split languages, and pin immutable snapshots in R2.

Usage:
    pixi run pin-source-data
    pixi run pin-source-data --languages pt ca --no-regenerate
    pixi run pin-source-data --languages pt ca --no-upload --output-dir /tmp/source-review

Steps:
1. Downloads raw Wiktionary data from kaikki.org and filters to relevant languages
2. Uploads filtered .zst files to R2 at source-data/<timestamp>/
3. Updates SOURCE_DATA_VERSION, or per-language overrides for a partial pin
4. Runs the full pipeline unless --no-regenerate is supplied

Use --input-file to reuse a downloaded source, and --source-sha256 to ensure
publication uses the exact source that was reviewed. --no-upload retains local
files without changing source versions or regenerating app output.

After running, review golden test diffs (pixi run test), then commit.
"""

import argparse
import ast
import datetime
import gzip
import hashlib
import logging
import os
import re
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path

import msgspec
import requests
import zstandard
from tqdm import tqdm

from .conjugation import CONFIG
from .dictionary import DICT_CONFIGS

log = logging.getLogger(__name__)

R2_BUCKET = "r2-congeegator:congeegator"


class LangCode(msgspec.Struct):
    lang_code: str | None = None


def _raw_data_url(wiki_lang: str) -> str:
    if wiki_lang == "en":
        return "https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"
    return f"https://kaikki.org/dictionary/downloads/{wiki_lang}/{wiki_lang}-extract.jsonl.gz"


def _filename(wiki_lang: str, lang: str) -> str:
    return f"{wiki_lang}-{lang}-filtered.jsonl.zst"


def configured_languages() -> list[str]:
    """Include dictionary-only languages, retaining deterministic config order."""
    return list(dict.fromkeys(config.code for config in [*CONFIG, *DICT_CONFIGS]))


def _source_lines(stream):
    """Read plain JSONL or gzip, including servers that gzip a .jsonl URL."""
    prefix = stream.read(2)

    class PrefixedReader:
        def read(self, n=-1):
            nonlocal prefix
            if n < 0:
                result, prefix = prefix + stream.read(), b""
                return result
            head, prefix = prefix[:n], prefix[n:]
            return head + stream.read(n - len(head))

    reader = PrefixedReader()
    with ExitStack() as stack:
        if prefix == b"\x1f\x8b":
            reader = stack.enter_context(gzip.GzipFile(fileobj=reader))
        buffer = b""
        while chunk := reader.read(128 * 1024):
            lines = (buffer + chunk).split(b"\n")
            buffer = lines.pop()
            yield from (line for line in lines if line.strip())
        if buffer.strip():
            yield buffer


def _download_and_filter(
    wiki_lang: str,
    output_paths: dict[str, str],
    input_file: Path | None = None,
    source_sha256: str | None = None,
) -> dict[str, int]:
    """Download each source once and stream requested languages into separate .zst files.

    Nothing is published unless the complete source parses and every requested
    language has entries. Temporary files are discarded after interrupted runs.
    """
    if not output_paths:
        raise ValueError("At least one language must be requested")
    url = _raw_data_url(wiki_lang)
    log.info("Downloading %s for %s", url, ", ".join(output_paths))
    counts = dict.fromkeys(output_paths, 0)
    temp_paths: dict[str, str] = {}
    try:
        with ExitStack() as stack:
            if input_file is not None:
                raw = stack.enter_context(input_file.open("rb"))
                total_size = input_file.stat().st_size
            else:
                response = stack.enter_context(requests.get(url, stream=True, timeout=(30, 300)))
                response.raise_for_status()
                # Decode HTTP Content-Encoding first; _source_lines handles a gzip file.
                response.raw.decode_content = True
                raw = response.raw
                total_size = int(response.headers.get("content-length", 0))
            digest = hashlib.sha256()
            progress = stack.enter_context(tqdm(
                total=total_size,
                unit="B", unit_scale=True, desc=f"Downloading ({wiki_lang})",
                disable=not sys.stderr.isatty(),
            ))

            class ProgressReader:
                def __init__(self):
                    self.bytes_read = 0
                    self.last_logged = 0

                def read(self, n=-1):
                    chunk = raw.read(n)
                    digest.update(chunk)
                    self.bytes_read += len(chunk)
                    progress.update(len(chunk))
                    if not sys.stderr.isatty() and self.bytes_read - self.last_logged >= 50 * 1024 * 1024:
                        log.info("Downloaded %.0f MB", self.bytes_read / (1024 * 1024))
                        self.last_logged = self.bytes_read
                    return chunk

            writers = {}
            for lang, output_path in output_paths.items():
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                temp_file = stack.enter_context(tempfile.NamedTemporaryFile(
                    dir=Path(output_path).parent, delete=False,
                ))
                temp_paths[lang] = temp_file.name
                writers[lang] = stack.enter_context(
                    zstandard.ZstdCompressor(level=3).stream_writer(temp_file, closefd=False)
                )
            decoder = msgspec.json.Decoder(LangCode)
            for line in _source_lines(ProgressReader()):
                lang = decoder.decode(line).lang_code
                if lang in writers:
                    writers[lang].write(line + b"\n")
                    counts[lang] += 1
            missing = [lang for lang, count in counts.items() if not count]
            if missing:
                raise ValueError(f"Source contains no entries for: {', '.join(missing)}")
            actual_sha256 = digest.hexdigest()
            if source_sha256 is not None and actual_sha256 != source_sha256.lower():
                raise ValueError(f"Source SHA256 mismatch: expected {source_sha256}, got {actual_sha256}")
            log.info("Source SHA256: %s", actual_sha256)

        for lang, output_path in output_paths.items():
            os.replace(temp_paths[lang], output_path)
            del temp_paths[lang]
            log.info("Saved %s (%s entries)", output_path, f"{counts[lang]:,}")
        return counts
    finally:
        for temp_path in temp_paths.values():
            if os.path.exists(temp_path):
                os.unlink(temp_path)


def _upload_to_r2(local_path: str, r2_path: str):
    log.info(f"Uploading {local_path} -> {r2_path}")
    result = subprocess.run(
        ["rclone", "copyto", "--immutable", local_path, r2_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"rclone error: {result.stderr}", file=sys.stderr)
        sys.exit(1)


def _update_version_in_source(version: str, languages: list[str] | None = None):
    """Update a full snapshot, or overrides for only the selected languages."""
    path = Path(__file__).with_name("cache.py")
    content = path.read_text()
    overrides = {}
    tree = ast.parse(content)
    override_node = next(
        node for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "SOURCE_DATA_VERSIONS"
    )
    if languages is not None:
        overrides = ast.literal_eval(override_node.value)
        overrides.update(dict.fromkeys(languages, version))
    replacement = "SOURCE_DATA_VERSIONS: dict[str, str] = {"
    if overrides:
        replacement += "\n" + "".join(
            f'    "{lang}": "{value}",\n' for lang, value in sorted(overrides.items())
        )
    replacement += "}"
    lines = content.splitlines(keepends=True)
    lines[override_node.lineno - 1:override_node.end_lineno] = [replacement + "\n"]
    content = "".join(lines)
    if languages is None:
        content, changed = re.subn(
            r'SOURCE_DATA_VERSION = "[^"]*"',
            f'SOURCE_DATA_VERSION = "{version}"', content,
        )
        if changed != 1:
            raise ValueError("Failed to find SOURCE_DATA_VERSION to update")
    path.write_text(content)
    log.info("Updated %s to %s", languages or "all languages", version)


def _run_pipeline():
    """Run the full data pipeline."""
    log.info("Running full data pipeline...")
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.generate"],
        cwd=os.path.dirname(os.path.dirname(__file__)) or ".",
    )
    if result.returncode != 0:
        print("Pipeline failed!", file=sys.stderr)
        sys.exit(1)
    log.info("Pipeline completed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", nargs="+", choices=configured_languages(),
                        help="Pin only these languages, preserving all other snapshots")
    parser.add_argument("--version", help="Snapshot timestamp (defaults to the current UTC time)")
    parser.add_argument("--output-dir", type=Path, help="Keep filtered source files in this directory")
    parser.add_argument("--input-file", type=Path, help="Split an already downloaded raw source file")
    parser.add_argument("--source-sha256", help="Reject a source file that differs from this SHA256")
    parser.add_argument("--no-upload", action="store_true",
                        help="Download for local review only; do not upload or update source versions")
    parser.add_argument("--no-regenerate", action="store_true", help="Do not run the data pipeline")
    args = parser.parse_args()
    if args.no_upload and args.output_dir is None:
        parser.error("--no-upload requires --output-dir so the downloaded files are retained")
    version = args.version or datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H%M%SZ")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{6}Z", version):
        parser.error("--version must have the form YYYY-MM-DDTHHMMSSZ")
    if args.source_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", args.source_sha256):
        parser.error("--source-sha256 must be a 64-character hexadecimal SHA256")
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    log.info("Source data version: %s", version)
    languages = list(dict.fromkeys(args.languages or configured_languages()))
    with ExitStack() as stack:
        output_dir = args.output_dir or Path(stack.enter_context(tempfile.TemporaryDirectory()))
        paths = {lang: str(output_dir / _filename("en", lang)) for lang in languages}
        _download_and_filter("en", paths, args.input_file, args.source_sha256)
        if args.no_upload:
            log.info("Local review files retained in %s; source versions unchanged", output_dir)
            return
        for lang, local_path in paths.items():
            _upload_to_r2(local_path, f"{R2_BUCKET}/source-data/{version}/{_filename('en', lang)}")
    _update_version_in_source(version, args.languages)
    if not args.no_regenerate:
        _run_pipeline()
    print(f"Done! Pinned {len(languages)} languages at {version}. Review tests and manifests before committing.")


if __name__ == "__main__":
    main()
