# Changelog

All notable changes to **FigTreeKit** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Version numbers below match the `vX.Y.Z` git tags and the corresponding PyPI
and Zenodo releases.

## [1.1.4] - 2026-09-27

### Fixed

- `examples/05_gtdb_workflow.py` raised `NameError` at the order-level collapse
  step. The audit block re-imported `group_tip_count` inside `main()`, which
  made the name local to that function, so the comprehension that selects the
  multi-tip groups could not see it even though the module already imports it.
  The example therefore crashed before writing panel B on every run, including
  the tagged v1.1.3 archive.
- CI never executed anything under `examples/`, which is why the above shipped.
  The workflow now runs `examples/06_beast_laca_workflow.py` end to end — it
  carries its own tree, so no external data are needed — and asserts the group
  counts the article quotes.
- The test job installs `[render]`, so the post-render appearance pass is
  exercised in CI and the coverage the pipeline reports matches the coverage
  the article publishes.

## [1.1.3] - 2026-09-26

### Fixed

- **`--label-color` reached FigTree as an attribute the renderer ignores.**
  The flag routed through `FigTreeStyler.set_tip_labels()`, writing
  `tipLabels.colorAttribute="#RRGGBB"`; stock FigTree 1.4.4's headless renderer
  does not honour a colour literal in that key, so the requested tip-label
  colour was silently dropped from rendered output. The flag now routes through
  the new `set_tip_label_colors()` API, which registers one `[&!color=…]` node
  annotation per tip and sets `colorAttribute="!color"`.
- **Monophyly rate could exceed 100%.** Single-taxon groups are trivially
  exclusive and carry no signal, so they were removed from the denominator of
  `monophyly_rate` — but the numerator still counted them. They are now removed
  from both sides, an empty denominator reports `0.0`, and the summary exposes
  `multi_tip_groups` and `multi_tip_monophyletic` separately from the total group
  count. On the 700-tip LACA-rooted test tree (125 groups, 66 of them
  single-taxon, 119 assessed exclusive) the rate moves from the impossible
  119/59 = 201.7% to 53/59 = 89.8%.

### Added

- `FigTreeStyler.set_tip_label_colors()` — set the colour of every tip label as
  FigTree-parseable node annotations.
- Post-render appearance pass (`figtreekit._appearance_post`):
  `--background-color` and `--foreground-color` now reach raster output instead
  of being left at FigTree's headless defaults. `render_with_figtree()` gained
  `background_color`, `foreground_color` and `label_color` keyword arguments.
  Vector output (PDF/SVG) is returned untouched.
- New optional dependency extras: `[render]` (Pillow, for the appearance pass)
  and `[benchmark]` (numpy + scipy, for re-running the measurement suite). The
  render path degrades with a `CompatibilityWarning` rather than failing.
- `benchmarks/gtdb_paths.py` resolves the GTDB reference trees from
  `$FTK_GTDB_DIR`, so the large-tree measurements run from a clean clone
  instead of a hard-coded local path; `benchmarks/gtdb_data/README.md` records
  where the trees come from.
- `examples/_audit.py` makes the two example workflows emit machine-readable
  audit files (per-clade verdicts and annotation accounting) instead of only
  printing a summary.
- `scripts/generate_conformance_index.py` derives
  `benchmarks/conformance_corpus_index.csv`, a machine-readable index of the
  golden conformance corpus keyed to the test that exercises each branch.
- A frozen `environment-benchmark.yml` records the benchmarking interpreter.
- JPEG rendering regression tests (`test/test_render_jpeg.py`).

### Changed

- Benchmark confidence intervals use exact Student-*t* critical values (scipy,
  with a four-term asymptotic fallback) instead of a hard-coded table, and now
  record `r_squared`, `df`, `n_points` and the critical value alongside each fit.
- GTDB large-tree memory is reported in SI megabytes (10<sup>6</sup> bytes);
  earlier result files labelled mebibyte values as `mb`.
- Added the `Operating System :: POSIX :: Linux` classifier; Linux is exercised
  continuously in CI alongside macOS.
- Article figures and the statistics tabulated in the article are produced by
  figure-generation code supplied with the article rather than by this
  repository, which ships the measurements they read (raw CSVs and the summary
  JSONs recomputed from them) and the scripts that take them.

**Test count:** 801 collected (v1.1.1, v1.1.2) → **808** collected. The seven
additional tests are the three monophyly-rate accounting regressions and the
four JPEG rendering tests. Both counts include the five property-based tests in
`test/test_hypothesis.py`, which are collected only when Hypothesis is
installed; without it the suite collects 796 and 803 respectively.

## [1.1.2] - 2026-09-03

Publication DOI and citation metadata updates; removal of redundant files,
including the `benchmarks_frozen_backup_2026-08-26/` provenance directory.
Fixed the memory-IQR error bars in `benchmarks/make_figures.py`. No change to
the installed package's behaviour; 801 tests collected.

## [1.1.1] - 2026-08-26

Independent stock-FigTree serialization oracle, build provenance for the
bundled Java archive, and the dual-panel figure workflow. Benchmark statistics
and the frozen benchmark environment were stamped with their source commit.

## [1.1.0] - 2026-08-26

Review-driven contract hardening, benchmark statistics corrections and version
metadata update.

## [1.0.x] - 2026-08

Initial public releases: core styling, taxonomy-aware auditing, headless
rendering integration, Docker self-test and tag-triggered PyPI publishing.
See the `v1.0.0`–`v1.0.3` git tags for details.

[1.1.4]: https://github.com/ZengZichao/FigTreeKit/releases/tag/v1.1.4
[1.1.3]: https://github.com/ZengZichao/FigTreeKit/releases/tag/v1.1.3
[1.1.2]: https://github.com/ZengZichao/FigTreeKit/releases/tag/v1.1.2
[1.1.1]: https://github.com/ZengZichao/FigTreeKit/releases/tag/v1.1.1
