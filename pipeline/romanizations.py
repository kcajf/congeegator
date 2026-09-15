"""Explicit headword readings only; no inferred vowels or paradigm expansion."""
import json
from pathlib import Path
import re
import unicodedata

PROFILES = json.loads((Path(__file__).resolve().parent.parent / 'shared/romanization-profiles.json').read_text())
VERSION = '1'


def romanization_keys(lang, reading):
    if lang not in PROFILES:
        return []
    strict = unicodedata.normalize('NFC', reading.strip().lower())
    if not strict:
        return []
    mapping = PROFILES[lang]
    loose = strict
    if mapping:
        pattern = '|'.join(re.escape(key) for key in sorted(mapping, key=len, reverse=True))
        loose = re.sub(pattern, lambda match: mapping[match[0]], loose)
    loose = ''.join(c for c in unicodedata.normalize('NFD', loose) if unicodedata.category(c) != 'Mn')
    if mapping:
        loose = re.sub(pattern, lambda match: mapping[match[0]], loose)
    loose = re.sub(r"[’'ʼʹʺ]", '', loose)
    loose = re.sub(r'[\s-]+', ' ', loose).strip()
    # Display retains the original spelling; index only one normalized key.
    return [(loose or strict, 5)]


def extract_romanizations(entry, clean_text):
    if entry.lang_code not in PROFILES:
        return []
    result = []
    for form in entry.forms:
        # Table cells and alternative native spellings aren't headword readings.
        if form.source:
            continue
        raw = form.form if form.tags & {'romanization', 'transliteration'} else (
            form.roman if form.form == entry.word else None
        )
        value = clean_text(raw or '')
        if not value or value in {'-', '—', '–', '?'} or any(c in value for c in '/,;()[]{}<>'):
            continue
        # Only Latin-script readings (plus marks and ordinary separators).
        if not any('LATIN' in unicodedata.name(c, '') for c in value):
            continue
        if any(c.isalpha() and c not in 'ʿʾʹʺʼ' and 'LATIN' not in unicodedata.name(c, '') for c in value):
            continue
        if value not in result:
            result.append(value)
    return result
