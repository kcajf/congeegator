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
        letter = key[0] if key else "_"
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


def generate_sitemaps(data: dict[str, dict[str, Any]], static_dir: str, base_url: str, entries_key: str = "verbs", name_key: str = "name"):
    os.makedirs(static_dir, exist_ok=True)

    lang_codes = sorted(data.keys())

    sitemap_index_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    sitemap_index_lines.append(
        f"  <sitemap><loc>{base_url}/sitemap-homepage.xml</loc></sitemap>"
    )
    for lang in lang_codes:
        sitemap_index_lines.append(
            f"  <sitemap><loc>{base_url}/sitemap-{lang}.xml</loc></sitemap>"
        )
    sitemap_index_lines.append("</sitemapindex>")
    sitemap_index_lines.append("")

    index_path = os.path.join(static_dir, "sitemap.xml")
    with open(index_path, "w") as f:
        f.write("\n".join(sitemap_index_lines))
    log.info(f"Wrote {index_path}")

    homepage_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <url><loc>{base_url}/</loc></url>",
        "</urlset>",
        "",
    ]
    homepage_path = os.path.join(static_dir, "sitemap-homepage.xml")
    with open(homepage_path, "w") as f:
        f.write("\n".join(homepage_lines))
    log.info(f"Wrote {homepage_path}")

    for lang in lang_codes:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        seen_names: set[str] = set()
        for entry in data[lang][entries_key]:
            if entry[name_key] not in seen_names:
                encoded_name = urllib.parse.quote(entry[name_key], safe="")
                lines.append(f"  <url><loc>{base_url}/{lang}/{encoded_name}</loc></url>")
                seen_names.add(entry[name_key])
        lines.append("</urlset>")
        lines.append("")

        lang_path = os.path.join(static_dir, f"sitemap-{lang}.xml")
        with open(lang_path, "w") as f:
            f.write("\n".join(lines))
        log.info(f"Wrote {lang_path} ({len(seen_names)} entries)")
