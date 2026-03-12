# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Congeegator?

A verb conjugation web app (PWA) built with SvelteKit 2 / Svelte 5, deployed to Cloudflare Workers. Currently supports French and Greek. Conjugation data is sourced from Wiktionary via a Python data pipeline, stored in Cloudflare R2, and cached client-side in IndexedDB (via Dexie).

## Commands

- **Dev server:** `npm run dev` (uses `.env` which points R2 URL to local mock at `/dev-r2-mock`)
- **Build:** `npm run build:prod` (production), `npm run build:staging`, `npm run build:dev`
- **Type check:** `npm run check`
- **Lint:** `npm run lint` (prettier + eslint)
- **Deploy:** `npm run deploy:staging`, `npm run deploy:prod` (builds then runs wrangler)
- **Data pipeline:** `python data_processing.py` (requires pixi environment: `pixi run python data_processing.py`). Use `--dev` flag for a small subset. Outputs to `r2_data/` and writes `src/lib/data-manifest.json`. Source data is always fetched from the pinned R2 version.
- **Upload data to R2:** `npm run r2-upload:staging`, `npm run r2-upload:prod` (uses rclone)

## Architecture

### Data Flow

1. **`data_processing.py`** downloads raw Wiktionary JSONL data, extracts verb conjugations per language config (`FR_CONFIG`, `EL_CONFIG`), builds a search index, and writes output to `r2_data/data/v1/<lang>-<hash>/`. It also generates `src/lib/data-manifest.json` containing per-language metadata (tense names, pronouns, tense groups, content hash).
2. **R2** hosts the processed data (individual verb JSON files, full `data.json` bundles, and `index.json` verb lists).
3. **SvelteKit SSR** (Cloudflare Worker) fetches individual verb data from R2 for initial page loads (`src/lib/dataLoading.ts`).
4. **Client-side sync** (`src/lib/sync.worker.ts`) runs in a Web Worker, downloads the full language bundle (`data.json`) into IndexedDB for offline use. Coordinated by `src/lib/syncManager.svelte.ts`. Uses `navigator.locks` to prevent concurrent syncs.
5. **Search** (`src/lib/searchLang.svelte.ts`) uses a prefix-based search index stored in IndexedDB metadata, resolving matching verb IDs via bulk Dexie lookups.

### Key Files

- `src/lib/types.ts` — Core types: `VerbRecord`, `DataManifest`, `SearchIndex`
- `src/lib/db.ts` — Dexie database schema (verbs + metadata tables)
- `src/lib/dataUtils.ts` — Manifest access, R2 URL construction
- `src/lib/i18n.svelte.ts` — Simple i18n using Svelte 5 `$state`, dictionaries in `src/lib/messages/{en,fr,el}.json`
- `src/lib/langTools.ts` — Language-specific display logic (e.g., French pronoun elision)
- `src/params/lang.ts` — SvelteKit param matcher validating language codes against manifest

### Routing

- `/` — redirects/landing
- `/[lang]` — verb list for a language (triggers background sync)
- `/[lang]/[verb]` — conjugation table for a specific verb
- `/app-shell` — prerendered PWA shell for offline navigation fallback
- `/dev-r2-mock/[...file]` — dev-only proxy serving `r2_data/` files locally

### Environment

- `VITE_R2_URL` — base URL for conjugation data. Set to `/dev-r2-mock` in dev (`.env`), real R2 URLs in `.env.staging` and `.env.production`.

## Data Pipeline & Testing

### Source Data Pinning

Source data from kaikki.org is pinned at a timestamp-keyed path in R2 (`source-data/<timestamp>/`). The version is controlled by `SOURCE_DATA_VERSION` in `data_processing.py` (format: `2026-03-12T143000Z`). This ensures reproducible builds — the data pipeline always fetches from the pinned version. Source data is cached locally in `cache/<version>/`.

### Updating Source Data

Run `pixi run pin-source-data` (or trigger the **Pin source data** GitHub Action) to:

1. Download and filter latest data from kaikki.org
2. Upload filtered `.zst` files to R2 at a new timestamp-keyed path
3. Update `SOURCE_DATA_VERSION` in `data_processing.py`
4. Regenerate `r2_data/` and `data-manifest.json`

The GitHub Action runs monthly and opens a PR automatically. When running locally, review golden test diffs (`pixi run test`), update golden files if needed (`pixi run pytest tests/ --update-golden`), and commit.

### Golden Tests

`tests/test_data_processing.py` runs `process_entry()` against committed fixture verbs and compares output to golden files in `tests/golden/`. To regenerate after intentional changes: `pixi run pytest tests/ --update-golden`.

### CI/Deploy Flow

- **PR CI:** lint, typecheck, build, golden tests (`pixi run test`), manifest metadata check
- **Merge to main:** generate data (fetches pinned source from R2) → upload to R2 → build → deploy
- **Manual deploy:** `npm run deploy:prod` runs the full pipeline locally (generate → R2 upload → build → deploy)

### Manifest Metadata Check

`python data_processing.py --check-manifest-metadata` verifies that the committed `data-manifest.json` structural metadata (tenseNames, tensePronouns, tenseGroups) matches current `LanguageConfig` definitions. Runs in CI on every PR.

## Conventions

- Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) throughout — no legacy `$:` reactive statements
- `.svelte.ts` extension for files using Svelte runes outside components
- Conjugation data is a flat array indexed by tense position (matching `tenseNames` in the manifest), not keyed by tense name
- Adding a new language requires: adding a `LanguageConfig` in `data_processing.py`, adding i18n translations, and re-running the data pipeline
