"""Pin Wiktionary's containment graph and produce Lexicoff's routing audit.

Usage: python scripts/classify_etymology_languages.py api-response.json [...]
Inputs are MediaWiki query/revisions responses with rvslots=main,
rvprop=ids|timestamp|content and formatversion=2 for the five modules below.
No Lua is executed. Unexpected syntax, missing codes and cycles fail closed.
The generated JSON is sufficient to route existing downloaded dictionaries;
dictionary bundles do not need to be regenerated when this metadata changes.
"""

import csv
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "Module:etymology languages/data",
    "Module:etymology languages/code to canonical name",
    "Module:languages/code to canonical name",
    "Module:languages/data",
    "Module:families/data",
}


def without_comments(source):
    # Strings come first: a quoted -- is text, not a Lua comment.
    token = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|--\[(=*)\[[\s\S]*?\]\1\]|--[^\n]*''')
    return token.sub(lambda m: "" if m[0].startswith("--") else m[0], source)


def string_map(source):
    return dict(re.findall(r'\["([^"\\]+)"\]\s*=\s*"([^"\\]+)"', source))


def main(paths):
    modules, revisions = {}, []
    for path in paths:
        for page in json.loads(Path(path).read_text())["query"]["pages"]:
            if page["title"] not in MODULES or "revisions" not in page:
                continue
            revision = page["revisions"][0]
            modules[page["title"]] = without_comments(revision["slots"]["main"]["content"])
            revisions.append({"title": page["title"], "revision": revision["revid"],
                              "timestamp": revision["timestamp"],
                              "url": f'https://en.wiktionary.org/w/index.php?oldid={revision["revid"]}'})
    assert modules.keys() == MODULES, MODULES - modules.keys()
    source = modules["Module:etymology languages/data"]
    varieties = {code: [name, parent] for code, name, parent in re.findall(
        r'^m\["([^"\\]+)"\]\s*=\s*\{\s*"([^"\\]+)",\s*(?:nil|\d+),\s*"([^"\\]+)"', source, re.M)}
    assert len(varieties) == len(re.findall(r'^m\[', source, re.M))
    assert {k: v[0] for k, v in varieties.items()} == string_map(
        modules["Module:etymology languages/code to canonical name"])
    full = string_map(modules["Module:languages/code to canonical name"])
    # The upstream loader gives full records precedence. Require explicit review
    # if the currently disjoint canonical registries ever gain overlapping codes.
    assert not varieties.keys() & full.keys(), varieties.keys() & full.keys()
    families = dict(re.findall(r'^m\["([^"\\]+)"\]\s*=\s*\{\s*"([^"\\]+)"',
                               modules["Module:families/data"], re.M))
    aliases = string_map(re.search(r'export.aliases\s*=\s*\{([^}]+)\}',
                                  modules["Module:languages/data"])[1])
    supported = json.loads((ROOT / "apps/lexicoff/src/lib/data-manifest.json").read_text())["languages"]
    terminals, rows = {}, []
    for code, (name, parent) in sorted(varieties.items()):
        chain, current = [code], parent
        while current in varieties or current in aliases:
            assert current not in chain, chain
            chain.append(current)
            current = aliases.get(current) or varieties[current][1]
        assert current in full or current in families, (code, current)
        chain.append(current)
        kind = "family" if current in families else "special" if current in {"mul", "und"} else "reconstructed" if current.endswith("-pro") else "language"
        section = full.get(current) or families[current]
        terminals[current] = [section, kind]
        classification = "available in Lexicoff" if current in supported else f"external {kind}"
        rows.append([code, name, parent, current, section, classification, " > ".join(chain)])
    # Keep existing non-installed historical-language tooltips and anchors.
    for code in {"fro", "frm", "gmh", "goh", "ang", "enm", "ofs", "nds", "is", "fo", "no", "xum"} | set(aliases.values()):
        if code in full and code not in varieties:
            terminals[code] = [full[code], "language"]
    result = {"sources": sorted(revisions, key=lambda r: r["title"]),
              "attribution": "Wiktionary contributors; factual projection of the linked module revisions (CC BY-SA 4.0).",
              "aliases": dict(sorted(aliases.items())), "varieties": dict(sorted(varieties.items())),
              "terminals": dict(sorted(terminals.items()))}
    (ROOT / "apps/lexicoff/src/lib/etymologyLanguages.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    with (ROOT / "docs/reviews/etymology-languages.csv").open("w") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["code", "name", "immediate parent", "entry language", "entry language name", "routing classification", "containment chain"])
        writer.writerows(rows)
    print(f"Classified {len(varieties)} etymology-only codes and {len(aliases)} legacy code aliases; no unresolved roots or cycles.")


if __name__ == "__main__":
    main(sys.argv[1:])
