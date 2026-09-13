"""Versioned, optional compression for JSON used only on dictionary pages.

SQLite TEXT remains JSON; BLOB is LZJ1 + uint32 LE decoded length + a checked
Zstandard frame. Keep the envelope in sync with Lexicoff's entryJson.ts.
"""

import msgspec
import orjson
import zstandard

ROW_COMPRESSION_LEVEL = 6
MIN_COMPRESS_BYTES = 512
MAX_COMPRESS_BYTES = 64 * 1024 * 1024
MAGIC = b"LZJ1"


def encode_entry_json(value, compressor: zstandard.ZstdCompressor) -> str | bytes | None:
    if not value:
        return None
    raw = bytes(value) if isinstance(value, msgspec.Raw) else orjson.dumps(value)
    if raw in (b"null", b"[]", b"{}"):
        return None
    if MIN_COMPRESS_BYTES <= len(raw) <= MAX_COMPRESS_BYTES:
        frame = compressor.compress(raw)
        if len(frame) + 8 < len(raw):
            return MAGIC + len(raw).to_bytes(4, "little") + frame
    return raw.decode()


def decode_entry_json(value: str | bytes):
    """Read current TEXT and compressed fields in pipeline audits/tools."""
    if isinstance(value, bytes):
        if len(value) < 9 or value[:4] != MAGIC:
            raise ValueError("Unsupported dictionary JSON encoding")
        size = int.from_bytes(value[4:8], "little")
        frame = value[8:]
        if not 0 < size <= MAX_COMPRESS_BYTES or len(frame) >= size:
            raise ValueError("Invalid dictionary JSON length")
        if zstandard.frame_content_size(frame) != size:
            raise ValueError("Dictionary JSON length mismatch")
        value = zstandard.ZstdDecompressor().decompress(frame, max_output_size=size, allow_extra_data=False)
        if len(value) != size:
            raise ValueError("Dictionary JSON length mismatch")
    return orjson.loads(value)
