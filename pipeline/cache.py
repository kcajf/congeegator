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
    "ang": "2026-09-14T200000Z",
    "ar": "2026-09-15T074500Z",
    "ast": "2026-09-15T074500Z",
    "az": "2026-09-13T130000Z",
    "bg": "2026-09-14T200000Z",
    "bn": "2026-09-15T074500Z",
    "br": "2026-09-13T130000Z",
    "ca": "2026-09-12T210000Z",
    "ceb": "2026-09-15T074500Z",
    "cs": "2026-09-12T210000Z",
    "cy": "2026-09-13T130000Z",
    "da": "2026-09-12T210000Z",
    "eo": "2026-09-12T210000Z",
    "et": "2026-09-13T130000Z",
    "eu": "2026-09-13T130000Z",
    "fa": "2026-09-13T130000Z",
    "fi": "2026-09-12T210000Z",
    "fo": "2026-09-14T200000Z",
    "ga": "2026-09-13T130000Z",
    "gd": "2026-09-14T200000Z",
    "gl": "2026-09-12T210000Z",
    "grc": "2026-09-13T130000Z",
    "he": "2026-09-13T130000Z",
    "hi": "2026-09-13T130000Z",
    "hu": "2026-09-12T210000Z",
    "hy": "2026-09-15T074500Z",
    "id": "2026-09-12T210000Z",
    "is": "2026-09-13T130000Z",
    "ja": "2026-09-15T074500Z",
    "ka": "2026-09-13T130000Z",
    "ko": "2026-09-13T130000Z",
    "la": "2026-09-12T210000Z",
    "lt": "2026-09-13T130000Z",
    "lv": "2026-09-14T200000Z",
    "mk": "2026-09-13T130000Z",
    "ms": "2026-09-13T130000Z",
    "mt": "2026-09-14T200000Z",
    "nb": "2026-09-12T210000Z",
    "nl": "2026-09-12T210000Z",
    "nn": "2026-09-14T200000Z",
    "non": "2026-09-14T200000Z",
    "nv": "2026-09-15T074500Z",
    "oc": "2026-09-13T130000Z",
    "pa": "2026-09-15T074500Z",
    "pl": "2026-09-12T210000Z",
    "pt": "2026-09-12T210000Z",
    "ro": "2026-09-12T210000Z",
    "ru": "2026-09-12T210000Z",
    "sa": "2026-09-13T130000Z",
    "sh": "2026-09-13T130000Z",
    "sk": "2026-09-13T130000Z",
    "sq": "2026-09-15T074500Z",
    "sv": "2026-09-12T210000Z",
    "sw": "2026-09-15T074500Z",
    "ta": "2026-09-15T074500Z",
    "te": "2026-09-15T074500Z",
    "th": "2026-09-15T074500Z",
    "tl": "2026-09-14T200000Z",
    "tr": "2026-09-12T210000Z",
    "uk": "2026-09-12T210000Z",
    "ur": "2026-09-15T074500Z",
    "vi": "2026-09-12T210000Z",
    "zh": "2026-09-15T074500Z",
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
