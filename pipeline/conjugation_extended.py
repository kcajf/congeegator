"""Reviewed Latin and Finnish conjugation coverage.

Hungarian is deliberately not configured: the pinned extract systematically
mislabels persons and omits moods in its conjugation tables.
"""

import re
import unicodedata

from .conjugation_types import FormMatcher, LanguageConfig, PERSONS_NUMBERS, TenseConfig, TenseGroup, full_tense
from .wiktionary import Entry, Form


LA_PRONOUNS = ("ego", "tū", "is/ea/id", "nōs", "vōs", "eī/eae/ea")
FI_PRONOUNS = ("minä", "sinä", "hän", "me", "te", "he")

_METADATA_TAGS = {"table-tags", "inflection-template", "class", "romanization", "error-unrecognized-form"}
_DIRTY = re.compile(r"\{\{|\}\}|\[\[|\]\]|[<>+=\d]|Template:|Module:|\ufffd")


def extended_form_is_clean(form: Form) -> bool:
    """Allow real negatives/compound forms and macrons, reject extraction notes."""
    if form.source != "conjugation" or not form.form or form.tags & _METADATA_TAGS:
        return False
    text = unicodedata.normalize("NFC", form.form).strip()
    if not text or text in {"-", "—", "–"} or _DIRTY.search(text):
        return False
    # Parentheses are reserved for the gender labels added by our bounded Latin
    # recipe expansion; raw table notes and footnote markers are not word forms.
    text = re.sub(r" \((?:masculine|feminine|neuter)\)$", "", text)
    return all(char.isalpha() or unicodedata.category(char) == "Mn" or char in " '’‑-" for char in text)


# The source uses these exact recipes instead of enumerated finite forms.
# Agreement and auxiliaries are checked against Allen & Greenough §§170,181–192:
# https://dcc.dickinson.edu/grammar/latin/sum
# https://dcc.dickinson.edu/sites/default/files/1st_conj_perf_passive.pdf
_LA_RECIPE = re.compile(r"([^\W\d_]+us) \+ (present|imperfect|future) active (indicative|subjunctive) of sum")
_SUM = {
    ("present", "indicative"): ("sum", "es", "est", "sumus", "estis", "sunt"),
    ("imperfect", "indicative"): ("eram", "erās", "erat", "erāmus", "erātis", "erant"),
    ("future", "indicative"): ("erō", "eris", "erit", "erimus", "eritis", "erunt"),
    ("present", "subjunctive"): ("sim", "sīs", "sit", "sīmus", "sītis", "sint"),
    ("imperfect", "subjunctive"): ("essem", "essēs", "esset", "essēmus", "essētis", "essent"),
}


def _la_gender_forms(stem, auxiliary, tags, person, number):
    endings = ("us", "a", "um") if number == "singular" else ("ī", "ae", "a")
    return [Form(f"{stem}{ending} {auxiliary} ({gender})",
                 tags | {person, number, gender, "multiword-construction"}, "conjugation")
            for ending, gender in zip(endings, ("masculine", "feminine", "neuter"))]


