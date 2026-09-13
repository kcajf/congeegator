"""Audit conjugation coverage and generated artifacts; reports stay outside the repo."""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import re

import msgspec
import zstandard

from .cache import SOURCE_DATA_VERSION, SOURCE_DATA_VERSIONS
from .conjugation import CONFIG, FormMatcher, entry_is_clean_verb_root, extract_conjugation
from .search import build_search_index
from .wiktionary import Entry

DIRTY = re.compile(r'\{\{|\}\}|\[\[|\]\]|Template:|Module:|<[^>]+>|\b(?:Lua|Script) error\b|\ufffd|[\x00-\x08\x0b\x0c\x0e-\x1f]')


def cells(record):
    # Structural validation reports malformed rows. Do not crash while also
    # checking their remaining valid cells for dirt and empty tables.
    rows = record.get('conjugation')
    if not isinstance(rows, (list, tuple)):
        return
    for row in rows:
        if isinstance(row, str):
            yield row
        elif isinstance(row, (list, tuple)):
            yield from (cell for cell in row if isinstance(cell, str))


def validate_records(records, config):
    errors = []
    seen = set()
    for record in records:
        name = record['name']
        if name in seen:
            errors.append(f'{name}: duplicate root')
        seen.add(name)
        rows = record['conjugation']
        if not isinstance(rows, (list, tuple)) or len(rows) != len(config.tenses):
            errors.append(f'{name}: wrong tense count')
            continue
        for row, tense in zip(rows, config.tenses):
            if isinstance(tense.form_matchers, FormMatcher):
                valid = isinstance(row, str)
            else:
                valid = isinstance(row, (list, tuple)) and len(row) == len(tense.form_matchers) and all(isinstance(c, str) for c in row)
            if not valid:
                errors.append(f'{name}: wrong row shape for {tense.name}')
        if not any(cells(record)):
            errors.append(f'{name}: empty table')
        if any(DIRTY.search(c) for c in cells(record) if isinstance(c, str)):
            errors.append(f'{name}: dirty cell')
        frequency = record.get('freq', 0)
        if not isinstance(frequency, (float, int)) or not math.isfinite(frequency) or not 0 <= frequency <= 8:
            errors.append(f'{name}: invalid frequency')
    return errors


def audit_language(config, cache_root, sample_count=12):
    version = SOURCE_DATA_VERSIONS.get(config.code, SOURCE_DATA_VERSION)
    path = cache_root / version / f'en-{config.code}-filtered.jsonl.zst'
    counts = Counter()
    tense_filled = Counter()
    source_error_tags = Counter()
    selected = {}
    rejected = []
    duplicate_examples = []
    with path.open('rb') as source:
        with io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(source)) as lines:
            for line in lines:
                raw = msgspec.json.decode(line)
                counts['source_records'] += 1
                if raw.get('pos') != 'verb':
                    continue
                counts['verb_records'] += 1
                entry = msgspec.convert(raw, type=Entry)
                has_table = any(f.source == 'conjugation' for f in entry.forms)
                counts['records_with_tables'] += has_table
                source_error_tags.update(tag for f in entry.forms if f.source == 'conjugation' for tag in f.tags if tag.startswith('error-'))
                if not entry_is_clean_verb_root(entry):
                    continue
                counts['clean_root_records'] += 1
                record = extract_conjugation(config, entry)
                if record is None:
                    if has_table:
                        counts['table_roots_with_no_usable_cells'] += 1
                        if len(rejected) < 30:
                            rejected.append(entry.word)
                    continue
                if entry.word in selected:
                    counts['duplicate_root_records'] += 1
                    if selected[entry.word]['conjugation'] != record['conjugation']:
                        counts['different_duplicate_tables'] += 1
                        if len(duplicate_examples) < 20:
                            duplicate_examples.append(entry.word)
                    continue
                selected[entry.word] = record
                for tense, row in zip(config.tenses, record['conjugation']):
                    tense_filled[tense.name] += sum(bool(c) for c in ([row] if isinstance(row, str) else row))
    records = list(selected.values())
    counts['released_roots'] = len(records)
    counts['filled_cells'] = sum(bool(c) for r in records for c in cells(r))
    counts['total_cells'] = sum(1 for r in records for _ in cells(r))
    by_hash = sorted(records, key=lambda r: hashlib.sha256(r['name'].encode()).hexdigest())
    sparse = sorted(records, key=lambda r: sum(bool(c) for c in cells(r)))
    variants = sorted(records, key=lambda r: max((c.count('/') + 1 for c in cells(r) if c), default=0), reverse=True)
    return {
        'code': config.code, 'source_version': version, 'counts': dict(counts),
        'source_error_tags': dict(source_error_tags), 'filled_cells_by_tense': dict(tense_filled),
        'rejected_table_examples': rejected, 'different_duplicate_examples': duplicate_examples,
        'validation_errors': validate_records(records, config),
        'deterministic_samples': by_hash[:sample_count], 'sparse_samples': sparse[:sample_count],
        'variant_heavy_samples': variants[:sample_count],
    }, selected


