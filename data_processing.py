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
import typing
import unicodedata
from collections import defaultdict
from typing import Any, Optional

import msgspec
import orjson
import polars as pl
import requests
import zstandard
from rich.pretty import pprint

log = logging.getLogger(__name__)

# Timestamp version of pinned source data in R2.
# Update by running: pixi run pin-source-data
SOURCE_DATA_VERSION = "2026-03-12T190220Z"


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
    categories: tuple[str, ...] = ()


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
    categories: tuple[str, ...] = ()


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
    "el": ("εγω", "εσυ", "αυτ(ος/ή/ό)", "εμείς", "εσείς", "αυτ(οί/ές/ά)"),
}


class FormMatcher(msgspec.Struct, frozen=True):
    tags: tuple[str, ...]
    formatter: str = "{}"
    pronoun: str | None = None

    def matches(self, form: Form) -> bool:
        for t in self.tags:
            if t not in form.tags:
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
    name: str  # This should be the language name that (English) wiktionary uses
    tenses: tuple[TenseConfig, ...]
    tense_groups: list[TenseGroup]


def full_tense(
    lang: str,
    name: str,
    tags: tuple[str, ...],
    auxiliaries: tuple[str, ...] | None = None,
):
    if auxiliaries is not None:
        assert len(auxiliaries) == len(PERSONS_NUMBERS)
        matchers = tuple(
            FormMatcher(
                (*PERSONS_NUMBERS[i], *tags),
                pronoun=LANG_PRONOUNS[lang][i],
                formatter=auxiliaries[i] + "{}",
            )
            for i in range(len(PERSONS_NUMBERS))
        )
    else:
        matchers = tuple(
            FormMatcher((*PERSONS_NUMBERS[i], *tags), pronoun=LANG_PRONOUNS[lang][i])
            for i in range(len(PERSONS_NUMBERS))
        )

    return TenseConfig(name, matchers)


def repeated_tense(
    lang: str, name: str, tags: tuple[str, ...], auxiliaries: tuple[str, ...]
):
    assert len(auxiliaries) == len(PERSONS_NUMBERS)
    matchers = tuple(
        FormMatcher(
            tags,
            pronoun=LANG_PRONOUNS[lang][i],
            formatter=auxiliaries[i] + " {}",
        )
        for i in range(len(PERSONS_NUMBERS))
    )

    return TenseConfig(name, matchers)


EL_THA = ("θα ", "θα ", "θα ", "θα ", "θα ", "θα ")

