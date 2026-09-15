"""Compare optional headword/form romanizations; does not change production output.

Uses seeded reservoir samples of source entries, identical accepted records in
all variants, production row compression and production download compression.
"""
import argparse
import copy
import io
import json
from pathlib import Path
import random
import shutil
import sqlite3
import tempfile
import unicodedata
from unittest.mock import patch

import msgspec
import zstandard
from wordfreq import available_languages, zipf_frequency

from .cache import source_data_version
from .dictionary import DICT_CONFIGS, INCLUDED_POS, _clean_text, process_dict_entry
from .entry_json import ROW_COMPRESSION_LEVEL, encode_entry_json, decode_entry_json
from .sqlite_output import write_sqlite_database
from .wiktionary import Entry

CONFIGS = {c.code: c for c in DICT_CONFIGS}


def clean_reading(value):
    if not isinstance(value, str):
        return None
    value = _clean_text(value)
    if not value or value in {'-', '—', '–', '?'} or any(c in value for c in '/,;()'):
        return None  # Do not guess how combined or annotated readings align.
    return value


def readings(raw, record):
    heads, forms = [], {}
    accepted = {unicodedata.normalize('NFC', f): f for f in record.get('forms', [])}
    rejected = 0
    for form in raw.get('forms', []):
        tags = set(form.get('tags', []))
        if tags & {'romanization', 'transliteration'} and not form.get('source'):
            value = clean_reading(form.get('form'))
            if value and value not in heads:
                heads.append(value)
        if not form.get('roman'):
            continue
        value = clean_reading(form['roman'])
        native = unicodedata.normalize('NFC', form.get('form') or '')
        if value and native == unicodedata.normalize('NFC', record['word']):
            if value not in heads:
                heads.append(value)
        elif value and native in accepted:
            bucket = forms.setdefault(accepted[native], [])
            if value not in bucket:
                bucket.append(value)
        else:
            rejected += 1
    return heads, forms, rejected


def sample_source(path, size, seed):
    rng, sample, count = random.Random(seed), [], 0
    with path.open('rb') as file, zstandard.ZstdDecompressor().stream_reader(file) as stream:
        for line in io.BufferedReader(stream):
            raw = msgspec.json.decode(line)
            if raw.get('pos') not in INCLUDED_POS:
                continue
            count += 1
            if len(sample) < size:
                sample.append((count, raw))
            elif (index := rng.randrange(count)) < size:
                sample[index] = (count, raw)
    return [raw for _, raw in sorted(sample)], count


def sizes(path):
    with path.open('rb') as source, tempfile.TemporaryFile() as target:
        zstandard.ZstdCompressor(level=9, write_checksum=True).copy_stream(source, target)
        return {'sqlite_bytes': path.stat().st_size, 'download_bytes': target.tell()}


def index_key(reading):
    # Only one literal lookup key per reading: no speculative language alias expansion.
    return unicodedata.normalize('NFC', reading.lower())


def reset_romanizations(conn):
    conn.execute('DROP TABLE IF EXISTS romanized_lookup')
    if 'romanizations' in {row[1] for row in conn.execute('PRAGMA table_info(entries)')}:
        conn.execute('ALTER TABLE entries DROP COLUMN romanizations')
    conn.execute("DELETE FROM metadata WHERE key = 'romanization_version'")


def variant(baseline, target, entries, extracted, mode, indexed):
    shutil.copyfile(baseline, target)
    compressor = zstandard.ZstdCompressor(level=ROW_COMPRESSION_LEVEL, write_checksum=True)
    alias_count = 0
    with sqlite3.connect(target) as conn:
        reset_romanizations(conn)
        conn.execute('ALTER TABLE entries ADD COLUMN romanizations TEXT')
        if indexed:
            conn.execute('''CREATE TABLE romanized_lookup (
                key TEXT NOT NULL, entry_id INTEGER NOT NULL, kind INTEGER NOT NULL,
                PRIMARY KEY (key, entry_id, kind)) WITHOUT ROWID''')
        for i, (record, (heads, forms, _)) in enumerate(zip(entries, extracted)):
            conn.execute('UPDATE entries SET romanizations=? WHERE id=?',
                         (encode_entry_json(heads, compressor), i))
            if mode == 'all_forms' and forms:
                details = copy.deepcopy(record.get('formDetails', []))
                for detail in details:
                    if detail['form'] in forms:
                        detail['romanizations'] = forms[detail['form']]
                conn.execute('UPDATE entries SET form_details=? WHERE id=?',
                             (encode_entry_json(details, compressor), i))
            if indexed:
                aliases = {(index_key(r), i, 0) for r in heads}
                if mode == 'all_forms':
                    aliases.update((index_key(r), i, 1) for values in forms.values() for r in values)
                conn.executemany('INSERT OR IGNORE INTO romanized_lookup VALUES (?,?,?)', sorted(aliases))
        if indexed:
            alias_count = conn.execute('SELECT COUNT(*) FROM romanized_lookup').fetchone()[0]
        conn.commit()
        compact = str(target) + '.compact'
        conn.execute('VACUUM INTO ?', (compact,))
    Path(compact).replace(target)
    with sqlite3.connect(target) as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        for i, (record, (heads, forms, _)) in enumerate(zip(entries, extracted)):
            head_data, form_data = conn.execute('SELECT romanizations, form_details FROM entries WHERE id=?', (i,)).fetchone()
            assert (decode_entry_json(head_data) if head_data is not None else []) == heads
            if mode == 'all_forms' and forms:
                stored = {d['form']: d.get('romanizations') for d in decode_entry_json(form_data)}
                assert all(stored.get(form) == values for form, values in forms.items())
    return sizes(target) | {'index_rows': alias_count}


