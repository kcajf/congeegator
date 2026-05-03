import logging
import os
import shutil
import tempfile

import requests
import zstandard

log = logging.getLogger(__name__)

# Timestamp version of pinned source data in R2.
# Update by running: pixi run pin-source-data
SOURCE_DATA_VERSION = "2026-05-03T080901Z"


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
        cache_path = os.path.join(
            self._version_cache_dir, f"{wiki_lang}-{lang}-filtered.jsonl.zst"
        )
        if not os.path.exists(cache_path):
            url = f"{self.R2_PUBLIC_URL}/source-data/{SOURCE_DATA_VERSION}/{wiki_lang}-{lang}-filtered.jsonl.zst"
            log.info(f"Fetching pinned source data: {url}")

            response = requests.get(url, stream=True)
            if response.status_code == 404:
                raise RuntimeError(
                    f"Pinned source data not found at {url}\n"
                    f"Make sure source data has been uploaded for version {SOURCE_DATA_VERSION}"
                )
            response.raise_for_status()

            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=self._version_cache_dir, delete=False
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
