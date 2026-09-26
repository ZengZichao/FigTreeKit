"""Unified FigTreeKit benchmark suite (single frozen source of truth).

Every reported performance number is produced by THIS script from a
single run, so the summary tables and the per-tree provenance can never
drift apart.

Outputs (all under ``benchmarks/``):
    benchmark_meta.json       machine spec, versions, seeds, repeats
    results.csv               main scaling curve (balanced trees)
    results_shapes.csv        topology sweep (balanced/caterpillar/star/polytomy)
    results_annotations.csv   annotation-count scaling (a = 0 / fixed / ~n)
    competitive_results.csv   FigTreeKit vs Bio.Phylo export-only
    stage_breakdown.csv       parse / annotate / export / render per stage
    gtdb_results.json         GTDB R232 real-dataset validation
    slope_summary.json        log-log slopes with 95% CI

Usage:
    python benchmarks/full_benchmark.py [--quick] [--gtdb-dir PATH]
"""

import argparse
import csv
import gc
import io
import json
import math
import platform
import random
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.setrecursionlimit(60000)  # caterpillar trees exceed 1,000 levels deep

import numpy as np

from gtdb_paths import gtdb_data_dir

from figtreekit import FigTreeStyler, LayoutType
from figtreekit._version import __version__

OUT = Path(__file__).parent


# ---------------------------------------------------------------------------
# Tree generators
# ---------------------------------------------------------------------------

def gen_balanced(n: int, seed: int) -> str:
    rng = random.Random(seed)
    nodes = [f"T{i:05d}" for i in range(1, n + 1)]
    while len(nodes) > 1:
        i, j = rng.sample(range(len(nodes)), 2)
        a, b = rng.expovariate(100.0), rng.expovariate(100.0)
        parent = f"({nodes[i]}:{a:.6f},{nodes[j]}:{b:.6f})"
        nodes = [x for k, x in enumerate(nodes) if k not in (i, j)] + [parent]
    return nodes[0] + ";"


def gen_caterpillar(n: int, seed: int) -> str:
    rng = random.Random(seed)
    taxa = [f"T{i:05d}" for i in range(1, n + 1)]
    tree = f"({taxa[0]}:{rng.expovariate(100.0):.6f},{taxa[1]}:{rng.expovariate(100.0):.6f})"
    for t in taxa[2:]:
        tree = f"({tree}:{rng.expovariate(100.0):.6f},{t}:{rng.expovariate(100.0):.6f})"
    return tree + ";"


def gen_star(n: int, seed: int) -> str:
    rng = random.Random(seed)
    tips = ",".join(f"T{i:05d}:{rng.expovariate(100.0):.6f}" for i in range(1, n + 1))
    return f"({tips});"


def gen_polytomy(n: int, seed: int) -> str:
    """Backbone of ~sqrt(n) multifurcating nodes, each with ~sqrt(n) tips."""
    rng = random.Random(seed)
    taxa = [f"T{i:05d}" for i in range(1, n + 1)]
    k = max(2, int(math.sqrt(n)))
    clades = []
    for chunk in (taxa[i:i + k] for i in range(0, n, k)):
        clades.append("(" + ",".join(f"{t}:{rng.expovariate(100.0):.6f}" for t in chunk) + ")")
    return "(" + ",".join(f"{c}:{rng.expovariate(100.0):.6f}" for c in clades) + ");"


GENERATORS = {
    "balanced": gen_balanced,
    "caterpillar": gen_caterpillar,
    "star": gen_star,
    "polytomy": gen_polytomy,
}


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------

def _gc():
    gc.collect()


