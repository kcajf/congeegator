"""Source pinning must preserve snapshots and include dictionary-only languages."""

import gzip
import hashlib
import io
from pathlib import Path
from unittest.mock import Mock

import msgspec
import pytest
import zstandard

from pipeline import cache, pin_source_data as pin
from pipeline.conjugation import CONFIG
from pipeline.dictionary import DICT_CONFIGS


def source_bytes():
    # Include an unrequested language, blanks, and a final unterminated line.
    return b'\n'.join(msgspec.json.encode(entry) for entry in [
        {"lang_code": "pt", "word": "casa"},
        {"lang_code": "fr", "word": "maison"},
        {"lang_code": "eo", "word": "domo"},
        {"lang_code": "pt", "word": "olá"},
    ])


def read_filtered(path):
    with path.open("rb") as source:
        with zstandard.ZstdDecompressor().stream_reader(source) as reader:
            return [msgspec.json.decode(line) for line in reader.read().splitlines()]


def test_language_catalogue():
    existing = {"en", "fr", "de", "el", "es", "it"}
    additions = {"pt", "ca", "ro", "gl", "nl", "sv", "da", "nb", "pl", "ru", "uk", "cs", "fi", "hu", "tr", "id", "vi", "eo", "la"}
    assert {c.code for c in CONFIG} == existing
    assert len(DICT_CONFIGS) == 25
    assert {c.code for c in DICT_CONFIGS} == existing | additions
    assert set(pin.configured_languages()) == existing | additions
    assert len(pin.configured_languages()) == 25


@pytest.mark.parametrize("compressed", [False, True])
def test_split_local_source_once(tmp_path, compressed):
    raw = gzip.compress(source_bytes()) if compressed else source_bytes()
    source = tmp_path / "source"
    source.write_bytes(raw)
    paths = {lang: str(tmp_path / f"{lang}.zst") for lang in ["pt", "eo"]}
    counts = pin._download_and_filter("en", paths, source, hashlib.sha256(raw).hexdigest())
    assert counts == {"pt": 2, "eo": 1}
    assert [entry["word"] for entry in read_filtered(Path(paths["pt"]))] == ["casa", "olá"]
    assert [entry["word"] for entry in read_filtered(Path(paths["eo"]))] == ["domo"]


def test_download_is_shared_by_languages(tmp_path, monkeypatch):
    raw = gzip.compress(source_bytes())
    response = Mock()
    response.headers = {"content-length": str(len(raw))}
    response.raw = io.BytesIO(raw)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    request = Mock(return_value=response)
    monkeypatch.setattr(pin.requests, "get", request)
    pin._download_and_filter("en", {lang: str(tmp_path / f"{lang}.zst") for lang in ["pt", "eo"]})
    assert request.call_count == 1
    response.raise_for_status.assert_called_once()
    assert response.raw.decode_content is True


@pytest.mark.parametrize("failure", ["missing", "malformed", "truncated", "checksum"])
def test_bad_source_does_not_replace_existing_files(tmp_path, failure):
    raw = source_bytes()
    languages = ["pt", "eo"]
    checksum = None
    if failure == "missing":
        languages.append("la")
    if failure == "malformed":
        raw += b'\n{"lang_code":'
    raw = gzip.compress(raw)
    if failure == "truncated":
        raw = raw[:-8]
    if failure == "checksum":
        checksum = "0" * 64
    source = tmp_path / "source"
    source.write_bytes(raw)
    output = tmp_path / "filtered"
    output.mkdir()
    paths = {lang: str(output / f"{lang}.zst") for lang in languages}
    for path in paths.values():
        Path(path).write_bytes(b"original")
    with pytest.raises((ValueError, EOFError, msgspec.DecodeError)):
        pin._download_and_filter("en", paths, source, checksum)
    assert set(output.iterdir()) == {Path(path) for path in paths.values()}
    assert all(Path(path).read_bytes() == b"original" for path in paths.values())


def test_partial_pin_preserves_existing_versions(tmp_path, monkeypatch):
    path = tmp_path / "cache.py"
    path.write_text('SOURCE_DATA_VERSION = "old"\nSOURCE_DATA_VERSIONS: dict[str, str] = {"pt": "earlier"}\n')
    monkeypatch.setattr(pin, "__file__", str(tmp_path / "pin_source_data.py"))
    pin._update_version_in_source("new", ["eo", "la"])
    namespace = {}
    exec(path.read_text(), namespace)
    assert namespace["SOURCE_DATA_VERSION"] == "old"
    assert namespace["SOURCE_DATA_VERSIONS"] == {"pt": "earlier", "eo": "new", "la": "new"}
    pin._update_version_in_source("refresh")
    exec(path.read_text(), namespace)
    assert namespace["SOURCE_DATA_VERSION"] == "refresh"
    assert namespace["SOURCE_DATA_VERSIONS"] == {}


def test_cache_selects_per_language_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "SOURCE_DATA_VERSION", "existing")
    monkeypatch.setattr(cache, "SOURCE_DATA_VERSIONS", {"pt": "added"})
    monkeypatch.setattr(cache.CacheManager, "CACHE_DIR", str(tmp_path))
    for version, lang in [("existing", "fr"), ("added", "pt")]:
        folder = tmp_path / version
        folder.mkdir()
        (folder / f"en-{lang}-filtered.jsonl.zst").write_bytes(zstandard.ZstdCompressor().compress(lang.encode() + b"\n"))
    manager = cache.CacheManager()
    assert list(manager.get_lang_filtered_raw_data("en", "fr")) == [b"fr"]
    assert list(manager.get_lang_filtered_raw_data("en", "pt")) == [b"pt"]


def test_local_only_cli_never_uploads_updates_or_regenerates(tmp_path, monkeypatch):
    source = tmp_path / "source.gz"
    source.write_bytes(gzip.compress(source_bytes()))
    output = tmp_path / "result"
    monkeypatch.setattr("sys.argv", ["pin", "--languages", "pt", "eo", "--input-file", str(source), "--output-dir", str(output), "--no-upload"])
    def forbidden(*args):
        pytest.fail("local review must not publish or change tracked source versions")
    monkeypatch.setattr(pin, "_upload_to_r2", forbidden)
    monkeypatch.setattr(pin, "_update_version_in_source", forbidden)
    monkeypatch.setattr(pin, "_run_pipeline", forbidden)
    pin.main()
    assert sorted(path.name for path in output.iterdir()) == ["en-eo-filtered.jsonl.zst", "en-pt-filtered.jsonl.zst"]


def test_upload_refuses_to_replace_different_remote_content(monkeypatch):
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(pin.subprocess, "run", run)
    pin._upload_to_r2("source.zst", "remote:bucket/source.zst")
    assert run.call_args.args[0] == ["rclone", "copyto", "--immutable", "source.zst", "remote:bucket/source.zst"]


def test_cache_fetches_selected_snapshot_and_cleans_up_interrupted_download(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "SOURCE_DATA_VERSIONS", {"pt": "added"})
    monkeypatch.setattr(cache.CacheManager, "CACHE_DIR", str(tmp_path))
    response = Mock()
    response.status_code = 200
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.raw.read.side_effect = [b"partial", OSError("interrupted download")]
    request = Mock(return_value=response)
    monkeypatch.setattr(cache.requests, "get", request)
    with pytest.raises(OSError, match="interrupted download"):
        cache.CacheManager().get_lang_filtered_raw_data("en", "pt")
    assert request.call_args.args[0].endswith("/source-data/added/en-pt-filtered.jsonl.zst")
    response.__exit__.assert_called_once()
    assert list((tmp_path / "added").iterdir()) == []
