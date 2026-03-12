import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data_processing import to_phonetic_el


@pytest.mark.parametrize(
    "input_str, expected",
    [
        # Consonant bigrams
        ("μπαίνω", "beno"),
        ("ντύνω", "dino"),
        ("γκρεμίζω", "gremizo"),
        ("τσάι", "tse"),
        ("τζάκι", "dzaki"),
        # αυ/ευ voicing: before voiceless → f
        ("αυτός", "aftos"),
        ("ευτυχία", "eftichia"),
        # αυ/ευ voicing: before voiced → v
        ("αυλή", "avli"),
        ("ευλογώ", "evlogo"),
        # αυ/ευ at end of word → f
        ("ευ", "ef"),
        # Vowel digraphs
        ("αίμα", "ema"),
        ("είμαι", "ime"),
        ("οίκος", "ikos"),
        ("ούτε", "ute"),
        # Single vowels
        ("ήμουν", "imun"),
        ("ώρα", "ora"),
        # Real verbs
        ("κάνω", "kano"),
        ("θέλω", "thelo"),
        ("αγαπώ", "agapo"),
        ("τρώω", "troo"),
        ("έχω", "echo"),
        # Latin input passthrough
        ("kano", "kano"),
        ("thelo", "thelo"),
        # Latin normalization
        ("cyma", "kima"),
        ("phyllo", "fillo"),
        ("kueri", "kueri"),
        # Latin vowel digraphs (naive transliteration convergence)
        ("eimai", "ime"),
        ("imai", "ime"),
        ("oikos", "ikos"),
        ("oute", "ute"),
        # Latin consonant bigrams
        ("mpeno", "beno"),
        ("ntino", "dino"),
        ("gkremizo", "gremizo"),
        # x, h, and w
        ("exo", "echo"),
        ("psaxno", "psachno"),
        ("eho", "echo"),
        ("eiha", "icha"),
        ("thelo", "thelo"),  # th stays as th
        ("kanw", "kano"),  # w as omega
        # Latin full words
        ("mirizei", "mirizi"),
        ("milousa", "milusa"),
        # Latin au/eu voicing
        ("autos", "aftos"),
        ("euro", "evro"),
        ("eu", "ef"),
        ("avli", "avli"),
        # Mixed / edge cases
        ("", ""),
        ("ξέρω", "ksero"),
        ("ψάχνω", "psachno"),
        # γγ
        ("αγγελία", "angelia"),
    ],
)
def test_to_phonetic_el(input_str, expected):
    assert to_phonetic_el(input_str) == expected
