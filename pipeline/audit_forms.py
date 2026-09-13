"""Reviewable forms regression inventory.

Run ``python -m pipeline.audit_forms --check`` in CI. After reviewing a source or
normalization change, use ``--update`` to deliberately replace the fixture
baseline. Counts are source-record form occurrences, before generator dedup.
The fixture inventory is a regression check, not linguistic certification.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import msgspec

from .dictionary import DICT_CONFIGS, process_dict_entry
from .form_quality import FormDiagnostics
from .wiktionary import Entry

FIXTURES = Path(__file__).parent / 'tests' / 'fixtures'
BASELINE = FIXTURES / 'forms_quality_baseline.json'
SOURCES = ('forms_quality_audit.jsonl', 'dictionary_expansion_quality.jsonl',
           'dictionary_el_apantao.jsonl', 'dictionary_az_flag.jsonl')


def inventory():
    configs = {c.code: c for c in DICT_CONFIGS}
    audit = FormDiagnostics()
    counts = Counter()
    distributions = Counter()
    digest = hashlib.sha256()
    for name in SOURCES:
        for line in (FIXTURES / name).read_bytes().splitlines():
            entry = msgspec.json.decode(line, type=Entry)
            record = process_dict_entry(configs[entry.lang_code], entry, audit)
            if record is None:
                continue
            forms = record.get('forms', [])
            counts[entry.lang_code] += len(forms)
            bucket = '0' if not forms else '1–10' if len(forms) <= 10 else '11–100' if len(forms) <= 100 else '101–1000' if len(forms) <= 1000 else '1001+'
            distributions[f'{entry.lang_code}:{bucket}'] += 1
            # Also catches changed spelling, grammar, qualifier scope and kind,
            # even when counts remain identical.
            digest.update(json.dumps([entry.lang_code, entry.word, entry.pos,
                                      forms, record.get('formDetails', [])],
                                     ensure_ascii=False, sort_keys=True).encode())
    return {'form_occurrences': dict(sorted(counts.items())),
            'forms_per_entry': dict(sorted(distributions.items())),
            'diagnostics': dict(sorted(audit.counts.items())),
            'samples': dict(sorted(audit.samples.items())),
            'output_sha256': digest.hexdigest()}


def scan_source(config, source_root, output, baseline_repo=None):
    """Full pinned-source omission/repair inventory; no downloads or mutations."""
    from .cache import CacheManager, source_data_version
    baseline = None
    if baseline_repo:
        import importlib.util
        import sys
        root = Path(baseline_repo) / 'pipeline'
        spec = importlib.util.spec_from_file_location('_forms_baseline', root / '__init__.py',
                                                       submodule_search_locations=[str(root)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package
        spec.loader.exec_module(package)
        baseline = __import__('_forms_baseline.dictionary', fromlist=['process_dict_entry'])
        baseline_entry = __import__('_forms_baseline.wiktionary', fromlist=['Entry']).Entry
    counts, distribution = Counter(), Counter()
    audit = FormDiagnostics()
    differences = {'removed': [], 'added': []}
    source = Path(source_root) / source_data_version(config.code) / f'en-{config.code}-filtered.jsonl.zst'
    for line in CacheManager()._stream_zstd_lines(str(source)):
        counts['source_lines'] += 1
        try:
            entry = msgspec.json.decode(line, type=Entry)
        except msgspec.ValidationError:
            continue
        if not entry.forms:
            continue
        record = process_dict_entry(config, entry, audit)
        forms = record.get('forms', []) if record else []
        if forms:
            counts['records_with_forms'] += 1
            counts['forms'] += len(forms)
            distribution['1–10' if len(forms) <= 10 else '11–100' if len(forms) <= 100 else '101–1000' if len(forms) <= 1000 else '1001+'] += 1
            for detail in record['formDetails']:
                counts['readings'] += len(detail.get('readings', []))
                counts['unlabelled'] += not detail.get('readings')
        if baseline:
            before = baseline.process_dict_entry(config, msgspec.json.decode(line, type=baseline_entry))
            old = set(before.get('forms', [])) if before else set()
            new = set(forms)
            counts['baseline_forms'] += len(old)
            for key, values in [('removed', old - new), ('added', new - old)]:
                counts[key] += len(values)
                for value in sorted(values):
                    if len(differences[key]) < 80 and not any(s['form'] == value for s in differences[key]):
                        differences[key].append({'word': entry.word, 'form': value})
    result = {'lang': config.code, 'source_version': source_data_version(config.code),
              'counts': dict(counts), 'forms_per_entry': dict(distribution),
              'diagnostics': dict(sorted(audit.counts.items())), 'samples': audit.samples,
              'differences': differences}
    Path(output).mkdir(parents=True, exist_ok=True)
    (Path(output) / f'{config.code}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return {'lang': config.code, 'counts': dict(counts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true')
    group.add_argument('--update', action='store_true')
    parser.add_argument('--source-root', type=Path, help='Cached pinned source directory for a full scan')
    parser.add_argument('--output', type=Path, default=Path('output/forms-quality'))
    parser.add_argument('--baseline-repo', type=Path, help='Checkout to compare source-record omissions against')
    parser.add_argument('--workers', type=int, default=1, choices=range(1, 9))
    parser.add_argument('--languages', nargs='+', help='Language codes; defaults to all 45')
    args = parser.parse_args()
    if args.source_root:
        configs = [c for c in DICT_CONFIGS if not args.languages or c.code in args.languages]
        if args.languages and set(args.languages) - {c.code for c in DICT_CONFIGS}:
            parser.error('Unknown language code')
        if args.workers == 1:
            for config in configs:
                print(json.dumps(scan_source(config, args.source_root, args.output, args.baseline_repo)), flush=True)
        else:
            from concurrent.futures import ProcessPoolExecutor, as_completed
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(scan_source, c, args.source_root, args.output, args.baseline_repo) for c in configs]
                for future in as_completed(futures):
                    print(json.dumps(future.result()), flush=True)
        return
    result = inventory()
    if args.check:
        if result != json.loads(BASELINE.read_text()):
            raise SystemExit('Forms inventory changed. Review spellings, readings, omission reasons and unknown tags before updating the baseline.')
        print('Reviewed forms inventory matches baseline.')
    elif args.update:
        BASELINE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