def _run_pipeline(newick: str, n_annotations: int, seed: int):
    """One parse-style-export pass WITHOUT tracemalloc (clean timings)."""
    rng = random.Random(seed)
    taxa = [f"T{i:05d}" for i in range(1, _count_tips(newick) + 1)]
    t0 = time.perf_counter()
    styler = FigTreeStyler().load_content(newick)
    t_parse = time.perf_counter() - t0
    for _ in range(n_annotations):
        group = rng.sample(taxa, min(10, len(taxa)))
        styler.set_clade_color(group, f"#{rng.randrange(0x1000000):06x}")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out.nex"
        t1 = time.perf_counter()
        styler.export(str(out))
        t_export = time.perf_counter() - t1
    return t_parse, t_export, time.perf_counter() - t0


def _peak_memory(newick: str, n_annotations: int, seed: int) -> float:
    """Peak traced memory (KB) for one pipeline pass.  tracemalloc adds
    overhead, so this is measured in a SEPARATE pass from timings."""
    tracemalloc.start()
    _run_pipeline(newick, n_annotations, seed)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1024.0


def _count_tips(newick: str) -> int:
    return newick.count("T")


def summarize(values):
    arr = np.asarray(values, dtype=float)
    return {
        "mean": float(arr.mean()),
        "sem": float(arr.std(ddof=1) / math.sqrt(len(arr))) if len(arr) > 1 else 0.0,
        "median": float(np.median(arr)),
        "iqr": float(np.percentile(arr, 75) - np.percentile(arr, 25)),
    }


def _t_crit(df: int, alpha: float = 0.05) -> float:
    """Two-sided Student-t critical value for ``df`` degrees of freedom.

    Replaces a small lookup table that silently fell back to the standard
    normal quantile (1.96) for any df outside 4-9, which made the reported
    confidence intervals narrower than true t-based intervals.
    """
    df = max(1, int(df))
    try:
        from scipy import stats as _st
        return float(_st.t.ppf(1.0 - alpha / 2.0, df))
    except Exception:
        z = 1.959964
        g1 = (z ** 3 + z) / 4.0
        g2 = (5 * z ** 5 + 16 * z ** 3 + 3 * z) / 96.0
        g3 = (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / 384.0
        g4 = (79 * z ** 9 + 776 * z ** 7 + 1482 * z ** 5 - 1920 * z ** 3 - 945 * z) / 92160.0
        i = 1.0 / df
        return z + g1 * i + g2 * i ** 2 + g3 * i ** 3 + g4 * i ** 4


def slope_ci(xs, ys):
    """Log-log OLS slope with a t-based 95% CI, plus R^2 and degrees of freedom."""
    lx, ly = np.log(np.asarray(xs, float)), np.log(np.asarray(ys, float))
    n = len(lx)
    slope, intercept = np.polyfit(lx, ly, 1)
    resid = ly - (slope * lx + intercept)
    dof = max(n - 2, 1)
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((ly - ly.mean()) ** 2).sum())
    se = math.sqrt(ss_res / dof / float(((lx - lx.mean()) ** 2).sum()))
    tcrit = _t_crit(dof)
    return {"slope": float(slope), "se": float(se),
            "ci95": [float(slope - tcrit * se), float(slope + tcrit * se)],
            "critical_value": tcrit, "r_squared": (1.0 - ss_res / ss_tot) if ss_tot else 0.0,
            "n_points": n, "df": dof}


# ---------------------------------------------------------------------------
# Benchmark sections
# ---------------------------------------------------------------------------

def run_scaling(sizes, repeats, seeds, out_csv):
    rows = []
    for n in sizes:
        for seed in seeds:
            tree = gen_balanced(n, seed)
            parses, exports, totals = [], [], []
            for r in range(repeats):
                p, e, tot = _run_pipeline(tree, 0, seed + r)
                parses.append(p); exports.append(e); totals.append(tot)
            mem_kb = _peak_memory(tree, 0, seed)
            rows.append({
                "n_taxa": n, "shape": "balanced", "seed": seed, "repeats": repeats,
                "parse_mean_s": summarize(parses)["mean"],
                "parse_sem_s": summarize(parses)["sem"],
                "export_mean_s": summarize(exports)["mean"],
                "export_sem_s": summarize(exports)["sem"],
                "total_mean_s": summarize(totals)["mean"],
                "total_sem_s": summarize(totals)["sem"],
                "export_median_s": summarize(exports)["median"],
                "export_iqr_s": summarize(exports)["iqr"],
                "peak_memory_bytes": int(mem_kb * 1024),
            })
            print(f"  scaling: n={n} seed={seed} export_median="
                  f"{summarize(exports)['median']:.4f}s")
    _write_csv(out_csv, rows)
    return rows


