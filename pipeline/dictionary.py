import logging
import re
from typing import Any, Callable, Optional

import msgspec

from .utils import _cat_names, to_phonetic_el
from .wiktionary import Entry

log = logging.getLogger(__name__)

# These markers are failed Wiktextract/template expansion, not display text.
# Drop a contaminated field rather than guessing at its intended definition.
_UNEXPANDED_MARKUP = re.compile(
    r"\{\{|\}\}|\[\[|\]\]|\b(?:Template|Module):|\b(?:Lua|Script) error\b",
    re.IGNORECASE,
)


def _clean_text(text: str) -> str | None:
    text = text.strip()
    return text if text and not _UNEXPANDED_MARKUP.search(text) else None

# POS types to include
INCLUDED_POS = frozenset({
    "noun", "verb", "adj", "adv", "prep", "conj", "pron", "det",
    "intj", "num", "particle", "affix", "prefix", "suffix",
    "phrase", "name",
    "article", "contraction", "postp", "ambiposition", "circumpos",
    "infix", "interfix", "circumfix", "combining_form", "root",
    "proverb", "prep_phrase", "adv_phrase", "classifier", "counter",
    "preverb", "converb", "adj_noun", "adj_verb", "adnominal",
})

# POS types to skip
EXCLUDED_POS = frozenset({
    "hard-redirect", "soft-redirect", "character", "symbol",
    "punct", "abbrev",
})


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
    DictLanguageConfig(code="pt", name="português", english_wiktionary_name="Portuguese"),
    DictLanguageConfig(code="ca", name="català", english_wiktionary_name="Catalan"),
    DictLanguageConfig(code="ro", name="română", english_wiktionary_name="Romanian"),
    DictLanguageConfig(code="gl", name="galego", english_wiktionary_name="Galician"),
    DictLanguageConfig(code="nl", name="Nederlands", english_wiktionary_name="Dutch"),
    DictLanguageConfig(code="sv", name="svenska", english_wiktionary_name="Swedish"),
    DictLanguageConfig(code="da", name="dansk", english_wiktionary_name="Danish"),
    DictLanguageConfig(code="nb", name="norsk bokmål", english_wiktionary_name="Norwegian Bokmål"),
    DictLanguageConfig(code="pl", name="polski", english_wiktionary_name="Polish"),
    DictLanguageConfig(code="ru", name="русский", english_wiktionary_name="Russian"),
    DictLanguageConfig(code="uk", name="українська", english_wiktionary_name="Ukrainian"),
    DictLanguageConfig(code="cs", name="čeština", english_wiktionary_name="Czech"),
    DictLanguageConfig(code="fi", name="suomi", english_wiktionary_name="Finnish"),
    DictLanguageConfig(code="hu", name="magyar", english_wiktionary_name="Hungarian"),
    DictLanguageConfig(code="tr", name="Türkçe", english_wiktionary_name="Turkish"),
    DictLanguageConfig(code="id", name="Bahasa Indonesia", english_wiktionary_name="Indonesian"),
    DictLanguageConfig(code="vi", name="Tiếng Việt", english_wiktionary_name="Vietnamese"),
    DictLanguageConfig(code="eo", name="Esperanto", english_wiktionary_name="Esperanto"),
    DictLanguageConfig(code="la", name="Latina", english_wiktionary_name="Latin"),
]


def extract_senses(entry: Entry) -> list[dict[str, Any]]:
    """Extract structured senses with glosses, examples, and tags."""
    senses: list[dict[str, Any]] = []
    for sense in entry.senses:
        if not sense.glosses:
            continue
        raw_gloss = sense.glosses[-1]
        gloss = _clean_text(raw_gloss)
        if not gloss:
            continue
        sense_dict: dict[str, Any] = {"gloss": gloss}
        examples: list[str] = []
        for ex in sense.examples:
            if isinstance(ex, dict):
                text = _clean_text(ex.get("text", ""))
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


VALID_GENDERS = {"m", "f", "n", "m-f", "mf", "m-p", "f-p", "n-p"}


def extract_gender(entry: Entry) -> Optional[str]:
    for ht in entry.head_templates:
        g = ht.args.get("g", "") or ht.args.get("1", "")
        if g in VALID_GENDERS:
            g2 = ht.args.get("g2", "")
            if g2 and g2 in VALID_GENDERS:
                return f"{g}-{g2}"
            return g
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
        text = _clean_text(form.form)
        if not text or text == "-":
            continue
        if text not in seen:
            forms.append(text)
            seen.add(text)
    return forms


def extract_pronunciation(entry: Entry) -> Optional[str]:
    for sound in entry.sounds:
        if isinstance(sound, dict):
            ipa = _clean_text(sound.get("ipa", ""))
            if ipa:
                return ipa
    return None


def extract_etymology(entry: Entry) -> Optional[str]:
    for et in entry.etymology_templates:
        if et.expansion and len(et.expansion) < 150:
            if any(kw in et.name for kw in ("inh", "bor", "der", "from", "inherited", "borrowed")):
                return _clean_text(et.expansion)
    return None


def entry_is_valid(entry: Entry) -> bool:
    if entry.pos in EXCLUDED_POS:
        return False
    if entry.pos not in INCLUDED_POS:
        return False
    if not entry.word:
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
