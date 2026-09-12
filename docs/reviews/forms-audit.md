# Lexicoff forms and retrieval audit

Audit date: 2026-09-12. Worktree: `/private/tmp/lexicoff-linked-entries`. Production code was read-only for this audit; findings were sent to the implementing agent. This report separates baseline defects from subsequent verification.

## Method and coverage

- Scanned all 25 pinned compressed language sources, choosing the latest available pinned file for each language. Found 3,248,080 raw form-bearing records; 3,151,478 had at least one retained string before final entry validation. Those records contained 66,599,172 raw form rows and 45,641,430 deduplicated retained strings. These are extractor-level counts, not counts of accepted dictionary entries or final database size.
- Deterministic reservoir: 20 form-bearing source records per language, seed `9132026 + sum(ord(c) for c in language_code)`, traversing each full source in original order. Total: **500 random source records**. Added **50 targeted/common source records** covering the requested German probes and Unicode cases. The appendix lists every randomly selected record.
- Compared raw forms/tags/senses with current processing. Broad automated anomaly detection searched for English grammar terms, digits, brackets, and long strings; those are flags for inspection, not defect totals. Manually inspected over 100 representative records across all languages, including all rows discussed below. This is a source/processing audit, not expert linguistic certification in 25 languages.
- Built 25 isolated temporary SQLite databases from the samples and targeted records. **543 records accepted**, 7 excluded; all **10,974 retained form strings** returned their originating entry through exact reverse lookup with decomposed Unicode input. Checked uppercase headword lookup in all languages except Turkish, which received explicit locale-aware probes. Accepted records retain **122 formOf links** and **24 altOf links**.
- Independently sampled 200 distinct form keys from each of eight completed full databases (de, en, el, es, ca, cs, da, eo): **1,600 exact-form candidate retrieval probes**. This tested the pre-fix FTS candidate stage against exact form_lookup parents.
- Random reservoir includes six excluded Vietnamese character records and English dissipativity, whose source has no gloss. These exclusions are expected, not lost lexical definitions.

## Material findings and response

1. **Auxiliaries and grammatical instructions were indexed as lexical forms.** German exact form lookup for haben returned 9,606 parents, haben or sein 456, and sein 1,496. Raw machen labels haben as auxiliary; it is not an inflection of machen. Italian random verbs promozionare/risdrucire similarly retained avére. The implementation agent added an auxiliary-tag filter; verification confirms these sampled entries no longer contain the auxiliary.

2. **Large recurring upstream placeholder families require targeted removal.** French aller supplied ten strings such as être + past participle and present indicative of être + past participle. The full French scan flagged 75,166 possible metadata strings, mostly this family; the broad flag count is not an exact count of placeholders. Ukrainian скніти/іти supplied Future conjugation of бути + infinitive and Past conjugation of бути + past tense; Ukrainian had 11,786 broad metadata flags. Both families are removed in the verified sample extraction. Czech full databases contained 159 parents for the exact shared paragraph When the verb is used in perfective aspect, it does not have present tense and the present forms are used to express future only. Word-specific versions such as The verb dostat ... also occur. The agent added Czech sentence filtering.

3. **Exact inflections could fall out of search candidates.** The former forms_text token-prefix search used LIMIT 50 with no exact-form stage. In 1,600 deterministic probes, two English keys omitted genuine parents: cob omitted corncob (noun and verb); rug omitted Rugbeian (noun). These are source alternative forms and abbreviations, not conventional suffix inflections, but should still be retrievable. Direct detail lookup already used the precise index. The exact-form stage is now implemented before broad FTS candidates, ranked after exact headwords and ahead of prefixes. Repeating its indexed query returns all three cob parents (close of business; corncob noun/verb) and Rugbeian for rug.

4. **Source forms are broader than inflections.** Random examples include Portuguese Coronel Freitas→coronelense (demonym), Polish komisarz→komisarski (adjective), trylogia→trylogiczny, Russian кот→кошка/кошачий and идти→пойти. A fallback label claiming inflection would be misleading; the agent changed the label to Found under. Keep this general wording unless source relationship tags are carried through.

5. **Canonical spellings are essential for navigation.** Latin amo has amō as a canonical form; mansio has mānsiō. Their preservation makes macron-bearing links resolve. Cyrillic canonical stress marks and Turkish case distinction also require Unicode-aware keys. The explicit checks below passed.

6. **Long paradigms justify collapsed disclosure and indexed retrieval.** The German phrase sich auf den Weg machen has 130 raw form rows, initially 86 unique strings (85 after dropping haben). Random Finnish kasvisruoka has 259 strings; Turkish ödenmek 910. The Finnish source alone yielded 27,717,256 strings before final entry validation. Do not use a full forms list as the primary definition presentation or linearly scan those JSON lists for every lookup.

## Additional upstream defects, cleanup verification, and practical limits