def preprocess_la_forms(entry: Entry) -> list[Form]:
    result = []
    participles = {unicodedata.normalize("NFC", f.form or "") for f in entry.forms
                   if f.source == "conjugation" and {"perfect", "participle"} <= f.tags}
    # The displayed sequor table says “secūtus or sequūtus + ...sum”. JSONL
    # attaches the shared auxiliary only to the last alternative. Restore it
    # only for an adjacent, same-tag, independently listed perfect participle.
    # https://en.wiktionary.org/wiki/sequor#Conjugation
    for position, form in enumerate(entry.forms):
        text = unicodedata.normalize("NFC", form.form or "").strip()
        tags = form.tags
        if entry.word == "sum" and text in {
            "siem", "siēs", "siet", "siēmus", "siētis", "sient",
            "fuam", "fuās", "fuat", "fuāmus", "fuātis", "fuant",
            "escit", "escunt", "fūvimus", "fūvisset",
        }:
            # A&G §170 and Wiktionary sum's old-subjunctive note/footnote.
            tags = tags | {"archaic"}
        match = _LA_RECIPE.fullmatch(text)
        if not match and text in participles and text.endswith("us"):
            for following in entry.forms[position + 1:]:
                if following.source != "conjugation" or following.tags != form.tags:
                    break
                next_text = unicodedata.normalize("NFC", following.form or "")
                next_match = _LA_RECIPE.fullmatch(next_text)
                if next_match:
                    match = _LA_RECIPE.fullmatch(text + next_text[next_text.index(" + "):])
                    break
                if next_text not in participles:
                    break
        if match and form.source == "conjugation" and not tags & _METADATA_TAGS:
            participle, tense, mood = match.groups()
            auxiliaries = _SUM.get((tense, mood))
            expected_time = {"present": "perfect", "imperfect": "pluperfect", "future": "perfect"}[tense]
            if auxiliaries and mood in tags and expected_time in tags and ((tense == "future") == ("future" in tags)):
                for i, (person, number) in enumerate(PERSONS_NUMBERS):
                    if any(p in tags for p in ("first-person", "second-person", "third-person")) and person not in tags:
                        continue
                    if any(n in tags for n in ("singular", "plural")) and number not in tags:
                        continue
                    result.extend(_la_gender_forms(participle[:-2], auxiliaries[i], tags, person, number))
                continue
        # Semideponents can enumerate a masculine compound for each person
        # instead of a shared recipe. Expand agreement only after independently
        # validating the participle and the person-specific auxiliary.
        parts = text.split()
        expanded = False
        if len(parts) == 2 and form.source == "conjugation" and not tags & _METADATA_TAGS:
            for i, (person, number) in enumerate(PERSONS_NUMBERS):
                if not {person, number} <= tags:
                    continue
                ending = "us" if number == "singular" else "ī"
                if not parts[0].endswith(ending):
                    continue
                stem = parts[0][:-len(ending)]
                if stem + "us" not in participles:
                    continue
                mood = "indicative" if "indicative" in tags else "subjunctive" if "subjunctive" in tags else None
                tense = "future" if "future" in tags else "imperfect" if "pluperfect" in tags else "present" if "perfect" in tags else None
                auxiliaries = _SUM.get((tense, mood))
                auxiliary = parts[1]
                if auxiliaries and (auxiliary == auxiliaries[i] or (auxiliary == "erint" and i == 5 and tense == "future" and mood == "indicative")):
                    # erint is a documented sporadic variant, not silently
                    # replaced with erunt: https://en.wiktionary.org/wiki/erint
                    variant_tags = tags | {"rare"} if auxiliary == "erint" else tags
                    result.extend(_la_gender_forms(stem, auxiliary, variant_tags, person, number))
                    expanded = True
        if not expanded:
            result.append(Form(text, tags, form.source))
    return result


def _la_finite(name, tense, mood, voice, extra=()):
    # Future perfect also has a future tag; keep it out of simple future and
    # perfect. Likewise, the source has unusual potential perfect infinitives.
    excludes = tuple(t for t in ("future", "perfect", "pluperfect", "sigmatic", "potential") if t not in (tense, *extra))
    return full_tense("la", name, (tense, mood, voice, *extra), exclude_tags=excludes, pronouns=LA_PRONOUNS)


def _la_imperative(name, tense, voice, positions):
    return TenseConfig(name, tuple(FormMatcher(
        (*PERSONS_NUMBERS[i], "imperative", tense, voice), pronoun=LA_PRONOUNS[i],
        exclude_tags=("sigmatic",),
    ) for i in positions))


LA_CONFIG = LanguageConfig(
    code="la", name="Latina", english_wiktionary_name="Latin",
    tenses=(
        *(_la_finite(f"la_indic_{key}_{voice}", tense, "indicative", voice, extra)
          for voice in ("active", "passive")
          for key, tense, extra in (
              ("pres", "present", ()), ("imperf", "imperfect", ()),
              ("fut", "future", ()), ("perf", "perfect", ()),
              ("pluperf", "pluperfect", ()), ("fut_perf", "perfect", ("future",)),
          )),
        *(_la_finite(f"la_subj_{key}_{voice}", tense, "subjunctive", voice)
          for voice in ("active", "passive")
          for key, tense in (("pres", "present"), ("imperf", "imperfect"), ("perf", "perfect"), ("pluperf", "pluperfect"))),
        _la_imperative("la_imper_pres_active", "present", "active", (1, 4)),
        _la_imperative("la_imper_fut_active", "future", "active", (1, 2, 4, 5)),
        _la_imperative("la_imper_pres_passive", "present", "passive", (1, 4)),
        _la_imperative("la_imper_fut_passive", "future", "passive", (1, 2, 5)),
        *(TenseConfig(f"la_nonfinite_inf_{key}_{voice}", FormMatcher(
            ("infinitive", tense, voice), exclude_tags=excludes,
        )) for voice in ("active", "passive") for key, tense, excludes in (
            ("pres", "present", ("future", "perfect", "potential")),
            ("perf", "perfect", ("future", "potential")),
            ("fut", "future", ("perfect", "potential")),
        )),
        *(TenseConfig(f"la_nonfinite_part_{key}_{voice}", FormMatcher(
            ("participle", tense, voice), exclude_tags=("potential",),
        )) for key, tense, voice in (
            ("pres", "present", "active"), ("perf", "perfect", "active"),
            ("perf", "perfect", "passive"), ("fut", "future", "active"),
        )),
        TenseConfig("la_nonfinite_gerundive", FormMatcher(("future", "participle", "passive"), exclude_tags=("perfect", "potential"))),
        TenseConfig("la_nonfinite_gerund", tuple(FormMatcher(("gerund", case), pronoun=label) for case, label in (
            ("genitive", "gen."), ("dative", "dat."), ("accusative", "acc."), ("ablative", "abl."),
        ))),
        TenseConfig("la_nonfinite_supine", tuple(FormMatcher(("supine", case), pronoun=label) for case, label in (("accusative", "acc."), ("ablative", "abl.")))),
    ),
    tense_groups=[TenseGroup(f"la_{group}", re.compile(f"la_{group}_")) for group in ("indic", "subj", "imper", "nonfinite")],
    preprocess_forms=preprocess_la_forms,
    form_filter=extended_form_is_clean,
    rare_tags=("archaic", "obsolete", "rare", "poetic"),
)


