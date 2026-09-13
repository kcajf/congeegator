"""Reviewed Portuguese and Catalan paradigms from English Wiktionary."""

import re
import unicodedata

from .conjugation_types import FormMatcher, LanguageConfig, PERSONS_NUMBERS, TenseConfig, TenseGroup, full_tense
from .wiktionary import Entry, Form

PT_PRONOUNS = ("eu", "tu", "ele/ela/você", "nós", "vós", "eles/elas/vocês")
CA_PRONOUNS = ("jo", "tu", "ell/ella", "nosaltres", "vosaltres", "ells/elles")
_METADATA_TAGS = {"table-tags", "inflection-template", "class", "canonical", "romanization", "negative", "combined-form"}
_LABELS = re.compile(r" \((?:Brazil|Portugal|pre-reform|figurative|cooking|stinging)(?:, (?:Brazil|Portugal|pre-reform|figurative|cooking|stinging))*\)$")


def conjugation_tables(entry: Entry) -> list[list[Form]]:
    """Keep the primary paradigm, not later contracted/auxiliary paradigms.

    In particular, estar's unlabelled tou/tás table and anar's auxiliary vam/vau
    table are not interchangeable with the ordinary lexical present tense.
    """
    tables = []
    current = []
    for form in entry.forms:
        if form.source not in {"conjugation", "declension", "inflection"}:
            continue
        if "table-tags" in form.tags:
            if current:
                tables.append(current)
            current = []
            continue
        current.append(form)
    if current:
        tables.append(current)
    matching = []
    for table in tables:
        if entry.lang_code == "ca" and any(
            form.form == "ca-conj" and "inflection-template" in form.tags for form in table
        ):
            # A handful of genuine verb tables are misclassified as declension
            # or inflection; the explicit ca-conj template identifies them.
            table = [Form(form.form, form.tags, "conjugation") for form in table]
        if any(form.source == "conjugation" and "infinitive" in form.tags and form.form == entry.word for form in table):
            matching.append(table)
    return matching


def first_conjugation_table(entry: Entry) -> list[Form]:
    tables = conjugation_tables(entry)
    # Do not publish a sole participle left over from a reflexive-only paradigm.
    return list(tables[0]) if tables else []


def _is_word(text: str) -> bool:
    # Catalan's middle dot is lexical, as in col·laborar.
    return bool(text) and unicodedata.normalize("NFC", text).replace("·", "").isalpha()


def romance_form_filter(form: Form) -> bool:
    if form.source != "conjugation" or not form.form or form.tags & _METADATA_TAGS:
        return False
    text = _LABELS.sub("", form.form)
    if "periphrastic" in form.tags:
        parts = text.split(" ")
        return len(parts) == 2 and parts[0] in {a for alternatives in CA_PAST_AUXILIARIES for a in alternatives} and _is_word(parts[1])
    return _is_word(text)


def preprocess_pt_forms(entry: Entry) -> list[Form]:
    result = []
    forms = first_conjugation_table(entry)
    for form in forms:
        if not form.form:
            continue
        labels = [region for region in ("Brazil", "Portugal") if region in form.tags]
        # Rendered pt-conj footnote 2 labels the accented -ámos alternative
        # European Portuguese; Wiktextract loses that footnote but retains the
        # paired Brazilian form. Recover only this unambiguous paired cell.
        if ({"first-person", "plural", "preterite", "indicative"} <= form.tags
                and form.form.endswith("ámos") and any(
                    candidate.form == form.form[:-4] + "amos"
                    and {"Brazil", "first-person", "plural", "preterite", "indicative"} <= candidate.tags
                    for candidate in forms)):
            labels.append("Portugal")
        # The source footnote is attached to pt-verb's stem specification but
        # omitted from the table form tags. Preserve that specific restriction.
        restricted_present = (
            {"present", "indicative", "first-person", "singular"} <= form.tags
            or {"present", "subjunctive"} <= form.tags
            or ("imperative" in form.tags and "second-person" not in form.tags)
        )
        if restricted_present and any(
            "Portugal only; missing in Brazil" in value
            for head in entry.head_templates for value in head.args.values()
        ):
            labels.append("Portugal")
        # The 1990 spelling agreement removed the trema in Portuguese gue/gui,
        # que/qui, and the circumflex in ôo/êem (voo, veem). Source tables
        # still include these pre-reform forms.
        if re.search(r"[gq][üú][ei]|ôo|êem$", form.form):
            labels.append("pre-reform")
        # Porto Editora explicitly permits the full paradigm in figurative or
        # poetic uses; literal weather chover is impersonal, third-person singular.
        if entry.word == "chover" and (
            "imperative" in form.tags
            or (form.tags & {"first-person", "second-person", "third-person"}
                and not {"third-person", "singular"} <= form.tags)
        ):
            labels.append("figurative")
        text = form.form + (f" ({', '.join(dict.fromkeys(labels))})" if labels else "")
        result.append(Form(text, form.tags, form.source))
    return result


# IEC/Generalitat and Gran Diccionari document these dedicated auxiliary forms;
# ordinary anar has anem/aneu, which must never be substituted here.
CA_PAST_AUXILIARIES = (("vaig",), ("vas", "vares"), ("va",), ("vam", "vàrem"), ("vau", "vàreu"), ("van", "varen"))


