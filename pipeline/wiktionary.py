from typing import Any, Optional

import msgspec


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
    examples: tuple[Any, ...] = ()


class HeadTemplate(msgspec.Struct, frozen=True):
    name: str
    args: dict[str, str] = {}


class EtymologyTemplate(msgspec.Struct, frozen=True):
    name: str
    args: dict[str, str] = {}
    expansion: str = ""


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
    sounds: tuple[Any, ...] = ()
