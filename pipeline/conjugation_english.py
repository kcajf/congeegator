"""English rows from attested Wiktionary headword principal parts.

Headword forms intentionally have no source='conjugation'. This adapter only
accepts identified English verb heads and exact grammatical principal-part tags;
it never generates suffix spellings. The base supplies zero-ending persons.
"""
import re
import unicodedata

import msgspec

from .conjugation_types import FormMatcher, LanguageConfig, TenseConfig, TenseGroup, repeated_tense
from .gloss import extract_gloss
from .wiktionary import Entry, Form

EN_MERGE_ROOTS = frozenset({'lie', 'bear'})
_CORE_MODALS = frozenset({'can', 'could', 'may', 'might', 'must', 'shall', 'should', 'will', 'would'})
_MODAL_PAST = {'can': 'could', 'may': 'might', 'shall': 'should', 'will': 'would'}
_EXCLUDED = {'alternative', 'archaic', 'obsolete', 'nonstandard', 'proscribed', 'misspelling', 'pronunciation-spelling', 'romanization', 'suppletive', 'canonical'}
_GRAMMAR = {'present', 'past', 'participle', 'singular', 'plural', 'first-person', 'second-person', 'third-person', 'infinitive', 'indicative', 'imperative', 'subjunctive'}
_LABELS = {'US', 'UK', 'British', 'Canada', 'Australia', 'New-Zealand', 'Ireland', 'Scotland', 'England', 'Northern-England', 'Northern-Ireland', 'Commonwealth', 'India', 'South-Africa', 'Southern-US', 'Geordie', 'Northumbria', 'Yorkshire', 'Ulster', 'rare', 'uncommon', 'dated', 'colloquial', 'informal', 'literary', 'poetic', 'humorous', 'slang', 'modal', 'dialectal', 'regional'}
_THIRD = {'present', 'singular', 'third-person'}
_PRESENT_PART = {'present', 'participle'}
_PAST_PART = {'past', 'participle'}


def _lexical_text(text: str | None) -> bool:
    if not text or text != text.strip() or len(text) > 150:
        return False
    # Permit actual English phrase/hyphen forms, never descriptions, labels,
    # pronunciation, placeholders, digits, or unexpanded template expressions.
    return all(part and all(unicodedata.category(c)[0] in {'L', 'M'} for c in part)
               for part in re.split(r"[ -]", text))


def _head_identifies_verb(entry: Entry) -> bool:
    return any(h.name == 'en-verb' or (h.name == 'head' and h.args.get('1') == 'en'
               and h.args.get('2') == 'verb' and 'third-person singular simple present' in h.args.values())
               for h in entry.head_templates)


def _lexical_senses(entry: Entry):
    return [s for s in entry.senses if s.glosses and not set(s.tags) & {'form-of', 'alt-of'}]


def _sense_labels(entry: Entry) -> set[str]:
    senses = _lexical_senses(entry)
    return set.intersection(*(set(s.tags) & (_LABELS - {'modal'}) for s in senses)) if senses else set()


def extract_english_gloss(entry: Entry) -> str | None:
    """Keep the displayed meaning aligned with modern accepted paradigms."""
    modern = tuple(s for s in _lexical_senses(entry)
                   if not set(s.tags) & {'obsolete', 'archaic'})
    return extract_gloss(msgspec.structs.replace(entry, senses=modern) if modern else entry)


def _principal_parts(entry: Entry) -> dict[str, list[Form]]:
    parts: dict[str, list[Form]] = {'third': [], 'ing': [], 'past': [], 'pp': []}
    if not _head_identifies_verb(entry):
        return parts
    for form in entry.forms:
        if form.source is not None or form.tags & _EXCLUDED or not _lexical_text(form.form):
            continue
        if len(re.split(r'[ -]', form.form)) != len(re.split(r'[ -]', entry.word)):
            continue
        grammar = form.tags & _GRAMMAR
        key = ('third' if grammar == _THIRD else 'ing' if grammar == _PRESENT_PART
               else 'pp' if grammar == _PAST_PART else 'past' if grammar == {'past'} else None)
        # The rendered drink head applies a shared nonstandard/historical
        # qualifier to these alternatives; the pinned extractor lost it.
        if entry.word == 'drink' and key == 'pp' and form.form in {'drinken', 'dranken'}:
            continue
        if key:
            parts[key].append(Form(form.form, form.tags | _sense_labels(entry), form.source, form.topics))
    return parts


