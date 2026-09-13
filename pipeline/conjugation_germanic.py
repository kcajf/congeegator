"""Audited Dutch and Swedish source-table configurations.

Dutch source tables do not identify perfect auxiliaries, so no compound tenses
are invented. Swedish perfects use the supine, never the adjectival participle.
"""

import re
import unicodedata

import msgspec

from .conjugation_types import FormMatcher, LanguageConfig, TenseConfig, TenseGroup
from .wiktionary import Entry, Form


_METADATA = {"table-tags", "inflection-template", "class", "romanization", "error-unrecognized-form"}
_RARE = {"archaic", "dated", "obsolete", "rare", "dialectal"}


def _germanic_form_is_clean(form: Form, allow_spaces: bool = False) -> bool:
    if form.source != "conjugation" or not form.form or form.tags & _METADATA:
        return False
    if form.tags & {"negative", "combined-form"}:
        return False
    # Dutch separable main-clause forms contain spaces without the German
    # multiword-construction tag. Other strings must be single lexical forms.
    text = unicodedata.normalize("NFC", form.form)
    if " " in text and not allow_spaces and "main-clause" not in form.tags:
        return False
    if text != text.strip() or not any(unicodedata.category(c).startswith("L") for c in text):
        return False
    return all(unicodedata.category(c)[0] in {"L", "M"} or c in " '-’" for c in text)


def dutch_form_is_clean(form: Form) -> bool:
    return _germanic_form_is_clean(form)


def swedish_form_is_clean(form: Form) -> bool:
    # Swedish particle/reflexive verbs have ordinary active/passive tags on
    # lexical forms such as "hutar åt", "lägger fram" and "annalka sig".
    if not form.tags & {"infinitive", "indicative", "imperative", "subjunctive", "participle", "supine"}:
        return False
    if form.form and ":" in form.form:
        # Swedish abbreviation verbs inflect after a colon (sms:ar, FTP:ade).
        if not re.fullmatch(r"[A-Za-z]{2,6}:[a-zåäö]+", form.form):
            return False
        form = msgspec.structs.replace(form, form=form.form.replace(":", ""))
    return _germanic_form_is_clean(form, allow_spaces=True)


def preprocess_nl_forms(entry: Entry) -> list[Form]:
    # The first full paradigm is the preferred one. Secondary tables can carry
    # untagged historical paradigms (werken: wrocht/gewrocht); do not mix them
    # into an unqualified modern table. Inflected alternatives within it remain.
    result = []
    table = 0
    for form in entry.forms:
        if form.source == "conjugation" and "table-tags" in form.tags:
            table += 1
        if table <= 1:
            result.append(form)
    return result


def preprocess_sv_forms(entry: Entry) -> list[Form]:
    # Register labels on table headings are not repeated on their cells.
    # Preserve those labels and collapse duplicate cells shared by modern and
    # dated paradigms (ha/hava), preferring the unmarked equivalent.
    result: dict[tuple[str | None, frozenset[str], str | None], Form] = {}
    table_register: set[str] = set()
    templates = [t for t in entry.inflection_templates if t.name.startswith("sv-conj")]
    table_count = sum(f.source == "conjugation" and "table-tags" in f.tags for f in entry.forms)
    table_index = -1
    for form in entry.forms:
        if form.source == "conjugation" and "table-tags" in form.tags:
            table_index += 1
            table_register = set((form.form or "").split()) & _RARE
            # The source loses some heading notes from table-tags (läsa's
            # obsolete strong paradigm). Template order matches every table
            # in the pinned Swedish dump; require alignment before using it.
            if len(templates) == table_count:
                note = templates[table_index].args.get("note", "").lower()
                table_register |= set(re.findall(r"\w+", note)) & (_RARE | {"nonstandard"})
                if "older" in note:
                    table_register.add("dated")
        if form.source == "conjugation":
            form = msgspec.structs.replace(form, tags=form.tags | table_register)
            # The gå table omits this label; the lemma's form entry explicitly
            # marks gack archaic: https://en.wiktionary.org/wiki/gack#Swedish
            if entry.word == "gå" and form.form == "gack" and "imperative" in form.tags:
                form = msgspec.structs.replace(form, tags=form.tags | {"archaic"})
        key = (form.form, frozenset(form.tags - _RARE), form.source)
        existing = result.get(key)
        if existing is None or len(form.tags & _RARE) < len(existing.tags & _RARE):
            result[key] = form
    return list(result.values())


