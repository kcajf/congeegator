# Lexicoff independent senses, examples, and relations audit

Audit date: 2026-09-12. This is a source-to-processed-data review of the linked-entries worktree, not an editorial certification of Wiktionary. Findings describe the processing snapshot collected during this audit; some have been reported to the implementation agent for correction while work continues.

## Method and coverage

- Streamed all pinned JSONL records in **10 languages**: English, Greek, German, French, Russian, Finnish, Hungarian, Turkish, Vietnamese, and Latin. Existing-language snapshot: `2026-09-07T120928Z`; added-language snapshot: `2026-09-12T210000Z`.
- Scanned **4,128,260 raw entries** and **5,001,737 senses**, after excluding the expressly excluded POS types from the sense statistics. The raw-entry count is before that exclusion. These are source counts, not final shipped-entry counts.
- Independently reservoir-sampled 12 example-bearing senses, 12 relation-bearing senses, and 12 labeled senses in each language, using Python `random.Random('lexicoff-senses-20260912-' + language)` and one sequential random stream per language. This yielded **360 distinct senses from 360 distinct entries**. Sample selection is uniform within each feature stratum, not uniform across the dictionary; large form-only populations do not drown out examples and relationships.
- Ran the typed production parser and `process_dict_entry` on every sampled entry. All 360 sampled senses survived and were matched by their final source gloss. Compared retained examples with their own source sense, verified translation/romanization/reference field retention, checked output emphasis ranges, and examined label/relation losses.
- Closely read the first six samples in each language/stratum: **180 sampled sense records**, including **60 example-bearing senses** and their displayed excerpts. Additional examples and anomaly records were read when investigating failures. This is a human-readable close review, separate from the full-file automated scan and 360-entry processing checks.
- Local reproducibility artifacts: `/private/tmp/lexicoff-senses-audit.py`, `/private/tmp/lexicoff-senses-audit.json`, `/private/tmp/lexicoff-senses-summary.py`, and `/private/tmp/lexicoff-senses-summary.json`. These contain sample source objects, processed records, source counters, and anomaly details; they are not runtime app assets.

## Full-source results

Across these ten languages the scan found **922,035 examples**, of which **130,373 have translations**, **835,918 have source bold offsets**, and **687,676 have references**. Both `translation` and legacy `english` are populated in many records: counting both would double-count the same translation.

There are **495,631 senses with examples**, **227,638 senses with synonyms or antonyms**, and **49,514 senses with more than three source examples**. The three-example shipping limit affects about **10.0% of example-bearing senses**. Only **490 individual example texts exceed 1,200 characters** (0.053% of examples). The cap is doing materially more size reduction than the length cutoff.

| Language | Examples | Type example | Type quotation | Missing type | Invalid original bold ranges | >3 examples/sense |
|---|---:|---:|---:|---:|---:|---:|
| en | 765,057 | 97,230 | 622,532 | 45,295 | 223 | 45,927 |
| el | 8,846 | 7,158 | 273 | 1,415 | 16 | 126 |
| de | 29,521 | 15,369 | 13,588 | 564 | 144 | 545 |
| fr | 20,607 | 11,690 | 7,541 | 1,376 | 46 | 523 |
| ru | 30,366 | 19,413 | 9,438 | 1,515 | 76 | 892 |
| fi | 19,927 | 17,535 | 1,483 | 909 | 16 | 476 |
| hu | 13,000 | 10,734 | 1,297 | 969 | 6 | 158 |
| tr | 4,920 | 3,304 | 838 | 778 | 14 | 89 |
| vi | 14,774 | 10,269 | 4,189 | 316 | 49 | 319 |
| la | 15,017 | 2,347 | 11,233 | 1,437 | 18 | 459 |

Only `example`, `quotation`, and missing type occurred in this full scan. A missing type is not necessarily corrupt: it includes legitimate collocations, usage notes, older quotations, and word-formation illustrations.

## Findings that merit bounded fixes

