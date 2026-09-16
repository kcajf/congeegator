# Headword-only versus all-form romanization storage

Measurements completed 15 September 2026 on `experiment/romanization-sizes`,
based on main `9695a4e`. These historical experiment results are retained on
`feature/headword-romanizations`, which now implements the headword-only feature;
see [the implementation notes](../headword-romanizations.md). No dictionaries
have been uploaded or deployed by this work.

## Recommendation

Start with headword-only display and search. Across five complete dictionaries,
that costs approximately 2–3% installed storage and 3–5% compressed download size
including a basic index. Standalone inflected-form entries receive their own
headword romanizations, so this already supports many inflected spellings.

Storing table-form readings for display is also reasonably compact. Indexing
all of them is the bigger cost: the complete Ukrainian, Hindi, Korean and Georgian
dictionaries grow 17–27% installed and 28–41% in download size. Hebrew adds almost
nothing beyond headwords because very few table forms have explicit romanizations.
These measurements supersede the earlier experiment that duplicated entire source
cells in uncompressed `details.sourceFormReadings`.

## Complete dictionaries: display plus a basic search index

Every accepted record in each pinned source was used. MB means decimal megabytes.
Columns compare actual rebuilt database sizes, not extrapolations from samples.

| Language | Entries | Current installed MB | Headwords installed MB | All forms installed MB | Current download MB | Headwords download MB | All forms download MB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Ukrainian | 59,740 | 80.87 | 83.02 | 94.26 | 22.99 | 23.87 | 29.33 |
| Hindi | 39,134 | 55.43 | 56.80 | 65.06 | 11.91 | 12.39 | 15.88 |
| Korean | 52,500 | 51.90 | 53.49 | 63.13 | 12.69 | 13.36 | 17.03 |
| Georgian | 27,020 | 59.60 | 60.64 | 75.87 | 15.32 | 15.72 | 21.62 |
| Hebrew | 17,981 | 24.95 | 25.49 | 25.51 | 7.81 | 8.04 | 8.05 |

| Language | Headwords installed growth | All forms installed growth | Headwords download growth | All forms download growth |
| --- | ---: | ---: | ---: | ---: |
| Ukrainian | +2.7% | +16.6% | +3.8% | +27.6% |
| Hindi | +2.5% | +17.4% | +4.0% | +33.4% |
| Korean | +3.1% | +21.6% | +5.2% | +34.2% |
| Georgian | +1.7% | +27.3% | +2.6% | +41.1% |
| Hebrew | +2.2% | +2.2% | +2.9% | +3.0% |

## Strings for display, excluding the new index

Each cell is the additional installed/download MB versus the same baseline.
These variants isolate the cost of retaining strings from the cost of looking
them up through an additional index.

| Language | Headword strings only: installed / download MB | Headword and table-form strings: installed / download MB |
| --- | ---: | ---: |
| Ukrainian | 0.95 / 0.35 | 3.42 / 3.37 |
| Hindi | 0.64 / 0.14 | 2.56 / 1.96 |
| Korean | 0.66 / 0.24 | 2.39 / 1.84 |
| Georgian | 0.48 / 0.15 | 2.92 / 2.75 |
| Hebrew | 0.21 / 0.07 | 0.23 / 0.08 |

## Existing form entries already cover many inflections

An entry with a source `form_of` relationship counts as a standalone form entry
here; this is not a claim that every inflection has its own entry. Each such
entry is eligible for headword romanizations in the headword-only variant.

| Language | Standalone form entries | Those with headword readings | Additional table forms with readings in all-forms variant |
| --- | ---: | ---: | ---: |
| Ukrainian | 29,200 | 29,134 | 412,132 |
| Hindi | 13,118 | 13,113 | 265,080 |
| Korean | 12,978 | 12,964 | 346,143 |
| Georgian | 4,189 | 4,189 | 550,320 |
| Hebrew | 2,192 | 2,061 | 354 |

Table forms are counted per parent entry, not as distinct spellings across the
whole dictionary. Some already have standalone entries. Therefore the number of
extra table readings is not the number of newly discoverable spellings.

## Six-language random-sample cross-check

A seeded reservoir sample of up to 5,000 eligible source records per language
was selected across the entire source file, then processed through the usual
entry validation. These are sample results only. Russian was measured only in
this sample; the other five languages were also measured completely above.

| Language | Accepted sample entries | Headwords installed/download growth | All forms installed/download growth |
| --- | ---: | ---: | ---: |
| Russian | 4,996 | +4.0% / +3.6% | +10.9% / +17.0% |
| Ukrainian | 4,994 | +2.5% / +1.3% | +15.5% / +21.5% |
| Hindi | 4,997 | +2.8% / +1.2% | +16.8% / +26.4% |
| Korean | 4,949 | +4.2% / +2.9% | +19.9% / +26.5% |
| Georgian | 5,000 | +2.0% / +1.4% | +26.6% / +36.7% |
| Hebrew | 4,996 | +2.5% / +1.3% | +2.5% / +1.4% |