def english_has_attested_head_paradigm(entry: Entry) -> bool:
    """Positive lexical evidence used for inherited-category/phrase filtering."""
    if entry.lang_code != 'en' or not _lexical_text(entry.word):
        return False
    parts = _principal_parts(entry)
    return all(parts.values()) or (entry.word in _CORE_MODALS and any(f.form == entry.word for f in parts['third']))


def english_form_is_clean(form: Form) -> bool:
    if form.source != 'conjugation' or form.tags & _EXCLUDED:
        return False
    if not form.tags & _GRAMMAR or form.tags & {'table-tags', 'inflection-template', 'negative', 'combined-form'}:
        return False
    return _lexical_text(re.sub(r' \([^()]+\)$', '', form.form or ''))


def _usage_label(entry: Entry, parts: dict[str, list[Form]]) -> str | None:
    past = {f.form for f in parts['past']}
    if entry.word == 'lie':
        return 'reclining' if 'lay' in past else 'telling untruths' if 'lied' in past else None
    if entry.word == 'bear':
        return 'carrying' if 'bore' in past else 'finance' if 'beared' in past else None
    return None


def _adapt(form: Form, tags: set[str], usage: str | None = None) -> Form:
    labels = ([usage] if usage else []) + [s.replace('-', ' ') for s in sorted(form.tags & _LABELS)]
    if 'in-compounds' in form.tags:
        labels.append('usually in compounds' if 'usually' in form.tags else 'in compounds')
    labels += [s for s in form.topics if s == 'law']
    text = form.form + (f" ({', '.join(dict.fromkeys(labels))})" if labels else '')
    return Form(text, tags | (form.tags & _EXCLUDED), 'conjugation')


def preprocess_en_forms(entry: Entry) -> list[Form]:
    senses = _lexical_senses(entry)
    if senses and all(set(s.tags) & {'obsolete', 'archaic'} for s in senses):
        return []
    if entry.word == 'be' and any(f.source == 'conjugation' for f in entry.forms):
        # Be has its own person distinctions. The source fails to mark art
        # archaic; never put that thou-form under the modern pronoun you.
        return [f for f in entry.forms if f.source == 'conjugation' and f.form not in {'art', "'rt"}]
    if entry.word == 'beware' and any(h.name == 'en-verb' for h in entry.head_templates):
        # Cambridge: modern beware is used only as imperative or infinitive.
        return [Form('beware', {'infinitive'}, 'conjugation')]
    parts = _principal_parts(entry)
    if not _lexical_text(entry.word):
        return []
    modal = entry.word in _CORE_MODALS and any(f.form == entry.word for f in parts['third'])
    if modal:
        # Even the source's 'able'/'couth' and modal 'willing' are not ordinary
        # nonfinite forms. No infinitive means no fabricated will can/may/etc.
        result = []
        modal_past = [f for f in parts['past'] if f.form == _MODAL_PAST.get(entry.word)]
        for tense, forms in [('present', parts['third']), ('past', modal_past)]:
            for form in forms:
                for tags in ({'first-person','singular'}, {'second-person','singular'}, {'third-person','singular'}, {'plural'}):
                    result.append(_adapt(form, tags | {tense}))
        return result
    # Partial/defective entries cannot establish the ordinary complete paradigm.
    if not all(parts.values()):
        return []
    result = [_adapt(Form(entry.word, _sense_labels(entry)), {'infinitive'})]
    # If only a rare third-person form is attested, keep that restriction on
    # the otherwise uninflected present persons as well.
    base_tags = set.intersection(*(f.tags & _LABELS for f in parts['third']))
    base = Form(entry.word, base_tags)
    for tags in ({'first-person','singular'}, {'second-person','singular'}, {'plural'}):
        result.append(_adapt(base, tags | {'present'}))
    result.extend(_adapt(f, _THIRD) for f in parts['third'])
    usage = _usage_label(entry, parts)
    for form in parts['past']:
        for tags in ({'first-person','singular'}, {'second-person','singular'}, {'third-person','singular'}, {'plural'}):
            result.append(_adapt(form, tags | {'past'}, usage))
    result.extend(_adapt(f, _PRESENT_PART) for f in parts['ing'])
    # Born belongs to the passive birth construction (was born); ordinary
    # active perfects of bear require borne. Do not produce "have born".
    result.extend(_adapt(f, _PAST_PART, usage) for f in parts['pp']
                  if not (entry.word == 'bear' and f.form == 'born'))
    return result


