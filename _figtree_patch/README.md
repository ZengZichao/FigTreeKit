# FigTree Patch for FigTreeKit

This directory contains the modified FigTree v1.4.4 sources and the pre-built patched JAR used by FigTreeKit's rendering features.

## What is patched?

FigTreeKit ships with a patched build of [FigTree v1.4.4](http://tree.bio.ed.ac.uk/software/figtree/) (© Andrew Rambaut, GPL-2.0-or-later). Four source files are modified:

- `src/figtree/treeviewer/treelayouts/RadialTreeLayout.java` — adds
  clade-collapse (triangle) rendering support for the radial layout.
- `src/figtree/treeviewer/painters/ScaleAxisPainter.java` — adds a
  radial time axis for the polar layout (`paintPolarAxis`), drawn from
  the tree centre outward; stock FigTree only paints a scale axis for
  the rectilinear layout.
- `src/figtree/treeviewer/decorators/DiscreteColourDecorator.java` —
  uses a `LinkedHashMap` instead of a `TreeMap` so discrete colour
  categories keep insertion order rather than being re-sorted.
- `src/figtree/treeviewer/decorators/AttributableDecorator.java` —
  uses the exact annotation colour for range fills instead of
  `Colour.brighter()`, so scripted colours render as specified.

All other rendering behaviour is unchanged. The patched JAR is built
from the official FigTree v1.4.4 source with these changes, targeting
Java 8.

The original unmodified JAR is preserved as `figtree_original.jar` for
reference. The compiled patched JAR is `figtree_patched_new.jar` and is
byte-identical to the copy shipped inside the Python package as
`figtreekit/figtree_patched.jar`.

## Automatic rebuild

If you install FigTreeKit from source and run:

```bash
figtreekit --setup-figtree
```

FigTreeKit will:

1. Download FigTree v1.4.4 source from https://github.com/rambaut/figtree
2. Copy the four patched source files from `_figtree_patch/src/` into the downloaded source tree
3. Apply compatibility fixes for modern JDKs (`build.xml`, `DiscreteColourScaleDialog.java`)
4. Compile with Apache Ant (`ant dist`)
5. Save the resulting `figtree.jar` to `~/.figtreekit/figtree/dist/figtree.jar`

## Manual rebuild

If you prefer to build the patched JAR manually:

```bash
# 1. Download FigTree v1.4.4 source
wget https://github.com/rambaut/figtree/archive/refs/tags/v1.4.4.zip
unzip v1.4.4.zip
cd figtree-1.4.4

# 2. Apply FigTreeKit patch (four modified source files)
cp -R /path/to/figtreekit/_figtree_patch/src/figtree src/

# 3. Build (Apache Ant required)
ant dist

# 4. The patched JAR is at dist/figtree.jar
```

## License

FigTree and its modifications are licensed under the GNU General Public License v2.0 or later (GPL-2.0-or-later). The patched JAR also bundles iText for PDF export, which is licensed under the GNU Affero General Public License v3 (AGPL-3.0).

See the top-level `LICENSE` file and the original FigTree source headers for full license text.
