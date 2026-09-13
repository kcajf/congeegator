"""Reviewed Latin/Finnish paradigms and Hungarian extraction-failure evidence.

The explicit expectations below precede the generated golden snapshots. Latin
agreement/auxiliaries were checked against Allen & Greenough (DCC §§170,181–192),
and Finnish forms against Wiktionary's Finnish conjugation/form appendices and
the displayed puhua/ei tables. Goldens provide regression coverage, not an
independent linguistic accuracy claim.
"""

import json
from pathlib import Path

import msgspec
import pytest

from pipeline.conjugation import entry_is_clean_verb_root, extract_conjugation
from pipeline.conjugation_extended import FI_CONFIG, LA_CONFIG, extended_form_is_clean, preprocess_fi_forms, preprocess_la_forms
from pipeline.wiktionary import Entry, Form, HeadTemplate, Sense


FIXTURES = Path(__file__).parent / "fixtures"
GOLDENS = Path(__file__).parent / "golden" / "conj"
CONFIGS = {"la": LA_CONFIG, "fi": FI_CONFIG}
WORDS = {
    "la": "amo moneo rego capio audio sum possum fero eo volo nolo malo fio loquor hortor vereor patior sequor audeo gaudeo soleo odi coepi memini pluit licet piget".split(),
    "fi": "puhua sanoa saada syödä mennä tulla olla nähdä tehdä juosta lukea haluta tarvita lämmetä vanheta ei voida sataa täytyä".split(),
}


def entries(code):
    return [msgspec.json.decode(line, type=Entry) for line in (FIXTURES / f"{code}_verbs.jsonl").read_bytes().splitlines() if line]


def result(code, word):
    for entry in entries(code):
        if entry.word == word:
            value = extract_conjugation(CONFIGS[code], entry)
            if value is not None:
                return value
    pytest.fail(f"Reviewed verb is missing or rejected: {code}/{word}")


def table(code, word, name):
    config = CONFIGS[code]
    index = next(i for i, tense in enumerate(config.tenses) if tense.name == name)
    return result(code, word)["conjugation"][index]


@pytest.mark.parametrize("word,expected", [
    ("amo", "amō amās amat amāmus amātis amant"),
    ("moneo", "moneō monēs monet monēmus monētis monent"),
    ("rego", "regō regis regit regimus regitis regunt"),
    ("capio", "capiō capis capit capimus capitis capiunt"),
    ("audio", "audiō audīs audit audīmus audītis audiunt"),
    ("sum", "sum es est sumus estis sunt"),
    ("possum", "possum potes potest possumus potestis possunt"),
    ("fero", "ferō fers fert ferimus fertis ferunt"),
    ("eo", "eō īs it īmus ītis eunt"),
    ("fio", "fīō fīs fit fīmus fītis fīunt"),
])
def test_latin_regular_classes_and_irregular_present(word, expected):
    assert table("la", word, "la_indic_pres_active") == tuple(expected.split())


def test_latin_future_perfect_does_not_leak_into_other_tenses():
    assert table("la", "amo", "la_indic_fut_active")[0] == "amābō"
    assert table("la", "amo", "la_indic_perf_active")[0] == "amāvī"
    assert "amāverō" in table("la", "amo", "la_indic_fut_perf_active")[0].split("/")


def test_latin_perfect_passive_person_number_gender_agreement():
    forms = table("la", "amo", "la_indic_perf_passive")
    assert forms[0].split("/") == ["amātus sum (masculine)", "amāta sum (feminine)", "amātum sum (neuter)"]
    assert forms[3].split("/") == ["amātī sumus (masculine)", "amātae sumus (feminine)", "amāta sumus (neuter)"]
    assert "amātae erunt (feminine)" in table("la", "amo", "la_indic_fut_perf_passive")[5]
    assert "amātae essētis (feminine)" in table("la", "amo", "la_subj_pluperf_passive")[4]
    assert "amātus sumus" not in "/".join(forms)


@pytest.mark.parametrize("word,present,perfect", [
    ("loquor", "loquor", "locūtus"), ("hortor", "hortor", "hortātus"),
    ("vereor", "vereor", "veritus"), ("patior", "patior", "passus"),
    ("sequor", "sequor", "secūtus"), ("audeo", "audeō", "ausus"),
    ("gaudeo", "gaudeō", "gāvīsus"), ("soleo", "soleō", "solitus"),
])
def test_deponent_and_semideponent_forms_keep_active_meaning(word, present, perfect):
    assert table("la", word, "la_indic_pres_active")[0] == present
    assert f"{perfect} sum (masculine)" in table("la", word, "la_indic_perf_active")[0]
    assert not any(table("la", word, "la_indic_perf_passive"))


