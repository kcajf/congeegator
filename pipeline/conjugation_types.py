"""Shared conjugation configuration types and row builders."""

import re
from typing import Callable

import msgspec

from .wiktionary import Entry, Form

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


class TenseGroup(msgspec.Struct, frozen=True):
    name: str
    pattern: re.Pattern


class LanguageConfig(msgspec.Struct, frozen=True):
    code: str
    name: str
    english_wiktionary_name: str
    tenses: tuple[TenseConfig, ...]
    tense_groups: list[TenseGroup]
    phonetic_fn: Callable[[str], str] | None = None
    max_conj_tables: int | None = None
    rare_tags: tuple[str, ...] = ()
    exclude_tags: tuple[str, ...] = ()
    preprocess_forms: Callable[[Entry], list[Form]] | None = None
    form_filter: Callable[[Form], bool] | None = None


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
