# Finnish extraction: memory and CPU investigation

The failed September 13 deployments stop during extraction, before the optimized
SQLite build. The earlier 48–56 second measurement covered database construction
from already extracted records, before expanded per-form metadata. It was not an
end-to-end extraction measurement.

## Cause

`generate.py` retained the entire dictionary as Python dictionaries and lists.
Every spelling now has a `formDetails` dictionary, a list of readings, a dictionary
per reading, and lists of grammar/qualifiers. The source `Entry` and `Form` objects
were already frozen `msgspec.Struct`s; the retained output was not.

An interrupted local run of the unchanged generator reached a 15 GB process
footprint after roughly 3 minutes 28 seconds, still in extraction. System swap
usage increased during the run. This supports memory pressure as the explanation
for the CI slowdown, but does not prove the hosted runner was OOM-killed.

A sequential first-1,000-accepted-record representation probe measured:

| Representation | Bytes |
| --- | ---: |
| Python object graph, counting shared objects once | 66,482,883 |
| Forms lists and their strings alone | 6,015,107 |
| Form-details graph alone | 59,639,832 |
| JSON | 14,315,226 |
| MessagePack | 11,713,846 |
| JSON with Zstandard level 1, one frame per record | 1,456,216 |
| MessagePack with Zstandard level 1, one frame per record | 1,580,655 |

The sample contained 95,624 forms. The two component memory figures are separate
walks and must not be added: form strings may be shared. JSON encoding and
compression each took about 14 ms for this sample; decompression, decoding and
comparison with the originals took about 60 ms. Every record matched exactly.
JSON won after compression and is already the destination format for metadata.

## What all those forms are

The pinned Finnish source is `2026-09-12T210000Z`. The complete source-record audit
is in [the recorded inventory](reviews/finnish-form-memory-audit.json). These counts
are before the generator removes five identical dictionary records; they are
form-to-entry memberships, not globally distinct words.

| Part of speech | Accepted records | Retained forms |
| --- | ---: | ---: |
| Noun | 175,377 | 20,901,846 |
| Adjective | 25,464 | 2,922,685 |
| Verb | 42,008 | 2,473,795 |
| Proper name | 10,660 | 1,331,184 |
| All categories | 266,055 | 27,696,843 |

There are 37,296,826 raw forms on these accepted source records before spelling
filtering/normalization/deduplication. The median record has 158 retained forms;
the 90th percentile has 170; the largest has 540. This is broad multiplication
across a large vocabulary, rather than a few pathological million-form entries.

The noun `talo` has 158 retained spellings: for example `talon`, `taloissa`, and
`taloihin`, plus possessive forms. Noun/adjective/name paradigms combine case,
singular/plural, possessors and alternative spellings. The verb `sanoa` has 165,
including `sanon`, `en sano`, `olen sanonut` and `en ole sanonut`: multiword
negative and compound-tense forms count too. These are attested source-table
spellings; this pipeline is not generating an arbitrary Cartesian product.

Across all 27.7 million details, there are only **803 distinct detail descriptions
once the spelling is removed**. The old representation repeatedly allocated that
small vocabulary of grammatical descriptions as millions of mutable containers.

## Combined extraction and storage design

The final design combines this investigation with the
[entry compression work](reviews/entry-compression.md):

1. Extract a single source record into typed source structs and small working
   objects. Cache immutable reading summaries and their encoded JSON suffixes.
   Add encoder-escaped spellings to produce `msgspec.Raw` form-detail JSON,
   avoiding millions of repeated grammar dictionaries and lists.
2. Encode and compress `forms` and `form_details` once, using the final LZJ1
   Zstandard level-6, checksummed field format. Retain those stored values plus
   small metadata JSON and scalar ranking structs in memory. Do not compress an
   intermediate copy of the whole record. Frequency sorting touches metadata
   only, preserves ties in source order, and hence preserves SQLite entry IDs.
