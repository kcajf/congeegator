# Verified Bug Hunt Findings

Bug-hunt run on the repository root. Final referee result: 9 reported, 1 dismissed, 8 confirmed.

## Confirmed Findings

| Bug | Severity | File | Summary | Suggested fix |
|---|---|---|---|---|
| BUG-1 | Medium | [apps/lexicoff/src/lib/download.worker.ts](/home/frigaardj/work/congeegator/apps/lexicoff/src/lib/download.worker.ts#L111) | Same-language downloads can run concurrently and write the same OPFS file. | Add per-language in-flight dedupe/locking and use exclusive or temp-file writes. |
| BUG-2 | Medium | [apps/lexicoff/src/lib/sqlite.worker.ts](/home/frigaardj/work/congeegator/apps/lexicoff/src/lib/sqlite.worker.ts#L147) | Raw SQLite file is deleted before the pooled DB is confirmed to open successfully. | Delete the raw file only after successful pooled open/validation. |
| BUG-3 | Medium | [pipeline/pin_source_data.py](/home/frigaardj/work/congeegator/pipeline/pin_source_data.py#L41) | English pinning fetches plain `.jsonl` but always tries to gunzip it. | Detect compression or special-case English to read the stream directly. |
| BUG-6 | Medium | [pipeline/generate.py](/home/frigaardj/work/congeegator/pipeline/generate.py#L44) | Generator loads the full filtered dataset into memory before processing, defeating `--dev` early exit. | Stream directly from the cache generator instead of `list(...)`. |
| BUG-4 | Low | [apps/congeegator/src/routes/dev-r2-mock/[...file]/+server.ts](/home/frigaardj/work/congeegator/apps/congeegator/src/routes/dev-r2-mock/[...file]/+server.ts#L24) | Dev mock route allows path traversal outside `r2_data`. | Verify the resolved path stays within the `r2_data` root. |
| BUG-5 | Low | [apps/lexicoff/src/routes/dev-r2-mock/[...file]/+server.ts](/home/frigaardj/work/congeegator/apps/lexicoff/src/routes/dev-r2-mock/[...file]/+server.ts#L26) | Lexicoff dev mock route has the same path traversal issue. | Verify the resolved path stays within the `r2_data` root. |
| BUG-8 | Low | [apps/congeegator/src/routes/[lang=lang]/[verb]/+page.svelte](/home/frigaardj/work/congeegator/apps/congeegator/src/routes/[lang=lang]/[verb]/+page.svelte#L24) | Highlighting fails for marker-bearing forms because the hash and displayed form are normalized differently. | Normalize both sides the same way before comparison. |
| BUG-9 | Low | [pipeline/output.py](/home/frigaardj/work/congeegator/pipeline/output.py#L38) | Reusing `write_language_data()` on an existing output dir crashes if `chunks/` already exists. | Make `chunks_dir` creation idempotent or recreate it safely. |

## Dismissed Finding

| Bug | Reason |
|---|---|
| BUG-7 | `zstddec/stream` appears valid; the observed failure was due to missing local installation or environment drift, not a code bug. |

## Summary

| Metric | Count |
|---|---:|
| Total reported by Hunter | 9 |
| Dismissed as false positives | 1 |
| Confirmed as real bugs | 8 |
| Medium | 4 |
| Low | 4 |

## Manual Review

The referee flagged these as lower-confidence items for manual review:

- BUG-4
- BUG-5
- BUG-9
