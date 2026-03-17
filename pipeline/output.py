import hashlib
import json
import logging
import os
import urllib.parse
from typing import Any, Callable

from .utils import _orjson_dump

log = logging.getLogger(__name__)


def write_language_data(data: dict[str, Any], lang_dir: str, entries_key: str = "verbs", name_key: str = "name", pretty: bool = False):
    os.makedirs(lang_dir, exist_ok=True)

    # full data file
    out_path = os.path.join(lang_dir, "data.json")
    with open(out_path, "wb") as f:
        f.write(_orjson_dump(data, pretty))
    log.info(f"Wrote {out_path}")

    # chunked files (grouped by first letter, lowercased)
    chunks_dir = os.path.join(lang_dir, "chunks")
    os.makedirs(chunks_dir)
    chunks: dict[str, dict[str, Any]] = {}
    for entry_data in data[entries_key]:
        key = entry_data[name_key].lower()
        letter = key[0] if key and key[0].isalnum() else "_"
        chunks.setdefault(letter, {})[key] = entry_data
    for letter, chunk_data in chunks.items():
        with open(os.path.join(chunks_dir, f"{letter}.json"), "wb") as f:
            f.write(_orjson_dump(chunk_data, pretty))

    # index file
    seen_names: set[str] = set()
    unique_names: list[str] = []
    for x in data[entries_key]:
        if x[name_key] not in seen_names:
            unique_names.append(x[name_key])
            seen_names.add(x[name_key])
    with open(os.path.join(lang_dir, "index.json"), "wb") as f:
        f.write(_orjson_dump(unique_names, pretty))


def write_data_manifest(
    data_dir: str,
    configs: list,
    make_metadata: Callable,
    manifest_path: str,
):
    language_hashes = {}
    for config in configs:
        data_path = os.path.join(data_dir, config.code, "data.json")
        if not os.path.exists(data_path):
            continue

        data_size = os.path.getsize(data_path)

        with open(data_path, "rb") as f:
            h = hashlib.file_digest(f, "md5").hexdigest()[:8]

        hashed_data_dir = os.path.join(data_dir, f"{config.code}-{h}")
        os.rename(os.path.join(data_dir, config.code), hashed_data_dir)

        log.info(f"{config.code}: dataHash={h} dataSize={data_size}")

        language_hashes[config.code] = {
            "dataHash": h,
            "dataSize": data_size,
            **make_metadata(config),
        }

    log.info(f"Writing {manifest_path}")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(
            {
                "languages": language_hashes,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


MAX_URLS_PER_SITEMAP = 40_000


def _write_sitemap(path: str, url_lines: list[str]):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        *url_lines,
        "</urlset>",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))


def generate_sitemaps(data: dict[str, dict[str, Any]], static_dir: str, base_url: str, entries_key: str = "verbs", name_key: str = "name"):
    os.makedirs(static_dir, exist_ok=True)

    lang_codes = sorted(data.keys())

    # Collect all sitemap filenames as we generate them
    sitemap_files: list[str] = []

    # Homepage sitemap
    homepage_file = "sitemap-homepage.xml"
    sitemap_files.append(homepage_file)
    _write_sitemap(
        os.path.join(static_dir, homepage_file),
        [f"  <url><loc>{base_url}/</loc></url>"],
    )
    log.info(f"Wrote {os.path.join(static_dir, homepage_file)}")

    # Per-language sitemaps (split if > MAX_URLS_PER_SITEMAP)
    for lang in lang_codes:
        seen_names: set[str] = set()
        url_lines: list[str] = []
        for entry in data[lang][entries_key]:
            name = entry[name_key]
            if name not in seen_names:
                encoded_name = urllib.parse.quote(name, safe="")
                url_lines.append(f"  <url><loc>{base_url}/{lang}/{encoded_name}</loc></url>")
                seen_names.add(name)

        if len(url_lines) <= MAX_URLS_PER_SITEMAP:
            filename = f"sitemap-{lang}.xml"
            sitemap_files.append(filename)
            _write_sitemap(os.path.join(static_dir, filename), url_lines)
            log.info(f"Wrote {os.path.join(static_dir, filename)} ({len(url_lines)} URLs)")
        else:
            part = 1
            for i in range(0, len(url_lines), MAX_URLS_PER_SITEMAP):
                chunk = url_lines[i : i + MAX_URLS_PER_SITEMAP]
                filename = f"sitemap-{lang}-{part}.xml"
                sitemap_files.append(filename)
                _write_sitemap(os.path.join(static_dir, filename), chunk)
                log.info(f"Wrote {os.path.join(static_dir, filename)} ({len(chunk)} URLs)")
                part += 1

    # Sitemap index
    sitemap_index_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for filename in sitemap_files:
        sitemap_index_lines.append(f"  <sitemap><loc>{base_url}/{filename}</loc></sitemap>")
    sitemap_index_lines.append("</sitemapindex>")
    sitemap_index_lines.append("")

    index_path = os.path.join(static_dir, "sitemap.xml")
    with open(index_path, "w") as f:
        f.write("\n".join(sitemap_index_lines))
    log.info(f"Wrote {index_path} ({len(sitemap_files)} sitemaps)")
