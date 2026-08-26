"""Performance benchmark for FigTreeKit.

Measures parse time, export time, and peak memory vs number of taxa.
Includes competitive benchmarks against Bio.Phylo Nexus export.

Usage:
    python benchmarks/performance.py
    python benchmarks/performance.py --output benchmarks/results.csv
    python benchmarks/performance.py --sizes 10 50 100 500 1000 5000 10000
"""

import csv
import gc
import io
import math
import random
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from figtreekit import FigTreeStyler, LayoutType


def generate_tree(n_taxa: int, seed: int = 42) -> str:
    """Generate a random Newick tree with n taxa (balanced topology)."""
    rng = random.Random(seed)
    taxa = [f"T{i:05d}" for i in range(1, n_taxa + 1)]
    nodes = list(taxa)
    while len(nodes) > 1:
        i, j = rng.sample(range(len(nodes)), 2)
        bl_a = round(rng.expovariate(1.0 / 0.01), 6)
        bl_b = round(rng.expovariate(1.0 / 0.01), 6)
        parent = f"({nodes[i]}:{bl_a},{nodes[j]}:{bl_b})"
        remaining = [n for k, n in enumerate(nodes) if k not in (i, j)]
        remaining.append(parent)
        nodes = remaining
    return nodes[0] + ";"


def generate_caterpillar_tree(n_taxa: int, seed: int = 42) -> str:
    """Generate a caterpillar (pectinate / extremely unbalanced) Newick tree.

    A caterpillar tree has the form ((...(T1,T2),T3),...,Tn), producing
    a maximally deep topology. This contrasts with the balanced trees from
    generate_tree() and stresses recursive tree-walking algorithms
    (e.g. Bio.Phylo's common_ancestor()).
    """
    rng = random.Random(seed)
    taxa = [f"T{i:05d}" for i in range(1, n_taxa + 1)]
    # Start with the last two taxa as a pair
    bl_a = round(rng.expovariate(1.0 / 0.01), 6)
    bl_b = round(rng.expovariate(1.0 / 0.01), 6)
    tree = f"({taxa[0]}:{bl_a},{taxa[1]}:{bl_b})"
    # Iteratively add remaining taxa on the right side
    for idx in range(2, n_taxa):
        bl_tree = round(rng.expovariate(1.0 / 0.01), 6)
        bl_taxon = round(rng.expovariate(1.0 / 0.01), 6)
        tree = f"({tree}:{bl_tree},{taxa[idx]}:{bl_taxon})"
    return tree + ";"


