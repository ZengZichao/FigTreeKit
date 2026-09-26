# GTDB release 232 inputs (not redistributed)

This directory is where the FigTreeKit benchmark and example scripts look for
the GTDB reference trees by default. Override with `--gtdb-dir PATH` or the
`FTK_GTDB_DIR` environment variable.

Required files (from the official release directory
<https://data.gtdb.ecogenomic.org/releases/release232/232.0/>):

| File | Used by | Notes |
|---|---|---|
| `ar53_r232.tree` | `benchmarks/full_benchmark.py`, `benchmarks/gtdb_benchmark.py`, `examples/05_gtdb_workflow.py` | archaeal reference tree, 10,122 tips |
| `bac120_r232.tree` | same | bacterial reference tree, 189,801 tips |
| `ar53_r232_metadata.tsv` | `examples/05_gtdb_workflow.py` | accession → taxonomy mapping for format B |

```bash
mkdir -p benchmarks/gtdb_data
cd benchmarks/gtdb_data
curl -O https://data.gtdb.ecogenomic.org/releases/release232/232.0/ar53_r232.tree
curl -O https://data.gtdb.ecogenomic.org/releases/release232/232.0/bac120_r232.tree
curl -O https://data.gtdb.ecogenomic.org/releases/release232/232.0/ar53_metadata_r232.tsv.gz
gunzip ar53_metadata_r232.tsv.gz && mv ar53_metadata_r232.tsv ar53_r232_metadata.tsv
```

GTDB designates this release **r232** (directory ``release232/232.0``, its
``VERSION.txt`` reads ``v232``, released 15 April 2026); the ``GB_`` and ``RS_``
prefixes on the tip labels mark GenBank- and RefSeq-sourced genomes and are not
part of the release number. GTDB data are not redistributed with FigTreeKit.
