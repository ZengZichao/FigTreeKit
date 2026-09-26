"""Generate the golden-conformance-corpus index cited by SI Section S9.

Collects every test in ``test/test_conformance.py`` (plus the pinned expected
FigTree 1.4.4 strings each one asserts) and writes

    benchmarks/conformance_corpus_index.csv

with one row per fixture: fixture id, the serialization or behavioural branch
it covers, the pinned expected FigTree string where one is asserted, the
pytest node id, and whether the case is executed against a FigTree binary
(stock / patched) or against FigTreeKit alone.

The index is derived from the test module itself, so it cannot drift from the
corpus. Run it whenever a conformance test is added or changed:

    python3 scripts/generate_conformance_index.py
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "test" / "test_conformance.py"
OUT = ROOT / "benchmarks" / "conformance_corpus_index.csv"

# Branch taxonomy: which documented serialisation / behaviour branch each test
# exercises. Keys are matched against the test name and its docstring, in
# order, so the mapping is auditable rather than guessed at write-up time.
BRANCH_RULES = [
    (r"stock.*jar.*identity|jar.*identity", "binary identity of the stock FigTree 1.4.4 JAR (SHA-256)"),
    (r"stock.*render|stock.*accept", "stock (unpatched) FigTree 1.4.4 parses and renders FigTreeKit output"),
    (r"annotation.*format|golden.*format|format.*golden", "annotation serialisation format (hex colour / hilight arity / Font.decode)"),
    (r"topology", "round-trip preservation of tree topology"),
    (r"tip.*set|tipset", "round-trip preservation of the tip set"),
    (r"branch.*length", "round-trip preservation of branch lengths"),
    (r"comment.*position|position.*matrix", "bracket-comment position support matrix"),
    (r"translate", "BEAST TRANSLATE block round-trip (quoted / escaped / comma-bearing names)"),
    (r"non.?ultrametric|node.*height|height", "iterative node-depth semantics on a non-ultrametric tree"),
    (r"multi.?tree|tree.*declaration|scanner", "position-aware multi-tree replacement and declaration scanning"),
    (r"collapse", "clade-collapse annotation and eligibility gating"),
    (r"render.*accept|accept.*render", "acceptance render through the bundled patched JAR"),
]


def branch_for(name: str, doc: str) -> str:
    hay = f"{name} {doc}".lower()
    for pattern, label in BRANCH_RULES:
        if re.search(pattern, hay):
            return label
    return "other conformance branch (see the test docstring)"


def expected_strings(body: str) -> list[str]:
    """Pinned expected FigTree strings asserted in a test body."""
    found = []
    for m in re.finditer(r"""assert(?:Equal|In)?\((?P<a>[^\n]*)\)|(?P<lit>[ru]?['"]\[&[^\n]*?['"])""", body):
        lit = m.group("lit")
        if lit:
            found.append(lit.strip().lstrip("ru'\"").rstrip("'\""))
            continue
        a = m.group("a") or ""
        for lit2 in re.findall(r"""['"](\[&[^\n]*?)['"]""", a):
            found.append(lit2)
    seen, out = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out[:3]


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()
    rows = []
    current_class = ""
    # collect (class, method, start_line) for every test method
    methods = []
    for i, line in enumerate(lines):
        cm = re.match(r"class\s+(Test\w+)", line.strip())
        if cm:
            current_class = cm.group(1)
        dm = re.match(r"def (test_\w+)\(", line.strip())
        if dm:
            methods.append((current_class, dm.group(1), i))
    for idx, (cls, meth, start) in enumerate(methods):
        end = methods[idx + 1][2] + 1 if idx + 1 < len(methods) else len(lines)
        body = "\n".join(lines[start:end])
        doc_m = re.search(r'(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', body, re.S)
        doc = (doc_m.group(1).strip().splitlines() or [""])[0] if doc_m else ""
        fixture = f"GOLDEN-{idx + 1:03d}"
        rows.append({
            "fixture_id": fixture,
            "test_class": cls,
            "test_function": meth,
            "pytest_node_id": f"test/test_conformance.py::{cls}::{meth}",
            "branch_covered": branch_for(meth, doc),
            "pinned_expected_figtree_string": " | ".join(expected_strings(body)),
            "docstring_first_line": doc,
            "oracle": ("stock FigTree 1.4.4 binary" if "stock" in meth.lower() or "Stock" in cls
                       else "patched FigTree JAR" if "render" in meth.lower()
                       else "FigTree 1.4.4 Java sources (transcribed, pinned fixture)"),
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} with {len(rows)} fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
