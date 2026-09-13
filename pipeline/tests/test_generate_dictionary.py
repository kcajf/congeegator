import msgspec
import pytest

from pipeline import generate
from pipeline.dictionary import DictLanguageConfig


def stub_source(monkeypatch, code, words):
    lines = [msgspec.json.encode({"word": word, "lang_code": code, "lang": "Test",
                                 "pos": "noun", "senses": [{"glosses": ["a house"]}]})
             for word in words]
    class Cache:
        def get_lang_filtered_raw_data(self, wiki_lang, lang):
            return iter(lines)
    monkeypatch.setattr(generate, "CacheManager", Cache)


def test_dictionary_without_frequency_corpus_still_generates(monkeypatch):
    config = DictLanguageConfig("eo", "Esperanto", "Esperanto")
    stub_source(monkeypatch, "eo", ["domo"])
    monkeypatch.setattr(generate, "available_languages", lambda: {"en": "unused"})
    def unsupported(*args, **kwargs):
        raise AssertionError("Must not use another language's frequencies")
    monkeypatch.setattr(generate, "zipf_frequency", unsupported)
    conjugation, dictionary = generate.generate_data_for_lang("en", None, config, False)
    assert conjugation is None
    assert dictionary["entries"][0]["freq"] == 0
    assert dictionary["entries"][0]["word"] == "domo"


def test_dictionary_only_dev_generation_stops_without_verbs(monkeypatch):
    config = DictLanguageConfig("eo", "Esperanto", "Esperanto")
    stub_source(monkeypatch, "eo", [f"word{i}" for i in range(150)])
    _, dictionary = generate.generate_data_for_lang("en", None, config, True)
    assert len(dictionary["entries"]) == 101


def test_thesaurus_supplements_without_pos_do_not_break_generation(monkeypatch):
    config = DictLanguageConfig("pt", "português", "Portuguese")
    class Cache:
        def get_lang_filtered_raw_data(self, *args):
            return iter([msgspec.json.encode({"word": "bicha", "lang": "Portuguese",
                         "lang_code": "pt", "source": "thesaurus", "senses": []})])
    monkeypatch.setattr(generate, "CacheManager", Cache)
    assert generate.generate_data_for_lang("en", None, config, False) == (None, None)


def test_missing_pos_in_ordinary_source_remains_an_error(monkeypatch):
    config = DictLanguageConfig("pt", "português", "Portuguese")
    class Cache:
        def get_lang_filtered_raw_data(self, *args):
            return iter([msgspec.json.encode({"word": "casa", "lang": "Portuguese",
                         "lang_code": "pt", "senses": []})])
    monkeypatch.setattr(generate, "CacheManager", Cache)
    with pytest.raises(msgspec.ValidationError, match="pos"):
        generate.generate_data_for_lang("en", None, config, False)


def test_identical_records_removed_but_distinct_meanings_retained(monkeypatch):
    config = DictLanguageConfig("eo", "Esperanto", "Esperanto")
    records = [{"word": "test", "lang": "Esperanto", "lang_code": "eo", "pos": "noun",
                "senses": [{"glosses": [gloss]}]} for gloss in ["one meaning", "one meaning", "another meaning"]]
    class Cache:
        def get_lang_filtered_raw_data(self, *args):
            return iter(map(msgspec.json.encode, records))
    monkeypatch.setattr(generate, "CacheManager", Cache)
    _, data = generate.generate_data_for_lang("en", None, config, False)
    assert [r["senses"][0]["gloss"] for r in data["entries"]] == ["one meaning", "another meaning"]


def test_lexicoff_selection_does_not_extract_conjugations(monkeypatch):
    calls = []
    def process(wiki_lang, conj_config, dict_config, dev):
        calls.append((conj_config, dict_config.code))
        return None, {"entries": []}
    monkeypatch.setattr(generate, "generate_data_for_lang", process)
    list(generate.iter_language_data(False, "lexicoff"))
    assert {code for _, code in calls} == {c.code for c in generate.DICT_CONFIGS}
    assert all(conj is None for conj, _ in calls)


