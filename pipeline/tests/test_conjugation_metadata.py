"""The added paradigms must be completely labelled and reachable in the UI."""
import json
from pathlib import Path

import pytest

from pipeline.conjugation import CONFIG, make_language_static_metadata

ADDED = {'pt', 'ca', 'nl', 'sv', 'la', 'fi'}
MESSAGES = Path(__file__).resolve().parents[2] / 'apps/congeegator/src/lib/messages'


@pytest.mark.parametrize('config', [c for c in CONFIG if c.code in ADDED], ids=lambda c: c.code)
def test_added_tenses_have_one_group_and_both_display_languages(config):
    metadata = make_language_static_metadata(config)
    grouped = [i for group in metadata['tenseGroups'] for i in group['tenseIndices']]
    assert sorted(grouped) == list(range(len(config.tenses))), 'Missing or duplicate display groups'
    keys = set(metadata['tenseNames']) | {g['name'] for g in metadata['tenseGroups']}
    for locale in ('en', config.code):
        messages = json.loads((MESSAGES / f'{locale}.json').read_text())
        assert not keys - messages.keys(), f'{locale}: missing tense labels'
        assert all(messages[k].strip() and messages[k] != k for k in keys)
