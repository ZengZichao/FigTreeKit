"""FigTreeKit benchmark figure generator.

Reconstructed single-source-of-truth plotting module for the manuscript
(Figure 2 + supplementary Figures S1, S2, S5, S6, S7).  Each public
function reads the CSV/JSON artefacts written by ``full_benchmark.py`` and
writes a PNG + PDF pair under ``benchmarks/``.

The per-figure wrapper scripts in ``FigTreeKit-论文手稿/`` import this
module, call the relevant function, and copy the produced files.
"""
from __future__ import annotations

import csv
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
import numpy as np
from matplotlib import pyplot as plt
from matplotlib import ticker as mticker
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

# Ignore any machine-local matplotlib style (a user stylelib file otherwise
# changes line widths, colours and fonts silently), so a regenerated figure
# depends only on this file and on the measurement artefacts.
matplotlib.rcdefaults()

OUT = Path(__file__).parent

# Unit convention shared with the manuscript: 1 MB = 10^6 bytes, 1 kB = 10^3
# bytes (SI, as declared in Table 2 of the main text and required by the
# journal's units guideline).  All memory values plotted or summarised by
# this module use these divisors; ``peak_memory_bytes`` is the raw source of
# truth and no MiB (1024*1024) conversion is performed anywhere.
MB = 1_000_000
kB = 1_000



# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _read_json(path: Path):
    with path.open() as fh:
        return json.load(fh)


def _pct(part: float, whole: float) -> float:
    return (part / whole * 100) if whole else 0.0


