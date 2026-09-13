"""Source-aware dictionary metadata for the reviewed 2026 language additions.

All behavior is explicitly scoped: existing language records retain their prior
serialization. Error tags alone never disqualify a lexical form.
"""
import re
import unicodedata

from .utils import strip_diacritics
from .wiktionary import Entry

QUALITY_LANGUAGES = frozenset('grc az eu br et ka he hi is ga ko lt mk ms oc fa sa sh sk cy'.split())
_GENDERLESS = frozenset('az eu et ka ko ms fa'.split())
_GENDERS = {'masculine': 'm', 'feminine': 'f', 'neuter': 'n', 'common-gender': 'c'}
# These are source usage/variety labels, not a guessed classification of words.
_LABELS = frozenset('''formal informal colloquial literary archaic dated rare uncommon vulgar slang figurative figuratively transitive intransitive obsolete nonstandard dialectal regional misspelling historical poetic humorous offensive derogatory proscribed alternative abbreviation initialism clipping pronunciation-spelling reconstructed hypothetical conjectural honorific polite impolite non-polite familiar humble diminutive augmentative relational perfective imperfective reflexive uncountable plural-only singular-only animate inanimate not-comparable comparative superlative mutation lenition nasalization eclipsis aspirate-mutation soft-mutation mixed-mutation no-mutation biblical Biblical Modern-Hebrew Modern-Israeli Tiberian Ashkenazi Sephardi reconstructed-Biblical Classical-Persian Dari Iranian Iran Tajik Tehrani Kabuli Hazaragi Vedic Classical-Sanskrit Epic Sanskrit Buddhist Epic-Sanskrit Attic Ionic Doric Aeolic Aeolian Koine Byzantine Homeric Epic-Greek New-Attic Old-Attic poetic dialectal Arcadian Cypriot Boeotian Laconian Thessalian Lesbian Cretan Pamphylian Macedonian Northwest-Greek North South Northern Southern Western Eastern Classical North-Azerbaijani South-Azerbaijani Tabriz Zaqatala Bilasuvar Gadabay Ordubad Zangilan Baku Salyan Nakhchivan Qazakh Kurdamir Barda Kalbajar Agdam Jalilabad Khojavend Iranian Azerbaijani Bosnia Croatia Serbia Montenegro Kajkavian Torlakian Ijekavian Ekavian Chakavian Ikavian Dalmatia Burgenland Bosnian Croatian Serbian Indonesia Malaysia Singapore Brunei Medan Penang Riau Pahang Sabah Jakarta Johore Sarawak-Malay Javanese Old-Lithuanian Aukštaitian North-Korea South-Korea Jeju Seoul Gyeongsang Hamgyong Pyongan Chungcheong Jeolla Munster Ulster Connacht North-Wales South-Wales Gascony Languedoc Limousin Provençal Mistralian Vivaro-Alpine Niçard Auvergnat Biscayan Navarro-Lapurdian Navarrese Lapurdian Souletin Gipuzkoan Upper-Navarrese Lower-Navarrese Standard Arabic Cyrillic Latin Roman Jawi Hanja Hangul Devanagari Urdu Bengali Brahmi Khmer Sinhala Tibetan Telugu Tamil Kannada Malayalam Gujarati Gurmukhi Newa Grantha Sharada Balinese Javanese-script Thai Myanmar Mongolian Yañalif'''.split())
_HEADERS = frozenset('singular plural nominative genitive dative accusative locative instrumental vocative'.split()) | {'plural 1', 'plural 2'}
_SK_PATTERNS = frozenset('žena ulica dlaň kosť chlap hrdina dub stroj mesto srdce vysvedčenie dievča gazdiná'.split())
_LINKAGE = re.compile(r'^(?:Near-synonyms?|Synonyms?|Antonyms?|Hypernyms?|Hyponyms?|Coordinate terms?):')
_BROKEN_ENTITY = re.compile(r'(?:[A-Za-z]#\d+;|&#?\d+;.*#\d+;)')


def labels(tags):
    # Wiktextract uses capitalized tags for named regions, periods and scripts.
    # Preserve those names, including ones outside the initial review sample.
    return list(dict.fromkeys(tag.replace('-', ' ') for tag in sorted(tags)
                              if tag in _LABELS or (tag[:1].isupper() and re.fullmatch(r'[\w-]+', tag))))


