import logging
import re
import time
import unicodedata
from contextlib import contextmanager
from typing import Any, Optional

import orjson

log = logging.getLogger(__name__)


@contextmanager
def log_timing(label: str):
    """Context manager that logs elapsed time for a block."""
    start = time.monotonic()
    log.info(f"[timing] {label}: started")
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        log.info(f"[timing] {label}: {elapsed:.1f}s")


def _cat_name(c: Any) -> str:
    """Extract category name from either a plain string or a dict with 'name' key."""
    if isinstance(c, str):
        return c
    if isinstance(c, dict):
        return c.get("name", "")
    return ""


def _cat_names(categories: tuple[Any, ...]) -> list[str]:
    """Extract all category names from a tuple of categories."""
    return [_cat_name(c) for c in categories]


def find_in_tags(tags: set[str], values: tuple[str, ...]) -> Optional[str]:
    for v in values:
        if v in tags:
            return v
    return None


def matches_tags(tags: set[str], want_tags: tuple[str, ...]) -> bool:
    for t in want_tags:
        if t not in tags:
            return False
    return True


def strip_diacritics(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def sort_without_diacritics(strings: list[str]) -> list[str]:
    return sorted(strings, key=strip_diacritics)


def to_phonetic_el(s: str) -> str:
    """Convert a Greek or Latin string to a canonical Latin phonetic representation."""
    s = strip_diacritics(s).lower()

    s = s.replace("μπ", "b")
    s = s.replace("ντ", "d")
    s = s.replace("γκ", "g")
    s = s.replace("γγ", "ng")
    s = s.replace("τσ", "ts")
    s = s.replace("τζ", "dz")

    voiceless = set("πτκθσφχξψ")
    result = []
    i = 0
    while i < len(s):
        if i + 1 < len(s) and s[i] in ("α", "ε") and s[i + 1] == "υ":
            vowel_part = "a" if s[i] == "α" else "e"
            next_after = s[i + 2] if i + 2 < len(s) else None
            if next_after is None or next_after in voiceless:
                result.append(vowel_part + "f")
            else:
                result.append(vowel_part + "v")
            i += 2
            continue
        result.append(s[i])
        i += 1
    s = "".join(result)

    s = s.replace("αι", "e")
    s = s.replace("ει", "i")
    s = s.replace("οι", "i")
    s = s.replace("ου", "U")
    s = s.replace("υι", "i")

    s = s.replace("η", "i")
    s = s.replace("ω", "o")
    s = s.replace("υ", "i")
    s = s.replace("α", "a")
    s = s.replace("ε", "e")
    s = s.replace("ι", "i")
    s = s.replace("ο", "o")

    s = s.replace("β", "v")
    s = s.replace("γ", "g")
    s = s.replace("δ", "d")
    s = s.replace("ζ", "z")
    s = s.replace("θ", "th")
    s = s.replace("κ", "k")
    s = s.replace("λ", "l")
    s = s.replace("μ", "m")
    s = s.replace("ν", "n")
    s = s.replace("ξ", "ks")
    s = s.replace("π", "p")
    s = s.replace("ρ", "r")
    s = s.replace("σ", "s")
    s = s.replace("ς", "s")
    s = s.replace("τ", "t")
    s = s.replace("φ", "f")
    s = s.replace("χ", "ch")
    s = s.replace("ψ", "ps")

    s = s.replace("mp", "b")
    s = s.replace("nt", "d")
    s = s.replace("gk", "g")

    s = s.replace("ph", "f")
    s = re.sub(r"c(?!h)", "k", s)
    s = s.replace("q", "k")
    s = s.replace("w", "o")
    s = s.replace("x", "ch")
    s = re.sub(r"(?<![ctk])h", "ch", s)
    s = s.replace("y", "i")

    latin_voiceless = set("ptksfc")
    result = []
    i = 0
    while i < len(s):
        if i + 1 < len(s) and s[i] in ("a", "e") and s[i + 1] == "u":
            next_after = s[i + 2] if i + 2 < len(s) else None
            if next_after is None or next_after in latin_voiceless:
                result.append(s[i] + "f")
            else:
                result.append(s[i] + "v")
            i += 2
            continue
        result.append(s[i])
        i += 1
    s = "".join(result)

    s = s.replace("ei", "i")
    s = s.replace("ai", "e")
    s = s.replace("oi", "i")
    s = s.replace("ou", "U")
    s = s.replace("u", "i")
    s = s.replace("U", "u")

    return s


def _orjson_dump(obj: Any, pretty: bool = False) -> bytes:
    opts = orjson.OPT_NON_STR_KEYS
    if pretty:
        opts |= orjson.OPT_INDENT_2
    return orjson.dumps(obj, option=opts)
