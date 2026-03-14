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

from data_processing import DE_CONFIG, EL_CONFIG, ES_CONFIG, FR_CONFIG, IT_CONFIG, Entry, LanguageConfig, process_entry

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")

CONFIGS: dict[str, LanguageConfig] = {
    "fr": FR_CONFIG,
    "el": EL_CONFIG,
    "de": DE_CONFIG,
    "es": ES_CONFIG,
    "it": IT_CONFIG,
}

FIXTURE_VERBS = {
    "fr": ["être", "avoir", "aller", "manger", "finir"],
    "el": ["έχω", "είμαι", "κάνω", "θέλω", "λέω", "ευχαριστώ", "απαντάω"],
    "de": ["haben", "sein", "machen", "gehen", "können"],
    "es": ["hablar", "ser", "tener", "ir", "hacer"],
    "it": ["parlare", "essere", "avere", "fare", "andare"],
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


@pytest.mark.parametrize(
    "verb,tense_idx,person_idx,expected_fragment",
    [
        # Future simple active (idx 8) — θα + dependent stem
        ("λέω", 8, 0, "θα πω"),
        ("θέλω", 8, 0, "θα θελήσω"),
        ("κάνω", 8, 0, "θα κάνω"),
        # Future simple passive (idx 9)
        ("λέω", 9, 0, "θα ειπωθώ"),
        # Subjunctive active (idx 10) — bare dependent stem
        ("λέω", 10, 0, "πω"),
        ("θέλω", 10, 0, "θελήσω"),
        # Subjunctive passive (idx 11)
        ("λέω", 11, 0, "ειπωθώ"),
        # Aorist active (idx 4) — already works, sanity check
        ("λέω", 4, 0, "είπα"),
    ],
)
def test_greek_form_spot_checks(verb, tense_idx, person_idx, expected_fragment):
    """Spot-check that specific Greek forms appear at the expected tense positions."""
    entries = load_fixture_entries("el")
    if verb not in entries:
        pytest.skip(f"Verb '{verb}' not found in el fixtures")
    result = process_entry(EL_CONFIG, entries[verb])
    assert result is not None, f"process_entry returned None for {verb}"
    form = result["conjugation"][tense_idx][person_idx]
    assert expected_fragment in form, (
        f"Expected '{expected_fragment}' in form at tense {tense_idx}, person {person_idx} "
        f"for {verb}, got: '{form}'"
    )


@pytest.mark.parametrize(
    "verb,tense_idx,person_idx,expected_fragment",
    [
        # Present indicative (idx 4)
        ("parlare", 4, 0, "pàrlo"),
        ("essere", 4, 0, "sóno"),
        ("avere", 4, 0, "hò"),
        ("fare", 4, 0, "fàccio"),
        ("andare", 4, 0, "vàdo"),
        # Passato remoto (idx 6)
        ("parlare", 6, 0, "parlài"),
        ("essere", 6, 0, "fùi"),
        # Future (idx 7)
        ("andare", 7, 0, "andrò"),
        # Conditional (idx 12)
        ("parlare", 12, 0, "parlerèi"),
        # Present subjunctive (idx 14)
        ("parlare", 14, 0, "pàrli"),
        # Imperative (idx 18) — 2sg
        ("parlare", 18, 0, "pàrla"),
        ("andare", 18, 0, "vài"),
    ],
)
def test_italian_form_spot_checks(verb, tense_idx, person_idx, expected_fragment):
    """Spot-check that specific Italian forms appear at the expected tense positions."""
    entries = load_fixture_entries("it")
    if verb not in entries:
        pytest.skip(f"Verb '{verb}' not found in it fixtures")
    result = process_entry(IT_CONFIG, entries[verb])
    assert result is not None, f"process_entry returned None for {verb}"
    form = result["conjugation"][tense_idx]
    if isinstance(form, (list, tuple)):
        form = form[person_idx]
    assert expected_fragment in form, (
        f"Expected '{expected_fragment}' in form at tense {tense_idx}, person {person_idx} "
        f"for {verb}, got: '{form}'"
    )


@pytest.mark.parametrize(
    "verb,tense_idx,person_idx,must_contain,must_not_contain",
    [
        # ευχαριστώ: present passive 1sg — both variants, no superscript, no ` - `
        ("ευχαριστώ", 1, 0, ["ευχαριστιέμαι", "ευχαριστούμαι"], ["¹", " - "]),
        # ευχαριστώ: future continuous passive 1sg — both variants get θα prefix
        ("ευχαριστώ", 7, 0, ["θα ευχαριστιέμαι", "θα ευχαριστούμαι"], [" - "]),
        # ευχαριστώ: imperfect passive 3sg — no ` - `, no superscript
        ("ευχαριστώ", 3, 2, ["ευχαριστιόταν"], ["¹", "—", " - "]),
        # απαντάω: present passive 1sg — both variants, no ` - `
        ("απαντάω", 1, 0, ["απαντιέμαι", "απαντώμαι"], [" - "]),
        # απαντάω: imperfect passive 1sg — em dash variant discarded
        ("απαντάω", 3, 0, ["απαντιόμουν"], ["—", " - "]),
        # απαντάω: imperfect passive 3sg — no em dash, no ` - `
        ("απαντάω", 3, 2, ["απαντιόταν"], ["—", " - "]),
    ],
)
def test_greek_variant_form_spot_checks(
    verb, tense_idx, person_idx, must_contain, must_not_contain
):
    """Spot-check that Greek variant forms are properly split and cleaned."""
    entries = load_fixture_entries("el")
    if verb not in entries:
        pytest.skip(f"Verb '{verb}' not found in el fixtures")
    result = process_entry(EL_CONFIG, entries[verb])
    assert result is not None, f"process_entry returned None for {verb}"
    form = result["conjugation"][tense_idx][person_idx]
    for fragment in must_contain:
        assert fragment in form, (
            f"Expected '{fragment}' in form at tense {tense_idx}, person {person_idx} "
            f"for {verb}, got: '{form}'"
        )
    for fragment in must_not_contain:
        assert fragment not in form, (
            f"Did not expect '{fragment}' in form at tense {tense_idx}, person {person_idx} "
            f"for {verb}, got: '{form}'"
        )


def test_check_manifest_metadata():
    """Verify that check_manifest_metadata passes with the current committed manifest."""
    from data_processing import check_manifest_metadata

    assert check_manifest_metadata(), (
        "Manifest metadata doesn't match current LanguageConfig definitions. "
        "Re-run the data pipeline to regenerate."
    )
