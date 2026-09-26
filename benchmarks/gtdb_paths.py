"""Single source of truth for the location of the GTDB R232 input files.

Used by ``benchmarks/full_benchmark.py``, ``benchmarks/gtdb_benchmark.py`` and
``examples/05_gtdb_workflow.py`` so the three entry points can no longer agree
on three different defaults.  GTDB data are not redistributed with FigTreeKit;
the files are downloaded from the official release directory and their location
is resolved here.

Resolution order:
    1. an explicit ``--gtdb-dir`` / ``tree_path`` argument,
    2. the ``FTK_GTDB_DIR`` environment variable,
    3. ``<repo>/benchmarks/gtdb_data``.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GTDB_RELEASE_URL = "https://data.gtdb.ecogenomic.org/releases/release232/232.0/"
GTDB_FILES = ("ar53_r232.tree", "bac120_r232.tree",
              "ar53_taxonomy_r232.tsv", "bac120_taxonomy_r232.tsv")


def gtdb_data_dir() -> Path:
    """Directory that should contain the GTDB R232 files."""
    env = os.environ.get("FTK_GTDB_DIR")
    if env:
        return Path(env).expanduser()
    return REPO_ROOT / "benchmarks" / "gtdb_data"


def download_instructions(missing: list[str] | None = None) -> str:
    """Human-readable instructions printed when the inputs are absent."""
    what = ", ".join(missing) if missing else ", ".join(GTDB_FILES)
    d = gtdb_data_dir()
    return (
        f"GTDB release 232 (R11-RS232) inputs not found: {what}\n"
        f"Download them from {GTDB_RELEASE_URL} into {d} , e.g.\n"
        f"  mkdir -p {d}\n"
        f"  curl -o {d}/ar53_r232.tree   {GTDB_RELEASE_URL}ar53_r232.tree\n"
        f"  curl -o {d}/bac120_r232.tree {GTDB_RELEASE_URL}bac120_r232.tree\n"
        f"or pass an explicit path (--gtdb-dir PATH / positional argument)."
    )
