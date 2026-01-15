#!/usr/bin/env python3

def get_raw_data_url(lang: str) -> str:
    return f"https://kaikki.org/dictionary/downloads/{lang}/{lang}-extract.jsonl.gz"

lang = "el"
