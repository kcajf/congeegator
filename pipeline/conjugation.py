import logging
import re
import typing
from typing import Any


from .gloss import extract_gloss
from .utils import _cat_names, strip_diacritics, to_phonetic_el
from .wiktionary import Entry, Form

log = logging.getLogger(__name__)

# Primary IPA Extensions
IPA_EXTENSIONS = "".join(chr(c) for c in range(0x0250, 0x02B0))

# Spacing Modifiers (includes tone marks and aspiration)
IPA_SPACING_MODIFIERS = "".join(chr(c) for c in range(0x02B0, 0x0300))

# Combining Diacritical Marks (accents, nasalization, etc.)
IPA_DIACRITICS = "".join(chr(c) for c in range(0x0300, 0x0370))

# Full IPA-related character set
IPA_ALL = IPA_EXTENSIONS + IPA_SPACING_MODIFIERS + IPA_DIACRITICS


from .conjugation_types import (
    PERSONS, NUMBERS, PERSONS_NUMBERS, LANG_PRONOUNS, FR_SUBJ_PRONOUNS,
    FormMatcher, TenseConfig, TenseGroup, LanguageConfig, full_tense, repeated_tense,
)


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

from .conjugation_romance import PT_CONFIG, CA_CONFIG
from .conjugation_germanic import NL_CONFIG, SV_CONFIG
from .conjugation_extended import LA_CONFIG, FI_CONFIG

CONFIG: list[LanguageConfig] = [
    FR_CONFIG,
    EL_CONFIG,
    DE_CONFIG,
    ES_CONFIG,
    IT_CONFIG,
    EN_CONFIG,
    PT_CONFIG,
    CA_CONFIG,
    NL_CONFIG,
    SV_CONFIG,
    LA_CONFIG,
    FI_CONFIG,
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

        # The rendered αρνούμαι-class table has a duplicated opening bracket
        # in this exact 2pl imperfect cell. Expand its two explicit suffix
        # abbreviations, preserving the source's rare/optional usage markers.
        malformed = re.fullmatch(
            r"\[(?P<stem>[α-ωάέήίόύώϊϋΐΰ]+)ούσασταν, \[-ούσαστε\] - "
            r"(?P=stem)ιόσασταν, \(-ιόσαστε\)", text
        )
        if malformed and {"imperfect", "plural", "second-person"} <= form.tags:
            stem = malformed.group("stem")
            for expanded in (
                f"[{stem}ούσασταν]", f"[{stem}ούσαστε]",
                f"{stem}ιόσασταν", f"({stem}ιόσαστε)",
            ):
                result.append(Form(form=expanded, tags=form.tags, source=form.source))
            continue

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
    all_forms: list[Form], max_tables: int, form_filter=None
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
        if (form_filter or form_is_clean_conjugation)(form):
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
    # IPA can contain only ordinary Latin letters (asseoir: /a.swa.je/),
    # so testing for IPA-specific characters alone does not exclude it.
    if len(form.form) > 2 and form.form.startswith("/") and form.form.endswith("/"):
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

    # Homographs can inherit the page's verb-form category despite a lexical
    # verb head (Latin licet/odi/fio; Finnish haluta). Sense-level form-of records
    # have already been excluded above; the head is positive lemma evidence.
    lexical_head = any(h.name == f"{entry.lang_code}-verb" for h in entry.head_templates)
    if entry.lang_code == "sv":
        lexical_head = lexical_head or any(
            h.name in {"sv-verb-reg", "sv-verb-irreg"}
            or (h.name == "head" and h.args.get("1") == "sv" and h.args.get("2") in {"verb", "verbs"})
            for h in entry.head_templates
        )
    if entry.lang_code in {"la", "fi", "sv"} and lexical_head:
        BAD_CATEGORIES.discard(f"{entry.lang} verb forms")

    for c in _cat_names(entry.categories):
        if c in BAD_CATEGORIES:
            return False

    if entry.senses and all(
        any(c in BAD_CATEGORIES for c in _cat_names(s.categories)) for s in entry.senses
    ):
        return False

    return True


def fr_is_aspirated(entry: Entry) -> bool:
    cat = "French terms with aspirated h"
    if cat in _cat_names(entry.categories):
        return True
    for s in entry.senses:
        if cat in _cat_names(s.categories):
            return True
    return False


def process_entry(config: LanguageConfig, entry: Entry) -> dict[str, Any] | None:
    """Process a single Wiktionary entry into a verb conjugation dict.

    Returns None if the entry should be skipped (not a clean verb root,
    no conjugation forms, or processing fails).
    """
    if not entry_is_clean_verb_root(entry):
        return None

    forms_to_filter = config.preprocess_forms(entry) if config.preprocess_forms else entry.forms
    if not any(x.source == "conjugation" for x in forms_to_filter):
        return None

    form_filter = config.form_filter or form_is_clean_conjugation
    if config.max_conj_tables is not None:
        filtered_forms = filter_forms_by_table(forms_to_filter, config.max_conj_tables, form_filter)
    else:
        if config.code == "el":
            # Preprocess Greek forms before filtering so that annotation
            # stripping runs before the space filter in form_is_clean_conjugation.
            forms_to_filter = preprocess_el_forms(forms_to_filter)
        filtered_forms = [f for f in forms_to_filter if form_filter(f)]
    try:
        conj = extract_conjugations_from_forms(config, filtered_forms, entry)
    except Exception as e:
        log.error(f"Failed to process {entry.lang_code} {entry.word}", exc_info=e)
        return None

    if not count_conjs(conj):
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



# Alias for the plan's naming convention
extract_conjugation = process_entry
