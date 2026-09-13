# Observed etymology language usage

Audit date: 2026-09-13. This inventory covers **all 25 final generated Lexicoff dictionaries**, selected by the hashes in `apps/lexicoff/src/lib/data-manifest.json` at audit time. It counts **2,032,256 serialized etymology links** across **7,632,607 dictionary records**, using **2,270 distinct raw language strings**. The companion `etymology-language-usage.csv` contains one row for every observed string, including invalid markers and the empty string.

This is an observed-data report. The separate complete registry classification covers etymology-only language codes that do not appear in these databases as well.

## Scope and counting method

- Opened each final SQLite database read-only after decompressing its manifest-selected `.sqlite.zst` file into a temporary directory. Temporary decompressions were removed after use. No dictionary data or application code was changed by this audit.
- Counted each item of `details.etymologyLinks` once. Separate source records—including homographs, parts of speech and etymologies—remain separate. A repeated target in separate source records contributes multiple links. `senses.links`, synonyms and other relation lists are outside this inventory.
- Compared observed language strings with the supplied official Wiktionary module snapshots: the code-to-canonical-name map, etymology-language classification, family definitions and core `export.aliases`. Etymology-only and family membership take precedence over the general code-name map.
- Registry inputs contained 8,246 code-name entries, 721 classified etymology-only entries, 1,238 family declarations and 11 core aliases. Their API snapshots were `/private/tmp/lexicoff-language-metadata.json` and `/private/tmp/lexicoff-language-core.json`; parent/root classifications came from `/private/tmp/lexicoff-etymology-classified.json`.
- Examples are the first up to three distinct source-language/source-word/target-word triples per observed string. The CSV preserves source record IDs, parts of speech, display labels and explicit anchors where present.
- The baseline databases still contain ambiguous groups and incorrectly extracted template markers. Their presence in this report does not endorse them as language codes or usable destinations. Current helper changes and future regeneration do not retroactively change these baseline counts.

## Observed classifications

| Classification | Distinct raw strings | Serialized links |
|---|---:|---:|
| Full language | 1,492 | 1,983,244 |
| Etymology-only language | 189 | 41,735 |
| Language family | 21 | 63 |
| Comma-separated language group | 540 | 3,110 |
| Surface-analysis template marker | 27 | 2,609 |
| Empty language / preserved-anchor fallback | 1 | 1,495 |
| **Total** | **2,270** | **2,032,256** |

**No otherwise-unrecognized language strings remain after official alias resolution.** All 540 comma-separated groups contain individually recognized registry members, but the combined string is not a single language code. The empty language value occurs on 1,495 links; source examples preserve anchors such as `pillar-pier-Latin` or `Etymology 2`, so it should not be treated as an inferred language.

## Etymology-only routing

| Classification in the complete registry | Observed raw strings | Links | Distinct canonical codes |
|---|---:|---:|---:|
| Parent language supported in Lexicoff | 62 | 27,287 | 57 |
| Parent language external to Lexicoff | 125 | 13,930 | 124 |
| Special category | 1 | 515 | 1 |
| Reconstructed ancestry | 1 | 3 | 1 |

**62 observed etymology code strings account for 27,287 links whose parent language is supported.** These represent 57 distinct canonical codes because five observed legacy Latin aliases duplicate canonical codes also present in the data. Registry resolution can route these links through the supported parent while preserving the historical variety as metadata. This classification alone does not guarantee that every target word has a local dictionary entry.

The external class includes 125 observed strings and 13,930 links. The special category is `mul-tax` (taxonomic name), 515 links. The reconstructed case is `frk` (Frankish), three links with reconstructed parent `gmw-pro`; this is not a basis for routing arbitrary Frankish words to modern German.

The examples below include both etymology-only varieties and historical full languages for comparison. Historical names alone do not justify a parent-language redirect: official full languages such as Old Swedish (`gmq-osw`) and Old Catalan (`roa-oca`) remain separate languages.

| Observed code | Registry name | Links | Parent/root destination | Example |
|---|---|---:|---|---|
| la-lat | Late Latin | 12,298 | la | fr -et → -ittus |
| la-med | Medieval Latin | 7,434 | la | fr armée → armāta |
| la-new | New Latin | 3,292 | la | fr national → nātiōnālis |
| roa-opt | Old Galician-Portuguese | 6,426 | roa-opt | fr couper → golpar |
| gmq-osw | Old Swedish | 4,184 | gmq-osw | fr aubin → hoppa |
| zlw-ocs | Old Czech | 2,722 | zlw-ocs | de Pistole → píščala |
| grc-koi | Koine Greek | 1,986 | grc | fr Michel → Μιχαήλ |
| roa-oca | Old Catalan | 899 | roa-oca | fr puis → puix |
| itc-ola | Old Latin | 319 | la | fr un → oinos |
| grk-mar | Mariupol Greek | 125 | grk-mar | el θα → тъа |
| itc-pra | Praenestine | 1 | la | la misceo → misc |
| fr-mis | Missouri French | 1 | fr | fr brème → brindgème |
| crp-cpr-kya | Kyakhta Chinese Pidgin Russian | 1 | crp-cpr | ru Шалтай-Болтай → шелатай-балетай |
| mul-tax | taxonomic name | 515 | mul | fr bégonia → Begonia |
| frk | Frankish | 3 | gmw-pro | fr brout → brust |