EL_CONFIG = LanguageConfig(
    code="el",
    name="Greek",
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
            ("subjunctive", "perfective", "active"),
            auxiliaries=EL_THA,
        ),
        full_tense(
            "el",
            "el_indic_fut_simple_passive",
            ("subjunctive", "perfective", "passive"),
            auxiliaries=EL_THA,
        ),
        # Subjunctive
        full_tense(
            "el",
            "el_subj_perf_active",
            ("subjunctive", "perfective", "active"),
        ),
        full_tense(
            "el",
            "el_subj_perf_passive",
            ("subjunctive", "perfective", "passive"),
        ),
        # Imperative (2nd person only — singular + plural)
        TenseConfig(
            "el_imper_imperf_active",
            (
                FormMatcher(("second-person", "singular", "imperative", "imperfective", "active")),
                FormMatcher(("second-person", "plural", "imperative", "imperfective", "active")),
            ),
        ),
        TenseConfig(
            "el_imper_perf_active",
            (
                FormMatcher(("second-person", "singular", "imperative", "perfective", "active")),
                FormMatcher(("second-person", "plural", "imperative", "perfective", "active")),
            ),
        ),
        TenseConfig(
            "el_imper_imperf_passive",
            (
                FormMatcher(("second-person", "singular", "imperative", "imperfective", "passive")),
                FormMatcher(("second-person", "plural", "imperative", "imperfective", "passive")),
            ),
        ),
        TenseConfig(
            "el_imper_perf_passive",
            (
                FormMatcher(("second-person", "singular", "imperative", "perfective", "passive")),
                FormMatcher(("second-person", "plural", "imperative", "perfective", "passive")),
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
)


FR_PRES_INDIC_AVOIR = ("ai", "as", "a", "avons", "avez", "ont")
FR_IMPERF_INDIC_AVOIR = ("avais", "avais", "avait", "avions", "aviez", "avaient")
FR_PAST_HIST_INDIC_AVOIR = ("eus", "eus", "eut", "eûmes", "eûtes", "eurent")
FR_FUT_INDIC_AVOIR = ("aurai", "auras", "aura", "aurons", "aurez", "auront")

FR_CONFIG = LanguageConfig(
    code="fr",
    name="French",
    tenses=(
        TenseConfig("fr_impers_pres_partic", FormMatcher(("participle", "present"))),
        TenseConfig("fr_impers_past_partic", FormMatcher(("participle", "past"))),
        full_tense("fr", "fr_indic_pres", ("present", "indicative")),
        full_tense("fr", "fr_indic_imperf", ("imperfect", "indicative")),
        full_tense("fr", "fr_indic_past_hist", ("past", "historic", "indicative")),
        full_tense("fr", "fr_indic_fut", ("future", "indicative")),
        full_tense("fr", "fr_cond_pres", ("conditional",)),
        full_tense("fr", "fr_subj_pres", ("subjunctive", "present")),
        full_tense("fr", "fr_subj_imperf", ("subjunctive", "imperfect")),
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
        TenseGroup("fr_impers", re.compile(r"^fr_impers_")),
        TenseGroup("fr_indic", re.compile(r"^fr_indic_")),
        TenseGroup("fr_subj", re.compile(r"^fr_subj_")),
        TenseGroup("fr_cond", re.compile(r"^fr_cond_")),
    ],
)

CONFIG: list[LanguageConfig] = [
    FR_CONFIG,
    EL_CONFIG,
]


def structure_map(f, s):
    if isinstance(s, list):
        return [structure_map(f, x) for x in s]
    if isinstance(s, tuple):
        return tuple(structure_map(f, x) for x in s)
    if isinstance(s, dict):
        return {k: structure_map(f, v) for k, v in s.items()}
    return f(s)


def clean_up_matched_forms(
    l: LanguageConfig, forms: list[str], entry: Entry
) -> list[str]:
    forms = [f.replace("‑", "-") for f in forms]

    if l.code == "el":
        new_forms = [*forms]
        for i, f in enumerate(forms):
            suffix_replacements = [
                ("ουμε", "ομε"),
                ("ιέστε", "ιόσαστε"),
                ("ιούνται", "ιόνται"),
                ("όμαστε", "ώμεθα"),
                ("άστε", "άσθε"),
            ]
            
            if i > 0:
                for from_, to in suffix_replacements:
                    if f == f'-{to}':
                        new_forms[i] = new_forms[i-1].replace(from_, to)

        for f in new_forms:
            if '-' in f and len(f) > 1:
                # log.warning(f"dodgy-looking form in {entry.word}: {f}")
                pass
        return new_forms
    return forms


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
            formatted = matcher.format(form)
            if formatted in seen:
                continue
            ret.append(formatted)
            seen.add(formatted)
    ret = clean_up_matched_forms(l, ret, entry)
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

    if "'" in form.form:  # French "t'es"
        return False

    if " " in form.form and ' - ' not in form.form:  # French "me suis"
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


def write_language_data(data: dict[str, Any], lang_dir: str):
    os.makedirs(lang_dir, exist_ok=True)

    # INDENT=None
    INDENT = 2

    # full data file
    out_path = os.path.join(lang_dir, "data.json")
    with open(out_path, "w") as f:
        log.info(f"Wrote {out_path}")
        json.dump(data, f, indent=INDENT, ensure_ascii=False)

    # single verbs file
    single_verbs_dir = os.path.join(lang_dir, "verbs")
    os.makedirs(single_verbs_dir)
    for verb_data in data["verbs"]:
        with open(
            os.path.join(single_verbs_dir, f"{verb_data['name']}.json"), "w"
        ) as f:
            json.dump(verb_data, f, indent=INDENT, ensure_ascii=False)

    # index file
    with open(os.path.join(lang_dir, "index.json"), "w") as f:
        names = [x["name"] for x in data["verbs"]]
        json.dump(names, f, indent=INDENT, ensure_ascii=False)


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

        with open(data_path, "rb") as f:
            h = hashlib.file_digest(f, "md5").hexdigest()[:8]

        hashed_data_dir = os.path.join(data_dir, f"{config.code}-{h}")
        os.rename(os.path.join(data_dir, config.code), hashed_data_dir)

        log.info(f"{config.code}: dataHash={h}")

        language_hashes[config.code] = {
            "dataHash": h,
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

    for s in entry.senses:
        if "form-of" in s.tags:
            return False
        if "alt-of" in s.tags:
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

    for c in entry.categories:
        if c in BAD_CATEGORIES:
            return False

    for s in entry.senses:
        for c in s.categories:
            if c in BAD_CATEGORIES:
                return False

    return True


def fr_is_aspirated(entry: Entry) -> bool:
    cat = "French terms with aspirated h"
    if cat in entry.categories:
        return True
    for s in entry.senses:
        if cat in s.categories:
            return True
    return False


def build_search_index(verbs: list[dict[str, Any]]) -> dict[str, list[int]]:
    log.info("generating search index")
    searchable_words = defaultdict[str, set[int]](lambda: set())

    def add_to_index(s: str, idx: int):
        if s == "" or s == "-":
            return
        for ss in s.split("/"):
            if ' ' in ss:
                ss = ss.split(' ')[-1]
            searchable_words[ss].add(idx)
            searchable_words[strip_diacritics(ss)].add(idx)

    # TODO: strip diacritics?
    # TODO split variants
    for i, v in enumerate(verbs):
        searchable_words[v["name"]].add(i)
        for c in v["conjugation"]:
            if isinstance(c, str):
                add_to_index(c, i)
            else:
                for cc in c:
                    # TODO; drop auxiliary? or split on word boundaries
                    add_to_index(cc, i)

    index = defaultdict[str, set[int]](lambda: set())

    MIN_PREFIX = 2
    MAX_PREFIX = 4

    for word, indices in searchable_words.items():
        for prefix_len in range(MIN_PREFIX, MAX_PREFIX + 1):
            word_prefix = word[:prefix_len]
            for i in indices:
                index[word_prefix].add(i)

    ret = {k: sorted(v) for k, v in index.items()}

    max_hits = 0
    max_key = None
    for k, v in ret.items():
        if len(v) > max_hits:
            max_hits = len(v)
            max_key = k

    log.info(f"Longest index entry: '{max_key}', {max_hits} hits")

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

    filtered_forms = [f for f in entry.forms if form_is_clean_conjugation(f)]
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

    return processed


def generate_data_for_lang(wiki_lang: str, lang: LanguageConfig, dev: bool):
    log.info(f"generating {lang.code} data")
    cache = CacheManager()
    data = cache.get_lang_filtered_raw_data(wiki_lang, lang.code)

    verbs: list[dict[str, Any]] = []

    seen_verbs: set[str] = set()

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

    unique_verbs = {x["name"] for x in verbs}
    if len(unique_verbs) != len(verbs):
        raise ValueError("duplicates")

    search_index = build_search_index(verbs)

    return {
        "verbs": verbs,
        "searchIndex": search_index,
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument(
        "--check-manifest-metadata",
        action="store_true",
        help="Verify data-manifest.json metadata matches current LanguageConfig definitions (no data generation)",
    )
    args = parser.parse_args()

    if args.check_manifest_metadata:
        ok = check_manifest_metadata()
        sys.exit(0 if ok else 1)

    data = generate_data(dev=args.dev)

    DATA_VERSION = "1"

    static_dir = os.path.join(os.path.dirname(__file__), "r2_data")
    data_dir = os.path.join(static_dir, "data", f"v{DATA_VERSION}")
    shutil.rmtree(data_dir, ignore_errors=True)

    for lang in data.keys():
        lang_dir = os.path.join(data_dir, lang)
        log.info(f"Writing {lang_dir}")
        write_language_data(data[lang], lang_dir)

    write_data_manifest(data_dir)
    log.info("all done")


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    main()
