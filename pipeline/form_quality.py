"""Reviewed form spellings and complete readings, shared by every dictionary.

Normalization happens before deduplication and reverse indexing. Error tags alone
never reject a spelling. Optional diagnostics explain omissions and repairs.
"""
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import groupby
import re
import unicodedata

from .dictionary_quality import _FORM_GRAMMAR, _LABELS, _form_variants, labels, raw_labels

# Source grammar vocabulary, including distinctions that cannot be flattened to
# plain person/number (objects, possessors, semantic addressees, noun classes).
GRAMMAR = tuple(dict.fromkeys(_FORM_GRAMMAR + '''
direct relative postpositional be-prefix broken-form perfective imperfective preterite historic anterior non-past past-future future-i future-ii perfect-i perfect-ii
subjunctive-i subjunctive-ii conditional-i conditional-ii imperfect-se
progressive continuative habitual frequentative semelfactive inferential evidential
reported quotative presumptive prospective non-prospective necessitative obligative
counterfactual injunctive jussive hortative volitive assertive interrogative
impersonal autonomous fourth-person second-person-semantically
strong weak mixed construct absolute oblique prepositional instructive
superessive sublative delative essive-formal essive-modal lative separative
causal-final causal destinative benefactive directive excessive privative
virile nonvirile proximal distal medial unspecified paucal collective singulative
attributive predicative adverbial adverbial-manner adjectival agent agentive
infinitive-i infinitive-i-long infinitive-ii infinitive-iii infinitive-iv infinitive-v
infinitive-ma infinitive-da infinitive-zu l-participle half-participle transgressive
middle-voice personal analytic short-form long-form apocopic contracted
main-clause subordinate-clause inversion without-article includes-article
with-article with-definite-article usually-without-article with-tú with-vos with-voseo vos-form
object-first-person object-second-person object-third-person object-singular object-plural
object-definite object-indefinite direct-object indirect-object objective subjective
singular-possessive plural-possessive possessed-single possessed-many possessed-form
addressee-singular reciprocal causative applicative stative resultative deliberate
involuntary affirmative negative non-subject independent augmented sigmatic deponent
clitic enclitic proclitic reduplication equative comparative superlative comparable
count-form determinate indeterminate numeral cardinal ordinal multiplicative distributive
conjunctive connective contrastive modal preparative sequential temporal situative motive-form
essive-formal definitive separable substantival substantive determinative-of ezafe
like-position on-position near-position in-position for-position from-position
since-position together-with-position towards-position up-to-position in-relation-to-position
mutation-soft mutation-hard mutation-mixed mutation-aspirate soft unmutated mutated
prothesis-h triggers-eclipsis triggers-h-prothesis triggers-lenition triggers-mutation-nasal
triggers-no-mutation triggers-mutation before-vowel after-vowel after-consonant
before-lenited-fh before-noun before-lenited-fh after-consonant-except-l after-l-consonant
with-dative with-genitive with-objective with-subjunctive without-noun without-numeral
stress-pattern-1 stress-pattern-2 stress-pattern-3 stress-pattern-3a stress-pattern-3b stress-pattern-4
stressed unstressed front-vowel pausal in-compounds stem root in-plural plural-normally
'''.split()))
GRAMMAR_SET = frozenset(GRAMMAR)
USAGE = _LABELS | frozenset('''deferential gender-neutral countable traditional common sometimes usually often also especially
mainly broadly mildly specifically recently contemporary modern standard vernacular
idiomatic emphatic unemphatic hypercorrect euphemistic pejorative meliorative endearing
childish bureaucratese jargon ironic neologism majestic unknown possibly epic extinct
reconstruction irregular suppletive defective indeclinable invariable no-comparative
no-infinitive no-perfect no-plural imperative-only in-certain-phrases before-noun
by-personal-gender animal-not-person person capitalized uppercase lowercase polytonic
phonetic syncope ellipsis parenthetic contraction stress-pattern-3b stress-pattern-3a
pronunciation-spelling calque initialism abbreviation acronym unabbreviation
'''.split())
RELATED = frozenset('''derived adjective adjectival adjective-from-noun abstract-noun
adverb noun noun-from-verb verb demonym surname patronymic toponymic proper-noun name
relational diminutive augmentative intensifier determiner pronoun article interjection
phrase pronominal numeral character symbol letter hangeul hanja eumhun kanji
'''.split())
VARIANTS = frozenset({'alternative', 'variant', 'alt-of', 'canonical', 'base-form', 'inflected'})
INTERNAL = frozenset('''canonical table-tags inflection-template romanization transliteration
class classifier auxiliary counter declension-pattern-of multiword-construction
combined-form conjugative-of plural-of reflexive-of correlative-of used-in-the-form
'''.split())
DISPLAY = {
    'infinitive-aorist': 'aorist infinitive', 'middle-voice': 'middle voice',
    'historic': 'past historic', 'second-person-semantically': 'second-person address',
    'singular-possessive': 'singular possessor', 'plural-possessive': 'plural possessor',
    'possessed-single': 'one possessed item', 'possessed-many': 'multiple possessed items',
    'possessed-form': 'possessive form', 'includes-article': 'with article',
    'infinitive-i': 'first infinitive', 'infinitive-i-long': 'long first infinitive',
    'infinitive-ii': 'second infinitive', 'infinitive-iii': 'third infinitive',
    'infinitive-iv': 'fourth infinitive', 'infinitive-v': 'fifth infinitive',
    'with-tú': 'tú form', 'with-vos': 'vos form', 'with-voseo': 'voseo',
    'prepositional': 'prepositional', 'l-participle': 'l-participle',
}

