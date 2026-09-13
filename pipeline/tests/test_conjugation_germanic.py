"""Reviewed source-table regressions for Dutch and Swedish.

Fixtures are complete verb records from the pinned English Wiktionary dump.
Golden output is supplemented with independent principal-part expectations.
"""
import json
from pathlib import Path

import msgspec
import pytest

from pipeline.conjugation import extract_conjugation
from pipeline.conjugation_germanic import NL_CONFIG, SV_CONFIG, swedish_form_is_clean
from pipeline.wiktionary import Entry, Form, Sense

ROOT = Path(__file__).parent
CONFIGS = {"nl": NL_CONFIG, "sv": SV_CONFIG}
ENTRIES = {
    lang: {entry.word: entry for line in (ROOT / "fixtures" / f"{lang}_verbs.jsonl").read_bytes().splitlines()
           if (entry := msgspec.json.decode(line, type=Entry))}
    for lang in CONFIGS
}


def conjugation(lang, word):
    result = extract_conjugation(CONFIGS[lang], ENTRIES[lang][word])
    assert result is not None
    return result["conjugation"]


@pytest.mark.parametrize("lang,word", [(lang, word) for lang in ENTRIES for word in ENTRIES[lang]])
def test_reviewed_golden(lang, word, update_golden):
    result = extract_conjugation(CONFIGS[lang], ENTRIES[lang][word])
    assert result is not None
    path = ROOT / "golden" / "conj" / f"{lang}_{word.replace(':', '_')}.json"
    if update_golden:
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    assert json.loads(json.dumps(result)) == json.loads(path.read_text())


@pytest.mark.parametrize("word,present,past,participle", [
    ("werken", "werk", "werkte", "gewerkt"),
    ("zijn", "ben", "was", "geweest"),
    ("hebben", "heb", "had", "gehad"),
    ("gaan", "ga", "ging", "gegaan"),
    ("eten", "eet", "at", "gegeten"),
    ("zien", "zie", "zag", "gezien"),
    ("lopen", "loop", "liep", "gelopen"),
    ("opbellen", "bel op", "belde op", "opgebeld"),
    ("opstaan", "sta op", "stond op", "opgestaan"),
    ("aankomen", "kom aan", "kwam aan", "aangekomen"),
    ("downloaden", "download", "downloadde", "gedownload"),
])
def test_dutch_reviewed_principal_parts(word, present, past, participle):
    rows = conjugation("nl", word)
    assert (rows[0][0], rows[1][0], rows[5]) == (present, past, participle)


def test_dutch_person_groups_inversion_and_formal_variants():
    rows = conjugation("nl", "zijn")
    assert list(rows[0]) == ["ben", "bent/ben", "bent/is", "is", "zijn"]
    assert NL_CONFIG.tenses[0].form_matchers[1].pronoun == "jij / … jij"
    assert len(rows[0]) == len(rows[1]) == 5
    assert conjugation("nl", "hebben")[0][2] == "hebt/heeft"
    assert conjugation("nl", "werken")[0][1] == "werkt/werk"


def test_dutch_no_unlabelled_second_paradigm_or_guessed_auxiliary():
    rows = conjugation("nl", "werken")
    assert "wrocht" not in json.dumps(rows)
    assert all("perfect" not in tense.name for tense in NL_CONFIG.tenses)
    assert conjugation("nl", "zullen")[5] == ""


@pytest.mark.parametrize("word,present,past,supine,participle", [
    ("tala", "talar", "talade", "talat", "talad"),
    ("köpa", "köper", "köpte", "köpt", "köpt"),
    ("bo", "bor", "bodde", "bott", ""),
    ("skriva", "skriver", "skrev", "skrivit", "skriven"),
    ("vara", "är", "var", "varit", ""),
    ("se", "ser", "såg", "sett", "sedd"),
    ("äta", "äter", "åt", "ätit", "äten"),
    ("kunna", "kan", "kunde", "kunnat", ""),
    ("vilja", "vill", "ville", "velat", ""),
    ("sms:a", "sms:ar", "sms:ade", "sms:at", "sms:ad"),
])
def test_swedish_reviewed_principal_parts(word, present, past, supine, participle):
    rows = conjugation("sv", word)
    assert all(isinstance(row, str) for row in rows)
    assert (rows[0], rows[1], rows[16], rows[19]) == (present, past, supine, participle)
    assert rows[2] == f"har {supine}"
    assert rows[3] == f"hade {supine}"


@pytest.mark.parametrize("word,present,past,supine", [
    ("hoppas", "hoppas", "hoppades", "hoppats"),
    ("minnas", "minns/minnes", "mindes", "mints"),
    ("finnas", "finns/finnes", "fanns", "funnits"),
    ("träffas", "träffas", "träffades", "träffats"),
])
def test_swedish_deponent_s_form_and_homograph_category(word, present, past, supine):
    rows = conjugation("sv", word)
    assert rows[:5] == [""] * 5
    assert (rows[5], rows[6], rows[17]) == (present, past, supine)
    assert rows[7] == f"har {supine}"
    form_of = msgspec.structs.replace(ENTRIES["sv"][word], senses=(Sense(tags=("form-of",)),))
    assert extract_conjugation(SV_CONFIG, form_of) is None


def test_swedish_register_notes_and_participle_distinction():
    rows = conjugation("sv", "läsa")
    assert rows[1] == "läste/[las]"
    assert rows[16] == "läst/[läsit]"
    assert rows[18] == "läsande"
    assert rows[19] == "läst/[läsen]"
    assert conjugation("sv", "ha")[2] == "har haft"
    assert conjugation("sv", "ha")[0] == "har/[haver]"
    assert conjugation("sv", "gå")[4] == "gå"


def test_swedish_particle_forms_and_defective_cells():
    assert conjugation("sv", "huta")[0] == "hutar åt"
    assert conjugation("sv", "framlägga")[2] == "har lagt fram"
    assert conjugation("sv", "må")[16] == ""
    rows = conjugation("sv", "annalka")
    assert [x for x in rows if x] == ["annalkande"]


@pytest.mark.parametrize("text", ["Template:foo", "x:y:z", "sms:1", "<b>sms:ar</b>", "sms:ar\n", "class 2", "-"])
def test_swedish_rejects_malformed_form_text(text):
    assert not swedish_form_is_clean(Form(form=text, source="conjugation", tags={"active", "indicative", "present"}))