def preprocess_ca_forms(entry: Entry) -> list[Form]:
    forms = first_conjugation_table(entry)
    if entry.word == "coure":
        # Optimot/IEC distinguish the cooking and stinging participles. Preserve
        # both source forms, with their meanings, without mixing other tables.
        participles = [form for table in conjugation_tables(entry) for form in table
                       if "participle" in form.tags and form.form in {"cuit", "cogut"}]
        forms = [form for form in forms if form.form not in {"cuit", "cogut"}
                 or "participle" not in form.tags]
        for form in participles:
            meaning = "cooking" if form.form == "cuit" else "stinging"
            forms.append(Form(f"{form.form} ({meaning})", form.tags, form.source))
    if entry.word == "ploure":
        # Gran Diccionari's reviewed paradigm has only third-person finite
        # forms and no imperative; the raw template overgenerates these cells.
        forms = [form for form in forms if "imperative" not in form.tags
                 and not form.tags & {"first-person", "second-person"}]
    infinitives = [form.form for form in forms if "infinitive" in form.tags and form.form and _is_word(form.form)]
    for person, number in PERSONS_NUMBERS:
        # A defective verb's missing persons stay empty. Only construct a past
        # person when the source actually supplies that person in its past table.
        if not any({person, number, "preterite", "indicative"} <= form.tags and romance_form_filter(form) for form in forms):
            continue
        for infinitive in infinitives:
            for auxiliary in CA_PAST_AUXILIARIES[PERSONS_NUMBERS.index((person, number))]:
                forms.append(Form(f"{auxiliary} {infinitive}", {person, number, "preterite", "indicative", "periphrastic"}, "conjugation"))
    return forms


def pt_tense(name, tags):
    return full_tense("pt", name, tags, pronouns=PT_PRONOUNS)


def ca_tense(name, tags, exclude_tags=()):
    return full_tense("ca", name, tags, pronouns=CA_PRONOUNS, exclude_tags=exclude_tags)


PT_CONFIG = LanguageConfig(
    code="pt", name="português", english_wiktionary_name="Portuguese",
    tenses=(
        TenseConfig("pt_impers_inf", FormMatcher(("infinitive", "impersonal"))),
        TenseConfig("pt_impers_gerund", FormMatcher(("gerund",))),
        TenseConfig("pt_impers_partic", FormMatcher(("participle", "past", "masculine", "singular"))),
        pt_tense("pt_inf_personal", ("infinitive",)),
        pt_tense("pt_indic_pres", ("present", "indicative")),
        pt_tense("pt_indic_pret", ("preterite", "indicative")),
        pt_tense("pt_indic_imperf", ("imperfect", "indicative")),
        pt_tense("pt_indic_pluperf", ("pluperfect", "indicative")),
        pt_tense("pt_indic_fut", ("future", "indicative")),
        pt_tense("pt_cond_pres", ("conditional",)),
        pt_tense("pt_subj_pres", ("present", "subjunctive")),
        pt_tense("pt_subj_imperf", ("imperfect", "subjunctive")),
        pt_tense("pt_subj_fut", ("future", "subjunctive")),
        TenseConfig("pt_imper", tuple(
            FormMatcher((person, number, "imperative"), pronoun=pronoun)
            for (person, number), pronoun in zip(PERSONS_NUMBERS[1:], ("tu", "você", "nós", "vós", "vocês"))
        )),
    ),
    tense_groups=[
        TenseGroup("pt_indic", re.compile(r"^pt_indic_")),
        TenseGroup("pt_subj", re.compile(r"^pt_subj_")),
        TenseGroup("pt_cond", re.compile(r"^pt_cond_")),
        TenseGroup("pt_imper", re.compile(r"^pt_imper$")),
        TenseGroup("pt_inf", re.compile(r"^pt_inf_")),
        TenseGroup("pt_impers", re.compile(r"^pt_impers_")),
    ],
    preprocess_forms=preprocess_pt_forms, form_filter=romance_form_filter,
    exclude_tags=("proscribed",), rare_tags=("archaic",),
)

CA_CONFIG = LanguageConfig(
    code="ca", name="català", english_wiktionary_name="Catalan",
    tenses=(
        TenseConfig("ca_impers_inf", FormMatcher(("infinitive",))),
        TenseConfig("ca_impers_gerund", FormMatcher(("gerund",))),
        TenseConfig("ca_impers_partic", FormMatcher(("participle", "past", "masculine", "singular"))),
        ca_tense("ca_indic_pres", ("present", "indicative")),
        ca_tense("ca_indic_imperf", ("imperfect", "indicative")),
        ca_tense("ca_indic_pret", ("preterite", "indicative"), ("periphrastic",)),
        ca_tense("ca_indic_periphrastic", ("preterite", "indicative", "periphrastic")),
        ca_tense("ca_indic_fut", ("future", "indicative")),
        ca_tense("ca_cond_pres", ("conditional",)),
        ca_tense("ca_subj_pres", ("present", "subjunctive")),
        ca_tense("ca_subj_imperf", ("imperfect", "subjunctive")),
        TenseConfig("ca_imper", (
            # Wiktextract omits singular on the informal 2sg Catalan imperative.
            FormMatcher(("imperative", "second-person"), pronoun="tu", exclude_tags=("plural",)),
            FormMatcher(("imperative", "second-person-semantically", "singular"), pronoun="vostè"),
            FormMatcher(("imperative", "first-person", "plural"), pronoun="nosaltres"),
            FormMatcher(("imperative", "second-person", "plural"), pronoun="vosaltres"),
            FormMatcher(("imperative", "second-person-semantically", "plural"), pronoun="vostès"),
        )),
    ),
    tense_groups=[
        TenseGroup("ca_indic", re.compile(r"^ca_indic_")),
        TenseGroup("ca_subj", re.compile(r"^ca_subj_")),
        TenseGroup("ca_cond", re.compile(r"^ca_cond_")),
        TenseGroup("ca_imper", re.compile(r"^ca_imper$")),
        TenseGroup("ca_impers", re.compile(r"^ca_impers_")),
    ],
    preprocess_forms=preprocess_ca_forms, form_filter=romance_form_filter,
    rare_tags=("obsolete",),
)
