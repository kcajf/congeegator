"""Reproducible, streaming quality review of dictionary source and built SQLite data.

Example (does not download or mutate source/build files):
    python -m pipeline.audit_dictionary --source-dir cache/VERSION \
        --data-dir apps/lexicoff/r2_data/data/v1 --output /tmp/dictionary-audit.json

Counts describe records and senses separately from distinct spellings. Form-of
senses, repeated word/POS pairs, and large paradigms are review signals, not
automatically errors: inflected forms and separate etymologies are legitimate.
"""

import argparse
from collections import Counter
import hashlib
import heapq
import io
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import unicodedata

import msgspec
import zstandard

from .entry_json import decode_entry_json
from .dictionary import DICT_CONFIGS, process_dict_entry
from .sqlite_output import dictionary_search_key
from .wiktionary import Entry


# Common nouns, verbs and adjectives, with diacritics and non-Latin scripts.
# These are presence/definition/search probes, not a vocabulary coverage estimate.
COMMON_WORDS = {
    "nn": ["hus", "vatn", "vera", "eta", "god", "eg", "ikkje", "ein", "ei", "eit"],
    "lv": ["māja", "ūdens", "būt", "ēst", "labs"],
    "bg": ["къща", "вода", "съм", "ям", "добър"],
    "mt": ["dar", "ilma", "kien", "kiel", "tajjeb"],
    "tl": ["bahay", "tubig", "kumain", "mabuti", "ako"],
    "gd": ["taigh", "uisge", "bi", "ith", "math"],
    "fo": ["hús", "vatn", "vera", "eta", "góður"],
    "ang": ["hus", "wæter", "beon", "etan", "god"],
    "non": ["hús", "vatn", "vera", "eta", "góðr"],
    "pt": ["casa", "água", "ser", "comer", "bom"],
    "ca": ["casa", "aigua", "ésser", "menjar", "bo"],
    "ro": ["casă", "apă", "fi", "mânca", "bun"],
    "gl": ["casa", "auga", "ser", "comer", "bo"],
    "nl": ["huis", "water", "zijn", "eten", "goed"],
    "sv": ["hus", "vatten", "vara", "äta", "bra"],
    "da": ["hus", "vand", "være", "spise", "god"],
    "nb": ["hus", "vann", "være", "spise", "god"],
    "pl": ["dom", "woda", "być", "jeść", "dobry"],
    "ru": ["дом", "вода", "быть", "есть", "хороший"],
    "uk": ["дім", "вода", "бути", "їсти", "добрий"],
    "cs": ["dům", "voda", "být", "jíst", "dobrý"],
    "fi": ["talo", "vesi", "olla", "syödä", "hyvä"],
    "hu": ["ház", "víz", "van", "eszik", "jó"],
    "tr": ["ev", "su", "olmak", "yemek", "iyi"],
    "id": ["rumah", "air", "ada", "makan", "baik"],
    "vi": ["nhà", "nước", "là", "ăn", "tốt"],
    "eo": ["domo", "akvo", "esti", "manĝi", "bona"],
    "la": ["domus", "aqua", "sum", "edo", "bonus"],
    "en": ["house", "water", "be", "eat", "good"],
    "fr": ["maison", "eau", "être", "manger", "bon"],
    "de": ["Haus", "Wasser", "sein", "essen", "gut"],
    "es": ["casa", "agua", "ser", "comer", "bueno"],
    "it": ["casa", "acqua", "essere", "mangiare", "buono"],
    "el": ["σπίτι", "νερό", "είμαι", "τρώω", "καλός"],
    "grc": ["οἶκος", "ὕδωρ", "εἰμί", "ἐσθίω", "ἀγαθός", "λόγος"],
    "az": ["ev", "su", "olmaq", "yemək", "yaxşı"],
    "eu": ["etxe", "ur", "izan", "jan", "on"],
    "br": ["ti", "dour", "bezañ", "debriñ", "mat"],
    "et": ["maja", "vesi", "olema", "sööma", "hea"],
    "ka": ["სახლი", "წყალი", "არის", "ჭამა", "კარგი"],
    "he": ["בית", "מים", "היה", "אכל", "טוב", "שלום"],
    "hi": ["घर", "पानी", "होना", "खाना", "अच्छा"],
    "is": ["hús", "vatn", "vera", "borða", "góður"],
    "ga": ["teach", "uisce", "bí", "ith", "maith"],
    "ko": ["집", "물", "이다", "먹다", "좋다"],
    "lt": ["namas", "vanduo", "būti", "valgyti", "geras"],
    "mk": ["куќа", "вода", "сум", "јаде", "добар"],
    "ms": ["rumah", "air", "ada", "makan", "baik"],
    "oc": ["ostal", "aiga", "èsser", "manjar", "bon"],
    "fa": ["خانه", "آب", "بودن", "خوردن", "خوب"],
    "sa": ["गृह", "जल", "अस्ति", "अत्ति", "साधु"],
    "sh": ["kuća", "voda", "biti", "jesti", "dobar", "кућа", "mleko", "mlijeko"],
    "sk": ["dom", "voda", "byť", "jesť", "dobrý"],
    "cy": ["tŷ", "dŵr", "bod", "bwyta", "da"],
}

