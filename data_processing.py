#!/usr/bin/env python3
import gzip
import io
import json
import logging
import os
import shutil
import sys

import requests
import zstandard
from tqdm import tqdm

log = logging.getLogger(__name__)

class CacheManager:
    CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
    
    def __init__(self):
        os.makedirs(CacheManager.CACHE_DIR, exist_ok=True)

    @staticmethod
    def _raw_data_url(lang: str) -> str:
        return f"https://kaikki.org/dictionary/downloads/{lang}/{lang}-extract.jsonl.gz"

    def _get_zstd_file_stream(self, path: str):
        f = open(path, 'rb')
        dctx = zstandard.ZstdDecompressor()
        reader = dctx.stream_reader(f)
        return io.TextIOWrapper(reader, encoding='utf-8')

    def get_cached_raw_data(self, lang: str) -> io.TextIOWrapper:
        cache_path = os.path.join(CacheManager.CACHE_DIR, f"{lang}-raw.jsonl.zst")

        if os.path.exists(cache_path):
            log.info(f"Found {cache_path}")
            return self._get_zstd_file_stream(cache_path)

        url = self._raw_data_url(lang)
        tmp_path = cache_path + ".tmp"
        log.info(f"requesting {url}")
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        progress_bar = tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading")

        with response as r:
            r.raise_for_status()

            class ProgressWrapper:
                def __init__(self, obj): self.obj = obj
                def read(self, n):
                    chunk = self.obj.read(n)
                    progress_bar.update(len(chunk))
                    return chunk

            wrapped_stream = ProgressWrapper(r.raw)
                
            # Remote -> Progress -> Gzip -> Zstd -> Disk
            with gzip.GzipFile(fileobj=wrapped_stream) as decompressor: # type: ignore
                with open(tmp_path, 'wb') as f_out:
                    cctx = zstandard.ZstdCompressor(level=3) 
                    with cctx.stream_writer(f_out) as compressor:
                        shutil.copyfileobj(decompressor, compressor)
        
        os.rename(tmp_path, cache_path)
        log.info(f"saved to {cache_path}")
        return self._get_zstd_file_stream(cache_path)

def main():
    lang = "el"
    cache = CacheManager()


    data = cache.get_cached_raw_data('el')
    i = 0
    for x in data:
        obj = json.loads(x)
        if obj['pos'] == "hard-redirect":
            continue

        if obj["lang_code"] != lang:
            continue
            
        if obj['pos'] != "verb":
            continue
            
        from pprint import pprint
        
        if obj['word'] == 'μιλάω' or obj['word'] == 'μιλώ':
            pprint(obj)
            print('---')

        i += 1
    print(i)
        


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    main()