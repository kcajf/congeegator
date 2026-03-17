# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is this repo?

A monorepo for Wiktionary-powered language apps. Currently contains:

- **Congeegator** (`apps/congeegator/`) — A verb conjugation PWA (SvelteKit 2 / Svelte 5, Cloudflare Workers). Supports French, Greek, German, Spanish, Italian, and English.
- **Pipeline** (`pipeline/`) — A shared Python data pipeline that processes Wiktionary JSONL data from kaikki.org.

## Directory Structure

```
/
├── pipeline/              # Shared Python data pipeline
│   ├── cache.py           # CacheManager, SOURCE_DATA_VERSION
│   ├── wiktionary.py      # Entry, Form, Sense structs
│   ├── utils.py           # strip_diacritics, to_phonetic_el, _orjson_dump
│   ├── gloss.py           # extract_gloss, _is_junk_gloss
│   ├── search.py          # build_search_index, build_gloss_index
│   ├── output.py          # write_language_data, write_data_manifest, generate_sitemaps
│   ├── conjugation.py     # LanguageConfig, TenseConfig, FormMatcher, all 6 lang configs, extract_conjugation()
│   ├── dictionary.py      # (Phase B: Lexicoff dictionary extraction)
│   ├── generate.py        # main() — entry point for data generation
│   └── tests/
│       ├── conftest.py
│       ├── test_conjugation.py  # verb golden tests
│       ├── test_shared.py       # phonetic tests
│       ├── test_search_index.py # search index tests
│       ├── fixtures/            # JSONL test data
│       └── golden/conj/        # golden files for conjugation
├── apps/
│   └── congeegator/       # SvelteKit verb conjugation app
│       ├── src/
│       ├── package.json
│       ├── wrangler.jsonc
│       └── ...
├── pixi.toml              # Python environment
├── pin_source_data.py     # Source data pinning script
└── .github/workflows/
```

## Commands

### Pipeline (run from repo root)
- **Generate data:** `pixi run generate` (or `pixi run generate-dev` for small subset)
- **Run pipeline tests:** `pixi run test`
- **Pin source data:** `pixi run pin-source-data`

### Congeegator frontend (run from `apps/congeegator/`)
- **Dev server:** `npm run dev`
- **Build:** `npm run build:prod` (production), `npm run build:staging`, `npm run build:dev`
- **Type check:** `npm run check`
- **Lint:** `npm run lint` (prettier + eslint)
- **Frontend tests:** `npm test`
- **Deploy:** `npm run deploy:staging`, `npm run deploy:prod`
- **Upload data to R2:** `npm run r2-upload:staging`, `npm run r2-upload:prod`

## Architecture

### Data Flow

1. **`pipeline/generate.py`** downloads raw Wiktionary JSONL data, extracts verb conjugations per language config, builds search indices, and writes output to `apps/congeegator/r2_data/data/v1/<lang>-<hash>/`. Also generates `apps/congeegator/src/lib/data-manifest.json`.
2. **R2** hosts the processed data (verb JSON chunks, full `data.json` bundles, and `index.json` verb lists).
3. **SvelteKit SSR** (Cloudflare Worker) fetches verb data from R2 chunks for initial page loads.
4. **Client-side sync** (`src/lib/sync.worker.ts`) downloads the full language bundle into IndexedDB for offline use.
5. **Search** (`src/lib/searchLang.svelte.ts`) uses a prefix-based search index stored in IndexedDB metadata.

### Key Frontend Files (in `apps/congeegator/`)

- `src/lib/types.ts` — Core types: `VerbRecord`, `DataManifest`, `SearchIndex`
- `src/lib/db.ts` — Dexie database schema (verbs + metadata tables)
- `src/lib/dataUtils.ts` — Manifest access, R2 URL construction
- `src/lib/i18n.svelte.ts` — Tense name translation
- `src/lib/langTools.ts` — Language-specific display logic

### Routing

- `/` — redirects/landing
- `/[lang]` — verb list for a language
- `/[lang]/[verb]` — conjugation table for a specific verb
- `/app-shell` — prerendered PWA shell for offline navigation fallback
- `/dev-r2-mock/[...file]` — dev-only proxy serving `r2_data/` files locally

### Environment

- `VITE_R2_URL` — base URL for conjugation data. Set to `/dev-r2-mock` in dev, real R2 URLs in `.env.staging` and `.env.production`.

## Data Pipeline

### Source Data Pinning

Source data from kaikki.org is pinned at a timestamp-keyed path in R2 (`source-data/<timestamp>/`). The version is controlled by `SOURCE_DATA_VERSION` in `pipeline/cache.py`. This ensures reproducible builds.

### Golden Tests

`pipeline/tests/test_conjugation.py` runs `extract_conjugation()` against committed fixture verbs and compares output to golden files in `pipeline/tests/golden/conj/`. To regenerate: `pixi run pytest pipeline/tests/ --update-golden`.

### CI/Deploy Flow

- **PR CI:** lint, typecheck, build, golden tests (`pixi run test`), manifest metadata check
- **Merge to main:** generate data → upload to R2 → build → deploy
- **Manual deploy:** `npm run deploy:prod` (from `apps/congeegator/`)

### Manifest Metadata Check

`pixi run python -m pipeline.generate --check-manifest-metadata` verifies that the committed `data-manifest.json` matches current `LanguageConfig` definitions. Runs in CI on every PR.

## Conventions

- Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) throughout — no legacy `$:` reactive statements
- `.svelte.ts` extension for files using Svelte runes outside components
- No npm workspaces — each app has its own `package.json` and `node_modules`
- Pipeline modules use relative imports within the `pipeline/` package
