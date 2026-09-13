# Pipeline performance

Run a complete single-language benchmark without modifying app manifests or
generated app data:

```sh
pixi run python -m pipeline.benchmark --language fi
```

The benchmark uses the pinned source cache, processes the applicable conjugation
and dictionary data, builds SQLite, and compresses it at the production Zstandard
level. Temporary databases are removed after the run. Its JSON summary separates
processing, database construction and compression. A cold source download is
included in processing time; warm the source cache before comparing changes.

For Python call counts and hotspots:

```sh
pixi run python -m cProfile -o /tmp/fi.prof -m pipeline.benchmark --language fi
pixi run python -m pstats /tmp/fi.prof
```

Use unprofiled runs for wall-clock comparisons. Profiling disproportionately adds
overhead to Python functions and iterators called millions of times. Run variants
sequentially on the same machine, with the same source and dependencies.

## Findings from September 2026

The Finnish benchmark input contains 266,050 accepted dictionary records and
27,717,066 distinct normalized form mappings (27,717,076 before normalization).
The database build includes all those
reverse lookups, two full-text indexes, and the structured dictionary content.
It is substantially more work than inserting 266,050 headwords.

Sequential local runs on macOS, Python 3.14.7 and SQLite 3.53.3 measured:

| Work | Original | Optimized |
| --- | ---: | ---: |
| Full Finnish SQLite build | 208.3 s | 48.1–55.7 s |
| Extract 10,000 Finnish source entries, median of 3 runs | 1.814 s | 0.995 s |
| Extract 10,000 English source entries, median of 3 runs | 2.296 s | 1.650 s |

Database measurements include both search indexes, compaction, validation and a
final file sync. The first round reached 90.3 s. Further changes reduced this to
69.1 s; repeats measured 54–56 s as machine load varied. A sequential full-input
comparison measured 54.3 s (54.2 CPU seconds) with default FTS settings against
48.1 s (46.7 CPU seconds) with larger FTS blocks and deferred merging.
The latter database was 1,745,567,744 bytes, compared with the original
1,802,424,320 bytes. Do not interpret the fastest run as a deployment guarantee.
The final-code repeat took 55.7 s (48.0 CPU seconds): 23.0 s loading rows,
8.9 s building form lookups, 0.7 s ordinary indexes, 3.7 s FTS merging,
10.0 s compaction/statistics and 9.2 s validation.

Zstandard level 9 compression of the earlier 90.3 s build took a separate 14.9 s,
reducing 1,802,424,320 bytes to 261,308,674 bytes. Compression is not included in
the database-build numbers. The final database compressed in 13.2 s to
266,459,211 bytes: the new page layout produces a 3.2% smaller raw database but
a 2.0% larger download at the same compression level.

The first-round database comparison checked every entry and form mapping,
metadata, schema, and both FTS vocabulary tables, including 25,151,485
main-search terms. They matched. The final build was then compared with that
verified output: all 266,050 entries, 27,717,066 form mappings, metadata,
28,892,770 main FTS postings and 2,303,538 fuzzy postings matched. The new nullable
form-label column was checked separately because the frozen input predates it.
SQLite and both FTS integrity checks passed. The Python sample outputs also
matched byte for byte. The final pipeline suite passed all 676 tests; both
manifest metadata checks passed, as did empty normal/extended database checks.

These are local measurements, not a prediction for the whole deployment. The
benchmark input was captured before PR #243 expanded form-label storage. The
changes have since been integrated with that schema and its tests. CI's pinned
Python/SQLite versions also differ from the local benchmark environment.

A full Finnish processing profile recorded about 37 million text-cleaning calls.
Form extraction was the largest Python hotspot. The optimized cleaner recognizes
alphabetic strings without running the markup regex; other strings retain the
existing filter. Form-tag checks reuse an immutable set, and dictionary links
reuse the language-anchor lookup instead of rebuilding it for each link.

Database loading now uses a bounded 64 MiB page cache and one loading transaction.
Ordinary indexes are built after inserting the entries. Each 5,000-entry batch
still bounds the Python row buffers, but no longer forces a transaction commit.
Form mappings first go into an on-disk temporary table, then into the final
primary-key index in sorted order, avoiding random-page updates for each form.
They are inserted 1,000 mappings per SQL statement. The scratch database uses
16 KiB pages and up to four SQLite sorter workers. Larger 32/64 KiB pages did not
improve build time and slowed sampled queries, so those variants were rejected.
FTS uses 16,300-byte leaf blocks with automatic merging deferred until the final
explicit optimize; the emergency merge threshold remains bounded at 1,024
segments, and normal merge settings are restored before publishing. Sampled
full-input FTS queries returned the same 7,204 rows; aggregate query time was
0.084 s versus 0.052 s for default FTS blocks, so the build saving has a small
measured read-time tradeoff on this local sample.

Further Python experiments were rejected: replacing the per-form loading loop
with iterator batching and passing JSON bytes through SQL casts both failed to
beat the unchanged control (roughly 13.6–13.9 s on one third of the entries).
Disabling Python garbage collection also gave no measurable improvement.

SQLite construction logs separate row insertion, ordinary indexes, FTS merging,
vacuuming and validation. Compression is timed separately in normal generation.

## Cache experiments

An 8,192-entry LRU cache for all short text-cleaning inputs hit about 31% of calls
on the Finnish sample, but slowed extraction from about 0.94–1.00 s to
1.12–1.20 s. Increasing it to 65,536 entries barely improved hits and was slower.
The alphabetic fast path costs less than managing these caches.

Across all Finnish form mappings, an 8,192-entry normalization cache hit only
1.6% of calls and increased normalization time from 6.1 s to 9.7 s. These caches
were not retained. Link-result caches also failed to improve the samples, while
selectively caching non-alphabetic cleaning had mixed gains. Wordfreq already
caches frequency results internally.

Grammatical readings introduced a much better reuse opportunity. Across the first
10,000 Finnish source records, 1,717,620 forms used only 379 distinct combinations
of recognized grammatical tags. A bounded 8,192-entry cache had 1,717,241 hits
(99.98%), reducing median formatting time from 2.212 s to 0.479 s across three
runs. This cache is retained. Keys contain only recognized grammar tags, values
are immutable tuples, and callers receive fresh lists so cached results cannot
be modified accidentally. This is a formatting microbenchmark, not the speedup
of the entire extractor.

## Build-file safety

The writer uses a SQLite-owned temporary database (an empty filename), which can
spill to disk and is removed when closed. It omits rollback journaling,
secure-deletion page wiping and repeated synchronization during this disposable
build because errors discard the file instead of attempting to recover or publish
it. `VACUUM INTO` compacts directly to a unique temporary sibling of the output,
avoiding ordinary VACUUM's copy back over the intermediate database. The result is
validated with `quick_check`, restored to DELETE journal mode, closed and synced
before replacing the destination. Existing downloads and browser SQLite settings
are unaffected. Both FTS indexes are still optimized, and compaction is retained.

These settings are specific to reproducible build artifacts. SQLite documents the
crash risks of disabling journaling and synchronization in its
[PRAGMA reference](https://sqlite.org/pragma.html), and the final FTS merging
operation in its [FTS5 reference](https://sqlite.org/fts5.html#the_optimize_command).
See also [temporary databases](https://sqlite.org/inmemorydb.html#temporary_databases)
and [VACUUM INTO](https://sqlite.org/lang_vacuum.html#vacuum_with_an_into_clause).
