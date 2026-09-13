"""Compact, repeatable dictionary records between extraction and SQLite writing.

Keep encoded records instead of millions of live form-detail dicts/lists. Large
records compress particularly well because their grammatical readings repeat.
Only the entry being consumed is expanded; the public JSON/SQLite schema stays
unchanged. Iteration returns independent snapshots, not mutable stored objects.
"""

from collections.abc import Callable, Iterator, Sequence
from typing import Any

import msgspec
import zstandard


class _SqliteEntry(msgspec.Struct):
    word: str
    pos: str
    senses: list[dict[str, Any]]
    forms: list[str] | None = None
    gender: str | None = None
    pronunciation: str | None = None
    etymology: str | None = None
    # These columns are copied into SQLite verbatim. Parsing their nested
    # dictionaries/lists would only be followed by encoding them again.
    details: msgspec.Raw = msgspec.Raw(b"null")
    formDetails: msgspec.Raw = msgspec.Raw(b"null")
    pronunciations: msgspec.Raw = msgspec.Raw(b"null")


# Private metadata contains only strings, bytes, bools and floats: no cycles.
class _PackedEntry(msgspec.Struct, gc=False):
    word: str
    payload: bytes
    compressed: bool
    frequency: float = 0.0


class PackedDictionaryEntries(Sequence[dict[str, Any]]):
    def __init__(self) -> None:
        self._rows: list[_PackedEntry] = []
        self._compressor = zstandard.ZstdCompressor(level=1)

    def append(self, entry: dict[str, Any], encoded: bytes) -> None:
        # Tiny entries gain little from a separate compression frame. Reuse the
        # exact JSON already encoded for deduplication rather than encode again.
        payload = self._compressor.compress(encoded) if len(encoded) >= 1024 else encoded
        compressed = len(payload) < len(encoded)
        self._rows.append(_PackedEntry(entry["word"], payload if compressed else encoded, compressed))

    def sort_by_frequency(self, frequency: Callable[[str], float]) -> None:
        for row in self._rows:
            row.frequency = frequency(row.word)
        # Python's stable sort preserves source order for tied frequencies,
        # including distinct entries sharing a headword. SQLite IDs depend on it.
        self._rows.sort(key=lambda row: -row.frequency)

    @property
    def payload_bytes(self) -> int:
        return sum(len(row.payload) for row in self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    @staticmethod
    def _decode(row: _PackedEntry, decompressor) -> dict[str, Any]:
        payload = decompressor.decompress(row.payload) if row.compressed else row.payload
        entry = msgspec.json.decode(payload)
        entry["freq"] = row.frequency
        return entry

    def __iter__(self) -> Iterator[dict[str, Any]]:
        decompressor = zstandard.ZstdDecompressor()
        for row in self._rows:
            yield self._decode(row, decompressor)

    def iter_for_sqlite(self) -> Iterator[dict[str, Any]]:
        decompressor = zstandard.ZstdDecompressor()
        decoder = msgspec.json.Decoder(_SqliteEntry)
        for row in self._rows:
            payload = decompressor.decompress(row.payload) if row.compressed else row.payload
            entry = msgspec.structs.asdict(decoder.decode(payload))
            entry["freq"] = row.frequency
            yield entry

    def __getitem__(self, index):
        decompressor = zstandard.ZstdDecompressor()
        if isinstance(index, slice):
            return [self._decode(row, decompressor) for row in self._rows[index]]
        return self._decode(self._rows[index], decompressor)