def raw_labels(tags, clean_text):
    """Keep short source qualifiers that Wiktextract could not normalize."""
    result = []
    for tag in tags:
        text = clean_text(tag)
        if not text or len(text) > 160 or any(x in text for x in ('[', ']', '<', '>', 'error-')):
            continue
        # Some head expansions truncate a closing quotation mark. Removing
        # unmatched quote punctuation preserves the attested meaning words.
        if text.count('"') % 2:
            text = text.replace('"', '')
        if text.count('(') != text.count(')'):
            continue
        result.append(text)
    return list(dict.fromkeys(result))


def _script(text, script):
    letters = [c for c in text if unicodedata.category(c).startswith('L')]
    return bool(letters) and all(script in unicodedata.name(c, '') for c in letters)


def trusted_persian_head(entry: Entry) -> bool:
    """Native lexical heads can coexist with a nonstandard-script page section."""
    return (entry.lang_code == 'fa' and _script(entry.word, 'ARABIC')
            and any(h.name in {'fa-verb', 'fa-noun', 'fa-adj', 'fa-adv', 'fa-proper noun',
                               'fa-pron', 'fa-num', 'fa-prep', 'fa-conj', 'fa-intj', 'fa-phrase'}
                    for h in entry.head_templates)
            and any(s.glosses and not set(s.tags) & {'form-of', 'alt-of'} for s in entry.senses))


def _gender(entry):
    if entry.lang_code in _GENDERLESS or entry.pos not in {'noun', 'name'}:
        return None
    # Canonical means the head itself; feminine related forms and possessors
    # must not add a gender to the noun being defined.
    tags = {t for f in entry.forms if 'canonical' in f.tags for t in f.tags}
    genders = {_GENDERS[t] for t in tags if t in _GENDERS}
    if not genders:
        for head in entry.head_templates:
            key = {'grc-noun': '3', 'sa-noun': '1', 'sh-noun': '2', 'mk-noun': '1'}.get(head.name)
            if key:
                value = head.args.get(key, '')
                if re.fullmatch(r'[mfn](?:[,-][mfn])*', value):
                    genders.update(re.split('[,-]', value))
    return '-'.join(g for g in ('m', 'f', 'n', 'c') if g in genders) or None


def _form_variants(entry, form, text):
    """Return attested cleaned spelling(s) and additional source qualifiers."""
    code = entry.lang_code
    extra = []
    if text == 'Term?':
        return [], extra
    if form.tags & {'counter', 'classifier', 'romanization', 'declension-pattern-of'}:
        return [], extra
    if code in {'grc', 'fa', 'hi', 'sa'} and _script(text, 'LATIN'):
        return [], extra
    if code == 'grc' and form.source and text in {'εἶτον', 'εἴτην', 'εἶμεν', 'εἶτε', 'εἶεν', 'εἴτᾱν', 'εἶμες'} and entry.word != 'εἰμί':
        # Pinned compound tables link this auxiliary label to the main verb's
        # participle, e.g. εἶτον -> ἠγμένω under ἄγω. Never a form of ἄγω.
        if any(isinstance(link, (list, tuple)) and len(link) >= 2 and strip_diacritics(str(link[1]).split('#')[0]) != strip_diacritics(text)
               for link in form.links):
            return [], extra
    if code in {'az', 'mk', 'he'} and ('+' in text or re.search(r'\b(?:present|imperfect|future|conditional|participle) of\b', text)):
        return [], extra
    if code == 'sk' and form.source == 'declension' and not form.tags and text in _HEADERS | _SK_PATTERNS:
        return [], extra
    if code == 'br' and text == 'never occurs':
        return [], extra
    if code == 'is' and text in {'declension', 'conjugation'}:
        return [], extra
    if code == 'ga' and text == 'obsolete':
        return [], extra
    if code == 'ka' and (text == 'Term?' or text.startswith(('with ', 'Main:'))):
        return [], extra
    if code == 'ko' and (text == 'no hanja' or text.startswith(('Formal ', 'Informal ', 'past:'))):
        return [], extra
    if code == 'he' and text.startswith('form '):
        candidate = text[5:]
        return ([candidate] if _script(candidate, 'HEBREW') else []), extra
    if code == 'hi' and re.search(r'\s[\u093e-\u094d]', text):
        candidate = re.sub(r'\s+(?=[\u093e-\u094d])', '', text)
        # Repair only when the exact spelling is independently present in the
        # same source head expansion; otherwise omit the malformed fragment.
        return ([candidate] if any(candidate in h.expansion for h in entry.head_templates) else []), extra
    if code == 'sa' and re.search(r'[0-9¹²³⁴⁵⁶⁷⁸⁹⁰]+$', text):
        # Footnote semantics are not preserved consistently in this snapshot.
        return [], extra
    if code == 'oc' and text.startswith('use ') and ('+' in text or 'participle' in text):
        return [], extra
    if code == 'oc' and ('[' in text or ']' in text or re.search('[¹²³⁴⁵]', text)):
        return [], extra
    if code == 'fa':
        if text == 'ZWNJ':
            return [], extra
        if '(' in text:
            # Source supplies native alternatives followed by their Latin
            # transcription. Do not infer spellings from the transcription.
            match = re.fullmatch(r'([^()]*)\s+\([^()]*[A-Za-z][^()]*\)', text)
            if not match:
                return [], extra
            text = match[1].strip()
        if re.search(r'[A-Za-z\[\]△^]', text):
            return [], extra
        return [x.strip() for x in text.split('،') if x.strip()], extra
    # Two reviewed Celtic metadata phrases enclose genuine forms. Keep the
    # qualifier as metadata instead of displaying it inside the spelling.
    if code == 'ga' and text.startswith('(obsolete except in sept names) '):
        return [text.removeprefix('(obsolete except in sept names) ')], ['obsolete except in sept names']
    if code == 'is' and text.endswith(' (rare; see appendix)'):
        return [text.removesuffix(' (rare; see appendix)')], ['rare']
    return [text], extra