DIRT_PATTERNS = {
    "wiki_markup": re.compile(r"\{\{|\}\}|\[\[|\]\]"),
    "html_markup": re.compile(r"</?(?:ref|span|div|br|p|small|sup|sub|table|a|i|b)(?:\s[^>]*|/?)>", re.I),
    "extraction_error": re.compile(r"(?i:Lua error|Script error)|\b(?:Template|Module):(?=\S)|\[\[Category:"),
    "replacement_character": re.compile("\ufffd"),
    "control_character": re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"),
    "placeholder_gloss": re.compile(r"(?:please (?:add|provide) (?:a |an |the )?(?:definition|translation)|definition (?:needed|missing)|\bno gloss(?: found)?\b)", re.I),
}


def _summary(record):
    result = {k: record[k] for k in ("word", "pos", "senses", "gender", "pronunciation", "etymology", "details") if k in record}
    if record.get("forms"):
        result["form_count"] = len(record["forms"])
        result["forms_sample"] = record["forms"][:20]
    if record.get("formDetails"):
        result["form_details_sample"] = record["formDetails"][:20]
    if record.get("pronunciations"):
        result["pronunciations"] = record["pronunciations"]
    return result


def _strings(record):
    yield "word", record["word"]
    for sense in record["senses"]:
        yield "gloss", sense["gloss"]
        for example in sense.get("examples", []):
            if isinstance(example, str):
                yield "example", example
            else:
                yield "example", example["text"]
                for key in ("translation", "roman", "ref"):
                    if example.get(key):
                        yield key, example[key]
        for key in ("tags", "topics"):
            for label in sense.get(key, []):
                yield key, label
        for key in ("links", "formOf", "altOf", "synonyms", "antonyms"):
            for link in sense.get(key, []):
                yield "link", link["word"]
                for field in ("label", "sense"):
                    if link.get(field):
                        yield field, link[field]
    for links in record.get("details", {}).values():
        for link in links:
            yield "link", link["word"]
            for field in ("label", "sense"):
                if link.get(field):
                    yield field, link[field]
    for form in record.get("forms", []):
        yield "form", form
    for key in ("etymology", "pronunciation"):
        if key in record:
            yield key, record[key]
    for form in record.get("formDetails", []):
        yield "annotated_form", form["form"]
        for tag in form.get("tags", []):
            yield "form_label", tag
    for detail in record.get("formDetails", []):
        for reading in detail.get("readings", []):
            for label in reading.get("grammar", []) + reading.get("qualifiers", []):
                yield "form_label", label
    for pronunciation in record.get("pronunciations", []):
        yield "labelled_ipa", pronunciation["ipa"]
        if pronunciation.get("label"):
            yield "pronunciation_label", pronunciation["label"]


def _record_fingerprint(record):
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True).encode()).digest()