@dataclass
class FormDiagnostics:
    counts: Counter = field(default_factory=Counter)
    samples: dict = field(default_factory=dict)

    def add(self, reason, entry, text):
        key = f'{entry.lang_code}:{reason}'
        self.counts[key] += 1
        self.samples.setdefault(key, {'word': entry.word, 'form': text})


def note(audit, reason, entry, text):
    if audit is not None:
        audit.add(reason, entry, text)


def rejected_reason(entry, form, text):
    code = entry.lang_code
    table = form.source in {'conjugation', 'declension', 'inflection'}
    if text in {'[please provide]', '[Term?]', 'Term?', '?', '—', '–', '- —'}:
        return 'placeholder'
    if code == 'fi' and (text == 'Rare. Only used with substantive adjectives.' or
                         text.startswith('Regularly derivable colloquial forms')):
        return 'table-instruction'
    if code == 'cs' and text.startswith(('When the verb ', 'The verb ')):
        return 'table-instruction'
    if code == 'hu' and text.startswith('(and the concomitant changes in conditional and subjunctive'):
        return 'table-instruction'
    if code == 'fr' and table:
        if re.match(r'^(?:present|past|imperfect|future|pluperfect).*\bof\b', text):
            return 'construction-instruction'
        if 'multiword-construction' in form.tags and text in {'ayant', 'étant', 'avoir', 'être'}:
            return 'detached-auxiliary'
    if code in {'it', 'de', 'ru'} and table and text in {'infinitive', 'imperative', 'declension'}:
        return 'table-header'
    if code == 'it' and text.startswith(('in the literal meaning ', 'the sense ', 'in most figurative')):
        return 'auxiliary-note'
    if code == 'la' and re.match(r'^(?:First|Second|Third|Fourth|Fifth)-declension noun\b', text):
        return 'declension-note'
    if code in {'ro', 'ru'} and text in {'not used', 'form is not used'}:
        return 'unavailable-form'
    if code in {'ko', 'grc'} and re.match(r'^(?:conjugation of |Formed using )', text):
        return 'construction-instruction'
    if code in {'id', 'ms'} and (text in {'or', '(Standard) Malay', 'standard Malay'} or
            re.fullmatch(r'(?:nonstandard or standard|standard|nonstandard) (?:Malay|Indonesian)', text)):
        return 'language-note'
    if 'literally' in form.tags and code == 'sv' and re.search(r'[A-Za-z]', text):
        return 'translation'
    if code == 'ru' and table and 'error-unrecognized-form' in form.tags and re.match(
            r'^(?:Comma|Semicolon|Colon|Full stop|Question mark|Exclamation|Hyphen|Dash|Quotation|Letter|Digit|Number|Capital)\b', text):
        return 'foreign-table-cell'
    if code == 'de' and text.startswith('pronunciation:'):
        return 'pronunciation-note'
    if code == 'uk' and table and re.search('[A-Za-z]', text) and not re.search('[А-Яа-яІіЇїЄєҐґ]', text):
        return 'transliteration-in-table'
    return None