- Hungarian suhog contains intransitive verb, definite forms are not used, Future is expressed with a present-tense verb with a completion-marking prefix and, or—more explicitly—with the infinitive plus the conjugated auxiliary verb fog, e.g. suhogni fog., and historical-tense explanatory fragments. Most carry error-unrecognized-form. van also has intransitive verb with otherwise ordinary grammatical tags. The final sample verification confirms removal of these instruction prefixes in suhog and van.
- Finnish olla supplies 1st sing. present indicative, 2nd sing. present indicative, and present indicative connegative, tagged error-unrecognized-form. Italian essere has comparable ordinal grammatical labels. The final sample verification confirms 11 grammatical-label strings removed from olla. Italian ordinal labels remain an upstream cleanup opportunity.
- Latin amo includes amātus + present active indicative of sum and analogous imperfect/future descriptions. These are construction recipes, not literal phrases to type. The final sample verification confirms all five sum recipe strings removed from amo.
- Polish Zawieja has married form Zawiejina / unmarried form Zawiejanka tagged traditional. Romanian masculine-equivalent prefixes also occur (vulpe→equivalent vulpoi). These are upstream labels concatenated with words; Romanian prefix filtering was broadened by the agent.
- Greek retained malformed single-brace and bracketed variants such as {ηθελημένος and ‑o}; another source row joins ευχαριστιόμουν - [ευχαριστούμουν]. Danish skelne contains (have /havde) skelnet. Dutch no. contains [please provide]. Conservative filtering is safer than inventing an inflection or blanket punctuation removal.
- Some untagged Russian romanizations survive (сельдям под шубой→selʹdjám pod šúboj), because the source provides no romanization tag. This is an upstream tagging omission; the extractor cannot infer all such cases safely.
- Digit flags are often legitimate: English 2day, German 3-Eck, Esperanto 1-a, Turkish 100., Vietnamese Chiến tranh thế giới 2. Do not delete all forms containing digits.
- Some source-generated Turkish compound plurals look linguistically suspect, for example eşek maydanozular beside eşek maydanozları for eşek maydanozu. This deserves native-speaker/upstream review; it was not silently corrected.
- Exact detail fallback retains distinctions such as Russian ё versus е and accented versus unaccented letters. Full FTS is forgiving; exact routes depend on available headword/canonical-form records. No new universal accent-stripping rule is justified by this audit.

## Explicit navigation probes

| Language | Query | Verified destination |
|---|---|---|
| de | MANCHEN | manchen (pron) |
| de | MACHE MICH AUF DEN WEG | sich auf den Weg machen (verb) |
| ru | КОТ | кот (noun) |
| ru | МОСКВА | Москва (name) |
| ru | КОТА́ | кот (noun) |
| uk | КИЇВ | Київ (name) |
| uk | КІТ | кіт (noun) |
| uk | КОТА́ | кіт (noun) |
| tr | IŞIK | ışık (noun), Işık (name) |
| tr | İSTANBUL | İstanbul (name) |
| tr | IŞIĞI | ışık (noun) |
| la | amō | amo (verb), amo (noun) |
| la | AMŌ | amo (verb), amo (noun) |
| la | mānsiō | mansio (noun) |
| la | MĀNSIŌ | mansio (noun) |
| la | canēs | canis (noun) |

**manchen** exists as a pronoun with three preserved sense paths: genitive masculine/neuter singular, accusative masculine singular, and dative plural; each links to manch. **manch** retains mancher, manche, manches, manchen, manchem. The earlier missing-word concern is resolved for this pinned source and extractor.

## Full-source extraction counts

Counts below precede final entry validity filtering and subsequent cleanup fixes. Metadata flags deliberately include false positives (e.g. Romanian case, Esperanto person); they are screening results.

| Language | Raw form-bearing records | Retained strings | Metadata flags | Digit flags |
|---|---:|---:|---:|---:|
| fr | 90,133 | 465,691 | 75,166 | 127 |
| el | 85,171 | 266,435 | 1,287 | 6 |
| de | 102,867 | 1,405,189 | 35 | 1,674 |
| es | 115,172 | 1,207,343 | 58 | 366 |
| it | 119,680 | 784,033 | 43 | 231 |
| en | 580,514 | 902,759 | 329 | 2,407 |
| pt | 74,045 | 497,508 | 5 | 341 |
| ca | 35,555 | 246,682 | 3 | 30 |
| ro | 100,855 | 749,333 | 129 | 7 |
| gl | 21,168 | 266,267 | 4 | 43 |
| nl | 65,031 | 197,724 | 11 | 105 |
| sv | 48,384 | 282,271 | 3 | 156 |
| da | 22,246 | 120,531 | 3 | 43 |
| nb | 37,544 | 88,763 | 4 | 125 |
| pl | 97,311 | 675,176 | 9 | 105 |
| ru | 442,556 | 1,475,917 | 11 | 298 |
| uk | 59,863 | 478,484 | 11,786 | 15 |
| cs | 47,676 | 479,636 | 2,004 | 24 |
| fi | 177,797 | 27,717,256 | 2 | 2,612 |
| hu | 42,521 | 2,238,409 | 15,138 | 8,723 |
| tr | 21,574 | 2,869,912 | 1 | 6 |
| id | 30,381 | 43,708 | 10 | 37 |
| vi | 16,427 | 28,117 | 2 | 10 |
| eo | 34,832 | 228,617 | 5 | 26 |
| la | 778,777 | 1,925,669 | 71 | 71 |

## Random-sample ledger (all 500 records)

Each row identifies the sampled source record, initial number of retained strings, and up to three representative strings. Excluded records remain visible so the sample denominator is auditable. Large paradigms were checked mechanically in full; these previews are deliberately abbreviated.

### fr

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| supraconductivité | noun | 1 | supraconductivités |
| kiplingien | adj | 3 | kiplingienne; kiplingiens; kiplingiennes |
| chlorose | noun | 1 | chloroses |
| débiné | verb | 3 | débinée; débinés; débinées |
| caquiste | adj | 1 | caquistes |
| réinjection | noun | 1 | réinjections |
| venaissin | adj | 3 | venaissine; venaissins; venaissines |
| ornithochorie | noun | 1 | ornithochories |
| piégeur | noun | 2 | piégeurs; piégeuse |
| saltatrice | noun | 1 | saltatrices |
| fossile | adj | 1 | fossiles |
| raclé | verb | 3 | raclée; raclés; raclées |
| subduction | noun | 1 | subductions |
| Dieppoise | noun | 1 | Dieppoises |
| radoub | noun | 1 | radoubs |
| gazetier | noun | 2 | gazetiers; gazetière |
| tel quel | adj | 3 | telle quelle; tels quels; telles quelles |
| chabin | noun | 3 | chabins; chabine; shabin |
| qui sème le vent récolte la tempête | proverb | 1 | qui sème le vent, récolte la tempête |
| pensé | verb | 3 | pensée; pensés; pensées |

