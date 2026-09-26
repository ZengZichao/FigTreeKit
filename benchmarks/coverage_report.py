#!/usr/bin/env python3
"""Coverage report: the reproducible source of Figure S1 and Table S15.

FigTreeKit reports nine *components*, which are author-defined groups of
source modules, while ``coverage.py`` reports per-*file* line rates.  The
mapping between the two used to be implicit, so a reader following the
reproduction instructions in the Supporting Information could not recompute
the nine bars (review ISSUE-038).  This script publishes the mapping, applies
it to a real measurement, and writes the summary that the figure reads.

Usage
-----
    # current working copy (writes benchmarks/coverage_summary.json)
    python3 -m pytest test --cov=figtreekit --cov-report=xml
    python3 benchmarks/coverage_report.py --revision <submitted revision>

    # the archived release snapshot (writes coverage_summary_v1.1.1.json)
    python3 benchmarks/coverage_report.py \
        --xml benchmarks/coverage_v1.1.1.xml --revision v1.1.1

Every number in Figure S1 and in the manuscript's coverage sentences comes
from the JSON written here; nothing is typed into the plotting script.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from make_figures import COVERAGE_COMPONENTS, OUT, _coverage_measure  # noqa: E402


def build_summary(xml: str | None, revision: str) -> Dict[str, object]:
    rows = _coverage_measure(xml)
    st = sum(int(r["statements"]) for r in rows)
    miss = sum(int(r["missed"]) for r in rows)
    weighted = (st - miss) / st * 100 if st else 0.0
    percents = [float(r["percent"]) for r in rows]
    return {
        "revision": revision,
        "source_xml": str(Path(xml).resolve()) if xml else "auto-detected",
        "mapping": [[label, list(mods)] for label, mods in COVERAGE_COMPONENTS],
        "components": rows,
        "component_statement_weighted_overall": round(weighted, 2),
        "component_arithmetic_mean": round(sum(percents) / len(percents), 2),
        "component_statements_total": st,
        "note": ("percent = statement coverage of the component's mapped "
                 "module(s), aggregated over statements; the statement-weighted "
                 "overall value is the manuscript headline, the arithmetic mean "
                 "is reported alongside so the weighting is visible."),
    }


def as_markdown(summary: Dict[str, object]) -> str:
    """Table S15 body: component -> modules -> statements -> coverage."""
    lines = [
        "| Component (Fig. S1 bar) | Source module(s) | Executable "
        "statements | Not executed | Statement coverage |",
        "|---|---|---|---|---|",
    ]
    for c in summary["components"]:
        lines.append(
            f"| {c['label']} | {', '.join(c['modules'])} | {c['statements']} "
            f"| {c['missed']} | {c['percent']:.2f}% |")
    lines.append(
        f"| **Overall (statement-weighted over the nine components)** | "
        f"{len(summary['components'])} components | "
        f"{summary['component_statements_total']} | — | "
        f"{summary['component_statement_weighted_overall']:.2f}% |")
    lines.append(
        f"| Overall (unweighted mean of the nine components) | — | — | — | "
        f"{summary['component_arithmetic_mean']:.2f}% |")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xml", default=None,
                    help="coverage.xml to read (default: auto-detect)")
    ap.add_argument("--revision", default="working copy",
                    help="revision label recorded in the summary")
    ap.add_argument("--out", default=None,
                    help="output JSON (default: coverage_summary_v<revision>.json "
                         "when --xml names a versioned snapshot, else "
                         "coverage_summary.json)")
    ap.add_argument("--markdown", action="store_true",
                    help="also print the Table S15 mapping table")
    args = ap.parse_args(argv)

    summary = build_summary(args.xml, args.revision)
    if args.out:
        dest = Path(args.out)
    elif args.xml:
        dest = OUT / f"coverage_summary_{args.revision.replace('/', '-')}.json"
    else:
        dest = OUT / "coverage_summary.json"
    dest.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                    encoding="utf-8")

    print(f"[coverage_report] revision: {summary['revision']}")
    print(f"[coverage_report] source:   {summary['source_xml']}")
    for c in summary["components"]:
        print(f"[coverage_report]   {c['label']:<24} {', '.join(c['modules']):<32}"
              f" {c['percent']:6.2f}%  ({c['statements'] - c['missed']}/"
              f"{c['statements']} statements)")
    print(f"[coverage_report] statement-weighted overall "
          f"{summary['component_statement_weighted_overall']:.2f}%  "
          f"unweighted mean {summary['component_arithmetic_mean']:.2f}%")
    print(f"[coverage_report] wrote {dest}")
    if args.markdown:
        print()
        print(as_markdown(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