def _nl_finite(name: str, tense: str) -> TenseConfig:
    excluded = ("subjunctive", "imperative", "participle", "subordinate-clause", "archaic", "Flanders")
    return TenseConfig(name, (
        FormMatcher((tense, "first-person", "singular"), pronoun="ik", exclude_tags=excluded),
        # The extractor merges ordinary and inverted jij forms into one tagged
        # cell. The row explicitly indicates both orders (werkt / werk).
        FormMatcher((tense, "second-person", "singular"), pronoun="jij / … jij", exclude_tags=(*excluded, "formal")),
        FormMatcher((tense, "second-person", "singular", "formal"), pronoun="u", exclude_tags=excluded),
        FormMatcher((tense, "third-person", "singular"), pronoun="hij/zij/het", exclude_tags=excluded),
        FormMatcher((tense, "plural"), pronoun="wij/jullie/zij", exclude_tags=excluded),
    ))


NL_CONFIG = LanguageConfig(
    code="nl", name="Nederlands", english_wiktionary_name="Dutch",
    tenses=(
        _nl_finite("nl_indic_pres", "present"),
        _nl_finite("nl_indic_past", "past"),
        TenseConfig("nl_imper_pres", FormMatcher(("imperative", "present", "singular"), exclude_tags=("archaic", "subordinate-clause"))),
        TenseConfig("nl_impers_inf", FormMatcher(("infinitive",))),
        TenseConfig("nl_impers_pres_partic", FormMatcher(("participle", "present"))),
        TenseConfig("nl_impers_past_partic", FormMatcher(("participle", "past"))),
    ),
    tense_groups=[
        TenseGroup("nl_indic", re.compile(r"^nl_indic_")),
        TenseGroup("nl_imper", re.compile(r"^nl_imper_")),
        TenseGroup("nl_impers", re.compile(r"^nl_impers_")),
    ],
    rare_tags=("archaic", "dated", "obsolete", "rare", "dialectal"),
    preprocess_forms=preprocess_nl_forms,
    form_filter=dutch_form_is_clean,
)


def _sv_row(name: str, tags: tuple[str, ...], formatter: str = "{}", exclude: tuple[str, ...] = ()) -> TenseConfig:
    return TenseConfig(name, FormMatcher(tags, formatter=formatter, exclude_tags=("archaic", *exclude)))


SV_CONFIG = LanguageConfig(
    code="sv", name="svenska", english_wiktionary_name="Swedish",
    tenses=(
        _sv_row("sv_active_pres", ("active", "indicative", "present")),
        _sv_row("sv_active_past", ("active", "indicative", "past")),
        _sv_row("sv_active_perfect", ("active", "supine"), "har {}"),
        _sv_row("sv_active_pluperfect", ("active", "supine"), "hade {}"),
        _sv_row("sv_active_imper", ("active", "imperative")),
        _sv_row("sv_s_pres", ("passive", "indicative", "present")),
        _sv_row("sv_s_past", ("passive", "indicative", "past")),
        _sv_row("sv_s_perfect", ("passive", "supine"), "har {}"),
        _sv_row("sv_s_pluperfect", ("passive", "supine"), "hade {}"),
        _sv_row("sv_s_imper", ("passive", "imperative")),
        _sv_row("sv_subj_pres", ("active", "subjunctive", "present")),
        _sv_row("sv_subj_past", ("active", "subjunctive", "past")),
        _sv_row("sv_subj_s_pres", ("passive", "subjunctive", "present")),
        _sv_row("sv_subj_s_past", ("passive", "subjunctive", "past")),
        _sv_row("sv_impers_inf", ("active", "infinitive")),
        _sv_row("sv_impers_s_inf", ("passive", "infinitive")),
        _sv_row("sv_impers_supine", ("active", "supine")),
        _sv_row("sv_impers_s_supine", ("passive", "supine")),
        # The source erroneously gives present participles BOTH present/past.
        _sv_row("sv_impers_pres_partic", ("participle", "present")),
        _sv_row("sv_impers_past_partic", ("participle", "past"), exclude=("present",)),
    ),
    tense_groups=[
        TenseGroup("sv_active", re.compile(r"^sv_active_")),
        # S-forms also express deponent/reciprocal verbs, not only passives.
        TenseGroup("sv_s", re.compile(r"^sv_s_")),
        TenseGroup("sv_subj", re.compile(r"^sv_subj_")),
        TenseGroup("sv_impers", re.compile(r"^sv_impers_")),
    ],
    rare_tags=("dated", "obsolete", "rare", "dialectal", "nonstandard"),
    preprocess_forms=preprocess_sv_forms,
    form_filter=swedish_form_is_clean,
)
