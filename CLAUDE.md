# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is this repo?

A monorepo for Wiktionary-powered language apps. Contains:

- **Congeegator** (`apps/congeegator/`) — A verb conjugation PWA. SvelteKit 2 / Svelte 5, Cloudflare Workers. https://congeegator.com
- **Lexicoff** (`apps/lexicoff/`) — An offline dictionary PWA (all parts of speech). SvelteKit 2 / Svelte 5, Cloudflare Workers. https://lexicoff.com
- **Pipeline** (`pipeline/`) — A shared Python data pipeline that processes Wiktionary JSONL data from kaikki.org. One loop over source data produces both conjugation and dictionary output.

Supported languages are configured in `pipeline/conjugation.py` (`CONFIG`) and `pipeline/dictionary.py` (`DICT_CONFIGS`).

## Directory Structure

```
/
├── pipeline/              # Shared Python data pipeline
│   ├── cache.py           # CacheManager, SOURCE_DATA_VERSION
│   ├── wiktionary.py      # Entry, Form, Sense structs (maximal, shared by both extractors)
│   ├── utils.py           # strip_diacritics, to_phonetic_el, _orjson_dump
│   ├── gloss.py           # extract_gloss, _is_junk_gloss
│   ├── search.py          # build_search_index (congeegator, with merged gloss index)
│   ├── output.py          # write_language_data, write_data_manifest, generate_sitemaps
│   ├── conjugation.py     # LanguageConfig, TenseConfig, FormMatcher, all 6 lang configs, extract_conjugation()
│   ├── dictionary.py      # DictLanguageConfig, process_dict_entry, extract_senses/gender/forms/pronunciation/etymology
│   ├── generate.py        # main() — single entry point, one loop, two outputs
│   ├── pin_source_data.py # Download & pin latest Wiktionary source data
│   └── tests/
│       ├── test_conjugation.py  # verb golden tests
│       ├── test_shared.py       # phonetic tests
│       ├── test_search_index.py # search index tests
│       ├── fixtures/            # JSONL test data
│       └── golden/conj/         # golden files for conjugation
├── apps/
│   ├── congeegator/       # SvelteKit verb conjugation app
│   │   ├── src/
│   │   ├── package.json
│   │   ├── wrangler.jsonc
│   │   └── ...
│   └── lexicoff/          # SvelteKit dictionary app
│       ├── src/
│       ├── package.json
│       ├── wrangler.jsonc
│       └── ...
├── pixi.toml              # Python environment
└── .github/workflows/
    ├── ci-congeegator.yml
    ├── ci-lexicoff.yml
    ├── deploy-congeegator.yml
    ├── deploy-lexicoff.yml
    └── pin-source-data.yml
```

## Commands

### Pipeline (run from repo root)
- **Generate data:** `pixi run generate` (or `pixi run generate-dev` for small subset). Outputs to both `apps/congeegator/r2_data/` and `apps/lexicoff/r2_data/`.
- **Run pipeline tests:** `pixi run test`
- **Pin source data:** `pixi run pin-source-data`
- **Check manifests:** `pixi run python -m pipeline.generate --check-manifest-metadata`

### Congeegator frontend (run from `apps/congeegator/`)
- **Dev server:** `npm run dev`
- **Build:** `npm run build:prod`, `npm run build:staging`, `npm run build:dev`
- **Type check:** `npm run check`
- **Lint:** `npm run lint` (prettier + eslint)
- **Frontend tests:** `npm test`
- **Deploy:** `npm run deploy:staging`, `npm run deploy:prod`

### Lexicoff frontend (run from `apps/lexicoff/`)
- Same commands as congeegator: `npm run dev`, `npm run check`, `npm run lint`, `npm run build:prod`, etc.

## Architecture

### Data Flow

1. **`pipeline/generate.py`** downloads raw Wiktionary JSONL data and loops over it once per language. For each entry:
   - If it's a verb with conjugation data → `extract_conjugation()` → congeegator output
   - If it's a valid dictionary entry (any POS) → `process_dict_entry()` → lexicoff output
2. Output is written to `apps/*/r2_data/data/v1/<lang>-<hash>/` with per-app `data-manifest.json`.
3. **R2** hosts the processed data (JSON chunks by first letter, full `data.json` bundles, `index.json` word lists). Both apps use the same R2 bucket.
4. **SvelteKit SSR** (Cloudflare Worker) fetches chunk data from R2 for initial page loads.
5. **Client-side sync** (Web Worker) downloads the full language bundle into IndexedDB for offline use.
6. **Search** uses a prefix-based search index stored in IndexedDB metadata.

