# Independent audit: Wiktionary etymology-language routing

Reviewed official Wiktionary documentation and implementation on 2026-09-13. This report checks semantics and representative dangerous cases; the accompanying generated inventory should provide exhaustive code counts and classifications. No application code was changed by this reviewer.

## Routing rule

Resolve explicit **code aliases**, then follow **containment parents** until reaching the full object. `getFullCode()` supplies its code and `getFullName()` its canonical name. Full languages have entry language headings; an etymology variety may have several containment levels. Keep the original variety name for display. Never infer this relation from a code prefix, the word “Old”, `ancestors`, or a genealogical family field. [Module:etymology languages](https://en.wiktionary.org/wiki/Module:etymology_languages)

A full object is not necessarily a usable local dictionary language. Wiktionary distinguishes language/family and regular/reconstructed/appendix-constructed types. The application should choose a local route only when the resolved full **language** is one of its supported dictionaries and is installed. Historical full languages remain separate. [Module:languages](https://en.wiktionary.org/wiki/Module:languages#Language:getTypes)

## Concrete boundary cases

These chains come from the current data revision **92528971**, dated 2026-09-09. “Local” means eligible when that dictionary is installed. [Pinned etymology-language data](https://en.wiktionary.org/w/index.php?title=Module:etymology_languages/data&oldid=92528971)

| Code | Containment chain | Route |
| --- | --- | --- |
| `la-eme` | `la-med → la` | Latin |
| `la-afr` | `roa-pro → la-lat → la` | Latin; preserve African Romance label |
| `frc` | `fr-lou → fr` | French |
| `roa-oit` | `it` | Italian |
| `de-AT-vie` | `de-AT → de` | German |
| `en-GB-SCT` | `en-GB → en` | English |
| `xno-law` | `xno → fro-nor → fro` | Old French externally; never French |
| `ang-nor` | `ang-ang → ang` | Old English externally; never English |
| `gkm`, `grc-koi` | `grc` | Ancient Greek externally; never Greek |
| `el-kth` | `el` | Greek, despite its Byzantine Greek ancestor |
| `gem-sue`, `frk` | `gmw-pro` | Reconstructed parent; no modern German route |
| `qsb-grc` | `und` | No fabricated Greek destination |

The data documentation's illustrative `gem-sue → gmw` example is **stale**: the current record says `gmw-pro`. This is a concrete reason to use the pinned data rather than copy examples from prose documentation. [Same data source](https://en.wiktionary.org/w/index.php?title=Module:etymology_languages/data&oldid=92528971)

Norwegian `no`, Nynorsk `nn`, and Bokmål `nb` are separate full-language records. Having only Bokmål installed does not authorize mapping `no` or `nn` to it. [Full-language data](https://en.wiktionary.org/wiki/Module:languages/data/2)

## Aliases, families, and anchors

Current `Module:languages` code uses `Module:languages/data.aliases` to normalize codes before lookup. Individual records' `aliases` fields instead contain **names**, and those names are explicitly not guaranteed unique. Build canonical-code routing from the former; do not turn every name synonym into an unconditional global route. A complete import should record unresolved or colliding names separately. [Module:languages](https://en.wiktionary.org/wiki/Module:languages#Language:getAliases)

Family objects have their own full-object methods; family ancestry must not be confused with language containment. Current family data includes `ira-old`, `ira-mid`, and `inc-old`. These represent groupings, not substitute dictionaries. A family classification should remain external or unlinked, without selecting a descendant language. [Module:families](https://en.wiktionary.org/wiki/Module:families#Family:getFull), [family data](https://en.wiktionary.org/wiki/Module:families/data)

Wiktionary's ordinary link builder defaults the fragment to **`getFullName()`**, so Medieval Latin links use `#Latin`, not `#Medieval_Latin`. Explicit fragments are preserved. `und` gets no invented `#Undetermined` section; Appendix and Reconstruction targets have separate handling. Keep the source variety label while using the full name for the destination section. [Module:links](https://en.wiktionary.org/wiki/Module:links)

## Implementation checks recommended

These are engineering recommendations derived from the preceding rules:

- Pin source revision IDs; keep code aliases, containment, names, and object type separate.
- Detect parent cycles, missing parents, and unresolved code aliases; retain safe external behavior for unresolved records.
- Test multi-hop chains and historical counterexamples above, plus installed/uninstalled parent behavior.
- Preserve explicit anchors and reconstructed-term handling before considering a local route.
- Do not equate a correct language route with proof that a word exists locally: canonical page spelling, diacritics, missing source entries, and extraction filters remain separate concerns.

## Import verification follow-up

The implementing agent's complete active-data classification reports **721 canonical etymology-only records**: 80 terminate in the 25 supported dictionaries, 610 in other full languages, 26 in proto-language roots, and 5 in `mul`/`und`. None currently terminates in a family. These are inventory results supplied by that importer, not independently recounted in this semantics review. Family-safe handling remains a forward-compatible requirement.

`lzh` is a full record named **Classical Chinese**. The variety `lzh-lit` must retain its distinct display name but resolve its section through `lzh`. The main language loader checks full-language data before the etymology fallback, so an import must retain that precedence for duplicate codes. [Full `lzh` record](https://en.wiktionary.org/w/index.php?title=Module:languages/data/3/l&oldid=92301794), [lookup implementation](https://en.wiktionary.org/wiki/Module:languages#export.getByCode)
