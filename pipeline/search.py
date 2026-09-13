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
    lang: str | None = None,
) -> dict[str, list[int]]:
    from .utils import strip_diacritics

    log.info("generating search index")
    MAX_PREFIX = 6
    searchable_words = defaultdict[str, set[int]](lambda: set())
    exact_forms = defaultdict[str, set[int]](lambda: set())
    expanded_language = lang in {"en", "pt", "ca", "nl", "sv", "fi", "la"}

    GERMAN_AUXILIARY_INFINITIVES = {"haben", "sein"}

    def add_to_index(s: str, idx: int):
        if s == "" or s == "-":
            return
        for ss in s.split("/"):
            # Usage qualifiers describe a variant; they are not its spelling.
            ss = re.sub(r"\s+\([^()]+\)(?=[\]}]*$)", "", ss)
            ss = ss.strip("[]{}()")
            if not ss.strip():
                continue
            if expanded_language:
                # Keep whole forms distinct from auxiliary tokens: har is a
                # form of ha, but merely a word inside har skrivit.
                exact_forms[ss.lower()].add(idx)
                exact_forms[strip_diacritics(ss).lower()].add(idx)
                # Longer whole forms are retrieved through the maximum
                # six-character key (essēmus -> essemu), not their full key.
                # Auxiliary words inside compounds must not receive this rank.
                exact_forms[ss[:MAX_PREFIX].lower()].add(idx)
                exact_forms[strip_diacritics(ss)[:MAX_PREFIX].lower()].add(idx)
                # Separable verbs and Latin/Finnish compounds do not always
                # put the lexical form last. Index the phrase and its words.
                # Preserve phrase/token order so JSON keys and bundle hashes
                # are reproducible across Python hash seeds.
                for token in dict.fromkeys((ss, *ss.split())):
                    searchable_words[token].add(idx)
                    searchable_words[strip_diacritics(token)].add(idx)
                continue
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

    # Native and gloss share MAX_PREFIX so neither can populate keys the other
    # can't reach — otherwise prefixLookup walks longest-first and gets shadowed
    # by a bucket that has only one source's IDs.
    MIN_PREFIX = 1
    MIN_GLOSS_PREFIX = 3
    MAX_PREFIX_IDS = 200

    for word, indices in searchable_words.items():
        if not word:
            continue
        for prefix_len in range(MIN_PREFIX, MAX_PREFIX + 1):
            word_prefix = word[:prefix_len].lower()
            for i in indices:
                index[word_prefix].add(i)

    for word, ids in gloss_words.items():
        for prefix_len in range(MIN_GLOSS_PREFIX, MAX_PREFIX + 1):
            prefix = word[:prefix_len].lower()
            index[prefix].update(ids)

    if expanded_language:
        roots = [(v["name"].lower(), strip_diacritics(v["name"]).lower()) for v in verbs]

        def candidate_priority(prefix: str, idx: int):
            return (
                prefix not in roots[idx],
                idx not in exact_forms.get(prefix, ()),
                not any(root.startswith(prefix) for root in roots[idx]),
                -verbs[idx].get("freq", 0),
                idx,
            )

        ret = {k: sorted(v, key=lambda idx: candidate_priority(k, idx))[:MAX_PREFIX_IDS]
               for k, v in index.items()}
    else:
        ret = {k: sorted(v)[:MAX_PREFIX_IDS] for k, v in index.items()}

    max_hits = 0
    max_key = None
    for k, v in ret.items():
        if len(v) > max_hits:
            max_hits = len(v)
            max_key = k

    log.info(f"Longest index entry: '{max_key}', {max_hits} hits")

    return ret
