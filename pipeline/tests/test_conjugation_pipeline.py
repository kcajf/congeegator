import hashlib
import json

import msgspec
import pytest

from pipeline import generate
from pipeline.audit_conjugation import validate_records, validate_artifact
from pipeline.conjugation import LanguageConfig, TenseConfig, FormMatcher, extract_conjugation
from pipeline.output import write_language_data
from pipeline.search import build_search_index
from pipeline.wiktionary import Entry, Form


def config(code='la'):
    return LanguageConfig(code, 'Test', 'Test', (TenseConfig('present', FormMatcher(('present',))),), [])


def test_empty_conjugation_table_is_not_released():
    value = Entry('verb', 'la', 'Latin', 'amo', forms=(Form('amare', {'infinitive'}, 'conjugation'),))
    assert extract_conjugation(config(), value) is None


def test_conjugation_without_frequency_corpus_is_neutral(monkeypatch):
    class Cache:
        def get_lang_filtered_raw_data(self, *args):
            return iter([msgspec.json.encode(Entry('verb', 'la', 'Latin', 'amo', forms=(Form('amo', {'present'}, 'conjugation'),)))])
    monkeypatch.setattr(generate, 'CacheManager', Cache)
    monkeypatch.setattr(generate, 'available_languages', lambda: {})
    def unsupported(*args, **kwargs):
        raise AssertionError('Do not substitute another language corpus')
    monkeypatch.setattr(generate, 'zipf_frequency', unsupported)
    data, dictionary = generate.generate_data_for_lang('en', config(), None, False)
    assert data['verbs'][0]['freq'] == 0
    assert dictionary is None


def test_missing_conjugation_language_fails(monkeypatch):
    monkeypatch.setattr(generate, 'generate_data_for_lang', lambda *a, **kw: (None, None))
    with pytest.raises(RuntimeError, match='No conjugation entries generated'):
        list(generate.iter_language_data(False, 'congeegator'))


def test_congeegator_generation_preserves_dictionary_output(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sentinel = tmp_path / 'apps/lexicoff/r2_data/data/v1/existing.sqlite'
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b'original dictionary')
    monkeypatch.setattr(generate, 'CONFIG', [config()])
    monkeypatch.setattr(generate, 'iter_language_data', lambda dev, app: iter([
        ('la', {'verbs': [{'name': 'amo', 'nameNoDiacritics': 'amo', 'conjugation': ['amo'], 'freq': 0}], 'searchIndex': {'amo': [0]}}, None)
    ]))
    monkeypatch.setattr('sys.argv', ['generate', '--app', 'congeegator'])
    generate.main()
    assert sentinel.read_bytes() == b'original dictionary'
    assert not (tmp_path / 'apps/lexicoff/src/lib/data-manifest.json').exists()
    assert (tmp_path / 'apps/congeegator/src/lib/data-manifest.json').exists()


def test_auditor_rejects_dirty_empty_duplicate_and_bad_frequency_records():
    rows = [
        {'name': 'amo', 'conjugation': ['{{bad}}'], 'freq': float('nan')},
        {'name': 'amo', 'conjugation': ['']},
        {'name': 'wrong', 'conjugation': []},
    ]
    errors = validate_records(rows, config())
    assert any('dirty cell' in e for e in errors)
    assert any('empty table' in e for e in errors)
    assert any('duplicate root' in e for e in errors)
    assert any('invalid frequency' in e for e in errors)
    assert any('wrong tense count' in e for e in errors)


@pytest.mark.parametrize('row', [None, 42, {'bad': 'shape'}, ['amo', None]])
def test_auditor_reports_malformed_rows_without_crashing(row):
    errors = validate_records([{'name': 'amo', 'conjugation': [row]}], config())
    assert any('wrong row shape' in error for error in errors)


def test_auditor_reports_nonsequence_conjugation_without_crashing():
    assert any('wrong tense count' in error for error in
               validate_records([{'name': 'amo', 'conjugation': None}], config()))


def test_artifact_audit_reconciles_bundle_chunks_source_and_hash(tmp_path):
    record = {'name': 'amo', 'nameNoDiacritics': 'amo', 'conjugation': ['amo'], 'freq': 0}
    data = {'verbs': [record], 'searchIndex': build_search_index([record], lang='la')}
    write_language_data(data, str(tmp_path))
    path = tmp_path / 'data.json'
    metadata = {'dataSize': path.stat().st_size, 'dataHash': hashlib.md5(path.read_bytes()).hexdigest()[:8]}
    expected = {'amo': {k: v for k, v in record.items() if k != 'freq'}}
    assert not validate_artifact(path, metadata, config(), expected)['errors']
    (tmp_path / 'chunks/a.json').write_text('{}')
    assert 'SSR chunks differ from bundle' in validate_artifact(path, metadata, config(), expected)['errors']
    data['searchIndex']['amo'] = [9]
    path.write_text(json.dumps(data))
    errors = validate_artifact(path, metadata, config(), expected)['errors']
    assert 'manifest hash/size mismatch' in errors
    assert any('invalid search index bucket' in e for e in errors)


def test_artifact_audit_rejects_empty_search_index_even_with_correct_hash(tmp_path):
    record = {'name': 'amo', 'nameNoDiacritics': 'amo', 'conjugation': ['amo'], 'freq': 0}
    write_language_data({'verbs': [record], 'searchIndex': {}}, str(tmp_path))
    path = tmp_path / 'data.json'
    metadata = {'dataSize': path.stat().st_size, 'dataHash': hashlib.md5(path.read_bytes()).hexdigest()[:8]}
    expected = {'amo': {k: v for k, v in record.items() if k != 'freq'}}
    errors = validate_artifact(path, metadata, config(), expected)['errors']
    assert errors == ['search index differs from rebuilt bundle index']
