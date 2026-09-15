"""Retain dictionary fields in the same compact format written into SQLite.

The large forms/details columns are encoded and compressed once on extraction.
Ranking touches only small metadata. SQLite expands forms for its search indexes,
but copies the stored fields directly; detail JSON stays compressed until a word
page is read. Ordinary sequence iteration returns independent decoded snapshots.
"""

from collections.abc import Callable, Iterator, Sequence
from typing import Any

import msgspec
import zstandard

from .entry_json import ROW_COMPRESSION_LEVEL, decode_entry_json, encode_entry_json

StoredJson = str | bytes | None


class _SqliteMetadata(msgspec.Struct, frozen=True):
    word: str
    pos: str
    senses: list[dict[str, Any]]
    gender: str | None = None
    pronunciation: str | None = None
    etymology: str | None = None
    # These smaller columns are also copied verbatim, without parsing their
    # nested objects just to encode them again. They retain JSON TEXT storage.
    details: msgspec.Raw = msgspec.Raw(b"null")
    romanizations: msgspec.Raw = msgspec.Raw(b"null")
    pronunciations: msgspec.Raw = msgspec.Raw(b"null")


class PreparedDictionaryEntry(msgspec.Struct, frozen=True):
    entry: dict[str, Any]
    forms: StoredJson
    form_details: StoredJson


# Private metadata contains only strings, bytes, bools and floats: no cycles.
class _PackedEntry(msgspec.Struct, gc=False):
    word: str
    payload: bytes
    forms: StoredJson
    form_details: StoredJson
    frequency: float = 0.0


class PackedDictionaryEntries(Sequence[dict[str, Any]]):
    def __init__(self) -> None:
        self._rows: list[_PackedEntry] = []
        self._compressor = zstandard.ZstdCompressor(level=ROW_COMPRESSION_LEVEL, write_checksum=True)
        self.form_count = 0

    def append(self, entry: dict[str, Any]) -> None:
        forms = encode_entry_json(entry.get("forms"), self._compressor)
        details = encode_entry_json(entry.get("formDetails"), self._compressor)
        # Keep only small fields in the metadata JSON, preserving explicit empty
        # values for ordinary sequence reads. Large columns live once, separately.
        metadata = dict(entry)
        if forms is not None:
            del metadata["forms"]
        if details is not None:
            del metadata["formDetails"]
        self._rows.append(_PackedEntry(entry["word"], msgspec.json.encode(metadata), forms, details))
        self.form_count += len(entry.get("forms") or ())

    def sort_by_frequency(self, frequency: Callable[[str], float]) -> None:
        for row in self._rows:
            row.frequency = frequency(row.word)
        # Stable source order for tied frequencies preserves SQLite entry IDs.
        self._rows.sort(key=lambda row: -row.frequency)

    @property
    def payload_bytes(self) -> int:
        def size(value):
            return len(value.encode()) if isinstance(value, str) else len(value or b"")
        return sum(len(row.payload) + size(row.forms) + size(row.form_details) for row in self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    @staticmethod
    def _decode(row: _PackedEntry) -> dict[str, Any]:
        entry = msgspec.json.decode(row.payload)
        if row.forms is not None:
            entry["forms"] = decode_entry_json(row.forms)
        if row.form_details is not None:
            entry["formDetails"] = decode_entry_json(row.form_details)
        entry["freq"] = row.frequency
        return entry

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for row in self._rows:
            yield self._decode(row)

    def iter_for_sqlite(self) -> Iterator[PreparedDictionaryEntry]:
        decoder = msgspec.json.Decoder(_SqliteMetadata)
        for row in self._rows:
            entry = msgspec.structs.asdict(decoder.decode(row.payload))
            entry["forms"] = decode_entry_json(row.forms) if row.forms is not None else None
            entry["freq"] = row.frequency
            yield PreparedDictionaryEntry(entry, row.forms, row.form_details)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self._decode(row) for row in self._rows[index]]
        return self._decode(self._rows[index])
