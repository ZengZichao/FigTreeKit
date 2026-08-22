# SPDX-License-Identifier: GPL-2.0-or-later
# This file is part of FigTreeKit; see LICENSE and NOTICE for licensing terms.
"""Nexus serialization and FigTree block generation."""

# Copyright (C) 2024-2026 Zeng Zichao
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import numbers
import re
from typing import Any, Dict, Optional

# Color patterns
COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')
OLD_STYLE_COLOR_PATTERN = re.compile(r'^#-\d+$')
# 3-digit hex shorthand (#RGB) — expanded to 6 digits on serialize.
_SHORT_HEX_PATTERN = re.compile(r'^#[0-9A-Fa-f]{3}$')

# Parameters read by FigTree using getFloat()/getDouble(); these must be
# serialized with a decimal point (e.g. "1.0" not "1").  Hoisted to module
# scope so generate_figtree_block does not rebuild the set on every call.
_FLOAT_PARAMS = {
    'appearance.branchLineWidth',
    'appearance.branchMinLineWidth',
    'scaleBar.lineWidth',
    'scaleBar.scaleRange',
    'scaleBar.fontSize',
    'scaleAxis.lineWidth',
    'scaleAxis.fontSize',
    'scaleAxis.majorTicks',
    'scaleAxis.origin',
    'nodeBars.barWidth',
    'nodeBars.fontSize',
    'nodeShapes.size',
    'nodeShapes.strokeWidth',
    'nodeShapes.fontSize',
    'nodeLabels.fontSize',
    'branchLabels.fontSize',
    'tipLabels.fontSize',
    'legend.fontSize',
    'legend.backgroundOpacity',
    'legend.borderWidth',
    'legend.x',
    'legend.y',
    'scale.rootAge',
    'scale.scaleFactor',
    'scale.offsetAge',
    'radialLayout.spread',
}


def _expand_hex_color(value: Any) -> Optional[str]:
    """Normalize a color string for serialization.

    Returns the lowercased 6-digit hex form (expanding a 3-digit ``#RGB``
    shorthand to ``#RRGGBB``), or ``None`` if *value* is not a recognized
    hex color.

    This is a non-breaking enhancement: existing 6-digit colors are passed
    through unchanged, while the ``#RGB`` shorthand — which FigTree itself
    does not accept — is expanded so the exported block stays valid.
    """
    if not isinstance(value, str):
        return None
    if COLOR_PATTERN.match(value):
        return value.lower()
    if _SHORT_HEX_PATTERN.match(value):
        return '#' + ''.join(ch * 2 for ch in value[1:]).lower()
    return None


def serialize_value(value: Any, force_float: bool = False) -> str:
    """Serialize a Python value to its FigTree Nexus string representation.

    Follows ``FigTreeNexusExporter.java`` ``createString()`` rules:

    - ``null`` / ``None`` → ``"null"``
    - ``bool`` → ``"true"`` / ``"false"`` (lowercase)
    - ``color`` (``#RRGGBB`` or ``#-decimal``) → unquoted, lowercased
    - ``int`` / ``float`` that is integer → integer string (no decimal point)
    - ``float`` → decimal string
    - ``str`` → double-quoted (e.g., ``"Arial"``)

    This prevents "float poisoning" where Java's ``Integer.parseInt`` would
    fail on ``"1.0"`` for parameters like ``fontStyle``.

    Args:
        force_float: If True, always output numeric values with decimal point
            (e.g., ``1.0`` instead of ``1``). This is needed for settings like
            ``branchLineWidth`` that FigTree reads with ``getFloat()``.

    Note:
        Boolean parameters must use Python ``True``/``False``. Integer values
        ``0`` and ``1`` will be serialized as ``"0"`` and ``"1"`` respectively,
        which FigTree may not interpret correctly for boolean settings.
    """
    if value is None or (isinstance(value, str) and value.lower() == "null"):
        return "null"

    if isinstance(value, bool):
        return "true" if value else "false"

    # Colors: unquoted, lowercase.  Support the #RGB shorthand by expanding
    # it to #RRGGBB so FigTree (which only reads 6-digit hex) accepts it.
    if isinstance(value, str):
        expanded = _expand_hex_color(value)
        if expanded is not None:
            return expanded
        if OLD_STYLE_COLOR_PATTERN.match(value):
            return value.lower()

    # Numbers: integers must not have decimal point.
    # Use numbers.Integral/Real to handle numpy scalar types.
    if isinstance(value, numbers.Integral):
        if force_float:
            return str(float(value))
        return str(int(value))
    if isinstance(value, numbers.Real):
        if force_float:
            return str(float(value))
        if float(value).is_integer():
            return str(int(value))
        return str(value)

    # Strings: all non-color strings are double-quoted with backslash escaping
    # (extends FigTreeNexusExporter.java createString to handle embedded quotes)
    if isinstance(value, str):
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'

    return str(value)


def generate_figtree_block(settings_dict: Dict[str, Any]) -> str:
    """Generate the ``begin figtree; ... end;`` block content.

    Args:
        settings_dict: Flat dictionary of ``"category.param"`` → value.

    Returns:
        Formatted block string, or empty string if no settings.
    """
    if not settings_dict:
        return ""

    # These parameters are read by FigTree using getFloat()/getDouble()
    # and must be serialized with decimal points (e.g., "1.0" not "1").
    # Reuse the module-level constant instead of rebuilding it per call.
    FLOAT_PARAMS = _FLOAT_PARAMS

    lines = ["begin figtree;"]
    for key, value in sorted(settings_dict.items()):
        force_float = key in FLOAT_PARAMS
        serialized = serialize_value(value, force_float=force_float)
        if serialized:
            lines.append(f"\tset {key}={serialized};")
    lines.append("end;")
    return '\n'.join(lines)