PERSON = frozenset({'first-person', 'second-person', 'third-person', 'singular', 'plural'})
COLUMNS = tuple(frozenset({person, number}) for number in ('singular', 'plural')
                for person in ('first-person', 'second-person', 'third-person'))
SHIFTED = (COLUMNS[2], COLUMNS[3], COLUMNS[4], COLUMNS[5], frozenset(), frozenset())
MISSING_FIRST = (frozenset(), *COLUMNS[1:])
FINITE = frozenset('aorist continuative progressive inferential future past conditional optative necessitative imperative'.split())


def source_forms(entry, audit=None):
    """Repair only the verified tr-conj column signatures, without suffix guessing.

    Wiktionary tr-conj has six finite columns: ben/sen/o/biz/siz/onlar.
    The pinned extractor shifts simple rows by two cells and loses the first
    person on compound rows. Incomplete/unknown rows retain tense and spelling,
    but withhold unverified person/number rather than publish a false reading.
    """
    if entry.lang_code != 'tr' or not any(t.name == 'tr-conj' for t in entry.inflection_templates):
        yield from entry.forms
        return
    import msgspec
    def key(f):
        return (f.source, frozenset(f.tags - PERSON))
    for (source, grammar), group in groupby(entry.forms, key):
        forms = list(group)
        if source != 'conjugation' or not grammar & FINITE:
            yield from forms
            continue
        # Adjacent rows can share all non-person tags. Accept the entire group
        # only when every six-cell row has a reviewed column signature.
        rows = [forms[i:i + 6] for i in range(0, len(forms), 6)]
        verified = all(tuple(frozenset(f.tags & PERSON) for f in row)
                       in {COLUMNS, SHIFTED, MISSING_FIRST} for row in rows)
        for row in rows:
            for index, form in enumerate(row):
                column = COLUMNS[index] if verified else frozenset()
                if form.tags & PERSON != column:
                    note(audit, 'repaired-person-column' if verified else 'withheld-person-column', entry, form.form)
                yield msgspec.structs.replace(form, tags=(form.tags - PERSON) | column)


def _whole_wrapper(text):
    if len(text) < 3 or (text[0], text[-1]) not in {('[', ']'), ('{', '}'), ('(', ')')}:
        return False
    stack = []
    for i, char in enumerate(text):
        if char in '[{(':
            stack.append(char)
        elif char in ']})':
            if not stack or (stack.pop(), char) not in {('[', ']'), ('{', '}'), ('(', ')')}:
                return False
            if not stack and i != len(text) - 1:
                return False
    return not stack


def greek_variants(text, preserve_suffix=False):
    """Separate table alternatives without losing bracket scope or particles."""
    # Keep meaningful optional letters (e.g. Ancient Greek movable nu) intact;
    # only whole-word wrappers are usage labels. Do not expand suffix shorthand.
    prefix = 'θα ' if text.startswith('θα ') else ''
    if prefix:
        text = text[len(prefix):]
    stack, start = [], 0
    parts = []
    for match in re.finditer(r'[\[\]{}()]|\s+[-–—/]\s+|,\s*', text):
        token = match.group()
        if token in '[{(':
            stack.append(token)
        elif token in ']})':
            if stack: stack.pop()
        elif not stack:
            parts.append(text[start:match.start()].strip())
            start = match.end()
    parts.append(text[start:].strip())
    for part in parts:
        if not part: continue
        qualifiers = []
        if _whole_wrapper(part):
            opener = part[0]
            part = part[1:-1].strip()
            qualifiers = {'[': ['rare'], '{': ['learned', 'archaic'], '(': ['optional or informal']}[opener]
            for inner, extra in greek_variants(part, preserve_suffix):
                if prefix and not inner.startswith(prefix): inner = prefix + inner
                yield inner, qualifiers + extra
            continue
        part = part.strip()
        if part.startswith('- '): part = part[2:].strip()
        # Footnotes need their missing qualifiers reviewed, not silently erased.
        if re.search(r'[¹²³⁴⁵⁶⁷⁸⁹⁰^]|[A-Za-z]|[\[\]{}]', part): continue
        if not part or part in {'—', '–', '-'} or part.startswith(('‑', '‐')): continue
        if part.startswith('-') and not preserve_suffix: continue
        if '(' in part or ')' in part:
            # A Greek optional ending is lexical notation, not an English note.
            if not re.fullmatch(r'[\w\u0300-\u036f]+\([\w\u0300-\u036f]+\)', part): continue
        if not any('GREEK' in unicodedata.name(c, '') for c in part): continue
        if prefix and not part.startswith(prefix): part = prefix + part
        yield part, qualifiers


