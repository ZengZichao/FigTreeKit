"""Recompute every manuscript-facing summary from the archived data files.

This is the audit-driven companion to ``full_benchmark.py``.  It never
re-measures timing; it re-derives the *reported* quantities from the stored
raw data (``results.csv``, ``competitive_results.json`` etc.) so that a
correction to a statistic definition, a unit convention or a coverage
measurement can be applied without re-running hours of benchmarking.

Produces / updates:
    benchmarks/slope_summary.json       t-based CIs, R^2, df, per-size variants
    benchmarks/table_values.json        exact Table 2 / Table 3 quantities
    benchmarks/figure2_summary.json     the four fits quoted in Fig. 2 legend
    benchmarks/coverage_summary.json    measured statement coverage per module
    benchmarks/gtdb_results.json        SI-unit (10^6 B) memory + own stamp
    benchmarks/figure*.{png,pdf}        regenerated artwork

Usage:
    python3 benchmarks/regenerate_summaries.py            # summaries + figures
    python3 benchmarks/regenerate_summaries.py --no-figs
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

OUT = Path(__file__).parent
ROOT = OUT.parent
sys.path.insert(0, str(OUT))

import numpy as np  # noqa: E402

import full_benchmark as fb  # noqa: E402
import make_figures as mf  # noqa: E402


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def recompute_slopes() -> dict:
    """Rebuild slope_summary.json from results.csv with t-based intervals."""
    rows = list(csv.DictReader((OUT / "results.csv").open(newline="")))
    by_n: dict[int, dict[str, list]] = {}
    for r in rows:
        d = by_n.setdefault(int(r["n_taxa"]), {"export": [], "mem": []})
        d["export"].append(float(r["export_median_s"]))
        d["mem"].append(int(r["peak_memory_bytes"]))

    sizes = sorted(by_n)
    tree_x, tree_y = [], []
    for n in sizes:
        tree_x.extend([n] * len(by_n[n]["export"]))
        tree_y.extend(by_n[n]["export"])

    out = {}
    pooled = fb.slope_ci(tree_x, tree_y)
    pooled["unit"] = "tree-level median over technical replicates"
    out["export_vs_taxa_loglog"] = pooled

    med_exp = [float(np.median(by_n[n]["export"])) for n in sizes]
    ps = fb.slope_ci(sizes, med_exp)
    ps["unit"] = "per-size median of tree-level export medians"
    out["export_vs_taxa_loglog_per_size_medians"] = ps

    maxima = [float(np.max(by_n[n]["mem"])) for n in sizes]
    ms = fb.slope_ci(sizes, maxima)
    ms["unit"] = "per-size maximum over independent trees"
    out["memory_vs_taxa_loglog"] = ms

    meds = [float(np.median(by_n[n]["mem"])) for n in sizes]
    mm = fb.slope_ci(sizes, meds)
    mm["unit"] = "per-size median over independent trees"
    out["memory_vs_taxa_loglog_per_size_medians"] = mm

    out["aggregation_note"] = (
        "All intervals are Student-t on n-2 degrees of freedom (two-sided 95%). "
        "Pooled fits use one point per independent tree; per-size fits use one "
        "point per taxon count. Intervals ignore the nesting of trees within "
        "size levels. Replaces the previous table-lookup critical values, which "
        "fell back to the normal quantile 1.96 for df outside 4-9."
    )
    (OUT / "slope_summary.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print("slope_summary.json rewritten (t-based)")
    return out


def migrate_gtdb_units() -> dict:
    """Express GTDB memory in SI units and give the pass its own stamp.

    The stored ``peak_memory_mb`` values were computed with a 1024*1024
    divisor (MiB). They are kept as ``peak_memory_mb_legacy_mib`` for
    provenance; the new canonical fields are derived from the same recorded
    measurement by exact unit conversion, and the provenance stamp is
    back-filled from benchmark_meta.json of the same frozen session.
    """
    path = OUT / "gtdb_results.json"
    data = _read_json(path)
    meta = _read_json(OUT / "benchmark_meta.json")

    for d in data.get("datasets", []):
        if "peak_memory_mb_legacy_mib" not in d:
            legacy = float(d.get("peak_memory_mb", d.get("peak_memory_MB", 0.0)))
            d["peak_memory_mb_legacy_mib"] = legacy
        mib = float(d["peak_memory_mb_legacy_mib"])
        approx_bytes = int(round(mib * 1024 * 1024))
        d["peak_memory_bytes_recorded"] = approx_bytes
        d["peak_memory_MB"] = round(approx_bytes / 1_000_000, 1)
        n_taxa = int(d["n_taxa"])
        d["heap_per_taxon_kB"] = round(approx_bytes / 1_000 / n_taxa, 2)
        d.pop("peak_memory_mb", None)

    data["mb_definition"] = "1 MB = 10^6 bytes; 1 kB = 10^3 bytes (SI, as in Table 2)"
    data["memory_unit_note"] = (
        "peak_memory_MB is the tracemalloc heap peak converted from the "
        "originally stored MiB figure (exact factor 1048576/1000000); the raw "
        "MiB value is retained as peak_memory_mb_legacy_mib."
    )
    data.setdefault("run_relationship", (
        "measured in the same frozen environment as the synthetic benchmark "
        "(benchmark_meta.json) in a separate pass 4 minutes later; one timed "
        "run per dataset, so no dispersion is assessed"))
    for key, src in (("cpu", "cpu"), ("ram_gb", "ram_gb"),
                     ("python_version", "python"), ("biopython", "biopython"),
                     ("java", "java"), ("commit", "commit"),
                     ("git_dirty", "git_dirty"),
                     ("figtreekit_version", "figtreekit_version")):
        if src in meta:
            data[key] = meta[src]
    data["stamp_source"] = (
        "cpu/ram/interpreter/biopython/java/commit back-filled from "
        "benchmarks/benchmark_meta.json, the machine-stamped record of the "
        "same frozen benchmark session (timestamp differs by ~4 min)")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("gtdb_results.json: SI memory units + provenance stamp added")
    return data


def main() -> int:
    make_figs = "--no-figs" not in sys.argv
    slopes = recompute_slopes()
    migrate_gtdb_units()
    mf.table_values()
    if make_figs:
        mf.figure2_main()
        mf.figure_s1()
        mf.figure_s2()
        mf.figure_s5()
        mf.figure_s6()
        print("figures regenerated")
    e = slopes["export_vs_taxa_loglog"]
    print(f"\nexport slope {e['slope']:.3f} CI {e['ci95'][0]:.3f}-{e['ci95'][1]:.3f} "
          f"R2={e['r_squared']:.3f} df={e['df']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