1. **Useful labels are silently omitted because normalized source names differ from the allowlist.** Seventeen sampled senses lose at least one of `figuratively`, `plural-normally`, `ambitransitive`, `familiar`, or `idiomatic`. Examples: English *hand-hold*, Greek *κολλάω*, French *ne pas être piqué des vers*, Russian *батя* and *абрикос*, Hungarian *jósol*. Source `figuratively` is especially common in this sample while the allowlist contains `figurative`. Normalize these aliases or allow the actual upstream tags. Latin *seraph* additionally uses `in-plural`, another useful usage distinction.

2. **Topic substring matching admits unwanted ancestor labels.** English *auracyanin* has explicit `(biochemistry)`, but the output also keeps `chemistry`. Vietnamese *xuất quân* has a similar false match for `war`. Two sampled senses show this. Match topic phrases at word boundaries, preferably inside explicit leading label groups, rather than arbitrary substrings of the whole raw gloss. Parent-topic suppression otherwise works well: English *kill* keeps metallurgy without engineering/natural sciences; German *Kapitän* keeps sports without hobbies/lifestyle.

3. **Relation qualifiers can change the meaning of a synonym.** English *mendacious* receives *bastard* from `Thesaurus:untrue`, qualified in raw data as `of plant species`. `raw_tags` is discarded, so the app shows an apparently unrestricted synonym. Preserve cleaned relationship `raw_tags` alongside recognized tags. One sampled relation has this specific loss. Fifteen sampled relations also retain redundant internal tags `synonym` / `synonym-of`, which should not become visible qualifiers beneath an already-labeled Synonyms list. Examples: French *petit pain*, Finnish *lähin*, Turkish *kulunç otu*.

4. **Maintenance-message filtering removes useful quotation attribution.** Three retained sampled quotations lose their complete source because its reference contains a trailing `(Please provide a date or year)`: Russian *выпиливать*, *болезнетворный*, *падчерица*. Each still has a usable author/title and original year. Remove narrowly recognized maintenance placeholders from a reference while preserving the remainder, rather than discarding the whole reference. Translation placeholders should still be omitted.

5. **A small amount of malformed markup still reaches examples.** English *Star Warsy* contains literal triple-apostrophe formatting remnants. Finnish *toteuttaa* contains `x²-9#61;0`, a broken equals entity. These are two retained sample examples, not a full-source prevalence estimate. A narrow malformed-markup filter is safer than attempting arbitrary wiki parsing. If replacing/removing text, offsets must be recalculated or omitted; do not shift text beneath unchanged emphasis offsets.

## Findings to retain as known limitations

- **Raw field assignments are sometimes already wrong.** German *unantastbar* stores a 1949 legal citation in `text`, the German sentence in `roman`, and its English rendering in `translation`. Turkish *kabul etmek* stores an English translation in `roman`. Latin *seraph* stores another Latin sentence there. Do not globally swap or reinterpret these fields: the same slot is correctly used for Russian/Greek transliteration in many good records.
- **Untyped examples can really be notes.** Greek *αγοροφέρνω* contains an English lemmatization explanation; *Λευτεράκης* contains “also see” alternative-name guidance. Latin *inspectrix* has only a citation as a quotation's text. Latin *donum* mixes source, Latin, translation, and explanatory prose inside one `text` field. These deserve upstream correction or a future typed “usage note” presentation. Dropping every untyped example would also lose valid data.
- **Ruby readings are not yet exposed.** Vietnamese *tình chung* has a Chữ Nôm quotation with 14 structured ruby pairs and no `roman` string. The original script and English remain, but the Vietnamese reading is unavailable. One sampled retained example has ruby without romanization. A future explicit ruby model/rendering is preferable to concatenating readings heuristically.
- **Grammar and geographic labels remain selective.** The sample includes Vietnamese *sui gia* and *lố* marked Southern Vietnam in raw tags; that distinction disappears. Finnish *lehto* keeps South Ostrobothnia through `qualifier` but loses Tavastia, which arrives as a tag. Russian *готовый* has a `with к + dative` construction in raw gloss text that is absent from the clean definition. These show why a strict whitelist cannot preserve every usage distinction. Broad raw-gloss replacement is not justified: it duplicates structured tags and carries its own inconsistent extraction artifacts. A separate, bounded usage-label/construction model is a better next step.
- **Thesaurus material is broad by nature.** English *outsider* imports a long range of terms through multiple thesaurus entries; English *mendacious* has 22 source synonyms. Sense attachment is preserved by the pipeline, but it cannot guarantee every imported synonym is interchangeable. Collapsing long lists and keeping qualifiers is appropriate.
- **Source offsets are not always correct.** The scan found 608 invalid original-text ranges and 2 invalid translation ranges. Greek *ρεύμα* is a concrete example: a source offset extends far beyond the text. Current bounds validation safely discards that bold range and keeps its valid translation emphasis. Bounds cannot catch plausible but semantically wrong offsets, so source-derived emphasis is still only as accurate as upstream extraction.

