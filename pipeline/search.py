import logging
import re
from collections import defaultdict
from typing import Any, Callable

from .gloss import _is_junk_gloss

log = logging.getLogger(__name__)


# Stop words for gloss search index
GLOSS_STOP_WORDS = frozenset(
    {
        "the", "and", "for", "not", "out", "off", "has", "are", "was",
        "but", "can", "may", "all", "any", "its", "also", "been", "into",
        "from", "with", "that", "this", "than", "when", "very", "more",
        "most", "such", "other",
        "something", "someone", "oneself", "one's", "etc", "e.g", "e.g.",
        "especially", "synonym", "spelling", "chiefly", "usually",
        "often", "sometimes",
    }
)

MIN_GLOSS_WORD_LENGTH = 3


def build_search_index(
    verbs: list[dict[str, Any]],
    phonetic_fn: Callable[[str], str] | None = None,
) -> dict[str, list[int]]:
    from .utils import strip_diacritics

    log.info("generating search index")
    searchable_words = defaultdict[str, set[int]](lambda: set())

    GERMAN_AUXILIARY_INFINITIVES = {"haben", "sein"}

    def add_to_index(s: str, idx: int):
        if s == "" or s == "-":
            return
        for ss in s.split("/"):
            if ' ' in ss:
                words = ss.split(' ')
                if len(words) >= 3 and words[-1] in GERMAN_AUXILIARY_INFINITIVES:
                    ss = words[-2]
                else:
                    ss = words[-1]
            searchable_words[ss].add(idx)
            searchable_words[strip_diacritics(ss)].add(idx)
            if phonetic_fn:
                phonetic = phonetic_fn(ss)
                if phonetic != ss and phonetic != strip_diacritics(ss):
                    searchable_words[phonetic].add(idx)

    for i, v in enumerate(verbs):
        searchable_words[v["name"]].add(i)
        searchable_words[strip_diacritics(v["name"])].add(i)
        if phonetic_fn:
            phonetic = phonetic_fn(v["name"])
            if phonetic != v["name"] and phonetic != strip_diacritics(v["name"]):
                searchable_words[phonetic].add(i)
        for c in v["conjugation"]:
            if isinstance(c, str):
                add_to_index(c, i)
            else:
                for cc in c:
                    add_to_index(cc, i)

    # Collect gloss words (English definitions) with prefix range 3-6
    gloss_words = defaultdict[str, set[int]](lambda: set())
    for i, v in enumerate(verbs):
        gloss = v.get("gloss", "")
        if not gloss:
            continue
        for clause in gloss.split("; "):
            if clause == "...":
                continue
            if _is_junk_gloss(clause):
                continue
            clause = re.sub(r"\s*\[.*?\]", "", clause)
            for token in re.split(r"[\s,;]+", clause.lower()):
                word = token.strip("().[]'\"")
                if len(word) >= MIN_GLOSS_WORD_LENGTH and word not in GLOSS_STOP_WORDS:
                    gloss_words[word].add(i)

    index = defaultdict[str, set[int]](lambda: set())

    MIN_PREFIX = 1
    MAX_PREFIX = 4
    MAX_PREFIX_IDS = 200

    for word, indices in searchable_words.items():
        for prefix_len in range(MIN_PREFIX, MAX_PREFIX + 1):
            word_prefix = word[:prefix_len].lower()
            for i in indices:
                index[word_prefix].add(i)

    # Gloss words use prefix range 3-6
    MIN_GLOSS_PREFIX = 3
    MAX_GLOSS_PREFIX = 6
    for word, ids in gloss_words.items():
        for prefix_len in range(MIN_GLOSS_PREFIX, MAX_GLOSS_PREFIX + 1):
            prefix = word[:prefix_len].lower()
            index[prefix].update(ids)

    ret = {k: sorted(v)[:MAX_PREFIX_IDS] for k, v in index.items()}

    max_hits = 0
    max_key = None
    for k, v in ret.items():
        if len(v) > max_hits:
            max_hits = len(v)
            max_key = k

    log.info(f"Longest index entry: '{max_key}', {max_hits} hits")

    return ret