3. SQLite writing decodes forms needed for FTS and reverse lookup, then copies
   the already stored forms/details columns directly. Grammar details are never
   decompressed during construction. Other completed JSON metadata uses
   `msgspec.Raw` to avoid decode/re-encode.
4. Compress the complete SQLite file at level 9 with a content checksum. The
   streaming download worker removes this outer layer and checks corruption.
   Inner compressed fields remain small in browser storage.
5. The query worker searches ordinary indexes without initializing a decoder.
   Only a word-page read decompresses its large fields. Small/non-beneficial
   fields remain TEXT in the current format. Old-schema query fallbacks have
   been removed; current optional language-specific columns remain supported.

All records, forms, reading boundaries and search associations are retained.
Ordinary packed-record sequence iteration returns independent fully decoded
snapshots for audits/callers; mutation does not modify stored entries.

This still stores the compressed language in memory. It is a much smaller
representation, not a constant-memory guarantee for arbitrarily large datasets.
Disk spooling remains an option if future inputs exceed the compressed budget.

## Msgspec audit

All seven Wiktionary source types and language/conjugation configuration types
already use frozen structs. The source nested sequences are mostly tuples;
`Form.tags` is a set. `sounds`, relations and some other heterogeneous fields
still contain dictionaries through `Any`. Those source objects are transient;
converting every one is not the main memory fix.

`frozen=True` prevents field assignment, not mutation inside a set/list/dict. It
also does not deduplicate objects. Structs already default to `dict=False` and
`weakref=False`. `omit_defaults` helps when encoding structs; our source structs
are primarily decoded. `array_like` would change the wire shape and is not
appropriate for the existing Wiktionary or browser JSON schemas. `cache_hash`
would add memory for hashes we do not repeatedly calculate.

The new private packed metadata contains only scalar/string/byte values.
A four-field prototype using `msgspec.Struct, gc=False` was 48 bytes locally
versus 64 bytes for a slotted dataclass; the final struct also holds the stored
field references. Its primitive-only fields cannot form reference cycles. It
remains mutable so frequency ranking can be populated without replacing records.

A three-repeat decode-only probe of 1,000 Finnish source lines, each decoded five
times per repeat, measured these medians (seconds):

| Configuration | Convenience decode | Reused Decoder |
| --- | ---: | ---: |
| Existing frozen structs | 0.2285 | 0.2272 |
| `gc=False` on source structs | 0.2221 | 0.2220 |
| Frozenset tags | 0.2340 | 0.2304 |
| Both options | 0.2252 | 0.2231 |

These small differences do not justify broadly changing the source type model.
The SQLite iteration path reuses its typed decoder. The installed msgspec 0.21.1
JSON Decoder has no configurable string-cache option; adding a Python interning
pass would be extra work and needs a separate measured benefit.

## Validation and measurement

Run the complete language benchmark with cached pinned data:

```sh
pixi run python -m pipeline.benchmark --language fi
```

The benchmark reports extraction, SQLite build and compression separately, plus
packed payload size and peak resident memory. macOS reports `ru_maxrss` in bytes;
Linux reports KiB, converted by the benchmark. Resident memory does not include
all macOS compressed/swapped memory, so it is not interchangeable with the
interrupted baseline's process-footprint measurement.

Full baseline and optimized object-path audits produced the same SHA-256 over
all accepted extracted records in source order:
`a9daa16be1708823c1d250178d4317362f99e8e3f1463dde2903c34325dec459`.
The audits took 140.9 and 120.1 seconds, respectively, including statistics and
per-reading counting. These are instrumented audit times, not generation times.

Tests cover stable ranking, retained distinct meanings, repeatable reads,
independent mutable snapshots, identical SQLite rows and FTS postings in ordinary
and extended schemas, raw JSON equality across all source fixtures, and JSON
escaping. Existing golden extraction and form-quality checks remain unchanged.


