# Lexicoff search investigation — 13 September 2026

## Findings

The premature “No matches found” message was a UI state bug: an empty result
array represented both a pending request and a completed search with no matches.
The layout now displays “Searching…” during the debounce and worker request,
shows no matches only after a successful empty response, and distinguishes
failures. Superseded requests cannot overwrite the current results or status.

The production Macedonian database is `mk-691cbc31` (68,775 entry records;
66,766 distinct words; 152,301,568 uncompressed bytes). The local generated
`mk-ab71353d` file is different, so production data was downloaded and used for
the browser measurements below. Production's worker SQL matches the checkout.

Using the actual search worker code, the pinned SQLite WebAssembly dependency,
and the same OPFS SAH Pool VFS, an isolated benchmark on this Mac measured:

| Search | Safari first measured run | Safari repeated run | Chrome first measured run | Chrome repeated run |
| ------ | ------------------------: | ------------------: | ------------------------: | ------------------: |
| `fart` |                     16 ms |                2 ms |                     21 ms |              2.5 ms |
| `s`    |                     16 ms |                6 ms |                     33 ms |               26 ms |

These are instrumented worker execution times, excluding the UI's 30 ms
debounce, queue waiting, message delivery and rendering. The database had just
been imported, so these are not cold-disk or full-production-session timings.
They do not reproduce the reported long pause by themselves.

## Sources of latency before this change

1. **Homepage word counting shares the search queue.** `StorageSummary.svelte`
   invokes `storage.wordCount()` when mounted. Search results replace the
   homepage; clearing the search mounts it again. The worker executes
   `COUNT(DISTINCT word)` across _every open dictionary_, synchronously, before
   it can handle another request. The query scans the word index and builds a
   temporary distinct-value tree. Even Macedonian alone took 69 ms in Chrome;
   an installation with all languages has about 7.77 million distinct words
   in total. This is the strongest candidate for a large pause
   after opening the app or clearing a previous search, but the full installed
   Safari collection has not been profiled. It cannot explain a pause that
   occurs after the count has already finished unless other work is queued.
2. **Obsolete searches remain queued.** The 30 ms debounce only cancels requests
   that have not yet been submitted. The client serializes submitted requests
   without replacing old search requests. Ignoring their results does not save
   their execution time or let the latest query skip ahead.
3. **Single-letter prefixes do more work.** The full-text index has no explicit
   prefix indexes. `s` runs word, form and English-gloss prefix searches; the
   gloss stage dominated the measured Chrome execution time (about 13–17 ms).
   A 50-result cap does not eliminate prefix-index traversal. All stages finish
   before any results are returned, including fuzzy fallback for `fart` because
   there are fewer than five Macedonian headword matches.
4. **Every search deliberately waits 30 ms before submission.** This dominates
   warm `fart` query execution time in both tested browsers.

## Recommended performance work

- Replace superseded queued searches, preserving serialization for database
  lifecycle operations. Measure queue wait separately from worker execution.
- Reassess the debounce after removing unnecessary queue work.
- Benchmark prefix indexes against representative languages before regenerating
  datasets; measure download size as well as latency and preserve result quality.

## Implemented fix

Generated databases now include `word_count` metadata, calculated once by the
pipeline using the same distinct-display-word semantics as the old runtime
query. The worker reads that value when opening a database and keeps it in
memory. Homepage requests only sum those saved numbers; no browser code counts
entry rows. Updating a dictionary replaces its count, removing it drops the
count, and restarting reads it again from the persistent downloaded database.

Older databases without valid count metadata remain searchable. The overall
word total is hidden while any open dictionary lacks its count, avoiding both
partial totals and a legacy fallback scan. No language is automatically updated.

The search feedback fix also distinguishes pending, empty and failed searches.
Queue coalescing and debounce changes remain separate follow-up opportunities.