def merge_english_records(existing: dict, incoming: dict) -> dict:
    """Merge attested ordinary homographs with source-gloss meaning labels.

    Existing contextual labels survive subsequent merges; a repeated source
    record never adds alternatives. Core modal paradigms stay separate from
    their ordinary lexical homographs (can food, will property, etc.).
    """
    if existing['name'] != incoming['name']:
        return existing
    if existing['name'] in _CORE_MODALS:
        if not existing['conjugation'][0]:
            return existing
        if not incoming['conjugation'][0]:
            return incoming
    def context(record):
        # Slashes delimit forms, brackets/parentheses delimit UI qualifiers.
        # Keep all accumulated contexts: two initially identical homographs
        # can acquire a differing third paradigm in a later merge.
        return '; '.join(dict.fromkeys(
            re.sub(r'\s+', ' ', re.sub(r'[/\[\]{}()]', ' ', gloss)).strip().removeprefix('to ')
            for gloss in record.get('gloss', '').split('; ') if gloss and gloss != '...'))
    def bare(form):
        return re.sub(r' \([^()]+\)$', '', form)
    def qualify(form, meaning):
        if not meaning or 'meaning: ' in form or (existing['name'] in EN_MERGE_ROOTS and re.search(r' \((?:reclining|telling untruths|carrying|finance)', form)):
            return form
        if form.endswith(')') and ' (' in form:
            return form[:-1] + '; meaning: ' + meaning + ')'
        return form + ' (meaning: ' + meaning + ')'
    def meaning_covers(existing_form, new_form):
        if 'meaning: ' not in existing_form or 'meaning: ' not in new_form:
            return existing_form == new_form
        old_prefix, old_context = existing_form.split('meaning: ', 1)
        new_prefix, new_context = new_form.split('meaning: ', 1)
        return old_prefix == new_prefix and set(new_context.removesuffix(')').split('; ')) <= set(old_context.removesuffix(')').split('; '))
    def merge_cell(a, b):
        left = [x for x in a.split('/') if x]
        right = [x for x in b.split('/') if x]
        left_bare = {bare(x) for x in left}
        right_bare = {bare(x) for x in right}
        # Repeated records are common in the source. Only introduce meaning
        # labels when spellings diverge, or when a spelling already has a
        # meaning label that must retain another homograph's association.
        differs = not (right_bare <= left_bare)
        result = [qualify(x, context(existing)) if differs and bare(x) not in right_bare else x for x in left]
        for form in right:
            matches = [x for x in result if bare(x) == bare(form)]
            if not matches:
                result.append(qualify(form, context(incoming)))
            elif any('meaning: ' in x for x in matches):
                # Keep distinct restrictions attached to their own meanings:
                # spelt (UK; meaning: letters) also occurs without that UK
                # restriction for the separate work-in-place-of meaning.
                candidate = qualify(form, context(incoming))
                if not any(meaning_covers(x, candidate) for x in matches):
                    result.append(candidate)
            elif form not in matches and not any(x == bare(x) for x in matches):
                # An unrestricted attestation must not inherit a different
                # homograph's rare/regional qualification.
                result.append(form)
        return '/'.join(dict.fromkeys(result))
    result = dict(existing)
    result['conjugation'] = [merge_cell(a,b) if isinstance(a,str) else tuple(merge_cell(x,y) for x,y in zip(a,b))
                             for a,b in zip(existing['conjugation'],incoming['conjugation'])]
    result['gloss'] = '; '.join(dict.fromkeys(x for value in (existing.get('gloss',''),incoming.get('gloss',''))
                                            for x in value.split('; ') if x and x != '...'))
    return result