def test_latin_defective_and_impersonal_cells_are_not_invented():
    assert not any(table("la", "coepi", "la_indic_pres_active"))
    assert table("la", "coepi", "la_indic_perf_active")[0] == "coepī"
    assert table("la", "odi", "la_indic_pres_active")[0] == "ōdī"
    assert table("la", "memini", "la_indic_pres_active")[0] == "meminī"
    assert not any(table("la", "memini", "la_indic_perf_active"))
    assert table("la", "pluit", "la_indic_pres_active") == ("", "", "pluit", "", "", "")
    assert not any(table("la", "sum", "la_indic_pres_passive"))


def test_latin_rendered_shared_recipe_and_explicit_compounds():
    # Rendered sequor has both participles sharing one sum recipe. The raw
    # extractor leaves secūtus without the auxiliary clause.
    assert "secūtae sumus (feminine)" in table("la", "sequor", "la_indic_perf_active")[3]
    assert "sequūtae sumus (feminine)" in table("la", "sequor", "la_indic_perf_active")[3]
    assert "ausae sumus (feminine)" in table("la", "audeo", "la_indic_perf_active")[3]
    assert "solita sumus (neuter)" in table("la", "soleo", "la_indic_perf_active")[3]
    # erint is a documented rare variant on Wiktionary's audeo and erint pages.
    assert "[ausī erint (masculine)]" in table("la", "audeo", "la_indic_fut_perf_active")[5]
    assert "[siem]" in table("la", "sum", "la_subj_pres_active")[0]
    assert "[fuam]" in table("la", "sum", "la_subj_pres_active")[0]
    assert "[siēmus]" in table("la", "sum", "la_subj_pres_active")[3]
    assert "[siētis]" in table("la", "sum", "la_subj_pres_active")[4]
    assert "[fuāmus]" in table("la", "sum", "la_subj_pres_active")[3]
    assert "[fuātis]" in table("la", "sum", "la_subj_pres_active")[4]


def test_latin_imperatives_and_nonfinite_citation_forms():
    assert table("la", "amo", "la_imper_pres_active") == ("amā", "amāte")
    assert table("la", "amo", "la_imper_fut_active") == ("amātō", "amātō", "amātōte", "amantō")
    assert table("la", "amo", "la_nonfinite_inf_pres_active") == "amāre"
    assert table("la", "amo", "la_nonfinite_inf_fut_passive") == "amātum īrī"
    assert table("la", "amo", "la_nonfinite_gerund") == ("amandī", "amandō", "amandum", "amandō")
    assert table("la", "amo", "la_nonfinite_supine") == ("amātum", "amātū")


def test_recipe_expansion_is_bounded_and_preserves_restricted_persons():
    raw = Entry(pos="verb", lang="Latin", lang_code="la", word="test", forms=(
        Form("amātus + present active indicative of sum", {"indicative", "passive", "perfect", "third-person", "plural"}, "conjugation"),
        Form("amātus + unknown form of sum", {"indicative", "passive", "perfect"}, "conjugation"),
    ))
    clean = [f for f in preprocess_la_forms(raw) if extended_form_is_clean(f)]
    assert len(clean) == 3
    assert all("third-person" in f.tags and "plural" in f.tags for f in clean)
    assert {f.form for f in clean} == {"amātī sunt (masculine)", "amātae sunt (feminine)", "amāta sunt (neuter)"}


@pytest.mark.parametrize("word,expected", [
    ("puhua", "puhun puhut puhuu puhumme puhutte puhuvat puhutaan"),
    ("olla", "olen olet on olemme olette ovat ollaan"),
    ("syödä", "syön syöt syö syömme syötte syövät syödään"),
    ("nähdä", "näen näet näkee näemme näette näkevät nähdään"),
    ("tehdä", "teen teet tekee teemme teette tekevät tehdään"),
    ("juosta", "juoksen juokset juoksee juoksemme juoksette juoksevat juostaan"),
    ("lukea", "luen luet lukee luemme luette lukevat luetaan"),
    ("haluta", "haluan haluat haluaa haluamme haluatte haluavat halutaan"),
    ("tarvita", "tarvitsen tarvitset tarvitsee tarvitsemme tarvitsette tarvitsevat tarvitaan"),
    ("vanheta", "vanhenen vanhenet vanhenee vanhenemme vanhenette vanhenevat vanhetaan"),
])
def test_finnish_regular_types_gradation_and_irregular_present(word, expected):
    assert table("fi", word, "fi_indic_pres") == tuple(expected.split())


