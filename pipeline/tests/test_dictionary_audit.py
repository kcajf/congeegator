import json

from pipeline.audit_dictionary import audit_source, audit_sqlite, read_source
from pipeline.dictionary import DictLanguageConfig
from pipeline.sqlite_output import write_sqlite_database


CONFIG = DictLanguageConfig(code="pt", name="português", english_wiktionary_name="Portuguese")


def _line(word, senses, **extra):
    return json.dumps({"word": word, "lang": "Portuguese", "lang_code": "pt", "pos": "noun", "senses": senses, **extra}).encode()


def test_audit_distinguishes_headwords_records_and_legitimate_forms():
    lines = [
        _line("casa", [{"glosses": ["house"]}]),
        _line("casa", [{"glosses": ["home"]}]),
        _line("casas", [{"glosses": ["plural of casa"], "form_of": [{"word": "casa"}], "tags": ["form-of"]}]),
    ]
    result = audit_source(lines, CONFIG)
    assert result["counts"]["records"] == 3
    assert result["counts"]["unique_headwords"] == 2
    assert result["counts"]["form_only_records"] == 1
    assert result["counts"]["repeated_word_pos_pairs"] == 1
    assert result["review_flags"] == {}
    assert len(result["common_words"]["casa"]) == 2


def test_audit_reports_dirty_text_and_duplicates_without_conflating_etymologies(monkeypatch):
    # Simulate a regression in the importer so the audit catches residual dirt.
    monkeypatch.setattr("pipeline.audit_dictionary.process_dict_entry", lambda config, entry: {
        "word": entry.word, "pos": entry.pos,
        "senses": [{"gloss": sense.glosses[-1]} for sense in entry.senses],
    })
    dirty = _line("casa", [{"glosses": ["{{broken}} <ref>citation</ref> Lua error \ufffd\u0000"]}])
    clean = _line("casa", [{"glosses": ["a different etymology; x < y"]}])
    result = audit_source([dirty, dirty, clean], CONFIG)
    assert result["review_flags"]["identical_record"] == 1
    for flag in ("wiki_markup", "html_markup", "extraction_error", "replacement_character", "control_character"):
        assert result["review_flags"][flag] == 2


def test_audit_handles_redirect_invalid_and_wrong_language_records():
    result = audit_source([
        b'{"pos":"hard-redirect"}', b"not json",
        _line("home", [{"glosses": ["house"]}], lang_code="en"),
        _line("casa", [{"glosses": ["house"]}]),
    ], CONFIG)
    assert result["counts"]["source_records"] == 4
    assert result["counts"]["records"] == 1
    assert result["review_flags"]["invalid_source_record"] == 1
    assert result["review_flags"]["wrong_language"] == 1


def test_samples_are_reproducible_across_source_order():
    lines = [_line(f"word{i}", [{"glosses": [str(i)]}]) for i in range(100)]
    forward = audit_source(lines, CONFIG, sample_size=5)
    reverse = audit_source(reversed(lines), CONFIG, sample_size=5)
    assert forward["random_samples"] == reverse["random_samples"]


def test_thesaurus_only_records_are_accounted_for_separately():
    result = audit_source([
        b'{"word":"bicha","source":"thesaurus","lang_code":"pt"}',
        _line("casa", [{"glosses": ["house"]}]),
    ], CONFIG)
    assert result["rejected_pos"] == {"thesaurus_without_pos": 1}
    assert result["review_flags"] == {}
    assert result["counts"]["source_records"] == 2


def test_sqlite_audit_checks_real_fts_and_source_counts(tmp_path):
    path = tmp_path / "pt.sqlite"
    entries = [{"word": "água", "pos": "noun", "senses": [{"gloss": "water"}], "freq": 5.0}]
    write_sqlite_database(entries, "pt", None, str(path))
    result = audit_sqlite(path, "pt", {"counts": {"records": 1, "unique_headwords": 1}})
    assert result["integrity_check"] == ["ok"]
    assert result["fts_integrity"] == {"entries_fts": "ok", "fuzzy": "ok"}
    assert result["fts_records"] == {"entries_fts": 1, "fuzzy": 1}
    assert result["source_counts_match"] is True
    assert result["invalid_frequency_records"] == 0
    assert next(p for p in result["search_probes"] if p["word"] == "água")["fts_matches_all_records"] is True


def test_read_source_preserves_unicode_and_final_unterminated_line(tmp_path):
    import zstandard

    lines = [_line("água", [{"glosses": ["water"]}]), _line("casa", [{"glosses": ["house"]}])]
    path = tmp_path / "pt.jsonl.zst"
    path.write_bytes(zstandard.ZstdCompressor().compress(b"\n".join(lines)))
    assert [line.rstrip(b"\n") for line in read_source(path)] == lines


def test_audit_tracks_linked_senses_and_structured_examples():
    result=audit_source([_line('casa',[{'glosses':['house'],'links':[['house','house']],
        'examples':[{'text':'a casa','translation':'the house','bold_text_offsets':[[2,6]]}]}],
        derived=[{'word':'casinha'}])],CONFIG)
    assert result['counts']['senses_with_links']==1
    assert result['counts']['translated_examples']==1
    assert result['counts']['emphasized_examples']==1
    assert result['counts']['records_with_derived']==1
    assert result['review_flags']=={}