def _mean(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def measure_peak_memory(func, *args, **kwargs) -> int:
    """Measure peak memory (bytes) of a function call using tracemalloc."""
    gc.collect()
    tracemalloc.start()
    result = func(*args, **kwargs)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.collect()
    return peak


def _sem(values: list) -> float:
    """Standard Error of the Mean."""
    if len(values) < 2:
        return 0.0
    return _std(values) / math.sqrt(len(values))


def benchmark_parse(tree_str: str, n_repeats: int = 10) -> dict:
    """Measure FigTreeKit parse time in seconds."""
    times = []
    for _ in range(n_repeats):
        start = time.perf_counter()
        styler = FigTreeStyler()
        styler.load_content(tree_str)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    return {"mean": _mean(times), "sem": _sem(times)}


def benchmark_export(styler: FigTreeStyler, n_repeats: int = 10) -> dict:
    """Measure FigTreeKit export time in seconds."""
    times = []
    for _ in range(n_repeats):
        with tempfile.NamedTemporaryFile(suffix=".nex", delete=True) as f:
            start = time.perf_counter()
            styler.export(f.name)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
    return {"mean": _mean(times), "sem": _sem(times)}


def benchmark_biopylo_nexus_export(tree_str: str, n_repeats: int = 10) -> dict:
    """Measure Bio.Phylo Nexus write time for comparison."""
    from Bio import Phylo
    times = []
    for _ in range(n_repeats):
        clean = tree_str
        tree = list(Phylo.parse(io.StringIO(clean), 'newick'))[0]
        with tempfile.NamedTemporaryFile(suffix=".nex", delete=True) as f:
            start = time.perf_counter()
            Phylo.write(tree, f.name, 'nexus')
            elapsed = time.perf_counter() - start
            times.append(elapsed)
    return {"mean": _mean(times), "sem": _sem(times)}


def benchmark_parse_and_export(n_taxa: int, n_repeats: int = 10) -> dict:
    """Full FigTreeKit benchmark: generate tree, parse, style, export."""
    tree_str = generate_tree(n_taxa)

    parse_result = benchmark_parse(tree_str, n_repeats)

    styler = FigTreeStyler()
    styler.load_content(tree_str)
    styler.set_layout(LayoutType.POLAR)
    styler.set_tip_labels(is_shown=True, font_size=10)
    styler.set_appearance(branch_line_width=1.5)
    
    # Add some annotations to trigger the full Bio.Phylo round-trip
    taxa = [f"T{i:05d}" for i in range(1, min(n_taxa + 1, 6))]
    if len(taxa) >= 2:
        styler.highlight_clade(taxa[:2], color="#FF0000")
        styler.set_clade_color(taxa[2:4] if len(taxa) >= 4 else taxa[:2], color="#00FF00")
    
    export_result = benchmark_export(styler, n_repeats)

    with tempfile.NamedTemporaryFile(suffix=".nex", delete=True) as tmp:
        peak_mem = measure_peak_memory(styler.export, tmp.name)

    return {
        "n_taxa": n_taxa,
        "tree_size_bytes": len(tree_str),
        "parse_time_mean_s": round(parse_result["mean"], 6),
        "parse_time_sem_s": round(parse_result["sem"], 6),
        "export_time_mean_s": round(export_result["mean"], 6),
        "export_time_sem_s": round(export_result["sem"], 6),
        "total_time_mean_s": round(parse_result["mean"] + export_result["mean"], 6),
        "total_time_sem_s": round(
            math.sqrt(parse_result["sem"] ** 2 + export_result["sem"] ** 2), 6
        ),
        "peak_memory_bytes": peak_mem,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="FigTreeKit performance benchmark")
    parser.add_argument(
        "--output", "-o",
        default="benchmarks/results.csv",
        help="Output CSV file path",
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=[10, 50, 100, 500, 1000, 5000, 10000],
        help="Taxon counts to benchmark",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=10,
        help="Number of repeats per measurement",
    )
    parser.add_argument(
        "--compare-biopylo",
        action="store_true",
        default=False,
        help="Also run Bio.Phylo Nexus export benchmark for comparison",
    )
    parser.add_argument(
        "--caterpillar",
        action="store_true",
        default=False,
        help="Also benchmark caterpillar (pectinate) tree topology",
    )
    parser.add_argument(
        "--jvm-cold-start",
        action="store_true",
        default=False,
        help="Measure JVM cold-start time for FigTree rendering context",
    )
    args = parser.parse_args()

    results = []
    print(f"{'n_taxa':>8} {'parse(s)':>18} {'export(s)':>18} {'total(s)':>18} {'peak_mem':>12} {'tree(KB)':>10}")
    print("-" * 88)

    for n in args.sizes:
        result = benchmark_parse_and_export(n, args.repeats)
        results.append(result)
        print(
            f"{result['n_taxa']:>8} "
            f"{result['parse_time_mean_s']:>8.4f} ± {result['parse_time_sem_s']:.4f} "
            f"{result['export_time_mean_s']:>8.4f} ± {result['export_time_sem_s']:.4f} "
            f"{result['total_time_mean_s']:>8.4f} ± {result['total_time_sem_s']:.4f} "
            f"{result['peak_memory_bytes'] / 1024:>8.1f} KB"
            f"{result['tree_size_bytes'] / 1024:>10.1f}"
        )

    # Write CSV
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults written to: {out_path}")

    # Competitive benchmark against Bio.Phylo
    if args.compare_biopylo:
        print("\n--- Competitive Benchmark: FigTreeKit vs Bio.Phylo Nexus Export ---")
        print(f"{'n_taxa':>8} {'FigTreeKit(s)':>14} {'Bio.Phylo(s)':>14} {'Ratio':>10}")
        print("-" * 50)

        competitive_rows = []
        for n in args.sizes:
            tree_str = generate_tree(n)

            # FigTreeKit export-only (styling applied, no annotation injection;
            # this is deliberately lighter than the Table-2 full pipeline)
            styler = FigTreeStyler()
            styler.load_content(tree_str)
            styler.set_layout(LayoutType.POLAR)
            styler.set_tip_labels(is_shown=True, font_size=10)
            styler.set_appearance(branch_line_width=1.5)
            pyfig_result = benchmark_export(styler, args.repeats)

            # Bio.Phylo Nexus export
            biopylo_result = benchmark_biopylo_nexus_export(tree_str, args.repeats)

            # Ratio: FigTreeKit / Bio.Phylo (higher means FigTreeKit is slower)
            ratio = pyfig_result["mean"] / biopylo_result["mean"] if biopylo_result["mean"] > 0 else float('inf')
            print(
                f"{n:>8} "
                f"{pyfig_result['mean']:>8.6f} ± {pyfig_result['sem']:.6f} "
                f"{biopylo_result['mean']:>8.6f} ± {biopylo_result['sem']:.6f} "
                f"{ratio:>8.2f}x"
            )
            competitive_rows.append({
                "n_taxa": n,
                "figtreekit_export_mean_s": round(pyfig_result["mean"], 6),
                "figtreekit_export_sem_s": round(pyfig_result["sem"], 6),
                "biophylo_export_mean_s": round(biopylo_result["mean"], 6),
                "biophylo_export_sem_s": round(biopylo_result["sem"], 6),
                "ratio": round(ratio, 3),
            })

        # Persist raw competitive data alongside the main results so the
        # manuscript's Table 3 is backed by an auditable artefact.
        comp_path = out_path.parent / "competitive_results.csv"
        with open(comp_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=competitive_rows[0].keys())
            writer.writeheader()
            writer.writerows(competitive_rows)
        print(f"Competitive results written to: {comp_path}")

    # Caterpillar (pectinate) tree topology benchmark
    if args.caterpillar:
        print("\n--- Caterpillar (Pectinate) Tree Topology Benchmark ---")
        print(f"{'n_taxa':>8} {'Topology':>12} {'parse(s)':>18} {'export(s)':>18} {'total(s)':>18}")
        print("-" * 78)

        for n in args.sizes:
            if n < 2:
                continue
            # Balanced tree
            bal_tree = generate_tree(n)
            styler_bal = FigTreeStyler()
            styler_bal.load_content(bal_tree)
            styler_bal.set_layout(LayoutType.POLAR)
            styler_bal.set_tip_labels(is_shown=True, font_size=10)
            styler_bal.set_appearance(branch_line_width=1.5)
            bal_export = benchmark_export(styler_bal, args.repeats)

            # Caterpillar tree
            cat_tree = generate_caterpillar_tree(n)
            styler_cat = FigTreeStyler()
            styler_cat.load_content(cat_tree)
            styler_cat.set_layout(LayoutType.POLAR)
            styler_cat.set_tip_labels(is_shown=True, font_size=10)
            styler_cat.set_appearance(branch_line_width=1.5)
            cat_export = benchmark_export(styler_cat, args.repeats)

            # Ratio: caterpillar / balanced (>1 means caterpillar is slower)
            ratio_exp = cat_export["mean"] / bal_export["mean"] if bal_export["mean"] > 0 else float('inf')
            print(
                f"{n:>8} {'balanced':>12} "
                f"{bal_export['mean']:>12.6f} ± {bal_export['sem']:.6f}"
            )
            print(
                f"{'':>8} {'caterpillar':>12} "
                f"{cat_export['mean']:>12.6f} ± {cat_export['sem']:.6f} "
                f"{ratio_exp:>8.2f}x vs balanced"
            )

    # JVM cold-start measurement
    if args.jvm_cold_start:
        import subprocess
        print("\n--- JVM Cold-Start Time Measurement ---")
        print("Measuring approximate JVM startup overhead for FigTree rendering context...")
        print("(Using `java -version` as a proxy for JVM initialization overhead)")

        jvm_times = []
        for i in range(args.repeats):
            start = time.perf_counter()
            try:
                subprocess.run(
                    ["java", "-version"],
                    capture_output=True, text=True, timeout=30,
                )
                elapsed = time.perf_counter() - start
                jvm_times.append(elapsed)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                print("WARNING: java command not found or timed out — skipping JVM measurement")
                jvm_times = []
                break

        if jvm_times:
            jvm_mean = _mean(jvm_times)
            jvm_sem = _sem(jvm_times)
            print(f"JVM cold start (java -version): {jvm_mean:.3f} ± {jvm_sem:.3f} s (n={len(jvm_times)})")
            print("Note: FigTree JAR launch adds additional classloading overhead beyond this baseline.")
            print("This measurement provides a lower bound for JVM cold-start penalty in FigTree rendering.")


if __name__ == "__main__":
    main()
