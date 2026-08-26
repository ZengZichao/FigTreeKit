# FigTree JAR Build Provenance (review C10/D2)

Binary identities and build lineage for the two FigTree 1.4.4 binaries
relevant to FigTreeKit. Serialization compatibility is evaluated against
the **stock** binary; headless rendering ships the **patched** binary.
The two are versioned independently, and published workflows should
record both.

## Stock FigTree 1.4.4 (independent oracle)

| Item | Value |
|---|---|
| File | `_figtree_patch/figtree_original.jar` |
| SHA-256 | `0d488f82297563a2327ced57e85bc40204f70e0d34de38d51db4da1998be0346` |
| Origin | Unmodified FigTree v1.4.4 build (© Andrew Rambaut, GPL-2.0-or-later), preserved for auditability |
| Role | Independent acceptance oracle: `test/test_conformance.py::TestStockFigTreeAcceptance` verifies that this binary — built without any FigTreeKit modification — parses FigTreeKit-generated annotated NEXUS and renders PDF/PNG. The fixture uses only `!color`/`!hilight` annotations (outside the four patched rendering behaviors), so acceptance is attributable to serialization compatibility rather than to the patched renderer. |
| CLI convention | `java -jar figtree_original.jar -graphic <FMT> <input> <output>` (input before output) |

## Patched FigTree 1.4.4 (bundled renderer)

| Item | Value |
|---|---|
| File | `figtreekit/figtree_patched.jar` (authoritative shipped copy) |
| SHA-256 | `13ba6b28335ec815dedab37d98da01e7a8e89ad997eea1ac38db62c55c7fd892` |
| Source base | Official FigTree v1.4.4 source with exactly four modified files (see `README.md`): `RadialTreeLayout.java`, `ScaleAxisPainter.java`, `DiscreteColourDecorator.java`, `AttributableDecorator.java` |
| Target | Java 8 (`java version "1.8.0_501"` used in the frozen benchmark environment) |
| Build | Apache Ant `dist` target on the patched source tree; automated reproduction via `figtreekit --setup-figtree` (downloads upstream source, applies the four files from `src/`, applies modern-JDK compatibility fixes, compiles) |
| Dependencies / licenses | iText (see repository `NOTICE`), Batik, jebl, JDOM — redistributed under the terms documented in `NOTICE` |

## Evidence boundary

* Positive behavior tests for the four patched rendering changes:
  `test/test_rendering_mock.py` and the patched-JAR render acceptance in
  `test/test_conformance.py::TestRenderAcceptance`.
* Stock/patched agreement outside the four intended changes is
  demonstrated by the stock acceptance tests above (same input, both
  binaries succeed) and by the documented scope of the four diffs; a
  full pixel-level regression matrix is not claimed.