### el

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| εορτάζομε | verb | 2 | γιορτάζουμε; εορτάζουμε |
| εχινόζωα | noun | 1 | εχινόζωων |
| συσκευή | noun | 3 | συσκευές; συσκευής; συσκευών |
| κατάρα | noun | 2 | κατάρες; κατάρας |
| δειγματοληψία | noun | 3 | δειγματοληψίες; δειγματοληψίας; δειγματοληψιών |
| απόστρατος | noun | 6 | απόστρατοι; αποστράτου; αποστράτων |
| ποδαρόδρομος | noun | 6 | ποδαρόδρομοι; ποδαρόδρομου; ποδαρόδρομων |
| ανακούφιση | noun | 1 | ανακούφισης |
| παλάβρα | noun | 2 | παλάβρες; παλάβρας |
| κέρινος | adj | 10 | κέρινη; κέρινο; κέρινοι |
| νάτριο | noun | 4 | νάτρια; νατρίου; νάτριου |
| σύστημα | noun | 3 | συστήματα; συστήματος; συστημάτων |
| αγοράκι | noun | 1 | αγοράκια |
| γαλοπούλα | noun | 2 | γαλοπούλες; γαλοπούλας |
| παιδαγωγήσεως | noun | 1 | παιδαγώγησης |
| αθηναίικος | adj | 10 | αθηναίικη; αθηναίικο; αθηναίικοι |
| ακρίβεια | noun | 2 | ακρίβειες; ακρίβειας |
| μπιφτέκι | noun | 3 | μπιφτέκια; μπιφτεκιού; μπιφτεκιών |
| Κωνσταντινούπολις | name | 3 | Κωνσταντινουπόλεως; Κωνσταντινούπολιν; Κωνσταντινούπολι |
| εθνικιστής | noun | 4 | εθνικιστές; εθνικίστρια; εθνικιστή |

### de

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| überprüfbar | adj | 23 | überprüfbarer; überprüfbare; überprüfbares |
| Aufgeblähtheit | noun | 1 | Aufgeblähtheiten |
| Support | noun | 1 | Supports |
| dagegen | adv | 1 | dargegen |
| einen Kopf kürzer | adj | 1 | 'n Kopp kürzer |
| Luftschloss | noun | 5 | Luftschlosses; Luftschlösser; Luftschlosse |
| das Pferd von hinten aufzäumen | verb | 4 | zäumt das Pferd von hinten auf; zäumte das Pferd von hinten auf; das Pferd von hinten aufgezäumt |
| Berliner | noun | 3 | Berliners; Berlinern; Berl. |
| genannt | adj | 23 | genannter; genannte; genanntes |
| funktionsfähig | adj | 70 | funktionsfähiger; am funktionsfähigsten; funktionsfähige |
| abgewirtschaftet | adj | 70 | abgewirtschafteter; am abgewirtschaftetsten; abgewirtschaftete |
| Brimsen | noun | 1 | Brimsens |
| du | pron | 1 | Du |
| durchzählen | verb | 61 | zählt durch; zählte durch; durchgezählt |
| Islamologin | noun | 1 | Islamologinnen |
| vorspielen | verb | 61 | spielt vor; spielte vor; vorgespielt |
| Ehrlosigkeit | noun | 1 | Ehrlosigkeiten |
| Kladderadatsch | noun | 4 | Kladderadatschs; Kladderadatsches; Kladderadatsche |
| Jährlein | noun | 1 | Jährleins |
| Pauli | name | 1 | Paulis |

### es

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| sikkimés | adj | 3 | sikkimesa; sikkimeses; sikkimesas |
| interventoría | noun | 1 | interventorías |
| aeróforo | noun | 1 | aeróforos |
| capucho | noun | 1 | capuchos |
| hidrazina | noun | 1 | hidrazinas |
| mesolita | noun | 1 | mesolitas |
| Teposcolula | name | 1 | Tepuzculula |
| chanfaina | noun | 1 | chanfainas |
| miguelista | adj | 1 | miguelistas |
| trompo | noun | 1 | trompos |
| remachar | verb | 132 | remacho; remaché; remachado |
| cesarista | adj | 1 | cesaristas |
| jefatura | noun | 2 | jefaturas; gefatura |
| buzón de salida | noun | 1 | buzones de salida |
| amigue | noun | 5 | amigues; amiga; amigas |
| zwitteriónico | adj | 3 | zwitteriónica; zwitteriónicos; zwitteriónicas |
| agricultor | adj | 3 | agricultora; agricultores; agricultoras |
| inmersivo | adj | 3 | inmersiva; inmersivos; inmersivas |
| cuarto de estar | noun | 1 | cuartos de estar |
| denunciar | verb | 132 | denuncio; denuncié; denunciado |

### it

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| efflorescente | adj | 1 | efflorescenti |
| promozionare | verb | 43 | promozionàre; promozióno; promozionài |
| otaria orsina | noun | 1 | otarie orsine |
| assente | adj | 1 | assenti |
| separazione | noun | 1 | separazioni |
| persica | noun | 1 | persiche |
| mascella | noun | 1 | mascelle |
| antemetico | adj | 3 | antemetica; antemetici; antemetiche |
| anarcopacifismo | noun | 1 | anarcopacifismi |
| insabbiamento | noun | 1 | insabbiamenti |
| temporofacciale | adj | 1 | temporofacciali |
| bestia | noun | 1 | bestie |
| risdrucire | verb | 51 | risdrucìre; risdrucìsco; risdrùcio |
| fatturato | verb | 3 | fatturata; fatturati; fatturate |
| pastore tedesco | noun | 3 | pastori tedeschi; pastora tedesca; pastore tedesche |
| pargoletto | adj | 3 | pargoletta; pargoletti; pargolette |
| clivo | noun | 1 | clivi |
| pirla | noun | 1 | pirli |
| scavalcato | adj | 3 | scavalcata; scavalcati; scavalcate |
| pileoriza | noun | 1 | pileorize |

