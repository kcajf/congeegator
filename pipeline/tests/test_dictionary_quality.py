"""Regressions discovered in the September 2026 full-language quality review."""

import pytest

from pipeline.dictionary import DictLanguageConfig, extract_forms, extract_gender, extract_senses, process_dict_entry
from pipeline.wiktionary import Entry, Form, HeadTemplate, Sense


def entry(**kwargs):
    defaults = dict(pos="noun", lang_code="pt", lang="Portuguese", word="casa", senses=(Sense(glosses=("house",)),))
    return Entry(**(defaults | kwargs))


def test_nested_form_of_gloss_retains_lemma_and_subsense_context():
    result = extract_senses(entry(senses=(Sense(glosses=("inflection of casar:", "third-person singular present indicative")),)))
    assert result == [{"gloss": "inflection of casar: third-person singular present indicative"}]


@pytest.mark.parametrize("dirty", ["Template:adj form of", "{{{pl}}}", "[[missing", "Lua error", "text <i>unfinished"])
def test_dirty_sense_is_omitted_and_other_senses_survive(dirty):
    result = extract_senses(entry(senses=(Sense(glosses=(dirty,)), Sense(glosses=("house",)))))
    assert result == [{"gloss": "house"}]


def test_ordinary_template_definition_and_mathematical_angle_brackets_survive():
    text = "template: a macromolecule which provides a pattern; x < y"
    assert extract_senses(entry(senses=(Sense(glosses=(text,)),)))[0]["gloss"] == text


def test_dirty_optional_fields_do_not_drop_good_entry():
    value = entry(
        senses=(Sense(glosses=("house",), examples=({"text": "{{bad}}"}, {"text": "a casa"})),),
        forms=(Form(form="{{{pl}}}"), Form(form="casas")),
        sounds=({"ipa": "[[:Template:pt-IPA"}, {"ipa": "/ˈkazɐ/"}),
    )
    result = process_dict_entry(DictLanguageConfig("pt", "português", "Portuguese"), value)
    assert result["forms"] == ["casas"]
    assert result["senses"][0]["examples"] == ["a casa"]
    assert result["pronunciation"] == "/ˈkazɐ/"


@pytest.mark.parametrize("code,word,template,tags,expected", [
    ("ru", "ребёнок", HeadTemplate("ru-noun+", {"1": "f"}), ("animate", "masculine"), "m"),
    ("da", "kvinde", HeadTemplate("da-noun", {"1": "n", "g": "c"}), ("common-gender",), "c"),
    ("nb", "bok", HeadTemplate("nb-noun", {}), ("feminine", "masculine"), "m-f"),
    ("la", "aqua", HeadTemplate("la-noun", {"1": "aqua<1>"}), ("declension-1", "feminine"), "f"),
])
def test_gender_uses_parsed_tags_not_language_specific_positional_args(code, word, template, tags, expected):
    assert extract_gender(entry(lang_code=code, word=word, head_templates=(template,), senses=(Sense(glosses=("definition",), tags=tags),))) == expected


def test_positional_gender_is_not_guessed_when_parsed_tags_absent():
    assert extract_gender(entry(head_templates=(HeadTemplate("ru-noun+", {"1": "f"}),))) is None


def test_canonical_macrons_preserved_while_grammar_metadata_is_removed():
    value = entry(lang_code="la", word="edo", forms=(
        Form("edō", {"canonical"}), Form("irregular conjugation", {"canonical"}),
        Form("3", {"class"}), Form("edunt", {"third-person", "plural"}),
    ))
    assert extract_forms(value) == ["edō", "edunt"]


def test_romanization_and_classifiers_are_not_misrepresented_as_forms():
    value = entry(forms=(Form("cái", {"classifier"}), Form("dom", {"romanization"}), Form("casas", {"plural"})))
    assert extract_forms(value) == ["casas"]


def test_finnish_headers_and_hungarian_alternative_marker():
    assert extract_forms(entry(lang_code="fi", forms=(Form("imperative mood", {"indicative", "person"}), Form("älä", {"second-person"})))) == ["älä"]
    assert extract_forms(entry(lang_code="hu", forms=(Form("eszem", {"error-unrecognized-form"}), Form("or eszek", {"error-unrecognized-form"})))) == ["eszem", "eszek"]


def test_historical_usage_labels_survive():
    assert extract_senses(entry(senses=(Sense(glosses=("him",), tags=("Old-Latin",)),)))[0]["tags"] == ["Old-Latin"]


@pytest.mark.parametrize("code,text,tags,expected", [
    ("nl", "form z'n", {"contracted"}, ["z'n"]),
    ("ro", "equivalent bună", {"feminine"}, ["bună"]),
    ("la", "declension", {"pronominal"}, []),
    ("nb", "used with neuter nouns", {"article", "neuter"}, []),
    ("pl", "cases", {"accusative", "genitive"}, []),
    ("ro", "of dezabuza", {"participle", "past"}, []),
])
def test_known_source_header_and_label_artifacts(code, text, tags, expected):
    assert extract_forms(entry(lang_code=code, forms=(Form(text, tags),))) == expected