def normalize(entry, form, text, clean_text, audit=None):
    reason = rejected_reason(entry, form, text)
    if reason:
        note(audit, reason, entry, text)
        return
    code = entry.lang_code
    variants, extra = _form_variants(entry, form, text)
    if not variants:
        note(audit, 'reviewed-source-cleanup', entry, text)
    for value in variants:
        qualifiers = list(extra)
        if code == 'el':
            found = list(greek_variants(value, entry.pos in {'affix', 'suffix', 'prefix', 'combining_form'}))
            if not found: note(audit, 'unresolved-greek-cell', entry, value)
            for spelling, q in found:
                if spelling != text: note(audit, 'split-or-unwrapped', entry, text)
                yield spelling, qualifiers + q
            continue
        # Hungarian alternatives use English 'or' between whole spellings. A
        # dangling 'or' is not part of the spelling; the next cell is independent.
        if code == 'hu':
            if '{' in value or '}' in value:
                note(audit, 'broken-brace', entry, value)
                continue
            value = re.sub(r'\s+or$', '', value)
            value = re.sub(r'^or\s+', '', value)
            match = re.fullmatch(r'(.+?)\s+\(or ([^()]+)\)', value)
            if match: value = match[1] + ' or ' + match[2]
            for part in value.split(' or '):
                if part: yield part.strip(), qualifiers
            continue
        if code == 'da' and re.match(r'^\((?:have|være)\s*/', value):
            match = re.fullmatch(r'\(([^()]+)\)\s+(.+)', value)
            if match:
                qualifiers.append('auxiliary: ' + match[1].replace('/', ' / ').replace('  ', ' '))
                value = match[2]
        if code == 'br':
            match = re.fullmatch(r'(.+?)\s+\(auxiliary verb: ([^()]+)\)', value)
            if match: value, qualifiers = match[1], qualifiers + ['auxiliary: ' + match[2]]
        if code == 'is' and re.match(r'^(?:conjugation|declension): ', value):
            for part in re.split(r'\s+[–—-]\s+', value.split(': ', 1)[1]):
                yield part, qualifiers
            continue
        # Preserve a native spelling while moving embedded notes off the link.
        if code in {'it', 'az', 'ka', 'mk', 'he', 'sa', 'id'}:
            match = re.fullmatch(r'(.+?)\s+\(([^()]*)\)', value)
            if match and (re.search(r'[“”"A-Za-z]', match[2])):
                value = match[1]
                qualifiers.append(match[2].strip())
            if code == 'it':
                match = re.fullmatch(r'\((rare)\)\s+(.+)', value)
                if match: qualifiers.append(match[1]); value = match[2]
                value = re.sub(r'\s+[mf]$', '', value)
            if code == 'ka' and re.search('[A-Za-z]', value) and re.search('[ა-ჰ]', value):
                # Truncated transliteration cannot be reliably detached.
                note(audit, 'mixed-script-fragment', entry, value)
                continue
        if code in {'de', 'ga'} and value.endswith(('>', '<')):
            value = value[:-1]
        # Split only attested lexical alternative fields, never prose phrases.
        if 'alternative' in form.tags and entry.pos not in {'phrase', 'proverb'}:
            separator = r',\s+' if code in {'fr', 'it', 'la', 'eu', 'grc', 'vi'} else None
            if separator and not any(c in value for c in '()[]“”"'):
                parts = re.split(separator, value)
                if all(part and not any(c.isspace() for c in part) for part in parts):
                    for part in parts:
                        yield part, qualifiers
                    continue
        if value != text: note(audit, 'normalized-spelling', entry, text)
        yield value, qualifiers