### en

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| ichiboo | noun | 1 | ichiboos |
| kolach | noun | 2 | kolaches; kolachi |
| allusive | adj | 2 | more allusive; most allusive |
| want out | verb | 3 | wants out; wanting out; wanted out |
| chaquitaklla | noun | 1 | chaquitakllas |
| unbalanced | adj | 2 | more unbalanced; most unbalanced |
| Laude | name | 1 | Laudes |
| dressing mirror | noun | 1 | dressing mirrors |
| sanctimoniously | adv | 2 | more sanctimoniously; most sanctimoniously |
| water birch | noun | 1 | water birches |
| dissipativity | noun | excluded |  |
| playworthy | adj | 2 | more playworthy; most playworthy |
| postfurca | noun | 1 | postfurcae |
| keratodont | noun | 1 | keratodonts |
| Mastodonian | adj | 2 | more Mastodonian; most Mastodonian |
| lockplate | noun | 1 | lockplates |
| encebollado | noun | 1 | encebollados |
| stratagematist | noun | 1 | stratagematists |
| Tropic | noun | 1 | Tropics |
| tub wheel | noun | 1 | tub wheels |

### pt

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| confeição | noun | 1 | confeições |
| molar | noun | 1 | molares |
| murtal | noun | 1 | murtais |
| envenenadora | noun | 1 | envenenadoras |
| raposa-do-ártico | noun | 2 | raposas-do-ártico; raposa do Ártico |
| náiada | noun | 1 | náiadas |
| monomérico | adj | 3 | monomérica; monoméricos; monoméricas |
| kibutz | noun | 3 | kibutzim; kibutzes; kibbutz |
| bayesiano | adj | 3 | bayesiana; bayesianos; bayesianas |
| portulaca | noun | 1 | portulacas |
| parque temático | noun | 1 | parques temáticos |
| siberiano | noun | 3 | siberianos; siberiana; siberianas |
| Coronel Freitas | name | 1 | coronelense |
| vênus | noun | 1 | vénus |
| subtraído | verb | 3 | subtraída; subtraídos; subtraídas |
| coronhada | noun | 1 | coronhadas |
| desabitar | verb | 58 | desabito; desabitei; desabitado |
| lula | noun | 1 | lulas |
| tejolo | noun | 1 | tejolos |
| frequente | verb | 2 | freqüente; freqùente |

### ca

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| morella | noun | 1 | morelles |
| ventrut | adj | 3 | ventruda; ventruts; ventrudes |
| parlada | noun | 1 | parlades |
| seixanta-novè | adj | 3 | seixanta-novena; seixanta-novens; seixanta-novenes |
| polinesi | adj | 3 | polinèsia; polinesis; polinèsies |
| reusenc | noun | 3 | reusencs; reusenca; reusenques |
| merder | noun | 1 | merders |
| dominicà | noun | 3 | dominicans; dominicana; dominicanes |
| admés | verb | 3 | admesa; admesos; admeses |
| paperer | adj | 3 | paperera; paperers; papereres |
| electrotècnia | noun | 1 | electrotècnies |
| receptor | adj | 3 | receptora; receptors; receptores |
| rata de sorra diürna | noun | 1 | rates de sorra diürnes |
| criança | noun | 1 | criances |
| petitó | adj | 3 | petitona; petitons; petitones |
| polset | noun | 1 | polsets |
| abadia | noun | 1 | abadies |
| endinsar | verb | 46 | endinso; endinsí; endinsat |
| obrar | verb | 46 | obro; obrí; obrat |
| premsa | noun | 1 | premses |

### ro

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| capsulare | noun | 6 | capsulări; capsularea; capsulările |
| sinonimie | noun | 4 | sinonimia; sinonimii; sinonimiei |
| chitab | noun | 6 | chitaburi; chitabul; chitaburile |
| samalit | adj | 11 | samalită; samaliți; samalite |
| tectogeneză | noun | 6 | tectogeneze; tectogeneza; tectogenezele |
| fantezie | noun | 6 | fantezii; fantezia; fanteziile |
| eroman | adj | 11 | eromană; eromani; eromane |
| constantinopolitan | adj | 11 | constantinopolitană; constantinopolitani; constantinopolitane |
| sughița | verb | 28 | sughiță; sughițat; a sughița |
| Apahideanu | name | 1 | lui Apahideanu |
| învioșare | noun | 6 | învioșări; învioșarea; învioșările |
| vinil | noun | 6 | viniluri; vinilul; vinilurile |
| succint | adj | 11 | succintă; succinți; succinte |
| muncitor | noun | 7 | muncitori; muncitoare; muncitorul |
| colargol | noun | 3 | colargolul; colargolului; colargolule |
| Mironică | name | 1 | lui Mironică |
| cadmia | verb | 29 | cadmiază; cadmiat; a cadmia |
| unghinal | adj | 11 | unghinală; unghinali; unghinale |
| electrochimie | noun | 4 | electrochimia; electrochimii; electrochimiei |
| tip | noun | 6 | tipuri; tipul; tipurile |