def _t_crit(df: int, alpha: float = 0.05) -> float:
    """Two-sided 95% Student-t critical value for ``df`` degrees of freedom.

    Uses ``scipy.stats.t.ppf`` when available.  The previous implementation
    looked values up in a small table and silently fell back to the standard
    normal quantile (1.96) for any df outside that table, which produced
    confidence intervals that were narrower than the t-based ones reported in
    the manuscript.  A normal approximation with a first-order correction is
    kept only as a last resort so this function never returns 1.96 for a
    small-sample fit.
    """
    df = max(1, int(df))
    try:
        from scipy import stats as _st  # type: ignore
        return float(_st.t.ppf(1.0 - alpha / 2.0, df))
    except Exception:
        if df <= 30:
            table = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
                     6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
                     11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
                     15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
                     19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
                     23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
                     27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}
            return table[df]
        z = 1.959964
        g1 = (z ** 3 + z) / 4.0
        g2 = (5 * z ** 5 + 16 * z ** 3 + 3 * z) / 96.0
        g3 = (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / 384.0
        g4 = (79 * z ** 9 + 776 * z ** 7 + 1482 * z ** 5 - 1920 * z ** 3 - 945 * z) / 92160.0
        inv = 1.0 / df
        return z + g1 * inv + g2 * inv**2 + g3 * inv**3 + g4 * inv**4


def _linregress_ci(
    x: np.ndarray, y: np.ndarray, alpha: float = 0.05
) -> Tuple[float, float, float, float]:
    """Simple OLS on (x, y); returns (slope, intercept, lower, upper).

    The interval is a Student-t interval on ``n - 2`` degrees of freedom
    (see :func:`_t_crit`).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    mx, my = np.mean(x), np.mean(y)
    ss_xx = np.sum((x - mx) ** 2)
    slope = np.sum((x - mx) * (y - my)) / ss_xx if ss_xx else 0.0
    intercept = my - slope * mx
    y_pred = slope * x + intercept
    resid = y - y_pred
    ss_res = np.sum(resid ** 2)
    df = max(1, n - 2)
    se = math.sqrt(ss_res / df / ss_xx) if ss_xx else 0.0
    margin = _t_crit(df, alpha) * se
    return float(slope), float(intercept), float(slope - margin), float(slope + margin)


def _linregress_full(x, y, alpha: float = 0.05) -> Dict[str, float]:
    """OLS summary with slope, SE, t-based 95% CI, R^2 and degrees of freedom."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    slope, intercept, lo, hi = _linregress_ci(x, y, alpha)
    df = max(1, n - 2)
    ss_xx = float(np.sum((x - x.mean()) ** 2))
    ss_res = float(np.sum((y - (slope * x + intercept)) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    se = math.sqrt(ss_res / df / ss_xx) if ss_xx else 0.0
    return {
        "n": n, "df": df, "slope": slope, "intercept": intercept,
        "std_error": se, "ci95_low": lo, "ci95_high": hi,
        "r2": (1.0 - ss_res / ss_tot) if ss_tot else 0.0,
        "critical_value": _t_crit(df, alpha),
    }


def _savefig(fig, stem: str, dpi: int = 300):
    base = OUT / stem
    fig.savefig(f"{base}.png", dpi=dpi, bbox_inches="tight")
    fig.savefig(f"{base}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  written {base}.{{png,pdf}}")


# ---------------------------------------------------------------------------
# Figure 2  – main scaling curve
# ---------------------------------------------------------------------------

def figure2_main():
    """Export time and peak memory versus taxon count (log–log).

    Review F2/D4: every point is one independently generated tree
    (median over its technical timing replicates); size-level summaries
    and the log–log fit are drawn on top so the tree-level structure is
    visible.
    """
    rows = _read_csv(OUT / "results.csv")
    sizes = sorted({int(r["n_taxa"]) for r in rows})

    # Tree-level points (one per row = one independent tree).
    tree_n = [int(r["n_taxa"]) for r in rows]
    tree_t = [float(r["export_median_s"]) for r in rows]
    tree_mem = [int(r["peak_memory_bytes"]) / MB for r in rows]

    # Size-level summaries.
    export_medians, export_iqrs, mem_medians, mem_iqrs, mem_maxima = [], [], [], [], []
    for n in sizes:
        pool = [float(r["export_median_s"]) for r in rows if int(r["n_taxa"]) == n]
        export_medians.append(float(np.median(pool)))
        export_iqrs.append(float(np.percentile(pool, 75) - np.percentile(pool, 25)))
        mems = [int(r["peak_memory_bytes"]) / MB for r in rows
                if int(r["n_taxa"]) == n]
        mem_medians.append(float(np.median(mems)))
        mem_iqrs.append(float(np.percentile(mems, 75) - np.percentile(mems, 25)))
        mem_maxima.append(float(np.max(mems)))

    # Fits on tree-level points (technical replicates already summarized).
    log_n = np.log10(np.asarray(tree_n, float))
    log_t = np.log10(np.asarray(tree_t, float))
    slope, intercept, lo, hi = _linregress_ci(log_n, log_t)
    fit_x = np.array(sizes)
    fit_y = 10 ** (slope * np.log10(fit_x) + intercept)

    # Machine-readable fit summary consumed by the figure legend and the
    # manuscript, so no quoted statistic is hand-entered anywhere.
    log_sz = np.log10(np.asarray(sizes, float))
    summary = {
        "unit": "log10(taxon count) vs log10(quantity)",
        "mb_definition": "1 MB = 10^6 bytes (SI), as declared in Table 2",
        "source_file": "benchmarks/results.csv",
        "export_time_pooled_tree_level": _linregress_full(log_n, log_t),
        "export_time_per_size_medians": _linregress_full(log_sz, np.log10(np.asarray(export_medians))),
        "memory_per_size_maxima": _linregress_full(log_sz, np.log10(np.asarray(mem_maxima))),
        "memory_per_size_medians": _linregress_full(log_sz, np.log10(np.asarray(mem_medians))),
        "per_size": {
            "taxa": sizes,
            "export_median_s": export_medians,
            "export_iqr_s": export_iqrs,
            "memory_median_MB": mem_medians,
            "memory_maximum_MB": mem_maxima,
        },
    }
    (OUT / "figure2_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"  written {OUT/'figure2_summary.json'}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.5))

    # Panel A: export time
    ax1.scatter(tree_n, tree_t, s=18, color="#1f77b4", alpha=0.45,
                label="Independent trees")
    ax1.errorbar(sizes, export_medians, yerr=export_iqrs, fmt="o-",
                 color="#0b3d66", ecolor="#0b3d66", capsize=4,
                 markersize=6, linewidth=1.5, label="Per-size median [Q1, Q3]")
    ax1.plot(fit_x, fit_y, "--", color="#1f77b4", alpha=0.7)
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xlabel("Taxa", fontsize=11)
    ax1.set_ylabel("Export time (s)", fontsize=11)
    ax1.text(0.97, 0.03,
             f"log–log slope = {slope:.2f} (95% CI {lo:.2f}–{hi:.2f})",
             transform=ax1.transAxes, fontsize=9.5, va="bottom", ha="right",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                       edgecolor="none", alpha=0.85))
    ax1.text(-0.14, 1.04, "A", transform=ax1.transAxes, fontsize=16,
             fontweight="bold", va="top", ha="left")
    ax1.legend(fontsize=7.5, loc="upper left")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: peak memory (per independent tree + per-size median [Q1, Q3]
    # + per-size maximum, the series the memory scaling slope is fitted to).
    ax2.scatter(tree_n, tree_mem, s=18, color="#2ca02c", alpha=0.45,
                label="Independent trees")
    ax2.errorbar(sizes, mem_medians, yerr=mem_iqrs, fmt="o-",
                 color="#14612a", ecolor="#14612a", capsize=4,
                 markersize=6, linewidth=1.5, label="Per-size median [Q1, Q3]")
    mem_slope, mem_icpt, mem_lo, mem_hi = _linregress_ci(
        log_sz, np.log10(np.asarray(mem_maxima)))
    ax2.plot(fit_x, 10 ** (mem_slope * np.log10(fit_x) + mem_icpt), "--",
             color="#14612a", alpha=0.7)
    ax2.scatter(sizes, mem_maxima, marker="^", s=42, color="#8b0000",
                zorder=5, label="Per-size maximum (fitted series)")
    ax2.text(0.97, 0.03,
             f"maxima fit: slope {mem_slope:.3f}\n"
             f"95% CI {mem_lo:.3f}-{mem_hi:.3f}",
             transform=ax2.transAxes, fontsize=9, va="bottom", ha="right",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                       edgecolor="none", alpha=0.85))
    ax2.set_xscale("log")
    ax2.set_xlabel("Taxa", fontsize=11)
    ax2.set_ylabel("Traced heap allocation (MB, 10$^6$ bytes)", fontsize=11)
    ax2.text(-0.14, 1.04, "B", transform=ax2.transAxes, fontsize=16,
             fontweight="bold", va="top", ha="left")
    ax2.legend(fontsize=7.5, loc="upper left")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.yaxis.set_major_formatter(mticker.ScalarFormatter())

    plt.tight_layout()
    _savefig(fig, "figure2_main")


# ---------------------------------------------------------------------------
# Manuscript table values (Table 2 / Table 3) — emitted so the tables cannot
# drift from the archived data.
# ---------------------------------------------------------------------------

def table_values():
    """Write ``table_values.json`` with the exact quantities behind Tables 2-3.

    Dispersion definitions are stated explicitly because the two tables use
    different levels: Table 2 reports tree-level summaries over the 10
    independent trees per taxon count, while each tree's own technical
    replicates are summarized within the tree first.
    """
    rows = _read_csv(OUT / "results.csv")
    sizes = sorted({int(r["n_taxa"]) for r in rows})
    table2 = []
    for n in sizes:
        sub = [r for r in rows if int(r["n_taxa"]) == n]
        exp = [float(r["export_median_s"]) for r in sub]
        tot = [float(r["total_mean_s"]) for r in sub]
        tot_sem_within = [float(r["total_sem_s"]) for r in sub]
        mem = [int(r["peak_memory_bytes"]) / MB for r in sub]
        table2.append({
            "taxa": n,
            "n_trees": len(sub),
            "export_median_s": float(np.median(exp)),
            "export_iqr_s": float(np.percentile(exp, 75) - np.percentile(exp, 25)),
            "total_mean_s": float(np.mean(tot)),
            # Tree-level SEM: SD over the n independent trees / sqrt(n).
            "total_sem_tree_level_s": (
                float(np.std(tot, ddof=1) / math.sqrt(len(tot))) if len(tot) > 1 else 0.0
            ),
            # Kept for transparency: the mean of the within-tree (technical
            # replicate) SEMs. This is NOT the tree-level SEM and must not be
            # labelled as such.
            "total_sem_mean_of_within_tree_s": float(np.mean(tot_sem_within)),
            "heap_median_MB": float(np.median(mem)),
            "heap_maximum_MB": float(np.max(mem)),
        })

    comp = _read_csv(OUT / "competitive_results.csv")
    table3 = [{
        "taxa": int(r["n_taxa"]), "n_trees": int(r["n_trees"]),
        "figtreekit_mean_s": float(r["figtreekit_export_mean_s"]),
        "figtreekit_sem_tree_level_s": float(r["figtreekit_export_sem_s"]),
        "biophylo_mean_s": float(r["biophylo_export_mean_s"]),
        "biophylo_sem_tree_level_s": float(r["biophylo_export_sem_s"]),
        "ratio_mean_of_per_tree": float(r["ratio"]),
        "ratio_sem_s": float(r["ratio_sem_s"]),
        "ratio_min": float(r["ratio_min"]), "ratio_max": float(r["ratio_max"]),
    } for r in comp]

    payload = {
        "units": {"time_s": "seconds", "memory_MB": "1 MB = 10^6 bytes (SI)"},
        "sem_definition": (
            "SEM in both tables is the tree-level standard error: the standard "
            "deviation (ddof=1) over the n independent trees divided by sqrt(n). "
            "Within-tree technical-replicate SEMs are summarized per tree before "
            "any tree-level statistic is formed."
        ),
        "table2_source": "benchmarks/results.csv",
        "table3_source": "benchmarks/competitive_results.csv",
        "table2": table2,
        "table3": table3,
    }
    (OUT / "table_values.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  written {OUT/'table_values.json'}")
    for r in table2:
        print(f"  Table2 {r['taxa']:>6}: total {r['total_mean_s']:.4f} "
              f"± tree-level SEM {r['total_sem_tree_level_s']:.4f} "
              f"(mean of within-tree SEM {r['total_sem_mean_of_within_tree_s']:.4f})")
    return payload


# ---------------------------------------------------------------------------
# Figure S1 – test coverage
# ---------------------------------------------------------------------------

# Manuscript component label -> module file, in the order Figure S1 lists them.
# Declared once here so the figure, the machine-readable summary and the
# manuscript cannot drift apart.
COVERAGE_COMPONENTS: List[Tuple[str, List[str]]] = [
    ("Package interface", ["__init__.py"]),
    ("Command-line interface", ["_cli.py"]),
    ("Tree parsing", ["_parser.py"]),
    ("NEXUS serialization", ["_serializer.py"]),
    ("Styling layer", ["styler.py"]),
    ("Taxonomy analysis", ["taxonomy.py"]),
    ("Input validation", ["validators.py"]),
    ("Rendering", ["_renderer.py", "_appearance_post.py"]),
    ("Environment setup", ["_figtree_setup.py"]),
]

# Modules that only exist from a given revision onwards.  When a coverage
# snapshot predates them they are skipped (and reported), so the same mapping
# can be applied to the archived v1.1.1 measurement and to a current run.
COVERAGE_OPTIONAL = {"_appearance_post.py"}


def _coverage_measure(xml_path: str | None = None) -> List[Dict[str, float]]:
    """Measure statement coverage from a real coverage run.

    Source resolution order: the ``xml_path`` argument, the
    ``FIGTREEKIT_COVERAGE_XML`` environment variable, ``coverage.xml`` in the
    repository root, then the binary ``.coverage`` data file.  Versioned
    snapshots (``benchmarks/coverage_v*.xml``) are deliberately *not* on the
    implicit path: they document a past revision, so picking one silently would
    relabel an old measurement as the current one.  Pass ``--xml`` or set
    ``FIGTREEKIT_COVERAGE_XML`` to render a snapshot on purpose.

    There is deliberately no hard-coded fallback: a figure that looks like a
    measurement but is typed in by hand cannot be audited, so this function
    raises if no measurement is available.  Returns the per-component rows and
    a description of the source actually used, so that whatever is written out
    can say which revision it measured.
    """
    root = OUT.parent
    candidates = [
        Path(xml_path) if xml_path else None,
        Path(os.environ["FIGTREEKIT_COVERAGE_XML"])
        if os.environ.get("FIGTREEKIT_COVERAGE_XML") else None,
        root / "coverage.xml",
    ]
    chosen = next((c for c in candidates if c and Path(c).exists()), None)
    dot_path = root / ".coverage"
    ordered = {fname for _label, fnames in COVERAGE_COMPONENTS for fname in fnames}
    rows: List[Dict[str, float]] = []
    all_files: Dict[str, Dict[str, int]] = {}

    if chosen is not None and str(chosen).endswith(".xml"):
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(chosen))
        for cls in tree.iter("class"):
            fn = cls.get("filename") or ""
            name = os.path.basename(fn)
            if not name.endswith(".py"):
                continue
            lines = cls.find("lines")
            total = len(lines) if lines is not None else 0
            covered = sum(1 for ln in lines if ln.get("hits", "0") != "0") if lines is not None else 0
            prev = all_files.get(name)
            if prev:  # merge duplicate class entries for the same module
                total += prev["statements"]
                covered += prev["statements"] - prev["missed"]
            all_files[name] = {"statements": total, "missed": total - covered}
    elif dot_path.exists():
        try:
            import coverage  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "coverage.py is required to build Figure S1; install it or "
                "produce coverage.xml first"
            ) from exc
        cov = coverage.Coverage(data_file=str(dot_path))
        cov.load()
        measured = {Path(f).name: f for f in cov.get_data().measured_files()
                    if "figtreekit" in f and f.endswith(".py")}
        for name, path in measured.items():
            _s, stmts, _e, missing, _ex = cov.analysis2(path)
            all_files[name] = {"statements": len(stmts), "missed": len(missing)}
    else:
        raise RuntimeError(
            "No coverage measurement found. Run:\n"
            "  python3 -m pytest --cov=figtreekit --cov-report=xml\n"
            "from the repository root (this produces coverage.xml), or set "
            "FIGTREEKIT_COVERAGE_XML to an existing coverage.xml. "
            "Figure S1 is never rendered from hard-coded values."
        )

    for label, fnames in COVERAGE_COMPONENTS:
        st = miss = 0
        present: List[str] = []
        for fname in fnames:
            d = all_files.get(fname)
            if d is None:
                if fname in COVERAGE_OPTIONAL:
                    continue          # module added after this snapshot
                raise RuntimeError(f"coverage data does not contain figtreekit/{fname}")
            present.append(fname)
            st += d["statements"]
            miss += d["missed"]
        if not present:
            raise RuntimeError(f"no measured module left for component {label!r}")
        rows.append({
            "label": label, "modules": present,
            "statements": st, "missed": miss,
            "percent": _pct(st - miss, st),
        })

    # Honest bookkeeping: every measured figtreekit module is either mapped to a
    # component or reported here as excluded from the nine-component figure.
    measured = {n for n, v in all_files.items() if v["statements"]}
    unmapped = sorted(measured - ordered)
    if unmapped:
        print("[coverage] modules excluded from the nine-component figure: "
              + ", ".join(unmapped))
    source = str(chosen) if chosen is not None else str(dot_path)
    return rows, source


