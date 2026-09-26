"""GTDB R232 end-to-end styling workflow.

Reproducible, version-controllable replacement for the manual FigTree
GUI workflow: colour every phylum and batch-collapse every validated
monophyletic order of the GTDB R232 archaeal reference tree.

This script is the figure-generation workflow for Figure 3: it writes
(and optionally renders) both panels — the fully expanded radial layout
(panel A) and the rectilinear layout with order-level collapse (panel B)
— from two independently styled copies of the same input tree, after a
shared completeness audit gates every downstream verdict.

The script prints a full audit report (mapped/unmapped tips, per-rank
completeness, monophyletic/non-monophyletic/skipped/collapsed counts)
so that every biological decision is reviewable.

Usage:
    python examples/05_gtdb_workflow.py [TREE] [METADATA] [OUTDIR]

Defaults assume the repository layout:
    TREE     = benchmarks/gtdb_data/ar53_r232.tree   (or $FTK_GTDB_DIR)
    METADATA = benchmarks/gtdb_data/ar53_r232_metadata.tsv
"""

import csv
import os
import sys
import tempfile
from pathlib import Path

from figtreekit import FigTreeStyler, LayoutType

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = os.environ.get("FTK_GTDB_DIR") or str(REPO_ROOT / "benchmarks" / "gtdb_data")
DEFAULT_TREE = Path(DEFAULT_DIR) / "ar53_r232.tree"
DEFAULT_META = Path(DEFAULT_DIR) / "ar53_r232_metadata.tsv"


def build_two_column_mapping(metadata_tsv: Path) -> str:
    """Reduce GTDB metadata (many columns) to the two-column mapping
    format accepted by FigTreeKit: ``accession<TAB>d__...;p__...;...``."""
    out = tempfile.NamedTemporaryFile(
        mode="w", suffix=".tsv", delete=False, encoding="utf-8")
    n = 0
    with open(metadata_tsv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            tax = (row.get("gtdb_taxonomy") or "").strip()
            acc = (row.get("accession") or "").strip()
            if acc and tax:
                out.write(f"{acc}\t{tax}\n")
                n += 1
    out.close()
    print(f"[prep] wrote 2-column mapping for {n} genomes -> {out.name}")
    return out.name


def main() -> int:
    tree_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TREE
    meta_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_META
    outdir = Path(sys.argv[3]) if len(sys.argv) > 3 else REPO_ROOT / "examples" / "output"
    outdir.mkdir(parents=True, exist_ok=True)

    if not tree_path.exists() or not meta_path.exists():
        print(f"[error] GTDB data not found:\n  {tree_path}\n  {meta_path}")
        print("Download GTDB R232 (ar53) or pass TREE/METADATA paths.")
        return 1

    mapping = build_two_column_mapping(meta_path)

    # ------------------------------------------------------------------
    # Shared audit (the completeness gate precedes every verdict)
    # ------------------------------------------------------------------
    audit_styler = FigTreeStyler(str(tree_path))
    comp = audit_styler.check_taxonomy_completeness(mapping_file=mapping)
    print(f"[audit] completeness summary: "
          f"{ {k: v for k, v in comp.items() if isinstance(v, (int, float))} }")
    orders = audit_styler.analyze_taxonomy(
        mapping_file=mapping, rank="order", style_monophyletic=False)
    n_orders = len(orders["monophyletic"]) + len(orders["non_monophyletic"])
    print(f"[order] groups={orders['summary'].get('total_groups', n_orders)} "
          f"monophyletic={len(orders['monophyletic'])} "
          f"non_monophyletic(skipped)={len(orders['non_monophyletic'])}")

    # ------------------------------------------------------------------
    # Panel A: fully expanded radial layout, phylum-level coloring
    # (Figure 3A; no collapse applied)
    # ------------------------------------------------------------------
    styler_a = FigTreeStyler(str(tree_path))
    styler_a.set_layout(LayoutType.RADIAL)
    phyla = styler_a.analyze_taxonomy(
        mapping_file=mapping, rank="phylum", style_monophyletic=True)
    print(f"[phylum] monophyletic={len(phyla['monophyletic'])} "
          f"non_monophyletic={len(phyla['non_monophyletic'])} "
          f"unmapped_tips={len(phyla['unmapped'])}")
    out_a_nex = outdir / "gtdb_ar53_radial_expanded.nex"
    styler_a.export(str(out_a_nex))
    print(f"[done] exported {out_a_nex}")

    # ------------------------------------------------------------------
    # Panel B: rectilinear layout with order-level clade collapse and
    # phylum-level coloring (Figure 3B; highlighting intentionally not
    # applied — stock FigTree 1.4.4 is unstable when rectilinear layout,
    # collapse, and highlighting are combined)
    # ------------------------------------------------------------------
    styler_b = FigTreeStyler(str(tree_path))
    styler_b.set_layout(LayoutType.RECTILINEAR)
    styler_b.analyze_taxonomy(
        mapping_file=mapping, rank="phylum", style_monophyletic=True)
    collapsed = 0
    for group in orders["monophyletic"]:
        styler_b.collapse_by_group(group, mapping_file=mapping)
        collapsed += 1
    print(f"[order] collapsed={collapsed}")
    out_b_nex = outdir / "gtdb_ar53_rectilinear_collapsed.nex"
    styler_b.export(str(out_b_nex))
    print(f"[done] exported {out_b_nex}")

    # ── Machine-readable audit emitted alongside the release outputs ────────
    try:
        from _audit import write_audit
        write_audit(out_b_nex.with_suffix(""), rank="order", groups=orders,
                    completeness=comp, nexus_path=out_b_nex,
                    extra={"workflow_script": "examples/05_gtdb_workflow.py",
                           "expanded_nexus": str(out_a_nex)})
    except Exception as exc:
        print(f"[audit] skipped: {exc}")

    # Optional rendering (requires Java + bundled patched JAR)
    for styler, name in ((styler_a, "gtdb_ar53_radial_expanded.pdf"),
                         (styler_b, "gtdb_ar53_rectilinear_collapsed.pdf")):
        try:
            out_pdf = outdir / name
            styler.render(str(out_pdf), format="PDF", width=2400, height=1600)
            print(f"[done] rendered {out_pdf}")
        except Exception as exc:  # rendering is optional
            print(f"[skip] rendering unavailable: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