### gl

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| sarabiar | verb | 15 | sarabia; sarabiou; sarabiado |
| terminoloxía | noun | 1 | terminoloxías |
| enxaugar | verb | 102 | enxaugo; enxauguei; enxaugado |
| esgotado | verb | 3 | esgotada; esgotados; esgotadas |
| emirato | noun | 2 | emiratos; emirado |
| mente | noun | 1 | mentes |
| camaleónico | adj | 3 | camaleónica; camaleónicos; camaleónicas |
| ós | contraction | 4 | ó; á; ás |
| esterqueiro | noun | 1 | esterqueiros |
| corrente | adj | 1 | correntes |
| insociábel | adj | 1 | insociábeis |
| hentai | noun | 1 | hentais |
| anglicana | noun | 1 | anglicanas |
| cabido | noun | 1 | cabidos |
| cambra | noun | 1 | cambras |
| escacho | noun | 1 | escachos |
| celular | adj | 1 | celulares |
| Bermún | name | 1 | Vermum |
| lobio | noun | 1 | lobios |
| matanza do porco | noun | 1 | matanzas do porco |

### nl

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| gildeproef | noun | 2 | gildeproeven; gildeproefje |
| stoned | adj | 9 | stoneder; stonedst; het stonedst |
| voetkusje | noun | 1 | voetkusjes |
| beeldelement | noun | 2 | beeldelementen; beeldelementje |
| golden retriever | noun | 2 | golden retrievers; golden retrievertje |
| voltooid | verb | 2 | voltooide; voltooids |
| slagend | verb | 2 | slagende; slagends |
| krabbelen | verb | 7 | krabbel; krabbelde; krabbelt |
| sleutelbosje | noun | 1 | sleutelbosjes |
| koppel | noun | 2 | koppels; koppeltje |
| baanwielrenner | noun | 3 | baanwielrenners; baanwielrennertje; baanwielrenster |
| houtachtig | adj | 9 | houtachtiger; houtachtigst; het houtachtigst |
| erupteren | verb | 7 | erupteer; erupteerde; erupteert |
| inspectie | noun | 1 | inspecties |
| onderzijde | noun | 1 | onderzijden |
| aantekenboek | noun | 2 | aantekenboeken; aantekenboekje |
| getutoyeerd | verb | 2 | getutoyeerde; getutoyeerds |
| belooning | noun | 2 | belooningen; belooninkje |
| Erichem | name | 2 | Erkum; Erkem |
| roodborstje | noun | 1 | roodborstjes |

### sv

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| Tjernobyl | name | 1 | Tjernobyls |
| order | noun | 7 | orders; ordern; orderns |
| styck | noun | 1 | st. |
| stoppur | noun | 5 | stoppurs; stoppuret; stoppurets |
| intresselöshet | noun | 3 | intresselöshets; intresselösheten; intresselöshetens |
| glitch | noun | 6 | glitchen; glitchens; glitchar |
| statsledning | noun | 3 | statslednings; statsledningen; statsledningens |
| förblinda | verb | 11 | förblindar; förblindade; förblindat |
| pippa | verb | 11 | pippar; pippade; pippat |
| slumpa sig | verb | 5 | slumpar sig; slumpade sig; slumpat sig |
| annullerad | adj | 2 | annullerat; annullerade |
| fort | noun | 5 | forts; fortet; fortets |
| daska | verb | 11 | daskar; daskade; daskat |
| givare | noun | 5 | givares; givaren; givarens |
| tjuvstarta | verb | 11 | tjuvstartar; tjuvstartade; tjuvstartat |
| åhöra | verb | 12 | åhör; åhörde; åhört |
| hyperlektisk | adj | 3 | hyperlektiskt; hyperlektiska; hyperlektiske |
| finnas kvar | verb | 3 | finns kvar; fanns kvar; funnits kvar |
| entledigad | adj | 2 | entledigat; entledigade |
| pålägg | noun | 5 | påläggs; pålägget; påläggets |

### da

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| moscovium | noun | 3 | moscoviummet; moscoviums; moscoviummets |
| endetarm | noun | 7 | endetarmen; endetarme; endetarmene |
| gigantisk | adj | 1 | gigantiske |
| skelne | verb | 9 | skelnede; skelnet; skelnes |
| komplicerethed | noun | 8 | kompliceretheden; kompliceretheder; komplicerethederne |
| situationsfornemmelse | noun | 7 | situationsfornemmelsen; situationsfornemmelser; situationsfornemmelserne |
| nordisk | adj | 1 | nordiske |
| kondom | noun | 7 | kondomet; kondomer; kondomerne |
| stifte | verb | 7 | stift; at stifte; stifter |
| altsaxofon | noun | 7 | altsaxofonen; altsaxofoner; altsaxofonerne |
| krokodille | noun | 7 | krokodillen; krokodiller; krokodillerne |
| hjorde | noun | 1 | hjorder |
| kanton | noun | 7 | kantonen; kantoner; kantonerne |
| koagulere | verb | 10 | koaguler; at koagulere; koagulerer |
| fløjte | verb | 9 | fløjtede; fløjtet; fløjtes |
| budgettere | verb | 10 | budgetter; at budgettere; budgetterer |
| omskifte | verb | 10 | omskift; at omskifte; omskifter |
| purisme | noun | 3 | purismen; purismes; purismens |
| hawaiigås | noun | 7 | hawaiigåsen; hawaiigæs; hawaiigæssene |
| båke | noun | 7 | båken; båker; båkerne |

### nb

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| peruansk | adj | 1 | peruanske |
| regnearkene | noun | 1 | regnearka |
| lyddemper | noun | 3 | lyddemperen; lyddempere; lyddemperne |
| motorsaga | noun | 1 | motorsagen |
| ubuden | adj | 2 | ubudent; ubudne |
| terne | noun | 4 | terna; ternen; terner |
| nordirsk | adj | 1 | nordirske |
| solslynget | noun | 1 | solslyngen |
| vedgå | verb | 3 | vedgår; vedgikk; vedgått |
| unngåelse | noun | 3 | unngåelsen; unngåelser; unngåelsene |
| høykommisjon | noun | 3 | høykommisjonen; høykommisjoner; høykommisjonene |
| hestesport | noun | 3 | hestesporten; hestesporter; hestesportene |
| bispedømme | noun | 4 | bispedømmet; bispedømmer; bispedømma |
| øyenbryn | noun | 4 | øyenbrynet; øyenbryna; øyenbrynene |
| kondolere | verb | 6 | kondoler; kondolerer; kondoleres |
| sørkyst | noun | 3 | sørkysten; sørkyster; sørkystene |
| utrolig | adj | 2 | utrolige; utrulig |
| montasje | noun | 3 | montasjen; montasjer; montasjene |
| ruse | noun | 4 | rusa; rusen; ruser |
| tredelingen | noun | 1 | tredelinga |