# ── Nexus trees/taxa block writers (moved from styler.py) ───────────────
# These functions own the physical writing of the taxa and trees blocks so
# that ``styler.py`` only orchestrates; serialization details live here in
# the serialization layer.

# Regex fallback used ONLY when the character scanner finds no tree
# declaration at all (degenerate trees blocks without a ``tree ... =`` line).
_NESTED_COMMENT = r"\[(?:[^\[\]]|\[(?:[^\[\]]|\[[^\]]*\])*\])*\]"
_TREE_VALUE_PATTERN = re.compile(
    r'tree\s+\S+\s*=\s*(?:(?:[^\[\];]|' + _NESTED_COMMENT + r')*;)',
    re.DOTALL | re.IGNORECASE
)


def _tree_declaration_head(trees_content: str, start: int, end: int) -> str:
    """Return the declaration head ``tree NAME = [leading comments] ``.

    The head spans from *start* (the ``tree`` keyword) through the ``=`` and
    any leading bracket comments that precede the Newick value, so that
    replacement preserves BEAST-style metadata comments attached before the
    tree string.
    """
    from ._parser import _TREE_NAME_PATTERN

    m = _TREE_NAME_PATTERN.match(trees_content, start)
    if m is None:  # pragma: no cover - spans are always produced by this regex
        return trees_content[start:end]
    j = m.end()
    # Skip leading bracket comments (arbitrary nesting) via a depth counter.
    while j < end:
        if trees_content[j].isspace():
            j += 1
            continue
        if trees_content[j] != '[':
            break
        depth = 0
        while j < end:
            if trees_content[j] == '[':
                depth += 1
            elif trees_content[j] == ']':
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
    return trees_content[start:j]


def write_taxa_block(
    out,
    *,
    include_taxa_block: bool,
    is_nexus_format: bool,
    tree_content: Optional[str],
    resolved_content: Optional[str],
    has_collapses: bool,
    taxa_block: Optional[str],
) -> None:
    """Write the taxa block to the output file.

    For Newick input a taxa block is generated from the (resolved) tree
    content; for Nexus input the original block is preserved verbatim.
    """
    # Local import to avoid a module-level cycle (_parser imports nothing
    # from _serializer, so this is safe either way).
    from ._parser import extract_taxa_from_newick

    if not include_taxa_block:
        return
    if not is_nexus_format:
        # Use resolved content when collapses may have changed terminal names
        source = (resolved_content
                  if (resolved_content and has_collapses)
                  else tree_content)
        taxa = extract_taxa_from_newick(source)
        out.write("begin taxa;\n")
        out.write(f"\tdimensions ntax={len(taxa)};\n")
        out.write("\ttaxlabels\n")
        for taxon in taxa:
            out.write(f"\t{taxon}\n")
        out.write("\t;\n")
        out.write("end;\n\n")
    elif taxa_block:
        out.write(taxa_block)
        out.write("\n\n")


def write_trees_block(
    out,
    *,
    resolved_tree_content: str,
    single_tree: bool,
    is_nexus_format: bool,
    translate_block: Optional[str],
    tree_block: Optional[str],
    has_trees: bool,
    tree_index: int,
) -> None:
    """Write the trees block to the output file.

    Args:
        out: File-like object to write to.
        resolved_tree_content: Tree content with annotations already applied.
        single_tree: If True, export only the selected tree (for CLI
            multi-tree modes). Otherwise preserve all trees.
        is_nexus_format: Whether the input was Nexus (multi-tree capable).
        translate_block: Original BEAST translate block, if any.
        tree_block: Original trees block, if Nexus input.
        has_trees: Whether any tree declarations were found in the input.
        tree_index: Index of the tree to replace within multi-tree input.
    """
    from ._parser import extract_trees_block_content, find_tree_declaration_spans

    out.write("begin trees;\n")
    if translate_block:
        out.write(translate_block)
        out.write("\n")

    if is_nexus_format and tree_block and has_trees:
        trees_content = extract_trees_block_content(tree_block)
        # Character-scanner spans: quote- and comment-aware, arbitrary
        # nesting depth (no regex nesting limit).
        spans = find_tree_declaration_spans(trees_content)
        clean = resolved_tree_content.rstrip(';')
        if spans and tree_index < len(spans):
            start, end = spans[tree_index]
            decl = _tree_declaration_head(trees_content, start, end)
            replacement = f'\t{decl}{clean};'
            if single_tree:
                trees_content = replacement
            else:
                trees_content = (
                    trees_content[:start] +
                    replacement +
                    trees_content[end:]
                )
        elif spans:
            # Requested tree_index out of range: fall back to replacing the
            # first declaration (matches historical behaviour).
            start, end = spans[0]
            decl = _tree_declaration_head(trees_content, start, end)
            replacement = f'\t{decl}{clean};'
            if single_tree:
                trees_content = replacement
            else:
                trees_content = (
                    trees_content[:start] +
                    replacement +
                    trees_content[end:]
                )
        else:
            # Degenerate block without any ``tree ... =`` declaration: the
            # scanner found nothing, so fall back to a tolerant regex
            # substitution (left unchanged when even that fails to match).
            replacement = f'\ttree TREE1 = {clean};'
            trees_content = _TREE_VALUE_PATTERN.sub(replacement, trees_content, count=1)
        out.write(trees_content)
        out.write("\n")
    else:
        clean = resolved_tree_content.rstrip(';')
        out.write(f"\ttree TREE1 = {clean};\n")

    out.write("end;\n\n")


def write_figtree_block(out, figtree_block: str) -> None:
    """Write the figtree settings block to the output file."""
    if figtree_block:
        out.write(figtree_block)
        out.write("\n")
