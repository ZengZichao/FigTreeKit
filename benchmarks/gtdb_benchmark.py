"""GTDB real-dataset benchmark for FigTreeKit.

Measures parse time, export time, and peak memory on the GTDB R232
archaeal (ar53) and bacterial (bac120) reference trees, and writes the
results to ``benchmarks/gtdb_results.json`` so the manuscript's Section
on real-dataset validation is backed by an auditable artefact.

Usage:
    python benchmarks/gtdb_benchmark.py [--gtdb-dir PATH] [--output PATH]

The GTDB R232 trees are distributed separately (https://gtdb.ecogenomic.org)
and are not part of this repository.
"""

import argparse
import csv
import gc
import io
import json
import platform
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from figtreekit import FigTreeStyler


def measure_dataset(tree_path: Path) -> dict:
    """Measure parse/export time and peak memory for one GTDB tree."""
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    styler = FigTreeStyler(str(tree_path))
    t1 = time.perf_counter()
    with tempfile.NamedTemporaryFile(suffix=".nex", delete=True) as tmp:
        styler.export(tmp.name)
    t2 = time.perf_counter()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "file": tree_path.name,
        "parse_time_s": round(t1 - t0, 3),
        "export_time_s": round(t2 - t1, 3),
        "total_time_s": round(t2 - t0, 3),
        "peak_memory_mb": round(peak / (1024 * 1024), 1),
    }


def count_taxa(tree_path: Path) -> int:
    """Count terminal taxa in a Newick file (fast comma/paren scan)."""
    text = tree_path.read_text(encoding="utf-8", errors="replace")
    # Count leaf labels: tokens after '(' or ',' that are not internal nodes.
    import re
    labels = re.findall(r'[(,]\s*([^(),;:\[\]]+?)\s*(?=[:),;])', text)
    return len(labels)


def main():
    parser = argparse.ArgumentParser(description="FigTreeKit GTDB benchmark")
    parser.add_argument(
        "--gtdb-dir",
        default=str(Path(__file__).parent.parent.parent / "参考-GTDB-R232"),
        help="Directory containing ar53_r232.tree and bac120_r232.tree",
    )
    parser.add_argument(
        "--output",
        default="benchmarks/gtdb_results.json",
        help="Output JSON file path",
    )
    args = parser.parse_args()

    gtdb_dir = Path(args.gtdb_dir)
    datasets = [
        ("ar53_r232", gtdb_dir / "ar53_r232.tree"),
        ("bac120_r232", gtdb_dir / "bac120_r232.tree"),
    ]

    results = {
        "benchmark": "GTDB R232 real-dataset validation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "datasets": [],
    }

    for name, path in datasets:
        if not path.exists():
            print(f"SKIP {name}: {path} not found (download from https://gtdb.ecogenomic.org)")
            continue
        print(f"Measuring {name} ({path.name}) ...", flush=True)
        entry = measure_dataset(path)
        entry["dataset"] = name
        entry["n_taxa"] = count_taxa(path)
        results["datasets"].append(entry)
        print(
            f"  taxa={entry['n_taxa']:,} parse={entry['parse_time_s']}s "
            f"export={entry['export_time_s']}s mem={entry['peak_memory_mb']}MB",
            flush=True,
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"Results written to: {out_path}")


if __name__ == "__main__":
    main()
