## Repository

A monorepo for two Wiktionary-powered language apps:

- **Congeegator** (`apps/congeegator/`) — verb conjugation PWA, https://congeegator.com.
- **Lexicoff** (`apps/lexicoff/`) — offline dictionary PWA covering all parts of speech, https://lexicoff.com.
- **Pipeline** (`pipeline/`) — shared Python pipeline processing English Wiktionary JSONL extracts from kaikki.org.

Both apps use SvelteKit 2, Svelte 5, TypeScript and Vite, and deploy to Cloudflare Workers. Each app has its own `package.json` and dependencies; there are no npm workspaces.

Language catalogues are independent: `pipeline/conjugation.py` defines `CONFIG`, and `pipeline/dictionary.py` defines `DICT_CONFIGS`. Do not infer one app's supported languages from the other.

## Commands

### Pipeline (repository root)

- Generate both apps: `pixi run generate`
- Generate a small development subset: `pixi run generate-dev`
- Generate only Lexicoff, preserving Congeegator output: `pixi run python -m pipeline.generate --app lexicoff`
- Generate only Congeegator: `pixi run python -m pipeline.generate --app congeegator`
- Tests: `pixi run test`
- Check manifest metadata: `pixi run python -m pipeline.generate --check-manifest-metadata`
- Pin source data: `pixi run pin-source-data`

The Pixi environment in `pixi.toml` currently targets Linux (`linux-64`).

### Frontends (run from the relevant app directory)

- Install dependencies: `npm ci`
- Development server: `npm run dev`
- Type check: `npm run check`
- Lint and formatting check: `npm run lint`
- Tests: `npm test`
- Build: `npm run build:dev`, `npm run build:staging`, `npm run build:prod`
- Deploy: `npm run deploy:staging`, `npm run deploy:prod`

Local deploy scripts regenerate data for both apps, upload the selected app's data, then build and deploy that app.

## Architecture

### Shared data pipeline

`pipeline/generate.py` processes one language at a time. A single pass over that language's source feeds the applicable conjugation and dictionary extractors. Dictionary output is written before moving to the next language to avoid retaining the whole catalogue in memory.

Generated data lives under `apps/<app>/r2_data/data/v1/<lang>-<hash>/`. Each app's `src/lib/data-manifest.json` identifies its language versions and download sizes. Both apps publish to the same R2 bucket, with content-hashed directories identifying their datasets.

Key pipeline files:

- `cache.py` — source versions, downloads and local caching.
- `wiktionary.py` — shared source entry, form and sense structures.
- `conjugation.py` — conjugation configurations and extraction.
- `dictionary.py` — dictionary configurations and extraction of senses, forms, pronunciation, etymology and links.
- `sqlite_output.py` — Lexicoff's SQLite schema, search indexes and database generation.
- `search.py` — Congeegator's prefix and gloss search index generation.
- `output.py` — JSON output, manifests and sitemap generation.
- `generate.py` — generation entry point; compresses Lexicoff databases with Zstandard.
- `pin_source_data.py` — source snapshot pinning.
- `audit_dictionary.py` — source and SQLite quality/integrity checks.

### Data delivery: server pages and client bundles

Preserve the distinction between server rendering and client data installation:

- **Server-rendered pages / SEO:** Congeegator's letter-based JSON chunks let a Cloudflare Worker fetch only the relevant portion of a language when rendering a page, including for search-engine crawlers. This keeps server-side data access efficient.
- **Client apps:** language downloads use complete bundles — `data.json` for Congeegator and `<lang>.sqlite.zst` for Lexicoff. Letter chunks are a server-rendering optimization, not the client language-download format. Keep full-bundle delivery as the client architecture.

Current fallback: Congeegator’s universal page loader also fetches a letter chunk in the browser when the requested verb is missing from IndexedDB or the local read fails. Thus chunks support server rendering and individual online lookups; they are not strictly server-only. `loadVerbIndex` similarly has a network fallback to `index.json`, though it currently has no callers.

### Congeegator: JSON and IndexedDB

R2 hosts the letter chunks for server-rendered verb pages, full `data.json` language bundles for client installation, and `index.json` word lists. The selected language syncs on app startup, language changes and reconnects, downloading the full bundle if its current version is not installed. Bundles are stored in IndexedDB through Dexie; search uses the generated index in IndexedDB metadata.

`VerbRecord` contains `name`, `nameNoDiacritics`, a flat `conjugation` array indexed by tense position, `freq` and `gloss`. The manifest supplies `tenseNames`, `tensePronouns` and `tenseGroups`.

Key files under `apps/congeegator/src/lib/`:

- `db.ts` — Dexie schema for verbs and metadata.
- `dataLoading.ts` — server data and IndexedDB loading.
- `search.ts`, `searchLang.svelte.ts` — search and language/index state.
- `sync.worker.ts`, `syncManager.svelte.ts` — offline downloads and orchestration.
- `i18n.svelte.ts`, `langTools.ts` — translations and language-specific presentation.

### Lexicoff: SQLite, WebAssembly and OPFS