def test_finnish_negative_auxiliary_person_and_participle_agreement():
    assert table("fi", "puhua", "fi_indic_pres_neg") == ("en puhu", "et puhu", "ei puhu", "emme puhu", "ette puhu", "eivät puhu", "ei puhuta")
    assert table("fi", "syödä", "fi_indic_past_neg")[0] == "en syönyt"
    assert table("fi", "syödä", "fi_indic_past_neg")[3] == "emme syöneet"
    assert table("fi", "puhua", "fi_indic_perf")[3] == "olemme puhuneet"
    assert table("fi", "puhua", "fi_indic_pluperf_neg")[5] == "eivät olleet puhuneet"
    assert table("fi", "puhua", "fi_cond_pres")[0] == "puhuisin"
    assert table("fi", "puhua", "fi_cond_perf_neg")[0] == "en olisi puhunut"
    assert table("fi", "puhua", "fi_pot_pres")[0] == "puhunen"
    assert table("fi", "puhua", "fi_pot_perf_neg")[0] == "en liene puhunut"


def test_finnish_imperative_and_impersonal_passive():
    assert table("fi", "puhua", "fi_imper_pres") == ("puhu", "puhukoon", "puhukaamme", "puhukaa", "puhukoot", "puhuttakoon")
    assert table("fi", "puhua", "fi_imper_pres_neg") == ("älä puhu", "älköön puhuko", "älkäämme puhuko", "älkää puhuko", "älkööt puhuko", "älköön puhuttako")
    assert table("fi", "puhua", "fi_indic_perf")[-1] == "on puhuttu"
    assert table("fi", "puhua", "fi_indic_pluperf_neg")[-1] == "ei ollut puhuttu"


def test_finnish_ei_and_impersonal_modal_are_not_regularized():
    assert table("fi", "ei", "fi_indic_pres") == ("en", "et", "ei", "emme", "ette", "eivät", "")
    assert table("fi", "ei", "fi_imper_pres") == ("älä", "älköön", "älkäämme", "älkää", "älkööt", "")
    assert not any(table("fi", "ei", "fi_indic_pres_neg"))
    assert table("fi", "ei", "fi_nonfinite_inf") == ""
    assert table("fi", "täytyä", "fi_indic_pres") == ("", "", "täytyy", "", "", "", "")


def test_finnish_explicit_slang_template_does_not_contaminate_standard_paradigm():
    assert table("fi", "stemmata", "fi_indic_pres")[5] == "stemmaavat"
    assert table("fi", "stemmata", "fi_indic_perf_neg")[2] == "ei ole stemmannut"
    assert table("fi", "stemmata", "fi_nonfinite_inf") == "stemmata"
    assert "ei oo stemmannu" not in json.dumps(result("fi", "stemmata"), ensure_ascii=False)
    raw = Entry(pos="verb", lang_code="fi", lang="Finnish", word="test", forms=(
        Form("fi-conj-salata-slang", {"inflection-template"}, "conjugation"),
        Form("slang", {"present"}, "conjugation"),
        Form("no-table-tags", {"table-tags"}, "conjugation"),
        Form("fi-conj-salata", {"inflection-template"}, "conjugation"),
        Form("standard", {"present"}, "conjugation"),
    ))
    assert [f.form for f in preprocess_fi_forms(raw) if extended_form_is_clean(f)] == ["standard"]


@pytest.mark.parametrize("code,word", [("la", "licet"), ("la", "odi"), ("la", "coepi"), ("la", "fio"), ("fi", "haluta"), ("fi", "vanheta")])
def test_real_lemma_survives_page_category_contamination(code, word):
    assert result(code, word) is not None
    fake = Entry(pos="verb", lang_code=code, lang="Latin" if code == "la" else "Finnish", word=word,
                 head_templates=(HeadTemplate(f"{code}-verb"),), senses=(Sense(glosses=("inflection of something",), tags=("form-of",)),))
    assert entry_is_clean_verb_root(fake) is False


def test_hungarian_fixture_documents_why_person_tag_matching_is_not_safe():
    raw = next(e for e in entries("hu") if e.word == "ír")
    # The displayed Wiktionary table has írok=1sg, írsz=2sg, ír=3sg. The pinned
    # JSONL instead labels them 2sg, 3sg, 1pl and omits the indicative mood.
    forms = {f.form: f for f in reversed(raw.forms)}
    assert {"error-unrecognized-form", "second-person", "singular"} <= forms["írok"].tags
    assert "first-person" not in forms["írok"].tags
    assert {"first-person", "plural"} <= forms["ír"].tags
    assert not any(extended_form_is_clean(f) for f in raw.forms if f.form in {"írok", "írsz", "ír"})


@pytest.mark.parametrize("code,word", [(code, word) for code, words in WORDS.items() for word in words])
def test_extended_golden(code, word, update_golden):
    actual = json.loads(json.dumps(result(code, word), ensure_ascii=False))
    path = GOLDENS / f"{code}_{word}.json"
    if update_golden:
        path.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n")
        pytest.skip(f"Updated {path.name}")
    assert path.exists(), f"Missing reviewed snapshot: {path}"
    assert actual == json.loads(path.read_text())
