import re
from typing import Optional

from .wiktionary import Entry

_JUNK_GLOSS_PREFIXES = (
    "used to form",
    "used for forming",
    "used as a",
    "used as an",
    "used with",
    "forms composite",
    "forms the",
    "synonym of",
    "alternative form of",
    "compound of",
    "see the full list",
    "post-1990",
)


def _is_junk_gloss(gloss: str) -> bool:
    """Return True if a gloss is a meta-description rather than a definition."""
    lower = gloss.lower()
    return any(lower.startswith(p) for p in _JUNK_GLOSS_PREFIXES)


def extract_gloss(entry: Entry) -> Optional[str]:
    """Extract up to 3 diverse English glosses from an entry's senses."""
    valid_senses = [
        s for s in entry.senses if not s.form_of and not s.alt_of and s.glosses
    ]
    if not valid_senses:
        return None

    seen_headers: set[str] = set()
    glosses: list[str] = []
    has_more = False
    for sense in valid_senses:
        header = sense.glosses[0] if len(sense.glosses) > 1 else ""
        if header in seen_headers:
            continue
        if header:
            seen_headers.add(header)
        raw_gloss = sense.glosses[-1][0].lower() + sense.glosses[-1][1:]
        if _is_junk_gloss(raw_gloss):
            continue
        stripped = re.sub(r"\s*\(.*?\)", "", raw_gloss).strip()
        stripped = re.sub(r"\s*\[.*?\]", "", stripped).strip()
        # If stripping qualifiers left an empty or single-word gloss (e.g. for loanwords
        # like "Leberkäse (a dish similar to meat loaf...)"), fall back to using the
        # content of the first long parenthetical as the definition.
        if not stripped or " " not in stripped:
            m = re.search(r"\(([^)]{20,})\)", raw_gloss)
            if m:
                stripped = m.group(1).strip()
        raw_gloss = stripped
        parts = [p.strip().rstrip(".") for p in raw_gloss.split(";")]
        for part in parts:
            if not part or _is_junk_gloss(part):
                continue
            if part not in glosses:
                if len(glosses) >= 3:
                    has_more = True
                    break
                glosses.append(part)
        if has_more:
            break

    if not glosses:
        return None

    result = "; ".join(glosses)
    if has_more:
        result += "; ..."
    return result