def _coverage_summary(rows: List[Dict[str, float]], source: str = "",
                      revision: str = "working copy") -> Dict[str, object]:
    """Statement-weighted total over the mapped components plus the all-file total."""
    st = sum(int(r["statements"]) for r in rows)
    miss = sum(int(r["missed"]) for r in rows)
    weighted = _pct(st - miss, st)
    unweighted = sum(float(r["percent"]) for r in rows) / len(rows)
    return {
        "revision": revision,
        "source_xml": source,
        "components": rows,
        "component_statement_weighted_overall": round(weighted, 2),
        "component_arithmetic_mean": round(unweighted, 1),
        "component_statements_total": st,
        "note": ("percent = statement coverage of the component's mapped "
                 "module(s), aggregated over statements; the statement-weighted "
                 "overall value is the manuscript headline, the arithmetic mean "
                 "is reported alongside so the weighting is visible."),
    }


def _coverage_from_dotfile() -> List[Tuple[str, float]]:
    """Coverage bar data, always measured (see :func:`_coverage_measure`)."""
    rows, source = _coverage_measure()
    (OUT / "coverage_summary.json").write_text(
        json.dumps(_coverage_summary(rows, source), indent=2, ensure_ascii=False),
        encoding="utf-8")
    return [(r["label"], float(r["percent"])) for r in rows]