def audit_source(lines, config, sample_size=12):
    """Audit every source line through the production importer, without frequencies."""
    counts, pos_counts, rejected_pos = Counter(), Counter(), Counter()
    dirt, examples = Counter(), {}
    words, word_pos, fingerprints = set(), Counter(), set()
    common = {word: [] for word in COMMON_WORDS.get(config.code, [])}
    random_samples = []
    largest_forms = []
    largest_senses = []

    def flag(kind, word, field, value):
        dirt[kind] += 1
        examples.setdefault(kind, [])
        if len(examples[kind]) < 10:
            examples[kind].append({"word": word, "field": field, "value": value[:500]})

    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        counts["source_records"] += 1
        try:
            raw = msgspec.json.decode(line)
            if raw.get("source") == "thesaurus" and not raw.get("pos"):
                rejected_pos["thesaurus_without_pos"] += 1
                continue
            if raw.get("pos") == "hard-redirect":
                rejected_pos["hard-redirect"] += 1
                continue
            entry = msgspec.json.decode(line, type=Entry)
        except (msgspec.DecodeError, TypeError, AttributeError) as exc:
            flag("invalid_source_record", str(line_number), "source", str(exc))
            continue
        if entry.lang_code != config.code:
            flag("wrong_language", entry.word, "lang_code", entry.lang_code)
            continue
        counts["source_senses"] += len(entry.senses)
        source_form_senses = sum(bool(s.form_of or "form-of" in s.tags) for s in entry.senses)
        counts["source_form_of_senses"] += source_form_senses
        record = process_dict_entry(config, entry)
        if record is None:
            rejected_pos[entry.pos] += 1
            continue
        counts["records"] += 1
        counts["senses"] += len(record["senses"])
        if source_form_senses == len(entry.senses):
            counts["form_only_records"] += 1
        word = record["word"]
        words.add(word)
        word_pos[(word, record["pos"])] += 1
        pos_counts[record["pos"]] += 1
        for key in ("forms", "gender", "pronunciation", "etymology"):
            counts[f"records_with_{key}"] += bool(record.get(key))
        counts["records_with_examples"] += any(s.get("examples") for s in record["senses"])
        for key in ("etymologyLinks", "synonyms", "antonyms", "related", "derived"):
            counts[f"records_with_{key}"] += bool(record.get("details", {}).get(key))
        for sense in record["senses"]:
            for key in ("links", "formOf", "altOf", "synonyms", "antonyms", "topics"):
                counts[f"senses_with_{key}"] += bool(sense.get(key))
            for example in sense.get("examples", []):
                if isinstance(example, str):
                    continue
                counts["translated_examples"] += bool(example.get("translation"))
                counts["emphasized_examples"] += bool(example.get("bold"))
                for text_key, range_key in (("text", "bold"), ("translation", "translationBold")):
                    for start, end in example.get(range_key, []):
                        if not (0 <= start < end <= len(example.get(text_key, ""))):
                            flag("invalid_emphasis", word, range_key, str([start, end]))
        fingerprint = _record_fingerprint(record)
        if fingerprint in fingerprints:
            flag("identical_record", word, "record", record["pos"])
        fingerprints.add(fingerprint)
        glosses = [s["gloss"] for s in record["senses"]]
        if len(set(glosses)) < len(glosses):
            counts["records_with_repeated_gloss"] += 1
        for field, value in _strings(record):
            for kind, pattern in DIRT_PATTERNS.items():
                if kind == "placeholder_gloss" and field != "gloss":
                    continue
                if pattern.search(value):
                    flag(kind, word, field, value)
            if not value.strip():
                flag("empty_text", word, field, value)
            if field == "word" and value != value.strip():
                flag("word_surrounding_whitespace", word, field, value)
            if unicodedata.normalize("NFC", value) != value:
                counts[f"non_nfc_{field}"] += 1
        if word in common:
            common[word].append(_summary(record))
        # Bottom-k stable content hashes give reproducible samples independent of
        # source ordering; the line number prevents heap comparisons of dicts.
        sample = (-int.from_bytes(fingerprint[:8], "big"), line_number, _summary(record))
        if sample_size:
            heapq.heappush(random_samples, sample)
            if len(random_samples) > sample_size:
                heapq.heappop(random_samples)
        forms = record.get("forms", [])
        counts["forms"] += len(forms)
        for heap, size in ((largest_forms, len(forms)), (largest_senses, len(glosses))):
            heapq.heappush(heap, (size, word, record["pos"]))
            if len(heap) > 10:
                heapq.heappop(heap)

    counts["unique_headwords"] = len(words)
    counts["unique_records"] = len(fingerprints)
    counts["repeated_word_pos_pairs"] = sum(n > 1 for n in word_pos.values())
    counts["rejected_records"] = counts["source_records"] - counts["records"]
    return {
        "language": config.code,
        "records_sha256": hashlib.sha256(b"".join(sorted(fingerprints))).hexdigest(),
        "counts": dict(counts),
        "pos_counts": dict(pos_counts),
        "rejected_pos": dict(rejected_pos),
        "review_flags": dict(dirt),
        "flag_examples": examples,
        "common_words": common,
        "missing_common_words": [word for word, records in common.items() if not records],
        "random_samples": [sample[2] for sample in sorted(random_samples, reverse=True)],
        "largest_form_counts": sorted(largest_forms, reverse=True),
        "largest_sense_counts": sorted(largest_senses, reverse=True),
        "most_repeated_word_pos": [(word, pos, n) for (word, pos), n in word_pos.most_common(10) if n > 1],
    }


