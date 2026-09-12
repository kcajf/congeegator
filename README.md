Source code for [congeegator.com](https://congeegator.com) and [lexicoff.com](https://lexicoff.com) (WIP).

Lexicoff supports 25 dictionaries with definitions from English Wiktionary. Its
language catalogue is independent of Congeegator's conjugation configurations.

Generate only Lexicoff, preserving Congeegator's output:

```sh
pixi run python -m pipeline.generate --app lexicoff
```

Generation streams the pinned source and writes one dictionary database at a
time. Galician, Esperanto, and Latin have no corpus in the current `wordfreq`
package; they use neutral frequency scores rather than another language's ranks.

Source pinning downloads the English extract once and splits the union of both
apps' language catalogues. Partial updates use independent immutable timestamps
in `SOURCE_DATA_VERSIONS`, leaving other languages' snapshots unchanged. For a
local review without uploads or version changes:

```sh
pixi run pin-source-data --languages pt ca --output-dir /tmp/dictionary-source --no-upload
pixi run python -m pipeline.audit_dictionary --languages pt ca \
  --source-dir /tmp/dictionary-source --output /tmp/dictionary-audit.json
```

The pinning command also accepts `--input-file` for an already downloaded raw
extract and `--source-sha256` to verify the exact reviewed compressed source.
The Pin source data workflow can publish that snapshot using its `languages`,
`version`, `source_sha256`, and `publish_only` inputs, without deploying either app.