### pl

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| zachlapać | verb | 1 | zachlapywać |
| Gawlica | name | 9 | Gawlice; Gawlicy; Gawlic |
| ponętnie | adv | 2 | ponętniej; najponętniej |
| zasłona | noun | 10 | zasłonka; zasłony; zasłon |
| Paszek | name | 9 | Paszkowie; Paszka; Paszków |
| opierunek | noun | 8 | opierunki; opierunku; opierunków |
| resorak | noun | 10 | resoraczek; resoraki; resoraka |
| ambitnik | noun | 10 | ambitnicy; ambitniki; ambitnika |
| sensowność | noun | 2 | sensowności; sensownością |
| wyprucie | noun | 3 | wyprucia; wypruciu; wypruciem |
| komisarz | noun | 14 | komisarski; komisarze; komisarza |
| Żakiewicz | name | 9 | Żakiewiczowie; Żakiewicza; Żakiewiczów |
| trylogia | noun | 10 | trylogiczny; trylogie; trylogii |
| Zawieja | name | 11 | married form Zawiejina; unmarried form Zawiejanka; Zawieje |
| bestialność | noun | 2 | bestialności; bestialnością |
| Sępowicz | name | 10 | Sępowiczowie; Sępowicza; Sępowiczów |
| chwast | noun | 9 | chwasty; chwastu; chwastów |
| Kuropaś | name | 9 | Kuropasiowie; Kuropasia; Kuropasiów |
| Wdowczak | name | 9 | Wdowczakowie; Wdowczaka; Wdowczaków |
| knajpka | noun | 10 | knajpeczka; knajpki; knajpek |

### ru

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| фарсам | noun | 1 | фа́рсам |
| сельдям под шубой | noun | 2 | сельдя́м под шу́бой; selʹdjám pod šúboj |
| заархивирует | verb | 1 | заархиви́рует |
| боровы | noun | 1 | бо́ровы |
| повыситесь | verb | 1 | повы́ситесь |
| дублениям | noun | 1 | дубле́ниям |
| полегайте | verb | 1 | полега́йте |
| отравлявший | verb | 13 | отравля́вший; отравля́вшее; отравля́вшая |
| плеоназмом | noun | 1 | плеона́змом |
| созваниваться | verb | 24 | созва́ниваться; созвони́ться; созва́нивающийся |
| сральне | noun | 1 | сра́льне |
| бисексуальности | noun | 1 | бисексуа́льности |
| сельчанину | noun | 1 | сельча́нину |
| турбореакторах | noun | 1 | ту̀рбореа́кторах |
| шелестах | noun | 1 | ше́лестах |
| почёсывавший | verb | 12 | почёсывавшее; почёсывавшая; почёсывавшие |
| периодической системы элементов | noun | 2 | периоди́ческой систе́мы элеме́нтов; periodíčeskoj sistémy eleméntov |
| восстановится | verb | 1 | восстано́вится |
| легкоатлетами | noun | 1 | легкоатле́тами |
| падубе | noun | 1 | па́дубе |

### uk

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| застерігайте | verb | 1 | застеріга́йте |
| п'юпітр | noun | 12 | п'юпі́тр; п'юпі́тра; п'юпі́три |
| школи | noun | 1 | шко́ли |
| особини | noun | 1 | осо́бини |
| модулі | noun | 1 | мо́дулі |
| дієтологією | noun | 1 | дієтоло́гією |
| Лазар | name | 10 | Ла́зар; Ла́заря; Ла́зарі |
| загальний | adj | 16 | зага́льний; зага́льно; зага́льність |
| свідок | noun | 1 | сві́док |
| чиїйсь | pron | 1 | чиї́йсь |
| столиків | noun | 1 | сто́ликів |
| ентомолог | noun | 10 | ентомо́лог; ентомо́лога; ентомо́логи |
| Ліваном | name | 1 | Ліва́ном |
| пропорціями | noun | 1 | пропо́рціями |
| скніти | verb | 31 | скні́ти; скніть; скні́ючи |
| зміцню | verb | 1 | зміцню́ |
| неґативний | adj | 16 | неґати́вний; неґати́вно; неґати́вність |
| геном | noun | 1 | ге́ном |
| візків | noun | 1 | візкі́в |
| вибиралося | verb | 1 | вибира́лося |

### cs

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| laťka | noun | 9 | laťky; latěk; laťce |
| exkrál | noun | 10 | exkrálové; exkrála; exkrálů |
| lípečka | noun | 9 | lípečky; lípeček; lípečce |
| rozhovor | noun | 7 | rozhovory; rozhovoru; rozhovorů |
| Ptáčník | name | 10 | Ptáčníková; Ptáčníkové; Ptáčníka |
| trsátko | noun | 7 | trsátka; trsátek; trsátku |
| jura | noun | 9 | jury; jur; juře |
| gramotnost | noun | 5 | gramotnosti; gramotností; gramotnostem |
| zralý | adj | 14 | zralejší; nejzralejší; zrale |
| isoglosa | noun | 10 | isoglosový; isoglosy; isoglos |
| maratón | noun | 9 | maratóny; maratónu; maratónů |
| aborce | noun | 5 | aborcí; aborci; aborcím |
| nezaujatý | adj | 11 | nezaujatá; nezaujaté; nezaujatého |
| berla | noun | 9 | berly; berel; berle |
| fáze měsíce | noun | 5 | fází měsíce; fázi měsíce; fázím měsíce |
| drobek | noun | 6 | drobky; drobku; drobků |
| mapa webu | noun | 9 | mapy webu; map webu; mapě webu |
| studená válka | noun | 9 | studené války; studených válek; studené válce |
| ananasovník | noun | 6 | ananasovníky; ananasovníku; ananasovníků |
| údajný | adj | 11 | údajná; údajné; údajného |