def run_shapes(sizes, repeats, seeds, out_csv):
    """Topology-shape sweep.

    Writes two files: the per-cell aggregates (``out_csv``)
    and the per-tree timings (``<stem>_per_tree.csv``) so the cell medians and
    the "10 independent trees x N repeats" provenance can be re-derived from
    the archive instead of being taken on trust.
    """
    rows = []
    per_tree = []
    for shape, gen in GENERATORS.items():
        for n in sizes:
            exports = []
            for seed in seeds:
                tree = gen(n, seed)
                for r in range(repeats):
                    _, e, _ = _run_pipeline(tree, 0, seed + r)
                    exports.append(e)
                    per_tree.append({
                        "shape": shape, "n_taxa": n, "seed": seed,
                        "repeat": r, "export_s": e,
                    })
            s = summarize(exports)
            rows.append({"n_taxa": n, "shape": shape, "n_trees": len(seeds),
                         "repeats_per_tree": repeats,
                         "export_mean_s": s["mean"], "export_sem_s": s["sem"],
                         "export_median_s": s["median"], "export_iqr_s": s["iqr"]})
            print(f"  shapes: {shape} n={n} median={s['median']:.4f}s")
    _write_csv(out_csv, rows)
    per_tree_csv = out_csv.with_name(out_csv.stem + "_per_tree.csv")
    _write_csv(per_tree_csv, per_tree)
    return rows