def figure_s1():
    """Statement coverage per mapped component and the statement-weighted total."""
    data = _coverage_from_dotfile()
    labels = [d[0] for d in data]
    values = [d[1] for d in data]
    summary = _read_json(OUT / "coverage_summary.json")
    overall = float(summary["component_statement_weighted_overall"])
    labels.append("Overall (statement-weighted)")
    values.append(overall)
    colors = ["#ff9f43" if v < 80 else "#17a2b8" for v in values]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(range(len(labels)), values, color=colors, edgecolor="white")
    ax.axhline(80, color="#d62728", linestyle="--", linewidth=1.5, label="80% target line")

    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.annotate(f"{val:.0f}%",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Statement coverage (%)", fontsize=11)
    ax.set_ylim(0, 105)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right")
    plt.tight_layout()
    _savefig(fig, "figure_s1")


# ---------------------------------------------------------------------------
# Figure S2 – competitive export comparison
# ---------------------------------------------------------------------------

def figure_s2():
    """FigTreeKit vs Bio.Phylo Nexus export time."""
    rows = _read_csv(OUT / "competitive_results.csv")
    sizes = [int(r["n_taxa"]) for r in rows]
    x = np.arange(len(sizes))
    width = 0.35

    ftk = [float(r["figtreekit_export_mean_s"]) for r in rows]
    ftk_err = [float(r["figtreekit_export_sem_s"]) for r in rows]
    bio = [float(r["biophylo_export_mean_s"]) for r in rows]
    bio_err = [float(r["biophylo_export_sem_s"]) for r in rows]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    bars1 = ax.bar(x - width / 2, ftk, width, yerr=ftk_err, label="FigTreeKit",
                   color="#1f77b4", capsize=4, edgecolor="white")
    bars2 = ax.bar(x + width / 2, bio, width, yerr=bio_err, label="Bio.Phylo Nexus",
                   color="#ff7f0e", capsize=4, edgecolor="white")

    # value labels
    for bars in (bars1, bars2):
        for bar in bars:
            h = bar.get_height()
            ax.annotate(f"{h:.4f}" if h < 0.1 else f"{h:.4f}",
                        xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.set_xlabel("Taxa", fontsize=11)
    ax.set_ylabel("Export time (s)", fontsize=11)
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    _savefig(fig, "figure_s2")


# ---------------------------------------------------------------------------
# Figure S5 – pipeline stage breakdown
# ---------------------------------------------------------------------------

def figure_s5():
    """Parse / annotate / export / render timing per stage."""
    rows = _read_csv(OUT / "stage_breakdown.csv")
    sizes = [int(r["n_taxa"]) for r in rows]
    x = np.arange(len(sizes))
    width = 0.2

    parse = [float(r["parse_s"]) for r in rows]
    annotate = [float(r["annotate_s"]) for r in rows]
    export = [float(r["export_s"]) for r in rows]
    render = [float(r["render_s"]) for r in rows]

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    b1 = ax.bar(x - 1.5 * width, parse, width, label="Parse", color="#1f77b4")
    b2 = ax.bar(x - 0.5 * width, annotate, width, label="Annotate (10 clades)",
                color="#9ecae1")
    b3 = ax.bar(x + 0.5 * width, export, width, label="Export (Nexus)", color="#ff7f0e")
    b4 = ax.bar(x + 1.5 * width, render, width, label="Render (JVM, PNG)", color="#2ca02c")

    for bars in (b1, b2, b3, b4):
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                label = f"{h:.2g}"
                ax.annotate(label,
                            xy=(bar.get_x() + bar.get_width() / 2, h),
                            xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(sizes)
    ax.set_xlabel("Taxa", fontsize=11)
    ax.set_ylabel("Time per stage (s, log)", fontsize=11)
    ax.set_yscale("log")
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    plt.tight_layout()
    _savefig(fig, "figure_s5")


# ---------------------------------------------------------------------------
# Figure S6 – GTDB R232 real-dataset validation
# ---------------------------------------------------------------------------

def figure_s6():
    """GTDB parse/export time and peak memory."""
    data = _read_json(OUT / "gtdb_results.json")
    datasets = data.get("datasets", [])
    names = [f"{d['dataset']}\n({d['n_taxa']:,} taxa)" for d in datasets]
    parse_t = [d["parse_time_s"] for d in datasets]
    export_t = [d["export_time_s"] for d in datasets]
    mem_mb = [d["peak_memory_MB"] for d in datasets]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.5))
    x = np.arange(len(names))
    width = 0.35

    # Time
    b1 = ax1.bar(x - width / 2, parse_t, width, label="Parse", color="#9ecae1")
    b2 = ax1.bar(x + width / 2, export_t, width, label="Export", color="#ff7f0e")
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax1.annotate(f"{h:.2f}",
                         xy=(bar.get_x() + bar.get_width() / 2, h),
                         xytext=(0, 3), textcoords="offset points",
                         ha="center", va="bottom", fontsize=9)
    ax1.set_xticks(x)
    ax1.set_xticklabels(names, fontsize=9)
    ax1.set_ylabel("Time (s)", fontsize=11)
    ax1.legend()
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Memory
    bars = ax2.bar(x, mem_mb, color="#2ca02c")
    for bar in bars:
        h = bar.get_height()
        ax2.annotate(f"{h:.1f}",
                     xy=(bar.get_x() + bar.get_width() / 2, h),
                     xytext=(0, 3), textcoords="offset points",
                     ha="center", va="bottom", fontsize=9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(names, fontsize=9)
    ax2.set_ylabel("Peak memory (MB)", fontsize=11)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    plt.tight_layout()
    _savefig(fig, "figure_s6")


# ---------------------------------------------------------------------------
# Figure S7 – tool feature matrix
# ---------------------------------------------------------------------------

def figure_s7():
    """Feature-support heatmap for phylogenetic tree tools."""
    tools = [
        "FigTreeKit", "Bio.Phylo", "DendroPy", "ETE3", "ggtree",
        "TreeViewer", "phylotreelib", "collapseGTDB", "figtree-recolor",
    ]
    features = [
        "Newick/Nexus I/O", "FigTree annotation\ninjunction",
        "BEAST translate\nhandling", "Taxonomy-aware\ncollapse",
        "Programmatic\nstyling API", "FigTree-format\noutput",
        "CLI rendering", "Input validation",
    ]
    # Encoding: 1 = Yes, 0.5 = Partial, 0 = No
    matrix = np.array([
        [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0],
        [1.0, 0.0, 0.5, 0.0, 0.5, 0.0, 1.0, 0.0],
        [1.0, 0.5, 0.0, 0.0, 0.5, 0.5, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.5, 0.0, 0.0, 1.0, 0.0],
        [0.5, 0.5, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0],
    ])

    cmap = ListedColormap(["#ffffcc", "#41b6c4", "#081d58"])  # No, Partial, Yes
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(np.arange(len(features)))
    ax.set_yticks(np.arange(len(tools)))
    ax.set_xticklabels(features, rotation=30, ha="right", fontsize=9)
    ax.set_yticklabels(tools, fontsize=10)

    text_map = {0.0: "No", 0.5: "Partial", 1.0: "Yes"}
    for i in range(len(tools)):
        for j in range(len(features)):
            val = matrix[i, j]
            ax.text(j, i, text_map[val], ha="center", va="center",
                    color="white" if val > 0.3 else "black", fontsize=9)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("support level", rotation=270, labelpad=18)
    cbar.set_ticks([0.0, 0.5, 1.0])
    cbar.set_ticklabels(["No", "Partial", "Yes"])

    plt.tight_layout()
    _savefig(fig, "figure_s7")


REGENERATORS = {
    "table_values": table_values,
    "figure2": figure2_main,
    "s1": figure_s1,
    "s2": figure_s2,
    "s5": figure_s5,
    "s6": figure_s6,
    "s7": figure_s7,
}


def main(argv: Optional[List[str]] = None) -> int:
    """Regenerate every figure, or only the named ones.

    ``python benchmarks/make_figures.py`` regenerates all of them (the
    documented single command).  ``python benchmarks/make_figures.py s1 s6``
    regenerates the named subset, which is useful when one input artifact was
    refreshed.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    names = argv or list(REGENERATORS)
    unknown = [n for n in names if n not in REGENERATORS]
    if unknown:
        print(f"unknown target(s): {', '.join(unknown)}\n"
              f"available: {', '.join(REGENERATORS)}", file=sys.stderr)
        return 2
    for name in names:
        print(f"[make_figures] {name}")
        REGENERATORS[name]()
    print("Benchmark figure regeneration finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
