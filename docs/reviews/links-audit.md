# Lexical links and etymology audit

Reviewed the linked-entry implementation against the pinned Wiktextract sources on 2026-09-12. This audit was read-only for production code and generated databases. Findings were sent to the implementing agent while work continued.

## Sampling and checks

- Streamed all **25 pinned language sources**, covering **7,653,656** records after excluding missing POS and hard redirects. **7,626,845** contained an etymology template or a sense link/form/alternative relationship. These are source-record counts, not unique words or final accepted dictionary records.
- Selected **300 enriched records**, 12 per language, by taking the lowest 64-bit SHA-256 values of complete raw JSONL lines among successfully processed candidates. This is deterministic and avoids selecting only familiar words. The sample is balanced by language, not proportional to dictionary size.
- Independently selected **200 records with etymology templates**, eight per language, using the same hash rule. Some overlap with the 300-record sample is intentional; 500 sample positions are not claimed as 500 distinct entries.
- Programmatically checked all 300 records: **356 senses**, **529 original links**, **206 form/alternative references**, and **67 original etymology links**. Checks covered competing destinations for the same display label, aspect-marker contamination in form targets, markup in targets, and form-target language consistency.
- Programmatically checked all 200 etymology records and the full-source inventory of doublet and component template arguments. Manually compared source versus processed text/links for **50 sense records and 50 etymology records**, two from every language, plus targeted doublets, template aliases, and all changed etymology links from the verification sample.
- Reprocessed all 300 + 200 sample positions after implementation fixes. This verifies extraction; it does not assert that every destination exists in the downloaded databases or that every Wiktionary URL was visited.

## Findings and verification

### Fixed: wrong doublet destination

`doublet|fr|parabole|palabre` in French **parole** was interpreted as display `palabre` pointing to `parabole`. French **computer** similarly linked `conter` to `compter`. Positional arguments after language are independent terms, with numbered display overrides, not the mention-template argument layout.

The complete corpus contains **6,231 multi-term `doublet`/`dbt` template occurrences**. This is an affected-input count, not 6,231 manually confirmed visible errors. The revised extractor emits independent links; sampled Indonesian **magister** now correctly produces `maestro`, `master`, and `mester`.

### Fixed: accented form labels suppressed valid links

In **20 sampled senses**, generated form references used accented display spellings while source links used canonical page titles. Because the renderer safely rejects ambiguous labels, it suppressed the useful link: **10 Russian, 2 Ukrainian, and 8 Latin senses**.

Examples: Russian **стыдитесь** had competing targets `стыди́ться` and `стыдиться`, both displayed as `стыди́ться`; Latin **transformandae** had `trānsfōrmandus` and `transformandus`. The source already supplied the correct label-to-page mapping.

Four further references included aspect markers as part of the destination (**1 Russian, 3 Ukrainian**), including Ukrainian **розряд** → `розряди́ти pf` and Russian **лежали** → `лежа́ть impf`.

Reprocessing the full 300-record sample with canonical source-link reuse reduced **both issue counts to zero**. The resulting sample contains **505 links**, reflecting removal of competing duplicates rather than lost definitions. All 206 form/alternative references remain.

### Fixed: supported language anchors with underscores

The source uses `#Norwegian_Bokmål`, whereas configuration names use `Norwegian Bokmål`. Previously these could be treated as unknown-language external links. A direct verification of `sjal#Norwegian_Bokmål` now returns language `nb`.

### Improved: high-volume structured etymology omissions

The initial whitelist omitted ordinary compounds, affixes, surface analyses, and borrowing aliases. Across all sources the component families `af`, `affix`, `compound`, `com`, `surf`, and `surface analysis` (including `+` aliases) occur **562,981 times**, containing **1,168,973 term slots**. Only **30,070 slots (2.57%)** contain inline modifiers or language prefixes, so conservative support of simple arguments gives broad coverage.

The full inventory includes **11,491 `lbor`**, **5,663 `ubor`**, **449 `slbor`**, and **26,111 `uder`** occurrences. Revised extraction handles these borrowing layouts and independent component arguments, preserving `lang1`/`alt1` style overrides. Explicitly confirmed that `m-g` is a gloss-only template and must not become a link.

Within the independent 200-record etymology sample, records with structured links improved from **70 to 129**, and links from **123 to 259**. Examples now linked include French **viveur** (`vive`, `-eur`), German **Wundbrand** (`Wunde`, `Brand`), Finnish **puoliloinen** (`puoli`, `loinen`), Hungarian **vízszennyezés** (`víz`, `szennyezés`), and Greek **συμφοιτητής** (Ancient Greek borrowing plus Greek components).

### Fixed in rendering: repeated etymology spelling can mean different languages

Indonesian **bejibun** mentions Hokkien **十分** and Japanese **十分**. Only the Japanese cog link was initially extracted because the Chinese-family template was unsupported, so both occurrences were rendered as Japanese links. Vietnamese **võ sĩ** similarly mentions Chinese and Japanese **武士**, but its Chinese target `武士//` is intentionally rejected as template syntax.

The existing ambiguous-label guard correctly handles *two extracted* destinations (French **Pékin**, English/Dutch `Peking`), but cannot detect a destination omitted during extraction. The implementation now uses a conservative etymology-only guard to leave repeated labels plain. Direct execution of the actual renderer helper confirms both problematic repeated-label cases emit no links in etymology mode; unique component labels still link.

### Additional malformed component target

