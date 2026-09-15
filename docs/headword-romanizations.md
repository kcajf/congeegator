# Headword romanization display and search

Entries may now include an optional `romanizations` array, displayed in search
results and under the part-of-speech heading on dictionary pages. Original source
spelling, stress and diacritics remain intact. Standalone inflected-form entries
receive the same treatment as other entries. Parent inflection tables are not
expanded, and no source-form archive is retained.

Source-backed support covers Greek, Russian, Ukrainian, Bulgarian, Macedonian,
Serbo-Croatian, Georgian, Ancient Greek, Sanskrit, Korean, Hindi, Hebrew and
Persian. It requires an explicit standalone source romanization or an attached
reading on the exact headword outside a table. Missing readings stay absent;
ambiguous combined readings are omitted. No pronunciation is invented from an
unpointed spelling, and coverage depends on the pinned source data.

`shared/romanization-profiles.json` defines language-specific keyboard folding.
For example, Russian scholarly šč maps to shch, Bulgarian št maps to sht, and
Macedonian ḱ maps to kj. Ancient Greek retains its own vowels and consonants;
Modern Greek's sound substitutions are not applied to it. Korean eo/eu and tense
consonants remain distinct. The first version accepts source spellings and the
specified normalized keyboard equivalents, not every romanization system.

Each dictionary stores original arrays once in an optional JSON TEXT column.
They are small headword lists, not entire paradigms. A separate WITHOUT ROWID
`romanized_lookup(key, entry_id)` table stores one normalized key per reading,
deduplicated per entry. Exact original readings rank with exact aliases; normalized
matches follow those. Partial matches remain below English-definition matches.
Exact lookup is independent of the prefix limit. Search compares original spelling
using the already-stored array instead of duplicating precise keys in the index.

The worker enables index queries only for `romanization_version=1`. Old databases
remain readable and searchable; they simply lack the new feature. Existing Greek
phonetic search remains available. The extra column and table are also harmless
to older app versions, which ignore them. Dictionaries get the new capability on
the usual manual download/update after the normal generation/deployment workflow.
This PR does not upload data or deploy the app.

Python and TypeScript share profiles and normalization fixtures. Tests cover
source extraction, both packed and ordinary generation, exact/prefix ranking,
standalone form entries, more than 50 prefix candidates, display, absent fields,
and compatibility with older or unknown-version databases.

The [storage comparison](reviews/romanization-size-comparison.md) records the
original headword/all-form experiment. The follow-up production sample measures
this PR's actual normalized index and extraction rules separately.