## Exactly what is stored

Headword-only adds an optional JSON array in an entry-level SQLite column:

```json
{"word": "собака", "romanizations": ["sobáka"]}
```

All-forms includes that same field and adds only an optional array to each
existing form-detail object that has an unambiguous source reading:

```json
{
  "form": "соба́ки",
  "romanizations": ["sobáki"],
  "readings": [{"grammar": ["genitive", "singular"]}]
}
```

The experiment aggregates display readings at the form spelling; it does not
attempt to assign each romanization to a particular grammatical interpretation.
Existing grammatical details remain unchanged. It does not duplicate source
records, links, tags or native spellings in another collection. Missing arrays
are omitted. Headword fields are NULL when absent.

The indexed variants additionally contain a `WITHOUT ROWID` lookup table with
`(key, entry_id, kind)` as the primary key. `kind` distinguishes headwords from
forms; duplicate keys for the same entry and kind are removed. The keys are
lowercase NFC versions of the original readings. This is a basic literal index,
not a completed language-specific phonetic search implementation. Extra accepted
ASCII spellings or pronunciation variants would require additional keys and
could increase size. No redundant reading string is stored in that table.

## Method and limits

- Use the current pinned snapshots, current dictionary extraction, production
  frequency ordering, and unchanged lexical/English/Greek-phonetic indices.
  Snapshot IDs and counts are in [the raw measurements](romanization-sizes.json).
- Start every variant from the same rebuilt baseline per language. Add optional
  romanizations and, for all forms, update existing form details. Compact each
  modified database with `VACUUM INTO`. SQLite's page size remains 16 KiB.
- Use the existing LZJ1 per-field Zstandard codec (level 6, minimum 512 bytes,
  only when beneficial). Form arrays go into the already-compressed form-details
  field. Headword arrays use the same codec but usually remain small JSON TEXT.
- Compress each complete database with production Zstandard level 9 and a
  checksum. The earlier preservation sample used level 19 and a different data
  shape, so its numbers are not directly comparable.
- Extract standalone romanization/transliteration-tagged readings outside tables,
  plus explicit attached readings matching the headword. Table-form readings are
  included only when their NFC spelling matches a retained lexical form exactly.
  No readings are guessed from pronunciation rules. Combined/annotated readings
  and unmatched normalized forms are skipped; counts are recorded.
- “All forms” means all those safely extractable explicit source readings, not
  synthesized romanizations of every paradigm cell. This matters particularly
  for Hebrew's sparse attached readings.
- Small compression decreases in display-only sample variants are file-layout
  and compression effects, not a claim that adding data always saves space.
- All variant databases passed SQLite integrity checks and decoded-string
  round-trip assertions. The full pipeline suite passed: 760 tests. Four added
  tests cover extraction, standalone form entries, ambiguity, optional fields,
  display storage and indexed variants.
- This experiment does not measure lookup latency or UI behavior. It supplies
  storage evidence for choosing the scope before implementing those features.

## Reproduce

From this worktree, using the project's Python environment and cached source data:

```sh
python -m pipeline.benchmark_romanizations \
  --cache-dir /path/to/cache --output-dir /tmp/romanization-sample \
  --sample-size 5000 --seed 260915 --languages ru uk ka hi ko he

python -m pipeline.benchmark_romanizations \
  --cache-dir /path/to/cache --output-dir /tmp/romanization-full \
  --sample-size 1000000 --languages he hi ka uk ko
```

A sample size above the eligible source count selects the whole dictionary. Only
one language is built at a time. Temporary databases are checked and deleted;
JSON measurements are retained. No upload, deployment or app download is triggered.

## Implemented headword-only feature: production sample

After implementation, the same seeded samples were rebuilt with the actual
source extractor, optional headword column and language-normalized lookup table.
The production table stores one normalized key per reading, without a duplicate
precise key; original spellings remain in the display array. These results measure
the implementation, whereas the earlier tables measure a basic literal index.
Download differences reflect both normalization and the generated file layout.
These are sample measurements, not full-dictionary projections.

| Language | Installed growth | Download growth | Index rows |
| --- | ---: | ---: | ---: |
| ru | +3.6% | +7.8% | 4,900 |
| uk | +2.5% | +4.4% | 4,972 |
| ka | +1.9% | +3.3% | 4,990 |
| hi | +2.6% | +4.5% | 4,998 |
| ko | +3.9% | +6.2% | 4,966 |
| he | +2.3% | +4.0% | 4,933 |

[Raw implementation measurements](romanization-headword-production-sample.json).
