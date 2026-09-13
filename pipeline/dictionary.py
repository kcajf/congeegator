import logging
import re
from typing import Any, Callable, Optional

import msgspec

from .utils import _cat_names, strip_diacritics, to_phonetic_el
from .wiktionary import Entry
from .dictionary_quality import enhance_record, trusted_persian_head, form_grammar, labels, raw_labels, QUALITY_LANGUAGES

log = logging.getLogger(__name__)

# These markers are failed Wiktextract/template expansion, not display text.
# Drop a contaminated field rather than guessing at its intended definition.
_UNEXPANDED_MARKUP = re.compile(
    r"\{\{|\}\}|\[\[|\]\]|\b(?:Template|Module):(?=\S)|(?i:\b(?:Lua|Script) error\b)"
    r"|(?i:</?(?:ref|span|div|br|p|small|sup|sub|table|a|i|b)(?:\s[^>]*|/?)>)",
)


def _clean_text(text: str) -> str | None:
    text = text.strip()
    # Most inflected forms are letters only. None of the rejected markup can
    # occur in such a string; avoid running the regex millions of times.
    if text.isalpha():
        return text
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


_LANGUAGE_ANCHORS = {c.english_wiktionary_name: c.code for c in DICT_CONFIGS}
_NON_LEXICAL_FORM_TAGS = frozenset({
    "table-tags", "inflection-template", "class", "romanization", "classifier", "auxiliary",
})


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
        examples = extract_examples(sense.examples)
        if examples:
            sense_dict["examples"] = examples
        # An unanchored link in an English definition points to English.
        # Explicit form/alternative relationships always use the entry language.
        links = [link for label, target in sense.links
                 if (link := word_link(target, "en", label))]
        for field, values in (("formOf", sense.form_of), ("altOf", sense.alt_of)):
            refs = []
            for value in values:
                # Wiktextract form_of can contain display stress marks and even
                # aspect labels. The corresponding wiki link has the page title.
                source = next((link for link in links
                               if value.word == link.get("label", link["word"])
                               or value.word in {link.get("label", link["word"]) + " pf",
                                                 link.get("label", link["word"]) + " impf"}), None)
                link = dict(source, lang=entry.lang_code) if source else word_link(value.word, entry.lang_code)
                if link:
                    refs.append(link)
            if refs:
                sense_dict[field] = unique_links(refs)
                targets = {ref["word"] for ref in refs}
                labels = {ref.get("label", ref["word"]) for ref in refs}
                links = [link for link in links if link["word"] not in targets
                         and link.get("label", link["word"]) not in labels]
                links = refs + links
        if links:
            sense_dict["links"] = unique_links(links)
        # Topics include inferred ancestors (politics → government). Prefer the
        # explicit labels from the source, keeping the structured gloss intact.
        labels = " ".join(match.group(1) for raw in sense.raw_glosses
                          if (match := re.match(r"^\(([^)]+)\)", raw)))
        topics = list(dict.fromkeys(t for t in sense.topics if _clean_text(t)
                                   and (not sense.raw_glosses or re.search(
                                       r"(?<!\w)" + re.escape(t.replace("-", " ")) + r"(?!\w)", labels))))
        if sense.qualifier and _clean_text(sense.qualifier):
            sense_dict["qualifier"] = sense.qualifier
        if topics:
            sense_dict["topics"] = topics
        for field in ("synonyms", "antonyms"):
            refs = extract_relations(getattr(sense, field), entry.lang_code, entry.word)
            if refs:
                sense_dict[field] = refs
        tags = [t for t in sense.tags if t in (
            "formal", "informal", "colloquial", "literary", "archaic", "dated", "rare",
            "vulgar", "slang", "figurative", "transitive", "intransitive", "obsolete",
            "nonstandard", "dialectal", "regional", "misspelling", "historical",
            "poetic", "humorous", "offensive", "derogatory", "Early", "Old-Latin",
            "Classical-Latin", "Late-Latin", "Medieval-Latin", "New-Latin",
            "Ecclesiastical-Latin", "reflexive", "impersonal", "ditransitive",
            "countable", "uncountable", "usually-plural", "plural-only", "singular-only",
            "figuratively", "plural-normally", "ambitransitive", "familiar", "invariable",
            "emphatic", "intensifier", "idiomatic",
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


def extract_form_items(entry: Entry):
    """Yield cleaned spellings with their original grammatical metadata."""
    for form in entry.forms:
        if form.form is None:
            continue
        if form.form == entry.word:
            continue
        if not form.tags.isdisjoint(_NON_LEXICAL_FORM_TAGS):
            continue
        if "canonical" in form.tags:
            # Canonical forms may be stressed/macronized spellings, but often
            # contain paradigm notes ("root stress:", "4th conjugation").
            if strip_diacritics(form.form) != strip_diacritics(entry.word):
                continue
        text = _clean_text(form.form)
        if not text or text == "-":
            continue
        # Descriptions of compound paradigms are not spellings. Keeping them
        # makes common auxiliaries and words like "past" match thousands of verbs.
        if entry.lang_code == "fr" and "past participle" in text and "+" in text:
            continue
        if entry.lang_code == "uk" and "conjugation of " in text and "+" in text:
            continue
        if entry.lang_code == "cs" and text.startswith(("When the verb ", "The verb ")) and "does not have present tense" in text:
            continue
        if entry.lang_code == "la" and "+" in text and " of sum" in text:
            continue
        if entry.lang_code == "hu" and (text == "intransitive verb" or text.startswith((
            "Future is expressed", "or—more explicitly", "definite forms are not used",
            "Two additional past tenses", "e.g. ",
        ))):
            continue
        if entry.lang_code == "fi" and "error-unrecognized-form" in form.tags and re.match(
            r"(?:[1-3](?:st|nd|rd) (?:sing|plur)\.|present indicative connegative)", text
        ):
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
        if entry.lang_code == "ro" and form.tags & {"feminine", "masculine"} and text.startswith("equivalent "):
            text = text[11:]
        variants = greek_form_variants(text) if entry.lang_code == "el" else [text]
        for variant in variants:
            yield variant, form


def greek_form_variants(text: str) -> list[str]:
    # Prose instructions and abbreviated endings are not searchable spellings.
    if re.search(r"[A-Za-z]", text):
        return []
    variants = []
    for part in re.split(r"\s+-\s+|,\s*", text):
        part = part.strip().lstrip("- ").strip("{} ")
        if not part or part in {"—", "–", "-"} or part.startswith(("‑", "‐")):
            continue
        if part in {"η", "ο"} and part != text:
            continue
        if any("\u0370" <= c <= "\u03ff" or "\u1f00" <= c <= "\u1fff" for c in part):
            # The future particle applies to each alternative in the same cell.
            if text.startswith("θα ") and not part.startswith("θα "):
                part = "θα " + part
            variants.append(part)
    return variants


def extract_forms(entry: Entry) -> list[str]:
    return list(dict.fromkeys(text for text, _ in extract_form_items(entry)))


def extract_pronunciation(entry: Entry) -> Optional[str]:
    for sound in entry.sounds:
        if isinstance(sound, dict):
            ipa = _clean_text(sound.get("ipa", ""))
            if ipa:
                return ipa
    return None


def extract_etymology(entry: Entry) -> Optional[str]:
    # Keep the complete explanation; a single template expansion loses context.
    raw = entry.etymology_text
    tree_end = f"\n{entry.lang} {entry.word}\n"
    if raw.startswith("Etymology tree\n") and tree_end in raw:
        raw = raw.split(tree_end, 1)[1]
    text = _clean_text(raw)
    if text:
        return text
    for et in entry.etymology_templates:
        if et.name in {"inh", "inherited", "bor", "borrowed", "der", "derived"}:
            if expansion := _clean_text(et.expansion):
                return expansion
    return None


def word_link(target: str, lang: str, label: str | None = None) -> dict | None:
    target = _clean_text(target)
    if not target or target in {"-", "?"} or target.startswith("*"):
        return None
    word, _, anchor = target.partition("#")
    # Namespaces and interwiki links are not dictionary headwords.
    if not word or any(c in word for c in ":/<>[]{},()") or len(word) > 200:
        return None
    language_anchor = anchor.replace("_", " ")
    if language_anchor in _LANGUAGE_ANCHORS:
        lang = _LANGUAGE_ANCHORS[language_anchor]
        anchor = ""
    elif anchor and anchor not in {"Noun", "Verb", "Adjective", "Adverb", "Pronoun", "Etymology"}:
        # Unknown language/section: preserve the original anchor on Wiktionary.
        lang = ""
    result = {"word": word, "lang": lang}
    if anchor:
        result["anchor"] = anchor
    if label and (clean := _clean_text(label)) and clean != word:
        result["label"] = clean
    return result


def unique_links(links: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for link in links:
        key = tuple((k, str(v)) for k, v in sorted(link.items()))
        if key not in seen:
            result.append(link)
            seen.add(key)
    return result


def extract_relations(values, lang: str, word: str) -> list[dict]:
    links = []
    for value in values:
        if not isinstance(value, dict):
            continue
        link = word_link(value.get("word", ""), lang, value.get("alt"))
        if not link or link["word"] == word:
            continue
        if sense := _clean_text(value.get("sense", "")):
            link["sense"] = sense
        tags = list(dict.fromkeys(t for t in (*value.get("tags", []), *value.get("raw_tags", []))
                                  if _clean_text(t) and not t.startswith("error-")
                                  and t not in {"synonym", "synonym-of"}))
        if tags:
            link["tags"] = tags
        links.append(link)
    return unique_links(links)


def extract_etymology_links(entry: Entry) -> list[dict]:
    links = []
    borrowing = {"inh", "inherited", "bor", "borrowed", "der", "derived",
                 "lbor", "learned borrowing", "ubor", "unadapted borrowing",
                 "slbor", "semi-learned borrowing", "uder"}
    mentions = {"m", "mention", "l", "link", "cog", "cognate", "ncog", "noncog", "noncognate"}
    compounds = {"af", "affix", "compound", "com", "surf", "surface analysis", "doublet", "dbt"}
    for template in entry.etymology_templates:
        args = template.args
        name = template.name.removesuffix("+")
        # surf can dispatch to another template with a different argument layout.
        # +suf, +it-deverbal, +bor+, etc. are instructions, not language codes.
        if name in {"surf", "surface analysis"} and args.get("1", "").startswith("+"):
            continue
        terms = []
        if name in borrowing:
            terms.append((args.get("2", ""), args.get("3", ""), args.get("alt") or args.get("4")))
        elif name in mentions:
            terms.append((args.get("1", ""), args.get("2", ""), args.get("alt") or args.get("3")))
        elif name in compounds:
            for position in sorted(int(k) for k in args if k.isdigit() and int(k) >= 2):
                term_index = position - 1
                terms.append((args.get(f"lang{term_index}") or args.get("1", ""),
                              args[str(position)], args.get(f"alt{term_index}")))
        for lang, word, label in terms:
            # Inline template modifiers are not a spelling. Unsupported syntax
            # stays plain in the complete etymology instead of guessing a URL.
            if lang and (link := word_link(word, lang, label)):
                links.append(link)
    return unique_links(links)


def _bold_ranges(text: str, values, offset: int = 0) -> list[list[int]]:
    # Source offsets count Unicode code points, not JavaScript UTF-16 units.
    ranges = []
    for pair in values:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        start, end = pair
        if type(start) is int and type(end) is int and 0 <= start - offset < end - offset <= len(text):
            ranges.append([start - offset, end - offset])
    return sorted(ranges)


def extract_examples(values) -> list[dict]:
    examples = []
    seen = set()
    # Lead with usage examples; retain quotations when fewer examples exist.
    ordered = sorted((v for v in values if isinstance(v, dict)),
                     key=lambda v: 0 if v.get("type") == "example" else 1)
    for value in ordered:
        raw = value.get("text", "")
        text = _clean_text(raw)
        if not text or len(text) > 1200 or text in seen or "'''" in text:
            continue
        example = {"text": text}
        for source, target in (("translation", "translation"), ("roman", "roman"), ("ref", "ref")):
            if content := _clean_text(value.get(source, "") or (value.get("english", "") if source == "translation" else "")):
                if target == "ref":
                    content = re.sub(r"\([^)]*(?i:please (?:add|provide|specify))[^)]*\)", "", content).strip()
                if content and not re.search(r"(?i)please (?:add|provide|specify)", content):
                    example[target] = content
        if value.get("type") == "quotation":
            example["type"] = "quotation"
        ranges = _bold_ranges(text, value.get("bold_text_offsets", []), len(raw) - len(raw.lstrip()))
        if ranges:
            example["bold"] = ranges
        translation = example.get("translation")
        if translation:
            raw_translation = value.get("translation") or value.get("english", "")
            ranges = _bold_ranges(translation, value.get("bold_translation_offsets", []), len(raw_translation) - len(raw_translation.lstrip()))
            if ranges:
                example["translationBold"] = ranges
        examples.append(example)
        seen.add(text)
        if len(examples) == 3:
            break
    return examples


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
    form_items = list(extract_form_items(entry))
    if form_items:
        processed["forms"] = list(dict.fromkeys(text for text, _ in form_items))
        details = {}
        for text, form in form_items:
            tags = form_grammar(form.tags) + labels(form.tags) + raw_labels(form.raw_tags, _clean_text)
            if tags:
                details[text] = list(dict.fromkeys(details.get(text, []) + tags))
        if details and entry.lang_code not in QUALITY_LANGUAGES:
            processed["formDetails"] = [{"form": text, "tags": tags} for text, tags in details.items()]
    pronunciation = extract_pronunciation(entry)
    if pronunciation:
        processed["pronunciation"] = pronunciation
    etymology = extract_etymology(entry)
    if etymology:
        processed["etymology"] = etymology
    details = {}
    etymology_links = extract_etymology_links(entry)
    if etymology_links:
        details["etymologyLinks"] = etymology_links
    for field in ("synonyms", "antonyms", "related", "derived"):
        refs = extract_relations(getattr(entry, field), entry.lang_code, entry.word)
        if refs:
            details[field] = refs
    if details:
        processed["details"] = details
    return enhance_record(entry, processed, _clean_text)


def make_dict_language_static_metadata(config: DictLanguageConfig):
    return {
        "code": config.code,
        "name": config.name,
        "englishWiktionaryName": config.english_wiktionary_name,
    }