EN_PRES_HAVE = ("have", "have", "has", "have", "have", "have")
EN_PAST_HAVE = ("had", "had", "had", "had", "had", "had")
EN_WILL = ("will", "will", "will", "will", "will", "will")

EN_EXCLUDE = ("archaic", "dialectal", "obsolete", "nonstandard", "proscribed")

EN_CONFIG = LanguageConfig(
    code="en",
    name="English",
    english_wiktionary_name="English",
    tenses=(
        # Impersonal
        TenseConfig("en_impers_inf", FormMatcher(("infinitive",), max_forms=1)),
        TenseConfig("en_impers_pres_partic", FormMatcher(("participle", "present"), exclude_tags=EN_EXCLUDE)),
        TenseConfig("en_impers_past_partic", FormMatcher(("participle", "past"), exclude_tags=EN_EXCLUDE)),
        # Indicative present — explicit matchers because Wiktionary plural forms lack person tags
        TenseConfig("en_indic_pres", (
            FormMatcher(("first-person", "singular", "present"), pronoun="I", exclude_tags=EN_EXCLUDE),
            FormMatcher(("second-person", "singular", "present"), pronoun="you", exclude_tags=EN_EXCLUDE),
            FormMatcher(("third-person", "singular", "present"), pronoun="he/she/it", exclude_tags=EN_EXCLUDE),
            FormMatcher(("plural", "present"), pronoun="we", exclude_tags=EN_EXCLUDE),
            FormMatcher(("plural", "present"), pronoun="you", exclude_tags=EN_EXCLUDE),
            FormMatcher(("plural", "present"), pronoun="they", exclude_tags=EN_EXCLUDE),
        )),
        # Indicative past
        TenseConfig("en_indic_past", (
            FormMatcher(("first-person", "singular", "past"), pronoun="I", exclude_tags=EN_EXCLUDE),
            FormMatcher(("second-person", "singular", "past"), pronoun="you", exclude_tags=EN_EXCLUDE),
            FormMatcher(("third-person", "singular", "past"), pronoun="he/she/it", exclude_tags=EN_EXCLUDE),
            FormMatcher(("plural", "past"), pronoun="we", exclude_tags=EN_EXCLUDE),
            FormMatcher(("plural", "past"), pronoun="you", exclude_tags=EN_EXCLUDE),
            FormMatcher(("plural", "past"), pronoun="they", exclude_tags=EN_EXCLUDE),
        )),
        # Compound
        repeated_tense("en", "en_indic_pres_perf", ("participle", "past"), EN_PRES_HAVE, exclude_tags=EN_EXCLUDE),
        repeated_tense("en", "en_indic_past_perf", ("participle", "past"), EN_PAST_HAVE, exclude_tags=EN_EXCLUDE),
        repeated_tense("en", "en_indic_fut", ("infinitive",), EN_WILL, exclude_tags=EN_EXCLUDE),
    ),
    preprocess_forms=preprocess_en_forms,
    form_filter=english_form_is_clean,
    tense_groups=[
        TenseGroup("en_indic", re.compile(r"^en_indic_")),
        TenseGroup("en_impers", re.compile(r"^en_impers_")),
    ],
)
