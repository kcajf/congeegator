# Etymology languages: complete classification and routing

Reviewed 2026-09-13 against Wiktionary's complete canonical etymology-only registry, with an independent semantics review and a separate inventory of all 25 generated Lexicoff dictionaries.

## Result

| Classification | Canonical codes | Behavior |
| --- | ---: | --- |
| Parent dictionary supported by Lexicoff | 80 | Open that dictionary when installed; otherwise link to its Wiktionary language section |
| Other full language | 610 | Keep external; never substitute a modern descendant |
| Reconstructed parent language | 26 | Keep external; never substitute a modern descendant |
| Translingual or undetermined parent | 5 | Keep external; no invented language dictionary |
| Family parent or unresolved parent | 0 | None in this revision; importer checks families and rejects unresolved roots |
| **Total etymology-only codes** | **721** | Every active record classified |

The 80 eligible codes span 16 of Lexicoff's 25 dictionaries. Eligibility is language-level: the source may still reference a word missing from the installed dictionary. Starred reconstructed terms never become local lemma links, including Proto-Romance, whose containment ultimately reaches Latin.

Wiktionary also defines **11 legacy code aliases**. These are applied before following containment. Eight occur in our dictionaries. They are distinct from the language-name aliases inside records, which are not guaranteed unique.

The [complete classification CSV](etymology-languages.csv) includes every code, name, immediate parent, ultimate entry language, routing class and full containment chain. [Independent semantics review](etymology-language-semantics.md). [Observed data audit](etymology-language-usage.md) and [all observed code strings](etymology-language-usage.csv).

## What changed

The application now resolves the exact Wiktionary containment graph and checks whether its final dictionary is installed. It retains the original variety name in the etymology and link tooltip. External links use the parent language section, for example `#Latin`, while retaining explicit source anchors. Existing downloaded dictionaries immediately benefit; no bundle download or regeneration is needed for the alias fix.

Browser-verified: French **manger → manducāre** now opens **/la/manduco** and shows the Latin verb's Classical and Late Latin senses. Middle French **manger** and Old French **mengier** remain external.

Other useful examples: `la-eme → la-med → la`, `frc → fr-lou → fr`, `en-GB-NIR → en-uls → en`, and `roa-oit → it`. Do not infer a rule from prefixes: `itc-ola` is an Old Latin variety, and `pld` (Polari) belongs under English.

Historical counterexamples matter: `gkm` (Byzantine Greek) and Koine Greek resolve to **Ancient Greek**, not modern Greek. Law French resolves to **Old French**, not French. Old/Middle English, Old/Middle French, Old/Middle High German, and Norwegian/Bokmål/Nynorsk remain distinct full languages. The graph follows containment, not linguistic descent.

The source-data audit also found 2,609 links bearing `+…` template instructions incorrectly extracted from `surf` dispatchers. Their varying argument layouts cannot safely be treated as ordinary compounds. The extractor now skips these unsupported dispatchers, and the text renderer filters them in existing bundles while preserving the prose. Multi-language codes (3,110 links) remain external and are not forced into one installed language. Blank-language links (1,495) commonly preserve explicit source anchors; blank does not by itself mean broken extraction.

## All varieties eligible for installed dictionaries