def validate_artifact(data_path, metadata, config, expected):
    raw = data_path.read_bytes()
    data = json.loads(raw)
    errors = validate_records(data['verbs'], config)
    if len(raw) != metadata['dataSize'] or hashlib.md5(raw).hexdigest()[:8] != metadata['dataHash']:
        errors.append('manifest hash/size mismatch')
    actual = {r['name']: {k: v for k, v in r.items() if k != 'freq'} for r in data['verbs']}
    # JSON normalizes row tuples to lists.
    normalized_expected = json.loads(json.dumps(expected))
    if actual != normalized_expected:
        errors.append('generated records differ from reviewed source extraction')
    index = data.get('searchIndex')
    if not isinstance(index, dict):
        errors.append('invalid search index object')
    else:
        for prefix, ids in index.items():
            if not isinstance(prefix, str) or not prefix or not isinstance(ids, list) or len(ids) > 200 or any(type(i) is not int or i < 0 or i >= len(data['verbs']) for i in ids):
                errors.append(f'invalid search index bucket {prefix!r}')
        # Range checks alone accept an empty or silently truncated index.
        # Rebuild with the production language/phonetic settings and actual
        # frequencies, which determine the capped-bucket priority ordering.
        if not validate_records(data['verbs'], config):
            rebuilt = build_search_index(data['verbs'], phonetic_fn=config.phonetic_fn, lang=config.code)
            if index != rebuilt:
                errors.append('search index differs from rebuilt bundle index')
    directory = data_path.parent
    if json.loads((directory / 'index.json').read_text()) != [r['name'] for r in data['verbs']]:
        errors.append('word index differs from bundle')
    chunk_records = {}
    for path in (directory / 'chunks').glob('*.json'):
        chunk_records.update(json.loads(path.read_text()))
    if chunk_records != {r['name'].lower(): r for r in data['verbs']}:
        errors.append('SSR chunks differ from bundle')
    return {'records': len(data['verbs']), 'bytes': len(raw), 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--languages', nargs='+', required=True)
    parser.add_argument('--cache-root', type=Path, default=Path('cache'))
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--manifest', type=Path, default=Path('apps/congeegator/src/lib/data-manifest.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    configs = {c.code: c for c in CONFIG}
    unknown = set(args.languages) - configs.keys()
    if unknown:
        parser.error(f'Unconfigured languages: {sorted(unknown)}')
    manifest = json.loads(args.manifest.read_text())['languages'] if args.data_dir else {}
    results = []
    for code in args.languages:
        result, records = audit_language(configs[code], args.cache_root)
        if args.data_dir:
            metadata = manifest[code]
            path = args.data_dir / f"{code}-{metadata['dataHash']}" / 'data.json'
            result['artifact'] = validate_artifact(path, metadata, configs[code], records)
        results.append(result)
        print(code, json.dumps(result['counts']), flush=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + '\n')
    if any(r['validation_errors'] or r.get('artifact', {}).get('errors') for r in results):
        raise SystemExit('Conjugation audit failed; inspect the output')


if __name__ == '__main__':
    main()
