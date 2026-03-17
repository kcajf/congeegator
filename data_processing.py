#!/usr/bin/env python3
import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
import typing
import unicodedata
import urllib.parse
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Callable, Optional

import msgspec
import orjson
import polars as pl
import requests
import zstandard
from rich.pretty import pprint
from wordfreq import zipf_frequency

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

# Timestamp version of pinned source data in R2.
# Update by running: pixi run pin-source-data
SOURCE_DATA_VERSION = "2026-03-16T074135Z"


class CacheManager:
    CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
    R2_PUBLIC_URL = "https://assets.congeegator.com"

    def __init__(self):
        self._version_cache_dir = os.path.join(CacheManager.CACHE_DIR, SOURCE_DATA_VERSION)
        os.makedirs(self._version_cache_dir, exist_ok=True)

    def _stream_zstd_lines(self, path: str, chunk_size: int = 128 * 1024):
        dctx = zstandard.ZstdDecompressor()
        with open(path, "rb") as f:
            with dctx.stream_reader(f) as reader:
                buffer = b""
                while True:
                    chunk = reader.read(chunk_size)
                    if not chunk:
                        if buffer:
                            yield buffer
                        break
                    buffer += chunk
                    lines = buffer.split(b"\n")
                    buffer = lines.pop()
                    for line in lines:
                        if line:
                            yield line

    def get_lang_filtered_raw_data(self, wiki_lang: str, lang: str):
        cache_path = os.path.join(
            self._version_cache_dir, f"{wiki_lang}-{lang}-filtered.jsonl.zst"
        )
        if not os.path.exists(cache_path):
            url = f"{self.R2_PUBLIC_URL}/source-data/{SOURCE_DATA_VERSION}/{wiki_lang}-{lang}-filtered.jsonl.zst"
            log.info(f"Fetching pinned source data: {url}")

            response = requests.get(url, stream=True)
            if response.status_code == 404:
                raise RuntimeError(
                    f"Pinned source data not found at {url}\n"
                    f"Make sure source data has been uploaded for version {SOURCE_DATA_VERSION}"
                )
            response.raise_for_status()

            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=self._version_cache_dir, delete=False
                ) as temp_file:
                    temp_path = temp_file.name
                    shutil.copyfileobj(response.raw, temp_file)
                os.rename(temp_path, cache_path)
                temp_path = None
                log.info(f"Downloaded to {cache_path}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            log.info(f"Found {cache_path}")

        return self._stream_zstd_lines(cache_path)


class Form(msgspec.Struct, frozen=True):
    form: Optional[str] = None
    tags: set[str] = set()
    source: Optional[str] = None


class FormOf(msgspec.Struct, frozen=True):
    word: str
    extra: Optional[str] = None


class Sense(msgspec.Struct, frozen=True):
    form_of: tuple[FormOf, ...] = ()
    alt_of: tuple[FormOf, ...] = ()
    tags: tuple[str, ...] = ()
    categories: tuple[Any, ...] = ()
    glosses: tuple[str, ...] = ()


class HeadTemplate(msgspec.Struct, frozen=True):
    name: str
    args: dict[str, str] = {}


class EtymologyTemplate(msgspec.Struct, frozen=True):
    name: str


class EntryJustPos(msgspec.Struct, frozen=True):
    pos: str


class Entry(msgspec.Struct, frozen=True):
    pos: str
    lang_code: str
    lang: str
    word: str
    forms: tuple[Form, ...] = ()
    senses: tuple[Sense, ...] = ()
    head_templates: tuple[HeadTemplate, ...] = ()
    etymology_templates: tuple[EtymologyTemplate, ...] = ()
    categories: tuple[Any, ...] = ()


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


def strip_diacritics(s):
    # https://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-normalize-in-a-python-unicode-string/518232#518232
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def sort_without_diacritics(strings: list[str]):
    return sorted(strings, key=strip_diacritics)


def to_phonetic_el(s: str) -> str:
    """Convert a Greek or Latin string to a canonical Latin phonetic representation."""
    s = strip_diacritics(s).lower()

    # Fuse Greek consonant bigrams
    s = s.replace("μπ", "b")
    s = s.replace("ντ", "d")
    s = s.replace("γκ", "g")
    s = s.replace("γγ", "ng")
    s = s.replace("τσ", "ts")
    s = s.replace("τζ", "dz")

    # Context-sensitive αυ/ευ voicing
    voiceless = set("πτκθσφχξψ")
    result = []
    i = 0
    while i < len(s):
        # αυ/ευ voicing rules
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

    # Vowel digraphs
    s = s.replace("αι", "e")
    s = s.replace("ει", "i")
    s = s.replace("οι", "i")
    s = s.replace("ου", "U")  # placeholder — ου sounds like "u", protected from u→i
    s = s.replace("υι", "i")

    # Single vowels
    s = s.replace("η", "i")
    s = s.replace("ω", "o")
    s = s.replace("υ", "i")
    s = s.replace("α", "a")
    s = s.replace("ε", "e")
    s = s.replace("ι", "i")
    s = s.replace("ο", "o")

    # Consonants
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

    # Latin consonant bigrams (mirrors Greek μπ/ντ/γκ)
    s = s.replace("mp", "b")
    s = s.replace("nt", "d")
    s = s.replace("gk", "g")

    # Latin normalization
    s = s.replace("ph", "f")
    s = re.sub(r"c(?!h)", "k", s)
    s = s.replace("q", "k")
    s = s.replace("w", "o")
    s = s.replace("x", "ch")
    s = re.sub(r"(?<![ctk])h", "ch", s)
    s = s.replace("y", "i")

    # Latin au/eu voicing (mirrors Greek αυ/ευ rules for naive transliterations)
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

    # Latin vowel digraphs (mirrors Greek αι/ει/οι/ου)
    s = s.replace("ei", "i")
    s = s.replace("ai", "e")
    s = s.replace("oi", "i")
    s = s.replace("ou", "U")  # placeholder to protect from u→i
    s = s.replace("u", "i")  # υ is pronounced "i" in modern Greek
    s = s.replace("U", "u")  # restore ou→u

    return s


# Primary IPA Extensions
IPA_EXTENSIONS = "".join(chr(c) for c in range(0x0250, 0x02B0))

# Spacing Modifiers (includes tone marks and aspiration)
IPA_SPACING_MODIFIERS = "".join(chr(c) for c in range(0x02B0, 0x0300))

# Combining Diacritical Marks (accents, nasalization, etc.)
IPA_DIACRITICS = "".join(chr(c) for c in range(0x0300, 0x0370))

# Full IPA-related character set
IPA_ALL = IPA_EXTENSIONS + IPA_SPACING_MODIFIERS + IPA_DIACRITICS


PERSONS = ("first-person", "second-person", "third-person")
NUMBERS = ("singular", "plural")
PERSONS_NUMBERS = tuple((person, number) for number in NUMBERS for person in PERSONS)

LANG_PRONOUNS = {
    "fr": ("je", "tu", "il/elle", "nous", "vous", "ils/elles"),
    "el": ("εγώ", "εσύ", "αυτ(ος/ή/ό)", "εμείς", "εσείς", "αυτ(οί/ές/ά)"),
    "de": ("ich", "du", "er/sie/es", "wir", "ihr", "sie/Sie"),
    "es": ("yo", "tú", "él/ella/usted", "nosotros/-as", "vosotros/-as", "ellos/-as/ustedes"),
    "it": ("io", "tu", "lui/lei", "noi", "voi", "loro"),
    "en": ("I", "you", "he/she/it", "we", "you", "they"),
}

FR_SUBJ_PRONOUNS = ("que je", "que tu", "qu'il/elle", "que nous", "que vous", "qu'ils/elles")


class FormMatcher(msgspec.Struct, frozen=True):
    tags: tuple[str, ...]
    formatter: str = "{}"
    pronoun: str | None = None
    exclude_tags: tuple[str, ...] = ()
    max_forms: int | None = None

    def matches(self, form: Form) -> bool:
        for t in self.tags:
            if t not in form.tags:
                return False
        for t in self.exclude_tags:
            if t in form.tags:
                return False
        return True

    def format(self, form: Form) -> str:
        return self.formatter.format(form.form)


class TenseConfig(msgspec.Struct, frozen=True):
    name: str
    form_matchers: FormMatcher | tuple[FormMatcher, ...]
    # pronouns: tuple[str, ...] | None


class TenseGroup(msgspec.Struct, frozen=True):
    name: str
    pattern: re.Pattern


class LanguageConfig(msgspec.Struct, frozen=True):
    code: str
    name: str  # Native display name (e.g. "français", "ελληνικά")
    english_wiktionary_name: str  # English name used in Wiktionary anchors (e.g. "French")
    tenses: tuple[TenseConfig, ...]
    tense_groups: list[TenseGroup]
    phonetic_fn: Callable[[str], str] | None = None
    max_conj_tables: int | None = None  # When set, only use forms from the first N conjugation tables
    rare_tags: tuple[str, ...] = ()  # Forms with these Wiktionary tags get wrapped in [] markers
    exclude_tags: tuple[str, ...] = ()  # Forms with any of these Wiktionary tags are excluded entirely


def full_tense(
    lang: str,
    name: str,
    tags: tuple[str, ...],
    auxiliaries: tuple[str, ...] | None = None,
    exclude_tags: tuple[str, ...] = (),
    pronouns: tuple[str, ...] | None = None,
):
    lang_pronouns = pronouns if pronouns is not None else LANG_PRONOUNS[lang]
    if auxiliaries is not None:
        assert len(auxiliaries) == len(PERSONS_NUMBERS)
        matchers = tuple(
            FormMatcher(
                (*PERSONS_NUMBERS[i], *tags),
                pronoun=lang_pronouns[i],
                formatter=auxiliaries[i] + "{}",
                exclude_tags=exclude_tags,
            )
            for i in range(len(PERSONS_NUMBERS))
        )
    else:
        matchers = tuple(
            FormMatcher(
                (*PERSONS_NUMBERS[i], *tags),
                pronoun=lang_pronouns[i],
                exclude_tags=exclude_tags,
            )
            for i in range(len(PERSONS_NUMBERS))
        )

    return TenseConfig(name, matchers)


def repeated_tense(
    lang: str, name: str, tags: tuple[str, ...], auxiliaries: tuple[str, ...],
    exclude_tags: tuple[str, ...] = (),
):
    assert len(auxiliaries) == len(PERSONS_NUMBERS)
    matchers = tuple(
        FormMatcher(
            tags,
            pronoun=LANG_PRONOUNS[lang][i],
            formatter=auxiliaries[i] + " {}",
            exclude_tags=exclude_tags,
        )
        for i in range(len(PERSONS_NUMBERS))
    )

    return TenseConfig(name, matchers)


EL_THA = ("θα ", "θα ", "θα ", "θα ", "θα ", "θα ")

EL_CONFIG = LanguageConfig(
    code="el",
    name="ελληνικά",
    english_wiktionary_name="Greek",
    tenses=(
        # Indicative
        full_tense(
            "el",
            "el_indic_pres_active",
            ("present", "indicative", "imperfective", "active"),
        ),
        full_tense(
            "el",
            "el_indic_pres_passive",
            ("present", "indicative", "imperfective", "passive"),
        ),
        full_tense(
            "el",
            "el_indic_imperf_active",
            ("imperfect", "indicative", "imperfective", "active"),
        ),
        full_tense(
            "el",
            "el_indic_imperf_passive",
            ("imperfect", "indicative", "imperfective", "passive"),
        ),
        full_tense(
            "el",
            "el_indic_aorist_active",
            ("past", "indicative", "perfective", "active"),
        ),
        full_tense(
            "el",
            "el_indic_aorist_passive",
            ("past", "indicative", "perfective", "passive"),
        ),
        full_tense(
            "el",
            "el_indic_fut_cont_active",
            ("present", "indicative", "imperfective", "active"),
            auxiliaries=EL_THA,
        ),
        full_tense(
            "el",
            "el_indic_fut_cont_passive",
            ("present", "indicative", "imperfective", "passive"),
            auxiliaries=EL_THA,
        ),
        full_tense(
            "el",
            "el_indic_fut_simple_active",
            ("dependent", "indicative", "perfective", "active"),
            auxiliaries=EL_THA,
        ),
        full_tense(
            "el",
            "el_indic_fut_simple_passive",
            ("dependent", "indicative", "perfective", "passive"),
            auxiliaries=EL_THA,
        ),
        # Subjunctive
        full_tense(
            "el",
            "el_subj_perf_active",
            ("dependent", "indicative", "perfective", "active"),
        ),
        full_tense(
            "el",
            "el_subj_perf_passive",
            ("dependent", "indicative", "perfective", "passive"),
        ),
        # Imperative (2nd person only — singular + plural)
        TenseConfig(
            "el_imper_imperf_active",
            (
                FormMatcher(("second-person", "singular", "imperative", "imperfective", "active"), pronoun="εσύ"),
                FormMatcher(("second-person", "plural", "imperative", "imperfective", "active"), pronoun="εσείς"),
            ),
        ),
        TenseConfig(
            "el_imper_perf_active",
            (
                FormMatcher(("second-person", "singular", "imperative", "perfective", "active"), pronoun="εσύ"),
                FormMatcher(("second-person", "plural", "imperative", "perfective", "active"), pronoun="εσείς"),
            ),
        ),
        TenseConfig(
            "el_imper_imperf_passive",
            (
                FormMatcher(("second-person", "singular", "imperative", "imperfective", "passive"), pronoun="εσύ"),
                FormMatcher(("second-person", "plural", "imperative", "imperfective", "passive"), pronoun="εσείς"),
            ),
        ),
        TenseConfig(
            "el_imper_perf_passive",
            (
                FormMatcher(("second-person", "singular", "imperative", "perfective", "passive"), pronoun="εσύ"),
                FormMatcher(("second-person", "plural", "imperative", "perfective", "passive"), pronoun="εσείς"),
            ),
        ),
        # Other forms (participles, infinitives)
        TenseConfig("el_impers_pres_parti_active", FormMatcher(("active", "present", "participle"))),
        TenseConfig("el_impers_past_parti_passive", FormMatcher(("passive", "past", "participle"))),
        TenseConfig("el_impers_pres_parti_passive", FormMatcher(("passive", "present", "participle"))),
        TenseConfig("el_impers_inf_aorist_active", FormMatcher(("active", "infinitive-aorist"))),
        TenseConfig("el_impers_inf_aorist_passive", FormMatcher(("passive", "infinitive-aorist"))),
    ),
    tense_groups=[
        TenseGroup("el_indic", re.compile(r"^el_indic_")),
        TenseGroup("el_subj", re.compile(r"^el_subj_")),
        TenseGroup("el_imper", re.compile(r"^el_imper_(?!s_)")),
        TenseGroup("el_impers", re.compile(r"^el_impers_")),
    ],
    phonetic_fn=to_phonetic_el,
    exclude_tags=("dated", "archaic"),
    rare_tags=("rare",),
)


FR_PRES_INDIC_AVOIR = ("ai", "as", "a", "avons", "avez", "ont")
FR_IMPERF_INDIC_AVOIR = ("avais", "avais", "avait", "avions", "aviez", "avaient")
FR_PAST_HIST_INDIC_AVOIR = ("eus", "eus", "eut", "eûmes", "eûtes", "eurent")
FR_FUT_INDIC_AVOIR = ("aurai", "auras", "aura", "aurons", "aurez", "auront")

FR_CONFIG = LanguageConfig(
    code="fr",
    name="français",
    english_wiktionary_name="French",
    tenses=(
        TenseConfig("fr_impers_pres_partic", FormMatcher(("participle", "present"), exclude_tags=("multiword-construction",))),
        TenseConfig("fr_impers_past_partic", FormMatcher(("participle", "past"))),
        full_tense("fr", "fr_indic_pres", ("present", "indicative")),
        full_tense("fr", "fr_indic_imperf", ("imperfect", "indicative")),
        full_tense("fr", "fr_indic_past_hist", ("past", "historic", "indicative")),
        full_tense("fr", "fr_indic_fut", ("future", "indicative")),
        full_tense("fr", "fr_cond_pres", ("conditional",)),
        TenseConfig(
            "fr_imper_pres",
            (
                FormMatcher(("second-person", "singular", "imperative"), pronoun="(tu)"),
                FormMatcher(("first-person", "plural", "imperative"), pronoun="(nous)"),
                FormMatcher(("second-person", "plural", "imperative"), pronoun="(vous)"),
            ),
        ),
        full_tense("fr", "fr_subj_pres", ("subjunctive", "present"), pronouns=FR_SUBJ_PRONOUNS),
        full_tense("fr", "fr_subj_imperf", ("subjunctive", "imperfect"), pronouns=FR_SUBJ_PRONOUNS),
        repeated_tense(
            "fr", "fr_indic_pres_perf", ("participle", "past"), FR_PRES_INDIC_AVOIR
        ),
        repeated_tense(
            "fr", "fr_indic_pluperf", ("participle", "past"), FR_IMPERF_INDIC_AVOIR
        ),
        repeated_tense(
            "fr", "fr_indic_past_ant", ("participle", "past"), FR_PAST_HIST_INDIC_AVOIR
        ),
        repeated_tense(
            "fr", "fr_indic_fut_perf", ("participle", "past"), FR_FUT_INDIC_AVOIR
        ),
    ),
    tense_groups=[
        TenseGroup("fr_indic", re.compile(r"^fr_indic_")),
        TenseGroup("fr_subj", re.compile(r"^fr_subj_")),
        TenseGroup("fr_cond", re.compile(r"^fr_cond_")),
        TenseGroup("fr_imper", re.compile(r"^fr_imper_(?!s_)")),
        TenseGroup("fr_impers", re.compile(r"^fr_impers_")),
    ],
    max_conj_tables=2,
)

DE_CONFIG = LanguageConfig(
    code="de",
    name="Deutsch",
    english_wiktionary_name="German",
    tenses=(
        full_tense("de", "de_indic_pres", ("present", "indicative")),
        full_tense("de", "de_indic_preterite", ("preterite",)),
        full_tense("de", "de_indic_perfect", ("perfect", "indicative")),
        full_tense("de", "de_indic_pluperfect", ("pluperfect", "indicative")),
        full_tense("de", "de_indic_fut_i", ("future-i", "indicative")),
        full_tense("de", "de_indic_fut_ii", ("future-ii", "indicative")),
        TenseConfig("de_impers_infinitive", FormMatcher(("infinitive",), exclude_tags=("multiword-construction",))),
        TenseConfig("de_impers_pres_partic", FormMatcher(("participle", "present"))),
        TenseConfig("de_impers_past_partic", FormMatcher(("participle", "past"))),
        full_tense("de", "de_subj_i", ("subjunctive", "subjunctive-i"), exclude_tags=("multiword-construction",)),
        full_tense("de", "de_subj_i_perfect", ("perfect", "subjunctive")),
        full_tense("de", "de_subj_i_fut_i", ("future-i", "subjunctive-i")),
        full_tense("de", "de_subj_i_fut_ii", ("future-ii", "subjunctive-i")),
        full_tense("de", "de_subj_ii", ("subjunctive", "subjunctive-ii"), exclude_tags=("multiword-construction",)),
        full_tense("de", "de_subj_ii_pluperfect", ("pluperfect", "subjunctive")),
        full_tense("de", "de_subj_ii_fut_i", ("future-i", "subjunctive-ii")),
        full_tense("de", "de_subj_ii_fut_ii", ("future-ii", "subjunctive-ii")),
    ),
    tense_groups=[
        TenseGroup("de_indic", re.compile(r"^de_indic_")),
        TenseGroup("de_impers", re.compile(r"^de_impers_")),
        TenseGroup("de_subj_i_grp", re.compile(r"^de_subj_i($|_)")),
        TenseGroup("de_subj_ii_grp", re.compile(r"^de_subj_ii($|_)")),
    ],
    rare_tags=("archaic",),
)
ES_PRES_INDIC_HABER = ("he", "has", "ha", "hemos", "habéis", "han")
ES_IMPERF_INDIC_HABER = ("había", "habías", "había", "habíamos", "habíais", "habían")

ES_CONFIG = LanguageConfig(
    code="es",
    name="español",
    english_wiktionary_name="Spanish",
    tenses=(
        # Impersonal
        TenseConfig("es_impers_inf", FormMatcher(("infinitive",), max_forms=1)),
        TenseConfig("es_impers_gerund", FormMatcher(("gerund",), max_forms=1)),
        TenseConfig("es_impers_past_partic", FormMatcher(("participle", "past"), exclude_tags=("feminine", "plural"))),
        # Indicative
        full_tense("es", "es_indic_pres", ("present", "indicative"), exclude_tags=("vos-form",)),
        full_tense("es", "es_indic_pret", ("preterite", "indicative"), exclude_tags=("vos-form",)),
        full_tense("es", "es_indic_imperf", ("imperfect", "indicative"), exclude_tags=("vos-form",)),
        full_tense("es", "es_indic_fut", ("future", "indicative"), exclude_tags=("vos-form",)),
        repeated_tense(
            "es", "es_indic_pres_perf", ("participle", "past", "masculine", "singular"), ES_PRES_INDIC_HABER
        ),
        repeated_tense(
            "es", "es_indic_pluperf", ("participle", "past", "masculine", "singular"), ES_IMPERF_INDIC_HABER
        ),
        # Conditional
        full_tense("es", "es_cond_pres", ("conditional",), exclude_tags=("vos-form",)),
        # Subjunctive
        full_tense("es", "es_subj_pres", ("present", "subjunctive"), exclude_tags=("vos-form",)),
        full_tense("es", "es_subj_imperf", ("imperfect", "subjunctive"), exclude_tags=("vos-form",)),
        # Imperative (5 forms — no 1st person singular)
        TenseConfig(
            "es_imper",
            (
                FormMatcher(("second-person", "singular", "imperative"), pronoun="tú", exclude_tags=("vos-form",)),
                FormMatcher(("third-person", "singular", "imperative"), pronoun="usted"),
                FormMatcher(("first-person", "plural", "imperative"), pronoun="nosotros/-as"),
                FormMatcher(("second-person", "plural", "imperative"), pronoun="vosotros/-as"),
                FormMatcher(("third-person", "plural", "imperative"), pronoun="ustedes"),
            ),
        ),
    ),
    tense_groups=[
        TenseGroup("es_indic", re.compile(r"^es_indic_")),
        TenseGroup("es_subj", re.compile(r"^es_subj_")),
        TenseGroup("es_cond", re.compile(r"^es_cond_")),
        TenseGroup("es_imper", re.compile(r"^es_imper$")),
        TenseGroup("es_impers", re.compile(r"^es_impers_")),
    ],
)

IT_PRES_INDIC_AVERE = ("ho", "hai", "ha", "abbiamo", "avete", "hanno")
IT_IMPERF_INDIC_AVERE = ("avevo", "avevi", "aveva", "avevamo", "avevate", "avevano")
IT_PAST_HIST_AVERE = ("ebbi", "avesti", "ebbe", "avemmo", "aveste", "ebbero")
IT_FUT_INDIC_AVERE = ("avrò", "avrai", "avrà", "avremo", "avrete", "avranno")
IT_COND_AVERE = ("avrei", "avresti", "avrebbe", "avremmo", "avreste", "avrebbero")
IT_PRES_SUBJ_AVERE = ("abbia", "abbia", "abbia", "abbiamo", "abbiate", "abbiano")
IT_IMPERF_SUBJ_AVERE = ("avessi", "avessi", "avesse", "avessimo", "aveste", "avessero")

IT_CONFIG = LanguageConfig(
    code="it",
    name="italiano",
    english_wiktionary_name="Italian",
    tenses=(
        # Impersonal
        TenseConfig("it_impers_inf", FormMatcher(("infinitive",), max_forms=1)),
        TenseConfig("it_impers_gerund", FormMatcher(("gerund",), max_forms=1)),
        TenseConfig("it_impers_pres_partic", FormMatcher(("participle", "present"))),
        TenseConfig("it_impers_past_partic", FormMatcher(("participle", "past"))),
        # Indicative
        full_tense("it", "it_indic_pres", ("present", "indicative")),
        full_tense("it", "it_indic_imperf", ("imperfect", "indicative")),
        full_tense("it", "it_indic_past_hist", ("past", "historic", "indicative")),
        full_tense("it", "it_indic_fut", ("future", "indicative")),
        repeated_tense("it", "it_indic_pres_perf", ("participle", "past"), IT_PRES_INDIC_AVERE),
        repeated_tense("it", "it_indic_pluperf", ("participle", "past"), IT_IMPERF_INDIC_AVERE),
        repeated_tense("it", "it_indic_past_ant", ("participle", "past"), IT_PAST_HIST_AVERE),
        repeated_tense("it", "it_indic_fut_perf", ("participle", "past"), IT_FUT_INDIC_AVERE),
        # Conditional
        full_tense("it", "it_cond_pres", ("conditional",)),
        repeated_tense("it", "it_cond_past", ("participle", "past"), IT_COND_AVERE),
        # Subjunctive
        full_tense("it", "it_subj_pres", ("present", "subjunctive")),
        full_tense("it", "it_subj_imperf", ("imperfect", "subjunctive")),
        repeated_tense("it", "it_subj_past", ("participle", "past"), IT_PRES_SUBJ_AVERE),
        repeated_tense("it", "it_subj_pluperf", ("participle", "past"), IT_IMPERF_SUBJ_AVERE),
        # Imperative (3 forms — 2sg, 1pl, 2pl)
        TenseConfig(
            "it_imper",
            (
                FormMatcher(("second-person", "singular", "imperative"), pronoun="(tu)", exclude_tags=("negative", "formal")),
                FormMatcher(("first-person", "plural", "imperative"), pronoun="(noi)", exclude_tags=("negative",)),
                FormMatcher(("second-person", "plural", "imperative"), pronoun="(voi)", exclude_tags=("negative",)),
            ),
        ),
    ),
    tense_groups=[
        TenseGroup("it_indic", re.compile(r"^it_indic_")),
        TenseGroup("it_subj", re.compile(r"^it_subj_")),
        TenseGroup("it_cond", re.compile(r"^it_cond_")),
        TenseGroup("it_imper", re.compile(r"^it_imper$")),
        TenseGroup("it_impers", re.compile(r"^it_impers_")),
    ],
    max_conj_tables=2,
    rare_tags=("archaic", "literary", "dialectal", "poetic"),
)

EN_PRES_HAVE = ("have", "have", "has", "have", "have", "have")
EN_PAST_HAVE = ("had", "had", "had", "had", "had", "had")
EN_WILL = ("will", "will", "will", "will", "will", "will")

EN_EXCLUDE = ("archaic", "dialectal")

EN_CONFIG = LanguageConfig(
    code="en",
    name="English",
    english_wiktionary_name="English",
    tenses=(
        # Impersonal
        TenseConfig("en_impers_inf", FormMatcher(("infinitive",), max_forms=1)),
        TenseConfig("en_impers_pres_partic", FormMatcher(("participle", "present"), max_forms=1, exclude_tags=EN_EXCLUDE)),
        TenseConfig("en_impers_past_partic", FormMatcher(("participle", "past"), max_forms=1, exclude_tags=EN_EXCLUDE)),
        # Indicative present — explicit matchers because Wiktionary plural forms lack person tags
        TenseConfig("en_indic_pres", (
            FormMatcher(("first-person", "singular", "present"), pronoun="I", exclude_tags=EN_EXCLUDE),
            FormMatcher(("second-person", "singular", "present"), pronoun="you", exclude_tags=EN_EXCLUDE),
            FormMatcher(("third-person", "singular", "present"), pronoun="he/she/it", exclude_tags=EN_EXCLUDE),
            FormMatcher(("plural", "present"), pronoun="we", exclude_tags=EN_EXCLUDE, max_forms=1),
            FormMatcher(("plural", "present"), pronoun="you", exclude_tags=EN_EXCLUDE, max_forms=1),
            FormMatcher(("plural", "present"), pronoun="they", exclude_tags=EN_EXCLUDE, max_forms=1),
        )),
        # Indicative past
        TenseConfig("en_indic_past", (
            FormMatcher(("first-person", "singular", "past"), pronoun="I", exclude_tags=EN_EXCLUDE),
            FormMatcher(("second-person", "singular", "past"), pronoun="you", exclude_tags=EN_EXCLUDE),
            FormMatcher(("third-person", "singular", "past"), pronoun="he/she/it", exclude_tags=EN_EXCLUDE),
            FormMatcher(("plural", "past"), pronoun="we", exclude_tags=EN_EXCLUDE, max_forms=1),
            FormMatcher(("plural", "past"), pronoun="you", exclude_tags=EN_EXCLUDE, max_forms=1),
            FormMatcher(("plural", "past"), pronoun="they", exclude_tags=EN_EXCLUDE, max_forms=1),
        )),
        # Compound
        repeated_tense("en", "en_indic_pres_perf", ("participle", "past"), EN_PRES_HAVE, exclude_tags=EN_EXCLUDE),
        repeated_tense("en", "en_indic_past_perf", ("participle", "past"), EN_PAST_HAVE, exclude_tags=EN_EXCLUDE),
        repeated_tense("en", "en_indic_fut", ("infinitive",), EN_WILL, exclude_tags=EN_EXCLUDE),
    ),
    tense_groups=[
        TenseGroup("en_indic", re.compile(r"^en_indic_")),
        TenseGroup("en_impers", re.compile(r"^en_impers_")),
    ],
)

CONFIG: list[LanguageConfig] = [
    FR_CONFIG,
    EL_CONFIG,
    DE_CONFIG,
    ES_CONFIG,
    IT_CONFIG,
    EN_CONFIG,
]


def structure_map(f, s):
    if isinstance(s, list):
        return [structure_map(f, x) for x in s]
    if isinstance(s, tuple):
        return tuple(structure_map(f, x) for x in s)
    if isinstance(s, dict):
        return {k: structure_map(f, v) for k, v in s.items()}
    return f(s)


def _strip_markers(s: str) -> tuple[str, str, str]:
    """Strip Wiktionary frequency/register markers from a form.

    Returns (prefix_markers, bare_form, suffix_markers).
    E.g. '[{foo}]' -> ('[{', 'foo', '}]')
    """
    prefix = ""
    suffix = ""
    openers = "([{"
    closers = "}])"
    while s and s[0] in openers:
        prefix += s[0]
        s = s[1:]
    while s and s[-1] in closers:
        suffix = s[-1] + suffix
        s = s[:-1]
    return prefix, s, suffix


_SUPERSCRIPT_DIGITS = str.maketrans("", "", "¹²³⁴⁵⁶⁷⁸⁹⁰")


_MATCHING_CLOSER = {"(": ")", "[": "]", "{": "}"}


def _strip_balanced_markers(s: str) -> tuple[str, str, str]:
    """Strip matched outer bracket pairs from a form.

    Unlike _strip_markers, only strips balanced pairs (e.g. `[...(...)...]`
    strips the outer `[]` but not the inner `()`).
    """
    prefix = ""
    suffix = ""
    while s and s[0] in _MATCHING_CLOSER:
        closer = _MATCHING_CLOSER[s[0]]
        if s.endswith(closer):
            prefix += s[0]
            suffix = closer + suffix
            s = s[1:-1]
        else:
            break
    return prefix, s, suffix


def _expand_el_part(part: str) -> list[str]:
    """Expand a single Greek form part, handling comma-separated sub-items.

    Drops suffix abbreviations (forms starting with `-` after stripping markers).
    For comma-separated items inside markers like `[foo, (-bar)]`, splits them
    and re-wraps each with the outer markers.
    """
    pre, bare, suf = _strip_balanced_markers(part)
    if bare.startswith("-"):
        return []

    # Handle comma-separated sub-items inside markers
    if ", " in bare and pre:
        sub_items = bare.split(", ")
        expanded = []
        for sub in sub_items:
            _, sub_bare, _ = _strip_balanced_markers(sub.strip())
            if sub_bare.startswith("-"):
                continue
            expanded.append(f"{pre}{sub.strip()}{suf}")
        return expanded

    return [part]


def preprocess_el_forms(forms: list[Form]) -> list[Form]:
    """Split Greek ` - ` variant forms into individual Form objects.

    Wiktionary encodes variant forms like `ευχαριστιέμαι¹ - ευχαριστούμαι`.
    Splitting them lets downstream processing (θα prefix, deduplication)
    work correctly on each variant. Suffix abbreviations (parts starting
    with `-` like `(-ιόσαστε)`) are dropped since they're only meaningful
    within the compound notation. Em dashes and superscripts are stripped.
    Comma-separated sub-items inside markers are expanded individually.
    """
    result: list[Form] = []
    for form in forms:
        text = form.form
        if text is None:
            result.append(form)
            continue

        # Normalize non-breaking hyphens and strip superscript digits
        text = text.replace("\u2011", "-")
        text = text.translate(_SUPERSCRIPT_DIGITS)

        # Strip trailing parenthesized annotations (cross-refs, variant notes)
        text = re.sub(r'\s*\([^)]*\)\s*$', '', text).strip()

        # Collect individual parts: split on ` - ` if present
        if " - " in text:
            raw_parts = [p.strip() for p in text.split(" - ")]
        else:
            raw_parts = [text]

        for part in raw_parts:
            if part == "—" or part == "":
                continue
            for expanded in _expand_el_part(part):
                result.append(Form(form=expanded, tags=form.tags, source=form.source))

    return result


def _is_de_volle_endung_pair(a: str, b: str) -> tuple[str, str] | None:
    """Detect if two German forms are a volle Endung (full ending) pair.

    Returns (common_form, formal_form) or None.
    E.g. ("gingst", "gingest") or ("seist gegangen", "seiest gegangen").
    """
    words_a = a.split()
    words_b = b.split()
    if len(words_a) != len(words_b):
        return None

    # Find the single differing word
    diffs = [
        (i, wa, wb)
        for i, (wa, wb) in enumerate(zip(words_a, words_b))
        if wa != wb
    ]
    if len(diffs) != 1:
        return None

    _, wa, wb = diffs[0]

    # Check suffix pairs: -st/-est first (more specific), then -t/-et
    for short_suf, long_suf in [("st", "est"), ("t", "et")]:
        if wa.endswith(short_suf) and wb.endswith(long_suf):
            if wa[: -len(short_suf)] == wb[: -len(long_suf)] and wa[: -len(short_suf)]:
                return (a, b)  # a is common, b is formal
        if wb.endswith(short_suf) and wa.endswith(long_suf):
            if wb[: -len(short_suf)] == wa[: -len(long_suf)] and wb[: -len(short_suf)]:
                return (b, a)  # b is common, a is formal

    return None


def clean_up_matched_forms(
    l: LanguageConfig, forms: list[str], entry: Entry
) -> list[str]:
    forms = [f.replace("‑", "-") for f in forms]

    if l.code == "el":
        new_forms = [*forms]
        suffix_replacements = [
            # existing (these expand archaic/formal variants)
            ("ουμε", "ομε"),
            ("ιέστε", "ιόσαστε"),
            ("ιούνται", "ιόνται"),
            ("όμαστε", "ώμεθα"),
            ("άστε", "άσθε"),
            # new: imperfect passive alternates
            ("όμασταν", "όμαστε"),
            ("όσασταν", "όσαστε"),
            ("ιόμασταν", "ιόμαστε"),
            ("ούμασταν", "ούμαστε"),
            # imperfect passive 2pl alternates
            ("ιόσασταν", "ιόσαστε"),
            ("ούσασταν", "ούσαστε"),
            # new: participle gender endings
            ("ος", "η"),
            ("ος", "ο"),
        ]
        for i, f in enumerate(forms):
            if i > 0:
                pre, bare_f, suf = _strip_markers(f)
                # Extract word prefix before dash (e.g. "θα " from "θα -ομε")
                word_prefix = ""
                dash_part = bare_f
                space_dash = bare_f.rfind(" -")
                if space_dash >= 0:
                    word_prefix = bare_f[: space_dash + 1]
                    dash_part = bare_f[space_dash + 1 :]

                expanded_ok = False
                for from_, to in suffix_replacements:
                    if dash_part == f"-{to}":
                        for j in range(i - 1, -1, -1):
                            _, bare_base, _ = _strip_markers(new_forms[j])
                            # Strip same word prefix from base
                            if word_prefix:
                                if not bare_base.startswith(word_prefix):
                                    continue
                                bare_base = bare_base[len(word_prefix) :]
                            if bare_base.endswith(from_):
                                expanded = bare_base[: -len(from_)] + to
                                new_forms[i] = f"{pre}{word_prefix}{expanded}{suf}"
                                expanded_ok = True
                                break
                        if expanded_ok:
                            break

        for f in new_forms:
            if "-" in f and len(f) > 1:
                log.warning(f"dodgy-looking form in {entry.word}: {f}")
        return new_forms

    if l.code == "de" and len(forms) == 2:
        result = _is_de_volle_endung_pair(forms[0], forms[1])
        if result is not None:
            common, formal = result
            return [common, "{" + formal + "}"]

    return forms


def filter_forms_by_table(
    all_forms: list[Form], max_tables: int
) -> list[Form]:
    """Filter forms to only include those from the first `max_tables` conjugation tables.

    Table boundaries are identified by `table-tags` entries in the unfiltered forms list.
    Forms before the first table-tags entry are in table 1.
    """
    table_num = 1
    result: list[Form] = []
    for form in all_forms:
        if "table-tags" in form.tags:
            table_num += 1
            continue
        if table_num > max_tables:
            continue
        if form_is_clean_conjugation(form):
            result.append(form)
    return result


def extract_one(
    l: LanguageConfig, matcher: FormMatcher, forms: list[Form], entry: Entry
) -> str:
    seen = set()
    ret: list[str] = []
    for form in forms:
        if form.source != "conjugation":
            continue
        assert form.form is not None
        if matcher.matches(form):
            if l.exclude_tags and form.tags & set(l.exclude_tags):
                continue
            formatted = matcher.format(form)
            if l.rare_tags and form.tags & set(l.rare_tags):
                formatted = f"[{formatted}]"
            if formatted in seen:
                continue
            ret.append(formatted)
            seen.add(formatted)
            if matcher.max_forms is not None and len(ret) >= matcher.max_forms:
                break
    ret = clean_up_matched_forms(l, ret, entry)
    ret = list(dict.fromkeys(ret))  # deduplicate preserving order
    return "/".join(ret)


def extract_tense(l: LanguageConfig, t: TenseConfig, forms: list[Form], entry: Entry):
    if isinstance(t.form_matchers, FormMatcher):
        x = extract_one(l, t.form_matchers, forms, entry)
    elif isinstance(t.form_matchers, tuple):
        x = tuple(extract_one(l, fm, forms, entry) for fm in t.form_matchers)
    else:
        typing.assert_never(t.form_matchers)
    return x


def extract_conjugations_from_forms(
    config: LanguageConfig, forms: list[Form], entry: Entry
):
    return {t.name: extract_tense(config, t, forms, entry) for t in config.tenses}


def form_is_clean_conjugation(form: Form) -> bool:
    if form.source != "conjugation":
        return False
    if form.form is None:
        return False
    if form.form in {
        "-",
        "Formed using present",
        "dependent (for simple past)",
        "present perfect from above with a particle (να, ας).",
        "no-table-tags",
    }:
        return False
    if "table-tags" in form.tags:
        return False
    if "inflection-template" in form.tags:
        return False
    if "combined-form" in form.tags:
        return False
    if "negative" in form.tags:
        return False

    if "'" in form.form:  # French "t'es"
        return False
    if '{' in form.form:  # Greek katharevousa/formal forms
        return False

    if " " in form.form and " - " not in form.form:
        # Allow German compound tenses (e.g. "habe gemacht") but reject
        # French reflexive forms ("me suis") and template descriptions
        # ("avoir + past participle").
        if "multiword-construction" not in form.tags or "+" in form.form:
            return False

    for c in IPA_ALL:
        if c in form.form:
            return False
    return True


def count_conjs(thing) -> int:
    n = 0
    if isinstance(thing, str):
        n += thing != ""
    elif isinstance(thing, dict):
        for _, v in thing.items():
            n += count_conjs(v)
    elif isinstance(thing, (tuple, list)):
        for x in thing:
            n += count_conjs(x)
    else:
        raise ValueError(thing)
    return n


def _orjson_dump(obj: Any, pretty: bool = False) -> bytes:
    opts = orjson.OPT_NON_STR_KEYS
    if pretty:
        opts |= orjson.OPT_INDENT_2
    return orjson.dumps(obj, option=opts)


def write_language_data(data: dict[str, Any], lang_dir: str, pretty: bool = False):
    os.makedirs(lang_dir, exist_ok=True)

    # full data file
    out_path = os.path.join(lang_dir, "data.json")
    with open(out_path, "wb") as f:
        f.write(_orjson_dump(data, pretty))
    log.info(f"Wrote {out_path}")

    # single verbs file
    single_verbs_dir = os.path.join(lang_dir, "verbs")
    os.makedirs(single_verbs_dir)
    for verb_data in data["verbs"]:
        with open(
            os.path.join(single_verbs_dir, f"{verb_data['name']}.json"), "wb"
        ) as f:
            f.write(_orjson_dump(verb_data, pretty))

    # index file
    with open(os.path.join(lang_dir, "index.json"), "wb") as f:
        names = [x["name"] for x in data["verbs"]]
        f.write(_orjson_dump(names, pretty))


def make_language_static_metadata(config: LanguageConfig):
    tense_names: list[str] = []
    tense_pronouns: list[list[str] | None] = []
    for t in config.tenses:
        tense_names.append(t.name)
        if isinstance(t.form_matchers, FormMatcher):
            tense_pronouns.append([])
        else:
            tense_pronouns.append([f.pronoun or "" for f in t.form_matchers])

    tense_groups: list[dict[str, Any]] = []
    for g in config.tense_groups:
        matching_tenses = [
            tense_names.index(t.name) for t in config.tenses if g.pattern.match(t.name)
        ]
        tense_groups.append(dict(name=g.name, tenseIndices=matching_tenses))

    return {
        "code": config.code,
        "name": config.name,
        "englishWiktionaryName": config.english_wiktionary_name,
        "tenseNames": tense_names,
        "tensePronouns": tense_pronouns,
        "tenseGroups": tense_groups,
    }


def write_data_manifest(data_dir: str):
    language_hashes = {}
    for config in CONFIG:
        data_path = os.path.join(data_dir, config.code, "data.json")
        if not os.path.exists(data_path):
            continue

        data_size = os.path.getsize(data_path)

        with open(data_path, "rb") as f:
            h = hashlib.file_digest(f, "md5").hexdigest()[:8]

        hashed_data_dir = os.path.join(data_dir, f"{config.code}-{h}")
        os.rename(os.path.join(data_dir, config.code), hashed_data_dir)

        log.info(f"{config.code}: dataHash={h} dataSize={data_size}")

        language_hashes[config.code] = {
            "dataHash": h,
            "dataSize": data_size,
            **make_language_static_metadata(config),
        }

    path = os.path.join("src", "lib", "data-manifest.json")
    log.info(f"Writing {path}")
    with open(path, "w") as f:
        json.dump(
            {
                "languages": language_hashes,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def entry_is_clean_verb_root(entry: Entry) -> bool:
    if entry.pos == "hard-redirect":
        return False

    if entry.pos != "verb":
        return False

    if entry.word is None:
        return False

    if "'" in entry.word:  # French "'a"
        return False

    if "-" in entry.word:  # Greek '-βιβάζω'
        return False

    if entry.senses and all(
        "form-of" in s.tags or "alt-of" in s.tags for s in entry.senses
    ):
        return False

    for h in entry.head_templates:
        if entry.lang_code == "el" and h.name == "el-part":
            return False  # past participle

    for h in entry.etymology_templates:
        if h.name == "participle of":
            return False  # past participle
        if h.name == "abbrev":
            return False  # abbreviation

    BAD_CATEGORIES = {
        f"{entry.lang} verb forms",
        f"{entry.lang} multiword forms",
        f"{entry.lang} multiword terms",
        f"{entry.lang} idioms",
        f"{entry.lang} terms in nonstandard scripts",
    }

    for c in _cat_names(entry.categories):
        if c in BAD_CATEGORIES:
            return False

    if entry.senses and all(
        any(c in BAD_CATEGORIES for c in _cat_names(s.categories)) for s in entry.senses
    ):
        return False

    return True


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
    """Extract up to 3 diverse English glosses from an entry's senses.

    Uses glosses[-1] (the specific definition) rather than glosses[0] (often a
    category header like "As an auxiliary verb:"). Deduplicates by category header
    to get diverse meanings across sense groups. Appends "..." when more senses exist.

    Filters out meta-glosses (grammar notes, "synonym of", etc.) and strips
    bracketed context ([with dative 'to someone']) from definitions.
    """
    valid_senses = [
        s for s in entry.senses if not s.form_of and not s.alt_of and s.glosses
    ]
    if not valid_senses:
        return None

    # Deduplicate by category header (glosses[0]) to pick one sense per group,
    # e.g. one from "As an auxiliary verb:", one from "As a copulative verb:", etc.
    seen_headers: set[str] = set()
    glosses: list[str] = []
    for sense in valid_senses:
        header = sense.glosses[0] if len(sense.glosses) > 1 else ""
        if header in seen_headers:
            continue
        if header:
            seen_headers.add(header)
        # Use glosses[-1] — the specific definition, not glosses[0] which is
        # often a category header like "As an auxiliary verb:"
        gloss = sense.glosses[-1][0].lower() + sense.glosses[-1][1:]
        # Skip meta-glosses (grammar notes, "synonym of", etc.)
        if _is_junk_gloss(gloss):
            continue
        # Strip parenthetical clarifications for brevity
        gloss = re.sub(r"\s*\(.*?\)", "", gloss).strip()
        # Strip bracketed context (grammar notes like [with dative 'to someone'])
        gloss = re.sub(r"\s*\[.*?\]", "", gloss).strip()
        # Take first clause only — Wiktionary glosses can contain semicolons
        gloss = gloss.split(";")[0].strip()
        # Normalise trailing punctuation
        gloss = gloss.rstrip(".")
        if gloss and gloss not in glosses:
            glosses.append(gloss)
        if len(glosses) >= 3:
            break

    if not glosses:
        return None

    result = "; ".join(glosses)
    if len(valid_senses) > len(glosses):
        result += "; ..."
    return result


def fr_is_aspirated(entry: Entry) -> bool:
    cat = "French terms with aspirated h"
    if cat in _cat_names(entry.categories):
        return True
    for s in entry.senses:
        if cat in _cat_names(s.categories):
            return True
    return False


def build_search_index(
    verbs: list[dict[str, Any]],
    phonetic_fn: Callable[[str], str] | None = None,
) -> dict[str, list[int]]:
    log.info("generating search index")
    searchable_words = defaultdict[str, set[int]](lambda: set())

    GERMAN_AUXILIARY_INFINITIVES = {"haben", "sein"}

    def add_to_index(s: str, idx: int):
        if s == "" or s == "-":
            return
        for ss in s.split("/"):
            if ' ' in ss:
                words = ss.split(' ')
                if len(words) >= 3 and words[-1] in GERMAN_AUXILIARY_INFINITIVES:
                    ss = words[-2]
                else:
                    ss = words[-1]
            searchable_words[ss].add(idx)
            searchable_words[strip_diacritics(ss)].add(idx)
            if phonetic_fn:
                phonetic = phonetic_fn(ss)
                if phonetic != ss and phonetic != strip_diacritics(ss):
                    searchable_words[phonetic].add(idx)

    for i, v in enumerate(verbs):
        searchable_words[v["name"]].add(i)
        searchable_words[strip_diacritics(v["name"])].add(i)
        if phonetic_fn:
            phonetic = phonetic_fn(v["name"])
            if phonetic != v["name"] and phonetic != strip_diacritics(v["name"]):
                searchable_words[phonetic].add(i)
        for c in v["conjugation"]:
            if isinstance(c, str):
                add_to_index(c, i)
            else:
                for cc in c:
                    add_to_index(cc, i)

    index = defaultdict[str, set[int]](lambda: set())

    MIN_PREFIX = 1
    MAX_PREFIX = 4
    MAX_PREFIX_IDS = 200

    for word, indices in searchable_words.items():
        for prefix_len in range(MIN_PREFIX, MAX_PREFIX + 1):
            word_prefix = word[:prefix_len].lower()
            for i in indices:
                index[word_prefix].add(i)

    ret = {k: sorted(v)[:MAX_PREFIX_IDS] for k, v in index.items()}

    max_hits = 0
    max_key = None
    for k, v in ret.items():
        if len(v) > max_hits:
            max_hits = len(v)
            max_key = k

    log.info(f"Longest index entry: '{max_key}', {max_hits} hits")

    return ret


# Stop words for gloss search index: standard English function words (3+ chars)
# plus gloss-specific noise words that appear in many definitions.
GLOSS_STOP_WORDS = frozenset(
    {
        # Standard English function words (3+ chars)
        "the",
        "and",
        "for",
        "not",
        "out",
        "off",
        "has",
        "are",
        "was",
        "but",
        "can",
        "may",
        "all",
        "any",
        "its",
        "also",
        "been",
        "into",
        "from",
        "with",
        "that",
        "this",
        "than",
        "when",
        "very",
        "more",
        "most",
        "such",
        "other",
        # Gloss-specific noise
        "something",
        "someone",
        "oneself",
        "one's",
        "etc",
        "e.g",
        "e.g.",
        "especially",
        "synonym",
        "spelling",
        "chiefly",
        "usually",
        "often",
        "sometimes",
    }
)

MIN_GLOSS_WORD_LENGTH = 3


def build_gloss_index(verbs: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Build a whole-word index mapping English gloss words to verb IDs.

    Unlike the main search index which uses prefix expansion (1-4 char keys),
    this index uses whole words as keys. This keeps the index small and avoids
    low-quality partial matches on common English words.
    """
    log.info("generating gloss index")
    word_to_ids: defaultdict[str, set[int]] = defaultdict(set)

    for i, v in enumerate(verbs):
        gloss = v.get("gloss", "")
        if not gloss:
            continue
        for clause in gloss.split("; "):
            if clause == "...":
                continue
            if _is_junk_gloss(clause):
                continue
            # Strip bracketed context
            clause = re.sub(r"\s*\[.*?\]", "", clause)
            for token in re.split(r"[\s,;]+", clause.lower()):
                word = token.strip("().[]'\"")
                if len(word) >= MIN_GLOSS_WORD_LENGTH and word not in GLOSS_STOP_WORDS:
                    word_to_ids[word].add(i)

    MAX_PREFIX_IDS = 200
    ret = {k: sorted(v)[:MAX_PREFIX_IDS] for k, v in word_to_ids.items()}
    log.info(f"Gloss index: {len(ret)} unique words")
    return ret


def process_entry(config: LanguageConfig, entry: Entry) -> dict[str, Any] | None:
    """Process a single Wiktionary entry into a verb conjugation dict.

    Returns None if the entry should be skipped (not a clean verb root,
    no conjugation forms, or processing fails).
    """
    if not entry_is_clean_verb_root(entry):
        return None

    if not any(x.source == "conjugation" for x in entry.forms):
        return None

    if config.max_conj_tables is not None:
        filtered_forms = filter_forms_by_table(entry.forms, config.max_conj_tables)
    else:
        forms_to_filter = entry.forms
        if config.code == "el":
            # Preprocess Greek forms before filtering so that annotation
            # stripping runs before the space filter in form_is_clean_conjugation.
            forms_to_filter = preprocess_el_forms(forms_to_filter)
        filtered_forms = [f for f in forms_to_filter if form_is_clean_conjugation(f)]
    try:
        conj = extract_conjugations_from_forms(config, filtered_forms, entry)
    except Exception as e:
        log.error(f"Failed to process {entry.lang_code} {entry.word}", exc_info=e)
        return None

    processed: dict[str, Any] = dict(
        name=entry.word,
        nameNoDiacritics=strip_diacritics(entry.word),
        conjugation=list(conj.values()),
    )

    if fr_is_aspirated(entry):
        processed["frIsAspirated"] = True

    gloss = extract_gloss(entry)
    if gloss:
        processed["gloss"] = gloss

    return processed


def generate_data_for_lang(wiki_lang: str, lang: LanguageConfig, dev: bool):
    log.info(f"generating {lang.code} data")
    cache = CacheManager()

    with log_timing(f"{lang.code} download"):
        data = list(cache.get_lang_filtered_raw_data(wiki_lang, lang.code))

    verbs: list[dict[str, Any]] = []
    seen_verbs: set[str] = set()

    with log_timing(f"{lang.code} process entries"):
        for line in data:
            entry_just_pos = msgspec.json.decode(line, type=EntryJustPos)
            if entry_just_pos.pos == "hard-redirect":
                continue

            entry = msgspec.json.decode(line, type=Entry)
            assert entry.lang_code == lang.code

            if entry.word in seen_verbs:
                log.debug(f"duplicate: {entry.word}")
                continue

            processed = process_entry(lang, entry)
            if processed is None:
                continue

            verbs.append(processed)
            seen_verbs.add(entry.word)

            if dev and len(seen_verbs) > 20:
                break

    log.info(f"{lang.code} has {len(verbs)} entries")
    verbs = sorted(verbs, key=lambda x: x["nameNoDiacritics"])

    with log_timing(f"{lang.code} word frequencies"):
        for verb in verbs:
            verb["freq"] = round(zipf_frequency(verb["name"], lang.code), 2)

    unique_verbs = {x["name"] for x in verbs}
    if len(unique_verbs) != len(verbs):
        raise ValueError("duplicates")

    with log_timing(f"{lang.code} search index"):
        search_index = build_search_index(verbs, phonetic_fn=lang.phonetic_fn)

    with log_timing(f"{lang.code} gloss index"):
        gloss_index = build_gloss_index(verbs)

    return {
        "verbs": verbs,
        "searchIndex": search_index,
        "glossIndex": gloss_index,
    }


def generate_data(dev: bool):
    ret: dict[str, dict[str, Any]] = {}

    for config in CONFIG:
        wiki_lang = "en"
        ret[config.code] = generate_data_for_lang(wiki_lang, config, dev=dev)

    return ret


def check_manifest_metadata():
    """Verify committed data-manifest.json structural metadata matches current LanguageConfig definitions."""
    manifest_path = os.path.join("src", "lib", "data-manifest.json")
    if not os.path.exists(manifest_path):
        log.error(f"{manifest_path} not found")
        return False

    with open(manifest_path) as f:
        manifest = json.load(f)

    ok = True
    for config in CONFIG:
        expected = make_language_static_metadata(config)
        if config.code not in manifest.get("languages", {}):
            log.error(f"Language '{config.code}' missing from manifest")
            ok = False
            continue

        actual = manifest["languages"][config.code]
        for key in ("tenseNames", "tensePronouns", "tenseGroups"):
            if expected[key] != actual.get(key):
                log.error(
                    f"Mismatch in {config.code}.{key}:\n"
                    f"  expected: {expected[key]}\n"
                    f"  actual:   {actual.get(key)}"
                )
                ok = False

    if ok:
        log.info("Manifest metadata matches current configs")
    return ok


BASE_URL = "https://congeegator.com"


def generate_sitemaps(data: dict[str, dict[str, Any]], static_dir: str):
    """Generate sitemap index and per-language sitemaps in static/."""
    os.makedirs(static_dir, exist_ok=True)

    lang_codes = sorted(data.keys())

    # Sitemap index
    sitemap_index_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    sitemap_index_lines.append(
        f"  <sitemap><loc>{BASE_URL}/sitemap-homepage.xml</loc></sitemap>"
    )
    for lang in lang_codes:
        sitemap_index_lines.append(
            f"  <sitemap><loc>{BASE_URL}/sitemap-{lang}.xml</loc></sitemap>"
        )
    sitemap_index_lines.append("</sitemapindex>")
    sitemap_index_lines.append("")

    index_path = os.path.join(static_dir, "sitemap.xml")
    with open(index_path, "w") as f:
        f.write("\n".join(sitemap_index_lines))
    log.info(f"Wrote {index_path}")

    # Homepage sitemap
    homepage_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <url><loc>{BASE_URL}/</loc></url>",
        "</urlset>",
        "",
    ]
    homepage_path = os.path.join(static_dir, "sitemap-homepage.xml")
    with open(homepage_path, "w") as f:
        f.write("\n".join(homepage_lines))
    log.info(f"Wrote {homepage_path}")

    # Per-language sitemaps
    for lang in lang_codes:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for verb in data[lang]["verbs"]:
            encoded_name = urllib.parse.quote(verb["name"], safe="")
            lines.append(f"  <url><loc>{BASE_URL}/{lang}/{encoded_name}</loc></url>")
        lines.append("</urlset>")
        lines.append("")

        lang_path = os.path.join(static_dir, f"sitemap-{lang}.xml")
        with open(lang_path, "w") as f:
            f.write("\n".join(lines))
        log.info(f"Wrote {lang_path} ({len(data[lang]['verbs'])} verbs)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output (useful for local dev)"
    )
    parser.add_argument(
        "--check-manifest-metadata",
        action="store_true",
        help="Verify data-manifest.json metadata matches current LanguageConfig definitions (no data generation)",
    )
    args = parser.parse_args()

    if args.check_manifest_metadata:
        ok = check_manifest_metadata()
        sys.exit(0 if ok else 1)

    total_start = time.monotonic()

    with log_timing("generate data (all languages)"):
        data = generate_data(dev=args.dev)

    with log_timing("generate sitemaps"):
        sitemaps_dir = os.path.join(os.path.dirname(__file__), "static")
        generate_sitemaps(data, sitemaps_dir)

    DATA_VERSION = "1"

    static_dir = os.path.join(os.path.dirname(__file__), "r2_data")
    data_dir = os.path.join(static_dir, "data", f"v{DATA_VERSION}")
    shutil.rmtree(data_dir, ignore_errors=True)

    with log_timing("write output files"):
        for lang in data.keys():
            lang_dir = os.path.join(data_dir, lang)
            log.info(f"Writing {lang_dir}")
            write_language_data(data[lang], lang_dir, pretty=args.pretty)

    write_data_manifest(data_dir)

    total = time.monotonic() - total_start
    log.info(f"[timing] total: {total:.1f}s")


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    main()