| Entry dictionary | Count | Varieties |
| --- | ---: | --- |
| Catalan (`ca`) | 1 | Valencian (`ca-val`) |
| Czech (`cs`) | 1 | Early Modern Czech (`cs-ear`) |
| German (`de`) | 5 | Austrian German (`de-AT`); Viennese German (`de-AT-vie`); Switzerland German (`de-CH`); Baltic German (`de-bal`); Early New High German (`de-ear`) |
| Greek (`el`) | 5 | Cretan Greek (`el-crt`); Cypriot Greek (`el-cyp`); Kaliarda (`el-kal`); Katharevousa (`el-kth`); Paphian Greek (`el-pap`) |
| English (`en`) | 20 | Australian English (`en-AU`); Canadian English (`en-CA`); British English (`en-GB`); Northern Irish English (`en-GB-NIR`); Scottish English (`en-GB-SCT`); Welsh English (`en-GB-WLS`); Hong Kong English (`en-HK`); Irish English (`en-IE`); Manx English (`en-IM`); Indian English (`en-IN`); North American English (`en-NNN`); New Zealand English (`en-NZ`); American English (`en-US`); California English (`en-US-CA`); South African English (`en-ZA`); Australian Aboriginal English (`en-aae`); Early Modern English (`en-ear`); Geordie (`en-geo`); Ulster English (`en-uls`); Polari (`pld`) |
| Spanish (`es`) | 13 | Rioplatense Spanish (`es-AR`); Bolivian Spanish (`es-BO`); Chilean Spanish (`es-CL`); Colombian Spanish (`es-CO`); Cuban Spanish (`es-CU`); Mexican Spanish (`es-MX`); Peruvian Spanish (`es-PE`); Philippine Spanish (`es-PH`); Puerto Rican Spanish (`es-PR`); United States Spanish (`es-US`); Venezuelan Spanish (`es-VE`); Early Modern Spanish (`es-ear`); Lunfardo (`es-lun`) |
| French (`fr`) | 6 | Canadian French (`fr-CA`); Swiss French (`fr-CH`); Acadian French (`fr-aca`); Louisiana French (`fr-lou`); Missouri French (`fr-mis`); Cajun French (`frc`) |
| Italian (`it`) | 2 | Switzerland Italian (`it-CH`); Old Italian (`roa-oit`) |
| Latin (`la`) | 15 | Archaic Latin (`itc-ala`); Lanuvian (`itc-lan`); Old Latin (`itc-ola`); Praenestine (`itc-pra`); African Romance (`la-afr`); Classical Latin (`la-cla`); Contemporary Latin (`la-con`); Ecclesiastical Latin (`la-ecc`); Early Medieval Latin (`la-eme`); Late Latin (`la-lat`); Medieval Latin (`la-med`); New Latin (`la-new`); Renaissance Latin (`la-ren`); Vulgar Latin (`la-vul`); Proto-Romance (`roa-pro`) |
| Dutch (`nl`) | 1 | Belgian Dutch (`nl-BE`) |
| Polish (`pl`) | 5 | Goral (`pl-gor`); Greater Polish (`pl-gre`); Lesser Polish (`pl-les`); Masovian Polish (`pl-mas`); Middle Polish (`zlw-mpl`) |
| Portuguese (`pt`) | 2 | Brazilian Portuguese (`pt-BR`); European Portuguese (`pt-PT`) |
| Romanian (`ro`) | 1 | Moldovan (`ro-MD`) |
| Russian (`ru`) | 1 | Middle Russian (`zle-mru`) |
| Turkish (`tr`) | 1 | Cypriot Turkish (`tr-CY`) |
| Ukrainian (`uk`) | 1 | Canadian Ukrainian (`uk-CA`) |

## Provenance and reproducibility

The application metadata contains the exact revision IDs, timestamps and permanent links for all five source modules. It is a factual projection attributed to Wiktionary contributors. The registry is 37.5 KB of JSON, about 10.1 KB gzipped; no dictionary bundle size increase is required.

- [Etymology varieties, revision 92528971](https://en.wiktionary.org/w/index.php?oldid=92528971)
- [Source module semantics](https://en.wiktionary.org/wiki/Module:etymology_languages/data)
- [Code alias and containment implementation](https://en.wiktionary.org/wiki/Module:languages)

`scripts/classify_etymology_languages.py` accepts saved MediaWiki API responses for the five named modules (see its docstring), strips Lua comments without executing Lua, validates every record against the separate canonical-name registry, follows every parent chain and emits the application registry plus the complete CSV. It fails for cycles, unresolved parents, unexpected record syntax, canonical-name disagreement or overlapping full/etymology code registries. Format its generated application JSON with the app's formatter.

The audit used the active Lua records, excluding seven commented-out proposals. This is why counting every textual `m[...]` assignment would incorrectly produce 728 instead of 721.

Wiktionary changes over time, so refresh this pinned metadata deliberately and review changed containment chains. One documentation example already disagrees with the current data: Suevic's parent is now Proto-West Germanic, not the West Germanic family. This review follows the data revision.

## Verification

The route tests traverse all 721 codes, all 11 legacy aliases, installed/uninstalled Latin, multi-hop chains, historical counterexamples, unknown codes, special parents and reconstructed terms. Existing dictionaries are covered by the renderer regression for malformed surface-analysis links. Pipeline tests cover multiple incompatible dispatcher layouts plus a valid ordinary `surf` compound.

The usage counts describe the generated dictionaries **before** the dispatcher filter added in this review. No full dictionary regeneration was needed for browser validation; existing bundles receive the defensive display fix immediately, and future pipeline generation omits those malformed link records.
