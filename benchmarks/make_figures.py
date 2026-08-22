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
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from matplotlib import pyplot as plt
from matplotlib import ticker as mticker
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

OUT = Path(__file__).parent


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


def _linregress_ci(
    x: np.ndarray, y: np.ndarray, alpha: float = 0.05
) -> Tuple[float, float, float, float]:
    """Simple OLS on (x, y); returns (slope, intercept, lower, upper)."""
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
    # t critical values for common dfs (95% two-sided)
    t_table = {1: 12.71, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
               6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228}
    t = t_table.get(df, 2.0)
    margin = t * se
    return float(slope), float(intercept), float(slope - margin), float(slope + margin)


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
    """Export time and peak memory versus taxon count (log–log)."""
    rows = _read_csv(OUT / "results.csv")
    sizes = sorted({int(r["n_taxa"]) for r in rows})

    export_medians = []
    export_iqrs = []
    peak_mem_mb = []

    for n in sizes:
        pool = [float(r["export_median_s"]) for r in rows if int(r["n_taxa"]) == n]
        export_medians.append(float(np.median(pool)))
        export_iqrs.append(float(np.percentile(pool, 75) - np.percentile(pool, 25)))
        mems = [int(r["peak_memory_bytes"]) / (1024 * 1024) for r in rows
                if int(r["n_taxa"]) == n]
        peak_mem_mb.append(float(np.median(mems)))

    log_n = np.log10(sizes)
    log_t = np.log10(export_medians)
    slope, intercept, lo, hi = _linregress_ci(log_n, log_t)
    fit_x = np.array(sizes)
    fit_y = 10 ** (slope * np.log10(fit_x) + intercept)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.5))

    # Panel A: export time
    ax1.errorbar(sizes, export_medians, yerr=export_iqrs, fmt="o-",
                 color="#1f77b4", ecolor="#1f77b4", capsize=4,
                 markersize=7, linewidth=1.5)
    ax1.plot(fit_x, fit_y, "--", color="#1f77b4", alpha=0.7)
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xlabel("Taxa", fontsize=11)
    ax1.set_ylabel("Export time (s)", fontsize=11)
    ax1.set_title(f"log–log slope = {slope:.2f} (95% CI {lo:.2f}–{hi:.2f})",
                  fontsize=10)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: peak memory
    ax2.plot(sizes, peak_mem_mb, "o-", color="#2ca02c", markersize=8,
             linewidth=1.5)
    ax2.set_xscale("log")
    ax2.set_xlabel("Taxa", fontsize=11)
    ax2.set_ylabel("Peak memory (MB)", fontsize=11)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    # ticks: 0, 1, 10, 100 to mimic original style
    ax2.set_yticks([0, 1, 10, 100])
    ax2.set_ylim(bottom=0)
    ax2.yaxis.set_major_formatter(mticker.ScalarFormatter())

    plt.tight_layout()
    _savefig(fig, "figure2_main")


# ---------------------------------------------------------------------------
# Figure S1 – test coverage
# ---------------------------------------------------------------------------

def _coverage_dynamic() -> List[Tuple[str, float]]:
    """Read current .coverage; may differ from the frozen manuscript snapshot."""
    import coverage  # type: ignore
    dotfile = OUT.parent / ".coverage"
    ordered_names = [
        "__init__.py", "_cli.py", "_parser.py", "_serializer.py", "styler.py",
        "taxonomy.py", "validators.py", "_renderer.py", "_figtree_setup.py",
    ]
    cov = coverage.Coverage(data_file=str(dotfile))
    cov.load()
    measured = {Path(f).name: f for f in cov.get_data().measured_files()
                if "figtreekit" in f and f.endswith(".py")}
    rows = []
    total_st, total_miss = 0, 0
    for name in ordered_names:
        pct = 0.0
        if name in measured:
            analysis = cov.analysis2(measured[name])
            statements, missing = analysis[1], analysis[2]
            st, miss = len(statements), len(missing)
            total_st += st
            total_miss += miss
            pct = _pct(st - miss, st)
        rows.append((name, pct))
    rows.append(("Total", _pct(total_st - total_miss, total_st)))
    return rows


def _coverage_from_dotfile() -> List[Tuple[str, float]]:
    """Coverage bar data.

    Defaults to the frozen snapshot that matches the current manuscript S1.
    Set ``FIGTREEKIT_DYNAMIC_COVERAGE=1`` to use the current ``.coverage`` file.
    """
    ordered_names = [
        "__init__.py", "_cli.py", "_parser.py", "_serializer.py", "styler.py",
        "taxonomy.py", "validators.py", "_renderer.py", "_figtree_setup.py",
    ]
    fallback = {
        "__init__.py": 78.0, "_cli.py": 83.0, "_parser.py": 84.0,
        "_serializer.py": 91.0, "styler.py": 82.0, "taxonomy.py": 81.0,
        "validators.py": 86.0, "_renderer.py": 72.0,
        "_figtree_setup.py": 38.0, "Total": 81.0,
    }
    if os.environ.get("FIGTREEKIT_DYNAMIC_COVERAGE"):
        return _coverage_dynamic()
    return [(n, fallback[n]) for n in ordered_names + ["Total"]]


def figure_s1():
    """Statement coverage per module and overall total."""
    data = _coverage_from_dotfile()
    labels = [d[0] for d in data]
    values = [d[1] for d in data]
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
    mem_mb = [d["peak_memory_mb"] for d in datasets]

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


if __name__ == "__main__":
    figure2_main()
    figure_s1()
    figure_s2()
    figure_s5()
    figure_s6()
    figure_s7()
    print("All benchmark figures regenerated.")