### fi

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| vuokra-asuminen | noun | 164 | vuokra-asumiset; vuokra-asumisen; vuokra-asumisten |
| änäri | noun | 177 | änärit; änärin; änärien |
| sadusto | noun | 177 | sadustot; saduston; sadustojen |
| Perkiömäki | name | 158 | Perkiömäet; Perkiömäen; Perkiömäkien |
| lohkeileminen | noun | 164 | lohkeilemiset; lohkeilemisen; lohkeilemisten |
| sooloilija | noun | 164 | sooloilijat; sooloilijan; sooloilijoiden |
| turripuku | noun | 158 | turripuvut; turripuvun; turripukujen |
| Irlanninmeri | name | 75 | Irlanninmeren; Irlanninmerta; Irlanninmeressä |
| ikinaisellinen | adj | 166 | ikinaiselliset; ikinaisellisen; ikinaisellisten |
| Joukahainen | name | 75 | Joukahaisen; Joukahaista; Joukahaisessa |
| hätääkärsivä | adj | 160 | hätääkärsivät; hätääkärsivän; hätääkärsivien |
| graani | noun | 158 | graanit; graanin; graanien |
| elämänrytmi | noun | 158 | elämänrytmit; elämänrytmin; elämänrytmien |
| valkokuonomyyrä | noun | 158 | valkokuonomyyrät; valkokuonomyyrän; valkokuonomyyrien |
| derivointiaika | noun | 158 | derivointiajat; derivointiajan; derivointiaikojen |
| Autio | name | 164 | Autiot; Aution; Autioiden |
| kasvisruoka | noun | 259 | kasvisruoat; kasvisruoan; kasvisruokien |
| lokerointi | noun | 158 | lokeroinnit; lokeroinnin; lokerointien |
| tasavaltalaisuus | noun | 158 | tasavaltalaisuudet; tasavaltalaisuuden; tasavaltalaisuuksien |
| Turpela | name | 164 | Turpelat; Turpelan; Turpeloiden |

### hu

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| okosmérő | noun | 49 | okosmérők; okosmérőt; okosmérőket |
| csat | noun | 49 | csatok; csatot; csatokat |
| utópisztikusabb | adj | 37 | utópisztikusabbak; utópisztikusabbat; utópisztikusabbakat |
| szerdai | adj | 37 | szerdaiak; szerdait; szerdaiakat |
| suhog | verb | 116 | suhogok; suhogsz; suhogunk |
| lakk | noun | 49 | lakkok; lakkot; lakkokat |
| vizsgáló | verb | 37 | vizsgálók; vizsgálót; vizsgálókat |
| állítmányai | noun | 19 | állítmányait; állítmányainak; állítmányaival |
| kandela | noun | 49 | kandelák; kandelát; kandelákat |
| százhuszonöt | num | 50 | százhuszonötök; százhuszonötöt; százhuszonötöket |
| bocsátottatok | verb | 1 | bocsájtottatok |
| bab | noun | 49 | babok; babot; babokat |
| egyesület | noun | 49 | egyesületek; egyesületet; egyesületeket |
| bizalmaim | noun | 19 | bizalmaimat; bizalmaimnak; bizalmaimmal |
| panaszkönyvetek | noun | 19 | panaszkönyveteket; panaszkönyveteknek; panaszkönyvetekkel |
| friuli | noun | 50 | friuliak; friulit; friuliakat |
| segítése | noun | 19 | segítését; segítésének; segítésével |
| születési | adj | 37 | születésiek; születésit; születésieket |
| mellékjel | noun | 49 | mellékjelek; mellékjelet; mellékjeleket |
| véglegesebb | adj | 35 | véglegesebbek; véglegesebbet; véglegesebbeket |

### tr

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| eşek maydanozu | noun | 12 | eşek maydanozunu; eşek maydanozular; eşek maydanozları |
| komünote | noun | 64 | komünoteyi; komünoteler; komünoteleri |
| kara boya | noun | 72 | kara boyayı; kara boyalar; kara boyaları |
| bulmaca | noun | 2 | bulmacayı; bulmacalar |
| Melahat | name | 23 | Melahatlar; Melahat'lar; Melahat'ı |
| gazeteci | noun | 63 | gazeteciyi; gazeteciler; gazetecileri |
| hıçkırık | noun | 57 | hıçkırığı; hıçkırıklar; hıçkırıkları |
| gericilik | noun | 58 | gericiliği; gericiliğe; gericilikte |
| ödenmek | verb | 910 | ödenir; ödenirim; ödenirsin |
| mayın | noun | 57 | mayını; mayınlar; mayınları |
| kazık | noun | 57 | kazığı; kazıklar; kazıkları |
| deney | noun | 57 | deneyi; deneyler; deneyleri |
| tebrik | noun | 11 | tebriği; tebrikler; tebrikleri |
| mahrum | adj | 49 | mahrumum; mahrum muyum?; mahrumsun |
| tartışma | noun | 63 | tartışmayı; tartışmalar; tartışmaları |
| Tarabya | name | 2 | Tarabyayı; Tarabyalar |
| Luhansk | name | 17 | Luhansklar; Luhansk'ı; Luhanskları |
| Adapazarı | name | 28 | Adapazarılar; Adapazarı'lar; Adapazarı'yı |
| az kalsın | adv | 1 | az kala |
| dietil | noun | 1 | dietili |