def enhance_record(entry, record, clean_text):
    """Add reviewed context and remove known source table debris in-place."""
    if entry.lang_code not in QUALITY_LANGUAGES:
        return record
    if entry.lang_code in _GENDERLESS:
        record.pop('gender', None)
    elif gender := _gender(entry):
        record['gender'] = gender
    # Keep only senses actually accepted by the base importer, in source order.
    valid_senses = [s for s in entry.senses if s.glosses and all(clean_text(g) for g in s.glosses)]
    for source, sense in zip(valid_senses, record['senses']):
        combined = list(dict.fromkeys(sense.get('tags', []) + labels(source.tags) + raw_labels(source.raw_tags, clean_text)))
        if combined:
            sense['tags'] = combined
        if 'examples' in sense:
            examples = [x for x in sense['examples'] if not _LINKAGE.match(x) and not _BROKEN_ENTITY.search(x)]
            if examples:
                sense['examples'] = examples
            else:
                sense.pop('examples')
    accepted = set(record.get('forms', []))
    output, details = {}, {}
    table_labels = []
    for form in entry.forms:
        if 'table-tags' in form.tags:
            table_labels = labels((form.form or '').split())
            continue
        text = clean_text(form.form or '')
        if text not in accepted:
            continue
        variants, extra = _form_variants(entry, form, text)
        source_labels = labels(form.tags) + raw_labels(form.raw_tags, clean_text) + (table_labels if form.source else []) + extra
        for variant in variants:
            if not variant or variant == entry.word:
                continue
            output[variant] = None
            if source_labels:
                details.setdefault(variant, [])
                details[variant] = list(dict.fromkeys(details[variant] + source_labels))
    if output:
        record['forms'] = list(output)
    else:
        record.pop('forms', None)
    if details:
        record['formDetails'] = [{'form': f, 'tags': tags} for f, tags in details.items()]
    pronunciations = []
    for sound in entry.sounds:
        if not isinstance(sound, dict) or not (ipa := clean_text(sound.get('ipa', ''))):
            continue
        note = clean_text(sound.get('note', ''))
        sound_labels = labels(sound.get('tags', [])) + raw_labels(sound.get('raw_tags', []), clean_text)
        label = ', '.join(dict.fromkeys(([note] if note else []) + sound_labels))
        if entry.lang_code == 'grc' and not label:
            continue
        # The pinned sounds lose the separate “Epic variant” heading on
        # https://en.wiktionary.org/wiki/ὕδωρ#Pronunciation. That page explicitly
        # restricts long upsilon to metrical lengthening in Epic poetry; retain
        # the source period as well as this verified conditional distinction.
        if entry.lang_code == 'grc' and entry.word == 'ὕδωρ' and ipa == '/hy̌ː.dɔːr/':
            label += '; Epic poetic variant; long υ'
        item = {'ipa': ipa}
        if label:
            item['label'] = label
        if item not in pronunciations:
            pronunciations.append(item)
    if pronunciations:
        record['pronunciation'] = pronunciations[0]['ipa']
        if len(pronunciations) > 1 or any('label' in p for p in pronunciations):
            record['pronunciations'] = pronunciations
    else:
        record.pop('pronunciation', None)
    return record
