# Dictionary entry compression

Lexicoff compresses `entries.forms` and `entries.form_details` independently with
Zstandard level 6. Search, FTS and exact reverse-form lookup still use their
existing uncompressed tables. Only word-page reads decode these fields. Senses
and other entry fields retain their existing representation.

## Storage and compatibility

- Null values retain their existing meaning. Plain values remain JSON TEXT.
- JSON of 512 bytes through 64 MiB is eligible for compression. Values outside
  that range, or without a net size saving, remain JSON TEXT.
- Compressed values use SQLite BLOB storage: ASCII `LZJ1`, a four-byte unsigned
  little-endian decoded byte length, then one Zstandard frame with a checksum.
- Both readers verify the decoded size and reject corrupt compressed data.
- The browser bundles the existing `zstddec` dependency into its query worker;
  WASM initialization waits until the first compressed detail field is read.
  It is included in the existing offline worker asset, without a runtime fetch.
- New readers accept old plaintext databases. Old readers cannot read compressed
  fields: publish the updated app and newly generated manifest together, retaining
  existing immutable data URLs for older app versions.
- Pipeline audits use the same codec. No migration of installed databases is
  required; the normal manual language update installs the new generated file.

Keep whole-database download compression at level 9. It still compresses the
search/index tables and SQLite layout after detail fields have been compressed.
The download worker removes that outer layer during installation; the inner
compressed fields remain small on disk.

## Brief level comparison, 2026-09-13

Local Finnish sample from the fresh database generated from source snapshot
`2026-09-12T210000Z`. These are small local benchmarks, not full-generation or
mobile performance estimates.

A 128 MiB field sample (134,230,508 JSON bytes; 13,798 fields) compared independent
frames, including the 8-byte envelope and the production threshold/checksum.
Times are medians of two runs.

| Field level | Stored field bytes | Compression seconds |
| --- | ---: | ---: |
| 6 | 9,790,740 | 0.447 |
| 9 | 9,492,677 | 1.030 |

Level 6 compressed about 2.3 times faster for 3.1% more field bytes.

A second sample selected 5,000 evenly spaced entries using
`WHERE id % 53 = 0 ORDER BY id LIMIT 5000`, decoded their original structured
fields, then rebuilt every table/index with `write_sqlite_database`, at the
existing 16 KiB page size. Each resulting database was compressed at outer levels
6 and 9 twice (order 6, 9, 9, 6). Outer times are medians; build times are single
runs including insertion, indexing and compaction.

| Field level | Outer level | Installed bytes | Download bytes | DB build seconds | Outer seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| 6 | 6 | 26,279,936 | 7,246,655 | 1.118 | 0.147 |
| 6 | 9 | 26,279,936 | 6,532,073 | 1.118 | 0.222 |
| 9 | 6 | 26,099,712 | 7,173,948 | 1.270 | 0.158 |
| 9 | 9 | 26,099,712 | 6,474,237 | 1.270 | 0.212 |

Chosen 6/9 adds 0.7% installed bytes and 0.9% downloaded bytes compared with 9/9.
With inner level 6, outer level 6 is about one-third faster but adds 10.9% download
bytes. Retaining outer level 9 is worthwhile for a file downloaded many times.

## Validation

The Python-generated shared fixture is decoded by the real Zstandard WASM in
frontend tests. Coverage includes legacy TEXT, compressed forms and grammar
labels, Unicode, corrupt/truncated frames, length limits, native SQLite BLOB
round trips, audit fingerprints, and unchanged FTS/reverse-form results. Worker
tests also assert search and plaintext reads do not initialize the decoder.

A Chrome smoke test used the real SQLite WASM and SAH Pool/OPFS: import a
Python-built database, search an inflected form, decode 106 forms and grammar
labels, read a legacy plaintext row, terminate/restart the worker, and reopen
the persisted database. All passed. On this tiny fixture, first word access
(including decoder initialization) took 3 ms and median warm access took 0.2 ms
over 20 reads. These timings do not predict large-word or mobile performance.