def test_missing_language_output_fails_instead_of_silently_shrinking_catalogue(monkeypatch):
    monkeypatch.setattr(generate, "generate_data_for_lang", lambda *args, **kwargs: (None, None))
    with pytest.raises(RuntimeError, match="No dictionary entries generated"):
        list(generate.iter_language_data(False, "lexicoff"))


def test_lexicoff_generation_leaves_congeegator_files_untouched(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    sentinel = tmp_path / "apps/congeegator/r2_data/data/v1/existing.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("existing conjugation data")
    config = DictLanguageConfig("eo", "Esperanto", "Esperanto")
    monkeypatch.setattr(generate, "DICT_CONFIGS", [config])
    monkeypatch.setattr(generate, "iter_language_data", lambda dev, app: iter([
        ("eo", None, {"entries": [{"word": "domo", "pos": "noun",
                                   "senses": [{"gloss": "house"}], "freq": 0}]})
    ]))
    monkeypatch.setattr("sys.argv", ["generate", "--app", "lexicoff"])
    generate.main()
    assert sentinel.read_text() == "existing conjugation data"
    assert not (tmp_path / "apps/congeegator/src/lib/data-manifest.json").exists()
    assert (tmp_path / "apps/lexicoff/src/lib/data-manifest.json").exists()


def test_frequency_corpora_are_released_after_each_language(monkeypatch):
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def frequency_list(lang):
        return [[lang]]

    @lru_cache(maxsize=None)
    def frequency_dict(lang):
        return {frequency_list(lang)[0][0]: 1.0}

    def frequency(word, lang):
        frequency_dict(lang)
        return 4.5

    monkeypatch.setattr(generate, "get_frequency_list", frequency_list)
    monkeypatch.setattr(generate, "get_frequency_dict", frequency_dict)
    monkeypatch.setattr(generate, "zipf_frequency", frequency)
    monkeypatch.setattr(generate, "available_languages", lambda: {"pt": "unused", "nl": "unused"})
    for code in ("pt", "nl"):
        config = DictLanguageConfig(code, code, code)
        stub_source(monkeypatch, code, ["test"])
        _, result = generate.generate_data_for_lang("en", None, config, False)
        assert result["entries"][0]["freq"] == 4.5
        assert frequency_dict.cache_info().currsize == 0
        assert frequency_list.cache_info().currsize == 0


def test_frequency_corpora_are_released_when_generation_fails(monkeypatch):
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def corpus(lang):
        return {lang: 1}

    def failing_frequency(word, lang):
        corpus(lang)
        raise RuntimeError("frequency failure")

    monkeypatch.setattr(generate, "get_frequency_list", corpus)
    monkeypatch.setattr(generate, "get_frequency_dict", corpus)
    monkeypatch.setattr(generate, "zipf_frequency", failing_frequency)
    monkeypatch.setattr(generate, "available_languages", lambda: {"pt": "unused"})
    stub_source(monkeypatch, "pt", ["casa"])
    with pytest.raises(RuntimeError, match="frequency failure"):
        generate.generate_data_for_lang("en", None, DictLanguageConfig("pt", "pt", "Portuguese"), False)
    assert corpus.cache_info().currsize == 0


def test_dictionary_download_has_verified_checksum(tmp_path):
    import io
    import zstandard

    config = DictLanguageConfig("eo", "Esperanto", "Esperanto")
    generate.write_dictionary_language(
        [{"word": "domo", "pos": "noun", "senses": [{"gloss": "house"}], "freq": 0}],
        config, str(tmp_path),
    )
    payload = (tmp_path / "eo/eo.sqlite.zst").read_bytes()
    assert zstandard.get_frame_parameters(payload).has_checksum
    decoded = io.BytesIO()
    zstandard.ZstdDecompressor().copy_stream(io.BytesIO(payload), decoded)
    assert decoded.getvalue().startswith(b"SQLite format 3\0")
    corrupted = payload[:-1] + bytes([payload[-1] ^ 1])
    with pytest.raises(zstandard.ZstdError, match="checksum"):
        zstandard.ZstdDecompressor().copy_stream(io.BytesIO(corrupted), io.BytesIO())