def run_annotation_scaling(out_csv):
    """a = 0 / fixed(25) / proportional(n/10) annotations."""
    rows = []
    for n in (500, 1000, 2000):
        tree = gen_balanced(n, 42)
        for label, a in (("none", 0), ("fixed25", 25), ("proportional", n // 10)):
            exports = []
            for r in range(5):
                _, e, _ = _run_pipeline(tree, a, 100 + r)
                exports.append(e)
            s = summarize(exports)
            rows.append({"n_taxa": n, "annotations": label, "a": a,
                         "export_mean_s": s["mean"], "export_sem_s": s["sem"],
                         "export_median_s": s["median"], "export_iqr_s": s["iqr"]})
            print(f"  annotations: n={n} a={label}({a}) median={s['median']:.4f}s")
    _write_csv(out_csv, rows)
    return rows


def run_competitive(sizes, repeats, seeds, out_csv):
    """Serialization-overhead microbenchmark vs Bio.Phylo (review F6).

    Paired measurements over independently generated trees (one tree per
    seed); the per-size ratio is summarized across trees, so the reported
    variability reflects cross-input uncertainty rather than technical
    timing repeats of a single tree.
    """
    from Bio import Phylo
    rows = []
    for n in sizes:
        ratios, ftk_tree, bio_tree = [], [], []
        for seed in seeds:
            tree = gen_balanced(n, seed)
            ftk, bio = [], []
            for _ in range(repeats):
                styler = FigTreeStyler().load_content(tree)
                with tempfile.TemporaryDirectory() as tmp:
                    t0 = time.perf_counter()
                    styler.export(str(Path(tmp) / "o.nex"))
                    ftk.append(time.perf_counter() - t0)
                t = Phylo.read(io.StringIO(tree), "newick")
                with tempfile.TemporaryDirectory() as tmp:
                    t0 = time.perf_counter()
                    Phylo.write(t, str(Path(tmp) / "o.nex"), "nexus")
                    bio.append(time.perf_counter() - t0)
            fmed, bmed = float(np.median(ftk)), float(np.median(bio))
            ftk_tree.append(fmed); bio_tree.append(bmed)
            ratios.append(fmed / bmed)
        rs = summarize(ratios)
        rows.append({"n_taxa": n, "n_trees": len(seeds),
                     "figtreekit_export_mean_s": float(np.mean(ftk_tree)),
                     "figtreekit_export_sem_s": summarize(ftk_tree)["sem"],
                     "biophylo_export_mean_s": float(np.mean(bio_tree)),
                     "biophylo_export_sem_s": summarize(bio_tree)["sem"],
                     "ratio": float(np.mean(ratios)),
                     "ratio_sem_s": rs["sem"],
                     "ratio_min": min(ratios), "ratio_max": max(ratios)})
        print(f"  competitive: n={n} ratio={rows[-1]['ratio']:.2f} "
              f"[{rows[-1]['ratio_min']:.2f}, {rows[-1]['ratio_max']:.2f}] "
              f"over {len(seeds)} trees")
    _write_csv(out_csv, rows)
    return rows


def run_stage_breakdown(sizes, jar_path, out_csv):
    rows = []
    for n in sizes:
        tree = gen_balanced(n, 42)
        parses, annotates, exports, renders = [], [], [], []
        for r in range(3):
            _gc()
            t0 = time.perf_counter()
            styler = FigTreeStyler().load_content(tree)
            parses.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            for i in range(10):
                styler.set_clade_color([f"T{(i * 10 + j) % n + 1:05d}" for j in range(5)],
                                       "#E91E63")
            annotates.append(time.perf_counter() - t0)
            with tempfile.TemporaryDirectory() as tmp:
                nex = Path(tmp) / "s.nex"
                t0 = time.perf_counter()
                styler.export(str(nex))
                exports.append(time.perf_counter() - t0)
                if jar_path:
                    png = Path(tmp) / "s.png"
                    t0 = time.perf_counter()
                    try:
                        subprocess.run(
                            ["java", "-jar", str(jar_path), "-graphic", "PNG",
                             str(nex), str(png)],
                            capture_output=True, timeout=180, check=True)
                        renders.append(time.perf_counter() - t0)
                    except Exception:
                        renders.append(float("nan"))
        row = {"n_taxa": n,
               "parse_s": summarize(parses)["median"],
               "annotate_s": summarize(annotates)["median"],
               "export_s": summarize(exports)["median"]}
        row["render_s"] = summarize(renders)["median"] if renders else float("nan")
        rows.append(row)
        print(f"  stages: n={n} {row}")
    _write_csv(out_csv, rows)
    return rows


def run_gtdb(gtdb_dir, out_json):
    datasets = []
    for name in ("ar53_r232.tree", "bac120_r232.tree"):
        path = Path(gtdb_dir) / name
        if not path.exists():
            print(f"  gtdb: SKIP {name} (not found under {gtdb_dir})")
            continue
        # Pass 1: clean timings (no tracemalloc overhead)
        _gc()
        t0 = time.perf_counter()
        styler = FigTreeStyler(str(path))
        t_parse = time.perf_counter() - t0
        with tempfile.TemporaryDirectory() as tmp:
            t1 = time.perf_counter()
            styler.export(str(Path(tmp) / "out.nex"))
            t_export = time.perf_counter() - t1
        # Pass 2: peak memory only
        _gc()
        tracemalloc.start()
        s2 = FigTreeStyler(str(path))
        with tempfile.TemporaryDirectory() as tmp:
            s2.export(str(Path(tmp) / "out.nex"))
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        n_taxa = sum(1 for _ in styler._parse_tree_with_biopython(
            styler._tree_content).get_terminals())
        datasets.append({
            "file": name, "dataset": name.split("_r232")[0], "n_taxa": n_taxa,
            "parse_time_s": round(t_parse, 3), "export_time_s": round(t_export, 3),
            "total_time_s": round(t_parse + t_export, 3),
            "peak_memory_MB": round(peak / 1_000_000, 1),
            "peak_memory_bytes": int(peak),
            "heap_per_taxon_kB": round(peak / 1_000 / n_taxa, 2),
        })
        print(f"  gtdb: {name} parse={t_parse:.2f}s export={t_export:.2f}s "
              f"mem={peak / 1_000_000:.1f}MB")
    payload = {
        "benchmark": "GTDB R232 real-dataset validation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        # Full machine stamp, identical in shape to benchmark_meta.json, so the
        # large-data pass carries its own provenance instead of borrowing the
        # synthetic benchmark's record.
        "cpu": _cpu_name(),
        "ram_gb": round(_ram_bytes() / 2 ** 30, 1),
        "figtreekit_version": __version__,
        "biopython": _biopython_version(),
        "java": _java_version(),
        "commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "mb_definition": "1 MB = 10^6 bytes; 1 kB = 10^3 bytes (SI)",
        "run_relationship": (
            "measured in the same frozen environment as the synthetic "
            "benchmark (see benchmark_meta.json) but in a separate pass; "
            "one timed run per dataset, so no dispersion is assessed"
        ),
        "datasets": datasets,
    }
    out_json.write_text(json.dumps(payload, indent=2))
    return payload


def _write_csv(path, rows):
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="reduced sizes for smoke runs")
    ap.add_argument("--gtdb-dir", default=gtdb_data_dir(),
                    help=("directory holding ar53_r232.tree / bac120_r232.tree; "
                          "defaults to $FTK_GTDB_DIR, then benchmarks/gtdb_data "
                          "(see benchmarks/gtdb_data/README.md)"))
    args = ap.parse_args()

    if args.quick:
        sizes, repeats, seeds = [100, 1000], 3, [42]
    else:
        # Statistical units (review D4): each (size, seed) pair is one
        # independently generated tree; the `repeats` timings per tree are
        # technical replicates summarized within-tree before inference.
        sizes, repeats, seeds = (
            [50, 100, 500, 1000, 5000, 10000], 10,
            [42, 7, 123, 2024, 314, 601, 808, 917, 1337, 5555],
        )

    jar = OUT.parent / "figtreekit" / "figtree_patched.jar"
    have_java = jar.exists() and subprocess.run(
        ["java", "-version"], capture_output=True).returncode == 0

    commit = _git_commit()
    dirty = _git_dirty()
    if dirty:
        print(f"[warn] uncommitted tracked changes present; results correspond "
              f"to commit {commit[:12]} plus local modifications")

    meta = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "figtreekit_version": __version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": _cpu_name(),
        "ram_gb": round(_ram_bytes() / 2 ** 30, 1),
        "python": platform.python_version(),
        "biopython": _biopython_version(),
        "java": _java_version() if have_java else None,
        "commit": commit,
        "git_dirty": dirty,
        "sizes": sizes, "repeats": repeats, "seeds": seeds,
        "statistical_unit": (
            "one independently generated tree per (size, seed); repeats "
            "are technical timing replicates summarized within tree "
            "(median) before inference (review D4)"
        ),
        "aggregation": (
            "per tree: mean±SEM and median/IQR over technical repeats; "
            "per size: tree-level summaries; scaling regression fitted on "
            "tree-level medians"
        ),
    }
    (OUT / "benchmark_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[meta] {meta['platform']} | {meta['cpu']} | {meta['ram_gb']} GB | "
          f"py{meta['python']} | biopython {meta['biopython']}")

    print("[1/6] main scaling (balanced)...")
    main_rows = run_scaling(sizes, repeats, seeds, OUT / "results.csv")

    print("[2/6] topology sweep...")
    shape_sizes = [s for s in sizes if s <= 5000] if not args.quick else sizes
    run_shapes(shape_sizes, max(3, repeats // 3), seeds, OUT / "results_shapes.csv")

    print("[3/6] annotation scaling...")
    run_annotation_scaling(OUT / "results_annotations.csv")

    print("[4/6] competitive vs Bio.Phylo...")
    run_competitive(sizes, repeats, seeds, OUT / "competitive_results.csv")

    print("[5/6] stage breakdown...")
    run_stage_breakdown([100, 500, 1000, 2000], jar if have_java else None,
                        OUT / "stage_breakdown.csv")

    print("[6/6] GTDB R232...")
    run_gtdb(args.gtdb_dir, OUT / "gtdb_results.json")

    # Slope summary from the main scaling curve.  Review D4: regression is
    # fitted at the tree level — each point is the median export time of one
    # independently generated tree (technical repeats already summarized).
    tree_points = [(r["n_taxa"], r["export_median_s"]) for r in main_rows]
    xs_all = [p[0] for p in tree_points]
    ys_all = [p[1] for p in tree_points]
    export_slope = slope_ci(xs_all, ys_all)
    export_slope["unit"] = "tree-level median over technical replicates"
    export_slope["n_points"] = len(tree_points)
    slopes = {"export_vs_taxa_loglog": export_slope}
    mem_by_n = {}
    exp_med_by_n = {}
    for r in main_rows:
        mem_by_n.setdefault(r["n_taxa"], []).append(r["peak_memory_bytes"])
        exp_med_by_n.setdefault(r["n_taxa"], []).append(r["export_median_s"])
    xs = sorted(mem_by_n)
    my = [float(np.max(mem_by_n[x])) for x in xs]
    mem_slope = slope_ci(xs, my)
    mem_slope["unit"] = "per-size maximum over independent trees"
    slopes["memory_vs_taxa_loglog"] = mem_slope
    mem_median_slope = slope_ci(xs, [float(np.median(mem_by_n[x])) for x in xs])
    mem_median_slope["unit"] = "per-size median over independent trees"
    slopes["memory_vs_taxa_loglog_per_size_medians"] = mem_median_slope
    exp_median_slope = slope_ci(xs, [float(np.median(exp_med_by_n[x])) for x in xs])
    exp_median_slope["unit"] = "per-size median of tree-level export medians"
    slopes["export_vs_taxa_loglog_per_size_medians"] = exp_median_slope
    slopes["aggregation_note"] = (
        "pooled fits use one point per independent tree (n = number of trees); "
        "per-size fits use one point per taxon count. All intervals are "
        "Student-t on n-2 degrees of freedom and ignore the nesting of trees "
        "within size levels."
    )
    (OUT / "slope_summary.json").write_text(json.dumps(slopes, indent=2))
    print(f"[slope] export: {slopes['export_vs_taxa_loglog']}")
    print(f"[slope] memory: {slopes['memory_vs_taxa_loglog']}")
    print("done.")


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=OUT.parent,
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _git_dirty():
    """True if tracked files have uncommitted changes (untracked ignored)."""
    try:
        out = subprocess.run(["git", "status", "--porcelain",
                              "--untracked-files=no"],
                             cwd=OUT.parent, capture_output=True, text=True,
                             timeout=10)
        return bool(out.stdout.strip()) if out.returncode == 0 else None
    except Exception:
        return None


def _cpu_name():
    try:
        out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return platform.processor() or "unknown"


def _ram_bytes():
    try:
        out = subprocess.run(["sysctl", "-n", "hw.memsize"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return int(out.stdout.strip())
    except Exception:
        pass
    return 0


def _biopython_version():
    import Bio
    return Bio.__version__


def _java_version():
    try:
        out = subprocess.run(["java", "-version"], capture_output=True,
                             text=True, timeout=10)
        return (out.stderr or out.stdout).splitlines()[0]
    except Exception:
        return None


if __name__ == "__main__":
    main()