### id

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| mendag | noun | 1 | mendag-mendag |
| menfess | noun | 2 | menfess-menfess; menfes |
| girilaya | noun | 1 | girilaya-girilaya |
| mengantar | verb | 1 | mêngantar |
| tata hukum | noun | 1 | tata-tata hukum |
| asta brata | noun | 1 | asta-asta brata |
| Serang | name | 1 | Sérang |
| dikenal | verb | 1 | dikênal |
| barangan | noun | 1 | barangan-barangan |
| remis | adj | 2 | lebih remis; paling remis |
| benda mengalir | noun | 2 | benda-benda mengalir; bendalir |
| kombu | noun | 1 | kombu-kombu |
| ataninai | noun | 1 | ataninai-ataninai |
| awam | noun | 1 | awam-awam |
| menakluk | verb | 1 | mênakluk |
| rasi bintang | noun | 2 | rasi-rasi bintang; rasi |
| senyawa kimia | noun | 1 | senyawa-senyawa kimia |
| madukara | noun | 1 | madukara-madukara |
| overval | noun | 4 | overval-overval; overpal; overvale |
| topik | noun | 1 | topik-topik |

### vi

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| kĩ trị | adj | 1 | kỹ trị |
| mía | noun | 1 | 𣖙 |
| vần vũ | verb | 1 | vần vụ |
| 間 | character | excluded |  |
| 㘋 | character | excluded |  |
| ròi | noun | 2 | 𧋆; 耒 |
| quy củ | adj | 1 | qui củ |
| dẽ | noun | 4 | 雉; 鵜; giẽ |
| chiên | noun | 1 | 𦍫 |
| ba | noun | 1 | 爸 |
| 抆 | character | excluded |  |
| mọng | adj | 2 | 濛; mòng mọng |
| châu chấu | noun | 2 | 蛛𧎝; 蝼𧎝 |
| xã hội chủ nghĩa | noun | 2 | 社會主義; xã hội chủ nghị |
| sả | noun | 1 | trả |
| 虛 | character | excluded |  |
| 撤 | character | excluded |  |
| hoạ báo | noun | 1 | họa báo |
| phi toàn cầu hoá | noun | 1 | phi toàn cầu hóa |
| 忼 | character | excluded |  |

### eo

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| fulmoŝirmilo | noun | 4 | fulmoŝirmilon; fulmoŝirmiloj; fulmoŝirmilojn |
| mustelo | noun | 3 | mustelon; musteloj; mustelojn |
| maljuniĝonta | adj | 3 | maljuniĝontan; maljuniĝontaj; maljuniĝontajn |
| elmigri | verb | 32 | elmigras; elmigris; elmigros |
| torpedo | noun | 3 | torpedon; torpedoj; torpedojn |
| klingo | noun | 3 | klingon; klingoj; klingojn |
| kunlaboranto | noun | 3 | kunlaboranton; kunlaborantoj; kunlaborantojn |
| arkivado | noun | 1 | arkivadon |
| fama | adj | 3 | faman; famaj; famajn |
| venkinto | noun | 3 | venkinton; venkintoj; venkintojn |
| batali | verb | 32 | batalas; batalis; batalos |
| kompatoto | noun | 3 | kompatoton; kompatotoj; kompatotojn |
| transitiva | adj | 3 | transitivan; transitivaj; transitivajn |
| koti | verb | 59 | kotas; kotis; kotos |
| cxefmangxo | noun | 3 | cxefmangxon; cxefmangxoj; cxefmangxojn |
| kreskanto | noun | 3 | kreskanton; kreskantoj; kreskantojn |
| razonto | noun | 3 | razonton; razontoj; razontojn |
| intereso | noun | 3 | intereson; interesoj; interesojn |
| anakronismo | noun | 4 | anakronismon; anakronismoj; anakronismojn |
| aliranto | noun | 3 | aliranton; alirantoj; alirantojn |

### la

| Source word | POS | Initial retained forms | Preview |
|---|---|---:|---|
| assolavere | verb | 1 | assolāvēre |
| acerbabimini | verb | 1 | acerbābiminī |
| adservarim | verb | 1 | adservārim |
| instrueretur | verb | 1 | īnstruerētur |
| exoletu | verb | 1 | exolētū |
| prosperaverimus | verb | 1 | prosperāverīmus |
| patrici | adj | 1 | patricī |
| hilarabuntur | verb | 1 | hilarābuntur |
| dormiveris | verb | 1 | dormīveris |
| inquinamus | verb | 1 | inquināmus |
| praeiudicarim | verb | 1 | praeiūdicārim |
| decussabimus | verb | 1 | decussābimus |
| Gallarum | adj | 1 | Gallārum |
| stabiliaris | verb | 1 | stabiliāris |
| inebriavissemus | verb | 1 | inēbriāvissēmus |
| adarabimini | verb | 1 | adarābiminī |
| purgatam | verb | 1 | pūrgātam |
| halandos | verb | 1 | hālandōs |
| necubi | adv | 1 | nēcubī̆ |
| apparescatis | verb | 1 | appārēscātis |

## Reproducibility artifacts

Temporary audit inputs/scripts: `/private/tmp/forms_audit.py`, `/private/tmp/forms-audit-samples.json`, `/private/tmp/forms_db_probe.py`, `/private/tmp/forms-db-results.json`, `/private/tmp/forms_verify.py`, `/private/tmp/forms-verification.json`. No production databases were modified by this audit. The final sample verification was rerun after the auxiliary, French, Ukrainian, Czech, Hungarian, Finnish, Romanian, and Latin cleanup changes. All 10,974 current retained form strings passed exact lookup. Full-source totals and initial-sample previews intentionally retain the pre-cleanup baseline. Final full database regeneration is owned by the implementing agent.
