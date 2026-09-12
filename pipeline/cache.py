import logging
import os
import shutil
import tempfile

import requests
import zstandard

log = logging.getLogger(__name__)

# Timestamp version of pinned source data in R2.
# Update by running: pixi run pin-source-data
SOURCE_DATA_VERSION = "2026-09-07T120928Z"

# Languages added between full refreshes use their own immutable snapshot.
# Existing languages retain SOURCE_DATA_VERSION until the next full refresh.
SOURCE_DATA_VERSIONS: dict[str, str] = {
    "ca": "2026-09-12T210000Z",
    "cs": "2026-09-12T210000Z",
    "da": "2026-09-12T210000Z",
    "eo": "2026-09-12T210000Z",
    "fi": "2026-09-12T210000Z",
    "gl": "2026-09-12T210000Z",
    "hu": "2026-09-12T210000Z",
    "id": "2026-09-12T210000Z",
    "la": "2026-09-12T210000Z",
    "nb": "2026-09-12T210000Z",
    "nl": "2026-09-12T210000Z",
    "pl": "2026-09-12T210000Z",
    "pt": "2026-09-12T210000Z",
    "ro": "2026-09-12T210000Z",
    "ru": "2026-09-12T210000Z",
    "sv": "2026-09-12T210000Z",
    "tr": "2026-09-12T210000Z",
    "uk": "2026-09-12T210000Z",
    "vi": "2026-09-12T210000Z",
}


def source_data_version(lang: str) -> str:
    return SOURCE_DATA_VERSIONS.get(lang, SOURCE_DATA_VERSION)


class CacheManager:
    CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
    R2_PUBLIC_URL = "https://assets.congeegator.com"

    def __init__(self):
        self._version_cache_dir = os.path.join(CacheManager.CACHE_DIR, SOURCE_DATA_VERSION)
        os.makedirs(self._version_cache_dir, exist_ok=True)

    def _stream_zstd_lines(self, path: str, chunk_size: int = 128 * 1024):
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
                    buffer = lines.pop()
                    for line in lines:
                        if line:
                            yield line

    def get_lang_filtered_raw_data(self, wiki_lang: str, lang: str):
        version = source_data_version(lang)
        version_cache_dir = os.path.join(self.CACHE_DIR, version)
        os.makedirs(version_cache_dir, exist_ok=True)
        cache_path = os.path.join(
            version_cache_dir, f"{wiki_lang}-{lang}-filtered.jsonl.zst"
        )
        if not os.path.exists(cache_path):
            url = f"{self.R2_PUBLIC_URL}/source-data/{version}/{wiki_lang}-{lang}-filtered.jsonl.zst"
            log.info(f"Fetching pinned source data: {url}")

            temp_path = None
            try:
                with requests.get(url, stream=True, timeout=(30, 300)) as response:
                    if response.status_code == 404:
                        raise RuntimeError(
                            f"Pinned source data not found at {url}\n"
                            f"Make sure source data has been uploaded for version {version}"
                        )
                    response.raise_for_status()
                    with tempfile.NamedTemporaryFile(
                        dir=version_cache_dir, delete=False
                    ) as temp_file:
                        temp_path = temp_file.name
                        shutil.copyfileobj(response.raw, temp_file)
                os.rename(temp_path, cache_path)
                temp_path = None
                log.info(f"Downloaded to {cache_path}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            log.info(f"Found {cache_path}")

        return self._stream_zstd_lines(cache_path)
