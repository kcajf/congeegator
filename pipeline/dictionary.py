import logging
import re
from typing import Any, Callable, Optional

import msgspec

from .utils import _cat_names, strip_diacritics, to_phonetic_el
from .wiktionary import Entry
from .dictionary_quality import enhance_record, trusted_persian_head

log = logging.getLogger(__name__)

# These markers are failed Wiktextract/template expansion, not display text.
# Drop a contaminated field rather than guessing at its intended definition.
_UNEXPANDED_MARKUP = re.compile(
    r"\{\{|\}\}|\[\[|\]\]|\b(?:Template|Module):(?=\S)|(?i:\b(?:Lua|Script) error\b)"
    r"|(?i:</?(?:ref|span|div|br|p|small|sup|sub|table|a|i|b)(?:\s[^>]*|/?)>)",
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
    DictLanguageConfig(code="grc", name="Ancient Greek", english_wiktionary_name="Ancient Greek"),
    DictLanguageConfig(code="az", name="azərbaycanca", english_wiktionary_name="Azerbaijani"),
    DictLanguageConfig(code="eu", name="euskara", english_wiktionary_name="Basque"),
    DictLanguageConfig(code="br", name="brezhoneg", english_wiktionary_name="Breton"),
    DictLanguageConfig(code="et", name="eesti", english_wiktionary_name="Estonian"),
    DictLanguageConfig(code="ka", name="ქართული", english_wiktionary_name="Georgian"),
    DictLanguageConfig(code="he", name="עברית", english_wiktionary_name="Hebrew"),
    DictLanguageConfig(code="hi", name="हिन्दी", english_wiktionary_name="Hindi"),
    DictLanguageConfig(code="is", name="íslenska", english_wiktionary_name="Icelandic"),
    DictLanguageConfig(code="ga", name="Gaeilge", english_wiktionary_name="Irish"),
    DictLanguageConfig(code="ko", name="한국어", english_wiktionary_name="Korean"),
    DictLanguageConfig(code="lt", name="lietuvių", english_wiktionary_name="Lithuanian"),
    DictLanguageConfig(code="mk", name="македонски", english_wiktionary_name="Macedonian"),
    DictLanguageConfig(code="ms", name="Bahasa Melayu", english_wiktionary_name="Malay"),
    DictLanguageConfig(code="oc", name="occitan", english_wiktionary_name="Occitan"),
    DictLanguageConfig(code="fa", name="فارسی", english_wiktionary_name="Persian"),
    DictLanguageConfig(code="sa", name="संस्कृतम्", english_wiktionary_name="Sanskrit"),
    DictLanguageConfig(code="sh", name="srpskohrvatski / српскохрватски", english_wiktionary_name="Serbo-Croatian"),
    DictLanguageConfig(code="sk", name="slovenčina", english_wiktionary_name="Slovak"),
    DictLanguageConfig(code="cy", name="Cymraeg", english_wiktionary_name="Welsh"),
]


def extract_senses(entry: Entry) -> list[dict[str, Any]]:
    """Extract structured senses with glosses, examples, and tags."""
    senses: list[dict[str, Any]] = []
    for sense in entry.senses:
        if not sense.glosses:
            continue
        # Wiktextract stores the full nesting path. Keeping only the last item
        # loses the lemma in form-of senses and context in subordinate meanings.
        parts = [_clean_text(part) for part in sense.glosses]
        if not all(parts):
            continue
        gloss = parts[0]
        for part in parts[1:]:
            gloss += (" " if gloss.endswith(":") else ": ") + part
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
        tags = [t for t in sense.tags if t in (
            "formal", "informal", "colloquial", "literary", "archaic", "dated", "rare",
            "vulgar", "slang", "figurative", "transitive", "intransitive", "obsolete",
            "nonstandard", "dialectal", "regional", "misspelling", "historical",
            "poetic", "humorous", "offensive", "derogatory", "Early", "Old-Latin",
            "Classical-Latin", "Late-Latin", "Medieval-Latin", "New-Latin",
            "Ecclesiastical-Latin",
        )]
        if tags:
            sense_dict["tags"] = tags
        senses.append(sense_dict)
    return senses


VALID_GENDERS = {"m", "f", "n", "c", "m-f", "mf", "m-p", "f-p", "n-p"}


def extract_gender(entry: Entry) -> Optional[str]:
    if entry.pos not in {"noun", "name"}:
        return None
    # Positional template arguments are language-specific: Russian noun+ arg1
    # 'f' is an accent paradigm, and Danish noun arg1 'n' can be an ending.
    # Wiktextract has already interpreted these templates into sense tags.
    gender_tags = {"masculine": "m", "feminine": "f", "neuter": "n", "common-gender": "c"}
    found = {gender_tags[tag] for sense in entry.senses for tag in sense.tags if tag in gender_tags}
    if found:
        return "-".join(g for g in ("m", "f", "n", "c") if g in found)
    for ht in entry.head_templates:
        g = ht.args.get("g", "")
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
        if form.tags & {"table-tags", "inflection-template", "class", "romanization", "classifier"}:
            continue
        if "canonical" in form.tags:
            # Canonical forms may be stressed/macronized spellings, but often
            # contain paradigm notes ("root stress:", "4th conjugation").
            if strip_diacritics(form.form) != strip_diacritics(entry.word):
                continue
        text = _clean_text(form.form)
        if not text or text == "-":
            continue
        # A few upstream table headers carry grammatical tags instead of class.
        if entry.lang_code == "fi" and "person" in form.tags and text in {"imperative mood", "optative mood"}:
            continue
        if entry.lang_code == "pl" and text == "cases" and not form.source:
            continue
        if entry.lang_code == "la" and text == "declension" and "pronominal" in form.tags:
            continue
        if entry.lang_code == "nb" and text == "used with neuter nouns" and "article" in form.tags:
            continue
        if entry.lang_code == "ro" and {"past", "participle"} <= form.tags and text.startswith("of "):
            continue
        if entry.lang_code == "hu" and "error-unrecognized-form" in form.tags and text.startswith("or "):
            text = text[3:]
        if entry.lang_code == "nl" and "contracted" in form.tags and text.startswith("form "):
            text = text[5:]
        if entry.lang_code == "ro" and "feminine" in form.tags and text.startswith("equivalent "):
            text = text[11:]
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
                expansion = _clean_text(et.expansion)
                if expansion:
                    return expansion
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
            if c == "Persian terms in nonstandard scripts" and trusted_persian_head(entry):
                continue
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
    return enhance_record(entry, processed, _clean_text)


def make_dict_language_static_metadata(config: DictLanguageConfig):
    return {
        "code": config.code,
        "name": config.name,
        "englishWiktionaryName": config.english_wiktionary_name,
    }