Each language is a prebuilt SQLite database, distributed from R2 as `<lang>.sqlite.zst`. `download.worker.ts` streams the download, decompresses it with Zstandard and writes it to the browser's Origin Private File System (OPFS). Downloads run separately from queries.

`sqlite.worker.ts` runs the official `@sqlite.org/sqlite-wasm` build in a Web Worker. Its Sync Access Handle pool VFS (SAH Pool) imports and opens the local databases read-only, reading pages as needed rather than loading a whole database into memory. A Web Lock gives one tab ownership of the storage pool; waiting tabs can acquire it when the owner releases it.

SQLite stores entry fields and JSON-encoded structured details. `entries_fts` uses FTS5 for word prefixes, forms, glosses and phonetic search; a separate trigram FTS5 table supports fuzzy matching. `form_lookup` maps exact inflected forms to entries. Search ranks match quality and frequency, with language-aware normalization.

`DictRecord` includes `id`, `word`, `lang`, `pos`, `senses` and `freq`, with optional forms, pronunciation, etymology and linked details. Some dictionaries include additional form and pronunciation metadata. Multiple records can share a word; detail pages group records by part of speech. Normalized lookup keys are stored separately from display spelling.

Dictionary pages disable server rendering and load from installed local databases. A PWA service worker caches the app shell, scripts, styles and WebAssembly assets for offline navigation. Lexicoff's dictionary storage uses SQLite/OPFS, not Dexie/IndexedDB.

Key files under `apps/lexicoff/src/lib/`:

- `sqlite.worker.ts` — database installation, queries, search and deletion.
- `sqliteClient.svelte.ts` — worker messaging and reactive storage state.
- `download.worker.ts` — streaming download and decompression to OPFS.
- `syncManager.svelte.ts` — manual download/update orchestration.
- `searchLang.svelte.ts` — selected language and database readiness.
- `searchNormalization.ts`, `phonetic.ts` — query normalization and phonetic helpers.
- `types.ts` — dictionary records and manifest types.

The SQLite dependency is pinned and patched to preserve downloaded databases when pool initialization fails. `npm ci` applies the patch through `postinstall`; review `apps/lexicoff/patches/README.md` and the patch when upgrading SQLite. Do not call `removeVfs()` for ordinary shutdown: it deletes installed dictionaries.

### Routing and environment

- Congeegator `/[lang]/[verb]` — verb conjugation page.
- Lexicoff `/[lang]/[word]` — local dictionary page.
- Both apps: `/` homepage, `/[lang]` redirect to `/?lang={lang}`, `/app-shell` offline fallback, `/dev-r2-mock/[...file]` local data proxy.
- Each app's `dataUtils.ts` reads its manifest and constructs R2 URLs.
- `VITE_R2_URL` is `/dev-r2-mock` in development and points at R2 in staging/production. Local proxy data comes from the app's `r2_data/` directory.

## Source data and validation

Source snapshots are pinned in R2 under `source-data/<timestamp>/`. `pipeline/cache.py` defines the default `SOURCE_DATA_VERSION` and per-language overrides in `SOURCE_DATA_VERSIONS`. Partial updates preserve other languages' snapshots. Pinning splits the English extract across the union of both apps' language catalogues.

For a local source review without uploads or version changes:

```sh
pixi run pin-source-data --languages pt ca --output-dir /tmp/dictionary-source --no-upload
pixi run python -m pipeline.audit_dictionary --languages pt ca \
  --source-dir /tmp/dictionary-source --output /tmp/dictionary-audit.json
```

Pinning also accepts `--input-file` for a downloaded extract and `--source-sha256` to verify it. The source-pinning workflow supports publishing a reviewed snapshot through its `languages`, `version`, `source_sha256` and `publish_only` inputs.

Conjugation golden tests compare fixtures with `pipeline/tests/golden/conj/`. Regenerate intentionally with `pixi run pytest pipeline/tests/ --update-golden`. Dictionary and SQLite tests live alongside them in `pipeline/tests/`. Manifest checks compare both apps' committed metadata with their language configurations.

The current generation entry point writes Congeegator sitemaps into `apps/congeegator/static/`; it does not generate Lexicoff dictionary sitemaps.

## CI and deployment

- `ci-congeegator.yml` and `ci-lexicoff.yml` run frontend checks and pipeline validation for their configured PR paths. Consult the workflows for exact filters and commands.
- `deploy.yml` runs on matching pushes to `main` or manual dispatch. It regenerates both datasets, uploads them to R2, then builds and deploys both apps in parallel using fresh manifest artifacts. There is currently no per-app change-detection job or UI-only generation bypass.
- `pin-source-data.yml` provides scheduled and manual source updates, with a publish-only option. Consult its schedule and inputs before changing source-pinning behavior.

## Conventions

- Use Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`), not legacy `$:` reactive statements.
- Use `.svelte.ts` for runes outside components.
- Use relative imports within the Python `pipeline` package.
- Preserve each app’s download behavior: Congeegator automatically syncs the selected language; Lexicoff uses manual downloads through the homepage download manager.
- Keep Python and browser dictionary normalization consistent, including language-specific casing and script handling.
