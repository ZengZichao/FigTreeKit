# Feature Comparison Matrix

Comparison of FigTreeKit with existing phylogenetic tree libraries and tools.

## Summary Table

| Feature | FigTreeKit | DendroPy | ETE3 | Bio.Phylo | TreeGraph2 | TreeViewer |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Parsing** |  |  |  |  |  |  |
| Newick parsing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nexus parsing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nexus multi-tree | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| PhyloXML | ⚠️ validated, but not loadable for style injection | ✅ | ❌ | ✅ | ❌ | ❌ |
| **FigTree Annotations** |  |  |  |  |  |  |
| `!hilight` injection | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `!color` injection | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `!font` injection (Java format) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| FigTree settings block | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `begin figtree; ... end;` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Taxonomy Analysis** |  |  |  |  |  |  |
| Embedded taxonomy parsing (`_d_`/`_p_`) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GTDB-style table parsing (`d__`/`p__`) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Mixed format support | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Monophyly detection | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Special identifiers (LUCA/LACA/LBCA) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Clade collapse by group name | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Validation** |  |  |  |  |  |  |
| Bracket balance check | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Negative branch length detection | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Duplicate tip name detection | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Self-loop detection | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Control character / bidi override scanning | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Tree-sequence cross-validation | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| FASTA/FASTQ validation | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Alphabet detection (DNA/RNA/protein) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Styling API** |  |  |  |  |  |  |
| Layout configuration | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Clade highlighting | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| Branch coloring | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| Font configuration | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| Scale bar/axis | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Export** |  |  |  |  |  |  |
| Nexus export | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Non-mutating export (no side effects, reproducible) | ✅ | ❌ | ❌ | ❌ | N/A | ✅ |
| Preserves existing annotations | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Image rendering (PNG/PDF/SVG/JPEG) | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| **Interface** |  |  |  |  |  |  |
| Python API | ✅ | ✅ | ✅ | ✅ | ❌ (GUI) | ❌ |
| CLI batch processing | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |
| JSON config files | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Self-test mode | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Real-time logging (ISO 8601) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Quality** |  |  |  |  |  |  |
| Type hints (PEP 561) | ✅ | ❌ | ❌ | ❌ | N/A | N/A |
| Test coverage | 80.9% overall (statement-weighted); CLI 83.1%, parsing 85.8%, NEXUS serialization 89.3%, styling 83.1%, taxonomy 81.6%, validation 85.9% (see the CI report and `benchmarks/coverage_summary_v1.1.4.json`) | ~70% | ~60% | ~75% | N/A | N/A |
| Python 3.11 support | ✅ | ✅ | ❌ (3.8 max) | ✅ | N/A | N/A |

> Note: PhyloXML is recognized by format detection and structural validation, but `--validate` rejects it as "not a tree format" (exit code 3), and `FigTreeStyler` cannot load PhyloXML for style injection.

## Key Differentiators

### 1. FigTree Annotation Injection

FigTreeKit is the **only** Python library that can programmatically inject FigTree-specific annotations into Nexus files. This is achieved by studying and replicating FigTree 1.4.4's publicly available Java source code (`FigTreeNexusExporter.java`, `AttributableDecorator.java`).

**What this means in practice:**
- Other libraries can *parse* trees and *export* Nexus, but the exported files lose all FigTree-specific styling
- FigTreeKit generates Nexus files that FigTree opens with all annotations, colors, fonts, and layouts pre-configured
- This enables reproducible, scriptable tree styling workflows

### 2. Taxonomy-Aware Analysis

FigTreeKit uniquely supports taxonomy extraction from two formats:

- **Format A (Embedded)**: `_d_Bacteria_p_Cyanobacteriota_c_...` encoded in labels
- **Format B (Table)**: `d__Archaea;p__Thermoproteota;...` from mapping files
- **Mixed mode**: Both formats in the same tree, with configurable priority

This enables monophyly detection and clade collapse by taxonomic group name — features no other Python tree library provides.

### 3. Deep Input Validation

FigTreeKit performs comprehensive validation that other libraries skip:

| Check | FigTreeKit | Others |
| --- | :---: | :---: |
| Bracket balance with position | ✅ | ❌ |
| Negative branch lengths (CRITICAL) | ✅ | ❌ |
| Duplicate tip names (ERROR) | ✅ | ❌ |
| Empty node names (ERROR) | ✅ | ❌ |
| Self-loop detection | ✅ | ❌ |
| Control character / bidi override scanning | ✅ | ❌ |
| FASTA duplicate ID detection | ✅ | ❌ |
| Alphabet validation with line numbers | ✅ | ❌ |

### 4. Non-Mutating Export

FigTreeKit's export process never modifies the internal tree content (`_tree_content`). Annotations are resolved into a local copy before writing, so calling `export()` multiple times on the same `FigTreeStyler` instance always produces identical output with no side effects. This guarantees reproducibility in automated pipelines.

### 5. Self-Test Mode

`figtreekit --self-test` runs 11 built-in checks covering:
- Dependency versions
- Newick/FASTA parsing
- Taxonomy extraction (both formats)
- Monophyly logic (monophyly check + special identifiers)
- Export round-trip
- Adversarial input detection

No other tree library offers this built-in verification.

## When to Use Each Tool

| Use Case | Recommended Tool |
| --- | --- |
| Scripted FigTree-styled trees for publication | **FigTreeKit** |
| Taxonomy-aware tree analysis (monophyly, collapse) | **FigTreeKit** |
| Input validation for phylogenetic pipelines | **FigTreeKit** |
| Programmatic phylogenetic analysis (tree manipulation, simulation) | DendroPy |
| Visualization with Python (matplotlib rendering) | ETE3 |
| Simple Newick/Nexus I/O in a Bio* workflow | Bio.Phylo |
| Interactive GUI tree editing | TreeGraph2 or FigTree |
| GUI/CLI modular tree plotting (cross-platform, >100k taxa) | TreeViewer |

## Reproducing the Comparison

To verify these claims, run:

```bash
# Install all tools
pip install figtreekit dendropy ete3 biopython

# Run FigTreeKit self-test
figtreekit --self-test

# Run FigTreeKit benchmark
python benchmarks/performance.py

# Run FigTreeKit test suite and coverage
pytest test/ --cov=figtreekit
```