def _fts_query(word, code="en"):
    # Match the browser's L/M/N token boundaries, including vowel/virama marks.
    word = dictionary_search_key(word, code)
    normalized = "".join(c if unicodedata.category(c)[0] in "LMN" or c.isspace() else " " for c in word)
    return " ".join('"' + token + '"' for token in normalized.split())


def audit_sqlite(path, code, source_report=None):
    """Verify downloaded-size accounting, integrity, counts and common-word FTS."""
    path = Path(path).resolve()
    result = {"artifact": path.name, "download_bytes": path.stat().st_size}
    with path.open("rb") as source:
        result["data_hash"] = hashlib.file_digest(source, "md5").hexdigest()[:8]
    with tempfile.TemporaryDirectory(prefix="lexicoff-audit-") as tmp:
        sqlite_path = Path(tmp) / f"{code}.sqlite"
        if path.suffix == ".zst":
            with path.open("rb") as source, sqlite_path.open("wb") as dest:
                zstandard.ZstdDecompressor().copy_stream(source, dest)
        else:
            shutil.copyfile(path, sqlite_path)
        result["sqlite_bytes"] = sqlite_path.stat().st_size
        # FTS5's own integrity command uses INSERT syntax. Run it only against
        # this disposable copy; source/build artifacts are never mutated.
        conn = sqlite3.connect(sqlite_path)
        try:
            result["integrity_check"] = [r[0] for r in conn.execute("PRAGMA integrity_check")]
            result["fts_integrity"] = {}
            result["fts_records"] = {}
            for table in ("entries_fts", "fuzzy"):
                try:
                    conn.execute(f"INSERT INTO {table}({table}) VALUES('integrity-check')")
                    result["fts_integrity"][table] = "ok"
                except sqlite3.DatabaseError as exc:
                    result["fts_integrity"][table] = str(exc)
                finally:
                    conn.rollback()
                result["fts_records"][table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "form_lookup" in tables:
                result["form_lookup_records"] = conn.execute("SELECT count(*) FROM form_lookup").fetchone()[0]
                result["form_lookup_orphans"] = conn.execute(
                    "SELECT count(*) FROM form_lookup f LEFT JOIN entries e ON e.id=f.entry_id WHERE e.id IS NULL"
                ).fetchone()[0]
            result["language"] = conn.execute("SELECT value FROM metadata WHERE key='lang'").fetchone()[0]
            result["records"] = conn.execute("SELECT count(*) FROM entries").fetchone()[0]
            result["unique_headwords"] = conn.execute("SELECT count(DISTINCT word) FROM entries").fetchone()[0]
            result["zero_frequency_records"] = conn.execute("SELECT count(*) FROM entries WHERE freq=0").fetchone()[0]
            result["frequency_range"] = list(conn.execute("SELECT min(freq), max(freq) FROM entries").fetchone())
            result["invalid_frequency_records"] = conn.execute("SELECT count(*) FROM entries WHERE freq IS NULL OR freq < 0 OR freq > 9").fetchone()[0]
            result["highest_frequency"] = [dict(zip(("word", "pos", "freq"), r)) for r in conn.execute("SELECT word,pos,freq FROM entries ORDER BY freq DESC, word LIMIT 20")]
            columns = {row[1] for row in conn.execute("PRAGMA table_info(entries)")}
            selected = ["word", "pos", "senses", "gender", "forms", "pronunciation", "etymology"]
            selected += [name for name in ("details", "form_details", "pronunciations") if name in columns]
            fingerprints = set()
            for row in conn.execute("SELECT " + ",".join(selected) + " FROM entries"):
                record = {}
                for key, value in zip(selected, row):
                    if value is None:
                        continue
                    if key in {"senses", "forms", "details", "form_details", "pronunciations"}:
                        value = decode_entry_json(value)
                    record["formDetails" if key == "form_details" else key] = value
                fingerprints.add(_record_fingerprint(record))
            result["records_sha256"] = hashlib.sha256(b"".join(sorted(fingerprints))).hexdigest()
            result["search_probes"] = []
            for word in COMMON_WORDS.get(code, []):
                ids = {r[0] for r in conn.execute("SELECT id FROM entries WHERE word=?", (word,))}
                fts_ids = {r[0] for r in conn.execute("SELECT rowid FROM entries_fts WHERE word MATCH ?", (_fts_query(word, code),))}
                result["search_probes"].append({"word": word, "present": bool(ids), "fts_matches_all_records": bool(ids) and ids <= fts_ids})
            if source_report:
                counts = source_report["counts"]
                result["source_counts_match"] = (
                    result["records"] == counts.get("unique_records", counts["records"])
                    and result["unique_headwords"] == counts["unique_headwords"]
                )
                if source_report.get("records_sha256"):
                    result["source_records_match"] = source_report["records_sha256"] == result["records_sha256"]
        finally:
            conn.close()
    return result


def read_source(path):
    with Path(path).open("rb") as source:
        if str(path).endswith(".zst"):
            with zstandard.ZstdDecompressor().stream_reader(source) as stream:
                yield from io.BufferedReader(stream)
        else:
            yield from source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--manifest", type=Path, help="Optionally verify compressed size/hash against a release manifest")
    parser.add_argument("--languages", nargs="+", default=list(COMMON_WORDS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=12, help="Deterministic random records per language")
    args = parser.parse_args()
    if args.sample_size < 0:
        parser.error("--sample-size must be nonnegative")
    if args.manifest and not args.data_dir:
        parser.error("--manifest requires --data-dir")
    manifest = json.loads(args.manifest.read_text())["languages"] if args.manifest else None
    configs = {config.code: config for config in DICT_CONFIGS}
    report = {"languages": {}, "notes": [
        "Form-only records are legitimate dictionary entries, not automatically dirt.",
        "Repeated word/POS pairs may represent distinct etymologies; identical records merit review.",
        "Common-word probes and deterministic samples are spot checks, not complete linguistic validation.",
        "Review flags are heuristics; inspect examples before changing source handling.",
    ]}
    for code in args.languages:
        if code not in configs:
            parser.error(f"Language is not configured: {code}")
        source = args.source_dir / f"en-{code}-filtered.jsonl.zst"
        if not source.exists():
            source = args.source_dir / f"en-{code}-filtered.jsonl"
        result = audit_source(read_source(source), configs[code], sample_size=args.sample_size)
        with source.open("rb") as f:
            result["source_sha256"] = hashlib.file_digest(f, "sha256").hexdigest()
        result["source_bytes"] = source.stat().st_size
        if args.data_dir:
            paths = sorted(args.data_dir.glob(f"{code}-*/{code}.sqlite.zst"))
            if not paths:
                paths = sorted(args.data_dir.glob(f"{code}/{code}.sqlite.zst"))
            if len(paths) != 1:
                parser.error(f"Expected one {code} database, found {len(paths)}")
            result["database"] = audit_sqlite(paths[0], code, result)
            if manifest is not None:
                expected = manifest.get(code, {})
                result["database"]["manifest_matches"] = (
                    expected.get("code") == code
                    and expected.get("dataHash") == result["database"]["data_hash"]
                    and expected.get("dataSize") == result["database"]["download_bytes"]
                )
        report["languages"][code] = result
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"{code}: {result['counts']['records']:,} records, {result['counts']['unique_headwords']:,} headwords, flags={result['review_flags']}", flush=True)


if __name__ == "__main__":
    main()
