# FigTreeKit

**Programmatic styling of phylogenetic trees for FigTree visualization**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v2+](https://img.shields.io/badge/License-GPL%20v2+-blue.svg)](https://spdx.org/licenses/GPL-2.0-or-later.html)
[![Version](https://img.shields.io/badge/version-1.0.3-green.svg)](https://pypi.org/project/figtreekit/)
[![Bioinformatics](https://img.shields.io/badge/topic-bioinformatics-green.svg)](https://github.com/ZengZichao/FigTreeKit)

[中文文档](https://github.com/ZengZichao/FigTreeKit/blob/main/README_CN.md) | [English](#)

---

## Overview

FigTreeKit is a Python library for programmatic publication-ready styling of phylogenetic trees. It addresses the problem of **reproducible, scriptable tree visualization** in evolutionary biology and comparative genomics — turning raw Newick/Nexus trees into annotated, publication-quality figures compatible with [FigTree](http://tree.bio.ed.ac.uk/software/figtree/).

Typical use cases include:
- Styling phylogenomic trees with taxonomic group highlights
- Batch-processing hundreds of gene trees with consistent formatting
- Validating and collapsing clades by taxonomic group name
- Generating publication-ready figures from BEAST/RAxML/IQ-TREE output

### Key Features

- **FigTree-Compatible Output**: Generates Nexus files with `[&!hilight]`, `[&!color]`, `[&!font]` annotations
- **Pythonic API**: Method chaining for intuitive tree styling
- **Taxonomy-Aware Analysis**: Automatic taxonomy extraction from labels (embedded `_d_`/`_p_`/`_g_`/`_s_`/`_ss_` format and table `d__`/`p__` format)
- **Monophyly Detection**: Check if taxa form monophyletic groups, with special identifiers (LUCA/LACA/LBCA)
- **Clade Collapse**: Collapse clades by taxonomic group name with monophyly validation
- **Multi-Tree Handling**: Detect and process multiple trees with `split`/`first`/`last`/`random` modes
- **Deep Input Validation**: Structural checks, negative branch detection, duplicate tip names, malicious character scanning
- **Real-Time Logging**: ISO 8601 timestamps, stdout flush, optional log file output
- **Self-Test Mode**: `--self-test` verifies dependencies, parsing, taxonomy, and monophyly logic
- **Batch Processing**: Process multiple tree files via CLI
- **Image Rendering**: Export to PNG/PDF/SVG without opening FigTree GUI (requires FigTree JAR); for command-line rendering of very large trees, [TreeViewer](https://doi.org/10.1002/ece3.10873) is also worth considering.

---

## Comparison with Existing Tools

| Capability | FigTreeKit | FigTree GUI | DendroPy | ETE3 | TreeViewer |
| --- | :---: | :---: | :---: | :---: | :---: |
| Programmatic / scriptable styling | ✅ | ❌ | ⚠️ limited | ⚠️ limited | ✅ (CLI) |
| Python API | ✅ | ❌ | ✅ | ✅ | ❌ |
| Inject FigTree annotations (`!hilight`/`!color`/`!font`) | ✅ | N/A | ❌ | ❌ | ❌ |
| Taxonomy-aware collapse / monophyly check | ✅ | manual | ⚠️ partial | ⚠️ partial | ❌ |
| Deep input validation (brackets, negative branches, malicious chars) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Batch CLI processing | ✅ | ❌ | ❌ | ✅ | ✅ |
| Image rendering (PNG/PDF/SVG) | ✅ | ✅ | ❌ | ✅ | ✅ |

See [docs/comparison_EN.md](docs/comparison_EN.md) for the full comparison matrix and reproduction instructions.

---

## Installation

### From PyPI (Recommended)

```bash
pip install figtreekit
```

### From Source

```bash
git clone https://github.com/ZengZichao/FigTreeKit.git
cd FigTreeKit
pip install -r requirements.txt
pip install -e .
```

### Dependencies

- **Required**: Python 3.11, Biopython (>=1.80, <2.0)
- **Optional**: psutil (for memory logging), Java 8+ (for rendering)
- **Tested on**: macOS Tahoe 26.5.2 (Apple Silicon)

### Self-Test

After installation, verify everything works:

```bash
figtreekit --self-test
```

This runs 11 built-in checks (dependencies, parsing, taxonomy, monophyly) and requires no external files. See the Quick Start section for expected output.

---

## Quick Start

### 1. Verify Installation

```bash
figtreekit --self-test
```

```
  [PASS]   Dependency: biopython
  [PASS]   Dependency: python
  [PASS]   Parse: Newick example
  [PASS]   Taxonomy: embedded format extraction
  [PASS]   Taxonomy: table format extraction
  [PASS]   Monophyly: Cyanobacteriales (monophyletic)
  [PASS]   Special ID: LUCA resolves all taxa
  [PASS]   Special ID: LACA resolves Archaea only
  [PASS]   Export: Newick → Nexus round-trip
  [PASS]   Validation: FASTA example
  [PASS]   Security: control char detection
  All 11 checks passed.
```

### 2. Basic Usage (Python API)

```python
from figtreekit import FigTreeStyler, LayoutType, FontStyle

styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);")
styler.set_layout(LayoutType.RECTILINEAR)
styler.set_appearance(background_color="#FAFAFA", branch_line_width=2.0)
styler.highlight_clade(["A", "B"], color="#FF0000")
styler.set_tip_labels(is_shown=True, font_size=12)
styler.export("output.nex")
```

### 3. Command Line Usage

```bash
figtreekit input.tre -o output.nex --layout polar --tip-labels-show
figtreekit input.tre --validate
figtreekit input.tre -o output.nex --clade Cyanobacteriota
```

### 4. Export and Render to Image

```bash
figtreekit --setup-figtree              # one-time setup
figtreekit input.tre -o output.nex --render tree.png
figtreekit input.tre -o output.nex --render tree.pdf --render-width 1600
```

---

## Taxonomy Analysis

### Automatic Taxonomy Extraction

FigTreeKit can extract taxonomy from two formats:

**Format A (Embedded)** — taxonomy encoded in the label:
```
GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota_c_Cyanobacteriia_o_Cyanobacteriales_f_Prochloraceae_g_Prochloron
```

**Format B (Table)** — semicolon-delimited taxonomy strings:
```
d__Archaea;p__Thermoproteota;c__Korarchaeia;o__Korarchaeales;f__Korarchaeaceae;g__WALU01;s__
```

### Python API

```python
from figtreekit import FigTreeStyler

styler = FigTreeStyler("tree.nwk")

# Check monophyly by group name (auto-detects format)
result = styler.check_monophyly_by_group("Cyanobacteriales")
print(result["is_monophyletic"])  # True/False
print(result["resolved_taxa"])    # list of taxon names

# Collapse a monophyletic clade
styler.collapse_by_group("Cyanobacteriales")
styler.export("collapsed.nex")
```

### CLI Usage

```bash
# Collapse by taxon group name
figtreekit tree.nwk -o collapsed.nex --clade Cyanobacteriota

# Strict mode (abort if not monophyletic)
figtreekit tree.nwk -o collapsed.nex --clade Cyanobacteriota --strict

# Multiple clades
figtreekit tree.nwk -o out.nex --clade Cyanobacteriota --clade Proteobacteria

# Custom taxonomy parsing
figtreekit tree.nwk -o out.nex --taxonomy-delimiter-mode greedy
figtreekit tree.nwk -o out.nex --taxonomy-table-sep "|"
figtreekit tree.nwk -o out.nex --taxonomy-levels "k:kingdom,ss:subspecies"
```

### Special Identifiers

| Identifier | Description |
|------------|-------------|
| `LUCA` | Last Universal Common Ancestor (all Bacteria + Archaea) |
| `LACA` | Last Archaeal Common Ancestor |
| `LBCA` | Last Bacterial Common Ancestor |
| `root` | Root of the tree (all terminal taxa) |

```python
result = styler.check_monophyly_by_group("LUCA")
```

### External Taxonomy Table

When labels don't contain taxonomy, provide a mapping file (TSV/CSV, two-column format). See [Input Format Details](#input-format-details) for the full specification.

```bash
figtreekit tree.nwk -o out.nex --clade Cyanobacteriales
```

---

## Multi-Tree Handling

When a file contains multiple trees (e.g., Nexus with multiple `tree` statements):

```bash
# Default: print summary and abort (exit code 2)
figtreekit multi.nex -o out.nex

# Process all trees with numeric suffixes
figtreekit multi.nex -o out.nex --multi-tree split

# Process only the first/last tree
figtreekit multi.nex -o out.nex --multi-tree first
figtreekit multi.nex -o out.nex --multi-tree last

# Random selection
figtreekit multi.nex -o out.nex --multi-tree random

# Same as split (process all trees)
figtreekit multi.nex -o out.nex --multi-tree all
```

---

## Sequence Validation

FigTreeKit can validate FASTA/FASTQ files:

```bash
# Validate FASTA
figtreekit sequences.fasta --validate

# Validate with expected molecule type
figtreekit sequences.fasta --validate --mol-type DNA

# Skip alignment length check
figtreekit aligned.fasta --validate --skip-length-check

# Cross-validate tree tips against sequence IDs
figtreekit tree.nwk -o out.nex --sequences sequences.fasta

# Cross-validate during validation mode
figtreekit tree.nwk --validate --sequences sequences.fasta
```

> **Note**: When using `--validate` with a sequence file (FASTA/FASTQ), the CLI returns exit code 0 (success) if deep validation passes, even though the file is not a tree format. This allows independent sequence validation in scripts.

Checks include:
- Duplicate sequence IDs (ERROR)
- Alphabet validation (DNA/RNA/protein) with invalid character reporting
- Alignment length consistency (WARNING)

See [Input Format Details](#input-format-details) for FASTA/FASTQ format specifications.

---

## Deep Input Validation

FigTreeKit performs comprehensive validation on all input files:

### Tree Files

| Check | Level |
|-------|-------|
| Bracket balance (parentheses, brackets) | ERROR with position |
| Negative branch lengths | CRITICAL (abort) |
| Empty node names | ERROR |
| Duplicate tip names | ERROR |
| Self-loop detection | ERROR |
| Control characters / Unicode bidi overrides | CRITICAL (abort) |

### Sequence Files

| Check | Level |
|-------|-------|
| Duplicate sequence IDs | ERROR (abort) |
| Invalid characters for alphabet | ERROR with line number |
| Alignment length inconsistency | WARNING |

### Adversarial Input Protection

- Control characters (`\x00`-`\x1f`) in node names → CRITICAL
- Unicode bidi overrides (`\u202E`) → CRITICAL
- Circular dependencies in taxonomy tables → ERROR
- Empty files (0 bytes) → CRITICAL

---

## Output Format

### Nexus File Structure

FigTreeKit exports FigTree-compatible Nexus files with three blocks:

```
#NEXUS
begin taxa;
    dimensions ntax=3;
    taxlabels A B C ;
end;
begin trees;
    tree TREE1 = ((A:0.1,B:0.2):0.3,C:0.4);
end;
begin figtree;
    set appearance.backgroundColour=#ffffff;
    set layout.layoutType=POLAR;
    set tipLabels.isShown=true;
end;
```

### Annotation Format

FigTreeKit injects annotations into the Newick tree string:

| Annotation | Format | Description |
|------------|--------|-------------|
| `!hilight` | `[&!hilight={tipCount,height,color}]` | Background highlight for a clade. `tipCount` = number of tips, `height` = node height from root, `color` = hex RGB. |
| `!color` | `[&!color=#RRGGBB]` | Branch color applied to the MRCA node. |
| `!font` | `[&!font=Name-STYLE-size]` | Font annotation (Java `Font.decode()` format). STYLE: `PLAIN`, `BOLD`, `ITALIC`, `BOLDITALIC`. |
| `!stroke` | `[&!stroke=N]` | Branch stroke width (forward compatibility; FigTree 1.4.4 ignores this). |

**Example** — highlighting clade (A,B):
```
((A:0.1,B:0.2)[&!hilight={2,0.3,#ff0000}]:0.3,C:0.4);
```

### Output File Naming

| Mode | Output Pattern |
|------|---------------|
| Single tree | `<output>.nex` (user-specified) |
| Batch | `<input_stem>.nex` in output directory |
| Multi-tree split | `<output>_tree1.nex`, `<output>_tree2.nex`, ... |
| Collapsed clade | Same as input (clade replaced in-place) |

---

## Input Format Details

### Format Standards

FigTreeKit follows these standards:
- **Newick**: [Newick tree format](https://en.wikipedia.org/wiki/Newick_format) — branch lengths are in substitution units (evolutionary distances from parent node)
- **Nexus**: [Nexus file format](https://en.wikipedia.org/wiki/Nexus_file) — compliant with the Maddison et al. (1997) specification
- **FASTA**: [FASTA format](https://www.ncbi.nlm.nih.gov/genbank/fastaformat/) — standard bioinformatics sequence format
- **FASTQ**: [FASTQ format](https://en.wikipedia.org/wiki/FASTQ_format) — Illumina/Sanger quality encoding

### Tree File Formats

**Newick** (`.nwk`, `.newick`, `.tree`, `.tre`, `.treefile`, `.nh`, `.nhy`, `.nhx`):
```
((A:0.1,B:0.2):0.3,C:0.4);
```
- Branch lengths are optional (default: no branch length displayed)
- Quoted names supported: `('Species A':0.1,'Species B':0.2);`
- Bracket comments preserved: `(A:0.1[&posterior=0.95],B:0.2);`

**Nexus** (`.nex`, `.nexus`, `.nx`):
```
#NEXUS
begin taxa;
    dimensions ntax=3;
    taxlabels A B C ;
end;
begin trees;
    tree TREE1 = ((A:0.1,B:0.2):0.3,C:0.4);
end;
```
- Translate blocks supported (BEAST format)
- Multiple trees preserved (all written to output)
- Existing `figtree` block parsed and merged
- **BEAST output**: Translate blocks and bracket annotations (e.g. `[&posterior=0.95]`) are preserved

### Taxonomy Mapping Files

**Two-column format** (auto-detected TSV/CSV):

With header:
```
name	taxonomy
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
RS_GCF_000013425.1	d__Archaea;p__Euryarchaeota;c__Methanomicrobia;o__Methanosarcinales;f__Methanosarcinaceae;g__Methanosarcina;s__
```

Without header:
```
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
RS_GCF_000013425.1	d__Archaea;p__Euryarchaeota;c__Methanomicrobia;o__Methanosarcinales;f__Methanosarcinaceae;g__Methanosarcina;s__
```

- Delimiter: tab (`.tsv`) or comma (`.csv`), auto-detected from extension
- Force delimiter: `--table-sep ","`
- Missing ranks (e.g. `s__` with no value) → stored as empty string
- Malformed rows: `--ignore-malformed` to skip instead of aborting

### Supported Input Formats Summary

| Type | Format | Extensions |
|------|--------|-----------|
| Tree | Newick | `.nwk`, `.newick`, `.tree`, `.tre`, `.treefile`, `.nh`, `.nhy`, `.nhx` |
| Tree | Nexus | `.nex`, `.nexus`, `.nx` |
| Tree | PhyloXML † | `.xml`, `.phyloxml` |
| Sequence | FASTA | `.fasta`, `.fa`, `.fas`, `.fna`, `.faa`, `.ffn`, `.frn` |
| Sequence | FASTQ | `.fastq`, `.fq` |
| Sequence | GenBank | `.gb`, `.gbk`, `.genbank` |
| Sequence | EMBL | `.embl` |
| Sequence | Stockholm | `.stockholm`, `.sto` |
| Sequence | Phylip | `.phylip`, `.phy` |
| Sequence | Clustal | `.clustal`, `.aln` |
| Taxonomy | TSV/CSV | `.tsv`, `.csv` |

> **† Format support scope:** Tree *styling and rendering* (`FigTreeStyler` and Nexus export) support **Newick and Nexus only**. PhyloXML is recognized by the input *validator* (`--validate`) but is **not** loaded, styled, or rendered by the tree styler. Sequence formats (FASTA, FASTQ, GenBank, EMBL, Stockholm, Phylip, Clustal) are supported for **input validation and tree↔sequence cross-validation** (`--validate` / `--sequences`), not for tree styling.

### Processing Flow

```
Input File
    │
    ▼
┌─────────────────┐
│  Format Detect   │  (Newick / Nexus / FASTA / FASTQ)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Deep Validation │  (brackets, branch lengths, duplicates, malicious chars)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Multi-Tree Check │  (ask / split / first / last / random / all)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Taxonomy Parse   │  (embedded _d_/_p_ or table d__/p__)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Style & Collapse │  (clade highlights, colors, monophyly check)
└────────┬────────┘
         ▼
┌─────────────────┐
│  Export / Render │  (Nexus output, optional PNG/PDF/SVG)
└─────────────────┘
```

### Common Issues and Boundary Cases

- **Quoted taxon names**: Names with spaces or special characters must be single-quoted in Newick: `('Species A':0.1,'Species B':0.2);`
- **Missing branch lengths**: Trees without branch lengths are valid; FigTree will display equal-length branches
- **Polytomies**: Unresolved nodes (more than 2 children) are fully supported
- **Translate blocks**: BEAST-style numeric taxon IDs are automatically resolved
- **Encoding**: Files with BOM (UTF-8-sig) or legacy encodings (latin-1) are handled transparently
- **Large trees**: Trees with >10,000 tips trigger a resource warning; use `--low-memory` mode
- **Empty taxa names**: Detected and rejected as ERROR (cannot map taxonomy)
- **Duplicate tip names**: Detected and rejected as ERROR (would cause taxonomy mapping conflicts)

---

## Real-Time Logging

All operations produce real-time log output with ISO 8601 timestamps:

```
2026-06-13T15:30:56.135 | [    INFO] | >>> Input file validation ...
2026-06-13T15:30:56.135 | [    INFO] | <<< Input file validation (0 ms)
2026-06-13T15:30:56.135 | [    INFO] | >>> Parsing tree file ...
2026-06-13T15:30:56.192 | [    INFO] | tree.nwk: parsed successfully, 3 taxa detected
2026-06-13T15:30:56.192 | [    INFO] | <<< Parsing tree file (57 ms)
2026-06-13T15:30:56.192 | [    INFO] | tree.nwk: DONE (total 0.06 s)
```

### Log Levels

| Flag | Level | Description |
|------|-------|-------------|
| `-q` | ERROR | Suppress all non-error output |
| (default) | WARNING | Warnings and errors only |
| `-v` | INFO | Normal operation flow |
| `-vv` | DEBUG | Detailed debugging info |

### Log File

```bash
# Write logs to file (all levels, UTF-8)
figtreekit tree.nwk -o out.nex --log-file figtreekit.log
```

---

## Command Line Interface

### Basic Commands

```bash
figtreekit input.tre -o output.nex [OPTIONS]
figtreekit input.tre --validate
figtreekit --version
figtreekit --self-test
figtreekit --help
```

### Common Options

> For the complete and up-to-date list, run `figtreekit --help`.

```
positional arguments:
  input                 Input tree file or directory for batch processing

options:
  -o, --output OUTPUT   Output Nexus file (or directory for batch)
  --validate            Check compatibility without exporting
  -v, --verbose         Increase verbosity (-v INFO, -vv DEBUG) (default: WARNING)
  -q, --quiet           Suppress non-error output
  --version             Show version, git commit hash, date and dependencies
  --self-test           Run self-diagnostic checks
  --config FILE         JSON config file
  --log-file FILE       Write logs to file (UTF-8, all levels)
  --force               Overwrite existing output files
  --no-clobber          Skip if output exists
  --strip-annotations   Strip bracket comments (NHX/bootstrap/posterior) to reduce file size

Tree:
  --clade NAME          Collapse clade by taxonomic group name
  --strict              Abort on non-monophyletic clades (default: warn and skip)
  --multi-tree MODE     Multi-tree handling (default: ask)
                        Choices: ask/split/first/last/random/all
  --rooted              Set tree as rooted
  --unrooted            Set tree as unrooted (takes precedence over --rooted)

Taxonomy:
  --taxonomy-levels SPEC          Extend rank prefixes (e.g. "k:kingdom,ss:subspecies")
  --taxonomy-delimiter-mode MODE  reverse/greedy/segment (default: reverse)
  --taxonomy-table-sep CHAR       Separator for taxonomy strings (default: ";")
  --taxonomy-source-priority P    embedded/table (default: table)
  --taxonomy-mapping-file FILE    Path to taxonomy mapping file (TSV/CSV)
  --table-sep CHAR                Force column delimiter for mapping file
  --ignore-malformed              Skip malformed taxonomy rows

Sequence:
  --mol-type TYPE       DNA/RNA/protein (default: auto-detect)
  --sequences FILE      Sequence file for cross-validation against tree tips
  --no-cross-check      Skip tree-sequence label cross-validation
  --skip-length-check   Skip alignment length check
  --low-memory          Reduce memory usage for large files (streaming)

Rendering:
  --render FILE               Render tree to image (PNG/PDF/SVG/JPEG)
  --render-format FORMAT      Force render format (PNG/PDF/SVG/JPEG)
  --render-width PX           Image width (default: 1200)
  --render-height PX          Image height (default: 800)
  --figtree-jar PATH          Path to figtree.jar
  --setup-figtree             Download/compile FigTree JAR
  --check-figtree             Check if FigTree JAR is available
```

### Config File

```json
{
    "layout.layoutType": "POLAR",
    "appearance.backgroundColour": "#FAFAFA",
    "tipLabels.isShown": true,
    "tipLabels.fontName": "Arial",
    "tipLabels.fontSize": 10
}
```

```bash
figtreekit input.tre -o output.nex --config style.json
```

---

## Python API Reference

### Tree Styling

```python
from figtreekit import FigTreeStyler, LayoutType, FontStyle, TransformType

styler = FigTreeStyler("tree.nwk")

# Layout
styler.set_layout(LayoutType.POLAR)
styler.set_polar_layout(angular_range=270, root_angle=45)

# Appearance
styler.set_appearance(background_color="#FFFFFF", branch_line_width=2.0)

# Clade annotations
styler.highlight_clade(["A", "B"], color="#FF0000")
styler.set_clade_color(["A", "B"], color="#2196F3")
styler.set_clade_color_all(["A", "B"], color="#2196F3")  # color all branches in subtree
# Note: set_clade_color + highlight_clade on the same taxa will drop the
# MRCA-level color to avoid FigTree ClassCastException.
# Use set_clade_color_all() as the recommended alternative.
styler.set_clade_font(["A"], font_name="Arial", font_style=FontStyle.BOLD, font_size=14)

# Labels
styler.set_tip_labels(is_shown=True, font_size=12)
styler.set_node_labels(is_shown=True, display_attribute="height")
styler.set_branch_labels(is_shown=True, display_attribute="length")

# Scale
styler.set_scale_bar(is_shown=True)
styler.set_scale_axis(is_shown=True)
styler.set_scale(root_age=1.0)

# Layout-specific settings
styler.set_radial_layout(spread=1.0)
styler.set_rectilinear_layout(curvature=0, root_length=0)

# Trees
styler.set_trees(rooting=True, transform=TransformType.PHYLOGRAM)

# Legend / node decorations
styler.set_legend(is_shown=True, position="bottom")
styler.set_node_bars(is_shown=True)
styler.set_node_shapes(is_shown=True)

# Apply from dict and reset
styler.apply_dict({"layout.layoutType": "POLAR"})

# Full reset: clears settings, annotations, taxonomy config, AND tree content
# Must reload tree via load_file / load_content before further operations
styler.reset()

# Or reset only styling, keeping the loaded tree
styler.reset(keep_tree=True)

# Export
styler.export("output.nex")
styler.render("tree.png")
styler.render("tree.pdf", format="PDF", width=1600, height=1000)
```

### Monophyly & Collapse

```python
# Check monophyly
result = styler.check_monophyly(["A", "B", "C"])
result = styler.check_monophyly_by_group("Cyanobacteriales")
result = styler.check_monophyly_by_group("LUCA")

# Collapse clades
styler.collapse_clade(["A", "B"], label="Clade1")
styler.collapse_by_group("Cyanobacteriales")
styler.collapse_by_group("Cyanobacteriales", label="Cyano")

# Nested collapse: collapse inner and outer clades simultaneously
# (automatically sorted by size, processed inner-first)
styler.collapse_clade(["A", "B"], label="Inner")
styler.collapse_clade(["A", "B", "C"], label="Outer")  # Both labels appear in output

# Convenience: check + style in one call
styler.style_monophyletic_clade(
    ["A", "B", "C"],
    color="#E91E63",
    highlight_color="#FFCDD2",
    font_name="Arial",
    font_style=FontStyle.BOLD,
    font_size=12,
)

# Clear pending operations
styler.clear_annotations()
styler.clear_clade_hilights()
styler.clear_collapses()

# Strip all bracket comments (NHX, bootstrap, posterior, etc.) to reduce output size
styler.strip_annotations()

# Get detailed clade information (MRCA, descendant tips, monophyly, etc.)
info = styler.get_clade_info(["A", "B", "C"])
print(info["is_monophyletic"], info["mrca_terminal_count"])
```

### Loading & Access

```python
# Load from string or file (auto-detect)
styler = FigTreeStyler().load_tree("((A:0.1,B:0.2):0.3,C:0.4);")
styler = FigTreeStyler().load_tree("tree.nwk")  # auto-loads from file if exists

# Access annotations and collapses
annotations = styler.get_annotations()  # get current annotations list
collapses = styler.get_collapses()      # get current collapses list

# Set font with defaults
styler.set_clade_font(["A", "B"])  # uses defaults: Arial, PLAIN, 12
styler.set_clade_font(["A", "B"], font_name="Helvetica", font_style=FontStyle.BOLD, font_size=14)
```

### Validation

```python
from figtreekit import (
    validate_input_file,
    deep_validate_newick,
    deep_validate_fasta,
    deep_validate_fastq,
    TreeValidator,
)

# File validation
result = validate_input_file("tree.nwk")
if not result["valid"]:
    for err in result["errors"]:
        print(err)

# Deep Newick validation
dv = deep_validate_newick(content, label="tree.nwk")
for err in dv["errors"]:
    print(err)

# FASTA / FASTQ validation
dv = deep_validate_fasta("seqs.fasta", expected_alphabet="DNA")
dv = deep_validate_fastq("reads.fastq", expected_alphabet="DNA")

# Styler-level validation
issues = styler.validate()

# Biological plausibility check (degenerate trees, all-zero branches, large tree warnings)
warnings = TreeValidator.validate_biological_plausibility(newick)
```

### Taxonomy

```python
from figtreekit import (
    parse_taxonomy_auto,
    detect_taxonomy_format,
    TaxonomyMapper,
    MonophylyAnalyzer,
    get_rank_prefixes,
    extend_rank_prefixes,
)

# Apply settings from CLI arguments
from figtreekit import apply_cli_args
# apply_cli_args(styler, args)  # args from argparse.Namespace

# Auto-detect and parse
tax = parse_taxonomy_auto("GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota_c_Cyanobacteriia_o_Cyanobacteriales_f_Prochloraceae_g_Prochloron")
# {"domain": "Bacteria", "phylum": "Cyanobacteriota", ...}

tax = parse_taxonomy_auto("d__Archaea;p__Euryarchaeota;s__")
# {"domain": "Archaea", "phylum": "Euryarchaeota", "species": ""}

# Styler taxonomy configuration
styler.configure_taxonomy(
    delimiter_mode="reverse",      # reverse / greedy / segment
    table_sep=";",
    source_priority="table",       # table / embedded
    mapping_file="taxonomy.tsv",
    ignore_malformed=False,
)

# Direct mapper usage
mapper = TaxonomyMapper()
mapper.load_mapping("taxonomy.tsv")
groups = mapper.identify_groups(rank="genus")

# Taxonomy analysis with automatic monophyly detection (requires pattern or mapping_file)
result = styler.analyze_taxonomy(mapping_file="taxonomy.tsv", rank="phylum")
# Convenience method: equivalent to analyze_taxonomy(mapping_file=...)
result = styler.analyze_taxonomy_from_mapping("taxonomy.tsv", rank="phylum")

# Parse taxonomy from labels (built-in patterns or custom regex)
taxonomy = styler.parse_label_taxonomy("genus_species")

# Check taxonomy data completeness
completeness = styler.check_taxonomy_completeness(mapping_file="taxonomy.tsv")
```

### Library Mode API

```python
from figtreekit import (
    parse_taxonomy,        # Standardized taxonomy parsing
    is_monophyletic,       # Monophyly check
    load_tree,             # Tree loading
    cross_validate,        # Cross-validation
    # Standardized exception hierarchy
    PhyloFormatError,      # File format error (inherits from ParseError)
    TaxonomyConflictError, # Taxonomy conflict (inherits from ValidationError)
    MonophylyError,        # Monophyly analysis error (inherits from ValidationError)
)

# Parse taxonomy label (standardized signature)
tax = parse_taxonomy("d__Bacteria;p__Cyanobacteriota", mode="reverse")
# -> {"domain": "Bacteria", "phylum": "Cyanobacteriota", ...}

# Check monophyly (standardized signature)
mono = is_monophyletic("tree.nwk", "Cyanobacteriota", rooted=True)
# -> True / False

# Load tree file (standardized signature)
styler = load_tree("tree.nwk", validate=True)

# Cross-validate tree and sequences (standardized signature)
report = cross_validate("tree.nwk", "sequences.fasta", strict=True)
# -> {"valid": True, "matched": 50, "tree_only": [], "seq_only": [], "errors": []}
```

---

## Error Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 0 | Success | All operations completed successfully |
| 1 | Runtime error | Dependency issues, self-test failures |
| 2 | Usage error | Invalid command-line arguments, missing input |
| 3 | Data error | Invalid input data (malformed tree, bad sequences) |
| 130 | Interrupted | User pressed Ctrl+C (SIGINT) or SIGTERM received |

### Exception Hierarchy

| Exception | Base Class | Purpose |
|-----------|-----------|---------|
| `FigTreeKitError` | `Exception` | Base class for all FigTreeKit exceptions |
| `ParseError` | `FigTreeKitError` | Tree/sequence file parsing errors |
| `ValidationError` | `FigTreeKitError` | Input validation failure |
| `ExportError` | `FigTreeKitError` | Export/render errors |
| `PhyloFormatError` | `ParseError` | File format error (library mode API alias) |
| `TaxonomyConflictError` | `ValidationError` | Taxonomy conflict (library mode API alias) |
| `MonophylyError` | `ValidationError` | Monophyly analysis error (library mode API alias) |
| `CompatibilityWarning` | `UserWarning` | Compatibility warning |

---

## Operational Notes

### Output Control

```bash
figtreekit tree.nwk -o existing.nex --force        # overwrite
figtreekit tree.nwk -o existing.nex --no-clobber    # skip if exists
figtreekit tree.nwk -o new/dir/output.nex           # auto-create dirs
```

### User Interrupt

Press `Ctrl+C` to gracefully terminate — progress is displayed, temporary files are cleaned up, exit code 130.

### Portability Design

- **Encoding**: UTF-8 with BOM and latin-1 fallback handled transparently
- **Newlines**: Unix `\n` on all platforms
- **Paths**: `pathlib.Path` throughout (platform-independent path handling)
- **Temporary files**: Auto-cleaned on exit, permissions set to 0o600 (HPC-safe), including Ctrl+C

> **Note**: Although the codebase uses platform-independent patterns, FigTreeKit has only been tested on macOS Tahoe 26.5.2. Compatibility with Windows or Linux is not guaranteed.

---

## Large-Scale Data

For trees with more than 10,000 tips:
- An INFO log entry warns about memory requirements
- Use `--low-memory` to stream sequence IDs during cross-validation
- Install `psutil` for DEBUG-level memory logging

### Resource Estimates

| Tree Size | Approx. Memory | Parse Time | Export Time |
|-----------|---------------|------------|-------------|
| 100 tips | < 10 MB | < 0.01 s | < 0.01 s |
| 1,000 tips | ~ 20 MB | < 0.01 s | ~ 0.01 s |
| 10,000 tips | ~ 100 MB | ~ 0.01 s | ~ 0.1 s |
| 100,000 tips | ~ 1 GB | ~ 0.1 s | ~ 1 s |

---

## FigTree Rendering Setup

> **Alternative note**: FigTreeKit rendering relies on the FigTree JAR to preserve FigTree annotations and styles in automated workflows. If you only need a **cross-platform GUI/CLI tool to render very large trees** (>100,000 taxa) without FigTree-compatible Nexus annotations, consider [TreeViewer](https://doi.org/10.1002/ece3.10873).

```bash
# Check status
figtreekit --check-figtree

# Download and compile
figtreekit --setup-figtree

# Use existing JAR
figtreekit --setup-figtree --figtree-jar /path/to/figtree.jar
```

### Rendering Output Formats

| Format | Extension | Best For |
|--------|-----------|---------|
| PNG | `.png` | Web, presentations, quick preview |
| PDF | `.pdf` | Publication, vector editing (Adobe Illustrator) |
| SVG | `.svg` | Web, scalable vector graphics |
| JPEG | `.jpg` | Email, small file size (lossy compression) |

```bash
# PNG (default, good for most uses)
figtreekit tree.nwk -o tree.nex --render tree.png

# PDF for publication
figtreekit tree.nwk -o tree.nex --render tree.pdf

# SVG for web
figtreekit tree.nwk -o tree.nex --render tree.svg

# Custom dimensions
figtreekit tree.nwk -o tree.nex --render tree.png --render-width 2000 --render-height 1500

# Explicit render format when extension is ambiguous
figtreekit tree.nwk -o tree.nex --render tree.out --render-format PNG
```

See [docs/user_manual_EN.md](docs/user_manual_EN.md) for detailed compilation instructions.

---

## Contact & Maintainer

- **Author**: Zeng Zichao (Shanghai Jiao Tong University)
- **Email**: zengzichao@sjtu.edu.cn
- **GitHub Issues**: https://github.com/ZengZichao/FigTreeKit/issues
- **GitHub Discussions**: https://github.com/ZengZichao/FigTreeKit/discussions

---

## Citation

If you use FigTreeKit in your research, please cite:

```bibtex
@software{figtreekit2026,
  author = {Zeng, Zichao},
  title = {FigTreeKit: Programmatic styling of phylogenetic trees for FigTree visualization},
  year = {2026},
  url = {https://github.com/ZengZichao/FigTreeKit}
}
```

---

## License

FigTreeKit is free software licensed under the **GNU General Public License v2.0 or later (GPL-2.0-or-later)**.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [LICENSE](LICENSE) file for details.

### Third-party components

- **FigTree** (`figtreekit/figtree_patched.jar`, `_figtree_patch/`, modified Java sources in `_figtree_patch/src/figtree/`): derived from [FigTree v1.4.4](http://tree.bio.ed.ac.uk/software/figtree/) by Andrew Rambaut, licensed under GPL-2.0-or-later. The original unmodified JAR (`_figtree_patch/figtree_original.jar`) is also provided to satisfy GPL source-provision requirements; see `_figtree_patch/README.md` for rebuild instructions.
- **iText** (bundled inside the FigTree JARs for PDF export): licensed under the GNU Affero General Public License v3 (AGPL-3.0).
- **Biopython** (runtime dependency): BSD-3-Clause.

When you redistribute FigTreeKit or the patched FigTree JAR, the copyleft terms of GPL-2.0-or-later and AGPL-3.0 apply.

**License compatibility**: FigTreeKit uses GPL-2.0-**or-later**, which allows upgrading to GPL-3.0, thereby achieving compatibility with iText's AGPL-3.0 license. GPL-3.0 and AGPL-3.0 have a defined compatibility path (AGPL-3.0 §13). Downstream users in strict compliance environments may treat FigTreeKit as a combined GPL-3.0 / AGPL-3.0 project.

---

## Links

- **Repository**: https://github.com/ZengZichao/FigTreeKit
- **PyPI**: https://pypi.org/project/figtreekit/
- **Zenodo Archive**: [![DOI](https://zenodo.org/badge/latestdoi/https://github.com/ZengZichao/FigTreeKit.svg)](https://zenodo.org/badge/latestdoi/https://github.com/ZengZichao/FigTreeKit) (auto-generated on each GitHub Release; see [.zenodo.json](.zenodo.json))
- **Documentation**: [docs/user_manual_EN.md](docs/user_manual_EN.md)
- **FigTree**: http://tree.bio.ed.ac.uk/software/figtree/
- **TreeViewer**: https://doi.org/10.1002/ece3.10873
- **Biopython**: https://biopython.org/

---

## Tested Environment

This software is developed and tested on the following environment:

| OS | Python | Biopython | Status |
|----|--------|-----------|--------|
| macOS Tahoe 26.5.2 (Apple Silicon) | 3.11 | 1.88 | ✅ Pass |

> **Note**: FigTreeKit has only been developed and tested on macOS Tahoe 26.5.2 with Python 3.11. Compatibility with other operating systems (Windows, Linux) or Python versions has not been verified.

To reproduce the exact environment:
```bash
pip install figtreekit==1.0.3 biopython==1.87
figtreekit --self-test
```

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](https://github.com/ZengZichao/FigTreeKit/blob/main/CONTRIBUTING.md) for guidelines.

