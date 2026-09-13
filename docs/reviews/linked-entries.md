# Lexicoff linked entries — review guide

Implemented on `codex/lexicoff-linked-entries` in an isolated worktree, initially from `eeed86d` and merged with main at `6e0e544` before PR review. The original checkout was left untouched. The local preview is [http://127.0.0.1:5177](http://127.0.0.1:5177).

## What changed

Definitions now link to source-specified words. Form-of and alternative-of senses point to their base entries, preserving grammatical context. Source link labels and canonical page titles are kept separate, which matters for stressed Russian/Ukrainian and macronized Latin. A downloaded target language opens inside Lexicoff; otherwise a marked ↗ link opens Wiktionary. Missing local entries offer similar-word search and a Wiktionary fallback.

Sense-level synonyms and antonyms retain their association and qualifiers. Grammar and explicit topic labels precede definitions. Examples retain original text, translation, romanization, validated emphasis, and quotation attribution. The first example is shown, with additional examples and references collapsed. Up to three examples are retained, preferring usage examples over quotations; texts longer than 1,200 characters are omitted.

Full etymology prose is preserved for each entry, with conservative links from common mention, borrowing, doublet, and compound/affix templates. Ambiguous and repeated etymology labels remain plain rather than receiving a guessed destination. Related words, derived words, and forms are collapsed; large collections load their contents on expansion. Related and derived words group repeated labels and offer filtering; forms have no separate search bar. Part-of-speech links allow quick jumps within long pages. Exact spellings distinguish entries such as German Haus and haus.

A new indexed `form_lookup` table provides exact reverse lookup without scanning paradigms. Exact form matches rank after exact headwords and before broad prefix matches, and the result shows the matched form alongside its headword. If a form has no standalone entry, its page shows the matching entries under “Found under.” This wording also covers source forms that are related words or derivations rather than strict inflections. Auxiliary verbs and identified grammatical instructions are excluded from form indexing.

Older installed dictionaries still open and render their original string examples. The new data is obtained through the existing manual update/download flow. The original 25 dictionaries and their manifest were regenerated locally; their data artifacts remain in the worktree's ignored `apps/lexicoff/r2_data/` directory. Main subsequently added 20 dictionaries. Those additions retain their existing manifest artifacts here; the merged pipeline will generate rich data for all 45 on deployment. The full-database audit and size figures below describe the original 25-dictionary snapshot.

The presentation follows the sense-level relationships and progressive disclosure described in [motî's documentation](https://xn--mot-xma.net/documentation/), while keeping Lexicoff's existing appearance. The extraction uses [Wiktextract's structured fields](https://github.com/tatuylonen/wiktextract/blob/master/src/wiktextract/extractor/en/type_utils.py), rather than parsing arbitrary raw gloss markup.

The merge preserves the new dictionaries’ pronunciation labels, form qualifiers, script isolation and search aliases. Regression checks cover rich examples through language-specific filtering and SQLite/worker round-trips with links, pronunciation metadata, and exact reverse forms together. The [complete etymology-language classification](etymology-languages.md) covers all 721 varieties and 11 legacy aliases; 144 varieties now resolve to 28 of the 45 supported dictionaries.

Kaikki still omits ordinary mention links from some etymologies, including French **avaler: aval + -er**. This PR does not guess those destinations. The extractor fix is committed separately on [kcajf/wiktextract’s etymology-links branch](https://github.com/kcajf/wiktextract/tree/etymology-links), with all 1,796 upstream tests passing. Integration of its new `etymology_links` field is deferred until upstream data carries it.

## Suggested review paths

Install languages from the preview homepage before exploring them. German, Greek, French, English, and Latin were installed in the review browser.

- [German Haus](http://127.0.0.1:5177/de/Haus): translated examples, synonym navigation to Heimat, grouped/filterable derived words, full etymology. Hausboot is a genuine missing entry in the pinned source and exercises the recovery page; Baumhaus and Hausarzt are present.
- [German manchen](http://127.0.0.1:5177/de/manchen): three grammatical senses, each linking to manch.
- [German phrase form](http://127.0.0.1:5177/de/machte%20sich%20auf%20den%20Weg): exact reverse lookup to sich auf den Weg machen. Searching the same phrase shows the entered form with its headword. Its 130 raw form rows become 85 distinct searchable strings after auxiliary removal.
- [Greek ψηφοφορία](http://127.0.0.1:5177/el/%CF%88%CE%B7%CF%86%CE%BF%CF%86%CE%BF%CF%81%CE%AF%CE%B1): feminine gender, politics label, English definition links, related Greek words.
- [French maison](http://127.0.0.1:5177/fr/maison): separate noun/adjective meanings, translated examples, and a Latin etymology target with a different display spelling.
- [French manger](http://127.0.0.1:5177/fr/manger): transitive/intransitive labels, synonyms, example emphasis and translations.

## Validation

- **606 pipeline tests** and **111 frontend tests** passed, including legacy-database compatibility, exact-form retrieval, Unicode boundaries, canonical targets, ambiguous links, and source emphasis offsets.
- Type checking passed with no errors. Lint and formatting passed. The production build completed. The staging build also passed after merging main. Non-blocking build warnings remain for optional PWA icon-generation packages absent in this local installation and a PWA JSON glob with no matches.
- All **25 generated databases**, containing **7,632,607 records** and **45,342,685 indexed form relationships**, passed SQLite integrity and both FTS integrity checks. No orphaned form relationships were found. All **125 common-word presence/search probes** passed. Every compressed hash and byte count matches the final manifest. The machine-readable results are in [database-verification.json](database-verification.json).
- Browser checks covered linked-word navigation, history, disclosure/filtering, missing-word recovery, exact form search, grammatical base links, and a 390-pixel layout without horizontal overflow. A Greek related-word navigation succeeded with the local server stopped, using the installed dictionary. This is an in-session offline navigation check, not a new end-to-end audit of the existing PWA installation/update lifecycle.

## Independent data reviews

The reviewers used different deterministic samples and feature strata. Counts below should not be added together as a count of unique reviewed entries: some samples overlap.

- [Links and etymologies](links-audit.md): all 25 source files inventoried; 300 enriched records plus 200 etymology sample positions; 100 closely read sample positions and 100 additional real multi-doublet examples. Fixes eliminate all identified wrong-link cases in the final checked samples. Etymology links appear in 129/200 sampled records, up from 70/200 in the initial implementation.
- [Senses, examples, and relations](senses-audit.md): 922,035 examples counted across 10 languages; 360 random enriched senses processed, 180 closely reviewed. Fixes preserve usage labels, relation qualifiers, valid attribution, and validated emphasis.
- [Forms and retrieval](forms-audit.md): 500 random form-bearing records plus 50 targeted records across all 25 languages; over 100 representative records closely inspected; 1,600 probes against full databases; all 10,974 retained forms in the final sample databases passed exact lookup.

The reusable `pipeline.audit_dictionary` command now understands structured examples and linked fields, reports relationship/translation/emphasis coverage, checks reverse-index orphans, and accepts `--sample-size` for larger deterministic samples.

## Known limits and data cost

This is a bounded first pass. It does not parse every etymology template, reconstruct proto-language URLs, render Vietnamese ruby readings, or expose every usage/construction tag. Unsupported complex templates and ambiguous etymology occurrences stay readable as plain text. Missing link targets can be genuine upstream red links or gaps in the pinned source. Some raw examples already misassign translations or contain usage notes; these are documented rather than silently reinterpreted. The audit reports distinguish structural checks from linguistic/editorial certainty.

The extra information and exact reverse index increase total compressed downloads from **763.1 MiB to 1,183.2 MiB (+55%)** across all 25 languages. Dictionaries remain individually downloadable. This is the principal product tradeoff for review; collapsed UI does not reduce download size. Finnish is particularly affected because its source contains tens of millions of forms. Full form data is still retained for search and optional inspection; further storage compaction is separate work.

| Language | Before (MiB) | After (MiB) | Change |
|---|---:|---:|---:|
| Catalan | 12.2 | 15.7 | +29% |
| Czech | 8.7 | 13.4 | +54% |
| Danish | 4.6 | 7.2 | +54% |
| German | 35.9 | 53.6 | +49% |
| Greek | 13.5 | 17.5 | +29% |
| English | 163.5 | 268.4 | +64% |
| Esperanto | 7.1 | 9.5 | +34% |
| Spanish | 53.8 | 67.7 | +26% |
| Finnish | 126.6 | 249.2 | +97% |
| French | 29.4 | 37.6 | +28% |
| Galician | 10.8 | 14.1 | +30% |
| Hungarian | 17.9 | 32.5 | +82% |
| Indonesian | 4.2 | 6.7 | +60% |
| Italian | 42.5 | 54.1 | +27% |
| Latin | 52.2 | 69.5 | +33% |
| Norwegian Bokmål | 6.1 | 8.6 | +41% |
| Dutch | 12.8 | 19.2 | +50% |
| Polish | 20.6 | 31.0 | +51% |
| Portuguese | 30.8 | 38.9 | +26% |
| Romanian | 13.3 | 20.8 | +57% |
| Russian | 45.4 | 64.9 | +43% |
| Swedish | 22.9 | 30.5 | +33% |
| Turkish | 15.5 | 31.2 | +101% |
| Ukrainian | 9.0 | 14.9 | +65% |
| Vietnamese | 3.8 | 6.3 | +66% |