Rare observed varieties are included in the CSV, rather than dropped for low frequency. Examples include Praenestine `itc-pra` (Latin misceo → misc), Missouri French `fr-mis` (French brème → brindgème), and Kyakhta Chinese Pidgin Russian `crp-cpr-kya` (Russian Шалтай-Болтай → шелатай-балетай), one link each.

## Eight observed legacy aliases

Alias resolution is taken from the official core module. Match the literal code before resolving its canonical code; case and punctuation are meaningful here.

| Observed alias | Canonical code | Links | Example |
|---|---|---:|---|
| ML. | la-med | 146 | fr registre → registrum |
| LL. | la-lat | 99 | fr purée → purare |
| NL. | la-new | 79 | fr européen → Eurōpaeānus |
| sa-ved | vsn | 15 | en ban → भन॑ति |
| grc-epc | grc-epi | 8 | el κήλεος → κήλεος |
| VL. | la-vul | 7 | fr Fontainebleau → Fontem blahaud |
| EL. | la-ecc | 4 | fr archiépiscopat → archiepiscopātus |
| roa-oan | roa-ona | 2 | es baldragas → baladreo |

The five Latin abbreviation aliases total 335 links. The three other observed aliases add 25 links, for **360 links using eight legacy aliases**. Unobserved aliases in the official registry remain relevant to future data, but are outside this usage count.

## Multiple-language groups: valid members, ambiguous targets

**540 distinct comma-separated strings account for 3,110 links.** Every individual member resolves in the supplied registries. These include regional or historical members as well as full languages; whitespace around commas is inconsistent.

| Raw group | Links | Example |
|---|---:|---|
| fo,is | 284 | de Ansgar → Ásgeir |
| da,nb,nn,sv | 168 | en new → ny |
| gl,es | 144 | es -acho → -azo |
| da,nb | 126 | de schmerzstillend → smertestillende |
| nb,nn | 118 | en for → for |
| es,pt | 101 | fr s'en être → ir |
| it, pt, es | 5 | en fine → fino |
| la-ecc,la-lat | 5 | pt batismo → baptismus |

A list of valid language codes does not identify which language owns a particular word target. For example, `fo,is` accompanies Ásgeir and `da,nb,nn,sv` accompanies shared Scandinavian spellings. Selecting the first member or emitting several guessed destination links would add unsupported certainty. Preserve these ambiguous mentions as plain text unless the source supplies an unambiguous per-word language assignment. The CSV includes the independently classified components so this decision can be reviewed.

## Surface-analysis dispatcher errors

**27 distinct `+…` strings account for 2,609 incorrectly extracted links.** A targeted source trace found an example of every marker spelling. All came from the `surf` dispatcher template; its first positional argument selects another template or operation and is not a language.

| Source word | Raw dispatcher arguments | Why generic language parsing fails |
|---|---|---|
| de Bewegung | `+suf`, `de`, `bewegen`, `ung` | The operation occupies argument 1; `de` is the language. The suffix spelling also needs template-aware hyphen handling. |
| fr insulte | `+deverbal`, `fr`, `insulter` | Generic parsing produced links to both `fr` and `insulter` under the invalid language `+deverbal`. |
| it antichità | `+bor+`, `it`, `la`, `antiquitas`, `antīquitātem` | The dispatcher introduces source/target-language and display-form roles, so simply shifting every argument is insufficient. |
| it rutto | `+it-deverbal`, `ruttare` | This language-specific operation has no separate language argument. |
| it scritta | `+it-deverbal fpp`, `scrivere` | Another language-specific operation with a different argument layout. |
| pl dobry dzień | `+lit`, `good day` | This is explanatory text, not a target-language/word pair. |
| pl chichot | `+onom`, `pl` | This supplies no lexical target at all. |

Use conservative plain text for these unsupported dispatcher cases. Do not publish the `+…` marker as a language label, a local language route or a Wiktionary language-section anchor. Only extract links from an operation once its actual argument contract is implemented and checked. The complete observed marker list follows.