def benchmark(lang, cache, count, seed, destination):
    version = source_data_version(lang)
    source = cache / version / f'en-{lang}-filtered.jsonl.zst'
    raw_entries, population = sample_source(source, count, seed)
    rows = []
    for raw in raw_entries:
        entry = msgspec.json.decode(msgspec.json.encode(raw), type=Entry)
        record = process_dict_entry(CONFIGS[lang], entry)
        if record is not None:
            rows.append((record, readings(raw, record), bool(any(s.get('form_of') for s in raw.get('senses', [])))))
    frequency = lang in available_languages()
    for record, _, _ in rows:
        record['freq'] = round(zipf_frequency(record['word'], lang), 2) if frequency else 0.0
    rows.sort(key=lambda row: -row[0]['freq'])
    records = [r for r, _, _ in rows]
    extracted = [r for _, r, _ in rows]
    result = {
        'source_version': version, 'eligible_source_entries': population,
        'sampled_source_entries': len(raw_entries), 'accepted_entries': len(rows),
        'entries_with_head_readings': sum(bool(h) for h, _, _ in extracted),
        'standalone_form_entries': sum(f for _, _, f in rows),
        'standalone_form_entries_with_head_readings': sum(f and bool(r[0]) for _, r, f in rows),
        'head_readings': sum(len(h) for h, _, _ in extracted),
        'forms_with_readings': sum(len(f) for _, f, _ in extracted),
        'form_readings': sum(sum(map(len, f.values())) for _, f, _ in extracted),
        'unmatched_or_ambiguous_form_readings': sum(n for _, _, n in extracted),
    }
    with tempfile.TemporaryDirectory(dir=destination) as directory:
        directory = Path(directory)
        baseline = directory / 'baseline.sqlite'
        write_sqlite_database(records, lang, CONFIGS[lang].phonetic_fn, str(baseline))
        production = sizes(baseline)
        with sqlite3.connect(baseline) as conn:
            production['index_rows'] = conn.execute('SELECT COUNT(*) FROM romanized_lookup').fetchone()[0]
        baseline.unlink()
        # Build the original schema directly, avoiding DROP COLUMN/VACUUM layout
        # changes in the baseline that could skew whole-file compression.
        with patch('pipeline.sqlite_output.PROFILES', {}):
            write_sqlite_database(records, lang, CONFIGS[lang].phonetic_fn, str(baseline))
        result['variants'] = {'baseline': sizes(baseline), 'production_headwords': production}
        for mode in ('headwords', 'all_forms'):
            for indexed in (False, True):
                name = mode + ('_indexed' if indexed else '_display')
                target = directory / (name + '.sqlite')
                result['variants'][name] = variant(baseline, target, records, extracted, mode, indexed)
                target.unlink()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', default=['ru', 'uk', 'ka', 'hi', 'ko', 'he'])
    parser.add_argument('--sample-size', type=int, default=5000)
    parser.add_argument('--seed', type=int, default=260915)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = {'sample_size': args.sample_size, 'seed': args.seed, 'download_zstd_level': 9,
              'row_zstd_level': ROW_COMPRESSION_LEVEL, 'languages': {}}
    for lang in args.languages:
        result['languages'][lang] = benchmark(lang, args.cache_dir, args.sample_size, args.seed, args.output_dir)
        (args.output_dir / 'sizes.json').write_text(json.dumps(result, indent=2) + '\n')
        print(lang, json.dumps(result['languages'][lang]), flush=True)


if __name__ == '__main__':
    main()