def preprocess_fi_forms(entry: Entry) -> list[Form]:
    result = []
    slang_table = False
    modern_senses = [s for s in entry.senses if not set(s.tags) & {"archaic", "obsolete", "dialectal", "dated"}]
    impersonal = bool(modern_senses) and all("impersonal" in s.tags for s in modern_senses)
    for form in entry.forms:
        text = unicodedata.normalize("NFC", form.form or "").strip()
        tags = form.tags
        # The source marks Helsinki slang at template level but drops it from
        # individual forms (stemmata: ei oo stemmannu). Keep the standard
        # paradigm; never mix the explicitly marked slang block into it.
        if "table-tags" in tags:
            slang_table = False
        if "inflection-template" in tags:
            slang_table = text.startswith("fi-conj-") and text.endswith("-slang")
        if slang_table:
            continue
        # Some Wiktionary templates print a complete mechanically regular table
        # even for impersonal senses (täytyä 'must'). Don't teach its obsolete
        # or dialectal personal forms as the modern impersonal construction.
        if impersonal and tags & {"indicative", "conditional", "potential", "imperative"}:
            if not {"third-person", "singular"} <= tags or "passive" in tags:
                continue
        if entry.word == "ei" and form.source == "conjugation":
            # Its special table omits tense and imperative headings in JSONL.
            # Only independently verified lexical forms are repaired; optatives
            # ällös/älköömme/älköötte are not guessed to be ordinary imperatives.
            if "indicative" in tags and text in {"en", "et", "ei", "emme", "ette", "eivät"}:
                tags = tags | {"present"}
            elif text in {"älä", "älköön", "älkäämme", "älkää", "älkööt"}:
                tags = tags | {"imperative", "present"}
        result.append(Form(text, tags, form.source))
    return result


def _fi_finite(name, tense, mood, negative):
    tags = (tense, mood) + (("negative",) if negative else ())
    exclude = () if negative else ("negative",)
    positions = (1, 2, 3, 4, 5) if mood == "imperative" else range(6)
    return TenseConfig(name, (
        *(FormMatcher((*PERSONS_NUMBERS[i], *tags), pronoun=FI_PRONOUNS[i], exclude_tags=(*exclude, "passive")) for i in positions),
        FormMatcher((*tags, "passive"), pronoun="passiivi", exclude_tags=exclude),
    ))


FI_CONFIG = LanguageConfig(
    code="fi", name="suomi", english_wiktionary_name="Finnish",
    tenses=(
        *(_fi_finite(f"fi_{group}_{key}{'_neg' if negative else ''}", tense, mood, negative)
          for group, mood, tenses in (
              ("indic", "indicative", (("pres", "present"), ("past", "past"), ("perf", "perfect"), ("pluperf", "pluperfect"))),
              ("cond", "conditional", (("pres", "present"), ("perf", "perfect"))),
              ("pot", "potential", (("pres", "present"), ("perf", "perfect"))),
              ("imper", "imperative", (("pres", "present"),)),
          ) for key, tense in tenses for negative in (False, True)),
        TenseConfig("fi_nonfinite_inf", FormMatcher(("infinitive", "infinitive-i"))),
        TenseConfig("fi_nonfinite_part_pres_active", FormMatcher(("participle", "present", "active"))),
        TenseConfig("fi_nonfinite_part_pres_passive", FormMatcher(("participle", "present", "passive"))),
    ),
    tense_groups=[TenseGroup(f"fi_{group}", re.compile(f"fi_{group}_")) for group in ("indic", "cond", "pot", "imper", "nonfinite")],
    preprocess_forms=preprocess_fi_forms,
    form_filter=extended_form_is_clean,
    rare_tags=("archaic", "obsolete", "rare", "poetic"),
)
