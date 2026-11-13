# FigTreeKit User Manual

[中文文档](https://github.com/ZengZichao/FigTreeKit/blob/main/docs/user_manual_CN.md) | [English](#)

**Version**: 1.1.4 | **License**: GPL-2.0-or-later | **Python**: 3.11 | **Platform**: macOS (Apple Silicon) and Ubuntu Linux

FigTreeKit is a Python library for programmatic styling of phylogenetic trees for FigTree visualization. It generates FigTree-compatible Nexus files with full annotation support (`[&!hilight]`, `[&!color]`, `[&!font]`), supports taxonomy-aware clade collapse, and integrates command-line image rendering.

---

## 1. Installation

### From PyPI (recommended)

```bash
pip install figtreekit
```

### From source

```bash
git clone https://github.com/ZengZichao/FigTreeKit.git
cd FigTreeKit
pip install -e .
```

### Dependencies

| Package | Version | Required | Purpose |
|---------|---------|----------|---------|
| biopython | >=1.80, <2.0 | Yes | Tree parsing (Bio.Phylo); bracket-comment preservation requires ≥1.80 |
| psutil | any | No | Memory logging |
| tqdm | any | No | Progress bars (batch mode) |
| Java 8+ | any | No | Image rendering via FigTree JAR |

### Verify installation

```bash
figtreekit --self-test
figtreekit --version
```

---

## 2. Input Formats

### Tree Files

| Format | Extensions | Description |
|--------|-----------|-------------|
| Newick | `.nwk`, `.newick`, `.tree`, `.tre`, `.treefile`, `.nh`, `.nhy`, `.nhx` | Standard phylogenetic tree format |
| Nexus | `.nex`, `.nexus`, `.nx` | Extended format with metadata blocks |
| PhyloXML | `.xml`, `.phyloxml` | XML-based phylogenetic format |

### Sequence Files (validated formats; only FASTA/FASTQ are used for cross-validation)

| Format | Extensions |
|--------|-----------|
| FASTA | `.fasta`, `.fa`, `.fas`, `.fna`, `.faa`, `.ffn`, `.frn` |
| FASTQ | `.fastq`, `.fq` |
| GenBank | `.gb`, `.gbk`, `.genbank` |
| EMBL | `.embl` |
| Stockholm | `.stockholm`, `.sto` |
| Phylip | `.phylip`, `.phy` |
| Clustal | `.clustal`, `.aln` |

### Taxonomy Mapping Files

Two-column TSV/CSV format (auto-detected), with or without header:

```
name	taxonomy
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
```

---

## 3. Command-Line Interface — Complete Reference

### Synopsis

```
figtreekit [input] [-o OUTPUT] [OPTIONS]
```

`input` can be a single tree file or a directory (batch mode).

### 3.1 General Options

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Show help message and exit |
| `--version` | Show version, git commit hash, python and dependency versions |
| `--self-test` | Run built-in diagnostic checks (11 tests) |
| `-v` | Increase verbosity: `-v` = INFO, `-vv` = DEBUG logging |
| `-q` | Quiet mode (raise the log level to ERROR, suppressing WARNING as well as INFO; the default level is WARNING) |
| `-o OUTPUT` | Output Nexus file path (or directory in batch mode) |
| `--validate` | Validate input file only (no output) |
| `--config FILE` | JSON configuration file (see Section 5) |
| `--log-file FILE` | Write log output to file (UTF-8). The file handler itself is set to DEBUG, but records are first filtered by the logger level chosen with `-v`/`-q`: the file sees every level only with `-vv`, and `-q` limits it to ERROR |
| `--force` | Overwrite existing output file |
| `--no-clobber` | Do not overwrite an existing output file (unless `--force` is also given, which wins): skip it, log at INFO, and still report success |
| `--strip-annotations` | Strip bracket comments (NHX/bootstrap/posterior) to reduce file size |
| `--low-memory` | Low-memory mode for large trees (>10k tips) |

### 3.2 Layout Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--layout` | `rectilinear`, `polar`, `radial` | `rectilinear` | Tree layout type |
| `--expansion INT` | >= 0 | `50` | Layout expansion value |
| `--zoom FLOAT` | > 0 | `1.0` | Layout zoom factor |

### 3.3 Appearance Options

| Option | Description |
|--------|-------------|
| `--branch-width FLOAT` | Branch line width |
| `--branch-color-attribute ATTR` | Attribute used for branch coloring |
| `--background-color #RRGGBB` | Background color |
| `--foreground-color #RRGGBB` | Foreground (branch) color |
| `--selection-color #RRGGBB` | Selection highlight color |

### 3.4 Tree Rooting and Transform

| Option | Description |
|--------|-------------|
| `--rooted` | Display tree as rooted |
| `--unrooted` | Display tree as unrooted |
| `--rooting-type {user,midpoint}` | Rooting method (user selection / mid-point) |
| `--transform {cladogram,phylogram}` | Transform: cladogram (equal branches) or phylogram (proportional) |
| `--order {increasing,decreasing}` | Branch ordering by node density |
| `--order-branches` | Enable branch ordering (increasing node density) |

### 3.5 Tip Labels

| Option | Description |
|--------|-------------|
| `--tip-labels-show` | Show tip labels |
| `--tip-labels-hide` | Hide tip labels |
| `--font-name NAME` | Font family name (e.g. "Arial") |
| `--font-size PT` | Font size in points (> 0) |
| `--font-style 0-3` | 0=plain, 1=bold, 2=italic, 3=bold-italic |
| `--label-color #RRGGBB` | Tip label color (internally calls `set_tip_label_colors()`, which writes `!color` annotations; a literal `tipLabels.color` value may not be honored by headless rendering) |

### 3.6 Node Labels

| Option | Description |
|--------|-------------|
| `--node-labels-show` | Show node labels |
| `--node-labels-hide` | Hide node labels |
| `--node-display-attribute ATTR` | Attribute to display (e.g. "height", "support") |

### 3.7 Branch Labels

| Option | Description |
|--------|-------------|
| `--branch-labels-show` | Show branch labels |
| `--branch-labels-hide` | Hide branch labels |
| `--branch-display-attribute ATTR` | Attribute to display (e.g. "length", "posterior") |

### 3.8 Scale Bar and Scale Axis

| Option | Description |
|--------|-------------|
| `--scale-bar-show` | Show scale bar |
| `--scale-bar-hide` | Hide scale bar |
| `--scale-axis-show` | Show scale axis (time axis) |
| `--scale-axis-hide` | Hide scale axis |
| `--root-age FLOAT` | Root age for time scale (>= 0) |
| `--scale-factor FLOAT` | Scale factor multiplier (> 0) |

### 3.9 Polar Layout

| Option | Description |
|--------|-------------|
| `--angular-range DEG` | Angular range in degrees (0–360, default: 360) |
| `--root-angle DEG` | Root angle in degrees (0–360) |
| `--align-tip-labels` | Align tip labels radially (applies to the layout selected with `--layout`: rectilinear, radial, or polar) |

### 3.10 Radial Layout

| Option | Description |
|--------|-------------|
| `--radial-spread FLOAT` | Radial spread factor (>= 0) |

### 3.11 Rectilinear Layout

| Option | Description |
|--------|-------------|
| `--curvature INT` | Branch curvature value (>= 0) |
| `--root-length INT` | Root branch length in pixels (>= 0) |

### 3.12 Legend

| Option | Description |
|--------|-------------|
| `--legend-show` | Show legend |
| `--legend-position {top,bottom,left,right}` | Legend position (default: top) |

### 3.13 Clade Collapse

| Option | Description |
|--------|-------------|
| `--clade NAME` | Collapse a clade by taxonomic group name. Checks monophyly; warns and skips if non-monophyletic (or aborts with `--strict`). Repeatable. |
| `--strict` | Abort on non-monophyletic clades instead of skipping |
| `--collapse-taxa TAXA` | Collapse by specific taxon names (comma-separated). Supports `label=NAME` and `type=TYPE` tokens. Repeatable. |
| `--collapse-rank RANK` | Collapse ALL monophyletic groups at the given taxonomic rank (e.g. `phylum`, `class`). Requires taxonomy info. |
| `--collapse-style {collapse,cartoon}` | Collapse style for `--collapse-rank` only (ignored by `--clade` and `--collapse-taxa`): `collapse` (triangle + label) or `cartoon` (triangle preserving branch span). Default: `collapse`. |

**`--collapse-taxa` format examples:**

```bash
# Basic: comma-separated taxon names
--collapse-taxa "TaxonA,TaxonB,TaxonC"

# With explicit label and type
--collapse-taxa "TaxonA,TaxonB,label=MyClade,type=cartoon"
```

### 3.14 Clade Coloring and Highlighting

| Option | Description |
|--------|-------------|
| `--auto-color [RANK]` | Auto-assign colors to all monophyletic groups at the given rank (default: phylum). |
| `--highlight SPEC` | Highlight a clade. Format: `"A,B,C[:#RRGGBB[:width[:offset]]]"`. Repeatable. |
| `--color-clade SPEC` | Color a clade (MRCA branch only). Format: `"A,B,C:#RRGGBB"`. Repeatable. |
| `--color-all` | With `--color-clade`, color ALL descendant branches (set_clade_color_all) |
| `--font-clade SPEC` | Set font for a clade. Format: `"A,B,C:FONTNAME[-STYLE[-SIZE]]"`. Repeatable. |
| `--clear-hilights` | Clear all hilight (`!hilight`) annotations, preserving color and font annotations |

**Examples:**

```bash
# Auto-color all phylum-level groups
figtreekit tree.nwk -o out.nex --auto-color phylum

# Highlight with custom color and width
figtreekit tree.nwk -o out.nex --highlight "A,B,C:#FF0000:6:2"

# Color all descendants of a clade
figtreekit tree.nwk -o out.nex --color-clade "A,B,C:#2196F3" --color-all

# Set bold font for a clade
figtreekit tree.nwk -o out.nex --font-clade "A,B,C:Arial-BOLD-14"
```

### 3.15 Taxonomy Analysis

| Option | Description |
|--------|-------------|
| `--taxonomy-levels SPEC` | Custom rank prefix mapping (e.g. `"d:domain,sp:superphylum,p:phylum,c:class,o:order,f:family,g:genus"`) |
| `--taxonomy-delimiter-mode {reverse,greedy,segment}` | Taxonomy parsing mode (default: `reverse`) |
| `--taxonomy-table-sep CHAR` | Separator for table-format taxonomy (Format B, default: `;`) |
| `--taxonomy-source-priority {embedded,table}` | Priority when both formats are present (default: `table`) |
| `--taxonomy-mapping-file FILE` | External taxonomy mapping file (TSV/CSV) |
| `--table-sep CHAR` | Force the column delimiter of the taxonomy mapping file (default: auto-detected from the file extension) |
| `--ignore-malformed` | Skip labels that fail taxonomy parsing |
| `--analyze-taxonomy [RANK]` | Print monophyly report and exit (default rank: phylum) |
| `--check-monophyly NAME` | Check if a group is monophyletic. Supports special IDs: LUCA/LACA/LBCA/root. Repeatable. |
| `--check-taxonomy` | Check taxonomy completeness for all tips and exit |

### 3.16 Multi-Tree Handling

| Option | Description |
|--------|-------------|
| `--multi-tree MODE` | Strategy: `split`, `first`, `last`, `random`, `all` (= split), `ask` (default) |
| `--seed N` | Random seed for `--multi-tree random` |

### 3.17 Sequence Cross-Validation

| Option | Description |
|--------|-------------|
| `--sequences FILE` | Sequence file (only FASTA/FASTQ) for cross-validation with tree tips |
| `--mol-type {DNA,RNA,protein}` | Expected molecule type for validation |
| `--no-cross-check` | Skip tree-sequence cross-validation |
| `--skip-length-check` | Skip sequence length uniformity check |

### 3.18 Rendering

| Option | Description |
|--------|-------------|
| `--render FILE` | Render output to image file (PNG/PDF/SVG/JPEG by extension) |
| `--render-format {PNG,PDF,SVG,JPEG}` | Explicit render format (overrides extension detection) |
| `--render-width PX` | Render width in pixels (default: 1200) |
| `--render-height PX` | Render height in pixels (default: 800) |

### 3.19 FigTree Setup

| Option | Description |
|--------|-------------|
| `--setup-figtree` | Download FigTree v1.4.4 source, apply patches, and compile |
| `--check-figtree` | Check FigTree JAR availability and status |
| `--figtree-jar PATH` | Path to an existing FigTree JAR |

### 3.20 Advanced: Arbitrary FigTree Parameters

| Option | Description |
|--------|-------------|
| `--set KEY=VALUE` | Set any FigTree parameter directly. Repeatable. |

**Examples:**

```bash
figtreekit tree.nwk -o out.nex --set tipLabels.fontSize=8
figtreekit tree.nwk -o out.nex --set polarLayout.angularRange=180000
figtreekit tree.nwk -o out.nex --set scaleAxis.reverseAxis=true
figtreekit tree.nwk -o out.nex --set scaleAxis.significantDigits=2
figtreekit tree.nwk -o out.nex --set appearance.branchLineWidth=2.5
```

The key names follow FigTree's internal parameter naming convention (e.g. `tipLabels.*`, `nodeLabels.*`, `scaleAxis.*`, `polarLayout.*`, `rectilinearLayout.*`, `appearance.*`).

---

## 4. Python API — Complete Reference

### 4.1 FigTreeStyler Class

The core class for all tree styling operations. All setter methods return `self` for method chaining.

```python
from figtreekit import FigTreeStyler, LayoutType, FontStyle

styler = FigTreeStyler("tree.nwk")  # Load from file
styler = FigTreeStyler()            # Empty, load later
```

#### Loading Trees

| Method | Description |
|--------|-------------|
| `load_tree(source)` | Auto-detect file path vs inline Newick/Nexus content |
| `load_file(file_path, encoding=None)` | Load from file with optional encoding |
| `load_content(content)` | Load from string content |
| `get_tree_content()` | Return raw tree content string |
| `parse_tree()` | Return Bio.Phylo tree object |
| `reset(keep_tree=False)` | Reset all annotations, settings, and taxonomy config. Use `keep_tree=True` to preserve the loaded tree content |

#### Layout Configuration

| Method | Parameters | Description |
|--------|-----------|-------------|
| `set_layout(layout_type, expansion=None, zoom=None)` | `LayoutType.RECTILINEAR/POLAR/RADIAL` | Set tree layout |
| `set_polar_layout(**kwargs)` | `angular_range`, `root_angle` | Polar-specific settings |
| `set_radial_layout(**kwargs)` | `spread` | Radial-specific settings |
| `set_rectilinear_layout(**kwargs)` | `curvature`, `root_length` | Rectilinear-specific settings |

#### Appearance

| Method | Parameters | Description |
|--------|-----------|-------------|
| `set_appearance(**kwargs)` | `background_color`, `foreground_color`, `branch_line_width`, `selection_color` | Global appearance |
| `set_hilighting(is_shown=None, gradient=None)` | — | Toggle hilight display |

#### Labels

| Method | Parameters | Description |
|--------|-----------|-------------|
| `set_tip_labels(**kwargs)` | `is_shown`, `font_name`, `font_size`, `font_style` | Tip label settings. `color` and `align` are not valid mapping keys — they are written out verbatim as unrecognized `tipLabels.*` settings (a literal `tipLabels.color` may not be honored by headless rendering); use `set_tip_label_colors()` for label color and `set_align_tip_labels()` for alignment |
| `set_node_labels(**kwargs)` | `is_shown`, `display_attribute`, `font_name`, `font_size` | Node label settings |
| `set_branch_labels(**kwargs)` | `is_shown`, `display_attribute`, `font_name`, `font_size` | Branch label settings |
| `set_align_tip_labels(align=True)` | — | Align tip labels radially for the currently active layout (rectilinear / radial / polar) |

#### Scale

| Method | Parameters | Description |
|--------|-----------|-------------|
| `set_scale_bar(**kwargs)` | `is_shown`, `font_size` | Scale bar settings |
| `set_scale_axis(**kwargs)` | `is_shown`, `automatic_scale`, `reverse_axis`, `show_grid`, `font_size`, `significant_digits` | Scale axis (time axis) |
| `set_scale(**kwargs)` | `root_age`, `scale_factor` | Scale parameters |

#### Legend

| Method | Parameters | Description |
|--------|-----------|-------------|
| `set_legend(**kwargs)` | `is_shown`, `position` | Legend settings |

#### Tree Properties

| Method | Parameters | Description |
|--------|-----------|-------------|
| `set_trees(rooting, rooting_type, transform, transform_type, order, order_type)` | See the enums in 4.2 below | Rooting, transform, ordering |

#### Clade Annotations

| Method | Description |
|--------|-------------|
| `highlight_clade(taxon_names, color="#804548", width=4, offset=0.0)` | Add `[&!hilight]` annotation |
| `set_clade_color(taxon_names, color)` | Add `[&!color]` to MRCA branch only |
| `set_clade_color_all(taxon_names, color)` | Add `[&!color]` to ALL descendant branches |
| `set_clade_font(taxon_names, font_name, font_style, font_size)` | Add `[&!font]` annotation |
| `set_clade_stroke(taxon_names, stroke_width)` | Set branch stroke width |
| `set_clade_hilight(clade_identifier, tip_count, height, color)` | Low-level hilight injection |
| `style_monophyletic_clade(taxon_names, color, highlight_color, ...)` | Combined color + highlight + font for monophyletic clades |
| `clear_clade_hilights()` | Remove all hilight annotations |
| `clear_annotations()` | Remove ALL annotations |

#### Clade Collapse

| Method | Description |
|--------|-------------|
| `collapse_clade(taxon_names, label=None, collapse_type="collapse")` | Collapse clade by taxon names |
| `cartoon_clade(taxon_names, label=None)` | Collapse in cartoon style |
| `collapse_by_group(group_name, pattern=None, mapping_file=None, label=None, collapse_type="collapse")` | Collapse by taxonomic group name |
| `clear_collapses()` | Remove all collapse annotations |
| `get_collapses()` | Return list of current collapses |

#### Taxonomy Analysis

| Method | Description |
|--------|-------------|
| `configure_taxonomy(*, delimiter_mode, table_sep, source_priority, mapping_file, ignore_malformed, file_delimiter)` | Configure taxonomy parsing (keyword-only arguments) |
| `parse_label_taxonomy(pattern)` | Parse all labels with regex pattern |
| `analyze_taxonomy(pattern, mapping_file, rank, style_monophyletic, color, highlight_color)` | Full taxonomy analysis with monophyly detection |
| `analyze_taxonomy_from_mapping(mapping_file, rank, style_monophyletic)` | Analyze from external mapping file |
| `check_monophyly(taxon_names)` | Check if taxa form a monophyletic group |
| `check_monophyly_by_group(group_name, pattern, mapping_file)` | Check monophyly by group name |
| `check_taxonomy_completeness(pattern, mapping_file, required_ranks)` | Report missing taxonomy data |

#### Validation and Export

| Method | Description |
|--------|-------------|
| `validate()` | Run structural validation, return list of issues |
| `get_clade_info(taxon_names)` | Get MRCA info for taxa |
| `get_annotations()` | Return all node annotations |
| `get_settings()` | Return current FigTree settings dict |
| `apply_dict(settings_dict)` | Apply settings from dictionary |
| `set_custom_param(key, value)` | Set arbitrary FigTree parameter |
| `strip_annotations()` | Remove bracket comments from tree content |
| `export(output_file, include_taxa_block=True, single_tree=False)` | Export to Nexus file |
| `render(output_file, format=None, width=1200, height=800, jar_path=None, include_taxa_block=True, keep_nex=False, timeout=120)` | Render to image via FigTree JAR (`timeout` in seconds) |

### 4.2 Enumerations

```python
from figtreekit import LayoutType, FontStyle
from figtreekit.enums import RootingType, TransformType, OrderType
```

| Enum | Values |
|------|--------|
| `LayoutType` | `RECTILINEAR`, `POLAR`, `RADIAL` |
| `FontStyle` | `PLAIN` (0), `BOLD` (1), `ITALIC` (2), `BOLD_ITALIC` (3) |
| `RootingType` | `USER_SELECTION`, `MID_POINT` |
| `TransformType` | `CLADOGRAM`, `PHYLOGRAM` |
| `OrderType` | `INCREASING_NODE_DENSITY`, `DECREASING_NODE_DENSITY` |

### 4.3 Library Mode API

Standardized functions for pipeline integration (Snakemake/Nextflow):

```python
from figtreekit import (
    parse_taxonomy,         # parse_taxonomy(label, mode="reverse")
    parse_taxonomy_auto,    # Auto-detect format
    detect_taxonomy_format, # Detect Format A vs B
    is_monophyletic,        # is_monophyletic(tree, taxon_label, rooted=True)
    load_tree,              # load_tree(path, validate=True)
    cross_validate,         # cross_validate(tree_path, seq_path, strict=True)
    validate_input_file,    # validate_input_file(path)
    deep_validate_newick,   # deep_validate_newick(content, label="<string>")
    deep_validate_fasta,    # deep_validate_fasta(path, expected_alphabet=None)
    apply_cli_args,         # apply_cli_args(styler, args)
)
```

### 4.4 Exception Hierarchy

| Exception | Base | Purpose |
|-----------|------|---------|
| `FigTreeKitError` | `Exception` | Base class for all FigTreeKit exceptions |
| `ParseError` | `FigTreeKitError` | Tree/sequence file parsing errors |
| `ValidationError` | `FigTreeKitError` | Input validation failures |
| `ExportError` | `FigTreeKitError` | Export/render errors |
| `RenderError` | `ExportError` | Rendering failure (missing Java runtime, failed FigTree source download / Ant compilation, non-zero exit from the headless renderer) |
| `PhyloFormatError` | `ParseError` | File format error (Library Mode API alias) |
| `TaxonomyConflictError` | `ValidationError` | Taxonomy conflict (Library Mode API alias) |
| `MonophylyError` | `ValidationError` | Monophyly analysis error (Library Mode API alias) |
| `CompatibilityWarning` | `UserWarning` | FigTree compatibility warning |

---

## 5. Configuration File (JSON)

Apply multiple FigTree settings via a JSON file:

```json
{
    "layout.layoutType": "POLAR",
    "appearance.backgroundColour": "#FAFAFA",
    "appearance.branchLineWidth": 2.0,
    "tipLabels.isShown": true,
    "tipLabels.fontName": "Arial",
    "tipLabels.fontSize": 10,
    "nodeLabels.isShown": false,
    "scaleAxis.isShown": true,
    "scaleAxis.reverseAxis": true,
    "polarLayout.angularRange": 180000,
    "polarLayout.rootAngle": 90000
}
```

```bash
figtreekit input.tre -o output.nex --config style.json
```

---

## 6. Rendering

FigTreeKit includes a patched FigTree v1.4.4 JAR for headless rendering. The PyPI package bundles the pre-built JAR — usually no extra setup is needed.

### Supported output formats

| Format | Extension | Best For |
|--------|-----------|----------|
| PNG | `.png` | Web, presentations, quick preview |
| PDF | `.pdf` | Publication, vector editing |
| SVG | `.svg` | Web, scalable vector graphics |
| JPEG | `.jpg`, `.jpeg` | Small file size (lossy) |

### CLI rendering

```bash
figtreekit input.tre -o out.nex --render tree.png
figtreekit input.tre -o out.nex --render tree.pdf --render-width 2400 --render-height 1600
```

### API rendering

```python
styler.render("tree.png", format="PNG", width=2400, height=1600)
styler.render("tree.pdf", format="PDF", width=2400, height=1600)
```

### Rebuild FigTree JAR (from source)

```bash
figtreekit --setup-figtree
figtreekit --check-figtree
```

### Use existing FigTree JAR

```bash
figtreekit --setup-figtree --figtree-jar /path/to/figtree.jar
```

This combination does not trigger the source download or the Ant compilation: `setup_figtree()` only checks that the given JAR path exists and then records it in `~/.figtreekit/figtree_path.txt` for subsequent renders.

---

## 7. Taxonomy Analysis Workflow

FigTreeKit supports two taxonomy label formats:

- **Format A (embedded)**: `GCA_001_d_Archaea_p_Euryarchaeota_c_Methanobacteria_...` (rank markers wrapped in **single underscores**, e.g. `_d_`, `_p_`)
- **Format B (table)**: `d__Archaea;p__Euryarchaeota;c__Methanobacteria;...` (GTDB double-underscore markers, semicolon-separated)

### Complete CLI workflow

```bash
# 1. Check taxonomy completeness
figtreekit tree.nwk --check-taxonomy --taxonomy-levels "d:domain,p:phylum,c:class,o:order,f:family,g:genus"

# 2. Analyze monophyly at phylum level
figtreekit tree.nwk --analyze-taxonomy phylum --taxonomy-levels "d:domain,p:phylum,c:class"

# 3. Check specific group
figtreekit tree.nwk --check-monophyly Cyanobacteriota

# 4. Auto-color + collapse + export + render
figtreekit tree.nwk -o out.nex \
  --taxonomy-levels "d:domain,sp:superphylum,p:phylum,c:class,o:order,f:family,g:genus" \
  --layout polar --auto-color phylum \
  --collapse-rank class --collapse-style cartoon \
  --tip-labels-hide \
  --set polarLayout.angularRange=180000 --set polarLayout.rootAngle=90000 \
  --render out.png --render-width 2400 --render-height 1600 --force
```

### Complete API workflow

```python
from figtreekit import FigTreeStyler, LayoutType
from figtreekit.taxonomy import TaxonomyMapper, MonophylyAnalyzer
from figtreekit._renderer import render_with_figtree

# Load and configure
styler = FigTreeStyler("tree.nwk")
styler.set_layout(LayoutType.POLAR)
styler.set_tip_labels(is_shown=False)
styler.set_polar_layout(angular_range=180, root_angle=270)
styler.set_scale_axis(is_shown=True, reverse_axis=False, font_size=14, significant_digits=2)

# Taxonomy-driven coloring
styler.analyze_taxonomy(mapping_file="taxonomy.tsv", rank="phylum",
                        style_monophyletic=True, color="#E91E63")

# Collapse at class level
styler.collapse_by_group("Methanobacteria", collapse_type="cartoon")

# Export and render
styler.export("output.nex")
render_with_figtree("output.nex", "output.png", format="PNG", width=2400, height=1600)
```

---

## 8. Batch Processing

Process all tree files in a directory:

```bash
figtreekit trees_dir/ -o output_dir/ --layout polar --config style.json --force
```

---

## 9. Exit Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 0 | Success | All operations completed successfully |
| 1 | Runtime error | Dependency issues, self-test failures, unexpected errors |
| 2 | Usage error | Invalid command-line arguments, missing input |
| 3 | Data error | Invalid input data (malformed tree, bad sequences) |
| 130 | Interrupted | User pressed Ctrl+C (SIGINT) or SIGTERM received |

---

## 10. Troubleshooting

| Problem | Solution |
|---------|----------|
| "File not found" | Ensure input path exists and is a regular file |
| "Multiple trees detected" | Use `--multi-tree first/split/last/random/all` (the default `ask` aborts with exit code 2) |
| "Non-monophyletic group" warning | The collapse is skipped by default with a warning while the remaining operations continue; use `--strict` to abort and report an error instead of skipping |
| "Negative branch length" | Fix tree before processing |
| "Duplicate tip name" | Ensure all tip names are unique |
| "Control character detected" | Remove the control characters from the input file |
| "Tree-sequence cross-validation FAILED" | Use `--no-cross-check` or fix label mismatches |
| Slow processing on large trees | Use `--low-memory`; allow 2–4 GB of RAM for trees with more than 50k tips |
| FigTree JAR not found | Run `figtreekit --setup-figtree` or set `--figtree-jar` |
| `ClassCastException` in FigTree | Avoid applying `set_clade_color()` + `highlight_clade()` to the same taxa; use `set_clade_color_all()` instead |

---

## 11. FigTree Parameter Reference (--set keys)

Common keys for `--set KEY=VALUE`:

| Key | Type | Description |
|-----|------|-------------|
| `tipLabels.isShown` | bool | Show/hide tip labels |
| `tipLabels.fontName` | string | Tip label font family |
| `tipLabels.fontSize` | int | Tip label font size |
| `tipLabels.fontStyle` | int | 0=plain, 1=bold, 2=italic, 3=bold-italic |
| `tipLabels.color` | color | Tip label color (this literal value may not be honored under headless rendering; annotation-based coloring via `--label-color` / `set_tip_label_colors()` is recommended) |
| `nodeLabels.isShown` | bool | Show/hide node labels |
| `nodeLabels.displayAttribute` | string | Node label attribute |
| `branchLabels.isShown` | bool | Show/hide branch labels |
| `appearance.branchLineWidth` | float | Branch line width |
| `appearance.backgroundColour` | color | Background color |
| `layout.layoutType` | string | RECTILINEAR / POLAR / RADIAL |
| `layout.expansion` | int | Layout expansion |
| `layout.zoom` | float | Layout zoom |
| `polarLayout.angularRange` | int | Angular range (the stored value is (360 − angle) × 1000, e.g. 180000 = 180°, 0 = 360°) |
| `polarLayout.rootAngle` | int | Root angle (the stored value is (angle − 180) × 1000, e.g. 90000 = 270°) |
| `radialLayout.spread` | float | Radial spread factor (>= 0, default: 0.5; corresponds to `--radial-spread`) |
| `rectilinearLayout.curvature` | int | Branch curvature |
| `rectilinearLayout.rootLength` | int | Root length (px) |
| `scaleAxis.isShown` | bool | Show/hide scale axis |
| `scaleAxis.reverseAxis` | bool | Reverse axis direction |
| `scaleAxis.fontSize` | int | Axis font size |
| `scaleAxis.significantDigits` | int | Number of significant digits |
| `scaleBar.isShown` | bool | Show/hide scale bar |
| `legend.isShown` | bool | Show/hide legend |
| `trees.rooting` | bool | Rooted/unrooted |
| `trees.transform` | bool | Enable transform |
| `trees.transformType` | string | cladogram / phylogram |
| `trees.order` | bool | Enable branch ordering |
| `trees.orderType` | string | Increasing/Decreasing Node Density |

> **Note**: Polar layout angles are stored as FigTree's internal slider values. For the angular range the stored value is (360 − angle) × 1000, so `--set polarLayout.angularRange=180000` equals 180° and `--set polarLayout.angularRange=0` equals 360°. The root angle carries an additional offset: the stored value is (angle − 180) × 1000, so `--set polarLayout.rootAngle=90000` equals 270°. The Python API `set_polar_layout(angular_range=180)` accepts degrees directly.
# FigTreeKit User Manual

## Installation

```bash
pip install figtreekit
```

Verify installation:
```bash
figtreekit --self-test
```

## Input Formats

### Tree Files

| Format | Extensions | Description |
|--------|-----------|-------------|
| Newick | `.nwk`, `.newick`, `.tree`, `.tre`, `.treefile`, `.nh`, `.nhy`, `.nhx` | Standard phylogenetic tree format |
| Nexus | `.nex`, `.nexus`, `.nx` | Extended format with metadata blocks |
| PhyloXML | `.xml`, `.phyloxml` | XML-based phylogenetic format |

### Sequence Files (validated formats; only FASTA/FASTQ are used for cross-validation)

| Format | Extensions | Description |
|--------|-----------|-------------|
| FASTA | `.fasta`, `.fa`, `.fas`, `.fna`, `.faa`, `.ffn`, `.frn` | Standard sequence format |
| FASTQ | `.fastq`, `.fq` | Sequencing reads with quality |
| GenBank | `.gb`, `.gbk`, `.genbank` | GenBank annotated format |
| EMBL | `.embl` | EMBL sequence format |
| Stockholm | `.stockholm`, `.sto` | Multiple sequence alignment format |
| Phylip | `.phylip`, `.phy` | Phylip alignment format |
| Clustal | `.clustal`, `.aln` | Clustal alignment format |

### Taxonomy Mapping Files

Two-column TSV/CSV format (auto-detected):

With header:
```
name	taxonomy
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
```

Without header:
```
GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__
```

## Exit Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 0 | Success | All operations completed successfully |
| 1 | Runtime error | Dependency issues, self-test failures, unexpected errors |
| 2 | Usage error | Invalid command-line arguments, missing input |
| 3 | Data error | Invalid input data (malformed tree, bad sequences) |
| 130 | Interrupted | User pressed Ctrl+C (SIGINT) or SIGTERM received |

> These exit codes are centrally defined by the `ExitCode` (`IntEnum`) in `figtreekit/_cli.py`; their numeric values match this table exactly.

## Command Line Usage

### Basic Commands

```bash
figtreekit input.tre -o output.nex
figtreekit input.tre --validate
figtreekit --version    # Show version, git commit hash, python and dependency versions
figtreekit --self-test
figtreekit --help
```

### Tree Styling

```bash
figtreekit input.tre -o out.nex --layout polar --tip-labels-show
figtreekit input.tre -o out.nex --branch-width 2.0 --background-color "#FFFFFF"
figtreekit input.tre -o out.nex --font-name Arial --font-size 12
figtreekit input.tre -o out.nex --node-labels-show --node-display-attribute height
```

### Clade Collapse

```bash
figtreekit tree.nwk -o out.nex --clade Cyanobacteriota
figtreekit tree.nwk -o out.nex --clade Cyanobacteriota --strict
figtreekit tree.nwk -o out.nex --clade Cyanobacteriota --clade Proteobacteria
# Nested collapse: collapse inner and outer clades simultaneously
figtreekit tree.nwk -o out.nex --clade Phylum --clade Class
```

### Tree Rooting

```bash
figtreekit tree.nwk -o out.nex --rooted      # Set tree as rooted
figtreekit tree.nwk -o out.nex --unrooted    # Set tree as unrooted
```

### Multi-Tree Handling

```bash
figtreekit multi.nex -o out.nex --multi-tree split
figtreekit multi.nex -o out.nex --multi-tree first
figtreekit multi.nex -o out.nex --multi-tree last
figtreekit multi.nex -o out.nex --multi-tree random
figtreekit multi.nex -o out.nex --multi-tree all    # same as split
```

### Taxonomy Configuration

```bash
figtreekit tree.nwk -o out.nex --taxonomy-delimiter-mode greedy
figtreekit tree.nwk -o out.nex --taxonomy-table-sep "|"
figtreekit tree.nwk -o out.nex --taxonomy-source-priority table
figtreekit tree.nwk -o out.nex --taxonomy-levels "k:kingdom,ss:subspecies"
figtreekit tree.nwk -o out.nex --table-sep ","
figtreekit tree.nwk -o out.nex --taxonomy-mapping-file taxonomy.tsv
figtreekit tree.nwk -o out.nex --ignore-malformed
```

### Sequence Validation

```bash
figtreekit sequences.fasta --validate
figtreekit sequences.fasta --validate --mol-type DNA
figtreekit aligned.fasta --validate --skip-length-check
figtreekit tree.nwk -o out.nex --sequences sequences.fasta
figtreekit tree.nwk --validate --sequences sequences.fasta
```

> **Note**: When using `--validate` with a sequence file (FASTA/FASTQ), the CLI returns exit code 0 (success) if deep validation passes, even though the file is not a tree format. This allows independent sequence validation in scripts.

### Output Control

```bash
figtreekit tree.nwk -o existing.nex --force
figtreekit tree.nwk -o existing.nex --no-clobber
figtreekit tree.nwk -o out.nex --log-file figtreekit.log
figtreekit tree.nwk -o out.nex --strip-annotations   # Strip bracket comments (NHX/bootstrap/posterior) to reduce file size
```

### Rendering

FigTreeKit renders annotated Nexus files to PNG, PDF, SVG or JPEG through a patched FigTree v1.4.4 JAR that runs headless (no display server required). The PyPI distribution already bundles the pre-built patched JAR (`figtreekit/figtree_patched.jar`), so usually no extra setup is required:

```bash
figtreekit input.tre -o out.nex --render tree.png
figtreekit input.tre -o out.nex --render tree.pdf --render-width 1600 --render-height 1000
figtreekit input.tre -o out.nex --render tree.pdf --render-width 1600   # height falls back to the default 800
figtreekit input.tre -o out.nex --render tree.svg
```

The format is inferred from the file extension; see Section 6 for the list of supported output formats.

If you install from source or need to rebuild the patched JAR yourself, make sure that Java 8+ and Apache Ant are installed, then run:

```bash
figtreekit --check-figtree                    # Check whether a JAR is available and print its status
figtreekit --setup-figtree                    # Download the source, apply the patches and compile
figtreekit --setup-figtree --figtree-jar /path/to/figtree.jar  # Use an existing JAR
```

`--setup-figtree` downloads the official FigTree v1.4.4 source from GitHub, copies the four FigTreeKit patches from `_figtree_patch/src/figtree/` into the source tree (`treeviewer/treelayouts/RadialTreeLayout.java`, `treeviewer/decorators/AttributableDecorator.java`, `treeviewer/decorators/DiscreteColourDecorator.java` and `treeviewer/painters/ScaleAxisPainter.java`), patches `build.xml` (source/target levels) and the `javax.activation` dependency for modern JDKs (Java 9+), and finally runs `ant dist`. The compiled JAR defaults to `~/.figtreekit/figtree/dist/figtree.jar`; a JAR passed explicitly with `--figtree-jar` is recorded in `~/.figtreekit/figtree_path.txt`. See `_figtree_patch/README.md` for the equivalent manual build steps.

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

## Python API Usage

### Basic Styling

```python
from figtreekit import FigTreeStyler, LayoutType, FontStyle

styler = FigTreeStyler("tree.nwk")
styler.set_layout(LayoutType.POLAR)
styler.set_appearance(background_color="#FFFFFF", branch_line_width=2.0)
styler.highlight_clade(["A", "B"], color="#FF0000")
styler.set_clade_color(["A", "B"], color="#2196F3")
styler.set_clade_color_all(["A", "B"], color="#2196F3")  # color all branches in subtree
# Note: set_clade_color + highlight_clade on the same taxa will drop the
# MRCA-level color to avoid FigTree ClassCastException.
# Use set_clade_color_all() as the recommended alternative.
styler.set_clade_font(["A"], font_name="Arial", font_style=FontStyle.BOLD, font_size=14)
styler.set_tip_labels(is_shown=True, font_size=12)
styler.set_node_labels(is_shown=True, display_attribute="height")
styler.set_scale_bar(is_shown=True)
styler.export("output.nex")
styler.render("tree.png")
```

### Loading Trees

```python
# load_tree() auto-detects file path vs inline content
styler = FigTreeStyler()
styler.load_tree("tree.nwk")  # detected as file path
styler.load_tree("((A:0.1,B:0.2):0.3,C:0.4);")  # detected as inline content
```

### Clade Info

```python
# Get detailed clade information
info = styler.get_clade_info(["A", "B"])
# Returns dict with MRCA terminals, terminal count, monophyly status, clade size, etc.
```

### Monophyly & Collapse

```python
# Check monophyly by exact taxa
result = styler.check_monophyly(["A", "B", "C"])

# Check by taxonomic group name (auto-detects format)
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

# Strip all bracket comments (NHX, bootstrap, posterior, etc.) to reduce output size
styler.strip_annotations()
```

### Validation

```python
from figtreekit import validate_input_file, deep_validate_newick, deep_validate_fasta

# File validation
result = validate_input_file("tree.nwk")
if not result["valid"]:
    for err in result["errors"]:
        print(err)

# Deep Newick validation
dv = deep_validate_newick(content, label="tree.nwk")
for err in dv["errors"]:
    print(err)

# FASTA validation
dv = deep_validate_fasta("seqs.fasta", expected_alphabet="DNA")
```

### Taxonomy

```python
from figtreekit import parse_taxonomy_auto, detect_taxonomy_format

# Auto-detect and parse
tax = parse_taxonomy_auto("GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota_c_...")
# {"domain": "Bacteria", "phylum": "Cyanobacteriota", ...}

tax = parse_taxonomy_auto("d__Archaea;p__Euryarchaeota;s__")
# {"domain": "Archaea", "phylum": "Euryarchaeota", "species": ""}

# Apply settings from CLI arguments
from figtreekit import apply_cli_args
# apply_cli_args(styler, args)  # args from argparse.Namespace

# Configure taxonomy parsing behavior
styler.configure_taxonomy(
    delimiter_mode="reverse",      # reverse / greedy / segment
    table_sep=";",                 # format B separator
    source_priority="table",       # table / embedded
    mapping_file="taxonomy.tsv",
    ignore_malformed=False,
)

# Taxonomy analysis with automatic monophyly detection (pattern and mapping_file are both optional; an omitted mapping_file falls back to the one set via configure_taxonomy())
groups = styler.analyze_taxonomy(mapping_file="taxonomy.tsv", rank="phylum")
# Returns monophyly info for each phylum

# Analyze from mapping file (convenience method)
groups = styler.analyze_taxonomy_from_mapping("taxonomy.tsv", rank="phylum")

# Check taxonomy data completeness
completeness = styler.check_taxonomy_completeness(mapping_file="taxonomy.tsv")
```

### Library Mode API

These standardized-signature functions are intended for integration into third-party pipelines (Snakemake/Nextflow):

```python
from figtreekit import (
    parse_taxonomy,        # Standardized taxonomy parsing
    is_monophyletic,       # Monophyly detection
    load_tree,             # Tree loading
    cross_validate,        # Cross-validation
    # Standardized exception hierarchy
    PhyloFormatError,      # File format error (subclass of ParseError)
    TaxonomyConflictError, # Taxonomy conflict (subclass of ValidationError)
    MonophylyError,        # Monophyly analysis error (subclass of ValidationError)
)

# Parse taxonomy label (standardized signature)
tax = parse_taxonomy("d__Bacteria;p__Cyanobacteriota", mode="reverse")
# -> {"domain": "Bacteria", "phylum": "Cyanobacteriota"}

# Detect monophyletic group (standardized signature; rooted is kept for signature
# compatibility but currently has no effect)
mono = is_monophyletic("tree.nwk", "Cyanobacteriota", rooted=True)
# -> True / False

# Load tree file (standardized signature)
styler = load_tree("tree.nwk", validate=True)

# Cross-validate tree and sequences (standardized signature)
report = cross_validate("tree.nwk", "sequences.fasta", strict=True)
# -> {"valid": True, "matched": 50, "tree_only": [], "seq_only": [], "errors": []}
```

## Troubleshooting

### "File not found" error
Ensure the input path exists and is a regular file (outside batch mode, the input must be a single file, not a directory).

### "Multiple trees detected" error
Use `--multi-tree` to specify handling strategy:
- `--multi-tree first` — process only the first tree
- `--multi-tree split` — process all trees with numeric suffixes
- `--multi-tree ask` — print summary and abort with exit code 2 (default)

### "Non-monophyletic group" warning
The specified clade does not form a monophyletic group. By default the warning is logged, the collapse is skipped, and the remaining operations continue; pass `--strict` to abort instead of skipping (the run then exits with the data-error code 3).

### "Negative branch length" critical error
The tree contains negative branch lengths. Fix the tree before processing.

### "Duplicate tip name" error
Tree contains duplicate terminal node labels. Ensure all tip names are unique.

### "Control character detected" error
Node names contain control characters (C0/C1 control codes or Unicode bidi overrides). Remove these control characters from the input file before processing.

### "Tree-sequence cross-validation FAILED" error
Tree tip labels don't match sequence IDs. Use `--no-cross-check` to skip, or fix the labels to match.

### Large tree performance
For trees with >10,000 tips:
- Use `--low-memory` mode
- Ensure sufficient RAM for FigTree rendering (2-4 GB for >50k tips)
- Install `psutil` for DEBUG-level memory logging

## Exit Codes and Exceptions

The exit codes are centrally defined by the `ExitCode` (`IntEnum`) in `figtreekit/_cli.py`; see the "Exit Codes" table earlier in this manual for the full list.

### Exception Hierarchy

| Exception | Base Class | Purpose |
|-----------|------------|---------|
| `FigTreeKitError` | `Exception` | Base class for all FigTreeKit exceptions |
| `ParseError` | `FigTreeKitError` | Tree/sequence file parsing errors |
| `ValidationError` | `FigTreeKitError` | Input validation failures |
| `ExportError` | `FigTreeKitError` | Export/render errors |
| `RenderError` | `ExportError` | Rendering failure (missing Java runtime, failed FigTree source download / Ant compilation, non-zero exit from the headless renderer) |
| `PhyloFormatError` | `ParseError` | File format error (Library Mode API alias) |
| `TaxonomyConflictError` | `ValidationError` | Taxonomy conflict (Library Mode API alias) |
| `MonophylyError` | `ValidationError` | Monophyly analysis error (Library Mode API alias) |
| `CompatibilityWarning` | `UserWarning` | FigTree compatibility warning |
