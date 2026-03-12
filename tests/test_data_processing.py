"""Golden tests for data_processing.process_entry().

Each test loads a raw Wiktionary JSONL fixture, runs process_entry(),
and compares output to a committed golden file. Use --update-golden
to regenerate golden files after intentional changes.
"""

import json
import os
import sys

import msgspec
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data_processing import DE_CONFIG, EL_CONFIG, FR_CONFIG, Entry, LanguageConfig, process_entry

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")

CONFIGS: dict[str, LanguageConfig] = {
    "fr": FR_CONFIG,
    "el": EL_CONFIG,
    "de": DE_CONFIG,
}

FIXTURE_VERBS = {
    "fr": ["être", "avoir", "aller", "manger", "finir"],
    "el": ["έχω", "είμαι", "κάνω", "θέλω", "λέω"],
    "de": ["haben", "sein", "machen", "gehen", "können"],
}


def load_fixture_entries(lang: str) -> dict[str, Entry]:
    """Load fixture JSONL file and return entries keyed by word."""
    path = os.path.join(FIXTURES_DIR, f"{lang}_verbs.jsonl")
    if not os.path.exists(path):
        pytest.skip(f"Fixture file not found: {path}. Run tests/extract_fixtures.py first.")
    entries = {}
    with open(path, "rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = msgspec.json.decode(line, type=Entry)
            entries[entry.word] = entry
    return entries


def normalize(obj):
    """Convert tuples to lists recursively for JSON-compatible comparison."""
    if isinstance(obj, (list, tuple)):
        return [normalize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    return obj


def golden_path(lang: str, verb: str) -> str:
    # Use a safe filename (replace / with _)
    safe_name = verb.replace("/", "_")
    return os.path.join(GOLDEN_DIR, f"{lang}_{safe_name}.json")


def _test_params():
    """Generate (lang, verb) pairs for parametrize."""
    params = []
    for lang, verbs in FIXTURE_VERBS.items():
        for verb in verbs:
            params.append((lang, verb))
    return params


@pytest.mark.parametrize("lang,verb", _test_params())
def test_golden(lang: str, verb: str, update_golden: bool):
    entries = load_fixture_entries(lang)
    if verb not in entries:
        pytest.skip(f"Verb '{verb}' not found in {lang} fixtures")

    config = CONFIGS[lang]
    result = process_entry(config, entries[verb])
    assert result is not None, f"process_entry returned None for {verb}"

    gpath = golden_path(lang, verb)

    if update_golden:
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        with open(gpath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
        pytest.skip(f"Updated golden file: {gpath}")

    if not os.path.exists(gpath):
        pytest.fail(
            f"Golden file not found: {gpath}\n"
            f"Run: pixi run pytest tests/ --update-golden"
        )

    with open(gpath, encoding="utf-8") as f:
        expected = json.load(f)

    assert normalize(result) == expected, (
        f"Output for {lang}/{verb} doesn't match golden file.\n"
        f"To update: pixi run pytest tests/ --update-golden"
    )


def test_check_manifest_metadata():
    """Verify that check_manifest_metadata passes with the current committed manifest."""
    from data_processing import check_manifest_metadata

    assert check_manifest_metadata(), (
        "Manifest metadata doesn't match current LanguageConfig definitions. "
        "Re-run the data pipeline to regenerate."
    )