| Marker | Links | Source example |
|---|---:|---|
| +suf | 739 | de Bewegung → de |
| +deverbal | 563 | fr insulte → fr |
| +univ | 377 | it inoltre → it |
| +com | 328 | de Gebäude → de |
| +pre | 248 | en until → en |
| +af | 126 | el είσοδος → el |
| +con | 56 | en equivalent → en |
| +clipping | 41 | nl auto → nl |
| +bf | 38 | nl correleren → nl |
| +blend | 18 | fr génome → fr |
| +com+ | 10 | en weekday → en |
| +suffix | 9 | en sympathetic → en |
| +rdp | 8 | tr yavaş yavaş → tr |
| +clip | 6 | en radio- → en |
| +compound | 6 | pl Baba Jędza → pl |
| +prefix | 6 | en Antichrist → en |
| +univerbation | 6 | nl voorhanden → nl |
| +bor+ | 4 | it antichità → it |
| +syncopic form | 4 | it condurre → it |
| +affix | 3 | de auslegen → de |
| +inh+ | 3 | it de → it |
| +apheretic form | 2 | id ponakan → id |
| +backformation | 2 | de -eck → de |
| +it-deverbal | 2 | it rutto → ruttare |
| +onom | 2 | pl chichot → pl |
| +it-deverbal fpp | 1 | it scritta → scrivere |
| +lit | 1 | pl dobry dzień → good day |

The representative target shown above is the baseline extractor output, including erroneous targets such as the literal `de` or `pl`; it documents the defect rather than a recommended link.

## Database snapshot

| Language | Data hash | Records | Records with etymology links | Etymology links |
|---|---|---:|---:|---:|
| fr | f341ae44 | 402,072 | 48,344 | 93,475 |
| el | 1d8989be | 85,148 | 13,033 | 21,995 |
| de | c9b5f4dc | 369,879 | 58,099 | 132,919 |
| es | 2a7c293a | 809,350 | 18,635 | 37,308 |
| it | 45cad447 | 623,265 | 44,499 | 78,254 |
| en | c0c521f5 | 1,490,762 | 197,305 | 449,196 |
| pt | b6345891 | 445,852 | 17,058 | 37,657 |
| ca | 066cd04d | 198,377 | 22,389 | 39,281 |
| ro | 68b4243d | 130,299 | 73,152 | 126,000 |
| gl | 2b6da7ec | 212,893 | 8,094 | 18,002 |
| nl | 76655a10 | 146,408 | 45,525 | 93,795 |
| sv | 5e53f10c | 313,174 | 42,312 | 97,245 |
| da | 1038c494 | 58,323 | 16,653 | 37,022 |
| nb | 59421dbd | 79,310 | 16,034 | 35,591 |
| pl | 752dfcfe | 199,136 | 14,204 | 30,487 |
| ru | c84322e9 | 442,326 | 40,878 | 85,945 |
| uk | 7dbf4451 | 59,693 | 15,062 | 38,203 |
| cs | b16f1ee4 | 72,124 | 5,879 | 10,478 |
| fi | 64b8cf7e | 266,050 | 142,282 | 271,871 |
| hu | 63c90087 | 78,716 | 67,024 | 141,717 |
| tr | 2c177d23 | 45,833 | 19,911 | 43,444 |
| id | 8c2fa11a | 39,938 | 27,419 | 57,857 |
| vi | ec120c14 | 42,049 | 12,165 | 23,316 |
| eo | fe556a4b | 135,043 | 4,524 | 11,905 |
| la | a805ace8 | 886,587 | 10,108 | 19,293 |

## CSV schema and reproducibility

The CSV contains 2,270 data rows sorted by descending link count, then raw code. `raw_code` is unchanged, including the empty string, commas, uppercase regions, aliases and leading plus markers. `link_count` is the count before alias resolution or expansion of language groups.

`registry_classification` distinguishes full languages, etymology-only languages, families, groups, template markers and empty-anchor fallbacks. `routing_classification` is populated for etymology-only languages. `canonical_code`, `canonical_name`, `parent_code`, `root_code`, `wiktionary_section` and `parent_chain_json` record registry resolution. `is_core_alias` identifies the eight observed core aliases. `components_json` contains classifications of language-list members; `source_language_counts_json` preserves frequency by source dictionary. Three sets of example columns retain source/target provenance.

Audit intermediates: `/private/tmp/lexicoff-etymology-code-usage.json`, `/private/tmp/lexicoff-etymology-observed-classification.json`, `/private/tmp/lexicoff-etymology-marker-traces.json`. Reproduction scripts: `/private/tmp/lexicoff_inventory_etymology_codes.py`, `/private/tmp/lexicoff_classify_observed_codes.py`, `/private/tmp/lexicoff_trace_etymology_markers.py`. These temporary files are not required to read the committed report and complete CSV.
