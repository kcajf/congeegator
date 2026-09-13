# Forms quality review, September 2026

Forms now retain complete grammatical readings for all 45 dictionaries. Subject,
object and possessor information remain distinct; usage notes belong to an
individual reading. The first reading is visible beside the spelling, with other
readings expandable underneath. Inflections, spelling variants and related
formations have separate groups. Unclassified forms remain visible as “Other
forms.” Old downloads still display their existing flattened labels as one
reading. Only exact dictionary headwords receive links.

Normalization happens before deduplication and SQLite reverse indexing. Reviewed
rules remove table instructions, placeholders, detached French auxiliaries,
foreign table cells and broken transcription fragments. Alternatives are split
only in known source patterns: French comma alternatives must be single words,
for example. Greek bracket qualifiers and shared future particles retain their
scope. Complete optional endings, multiword forms, alternate scripts, suffixes,
and valid error-tagged forms are protected by regression tests.

The Turkish `tr-conj` source has shifted person columns. Six-cell signatures
matching the reviewed column layouts are corrected; uncertain or incomplete
rows retain spelling and tense but omit person and number. Across the pinned
source, 534,912 source form objects receive corrected person labels and
1,156,660 have unverified person labels withheld. These are processing counts,
not a claim that every withheld label was wrong. Missing tense distinctions in
upstream extracts are not guessed.

The source comparison against main after PR #243 (`bc209df`) covers 8,260,472
source lines and 51,988,813 baseline form occurrences across all 45 languages.
The new output contains 51,963,376 form occurrences: 57,097 old occurrences are
replaced or omitted, and 31,660 cleaned alternatives are added. Counts refer to
spellings within source records before final generator deduplication, not
unique words or confirmed errors. Replacing `lennék or` with `lennék` contributes
one removal and one addition. Moving an auxiliary note to metadata may merge
with a spelling already present and contribute only a removal.

[The scan inventory](forms-quality-scan.json) records per-language counts and
reason counters. Initial omission review caught and corrected over-broad French
comma splitting. Broken Greek cells with unresolved footnotes or brackets remain
omitted; the importer does not invent stems from shorthand endings. Ambiguous
source tags such as `specific` and `special` remain in the audit inventory rather
than receiving guessed meanings. This is a reviewed cleanup with regression
coverage, not certification of every linguistic reading.

## Repeat the checks

`pixi run test` includes the reviewed forms baseline and source regressions.
`pixi run python -m pipeline.audit_forms --check` checks the baseline directly.
It includes spelling/reading fingerprints, unknown tags, omission/repair reasons,
and forms-per-entry distributions. Use `--update` only after reviewing changes.

For a full cached-source audit:

```sh
pixi run python -m pipeline.audit_forms --source-root cache --workers 4 --output output/forms-quality
```

Add `--baseline-repo /path/to/previous/checkout` to compare source-record
omissions and additions. Use `--languages el fr` to limit a review. Full scans
read pinned local source files; they neither download nor publish data.

The existing monthly source refresh runs this full inventory and uploads a
`dictionary-forms-quality` artifact for its refresh PR. New source anomalies are
review signals; no arbitrary punctuation threshold fails CI. The compact,
committed fixture baseline protects importer changes on ordinary PRs.

Local validation includes the pipeline suite, frontend tests, formatting,
type checking, staging build and a browser check of expanded Greek readings and
exact-headword links. Deployment regenerates dictionaries; already downloaded
databases retain their old data until the user updates them.