@lru_cache(maxsize=16384)
def reading_tags(tags):
    tags = frozenset(tags)
    grammar = [DISPLAY.get(t, t.replace('-', ' ')) for t in GRAMMAR if t in tags]
    # These are synonyms or redundant components of a more specific label.
    if 'historic' in tags and 'past' in tags: grammar.remove('past')
    if 'middle-voice' in tags and 'middle' in tags: grammar.remove('middle')
    for basic, specific in [('future', 'future-i'), ('future', 'future-ii'),
                            ('subjunctive', 'subjunctive-i'), ('subjunctive', 'subjunctive-ii'),
                            ('conditional', 'conditional-i'), ('conditional', 'conditional-ii')]:
        if basic in tags and specific in tags and basic in grammar: grammar.remove(basic)
    obj = [t.removeprefix('object-').replace('-', ' ') for t in GRAMMAR if t in tags and t.startswith('object-')]
    if obj:
        grammar = [g for g in grammar if not g.startswith('object ')]
        grammar.append('object: ' + ' '.join(obj))
    if tags & {'singular-possessive', 'plural-possessive', 'possessed-single', 'possessed-many'}:
        people = [t.replace('-', ' ') for t in ('first-person', 'second-person', 'third-person') if t in tags]
        numbers = [n for n in ('singular', 'plural') if n + '-possessive' in tags]
        if not numbers and tags & {'possessed-single', 'possessed-many'}:
            numbers = [n for n in ('singular', 'plural') if n in tags]
        removed = people + ['singular possessor', 'plural possessor']
        if tags & {'possessed-single', 'possessed-many'}:
            removed += numbers
        grammar = [g for g in grammar if g not in removed]
        grammar.append('possessor: ' + ' '.join(people + numbers))
    qualifiers = [t.replace('-', ' ') for t in sorted(tags) if
                  (t in USAGE or (t[:1].isupper() and re.fullmatch(r'[\w-]+', t))) and t not in GRAMMAR_SET]
    relation = tags & RELATED
    # Participles/adjectival readings remain inflections when grammar exists.
    kind = ('related' if tags & {'derived', 'relational', 'diminutive', 'augmentative', 'abstract-noun', 'adjective-from-noun', 'noun-from-verb'} else
            'inflection' if grammar else 'related' if relation else 'variant' if tags & VARIANTS else 'other')
    if relation and kind == 'related':
        qualifiers = list(dict.fromkeys([t.replace('-', ' ') for t in sorted(relation)] + qualifiers))
    unknown = tags - GRAMMAR_SET - USAGE - RELATED - VARIANTS - INTERNAL
    return tuple(grammar), tuple(qualifiers), kind, tuple(sorted(t for t in unknown if not t.startswith('error-') and not t[:1].isupper()))


def build_details(items, entry, clean_text, audit=None):
    by_form = {}
    for text, form, extra in items:
        grammar, qualifiers, kind, unknown = reading_tags(tuple(sorted(form.tags)))
        for tag in unknown: note(audit, 'unknown-tag:' + tag, entry, text)
        qualifiers = tuple(dict.fromkeys((*qualifiers, *raw_labels(form.raw_tags, clean_text), *extra)))
        bucket = by_form.setdefault(text, [])
        value = (grammar, qualifiers, kind)
        if value not in bucket: bucket.append(value)
    output = []
    for text, readings in by_form.items():
        # Suppress a less-specific duplicate only within the same meaning/kind
        # and with exactly the same qualifiers. Never transfer a qualifier.
        unique = [r for r in readings if not any(r != other and r[1:] == other[1:] and
                  set(r[0]) < set(other[0]) for other in readings)]
        kinds = {r[2] for r in unique}
        kind = next(k for k in ('inflection', 'related', 'variant', 'other') if k in kinds)
        formatted = []
        for grammar, qualifiers, _ in unique:
            reading = {}
            if grammar: reading['grammar'] = list(grammar)
            if qualifiers: reading['qualifiers'] = list(qualifiers)
            if reading and reading not in formatted: formatted.append(reading)
        detail = {'form': text, 'kind': kind}
        if formatted: detail['readings'] = formatted
        output.append(detail)
    return output
