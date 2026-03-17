import logging
import re
from typing import Any, Callable, Optional

import msgspec

from .utils import _cat_names, strip_diacritics, to_phonetic_el
from .wiktionary import Entry

log = logging.getLogger(__name__)

# POS types to include
INCLUDED_POS = frozenset({
    "noun", "verb", "adj", "adv", "prep", "conj", "pron", "det",
    "intj", "num", "particle", "affix", "prefix", "suffix",
    "phrase", "name",
})

# POS types to skip
EXCLUDED_POS = frozenset({
    "hard-redirect", "soft-redirect", "character", "symbol",
    "punct", "abbrev",
})

# Junk gloss prefixes (superset of conjugation one, includes more form-of patterns)
_JUNK_GLOSS_PREFIXES = (
    "used to form", "used for forming", "used as a", "used as an",
    "used with", "forms composite", "forms the",
    "synonym of", "alternative form of", "compound of",
    "see the full list", "post-1990",
    "alternative spelling of", "obsolete spelling of",
    "eye dialect of", "misspelling of", "dated form of",
    "rare form of", "archaic form of", "clipping of",
    "abbreviation of", "initialism of", "acronym of",
)

def _is_junk_gloss(gloss: str) -> bool:
    lower = gloss.lower()
    return any(lower.startswith(p) for p in _JUNK_GLOSS_PREFIXES)


class DictLanguageConfig(msgspec.Struct, frozen=True):
    code: str
    name: str
    english_wiktionary_name: str
    phonetic_fn: Callable[[str], str] | None = None


DICT_CONFIGS: list[DictLanguageConfig] = [
    DictLanguageConfig(code="fr", name="français", english_wiktionary_name="French"),
    DictLanguageConfig(code="el", name="ελληνικά", english_wiktionary_name="Greek", phonetic_fn=to_phonetic_el),
    DictLanguageConfig(code="de", name="Deutsch", english_wiktionary_name="German"),
    DictLanguageConfig(code="es", name="español", english_wiktionary_name="Spanish"),
    DictLanguageConfig(code="it", name="italiano", english_wiktionary_name="Italian"),
    DictLanguageConfig(code="en", name="English", english_wiktionary_name="English"),
]


def extract_senses(entry: Entry) -> list[dict[str, Any]]:
    """Extract structured senses with glosses, examples, and tags."""
    senses: list[dict[str, Any]] = []
    for sense in entry.senses:
        if sense.form_of or sense.alt_of:
            continue
        if not sense.glosses:
            continue
        raw_gloss = sense.glosses[-1]
        if _is_junk_gloss(raw_gloss.lower()):
            continue
        gloss = re.sub(r"\s*\(.*?\)", "", raw_gloss).strip()
        gloss = re.sub(r"\s*\[.*?\]", "", gloss).strip()
        if not gloss:
            continue
        sense_dict: dict[str, Any] = {"gloss": gloss}
        examples: list[str] = []
        for ex in sense.examples:
            if isinstance(ex, dict):
                text = ex.get("text", "")
                if text and len(text) < 200:
                    examples.append(text)
            if len(examples) >= 2:
                break
        if examples:
            sense_dict["examples"] = examples
        tags = [t for t in sense.tags if t in ("formal", "informal", "colloquial", "literary", "archaic", "dated", "rare", "vulgar", "slang", "figurative", "transitive", "intransitive")]
        if tags:
            sense_dict["tags"] = tags
        senses.append(sense_dict)
    return senses


def extract_gender(entry: Entry) -> Optional[str]:
    for ht in entry.head_templates:
        g = ht.args.get("g", "") or ht.args.get("1", "")
        if g in ("m", "f", "n", "m-f", "mf", "m-p", "f-p", "n-p"):
            return g
        g2 = ht.args.get("g2", "")
        if g and g2:
            return f"{g}-{g2}"
    return None


def extract_forms(entry: Entry) -> list[str]:
    forms: list[str] = []
    seen: set[str] = set()
    for form in entry.forms:
        if form.form is None:
            continue
        if form.form == entry.word:
            continue
        if "table-tags" in form.tags:
            continue
        if "inflection-template" in form.tags:
            continue
        text = form.form.strip()
        if not text or text == "-":
            continue
        if text not in seen:
            forms.append(text)
            seen.add(text)
    return forms


def extract_pronunciation(entry: Entry) -> Optional[str]:
    for sound in entry.sounds:
        if isinstance(sound, dict):
            ipa = sound.get("ipa", "")
            if ipa:
                return ipa
    return None


def extract_etymology(entry: Entry) -> Optional[str]:
    for et in entry.etymology_templates:
        if et.expansion and len(et.expansion) < 150:
            if any(kw in et.name for kw in ("inh", "bor", "der", "from", "inherited", "borrowed")):
                return et.expansion
    return None


def entry_is_valid(entry: Entry) -> bool:
    if entry.pos in EXCLUDED_POS:
        return False
    if entry.pos not in INCLUDED_POS:
        return False
    if entry.word is None:
        return False
    if entry.senses and all(
        "form-of" in s.tags or "alt-of" in s.tags for s in entry.senses
    ):
        return False
    BAD_CATEGORIES = {
        f"{entry.lang} multiword forms",
        f"{entry.lang} terms in nonstandard scripts",
    }
    for c in _cat_names(entry.categories):
        if c in BAD_CATEGORIES:
            return False
    return True


def process_dict_entry(config: DictLanguageConfig, entry: Entry) -> dict[str, Any] | None:
    if not entry_is_valid(entry):
        return None
    senses = extract_senses(entry)
    if not senses:
        return None
    processed: dict[str, Any] = {
        "word": entry.word,
        "wordNoDiacritics": strip_diacritics(entry.word),
        "pos": entry.pos,
        "senses": senses,
    }
    gender = extract_gender(entry)
    if gender:
        processed["gender"] = gender
    forms = extract_forms(entry)
    if forms:
        processed["forms"] = forms
    pronunciation = extract_pronunciation(entry)
    if pronunciation:
        processed["pronunciation"] = pronunciation
    etymology = extract_etymology(entry)
    if etymology:
        processed["etymology"] = etymology
    return processed


def make_dict_language_static_metadata(config: DictLanguageConfig):
    return {
        "code": config.code,
        "name": config.name,
        "englishWiktionaryName": config.english_wiktionary_name,
    }