The expanded compound extraction exposed Catalan **motocicleta** → `(bi)cicleta`, an annotated morphological spelling rather than an ordinary page title. Reported a bounded fix: reject parentheses in target spellings while preserving them in source display labels (e.g. English **pramiverine**, `pr(opyl)ami(ne)` → `propylamine`). Direct checks confirm the annotated target is rejected and the legitimate display label remains supported.

## Remaining bounded limitations

- `ety`/`etymon` templates and complex inline modifiers stay plain. These are substantial: **419,845 `ety`** and **25,047 `etymon`** occurrences, often alongside conventional templates, so counts do not imply entirely missing entries. Etymology-only examples include Spanish **reyezuelo** (`rey` + `-zuelo`) and Czech **zašeptat** (`za-` + `šeptat`). A future parser should use structured arguments, not the malformed HTML/JSON expansion fragments present in some source templates.
- Prefix/suffix aliases can require adding hyphens absent from raw arguments, e.g. Dutch **aannemer**, `suf|nl|aannemen|er` expands to `aannemen + -er`. Leaving unsupported families plain is safer than inventing the wrong page title.
- Reconstructed `*` terms, namespace/interwiki targets, and malformed template arguments are deliberately not navigable dictionary links.
- Unsupported historical-language codes fall back to Wiktionary. The source preserves codes such as `grc`, `ota`, `kaw`, `la-med`, and `xdk`; not all have a section-name mapping. Some links open the correct page without jumping to the language section. This audit did not visit every historical destination.
- A compound/etymology spelling may itself be a source red link or use stress/macrons that need a canonical form lookup. The audit checked extraction fidelity, not global destination existence. The form-reference fix specifically uses source page titles and does not globally strip meaningful diacritics.
- Multi-language cognates appear as comma-separated codes (`gl,ast`, `ca,oc` in Portuguese **justeza**). They cannot safely choose a single installed-language route; external fallback is appropriate.
- The raw data lacks link offsets. Longest complete-label matching and ambiguity rejection are conservative approximations; omitted templates can otherwise create false confidence about repeated spellings.

## Manual sample register

Each row lists the first two records in each deterministic random sample. Source link targets/labels and resulting glosses or etymologies were inspected for these 100 sample positions; they include overlapping entries.

| Language | Sense sample | Etymology sample |
| --- | --- | --- |
| fr | suifèrent, pilâmes | encor, viveur |
| el | δημόσιος υπάλληλος, ισόβια δεσμά | αυτοεκφραστικός, συμφοιτητής |
| de | ärgerlicherem, Ettlingen | Gefach, Wundbrand |
| es | disembrioplástico, cansemos | reyezuelo, olivínico |
| it | acciottolato, piagnucolosa | tegumento, vombato |
| en | neovascularised, Punxsutawney | neovascularised, Punxsutawney |
| pt | concebe, Outubro | justeza, excepcionalismo |
| ca | desatendràs, gòfer | gòfer, descens |
| ro | exortare, ondometru | exortare, ondometru |
| gl | berran, mediatizariam | favorable, maniotas |
| nl | spreekgestoeltes, ondername | kol, aannemer |
| sv | rättrogenhet, uråkningarnas | rättrogenhet, restaurangvagn |
| da | klammeris, præsens | præsens, kofanger |
| nb | gallion, sjalet | gallion, -ynene |
| pl | świętej krowie, jaszczurczemu | angelologia, literka |
| ru | стыдитесь, погашении | расхитить, бивуачный |
| uk | розряд, алегорія | розряд, алегорія |
| cs | zašeptat, interpret | zašeptat, proň |
| fi | puoliloinen, rekisteri | puoliloinen, rekisteri |
| hu | addig, vízszennyezés | addig, vízszennyezés |
| tr | yaratılışı, kırımı | kırımı, asıntı |
| id | bejibun, munggah | bejibun, munggah |
| vi | trái ngang, 竿鈎 | trái ngang, võ sĩ |
| eo | estimindajn, distribuata | prujno, silentema |
| la | Thynias, transformandae | Thynias, alumnor |

## Reproduction artifacts

Temporary audit artifacts (not production outputs):

- `/private/tmp/audit_lex_links.py` and `/private/tmp/lexicoff-links-audit-samples.json`: complete inventory and 300 source/output pairs.
- `/private/tmp/audit_lex_etym.py` and `/private/tmp/lexicoff-etym-audit-samples.json`: template counts and 200 stratified source/output pairs.
- `/private/tmp/check_lex_links_samples.py`, `/private/tmp/lexicoff-links-sample-checks.json`, `/private/tmp/lexicoff-etym-sample-checks.json`: initial issue details.
- `/private/tmp/recheck_lex_links.py`, `/private/tmp/lexicoff-links-recheck.json`: post-fix reprocessing and changed etymology links.

## Final verification notes

- Reprocessed all 300 enriched and 200 etymology sample positions against the final extractor. No competing canonical/display morphology links or aspect-contaminated form targets remain in the checked sample.
- Verified **100 captured real multi-term doublet templates**, four per language, emit the separate source terms with their own numbered display overrides; no mismatches.
- Directly executed the actual TypeScript `linkedText` helper for the Chinese/Japanese repeated-label hazards. Etymology mode emits zero links for each repeated ambiguous spelling; normal mode is unchanged; unique `vive` and `-eur` components remain linked.
- Confirmed the entry page passes `uniqueOnly` for etymology and the `LinkedText` component forwards it.
- Confirmed `(bi)cicleta` is rejected while display `pr(opyl)ami(ne)` targeting `propylamine` is preserved.
- Final independent etymology sample: **129/200 records have links, 259 links total** (the intermediate 260 count included the now-rejected `(bi)cicleta`).
