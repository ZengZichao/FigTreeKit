"""BEAST-style time-calibrated tree workflow (main text Code 1 caption).

Demonstrates FigTreeKit on the published 700-tip time-calibrated
archaeal-bacterial phylogeny of Moody et al. (2025), supplied as
BEAST-style annotated NEXUS with 699 node-age confidence-interval
annotations of the form ``[&95%={lo, hi}]``:

  Moody, E.R.R., Williams, T.A., Alvarez-Carretero, S., Szollosi, G.J.,
  Pisani, D., Lenton, T.M., Donoghue, P.C.J. (2025). The emergence of
  metabolisms through Earth history and implications for biospheric
  evolution. Phil. Trans. R. Soc. B 380: 20240097.
  https://doi.org/10.1098/rstb.2024.0097

The tip labels of the bundled copy were renamed into GTDB embedded
format A so that the tree exercises the taxonomy-aware workflow; the
topology, node ages, and annotations are unchanged (see
examples/data/README.md for the full provenance statement).

The script prints a full audit report (tips, phylum-level monophyly
counts, unmapped tips, and the 95% CI comment count before/after
export) corresponding to Supplementary Table S11.

Usage:
    python examples/06_beast_laca_workflow.py [TREE] [OUTDIR]

Defaults assume the repository layout:
    TREE   = examples/data/FigTree_withLACA_CLK_95CI.tree.recover
    OUTDIR = examples/output
"""

import sys
from pathlib import Path

from Bio import Phylo

from figtreekit import FigTreeStyler, LayoutType
from figtreekit.taxonomy import extend_rank_prefixes

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TREE = (REPO_ROOT / "examples" / "data" /
                "FigTree_withLACA_CLK_95CI.tree.recover")

CI_MARKER = "[&95%="


def count_ci_comments(path: Path) -> int:
    """Count BEAST-style ``[&95%={lo, hi}]`` node-age annotations."""
    return path.read_text(encoding="utf-8").count(CI_MARKER)


def main() -> int:
    tree_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TREE
    outdir = (Path(sys.argv[2]) if len(sys.argv) > 2
              else REPO_ROOT / "examples" / "output")
    outdir.mkdir(parents=True, exist_ok=True)

    if not tree_path.exists():
        print(f"[error] tree not found: {tree_path}")
        return 1

    # ── Custom rank prefixes matching the embedded format A labels ──
    # (equivalent of CLI ``--taxonomy-levels``; instance-scoped
    # TaxonomyMapper(prefixes=...) is preferred in long-running apps)
    extend_rank_prefixes({
        "d": "domain", "sp": "superphylum", "p": "phylum",
        "c": "class", "o": "order", "f": "family", "g": "genus",
    })

    ci_in = count_ci_comments(tree_path)

    styler = FigTreeStyler(str(tree_path))
    styler.set_layout(LayoutType.POLAR)

    # ── Completeness audit (required before trusting any monophyly call) ──
    comp = styler.check_taxonomy_completeness()
    print(f"[audit] completeness summary: "
          f"{ {k: v for k, v in comp.items() if isinstance(v, (int, float))} }")

    # ── Phylum-level styling on embedded format A taxonomy ──
    phyla = styler.analyze_taxonomy(rank="phylum", style_monophyletic=True)
    print(f"[phylum] total_groups={phyla['summary'].get('total_groups', '?')} "
          f"monophyletic={len(phyla['monophyletic'])} "
          f"non_monophyletic={len(phyla['non_monophyletic'])} "
          f"unmapped_tips={len(phyla['unmapped'])}")

    out_nex = outdir / "beast_laca_styled.nex"
    styler.export(str(out_nex))
    ci_out = count_ci_comments(out_nex)
    print(f"[done] exported {out_nex}")
    n_tips = len(Phylo.read(str(tree_path), "nexus").get_terminals())
    print(f"[meta] tips={n_tips} "
          f"95% CI comments in -> out: {ci_in} -> {ci_out} "
          f"({'no loss' if ci_in == ci_out else 'LOSS DETECTED'})")

    # Optional rendering (requires Java + bundled patched JAR)
    try:
        out_pdf = outdir / "beast_laca_styled.pdf"
        styler.render(str(out_pdf), format="PDF", width=2400, height=1600)
        print(f"[done] rendered {out_pdf} (polar layout)")
    except Exception as exc:  # rendering is optional
        print(f"[skip] rendering unavailable: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
