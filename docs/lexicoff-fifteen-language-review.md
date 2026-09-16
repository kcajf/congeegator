# Fifteen Lexicoff dictionaries — September 15, 2026

Adds Arabic, Chinese, Japanese, Asturian, Navajo, Albanian, Telugu, Swahili, Armenian, Thai, Cebuano, Tamil, Bengali, Punjabi and Urdu (69 dictionaries total).

## Source

Full raw English Wiktionary extract, September 2 dump / September 9 extraction. Compressed extract SHA256: `42e0bfe1669513cb89bd0a12f2e85d1a8f4ebedc70c65ec88c9509d0f5d392f9`. New languages use the immutable snapshot `2026-09-15T074500Z`; existing source pins and language manifest entries are preserved. All 15 published compressed source files were downloaded and SHA256-matched against the reviewed local copies.

## Generated output

These counts include inflections, spelling variants and Chinese/Japanese cross-reference entries; they are not lemma counts. Exact duplicate records are removed. Published Kaikki website counts describe a different, postprocessed dataset.

| Language | Records | Distinct spellings | Download MiB | Installed SQLite MiB |
|---|---:|---:|---:|---:|
| Arabic (`ar`) | 36,501 | 26,627 | 30.3 | 102.4 |
| Chinese (`zh`) | 318,312 | 299,054 | 128.8 | 973.0 |
| Japanese (`ja`) | 157,062 | 134,370 | 31.9 | 114.3 |
| Asturian (`ast`) | 34,899 | 33,912 | 3.7 | 17.9 |
| Navajo (`nv`) | 25,192 | 24,842 | 2.5 | 12.8 |
| Albanian (`sq`) | 24,163 | 22,889 | 6.0 | 21.4 |
| Telugu (`te`) | 22,564 | 21,122 | 3.4 | 16.7 |
| Swahili (`sw`) | 20,666 | 19,779 | 4.3 | 22.2 |
| Armenian (`hy`) | 22,010 | 20,169 | 13.0 | 53.2 |
| Thai (`th`) | 20,872 | 17,501 | 5.0 | 24.2 |
| Cebuano (`ceb`) | 19,007 | 16,161 | 2.5 | 9.8 |
| Tamil (`ta`) | 13,731 | 11,094 | 9.7 | 38.1 |
| Bengali (`bn`) | 11,158 | 9,918 | 4.1 | 16.2 |
| Punjabi (`pa`) | 10,559 | 9,359 | 2.9 | 12.1 |
| Urdu (`ur`) | 10,353 | 9,129 | 3.3 | 13.1 |

## Import and search changes

- Retain Chinese/Japanese character entries (Chinese 水 and 吃 are lexical definitions) and explicit soft-redirect targets. Keep source cross-references rather than inventing definitions or parts of speech.
- Preserve labelled readings, romanizations, Chinese pronunciation systems and Japanese kana readings in entry details; index these for search.
- Normalize optional Arabic/Urdu vocalization and tatweel while retaining hamza/madda and exact display spelling. Japanese search accepts kana width variants and katakana input for hiragana readings. Indic and Thai vowel marks remain significant.
- Clean bracketed romanization from Japanese conjugation spellings. Preserve the original grammatical tags.
- Retain native Latin-script Navajo entries incorrectly marked as nonstandard script upstream, including yáʼátʼééh. Reject the corrupt Chinese reading containing U+0006 without dropping its definition.
- Add a native/English-name language filter, interleave native names by pronunciation, display readings, collapse lengthy pronunciation lists, and prevent IME confirmation Enter from opening a result.

## Validation

- Full-source importer audit for every new language; all common-word probes present. Reviewed 12 deterministic output samples per language (180 total). This is a structure and content spot check, not native-speaker certification.
- All 15 final databases pass SQLite/FTS integrity, source-record equivalence, manifest size/hash, frequency, orphan form lookup and common-word search checks.
- 803 pipeline tests pass, including source-derived fixtures and real SQLite round trips for readings and inflections.
- Frontend: 195 tests pass, no type errors or warnings, lint and development-mode production build pass.
- Real Chrome/SQLite/OPFS: installed Arabic, Chinese, Japanese, Urdu, Punjabi and Thai; verified vocalized Arabic, Chinese characters and simplified cross-references, Japanese kana/romanization, native-script queries, reload persistence, and offline Chinese search. Mobile pages have no horizontal overflow. Checked light/dark mode, language filtering and pronunciation expansion.

## Limits

Chinese expands to approximately 973 MiB on disk. Private browsing may provide insufficient storage even though the compressed download is 129 MiB. Cross-reference entries require following their source target; they do not duplicate target definitions. The raw source includes historical, regional and spelling variants, and preserves those distinctions. Roughly 41,000 Arabic verb-form records have no structured gloss in the raw extract and remain excluded by the existing importer rule; forms attached to retained base entries remain searchable through the reverse form index.
