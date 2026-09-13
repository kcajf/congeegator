# Congeegator & Lexicoff

Two Wiktionary-powered language apps:

- **[Congeegator](https://congeegator.com)** — verb conjugation tables with downloadable languages for offline use.
- **[Lexicoff](https://lexicoff.com)** — an offline dictionary with definitions, inflected forms, pronunciation and etymology.

## How they work

Both apps use **SvelteKit, Svelte and TypeScript**, run as installable progressive web apps, and are hosted on **Cloudflare Workers**. A shared **Python pipeline** processes English Wiktionary data from [kaikki.org](https://kaikki.org), with generated datasets distributed through **Cloudflare R2**.

Data delivery has two purposes: **small letter-based chunks for efficient server-rendered SEO pages**, and **complete language bundles for client apps**. Congeegator's Cloudflare Worker fetches the relevant letter chunk to render a page for visitors and crawlers. Congeegator automatically syncs the selected language as a full bundle, stored in **IndexedDB using Dexie**. Its browser page loader can also fetch an individual letter chunk when a verb is unavailable locally.

Lexicoff lets users manually download one **Zstandard-compressed SQLite database per language**. **SQLite runs in the browser through WebAssembly**, reading downloaded files from **OPFS**, the browser's private filesystem. **FTS5** indexes support prefix, inflection, definition and phonetic searches, with a trigram index for fuzzy matching. Separate background workers handle downloads and queries. Once a language is installed, lookups work offline.

## Repository

```text
apps/congeegator/   Conjugation app
apps/lexicoff/      Offline dictionary
pipeline/          Shared data extraction and database generation
```

Each app has its own npm dependencies and independent language catalogue.

## Development

Install dependencies and start either app from its directory:

```sh
cd apps/lexicoff # or apps/congeegator
npm ci
npm run dev
```

Local dictionary/conjugation data must be generated separately. From the repository root, use [Pixi](https://pixi.sh) to generate a development subset:

```sh
pixi run generate-dev
```

The configured Pixi environment currently targets Linux. Development apps serve generated files from their `r2_data/` directory through `/dev-r2-mock`.

For full datasets, run `pixi run generate`. To generate just Lexicoff:

```sh
pixi run python -m pipeline.generate --app lexicoff
```

## Checks

From either app directory:

```sh
npm run check
npm run lint
npm test
npm run build:staging
```

From the repository root:

```sh
pixi run test
pixi run python -m pipeline.generate --check-manifest-metadata
```

See [AGENTS.md](AGENTS.md) for architecture details, source-pinning instructions and deployment behavior.
