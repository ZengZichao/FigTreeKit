"""GTDB R232 end-to-end styling workflow (main text Section 3.4).

Reproducible, version-controllable replacement for the manual FigTree
GUI workflow: colour every phylum and batch-collapse every validated
monophyletic order of the GTDB R232 archaeal reference tree.

The script prints a full audit report (mapped/unmapped tips, per-rank
completeness, monophyletic/non-monophyletic/skipped/collapsed counts)
so that every biological decision is reviewable.

Usage:
    python examples/05_gtdb_workflow.py [TREE] [METADATA] [OUTDIR]

Defaults assume the repository layout:
    TREE     = ../../参考数据-GTDB-R232/ar53_r232.tree
    METADATA = ../../参考数据-GTDB-R232/ar53_r232_metadata.tsv
"""

import csv
import sys
import tempfile
from pathlib import Path

from figtreekit import FigTreeStyler, LayoutType

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TREE = REPO_ROOT.parent / "参考数据-GTDB-R232" / "ar53_r232.tree"
DEFAULT_META = REPO_ROOT.parent / "参考数据-GTDB-R232" / "ar53_r232_metadata.tsv"


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

    styler = FigTreeStyler(str(tree_path))
    styler.set_layout(LayoutType.RADIAL)

    # ── Completeness audit (required before trusting any monophyly call) ──
    comp = styler.check_taxonomy_completeness(mapping_file=mapping)
    print(f"[audit] completeness summary: "
          f"{ {k: v for k, v in comp.items() if isinstance(v, (int, float))} }")

    # ── Phylum-level styling ──
    phyla = styler.analyze_taxonomy(
        mapping_file=mapping, rank="phylum", style_monophyletic=True)
    print(f"[phylum] monophyletic={len(phyla['monophyletic'])} "
          f"non_monophyletic={len(phyla['non_monophyletic'])} "
          f"unmapped_tips={len(phyla['unmapped'])}")

    # ── Order-level batch collapse (validated monophyletic only) ──
    orders = styler.analyze_taxonomy(
        mapping_file=mapping, rank="order", style_monophyletic=False)
    collapsed = 0
    for group in orders["monophyletic"]:
        styler.collapse_by_group(group, mapping_file=mapping)
        collapsed += 1
    print(f"[order] groups={orders['summary'].get('total_groups', '?')} "
          f"monophyletic={len(orders['monophyletic'])} "
          f"non_monophyletic(skipped)={len(orders['non_monophyletic'])} "
          f"collapsed={collapsed}")

    out_nex = outdir / "gtdb_ar53_styled.nex"
    styler.export(str(out_nex))
    print(f"[done] exported {out_nex}")

    # Optional rendering (requires Java + bundled patched JAR)
    try:
        out_pdf = outdir / "gtdb_ar53_styled.pdf"
        styler.render(str(out_pdf), format="PDF", width=2400, height=1600)
        print(f"[done] rendered {out_pdf}")
    except Exception as exc:  # rendering is optional
        print(f"[skip] rendering unavailable: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