### Congeegator Data Model

Each verb produces a `VerbRecord` with `name`, `nameNoDiacritics`, `conjugation` (flat array indexed by tense position), `freq`, `gloss`. Manifest includes `tenseNames`, `tensePronouns`, `tenseGroups` per language.

### Lexicoff Data Model

Each dictionary entry (`DictRecord`) has `word`, `wordNoDiacritics`, `pos`, `senses[]` (gloss, examples, tags), `freq`, and optional `gender`, `forms`, `pronunciation`, `etymology`. Same word with multiple POS = separate records with different IDs. Detail page groups by POS.

### Key Frontend Files

**Congeegator** (`apps/congeegator/src/lib/`):
- `types.ts` — `VerbRecord`, `DataManifest` (with tense metadata)
- `db.ts` — Dexie schema (verbs + metadata)
- `i18n.svelte.ts` — Tense name translation
- `langTools.ts` — Language-specific display logic (e.g. French pronoun elision)

**Lexicoff** (`apps/lexicoff/src/lib/`):
- `types.ts` — `DictRecord`, `DictSense`, `DataManifest` (simpler, no tense metadata)
- `db.ts` — Dexie schema (entries + metadata)
- `search.ts` — Prefix search with phonetic (Greek) and gloss matching

**Shared patterns** (both apps have their own copies):
- `dataUtils.ts` — Manifest access, R2 URL construction
- `dataLoading.ts` — SSR + IndexedDB hybrid loading
- `sync.worker.ts` — Web Worker for offline bundle download
- `syncManager.svelte.ts` — Sync orchestration with toasts
- `searchLang.svelte.ts` — Language selection state + search index loading

### Routing

**Congeegator:**
- `/[lang]/[verb]` — conjugation table for a specific verb

**Lexicoff:**
- `/[lang]/[word]` — dictionary entry page (all POS for that word)

**Both apps:**
- `/` — homepage
- `/[lang]` — redirects to `/?lang={lang}`
- `/app-shell` — prerendered PWA shell for offline navigation fallback
- `/dev-r2-mock/[...file]` — dev-only proxy serving `r2_data/` files locally

### Environment

- `VITE_R2_URL` — base URL for data. Set to `/dev-r2-mock` in dev (`.env`), real R2 URLs in `.env.staging` and `.env.production`. Both apps point to the same R2 bucket.

## Data Pipeline

### Source Data Pinning

Source data from kaikki.org is pinned at a timestamp-keyed path in R2 (`source-data/<timestamp>/`). The version is controlled by `SOURCE_DATA_VERSION` in `pipeline/cache.py`. This ensures reproducible builds.

### Golden Tests

`pipeline/tests/test_conjugation.py` runs `extract_conjugation()` against committed fixture verbs and compares output to golden files in `pipeline/tests/golden/conj/`. To regenerate: `pixi run pytest pipeline/tests/ --update-golden`.

### Sitemaps

Generated into `apps/*/static/`. Large sitemaps (>40K URLs) are automatically split into numbered parts (e.g. `sitemap-en-1.xml`, `sitemap-en-2.xml`). English dictionary has ~700K entries = ~18 sitemap files.

### CI/Deploy Flow

- **PR CI:** `ci-congeegator.yml` and `ci-lexicoff.yml` with path filters on `apps/<app>/**` and `pipeline/**`. Runs lint, typecheck, build, pipeline golden tests, manifest metadata check.
- **Merge to main:** `deploy-congeegator.yml` and `deploy-lexicoff.yml` each generate data (pipeline runs in both — to be optimized), upload to R2, build, and deploy.
- **Manual deploy:** `npm run deploy:prod` from the app directory.
- **Pin source data:** Monthly cron (`pin-source-data.yml`). Downloads latest data, updates `SOURCE_DATA_VERSION`, regenerates output, opens PR.

### Manifest Metadata Check

`pixi run python -m pipeline.generate --check-manifest-metadata` verifies both congeegator and lexicoff `data-manifest.json` files match current config definitions. Runs in CI on every PR.

## Conventions

- Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) throughout — no legacy `$:` reactive statements
- `.svelte.ts` extension for files using Svelte runes outside components
- No npm workspaces — each app has its own `package.json` and `node_modules`
- Pipeline modules use relative imports within the `pipeline/` package
- No auto-sync — downloads are manual via the homepage download manager