### Intermediate whole-record packing benchmark

Before integrating field storage, on the same local Mac (Python 3.14.7, msgspec 0.21.1, SQLite 3.53.3,
Zstandard 0.25.0), generating both Finnish app datasets and the complete SQLite
file measured:

| Stage | Seconds |
| --- | ---: |
| Source extraction for both apps, including packing | 109.3 |
| Conjugation frequency/index and dictionary ranking | 17.4 |
| SQLite construction, including indexes/compaction/validation | 109.8 |
| Zstandard level 9 download compression | 28.8 |
| Total | 265.3 |

The run completed with 266,050 dictionary records, 27,696,833 normalized form
mappings and 10,890 conjugation records. Packed dictionary payload: 387,591,702
bytes (369.6 MiB). Peak resident memory for the whole process: 3,754,639,360 bytes
(3.50 GiB). The SQLite file is 5,826,543,616 bytes and the compressed download is
409,153,214 bytes. The large increase from the older 1.7 GB SQLite benchmark
reflects the current form metadata, not a change to the schema in this branch.

This is a local completion measurement, not a promise of CI timing. The lockfile
uses Python 3.14.2, SQLite 3.51.2 and msgspec 0.20.0. All 720 pipeline tests also
pass against an isolated installation of msgspec 0.20.0, and both app manifest
metadata checks pass. That intermediate run used plain SQLite fields. The final combined design adds
versioned BLOB storage for large fields and keeps full-language delivery.


The raw-JSON extraction path was also checked against every accepted Finnish
source record under CI's msgspec 0.20.0. All 266,055 records produced the same
SHA-256 shown above. That streaming extraction/hash check took 81.1 seconds and
49.2 MB peak resident memory; it does not retain the language, extract
conjugations, rank frequencies, or build SQLite. The reading-JSON cache had
27,696,005 hits and 838 misses (some source patterns simplify to the same output).


### Final combined generation and storage

The complete combined run used Python 3.14.7, CI-pinned msgspec 0.20.0,
SQLite 3.53.3 and Zstandard 0.25.0 on the local Mac. It measured:

| Metric | Intermediate plain SQLite fields | Final compressed fields |
| --- | ---: | ---: |
| Extraction, packing, both apps' indexes and ranking | 126.7 s | 126.3 s |
| SQLite construction and validation | 109.8 s | 40.3 s |
| Outer compression | 28.8 s | 9.9 s |
| Total | 265.3 s | 176.5 s |
| Retained dictionary payload | 369.6 MiB | 364.8 MiB |
| Whole-process peak RSS | 3.50 GiB | 2.11 GiB |
| Installed SQLite bytes | 5,826,543,616 | 1,415,987,200 |
| Download bytes | 409,153,214 | 306,261,933 |

In the final run, extraction itself took 111.0 s and peaked at 745,521,152 bytes
(711 MiB). The later Congeegator search-index stage took 14.0 s and raised the
process high-water mark to 2.11 GiB. The dictionary-object blowup is resolved;
the next distinct memory hotspot is that conjugation search-index construction.
These are single desktop runs (the staging build briefly overlapped the start of
the final run), not isolated multi-run CPU comparisons or Linux runner timings.

Full database comparison checked every one of the 266,050 entry rows, decoding
only the changed storage representation for comparison. All fields matched.
All 27,696,833 `form_lookup` rows, metadata and every row of both FTS indexes'
internal data/index/docsize/config tables matched exactly. This check took 50.3 s.
No form, reading or search association was dropped to obtain the savings.

Final checks: 731 Python tests with msgspec 0.20.0, 153 frontend tests, frontend
lint, Svelte typecheck and staging build pass. Tests include the actual Zstandard
WASM decoding Python fixtures and checksum corruption/retry in the streaming
download worker. The older-schema fallbacks are removed, while basic and extended
current schemas and TEXT/NULL/BLOB fields remain tested.