## Checks that passed

All **219 retained examples** encountered across the 360 sampled senses could be traced back to the same source sense. All **136 retained translations** matched the source translation/legacy-English text after whitespace normalization; there were no observed translation swaps introduced by the pipeline. All **295 retained bold ranges** were within the corresponding processed text's Unicode-code-point bounds. No sampled sense disappeared and no relation was moved between senses by the processor.

Good examples include Greek *είδος*, *φταίω* and *μιλάω* (original, transliteration, translation, aligned emphasis); French *éraillé* (quotation, translation and author preserved); Finnish *hoitaa* and *mallisto*; Hungarian *igénybe vesz* and *rajtuk*; Vietnamese *phòng bị* and *xoa*; Latin *procuro* and *sperno*. Nested Latin *sub-* and German inflection senses preserve their parent context in the reconstructed gloss, rather than showing disconnected fragments.

The first-example preview with additional examples collapsed is sensible. Keeping references collapsed avoids making ordinary reading compete with long bibliographic strings. Likewise, sense-level synonyms immediately under their own meaning are easier to interpret than an undifferentiated entry-level list.

## Limits of the conclusions

The full scan covers ten varied languages, not all 25. The sample intentionally overrepresents enriched records and is not an estimate of the fraction of all dictionary pages with editorial problems. Full-source counting validates structure and prevalence, not the linguistic correctness of nearly a million examples. The close review checks meaning/presentation where reasonably interpretable and compares source association, but is not native-speaker verification across ten languages. Source and generated output were inspected locally; no external Wiktionary edits were made.

## Verification after implementation fixes

Replayed the current `extract_senses` against all **360 saved raw sample senses** after the implementation agent addressed the reported issues. All 360 still survive. There are now **218 retained examples** and **292 output emphasis ranges**; every range remains valid. The removed example is the malformed *Star Warsy* quotation.

Confirmed fixes:

- `figuratively`, `plural-normally`, `ambitransitive`, and `familiar` are now retained in the reported cases.
- *auracyanin* retains only biochemistry; *xuất quân* retains only military, with accidental substring-topic matches gone.
- *mendacious* → *bastard* now keeps “of plant species”.
- All three reported Russian quotation references retain their author/title/year with the maintenance prompt removed.
- Usage examples are prioritized before quotations while the bounded number remains unchanged.

Final follow-up: `idiomatic` was subsequently added to the retained labels. Remaining residuals: the cleaned references can end in cosmetic fragments such as “English translation from :”; Finnish *toteuttaa* still contains the broken equals entity. A closer read of Russian *падчерица* also reveals that its **raw source already supplies the author's name, “Elizaveta Vodovozova”, as the translation**. The pipeline preserves that mistaken source assignment. This is an upstream editorial issue, not a translation swap introduced by the implementation.

There is no reliably safe small filter for all untyped usage notes in this sample. The same structural shape carries legitimate Latin word-formation examples, collocations, and older quotations. Keep these source limitations documented instead of deleting all untyped examples or guessing at text-language classification.
