"""FigTreeStyler — main API for styling phylogenetic trees."""

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

import colorsys
import os
import re
import warnings
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .annotations import CladeCollapse, NodeAnnotation
from .enums import FontStyle, LayoutType, OrderType, RootingType, TransformType
from .exceptions import CompatibilityWarning, ExportError, ParseError, ValidationError
from .validators import TreeValidator, scan_for_anomalous_content, read_text_with_fallback
from .taxonomy import TaxonomyMapper, MonophylyAnalyzer
from ._defaults import get_figtree_defaults
from ._parser import (
    apply_parsed_setting,
    extract_bracket_comments,
    extract_taxa_from_newick,
    load_existing_figtree_block,
    parse_nexus_content,
    reinsert_bracket_comments,
    strip_square_bracket_comments,
)
from ._serializer import (
    COLOR_PATTERN,
    OLD_STYLE_COLOR_PATTERN,
    generate_figtree_block,
    serialize_value,
    write_figtree_block,
    write_taxa_block,
    write_trees_block,
)

# Java Font.decode() format strings — note "BOLDITALIC" (no underscore),
# which differs from FontStyle.BOLD_ITALIC's Python enum name.
_FONT_STYLE_MAP: Dict[int, str] = {0: "PLAIN", 1: "BOLD", 2: "ITALIC", 3: "BOLDITALIC"}

# Explicit states of the BEAST translate-block parser (see
# ``FigTreeStyler._parse_translate_block``).  The machine is always in
# exactly one of these four states:
#
# * NORMAL            — outside any quoted region; commas delimit entries.
# * IN_SINGLE_QUOTE   — inside a single-quoted taxon name.
# * IN_DOUBLE_QUOTE   — inside a double-quoted taxon name.
# * ESCAPING          — a matching quote was just seen inside a quoted
#                       region; the next character decides whether it is a
#                       doubled-quote escape ('' / "") or the closing quote.
TRANSLATE_NORMAL = "NORMAL"
TRANSLATE_IN_SINGLE_QUOTE = "IN_SINGLE_QUOTE"
TRANSLATE_IN_DOUBLE_QUOTE = "IN_DOUBLE_QUOTE"
TRANSLATE_ESCAPING = "ESCAPING"

# Cached default settings (fix #25).  Previously every ``FigTreeSettings``
# field used a fresh ``get_figtree_defaults()`` call per instance, which is
# wasteful when many styler objects are created.  Memoize the result once
# per process; each field still receives an independent ``.copy()`` so that
# instances never share mutable default dictionaries.
_DEFAULTS_CACHE: Optional[Dict[str, Any]] = None


def _get_figtree_defaults() -> Dict[str, Any]:
    """Return the FigTree default settings, memoized at module level (fix #25).

    ``FigTreeSettings`` previously invoked ``get_figtree_defaults()`` once per
    field per instance.  This caches the dictionary so it is built a single
    time, while each field still copies the relevant sub-dictionary so that
    instances do not share mutable state.
    """
    global _DEFAULTS_CACHE
    if _DEFAULTS_CACHE is None:
        _DEFAULTS_CACHE = get_figtree_defaults()
    return _DEFAULTS_CACHE

@dataclass
class FigTreeSettings:
    """Container for all FigTree settings organized by category.

    Settings are stored as raw Python types and serialized via
    :func:`~figtreekit._serializer.serialize_value`.
    """
    appearance: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["appearance"].copy())
    layout: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["layout"].copy())
    trees: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["trees"].copy())
    tipLabels: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["tipLabels"].copy())
    nodeLabels: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["nodeLabels"].copy())
    branchLabels: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["branchLabels"].copy())
    scaleBar: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["scaleBar"].copy())
    scaleAxis: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["scaleAxis"].copy())
    scale: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["scale"].copy())
    polarLayout: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["polarLayout"].copy())
    radialLayout: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["radialLayout"].copy())
    rectilinearLayout: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["rectilinearLayout"].copy())
    nodeBars: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["nodeBars"].copy())
    nodeShapes: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["nodeShapes"].copy())
    legend: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["legend"].copy())
    hilighting: Dict[str, Any] = field(default_factory=lambda: _get_figtree_defaults()["hilighting"].copy())
    _custom: Dict[str, Any] = field(default_factory=dict)
    _node_annotations: List[NodeAnnotation] = field(default_factory=list)
    _collapses: List[CladeCollapse] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for category, values in vars(self).items():
            if category.startswith('_'):
                continue
            for key, value in values.items():
                result[f"{category}.{key}"] = value
        for key, value in self._custom.items():
            result[key] = value
        return result

    def set(self, key: str, value: Any) -> None:
        """Set a single setting by its ``"category.param"`` key.

        This is the public, supported way to assign a parsed setting.  It
        replaces the previous practice of reaching into ``self.__dict__``
        directly (see :func:`figtreekit._parser.apply_parsed_setting`).

        Args:
            key: Setting key, either ``"category.param"`` or a bare
                ``"param"`` (in which case *category* and *param* are the
                same string).
            value: Value to assign.  Stored in the matching category dict,
                or in :attr:`_custom` when the category is unknown.
        """
        if '.' in key:
            category, param = key.split('.', 1)
        else:
            category = key
            param = key
        # Only the named category dicts (not the private ``_``-prefixed fields)
        # are valid targets; this mirrors to_dict()'s view of the settings.
        # Look the category up directly (O(1)) instead of rebuilding a dict of
        # every category on every call — the previous O(n) rebuild per call
        # made bulk loads (many settings) O(n²) for no reason.
        attr = getattr(self, category, None)
        if isinstance(attr, dict) and not category.startswith('_'):
            attr[param] = value
        else:
            self._custom[key] = value


class FigTreeStyler:
    """Main class for styling phylogenetic trees for FigTree.

    Reads Newick or Nexus files, applies aesthetic configurations via a
    Pythonic API, and exports FigTree-compatible Nexus files with proper
    ``begin figtree; ... end;`` blocks.

    Example:
        Basic usage with method chaining::

            from figtreekit import FigTreeStyler, LayoutType

            styler = FigTreeStyler("input.tre")
            styler.set_layout(LayoutType.POLAR)
            styler.highlight_clade(["T001", "T002"], color="#2196F3")
            styler.export("styled.nex")

        Loading from string::

            newick = "((A:0.1,B:0.2):0.3,C:0.4);"
            styler = FigTreeStyler().load_content(newick)
    """

    COLOR_PATTERN = COLOR_PATTERN
    OLD_STYLE_COLOR_PATTERN = OLD_STYLE_COLOR_PATTERN
    HILIGHT_ATTRIBUTE_NAME = "!hilight"
    COLOR_ATTRIBUTE_NAME = "!color"
    FONT_ATTRIBUTE_NAME = "!font"

    def __init__(self, input_file: Optional[str] = None, tree_index: int = 0,
                 strict: bool = False):
        self._settings = FigTreeSettings()
        self._tree_content: Optional[str] = None
        self._is_nexus_format: bool = False
        self._tree_block: Optional[str] = None
        self._taxa_block: Optional[str] = None
        self._translate_block: Optional[str] = None
        self._all_trees: List[str] = []
        self._tree_index: int = tree_index
        self._strict: bool = strict
        self._hilight_marks: List[Tuple[Any, int, float, str]] = []
        # Taxonomy parsing configuration
        self._taxonomy_delimiter_mode: str = "reverse"
        self._taxonomy_table_sep: str = ";"
        self._taxonomy_source_priority: str = "table"
        self._taxonomy_mapping_file: Optional[str] = None
        self._ignore_malformed: bool = False
        self._table_sep: Optional[str] = None
        if input_file:
            self.load_file(input_file)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_file(self, file_path: str, encoding: Optional[str] = None) -> "FigTreeStyler":
        """Load a tree file (Newick or Nexus format).

        Args:
            file_path: Path to the tree file.
            encoding: File encoding. If ``None`` (default), tries UTF-8 first,
                then falls back to latin-1 for legacy files.

        Returns:
            self for method chaining.

        Raises:
            FileNotFoundError: If the file does not exist.
            ParseError: If the content cannot be parsed.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Tree file not found: {file_path}")

        if encoding:
            content = path.read_text(encoding=encoding)
        else:
            # Use the shared fallback reader so behaviour matches the rest of
            # the codebase: tries UTF-8, then UTF-8-sig (BOM), then latin-1,
            # and opens with newline='' so universal-newline translation does
            # not alter reported offsets / line numbers.
            content, warns = read_text_with_fallback(str(path), label=path.name)
            for w in warns:
                warnings.warn(w, CompatibilityWarning)

        return self.load_content(content)

    def load_content(self, content: str) -> "FigTreeStyler":
        """Load tree content from a string.

        Args:
            content: Newick or Nexus format tree content.

        Returns:
            self for method chaining.

        Raises:
            ParseError: If the content is empty or malformed.
            ValidationError: If strict mode is enabled (``strict=True``)
                and negative branch lengths are detected in the tree.
        """
        content = content.strip()
        if not content:
            raise ParseError("Empty tree content")

        # Scan for malicious content (control characters, bidi overrides)
        mal_errors = scan_for_anomalous_content(content, label="tree content", source="input")
        if mal_errors:
            raise ValidationError(
                "Malicious content detected:\n" + "\n".join(mal_errors)
            )

        self._tree_content = None
        self._is_nexus_format = False
        self._tree_block = None
        self._taxa_block = None
        self._translate_block = None
        self._all_trees = []
        self._settings._node_annotations.clear()
        self._settings._collapses.clear()
        self._hilight_marks = []
        # Drop any memoized node-height caches — a fresh tree is being loaded.
        self._node_height_cache = {}
        self._height_cache = {}

        if content.upper().startswith('#NEXUS'):
            self._is_nexus_format = True
            self._parse_nexus_content(content)
        else:
            if content.rstrip() == ';':
                warnings.warn(
                    "Loaded Newick string contains only a semicolon (empty tree). "
                    "This is technically valid but may indicate missing tree data.",
                    CompatibilityWarning,
                )
            self._is_nexus_format = False
            if not content.rstrip().endswith(';'):
                last_taxon = re.findall(r'([A-Za-z0-9_][A-Za-z0-9_.]*)\s*:', content)
                ctx = f" after clade '{last_taxon[-1]}'" if last_taxon else ""
                raise ParseError(f"Invalid Newick: missing semicolon{ctx}")
            self._tree_content = content

        # Strict mode: check for negative branch lengths at load time
        if self._strict and self._tree_content:
            self._parse_tree_with_biopython(self._tree_content)

        # Advisory warnings for biologically unusual but technically valid trees
        if self._tree_content:
            issues = TreeValidator.validate_biological_plausibility(self._tree_content)
            for issue in issues:
                warnings.warn(issue, CompatibilityWarning)

        return self

    def load_tree(self, source: str, **kwargs) -> "FigTreeStyler":
        """Load tree from file or string content.

        This is a convenience alias that auto-detects whether *source* is a
        file path or inline content.

        Args:
            source: File path or Newick/Nexus string content.
            **kwargs: Passed to :meth:`load_file` or :meth:`load_content`.

        Returns:
            self for method chaining.

        Raises:
            FileNotFoundError: If *source* looks like a file path but doesn't exist.
            ParseError: If the content cannot be parsed.
        """
        # If source looks like an existing file, load from file
        if os.path.exists(source):
            return self.load_file(source, **kwargs)
        # Otherwise treat as inline content
        return self.load_content(source, **kwargs)

    def get_annotations(self) -> List[NodeAnnotation]:
        """Get list of current node annotations.

        Returns:
            List of NodeAnnotation objects.
        """
        return list(self._settings._node_annotations)

    def get_collapses(self) -> List[CladeCollapse]:
        """Get list of current clade collapses.

        Returns:
            List of CladeCollapse objects.
        """
        return list(self._settings._collapses)

    # ------------------------------------------------------------------
    # Nexus parsing (delegates to _parser)
    # ------------------------------------------------------------------

    def _parse_nexus_content(self, content: str) -> None:
        parsed = parse_nexus_content(content, self._tree_index)
        self._taxa_block = parsed['taxa_block']
        self._tree_block = parsed['tree_block']
        self._translate_block = parsed['translate_block']
        self._tree_content = parsed['tree_content']
        self._all_trees = parsed['all_trees']
        if parsed['figtree_block']:
            load_existing_figtree_block(self._settings, parsed['figtree_block'])

    # ------------------------------------------------------------------
    # Tree parsing engine (Bio.Phylo)
    # ------------------------------------------------------------------

    def _parse_tree_with_biopython(self, tree_string: str) -> Optional[Any]:
        try:
            from Bio import Phylo
            import io as _io

            # Biopython >= 1.80 captures bracket comments into ``Clade.comment``
            # and writes them back on serialization, so comments are NO LONGER
            # stripped before parsing: node-level metadata (BEAST 95% HPD
            # ranges, posterior probabilities, NHX tags) now survives the
            # round-trip through the tree object itself, at every attachment
            # position Bio.Phylo supports.
            trees = list(Phylo.parse(_io.StringIO(tree_string), 'newick'))
            if not trees:
                return None

            tree = trees[0]
            negative_branches: List[str] = []
            for clade in tree.find_clades():
                if clade.branch_length is not None and clade.branch_length < 0:
                    node_name = clade.name or '<internal>'
                    negative_branches.append(f"{node_name} ({clade.branch_length})")
                    if self._strict:
                        raise ValidationError(
                            f"Strict mode: negative branch length ({clade.branch_length}) "
                            f"found for node '{node_name}'"
                        )
            if negative_branches and not self._strict:
                warnings.warn(
                    f"Negative branch length(s) found: {', '.join(negative_branches[:5])}"
                    + (f" and {len(negative_branches) - 5} more" if len(negative_branches) > 5 else "")
                    + ". FigTree may render this incorrectly.",
                    CompatibilityWarning,
                )
            return tree
        except (ValidationError, ExportError):
            raise
        except Exception as e:
            warnings.warn(
                f"Bio.Phylo tree parsing failed ({type(e).__name__}): {e}"
            )
            return None

    def _find_mrca_clade(self, tree: Any, taxon_names: List[str]) -> Optional[Any]:
        try:
            # Bio.Phylo.common_ancestor iterates over its argument; a bare
            # string is treated as a sequence of characters.  Always pass a
            # list to avoid this.
            names = list(taxon_names)
            # Filter out taxa not in the tree (e.g. removed by collapse)
            tips = {t.name for t in tree.get_terminals()}
            names = [n for n in names if n in tips]
            if not names:
                # None of the requested taxa are present in the tree.  For a
                # direct user request this is a genuine error and must be
                # surfaced; for internal/derived calls (e.g. a taxon already
                # removed by a prior collapse) it is benign.  Either way we
                # emit a (narrowed) warning rather than raising, so that a
                # subsequently-unresolved annotation is reported instead of
                # silently dropped (fix #29).
                warnings.warn(
                    f"MRCA search failed for taxa {taxon_names}: no matching taxa "
                    f"found in tree"
                )
                return None
            if len(names) == 1:
                # Single taxon — return the terminal node directly
                for t in tree.get_terminals():
                    if t.name == names[0]:
                        return t
                return None
            # Bio.Phylo raises ValueError when a target is missing; that is
            # caught below.  After pre-filtering against the tip set, a None
            # return is unreachable but kept defensive-free: any failure
            # surfaces through the except clause.
            return tree.common_ancestor(names)
        except (ValueError, AttributeError, KeyError) as e:
            warnings.warn(f"MRCA search failed for taxa {taxon_names}: {e}")
            return None

    @staticmethod
    def _find_mrca_of_nodes(tree: Any, nodes: List[Any]) -> Optional[Any]:
        """Find the MRCA of a set of clade *node objects* (not names).

        Uses ``tree.get_path`` (Bio.Phylo) to build ancestor chains for each
        node, then returns the deepest common ancestor.  Used for nested
        collapse resolution where ``common_ancestor`` cannot find internal
        node names.
        """
        if not nodes:
            return None
        if len(nodes) == 1:
            return nodes[0]

        # Build ancestor chains using get_path (root→node, inclusive)
        chains = []
        for n in nodes:
            try:
                path = tree.get_path(n)
                # get_path returns list of ancestors from root to parent;
                # include the node itself
                chain = list(path) + [n]
            except (ValueError, AttributeError):
                # Fallback: just use the node itself
                chain = [n]
            chains.append(set(id(c) for c in chain))

        common_ids = chains[0]
        for chain in chains[1:]:
            common_ids &= chain

        if not common_ids:
            return None

        # Return the deepest common ancestor (most descendant)
        best = None
        best_depth = -1
        for clade in tree.find_clades():
            if id(clade) in common_ids:
                depth = len(tree.get_path(clade) or [])
                if depth > best_depth:
                    best_depth = depth
                    best = clade
        return best

    def _calculate_node_height(self, tree, node) -> float:
        # Memoize per (tree, node) so repeated height queries across many
        # hilight/collapse annotations don't re-run the full DFS (fix #26).
        cache = self.__dict__.setdefault('_node_height_cache', {})
        key = (id(tree), id(node))
        if key in cache:
            return cache[key]
        try:
            root = tree.root
            # Iterative DFS to find the target node and accumulate height
            # Stack entries: (node, height_from_root)
            stack = [(root, 0.0)]
            while stack:
                current, height = stack.pop()
                if current is node:
                    result = round(height, 10)
                    cache[key] = result
                    return result
                if hasattr(current, 'clades'):
                    for child in current.clades:
                        child_height = height + (child.branch_length or 0.0)
                        stack.append((child, child_height))
            warnings.warn(
                f"Could not find path from root to node "
                f"'{getattr(node, 'name', None) or '<internal>'}'; "
                f"height defaults to 0.0",
                CompatibilityWarning,
            )
            result = 0.0
        except (ValueError, AttributeError) as e:
            warnings.warn(
                f"Failed to calculate node height: {e}",
                CompatibilityWarning,
            )
            result = 0.0
        cache[key] = result
        return result

    def _get_min_tip_height(self, tree, node) -> float:
        """Calculate jebl's ``RootedTreeUtils.getMinTipHeight(tree, node)``.

        jebl uses **time-backward** node heights: ``getHeight(tip) =
        maxHeight - depth(tip)``, where ``depth`` is the root-to-tip
        cumulative branch length and ``maxHeight`` is the maximum depth over
        all tips in the **entire** tree.

        ``getMinTipHeight`` returns the minimum ``getHeight(tip)`` over all
        tips in *node*'s subtree, which equals::

            maxHeight - max(depth(tip) for tip in node's subtree)
            = maxHeight - (depth(node) + maxDistToFarthestTipInSubtree)

        FigTree's ``constructCollapsedNode`` computes::

            maxXPos = xPosition + height - tipHeight

        where ``height = getHeight(node) = maxHeight - depth(node)`` and
        ``xPosition = rootLength + depth(node)``.  Substituting the correct
        ``tipHeight`` yields ``maxXPos = rootLength + maxTipDepthInSubtree``,
        i.e. the triangle base sits at the farthest tip's absolute x position,
        making the triangle point **right** (toward the tips).
        """
        # 1. depth(node) = root-to-node cumulative branch length
        node_depth = self._calculate_node_height(tree, node)

        # 2. max tip depth within node's subtree = depth(node) + maxDist
        max_dist_in_subtree = 0.0
        stack = [(node, 0.0)]
        while stack:
            current, dist = stack.pop()
            is_terminal = (
                not hasattr(current, 'clades') or
                not current.clades
            )
            if is_terminal:
                if dist > max_dist_in_subtree:
                    max_dist_in_subtree = dist
            else:
                for child in current.clades:
                    stack.append((child, dist + (child.branch_length or 0.0)))
        max_tip_depth_in_subtree = node_depth + max_dist_in_subtree

        # 3. maxHeight = max tip depth in the entire tree (cache once per tree,
        # since it is identical for every hilight/collapse annotation, fix #26).
        hcache = self.__dict__.setdefault('_height_cache', {})
        tree_id = id(tree)
        if tree_id not in hcache:
            max_height = 0.0
            stack = [(tree.root, 0.0)]
            while stack:
                current, depth = stack.pop()
                is_terminal = (
                    not hasattr(current, 'clades') or
                    not current.clades
                )
                if is_terminal:
                    if depth > max_height:
                        max_height = depth
                else:
                    for child in current.clades:
                        stack.append((child, depth + (child.branch_length or 0.0)))
            hcache[tree_id] = max_height
        max_height = hcache[tree_id]

        # 4. getMinTipHeight = maxHeight - maxTipDepthInSubtree
        result = max_height - max_tip_depth_in_subtree
        return round(max(0.0, result), 10)

    def _inject_annotation_to_node(self, node, annotation_type: str, values: Any,
                                     extra_params: Optional[Dict[str, Any]] = None):
        if node is None:
            return

        tag = f"!{annotation_type.replace('!', '')}"

        if annotation_type == 'color':
            color_value = values.lower() if isinstance(values, str) else values
            annotation_str = f"&{tag}={color_value}"
        elif annotation_type == 'hilight':
            if isinstance(values, (list, tuple)) and len(values) >= 3:
                color = values[2].lower() if isinstance(values[2], str) else values[2]
                # FigTree only supports 3-element format: {tipCount,tipHeight,color}
                # Extra parameters (width, offset) cause ClassCastException
                annotation_str = f"&{tag}={{{values[0]},{values[1]},{color}}}"
            else:
                warnings.warn(f"Invalid hilight values: {values}")
                return
        elif annotation_type == 'font':
            if isinstance(values, str) and ',' in values:
                parts = values.split(',')
                try:
                    name, style_int, size = parts[0], int(parts[1]), parts[2]
                except (ValueError, IndexError):
                    warnings.warn(f"Invalid font annotation format: {values!r}")
                    return
                style_str = _FONT_STYLE_MAP.get(style_int, "PLAIN")
                annotation_str = f"&{tag}={name}-{style_str}-{size}"
            else:
                annotation_str = f"&{tag}={values}"
        elif annotation_type == 'stroke':
            try:
                numeric = float(values)
                stroke_value = int(numeric) if numeric.is_integer() else numeric
            except (TypeError, ValueError):
                warnings.warn(f"Invalid stroke value: {values!r} (expected numeric)")
                return
            annotation_str = f"&{tag}={stroke_value}"
        else:
            annotation_str = f"&{tag}={serialize_value(values)}"

        if node.comment is None:
            node.comment = annotation_str
        else:
            tag_present = f"{tag}=" in node.comment
            if annotation_type == 'hilight' or not tag_present:
                # Standard jebl meta-comment format: [&k1=v1,k2=v2]
                # The & prefix only appears once at the start; subsequent
                # annotations are separated by commas without & prefix.
                node.comment += f",{annotation_str.lstrip('&')}"
            else:
                # Same annotation type already present: override its value
                # rather than silently dropping the new value (fix #28).
                node.comment = re.sub(
                    rf'{re.escape(tag)}=[^,&]*',
                    annotation_str.lstrip('&'),
                    node.comment,
                    count=1,
                )

    def _apply_single_annotation(self, tree, annotation) -> bool:
        """Apply one annotation to its target MRCA node.

        Shared by :meth:`_apply_annotations_to_tree` and the inline
        annotation loop in :meth:`_resolve_annotations_copy` so that the
        generic (non-``color``/``color_all``/``hilight``) injection logic
        is implemented exactly once.

        Args:
            tree: Bio.Phylo tree.
            annotation: A :class:`~figtreekit.annotations.NodeAnnotation`.

        Returns:
            ``True`` if the annotation was applied, ``False`` if its target
            taxa could not be resolved.
        """
        if not annotation.target_taxa:
            return False
        target_node = self._find_mrca_clade(tree, annotation.target_taxa)
        if target_node is None:
            return False
        self._inject_annotation_to_node(
            target_node, annotation.annotation_type, annotation.values,
            extra_params=annotation.extra_params
        )
        return True

    def _apply_annotations_to_tree(self, tree, annotations=None):
        if annotations is None:
            annotations = self._settings._node_annotations
        if not annotations:
            return tree
        for annotation in annotations:
            if not self._apply_single_annotation(tree, annotation):
                warnings.warn(f"Could not find target node for annotation: {annotation}")
        return tree

    def _count_unresolved_annotations(self, tree, annotations) -> List[str]:
        """Return descriptions of annotations whose target taxa could not be resolved."""
        unresolved: List[str] = []
        for annotation in annotations:
            if not annotation.target_taxa:
                continue
            node = self._find_mrca_clade(tree, annotation.target_taxa)
            if node is None:
                unresolved.append(
                    f"{annotation.annotation_type} for taxa {annotation.target_taxa}"
                )
        return unresolved

    def _serialize_tree_to_newick(self, tree) -> Optional[str]:
        try:
            from Bio import Phylo
            import io as _io
            has_translate = bool(self._translate_block)
            for clade in tree.find_clades():
                if clade.name:
                    # Strip leading bootstrap prefix (e.g. "100.0:" or "'99.0:")
                    m = re.match(r"^'?\d+\.?\d*:(.+?)'?$", clade.name)
                    if m:
                        clade.name = m.group(1)
                    # Replace semicolons inside node names to prevent Nexus
                    # parser confusion (e.g. GTDB "c__X; o__Y" → "c__X, o__Y")
                    if clade.name and ';' in clade.name:
                        clade.name = clade.name.replace(';', ',')
                # NOTE: Numeric node names are intentionally PRESERVED here.
                # In BEAST trees and trees without a `translate` block, purely
                # numeric leaf names (e.g. "1", "123") are real taxon labels and
                # must survive the round-trip. Internal-node bootstrap values
                # are stored by Bio.Phylo in `clade.confidence` (not
                # `clade.name`); they are cleared by the block below, so we
                # must not strip numeric `clade.name` values.
                # Clear confidence values — Bio.Phylo writes them as bare
                # numbers in the Newick (e.g. ")100.00:length") which causes
                # FigTree ClassCastException on GTDB-scale trees.
                if clade.confidence is not None:
                    clade.confidence = None
            output = _io.StringIO()
            Phylo.write(tree, output, 'newick')
            return output.getvalue().strip()
        except (ValueError, AttributeError, TypeError, OSError) as e:
            warnings.warn(f"Tree serialization failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Annotation API
    # ------------------------------------------------------------------

    def highlight_clade(self, taxon_names: List[str], color: str = "#804548",
                        width: int = 4, offset: float = 0.0) -> "FigTreeStyler":
        """Highlight a clade defined by its constituent taxa.

        Finds the MRCA of the specified taxa and applies a colored background
        highlight corresponding to ``[&!hilight={tipCount,height,color}]``.

        Args:
            taxon_names: Taxa that define the clade (case-sensitive).
            color: Hex RGB color (``"#RRGGBB"``). Default ``"#804548"``.
            width: Highlight border width. Default ``4``.
            offset: Vertical offset. Default ``0.0``.

        Returns:
            self for method chaining.

        Raises:
            ValidationError: If color or taxon names are invalid.
        """
        if not TreeValidator.validate_color(color):
            raise ValidationError(f"Invalid hex color: {color}")
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")

        annotation = NodeAnnotation(
            annotation_type='hilight',
            values=[0, 0.0, color],
            target_taxa=taxon_names,
            extra_params={'width': width, 'offset': offset},
        )
        self._settings._node_annotations.append(annotation)
        self._settings.hilighting['isShown'] = True
        return self

    def set_clade_color(self, taxon_names: List[str], color: str) -> "FigTreeStyler":
        """Set branch color for a clade.

        Args:
            taxon_names: Taxa defining the clade.
            color: Hex RGB color.

        Returns:
            self for method chaining.
        """
        if not TreeValidator.validate_color(color):
            raise ValidationError(f"Invalid hex color: {color}")
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")

        self._settings._node_annotations.append(
            NodeAnnotation(annotation_type='color', values=color, target_taxa=taxon_names)
        )
        return self

    def set_clade_color_all(self, taxon_names: List[str], color: str) -> "FigTreeStyler":
        """Set branch color for ALL branches in a clade (MRCA + all descendants).

        Unlike :meth:`set_clade_color` which only colors the MRCA branch,
        this method colors every branch in the clade, producing a fully
        colored subtree.

        Args:
            taxon_names: Taxa defining the clade.
            color: Hex RGB color.

        Returns:
            self for method chaining.
        """
        if not TreeValidator.validate_color(color):
            raise ValidationError(f"Invalid hex color: {color}")
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")

        self._settings._node_annotations.append(
            NodeAnnotation(annotation_type='color_all', values=color, target_taxa=taxon_names)
        )
        return self

    def set_clade_font(self, taxon_names: List[str], font_name: str = "Arial",
                       font_style: Union[int, FontStyle] = FontStyle.PLAIN,
                       font_size: int = 12) -> "FigTreeStyler":
        """Set font for a clade's labels.

        The annotation is serialized as ``[&!font=Name-STYLE-size]`` compatible
        with Java ``Font.decode()``.

        Args:
            taxon_names: Taxa defining the clade.
            font_name: Font family name (e.g., ``"Arial"``). Defaults to ``"Arial"``.
            font_style: Style code as ``FontStyle`` enum or int
                (0=PLAIN, 1=BOLD, 2=ITALIC, 3=BOLDITALIC). Defaults to ``FontStyle.PLAIN``.
            font_size: Font size in points. Defaults to ``12``.

        Returns:
            self for method chaining.
        """
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")
        if isinstance(font_style, FontStyle):
            font_style = font_style.value
        if not TreeValidator.validate_font_style(font_style):
            raise ValidationError(f"Invalid font style: {font_style} (must be 0-3)")
        if not isinstance(font_size, int) or font_size <= 0:
            raise ValidationError(f"Invalid font size: {font_size} (must be positive integer)")
        # A comma in the font name would corrupt the comma-separated
        # "!font=Name-STYLE-size" annotation (fix #33).
        if ',' in font_name:
            raise ValidationError(
                f"Invalid font name: '{font_name}' must not contain a comma"
            )

        self._settings._node_annotations.append(
            NodeAnnotation(
                annotation_type='font',
                values=f"{font_name},{font_style},{font_size}",
                target_taxa=taxon_names,
            )
        )
        return self

    def set_clade_stroke(self, taxon_names: List[str], stroke_width: float) -> "FigTreeStyler":
        """Set branch stroke width annotation for a clade.

        .. warning::
            FigTree 1.4.4's ``getStrokeAttribute()`` is a stub that always
            returns ``None``. The ``[&!stroke=...]`` annotation is written but
            **silently ignored** by FigTree 1.4.4. Provided for forward
            compatibility; every call therefore emits an explicit
            :class:`CompatibilityWarning` so users are never misled into
            expecting a visible effect in FigTree 1.4.4.
        """
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")

        warnings.warn(
            "!stroke is accepted but silently ignored by FigTree 1.4.4 "
            "(getStrokeAttribute() is an empty implementation). The "
            "annotation is written for forward compatibility only and will "
            "have no visible effect; use branch_line_width for global "
            "branch thickness instead.",
            CompatibilityWarning,
        )
        self._settings._node_annotations.append(
            NodeAnnotation(annotation_type='stroke', values=stroke_width, target_taxa=taxon_names)
        )
        return self

    def set_clade_hilight(self, clade_identifier: str, tip_count: int,
                          height: float, color: str) -> "FigTreeStyler":
        """Set hilight annotation with explicit parameters.

        Args:
            clade_identifier: Clade identifier (e.g., ``"MRCA(A,B,C)"``).
            tip_count: Number of tips in the clade.
            height: Node height (minimum tip height).
            color: Hex color.

        Returns:
            self for method chaining.
        """
        if not TreeValidator.validate_color(color):
            raise ValidationError(f"Invalid hex color: {color}")

        target_taxa = None
        mrca_match = re.match(r'MRCA\(([^)]+)\)', clade_identifier, re.IGNORECASE)
        if mrca_match:
            target_taxa = [t.strip() for t in mrca_match.group(1).split(',')]
        else:
            warnings.warn(
                f"clade_identifier '{clade_identifier}' does not match MRCA(taxa,...) pattern; "
                f"annotation will not be resolved to any node",
                CompatibilityWarning,
            )

        self._settings._node_annotations.append(
            NodeAnnotation(
                annotation_type='hilight',
                values=[tip_count, height, color],
                target_taxa=target_taxa,
                extra_params={},
            )
        )
        self._settings.hilighting['isShown'] = True
        return self

    def clear_annotations(self) -> "FigTreeStyler":
        """Clear all node annotations."""
        self._settings._node_annotations.clear()
        return self

    def clear_clade_hilights(self) -> "FigTreeStyler":
        """Clear only hilight annotations, preserving color/font annotations."""
        self._settings._node_annotations = [
            a for a in self._settings._node_annotations if a.annotation_type != 'hilight'
        ]
        return self

    def check_monophyly(self, taxon_names: List[str]) -> dict:
        """Check if the given taxa form a monophyletic group.

        A group is monophyletic if the MRCA (Most Recent Common Ancestor)
        of the taxa contains only the specified taxa as terminals.

        Args:
            taxon_names: List of taxon names to check.

        Returns:
            Dictionary with keys:
                - ``is_monophyletic`` (bool): Whether the taxa form a monophyletic group.
                - ``mrca_found`` (bool): Whether MRCA was found.
                - ``mrca_terminals`` (list): Terminals under the MRCA.
                - ``missing_taxa`` (list): Taxa under MRCA not in the input list.
                - ``extra_taxa`` (list): Taxa in input list not under MRCA.

        Example:
            .. code-block:: python

                styler = FigTreeStyler("tree.nwk")
                result = styler.check_monophyly(["A", "B", "C"])

                if result["is_monophyletic"]:
                    print("Taxa form a monophyletic group!")
                else:
                    print(f"Not monophyletic. Missing: {result['missing_taxa']}")
        """
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")

        # Parse tree to check monophyly
        tree = self._parse_tree_with_biopython(self._tree_content)
        if tree is None:
            return {
                "is_monophyletic": False,
                "mrca_found": False,
                "mrca_terminals": [],
                "missing_taxa": [],
                "extra_taxa": taxon_names,
            }

        # Find MRCA
        mrca = self._find_mrca_clade(tree, taxon_names)
        if mrca is None:
            return {
                "is_monophyletic": False,
                "mrca_found": False,
                "mrca_terminals": [],
                "missing_taxa": [],
                "extra_taxa": taxon_names,
            }

        # Get MRCA terminals
        mrca_terminal_names = [t.name for t in mrca.get_terminals()]
        target_set = set(taxon_names)
        mrca_set = set(mrca_terminal_names)

        # Check if monophyletic: MRCA terminals must exactly match target taxa
        is_monophyletic = (mrca_set == target_set)
        missing = list(mrca_set - target_set)
        extra = list(target_set - mrca_set)

        return {
            "is_monophyletic": is_monophyletic,
            "mrca_found": True,
            "mrca_terminals": mrca_terminal_names,
            "missing_taxa": missing,
            "extra_taxa": extra,
        }

    def check_monophyly_by_group(
        self,
        group_name: str,
        pattern: Optional[str] = None,
        mapping_file: Optional[str] = None,
    ) -> dict:
        """Check monophyly of a taxon group identified by name.

        Resolves *group_name* to terminal taxa using taxonomy information
        (parsed from labels via *pattern* or loaded from *mapping_file*),
        then checks whether those taxa form a monophyletic group.

        Supports special identifiers:
          - ``LUCA``: all Bacteria + Archaea taxa
          - ``LACA``: all Archaea taxa
          - ``LBCA``: all Bacteria taxa

        Args:
            group_name: Taxon group name (e.g. ``"Bacteria"``,
                ``"Cyanobacteriales"``) or special identifier.
            pattern: Regex pattern for parsing taxonomy from labels,
                or built-in pattern name (e.g. ``"full_taxonomy"``).
            mapping_file: Path to CSV/TSV file with taxonomy mapping.

        Returns:
            Dictionary with:
                - ``group_name`` (str): The requested group name.
                - ``resolved_taxa`` (list): Taxa belonging to the group.
                - ``is_monophyletic`` (bool): Whether the group is monophyletic.
                - ``mrca_found`` (bool): Whether MRCA was found.
                - ``mrca_terminals`` (list): All terminals under the MRCA.
                - ``missing_taxa`` (list): Extra taxa under MRCA.
                - ``warning`` (str or None): Warning if not monophyletic.

        Raises:
            ValidationError: If group_name cannot be resolved.
            ExportError: If tree cannot be parsed.

        Example:
            .. code-block:: python

                styler = FigTreeStyler("tree.nwk")

                # Using full_taxonomy pattern for _d_/_p_/... format
                result = styler.check_monophyly_by_group(
                    "Cyanobacteriales",
                    pattern="full_taxonomy",
                )

                # Special identifiers
                result = styler.check_monophyly_by_group("LUCA", pattern="full_taxonomy")

                if result["is_monophyletic"]:
                    print(f"Monophyletic! MRCA terminals: {result['mrca_terminals']}")
                else:
                    print(f"WARNING: {result['warning']}")
        """
        from .taxonomy import TaxonomyMapper, MonophylyAnalyzer

        tree = self._parse_tree_with_biopython(self._tree_content)
        if tree is None:
            raise ExportError("Failed to parse tree for monophyly check")

        map_file = mapping_file or self._taxonomy_mapping_file
        mapper = TaxonomyMapper(
            pattern=pattern, delimiter=self._table_sep,
            priority=self._taxonomy_source_priority,
        )
        if map_file:
            mapper.load_mapping(
                map_file,
                delimiter=self._table_sep,
                taxonomy_sep=self._taxonomy_table_sep,
                ignore_malformed=self._ignore_malformed,
            )

        labels = [t.name for t in tree.get_terminals() if t.name]

        # Parse labels with configured mode
        from .taxonomy import parse_taxonomy_auto
        if pattern:
            mapper.parse_labels(
                labels,
                mode=self._taxonomy_delimiter_mode,
                sep=self._taxonomy_table_sep,
            )
        else:
            for label in labels:
                tax = parse_taxonomy_auto(
                    label,
                    mode=self._taxonomy_delimiter_mode,
                    sep=self._taxonomy_table_sep,
                )
                if tax:
                    mapper._label_taxonomy[label] = tax

        # Validate mapping against tree if mapping file was provided
        if mapper._mapping:
            consistency = mapper.validate_mapping_against_tree(labels)
            for w in consistency.get("warnings", []):
                warnings.warn(w, CompatibilityWarning)

        analyzer = MonophylyAnalyzer(mapper)
        return analyzer.check_monophyly_by_group(tree, group_name, labels)

    # ------------------------------------------------------------------
    # Taxonomy configuration
    # ------------------------------------------------------------------

    def configure_taxonomy(
        self,
        *,
        delimiter_mode: Optional[str] = None,
        table_sep: Optional[str] = None,
        source_priority: Optional[str] = None,
        mapping_file: Optional[str] = None,
        ignore_malformed: Optional[bool] = None,
        file_delimiter: Optional[str] = None,
    ) -> "FigTreeStyler":
        """Configure taxonomy parsing behavior.

        Args:
            delimiter_mode: Embedded taxonomy parsing strategy
                (``"reverse"``, ``"greedy"``, ``"segment"``).
            table_sep: Separator for format B taxonomy strings.
            source_priority: ``"embedded"`` or ``"table"``.
            mapping_file: Path to taxonomy mapping file.
            ignore_malformed: Skip malformed taxonomy rows.
            file_delimiter: Column delimiter for mapping file.

        Returns:
            self for method chaining.
        """
        if delimiter_mode is not None:
            self._taxonomy_delimiter_mode = delimiter_mode
        if table_sep is not None:
            self._taxonomy_table_sep = table_sep
        if source_priority is not None:
            self._taxonomy_source_priority = source_priority
        if mapping_file is not None:
            self._taxonomy_mapping_file = mapping_file
        if ignore_malformed is not None:
            self._ignore_malformed = ignore_malformed
        if file_delimiter is not None:
            self._table_sep = file_delimiter
        return self

    # ------------------------------------------------------------------
    # Clade collapse API
    # ------------------------------------------------------------------

    def collapse_clade(
        self,
        taxon_names: List[str],
        label: Optional[str] = None,
        collapse_type: str = "collapse",
    ) -> "FigTreeStyler":
        """Collapse a clade defined by its constituent taxa.

        The clade is collapsed during export: the MRCA subtree is replaced
        by a single terminal node with the given *label*.

        Args:
            taxon_names: Taxa that define the clade (case-sensitive).
            label: Display label for the collapsed node.  If ``None``,
                a default label is generated (e.g. ``"{3 taxa}"``).
            collapse_type: ``"collapse"`` (default) draws a triangle whose
                tip carries *label* (``!collapse`` annotation);
                ``"cartoon"`` draws a triangle spanning the original tip
                range with tip count (``!cartoon`` annotation).

        Returns:
            self for method chaining.

        Raises:
            ValidationError: If taxon names are invalid.
        """
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")

        if collapse_type not in ("collapse", "cartoon"):
            raise ValidationError(
                f"Invalid collapse_type: {collapse_type!r} "
                f"(expected 'collapse' or 'cartoon')"
            )

        if label is None:
            label = f"{{{len(taxon_names)} taxa}}"

        # P0 #21: validate that the requested taxa form a monophyletic clade,
        # consistent with collapse_by_group.  Collapsing a non-monophyletic
        # set would produce a triangle that silently swallows the extra tips,
        # so we refuse (warn + skip) and report the actual terminal count.
        # If the tree is unavailable or the MRCA cannot be resolved we fall
        # back to the legacy behaviour and still register the collapse.
        if self._tree_content:
            tree = self._parse_tree_with_biopython(self._tree_content)
            if tree is not None:
                tips = {t.name for t in tree.get_terminals()}
                present = [n for n in taxon_names if n in tips]
                if present:
                    mrca = self._find_mrca_clade(tree, present)
                    if mrca is not None:
                        mrca_terminals = [t.name for t in mrca.get_terminals()]
                        if set(mrca_terminals) != set(present):
                            extra = sorted(set(mrca_terminals) - set(present))
                            extra_str = (
                                f" (extra tips: {extra[:5]}"
                                f"{'...' if len(extra) > 5 else ''})"
                                if extra else ""
                            )
                            warnings.warn(
                                f"collapse_clade: taxa {list(taxon_names)} are not "
                                f"monophyletic — the MRCA actually contains "
                                f"{len(mrca_terminals)} tip(s){extra_str}. "
                                f"Collapse skipped to avoid misrepresenting the clade.",
                                CompatibilityWarning,
                            )
                            return self

        self._settings._collapses.append(
            CladeCollapse(
                target_taxa=list(taxon_names),
                label=label,
                collapse_type=collapse_type,
            )
        )
        return self

    def cartoon_clade(
        self,
        taxon_names: List[str],
        label: Optional[str] = None,
    ) -> "FigTreeStyler":
        """Cartoon a clade (FigTree ``!cartoon`` annotation).

        Convenience wrapper around :meth:`collapse_clade` with
        ``collapse_type="cartoon"``.  The clade is drawn as a triangle
        whose width spans the original tip range; FigTree stores
        ``!cartoon={tipCount, height}``.

        Args:
            taxon_names: Taxa that define the clade (case-sensitive).
            label: Display label for the collapsed node.

        Returns:
            self for method chaining.
        """
        return self.collapse_clade(
            taxon_names, label=label, collapse_type="cartoon"
        )

    def collapse_by_group(
        self,
        group_name: str,
        pattern: Optional[str] = None,
        mapping_file: Optional[str] = None,
        label: Optional[str] = None,
        collapse_type: str = "collapse",
    ) -> "FigTreeStyler":
        """Collapse a clade identified by taxonomic group name.

        The group is first resolved to terminal taxa, then checked for
        monophyly.  If the group is **not** monophyletic a
        ``CompatibilityWarning`` is emitted and the collapse is **not**
        performed.

        Supports special identifiers ``LUCA``, ``LACA``, ``LBCA``.

        Args:
            group_name: Taxon group name (e.g. ``"Cyanobacteriales"``)
                or special identifier.
            pattern: Regex pattern for parsing taxonomy from labels,
                or built-in pattern name (e.g. ``"full_taxonomy"``).
            mapping_file: Path to CSV/TSV file with taxonomy mapping.
            label: Display label for the collapsed node.  If ``None``,
                defaults to *group_name*.
            collapse_type: ``"collapse"`` (default) or ``"cartoon"``.

        Returns:
            self for method chaining.

        Raises:
            ValidationError: If group_name cannot be resolved.
            ExportError: If tree cannot be parsed.
        """
        result = self.check_monophyly_by_group(
            group_name, pattern=pattern, mapping_file=mapping_file
        )

        if not result["is_monophyletic"]:
            warning = result.get("warning") or (
                f"'{group_name}' is not a monophyletic group — "
                f"collapse is not allowed."
            )
            warnings.warn(warning, CompatibilityWarning)
            return self

        resolved = result["resolved_taxa"]
        if not resolved:
            warnings.warn(
                f"Group '{group_name}' resolved to zero taxa — nothing to collapse.",
                CompatibilityWarning,
            )
            return self

        if label is None:
            label = group_name

        self._settings._collapses.append(
            CladeCollapse(
                target_taxa=resolved,
                label=label,
                group_name=group_name,
                collapse_type=collapse_type,
            )
        )
        return self

    def clear_collapses(self) -> "FigTreeStyler":
        """Clear all pending collapse operations."""
        self._settings._collapses.clear()
        return self

    def _apply_collapses_to_tree(self, tree: Any) -> Any:
        """Apply all pending collapse operations to a parsed tree.

        For each collapse, finds the MRCA of the target taxa and injects a
        ``!collapse`` annotation onto the MRCA node.  FigTree reads this
        annotation and renders the clade as a triangle, with the collapse
        *label* shown at the triangle's tip.

        Unlike the previous approach (which physically removed child nodes),
        this method **preserves the full tree topology**.  This ensures:
        - FigTree renders proper triangles (not single tips)
        - Subsequent color annotations (Phase 3) can still resolve MRCA
          for all original taxa
        - Nested collapses work correctly

        Collapses are sorted by clade size (smallest first) so that inner
        (descendant) collapses are applied before outer (ancestral) ones.
        """
        sorted_collapses = sorted(
            self._settings._collapses,
            key=lambda c: len(c.target_taxa),
        )

        # Track original taxa → collapsed label for nested resolution
        collapsed_taxa_map: Dict[str, str] = {}
        # Track collapsed label → MRCA node reference for nested resolution
        collapsed_node_map: Dict[str, Any] = {}

        for collapse in sorted_collapses:
            # Resolve taxa through previous collapse mappings
            resolved_taxa = []
            resolved_nodes = []
            is_nested = False
            for t in collapse.target_taxa:
                if t in collapsed_taxa_map:
                    resolved_taxa.append(collapsed_taxa_map[t])
                    resolved_nodes.append(collapsed_node_map[collapsed_taxa_map[t]])
                    is_nested = True
                else:
                    resolved_taxa.append(t)
            # Deduplicate (multiple original taxa may map to same label)
            resolved_taxa = list(dict.fromkeys(resolved_taxa))

            if is_nested:
                # For nested collapses, use node references to find MRCA
                # because internal node names are not visible to
                # Bio.Phylo.common_ancestor.
                mrca = self._find_mrca_of_nodes(tree, resolved_nodes)
                # Also resolve any non-collapsed taxa by name
                non_collapsed = [t for t in collapse.target_taxa if t not in collapsed_taxa_map]
                if non_collapsed:
                    name_mrca = self._find_mrca_clade(tree, non_collapsed)
                    if name_mrca is not None and mrca is not None:
                        # MRCA of all = MRCA of (node_mrca, name_mrca)
                        mrca = self._find_mrca_of_nodes(tree, [mrca, name_mrca])
                    elif name_mrca is not None:
                        mrca = name_mrca
            else:
                mrca = self._find_mrca_clade(tree, resolved_taxa)

            if mrca is None:
                warnings.warn(
                    f"Could not find MRCA for collapse target "
                    f"{collapse.target_taxa} — skipping.",
                    CompatibilityWarning,
                )
                continue

            if not mrca.clades:
                continue

            # Calculate min tip height for the collapse annotation
            min_height = self._get_min_tip_height(tree, mrca)

            # Inject !collapse or !cartoon annotation onto the MRCA node.
            # FigTree expects:
            #   !collapse = {tipName, height}  (string label, double height)
            #   !cartoon  = {tipCount, height} (int count,   double height)
            ctype = collapse.collapse_type
            if ctype == "cartoon":
                tip_count = len(mrca.get_terminals())
                annot_name = "!cartoon"
                annot_str = f'&!cartoon={{{tip_count},{min_height}}}'
            else:
                annot_name = "!collapse"
                annot_str = f'&!collapse={{{collapse.label},{min_height}}}'

            if mrca.comment is None:
                mrca.comment = annot_str
            elif f'{annot_name}=' not in mrca.comment:
                # Standard jebl format: & only at start, subsequent
                # annotations separated by commas without & prefix.
                mrca.comment += f',{annot_str.lstrip("&")}'
            else:
                # Update existing annotation of the same type.
                # Pattern matches the tag without & prefix so it works
                # for both first and subsequent annotations.
                mrca.comment = re.sub(
                    rf'{annot_name}=\{{[^}}]+\}}',
                    annot_str.lstrip('&'),
                    mrca.comment
                )

            # Set MRCA name to collapse label for FigTree node label display
            mrca.name = collapse.label

            # Record which original taxa are now consumed by this collapse
            collapsed_node_map[collapse.label] = mrca
            for t in collapse.target_taxa:
                collapsed_taxa_map[t] = collapse.label

        return tree

    def style_monophyletic_clade(
        self,
        taxon_names: List[str],
        color: str = "#E91E63",
        highlight_color: Optional[str] = None,
        font_name: Optional[str] = None,
        font_style: Optional[Union[int, FontStyle]] = None,
        font_size: Optional[int] = None,
        warn_if_not_monophyletic: bool = True,
    ) -> "FigTreeStyler":
        """Check monophyly and apply styles to a clade.

        This method checks if the given taxa form a monophyletic group,
        then applies color and highlight styles accordingly.

        Args:
            taxon_names: List of taxon names defining the clade.
            color: Hex RGB color for branches (default: ``"#E91E63"``).
            highlight_color: Hex RGB color for background highlight.
                If ``None``, no highlight is applied.
            font_name: Font family name (e.g., ``"Arial"``).
            font_style: Font style (``FontStyle`` enum or int).
            font_size: Font size in points.
            warn_if_not_monophyletic: If ``True`` (default), emit a
                ``CompatibilityWarning`` when taxa are not monophyletic.

        Returns:
            self for method chaining.

        Raises:
            ValidationError: If color or taxon names are invalid.

        Example:
            .. code-block:: python

                styler = FigTreeStyler("tree.nwk")

                # Check and style a monophyletic clade
                styler.style_monophyletic_clade(
                    ["T001", "T002", "T003"],
                    color="#E91E63",
                    highlight_color="#FFCDD2",
                    font_name="Arial",
                    font_style=FontStyle.BOLD,
                    font_size=12,
                )
        """
        if not TreeValidator.validate_color(color):
            raise ValidationError(f"Invalid hex color: {color}")
        if highlight_color and not TreeValidator.validate_color(highlight_color):
            raise ValidationError(f"Invalid highlight color: {highlight_color}")
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")

        # Check monophyly
        result = self.check_monophyly(taxon_names)

        if not result["is_monophyletic"] and warn_if_not_monophyletic:
            if result["mrca_found"]:
                warnings.warn(
                    f"Taxa {taxon_names} are not monophyletic. "
                    f"MRCA also contains: {result['missing_taxa']}. "
                    f"Styles will be applied to the entire MRCA clade.",
                    CompatibilityWarning,
                )
            else:
                warnings.warn(
                    f"Could not find MRCA for taxa {taxon_names}. "
                    f"No styles will be applied.",
                    CompatibilityWarning,
                )

        # Apply color to branches
        self.set_clade_color(taxon_names, color)

        # Apply highlight if specified
        if highlight_color:
            self.highlight_clade(taxon_names, highlight_color)

        # Apply font if specified
        if font_name and font_style is not None and font_size is not None:
            self.set_clade_font(taxon_names, font_name, font_style, font_size)

        return self

    def get_clade_info(self, taxon_names: List[str]) -> dict:
        """Get information about a clade defined by the given taxa.

        Args:
            taxon_names: List of taxon names defining the clade.

        Returns:
            Dictionary with keys:
                - ``taxa_count`` (int): Number of input taxa.
                - ``mrca_found`` (bool): Whether MRCA was found.
                - ``mrca_terminals`` (list): All terminals under MRCA.
                - ``mrca_terminal_count`` (int): Number of terminals under MRCA.
                - ``is_monophyletic`` (bool): Whether taxa form a monophyletic group.
                - ``clade_size`` (int): Total number of nodes in clade.

        Example:
            .. code-block:: python

                styler = FigTreeStyler("tree.nwk")
                info = styler.get_clade_info(["A", "B", "C"])
                print(f"Clade has {info['mrca_terminal_count']} terminals")
        """
        if not TreeValidator.validate_taxon_names(taxon_names):
            raise ValidationError(f"Invalid taxon names: {taxon_names}")

        tree = self._parse_tree_with_biopython(self._tree_content)
        if tree is None:
            return {
                "taxa_count": len(taxon_names),
                "mrca_found": False,
                "mrca_terminals": [],
                "mrca_terminal_count": 0,
                "is_monophyletic": False,
                "clade_size": 0,
            }

        mrca = self._find_mrca_clade(tree, taxon_names)
        if mrca is None:
            return {
                "taxa_count": len(taxon_names),
                "mrca_found": False,
                "mrca_terminals": [],
                "mrca_terminal_count": 0,
                "is_monophyletic": False,
                "clade_size": 0,
            }

        mrca_terminals = [t.name for t in mrca.get_terminals()]
        is_monophyletic = set(mrca_terminals) == set(taxon_names)

        # Count nodes in clade
        clade_size = sum(1 for _ in mrca.find_clades())

        return {
            "taxa_count": len(taxon_names),
            "mrca_found": True,
            "mrca_terminals": mrca_terminals,
            "mrca_terminal_count": len(mrca_terminals),
            "is_monophyletic": is_monophyletic,
            "clade_size": clade_size,
        }

    # ------------------------------------------------------------------
    # Taxonomy Analysis API
    # ------------------------------------------------------------------

    def analyze_taxonomy(
        self,
        pattern: Optional[str] = None,
        mapping_file: Optional[str] = None,
        rank: str = "genus",
        style_monophyletic: bool = True,
        color: str = "#E91E63",
        highlight_color: Optional[str] = None,
    ) -> dict:
        """Analyze taxonomy and identify monophyletic groups.

        This method analyzes the tree to identify taxonomic groups and
        determine their monophyly status. It can automatically style
        monophyletic groups.

        Args:
            pattern: Regex pattern for parsing taxonomy from labels.
                Built-in patterns: "beast", "genus_species", "underscore_taxonomy".
                Or provide custom regex with named groups.
            mapping_file: Path to CSV/TSV file with taxonomy mapping.
                First column: taxon name, other columns: taxonomic ranks.
            rank: Taxonomic rank to analyze (e.g., "genus", "family").
            style_monophyletic: If True, automatically style monophyletic groups.
            color: Base color for branches.
            highlight_color: Color for background highlight. None (default)
                to skip — most callers want branch colors, not background
                highlights. Pass a hex color (e.g. ``"#FFCDD2"``) to also
                add a ``!hilight`` annotation to each monophyletic clade.

        Returns:
            Dictionary with analysis results (see MonophylyAnalyzer.analyze_tree).

        Example:
            .. code-block:: python

                # Using built-in pattern
                styler = FigTreeStyler("tree.nwk")
                result = styler.analyze_taxonomy(pattern="genus_species", rank="genus")

                # Using mapping file
                result = styler.analyze_taxonomy(mapping_file="taxonomy.csv", rank="family")

                # With custom pattern
                result = styler.analyze_taxonomy(
                    pattern=r"^(?P<genus>[A-Z][a-z]+)_(?P<species>[a-z]+)",
                    rank="genus"
                )
        """
        # Create mapper
        mapper = TaxonomyMapper(pattern=pattern, mapping_file=mapping_file)

        # Get labels from tree
        tree = self._parse_tree_with_biopython(self._tree_content)
        if tree is None:
            raise ExportError("Failed to parse tree for taxonomy analysis")

        labels = [t.name for t in tree.get_terminals() if t.name]

        # Parse labels if pattern provided
        if pattern:
            mapper.parse_labels(labels)
        else:
            mapper.parse_labels(
                labels,
                mode=self._taxonomy_delimiter_mode,
                sep=self._taxonomy_table_sep,
            )

        # Check completeness
        completeness = mapper.check_completeness(labels)

        if completeness["missing"]:
            warnings.warn(
                f"{len(completeness['missing'])} labels have no taxonomy data. "
                f"Consider providing a mapping file.",
                CompatibilityWarning,
            )

        # Analyze monophyly
        analyzer = MonophylyAnalyzer(mapper)
        result = analyzer.analyze_tree(tree, rank=rank, labels=labels)

        # Style monophyletic groups
        if style_monophyletic and result["monophyletic"]:
            colors = self._generate_group_colors(len(result["monophyletic"]))
            for i, (group_name, group_info) in enumerate(result["monophyletic"].items()):
                if group_info["type"] == "single_taxon":
                    continue

                group_color = colors[i % len(colors)]
                self.set_clade_color(group_info["taxa"], group_color)

                if highlight_color:
                    self.highlight_clade(group_info["taxa"], highlight_color)

        # Add warnings to result
        result["mapper_warnings"] = mapper.get_warnings()
        result["analyzer_warnings"] = analyzer.get_warnings()
        result["completeness"] = completeness

        return result

    def analyze_taxonomy_from_mapping(
        self,
        mapping_file: str,
        rank: str = "genus",
        style_monophyletic: bool = True,
    ) -> dict:
        """Analyze taxonomy using a mapping file.

        This is a convenience method that loads taxonomy from a file
        and analyzes monophyly.

        Args:
            mapping_file: Path to CSV/TSV file with taxonomy mapping.
            rank: Taxonomic rank to analyze.
            style_monophyletic: If True, automatically style monophyletic groups.

        Returns:
            Dictionary with analysis results.

        Example:
            CSV file format::

                taxon,phylum,class,order,family
                T001,Synthetic,Metazoa,GroupA,FamilyA
                T002,Synthetic,Metazoa,GroupA,FamilyA
        """
        return self.analyze_taxonomy(
            mapping_file=mapping_file,
            rank=rank,
            style_monophyletic=style_monophyletic,
        )

    def parse_label_taxonomy(
        self,
        pattern: str,
    ) -> Dict[str, Dict[str, str]]:
        """Parse taxonomy information from node labels.

        Args:
            pattern: Regex pattern with named groups, or built-in pattern name.

        Returns:
            Dictionary mapping label to taxonomy dict.

        Example:
            .. code-block:: python

                styler = FigTreeStyler("tree.nwk")

                # Using built-in pattern
                taxonomy = styler.parse_label_taxonomy("genus_species")

                # Using custom pattern
                taxonomy = styler.parse_label_taxonomy(
                    r"^(?P<genus>[A-Z][a-z]+)_(?P<species>[a-z]+)"
                )
        """
        mapper = TaxonomyMapper(pattern=pattern)

        # Get labels from tree
        tree = self._parse_tree_with_biopython(self._tree_content)
        if tree is None:
            raise ExportError("Failed to parse tree")

        labels = [t.name for t in tree.get_terminals() if t.name]
        return mapper.parse_labels(
            labels,
            mode=self._taxonomy_delimiter_mode,
            sep=self._taxonomy_table_sep,
        )

    def check_taxonomy_completeness(
        self,
        pattern: Optional[str] = None,
        mapping_file: Optional[str] = None,
        required_ranks: Optional[List[str]] = None,
    ) -> dict:
        """Check completeness of taxonomy data.

        Args:
            pattern: Regex pattern for parsing labels.
            mapping_file: Path to mapping file.
            required_ranks: List of required taxonomic ranks.

        Returns:
            Dictionary with completeness information.
        """
        mapper = TaxonomyMapper(pattern=pattern, mapping_file=mapping_file)

        tree = self._parse_tree_with_biopython(self._tree_content)
        if tree is None:
            raise ExportError("Failed to parse tree")

        labels = [t.name for t in tree.get_terminals() if t.name]

        if pattern:
            mapper.parse_labels(labels)
        else:
            mapper.parse_labels(
                labels,
                mode=self._taxonomy_delimiter_mode,
                sep=self._taxonomy_table_sep,
            )

        return mapper.check_completeness(labels, required_ranks)

    def _generate_group_colors(self, n: int) -> List[str]:
        """Generate n distinct colors for groups."""
        # Predefined colors for common cases
        predefined = [
            "#E91E63",  # Pink
            "#2196F3",  # Blue
            "#4CAF50",  # Green
            "#FF9800",  # Orange
            "#9C27B0",  # Purple
            "#00BCD4",  # Cyan
            "#795548",  # Brown
            "#607D8B",  # Blue Grey
            "#F44336",  # Red
            "#3F51B5",  # Indigo
        ]

        if n <= len(predefined):
            return predefined[:n]

        # Generate more colors using HSV
        colors = []
        for i in range(n):
            hue = i / n
            r, g, b = colorsys.hsv_to_rgb(hue, 0.7, 0.9)
            colors.append(f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}")
        return colors

    # ------------------------------------------------------------------
    # Settings API
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_mapped_kwargs(target: Dict[str, Any], kwargs: Dict[str, Any],
                             mapping: Dict[str, str]) -> None:
        """Apply keyword arguments to *target* dict using *mapping*.

        Keys not in *mapping* are passed through unchanged.
        ``None`` values are skipped. Enum values are converted to their
        underlying value (e.g., ``FontStyle.BOLD`` → ``1``).
        """
        for key, val in kwargs.items():
            if val is None:
                continue
            if isinstance(val, FontStyle):
                val = val.value
            target[mapping.get(key, key)] = val

    _APPEARANCE_MAPPING: Dict[str, str] = {
        'branch_line_width': 'branchLineWidth',
        'background_color': 'backgroundColour',
        'foreground_color': 'foregroundColour',
        'selection_color': 'selectionColour',
        'background_color_attribute': 'backgroundColorAttribute',
        'branch_color_attribute': 'branchColorAttribute',
        'branch_width_attribute': 'branchWidthAttribute',
        'branch_min_line_width': 'branchMinLineWidth',
        'branch_color_gradient': 'branchColorGradient',
        'hilighting_gradient': 'hilightingGradient',
    }

    def set_appearance(self, **kwargs: Any) -> "FigTreeStyler":
        """Configure appearance settings.

        Keyword Args:
            branch_line_width: Branch line width.
            background_color: Background hex color.
            foreground_color: Foreground hex color.
            selection_color: Selection hex color.
            background_color_attribute: Attribute for background coloring.
            branch_color_attribute: Attribute for branch coloring.
            branch_width_attribute: Attribute for branch width mapping.
            branch_min_line_width: Minimum line width.
            branch_color_gradient: Enable gradient branch coloring.
            hilighting_gradient: Enable gradient highlighting.
            discrete_coloring: Enable discrete color scheme (appends ``*`` to attribute).

        Returns:
            self for method chaining.
        """
        s = self._settings.appearance

        # Create a copy to avoid mutating the caller's kwargs dict
        kwargs = kwargs.copy()

        # Validate color arguments before applying
        for color_key in ('background_color', 'foreground_color', 'selection_color'):
            if color_key in kwargs and kwargs[color_key] is not None:
                if not TreeValidator.validate_color(kwargs[color_key]):
                    raise ValidationError(f"Invalid {color_key}: {kwargs[color_key]}")
                kwargs[color_key] = kwargs[color_key].lower()

        # Handle discrete_coloring special case
        discrete = kwargs.pop('discrete_coloring', None)

        # Apply mapped kwargs
        self._apply_mapped_kwargs(s, kwargs, self._APPEARANCE_MAPPING)

        # Post-process discrete_coloring
        if discrete is not None:
            branch_color_attr = kwargs.get('branch_color_attribute')
            if branch_color_attr:
                if discrete and not branch_color_attr.endswith('*'):
                    s['branchColorAttribute'] = f"{branch_color_attr} *"
            else:
                # Check if branch_color_attribute was set in a previous call
                existing_attr = s.get('branchColorAttribute')
                if existing_attr and existing_attr != "None" and discrete:
                    # Append '*' to existing attribute if not already present
                    if not existing_attr.endswith('*'):
                        s['branchColorAttribute'] = f"{existing_attr} *"
                elif discrete:
                    warnings.warn("discrete_coloring=True requires branch_color_attribute; ignoring")

        return self

    def set_hilighting(self, is_shown: Optional[bool] = None,
                       gradient: Optional[bool] = None) -> "FigTreeStyler":
        if is_shown is not None:
            self._settings.hilighting['isShown'] = is_shown
        if gradient is not None:
            self._settings.hilighting['gradient'] = gradient
        return self

    def set_layout(self, layout_type: Optional[LayoutType] = None,
                   expansion: Optional[int] = None,
                   zoom: Optional[float] = None) -> "FigTreeStyler":
        if layout_type is not None:
            self._settings.layout['layoutType'] = layout_type.value
        if expansion is not None:
            self._settings.layout['expansion'] = expansion
        if zoom is not None:
            self._settings.layout['zoom'] = zoom
        return self

    def set_align_tip_labels(self, align: bool = True) -> "FigTreeStyler":
        """Set alignTipLabels for the current layout type.

        Automatically selects the correct layout-specific setting
        (rectilinearLayout, radialLayout, or polarLayout) based on the
        currently active layout type.

        Args:
            align: Whether to align tip labels.

        Returns:
            Self for method chaining.
        """
        layout_type = self._settings.layout.get('layoutType', 'RECTILINEAR')
        if layout_type == 'RECTILINEAR':
            self._settings.rectilinearLayout['alignTipLabels'] = align
        elif layout_type == 'RADIAL':
            self._settings.radialLayout['alignTipLabels'] = align
        elif layout_type == 'POLAR':
            self._settings.polarLayout['alignTipLabels'] = align
        return self

    def set_trees(self, rooting: Optional[bool] = None,
                  rooting_type: Optional[RootingType] = None,
                  transform: Optional[bool] = None,
                  transform_type: Optional[TransformType] = None,
                  order: Optional[bool] = None,
                  order_type: Optional[OrderType] = None) -> "FigTreeStyler":
        if rooting is not None:
            self._settings.trees['rooting'] = rooting
        if rooting_type is not None:
            self._settings.trees['rootingType'] = rooting_type.value
        if transform is not None:
            self._settings.trees['transform'] = transform
        if transform_type is not None:
            self._settings.trees['transformType'] = transform_type.value
        if order is not None:
            self._settings.trees['order'] = order
        if order_type is not None:
            self._settings.trees['orderType'] = order_type.value
        return self

    _LABEL_MAPPING: Dict[str, str] = {
        'is_shown': 'isShown', 'font_name': 'fontName', 'font_size': 'fontSize',
        'font_style': 'fontStyle', 'display_attribute': 'displayAttribute',
        'color_attribute': 'colorAttribute', 'significant_digits': 'significantDigits',
    }

    def set_tip_labels(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.tipLabels, kwargs, self._LABEL_MAPPING)
        return self

    def set_node_labels(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.nodeLabels, kwargs, self._LABEL_MAPPING)
        return self

    def set_branch_labels(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.branchLabels, kwargs, self._LABEL_MAPPING)
        return self

    _SCALE_BAR_MAPPING: Dict[str, str] = {
        'is_shown': 'isShown', 'automatic_scale': 'automaticScale',
        'scale_range': 'scaleRange', 'font_name': 'fontName',
        'font_size': 'fontSize', 'font_style': 'fontStyle',
        'line_width': 'lineWidth', 'significant_digits': 'significantDigits',
        'color': 'colour',
    }

    def set_scale_bar(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.scaleBar, kwargs, self._SCALE_BAR_MAPPING)
        return self

    _SCALE_AXIS_MAPPING: Dict[str, str] = {
        'is_shown': 'isShown', 'automatic_scale': 'automaticScale',
        'reverse_axis': 'reverseAxis', 'show_grid': 'showGrid',
        'font_name': 'fontName', 'font_size': 'fontSize',
        'font_style': 'fontStyle', 'line_width': 'lineWidth',
        'major_ticks': 'majorTicks', 'origin': 'origin',
        'significant_digits': 'significantDigits',
        'tick_direction': 'tickDirection', 'color': 'colour',
    }

    def set_scale_axis(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.scaleAxis, kwargs, self._SCALE_AXIS_MAPPING)
        return self

    _SCALE_MAPPING: Dict[str, str] = {
        'root_age': 'rootAge', 'scale_root': 'scaleRoot',
        'scale_factor': 'scaleFactor', 'offset_age': 'offsetAge',
        'auto_scale': 'autoScale',
    }

    def set_scale(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.scale, kwargs, self._SCALE_MAPPING)
        return self

    _POLAR_MAPPING: Dict[str, str] = {
        'align_tip_labels': 'alignTipLabels', 'angular_range': 'angularRange',
        'root_angle': 'rootAngle', 'root_length': 'rootLength',
        'show_root': 'showRoot',
    }

    def set_polar_layout(self, **kwargs: Any) -> "FigTreeStyler":
        """Configure polar layout.

        ``angular_range`` and ``root_angle`` are given in **degrees**
        (e.g. ``angular_range=180`` for a half-circle, ``root_angle=270``
        to centre the tree at 6 o'clock).  They are internally converted
        to the integer *slider* values that FigTree stores in its NEXUS
        settings block (see ``PolarTreeLayoutController``).
        """
        # FigTree's NEXUS format stores slider integers, not actual angles.
        #   rootAngle slider  = (actual - 180) * 1000
        #   angularRange slider = (360 - actual) * 1000
        if 'angular_range' in kwargs and kwargs['angular_range'] is not None:
            kwargs['angular_range'] = int((360 - kwargs['angular_range']) * 1000)
        if 'root_angle' in kwargs and kwargs['root_angle'] is not None:
            kwargs['root_angle'] = int((kwargs['root_angle'] - 180) * 1000)
        self._apply_mapped_kwargs(self._settings.polarLayout, kwargs, self._POLAR_MAPPING)
        return self

    _RADIAL_MAPPING: Dict[str, str] = {
        'align_tip_labels': 'alignTipLabels', 'spread': 'spread',
    }

    def set_radial_layout(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.radialLayout, kwargs, self._RADIAL_MAPPING)
        return self

    _RECTILINEAR_MAPPING: Dict[str, str] = {
        'align_tip_labels': 'alignTipLabels', 'curvature': 'curvature',
        'root_length': 'rootLength',
    }

    def set_rectilinear_layout(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.rectilinearLayout, kwargs, self._RECTILINEAR_MAPPING)
        return self

    _NODE_BARS_MAPPING: Dict[str, str] = {
        'is_shown': 'isShown', 'bar_width': 'barWidth',
        'attribute': 'attribute', 'color_attribute': 'colorAttribute',
        'color': 'colour', 'font_size': 'fontSize',
        'font_style': 'fontStyle', 'significant_digits': 'significantDigits',
    }

    def set_node_bars(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.nodeBars, kwargs, self._NODE_BARS_MAPPING)
        return self

    _NODE_SHAPES_MAPPING: Dict[str, str] = {
        'is_shown': 'isShown', 'attribute': 'attribute',
        'color_attribute': 'colorAttribute', 'shape_type': 'shapeType',
        'color': 'colour', 'size': 'size', 'font_size': 'fontSize',
        'font_style': 'fontStyle', 'significant_digits': 'significantDigits',
        'stroke_width': 'strokeWidth',
    }

    def set_node_shapes(self, **kwargs: Any) -> "FigTreeStyler":
        self._apply_mapped_kwargs(self._settings.nodeShapes, kwargs, self._NODE_SHAPES_MAPPING)
        return self

    _LEGEND_MAPPING: Dict[str, str] = {
        'is_shown': 'isShown', 'position': 'position',
        'x_position': 'x', 'y_position': 'y',
        'font_size': 'fontSize', 'font_style': 'fontStyle',
        'color': 'colour', 'background_color': 'backgroundColour',
        'background_opacity': 'backgroundOpacity',
        'border_width': 'borderWidth', 'reverse_order': 'reverseOrder',
        'is_visible': 'isVisible',
    }

    def set_legend(self, **kwargs: Any) -> "FigTreeStyler":
        if 'position' in kwargs and isinstance(kwargs['position'], str):
            kwargs = {**kwargs, 'position': kwargs['position'].capitalize()}
        self._apply_mapped_kwargs(self._settings.legend, kwargs, self._LEGEND_MAPPING)
        return self

    def set_custom_param(self, key: str, value: Any) -> "FigTreeStyler":
        """Set a custom parameter not covered by the typed API."""
        if '.' in key:
            category, param = key.split('.', 1)
            attr = getattr(self._settings, category, None)
            if isinstance(attr, dict):
                attr[param] = value
            else:
                self._settings._custom[key] = value
        else:
            self._settings._custom[key] = value
        return self

    def get_settings(self) -> Dict[str, Any]:
        return self._settings.to_dict()

    def get_tree_content(self) -> Optional[str]:
        """Return the current tree content (Newick string), or ``None`` if not loaded."""
        return self._tree_content

    def parse_tree(self) -> Optional[Any]:
        """Parse the current tree content with Bio.Phylo and return a Tree object.

        This is a public wrapper around :meth:`_parse_tree_with_biopython`,
        intended for downstream scripts that need direct access to the parsed
        ``Bio.Phylo.BaseTree.Tree`` object (e.g., for custom taxonomic
        analysis or label extraction).

        Returns:
            Bio.Phylo Tree object, or ``None`` if no tree content is loaded
            or parsing fails.
        """
        if not self._tree_content:
            return None
        return self._parse_tree_with_biopython(self._tree_content)

    def apply_dict(self, settings_dict: Dict[str, Any]) -> "FigTreeStyler":
        for key, value in settings_dict.items():
            self.set_custom_param(key, value)
        return self

    def reset(self, keep_tree: bool = False) -> "FigTreeStyler":
        """Reset all styling settings, annotations, and cached state.

        By default, also clears the loaded tree content — the caller must
        re-load the tree via :meth:`load_file` or :meth:`load_content`
        before further operations.

        Args:
            keep_tree: If True, preserve the loaded tree content and its
                parsed metadata (format, blocks, translate table, etc.).
                Only styling settings, annotations, and taxonomy config
                are reset. This is useful when you want to discard all
                styling but keep the same tree loaded for a fresh look.

        Returns:
            self for method chaining.

        Example:

            .. code-block:: python

                # Full reset — tree content is also cleared
                styler.reset()

                # Reset only styling, keep the tree
                styler.reset(keep_tree=True)
        """
        self._settings = FigTreeSettings()
        self._hilight_marks = []
        self._node_height_cache = {}
        self._height_cache = {}
        # Reset taxonomy config to defaults
        self._taxonomy_delimiter_mode = "reverse"
        self._taxonomy_table_sep = ";"
        self._taxonomy_source_priority = "table"
        self._taxonomy_mapping_file = None
        self._ignore_malformed = False
        self._table_sep = None

        if not keep_tree:
            self._tree_content = None
            self._is_nexus_format = False
            self._tree_block = None
            self._taxa_block = None
            self._translate_block = None
            self._all_trees = []

        return self

    def _serialize_value(self, value: Any) -> str:
        return serialize_value(value)

    def _generate_figtree_block(self) -> str:
        return generate_figtree_block(self._settings.to_dict())

    def validate(self) -> List[str]:
        """Validate the current tree content for FigTree compatibility.

        Returns:
            List of warning/error messages. Empty list means valid.
        """
        issues: List[str] = []
        if self._tree_content is None:
            issues.append("No tree content loaded")
            return issues

        tree = self._parse_tree_with_biopython(self._tree_content)
        if tree is None:
            issues.append("Bio.Phylo failed to parse the tree")
            return issues

        for clade in tree.find_clades():
            if clade.branch_length is not None and clade.branch_length < 0:
                issues.append(
                    f"Negative branch length ({clade.branch_length}) on "
                    f"node '{clade.name or '<internal>'}'"
                )

        taxa = extract_taxa_from_newick(self._tree_content)
        if not taxa:
            issues.append("No terminal taxa found")

        return issues

    # ------------------------------------------------------------------
    # Export — non-mutating annotation resolution and file write
    # ------------------------------------------------------------------

    def _parse_translate_block(self) -> Dict[str, str]:
        """Parse translate block and return mapping from taxon name to translate ID.

        Implemented as an explicit four-state machine
        (``TRANSLATE_NORMAL``, ``TRANSLATE_IN_SINGLE_QUOTE``,
        ``TRANSLATE_IN_DOUBLE_QUOTE``, ``TRANSLATE_ESCAPING``) so that
        quoted taxon names containing commas, nested quotes of the other
        kind, and doubled-quote escapes (``''`` / ``""`` per the Nexus
        specification) are all handled deterministically.

        Returns:
            Dictionary mapping taxon names to their translate IDs.
            Returns empty dict if no translate block exists.
        """
        if not self._translate_block:
            return {}

        mapping: Dict[str, str] = {}
        # Extract content after 'translate' keyword
        content = re.sub(r'^\s*translate\s+', '', self._translate_block, flags=re.IGNORECASE)
        content = content.rstrip(';').strip()

        # Four-state machine: split the block into comma-delimited entries,
        # keeping commas and quotes inside quoted regions verbatim.
        entries: List[str] = []
        current = ''
        state = TRANSLATE_NORMAL
        open_quote = ''
        for char in content:
            if state == TRANSLATE_ESCAPING:
                # The previous character was a quote matching the open one.
                if char == open_quote:
                    # Doubled quote: an escaped literal quote inside the name.
                    current += char
                    state = (
                        TRANSLATE_IN_SINGLE_QUOTE
                        if open_quote == "'"
                        else TRANSLATE_IN_DOUBLE_QUOTE
                    )
                    continue
                # Otherwise the previous quote closed the region; fall
                # through and reprocess *char* in NORMAL state.
                state = TRANSLATE_NORMAL
            if state == TRANSLATE_NORMAL:
                if char == "'":
                    state = TRANSLATE_IN_SINGLE_QUOTE
                    open_quote = char
                    current += char
                elif char == '"':
                    state = TRANSLATE_IN_DOUBLE_QUOTE
                    open_quote = char
                    current += char
                elif char == ',':
                    entries.append(current.strip())
                    current = ''
                else:
                    current += char
            else:  # IN_SINGLE_QUOTE or IN_DOUBLE_QUOTE
                matching = "'" if state == TRANSLATE_IN_SINGLE_QUOTE else '"'
                if char == matching:
                    open_quote = matching
                    state = TRANSLATE_ESCAPING
                    current += char
                else:
                    current += char
        # A trailing closing quote leaves the machine in ESCAPING; the
        # quoted region is simply complete.
        if current.strip():
            entries.append(current.strip())

        for entry in entries:
            if not entry:
                continue
            # Parse each entry: ID (whitespace) name
            parts = entry.split(None, 1)
            if len(parts) != 2:
                continue
            translate_id, taxon_name = parts
            translate_id = translate_id.strip()
            taxon_name = taxon_name.strip()
            # Remove quotes if present
            if (taxon_name.startswith("'") and taxon_name.endswith("'")) or \
               (taxon_name.startswith('"') and taxon_name.endswith('"')):
                taxon_name = taxon_name[1:-1]
            # Unescape doubled quotes per Nexus specification ('' → ')
            taxon_name = taxon_name.replace("''", "'").replace('""', '"')
            if taxon_name:
                mapping[taxon_name] = translate_id

        return mapping

    def _resolve_annotations_copy(self) -> str:
        """Return a copy of tree content with all pending annotations applied.

        Does **not** mutate ``self._tree_content``.  Returns the original
        content unchanged if parsing fails or no annotations are pending.
        When a translate block exists, converts taxon names back to translate
        IDs in the serialized output to maintain consistency.

        Preserves existing bracket comments (``[&...]``) from the original
        tree by extracting them before Bio.Phylo parsing and re-inserting
        them after serialization. This prevents metadata loss for BEAST
        posterior probabilities and other bracket annotations.
        """
        # Reset hilight marker state at the very start so the early-return
        # branch below (tree parse failure) cannot leak stale markers from a
        # previous export into the next one (fix #18).
        self._hilight_marks = []

        tree = self._parse_tree_with_biopython(self._tree_content)
        if not tree:
            if self._settings._node_annotations:
                warnings.warn(
                    f"Tree parsing failed — {len(self._settings._node_annotations)} "
                    f"annotation(s) will not be applied to the output.",
                    CompatibilityWarning,
                )
            return self._tree_content

        # Extract existing bracket comments before Bio.Phylo strips them
        bracket_comments = self._extract_bracket_comments(self._tree_content)

        # ── Phase 1: Apply hilight annotations BEFORE collapses ──
        # Hilight needs the original tree structure to find the correct MRCA.
        # After collapses, original taxa are removed and MRCA resolves to root.
        # The hilight band is written directly into the MRCA node's bracket
        # comment (jebl meta-comment format) rather than renaming the node.
        # This avoids any collision with a collapse label written to the same
        # node's *name*, and lets root nodes / nodes without a branch length
        # receive the band correctly (fix #20).
        resolved = list(self._settings._node_annotations)
        unresolved_hilights = []
        # Each entry: (mrca_node, tip_count, height, color)
        self._hilight_marks = []
        _hl_idx = 0
        for ann in resolved:
            if ann.annotation_type != 'hilight' or not ann.target_taxa:
                continue
            try:
                mrca = self._find_mrca_clade(tree, ann.target_taxa)
                if mrca:
                    tip_count = len(mrca.get_terminals())
                    # FigTree's !hilight height uses
                    # RootedTreeUtils.getMinTipHeight(tree, node)
                    # (TreePane.java:781-784) — the same jebl time-backward
                    # convention as the collapse height.  Use the shared
                    # _get_min_tip_height implementation so hilight and
                    # collapse bands are positioned in the same coordinate
                    # system.
                    height = self._get_min_tip_height(tree, mrca)
                    _raw_color = ann.values[2] if isinstance(ann.values, (list, tuple)) and len(ann.values) >= 3 else "#ff0000"
                    # Normalize the color to lowercase so the band serialized
                    # here (and re-written by the Phase 2b regex) matches the
                    # lowercased value emitted by _inject_annotation_to_node
                    # and FigTree's case-insensitive hex parsing.
                    color = _raw_color.lower() if isinstance(_raw_color, str) else _raw_color
                    # Inject the band straight into the node comment using the
                    # shared annotation engine (the node object, not a temporary
                    # marker name, is recorded so Phase 2b and the color
                    # exclusion logic can locate it without relying on a
                    # name that a subsequent collapse might overwrite).
                    self._inject_annotation_to_node(
                        mrca, 'hilight', [tip_count, height, color]
                    )
                    self._hilight_marks.append((mrca, tip_count, height, color))
                    _hl_idx += 1
                else:
                    unresolved_hilights.append(ann)
            except (ValueError, AttributeError):
                unresolved_hilights.append(ann)

        # ── Phase 2: Apply collapses ──
        if self._settings._collapses:
            tree = self._apply_collapses_to_tree(tree)

        # ── Phase 2b: Recompute hilight tip counts after collapses ──
        # After collapse, the actual number of terminal taxa under each
        # hilight MRCA may differ from the pre-collapse count. FigTree
        # uses this tip_count to determine the hilight's angular span in
        # polar/radial layouts, so an outdated count causes the hilight
        # to cover far too much area.  We operate on the stored node
        # objects directly (no per-marker full-tree scan), which also
        # resolves #27.
        if self._hilight_marks:
            for entry in self._hilight_marks:
                node, _old_tip_count, height, color = entry
                new_tip_count = len(node.get_terminals() or [])
                # Update the !hilight={...} band already written into the
                # node comment (tip_count may have changed after collapse).
                if node.comment and "!hilight=" in node.comment:
                    node.comment = re.sub(
                        r'(!hilight=\{)[^}]*(\})',
                        lambda m, tc=new_tip_count, h=height, c=color:
                            f"{m.group(1)}{tc},{h},{c}{m.group(2)}",
                        node.comment,
                        count=1,
                    )

        # ── Phase 3: Apply remaining annotations (color, font, stroke, etc.) ──
        # Collect hilight node ids so a branch color is never stacked onto a
        # hilight node (which would trigger a FigTree ClassCastException).
        _hl_node_ids = {id(m[0]) for m in self._hilight_marks}

        for i, ann in enumerate(resolved):
            if ann.annotation_type == 'hilight':
                continue
            if ann.annotation_type == 'color_all' and ann.target_taxa:
                mrca = self._find_mrca_clade(tree, ann.target_taxa)
                if mrca:
                    color_value = ann.values.lower() if isinstance(ann.values, str) else ann.values
                    for clade in mrca.find_clades():
                        if id(clade) in _hl_node_ids:
                            continue
                        self._inject_annotation_to_node(clade, 'color', color_value)
            elif ann.annotation_type == 'color' and ann.target_taxa:
                target_node = self._find_mrca_clade(tree, ann.target_taxa)
                if target_node:
                    if id(target_node) in _hl_node_ids:
                        warnings.warn(
                            f"Branch color for taxa {ann.target_taxa} conflicts with "
                            f"a hilight annotation on the same node — the color will "
                            f"be dropped to prevent a FigTree ClassCastException. "
                            f"Use set_clade_color_all() instead to color descendant branches.",
                            CompatibilityWarning,
                        )
                    else:
                        self._inject_annotation_to_node(
                            target_node, ann.annotation_type, ann.values,
                            extra_params=ann.extra_params
                        )
            elif ann.annotation_type not in ('hilight', 'color_all', 'color'):
                # Generic annotations (font, stroke, etc.) reuse the shared
                # single-annotation engine so this loop does not duplicate the
                # MRCA resolution / injection logic in _apply_annotations_to_tree.
                self._apply_single_annotation(tree, ann)

        # Strip any !color annotation from hilight nodes (node-id based) to
        # avoid a FigTree ClassCastException when both appear on the same node.
        if _hl_node_ids:
            for entry in self._hilight_marks:
                node = entry[0]
                if node.comment and "!color=" in node.comment:
                    node.comment = re.sub(r'&?!color=[^,&]+,?', '', node.comment).strip(',').strip()
                    # Ensure & prefix if comment is non-empty (jebl meta-comment format)
                    if node.comment and not node.comment.startswith('&'):
                        node.comment = '&' + node.comment
                    if not node.comment:
                        node.comment = None

        unresolved = unresolved_hilights + [
            a for a in resolved
            if a.annotation_type not in ('hilight', 'color_all')
            and a.target_taxa
            and not self._find_mrca_clade(tree, a.target_taxa)]
        if unresolved:
            warnings.warn(
                f"{len(unresolved)} annotation(s) could not be resolved "
                f"and were skipped: {'; '.join(str(a) for a in unresolved)}",
                CompatibilityWarning,
            )
        serialized = self._serialize_tree_to_newick(tree)
        if serialized:
            # Re-insert preserved bracket comments
            if bracket_comments:
                serialized = self._reinsert_bracket_comments(serialized, bracket_comments)

            if self._translate_block:
                translate_map = self._parse_translate_block()
                if translate_map:
                    for taxon_name, translate_id in sorted(
                        translate_map.items(), key=lambda x: len(x[0]), reverse=True
                    ):
                        # Try both quoted and unquoted replacement to handle
                        # inconsistent quoting between Bio.Phylo and our extraction
                        escaped_name = taxon_name.replace("'", "''")
                        # First try quoted replacement
                        quoted_replaced = serialized.replace(f"'{escaped_name}'", translate_id)
                        if quoted_replaced != serialized:
                            serialized = quoted_replaced
                        else:
                            # Try unquoted replacement, but restrict to
                            # taxon-name tokens only (preceded by '(' or ',';
                            # followed by ':', ',', ')', ';' or end-of-string).
                            # This prevents matching numeric taxon names inside
                            # branch lengths such as '0.123'.
                            pattern = (
                                r'(^|[(,])\s*' + re.escape(taxon_name)
                                + r'\s*(?=[,:);]|$)'
                            )
                            serialized = re.sub(
                                pattern,
                                lambda m: m.group(1) + translate_id,
                                serialized,
                            )
            return serialized
        return self._tree_content

    def _extract_bracket_comments(self, newick: str) -> List[Dict[str, Any]]:
        """Extract bracket comments from a Newick string, preserving their positions.

        Delegates to :func:`_parser.extract_bracket_comments`; the parsing
        layer owns the mechanism, this method remains for backward
        compatibility with existing callers and tests.
        """
        return extract_bracket_comments(newick)

    def _reinsert_bracket_comments(self, newick: str, comments: List[Dict[str, Any]]) -> str:
        """Re-insert bracket comments into a serialized Newick string.

        Delegates to :func:`_parser.reinsert_bracket_comments`; see that
        function for the matching strategy.
        """
        return reinsert_bracket_comments(newick, comments)

    def _write_taxa_block(self, out, include_taxa_block: bool,
                          resolved_content: Optional[str] = None) -> None:
        """Write the taxa block to the output file.

        Delegates to :func:`_serializer.write_taxa_block`; the serialization
        layer owns the physical block writing.
        """
        write_taxa_block(
            out,
            include_taxa_block=include_taxa_block,
            is_nexus_format=self._is_nexus_format,
            tree_content=self._tree_content,
            resolved_content=resolved_content,
            has_collapses=bool(self._settings._collapses),
            taxa_block=self._taxa_block,
        )

    def _write_trees_block(
        self, out, resolved_tree_content: str, single_tree: bool = False
    ) -> None:
        """Write the trees block to the output file.

        Delegates to :func:`_serializer.write_trees_block`; the
        serialization layer owns the physical block writing.
        """
        write_trees_block(
            out,
            resolved_tree_content=resolved_tree_content,
            single_tree=single_tree,
            is_nexus_format=self._is_nexus_format,
            translate_block=self._translate_block,
            tree_block=self._tree_block,
            has_trees=bool(self._all_trees),
            tree_index=self._tree_index,
        )

    def _write_figtree_block(self, out) -> None:
        """Write the figtree settings block to the output file.

        Delegates to :func:`_serializer.write_figtree_block`.
        """
        write_figtree_block(out, self._generate_figtree_block())

    def strip_annotations(self) -> "FigTreeStyler":
        """Remove all bracket comments (e.g. NHX, bootstrap) from tree content.

        Strips ``[...]`` comment blocks from the loaded Newick/Nexus tree
        content, including NHX annotations (``[&&NHX:...]``), bootstrap
        support values, and posterior probability comments. This is useful
        for reducing output file size when annotations are not needed.

        Annotations injected by FigTreeKit itself (e.g. ``[&!hilight=...]``)
        are applied during export, after this method runs, so they are not
        affected.

        Returns:
            self for method chaining.
        """
        if self._tree_content is None:
            return self

        # Remove all [...] bracket comments (including nested) from the
        # Newick tree string (fix #32), via the canonical parser-layer scan.
        self._tree_content = strip_square_bracket_comments(self._tree_content)

        # Also strip from multi-tree content if present
        if self._all_trees:
            self._all_trees = [
                strip_square_bracket_comments(t) if t else t
                for t in self._all_trees
            ]

        return self

    def export(
        self,
        output_file: str,
        include_taxa_block: bool = True,
        single_tree: bool = False,
    ) -> "FigTreeStyler":
        """Export the styled tree to a Nexus file.

        The tree content is resolved (annotations applied) into a local copy
        so that ``self._tree_content`` is never mutated.  The output file is
        written atomically via a temporary file that is renamed into place
        once the write completes successfully.

        Args:
            output_file: Path for the output Nexus file.
            include_taxa_block: Whether to include the taxa block. When ``True``
                (default), a taxa block is generated from Newick input or
                preserved from Nexus input. When ``False``, the taxa block is
                omitted entirely — this produces a minimal Nexus file that may
                not display taxon labels in FigTree.
            single_tree: If ``True`` and the input was a multi-tree Nexus file,
                export only the tree selected by ``tree_index`` instead of
                preserving all trees. Default ``False`` preserves all trees.

        Returns:
            self for method chaining.

        Raises:
            ExportError: If no tree content is available.

        Notes:
            - **Multi-tree input:** annotations are applied only to the tree
              selected by ``tree_index``.  The other trees in a multi-tree
              Nexus file are written back unchanged (unstyled).  Pass
              ``single_tree=True`` to drop the unstyled trees entirely.
            - **Posterior probabilities / branch-length metadata:** BEAST
              bracket comments attached to *branch lengths*
              (``:0.123[&posterior=0.95]``) cannot be reliably re-inserted
              after Bio.Phylo serialization and may be lost.  Comments
              attached to *taxon names* are preserved.  Attach critical
              metadata to taxon names rather than branch lengths when
              round-tripping through ``export()``.
            - Taxon names containing ``;`` are rewritten to ``,`` so that
              FigTree's Nexus parser does not misinterpret them.
        """
        # Reset hilight marker state at the very entry (before any early
        # return) so a second export() call — or an export following a failed
        # annotation resolve — never re-injects stale [_HL_x] markers left
        # behind by a previous run (fix #18).
        self._hilight_marks = []

        if self._tree_content is None:
            raise ExportError("No tree content available to export")

        if not include_taxa_block and not self._is_nexus_format:
            warnings.warn(
                "include_taxa_block=False with Newick input: the exported Nexus "
                "file will lack a taxa block. FigTree may not display taxon labels.",
                CompatibilityWarning,
            )

        resolved_content = self._resolve_annotations_copy()

        # Atomic write: write to temp file first, then rename
        output_path = Path(output_file)
        tmp_path = output_path.with_suffix(output_path.suffix + '.tmp')
        try:
            with open(tmp_path, 'w', encoding='utf-8', newline='\n') as out:
                out.write("#NEXUS\n")
                self._write_taxa_block(out, include_taxa_block, resolved_content)
                self._write_trees_block(out, resolved_content, single_tree=single_tree)
                self._write_figtree_block(out)
            tmp_path.replace(output_path)
        except BaseException:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

        # NOTE: hilight bands are injected directly into the MRCA node's
        # bracket comment inside _resolve_annotations_copy (fix #20), so no
        # post-export marker substitution is needed here.
        return self

    def render(
        self,
        output_file: str,
        format: Optional[str] = None,
        width: int = 1200,
        height: int = 800,
        jar_path: Optional[str] = None,
        include_taxa_block: bool = True,
        keep_nex: bool = False,
        timeout: int = 120,
    ) -> "FigTreeStyler":
        """Export and render the styled tree to an image file.

        This method first exports the tree to a temporary Nexus file,
        then uses FigTree's command-line interface to render it to an
        image. Requires Java 8+ and a compiled FigTree JAR.

        Args:
            output_file: Path for the output image file (e.g., ``"tree.png"``).
            format: Output format (``"PNG"``, ``"PDF"``, ``"SVG"``, ``"JPEG"``).
                If ``None`` (default), the format is auto-detected from the
                file extension and falls back to ``"PNG"``.
            width: Image width in pixels. Default ``1200``.
            height: Image height in pixels. Default ``800``.
            jar_path: Path to ``figtree.jar``. If ``None`` (default), searches
                in standard locations or uses ``FIGTREE_JAR`` environment variable.
            include_taxa_block: Whether to include the taxa block. Default ``True``.
            keep_nex: If ``True``, keep the intermediate Nexus file alongside
                the image. Default ``False``.

        Returns:
            self for method chaining.

        Raises:
            ExportError: If no tree content is available, Java is not installed,
                FigTree JAR is not found, or rendering fails.

        Example:
            .. code-block:: python

                styler = FigTreeStyler("input.tre")
                styler.set_layout(LayoutType.POLAR)
                styler.highlight_clade(["A", "B"], color="#FF0000")

                # Render to PNG
                styler.render("tree.png")

                # Render to PDF with custom size
                styler.render("tree.pdf", width=1600, height=1000)

                # Method chaining
                styler.export("tree.nex").render("tree.png")

        Note:
            Rendering requires FigTree (GPLv2), which is not bundled with
            FigTreeKit. Compile FigTree separately or set ``FIGTREE_JAR``
            environment variable. See: http://tree.bio.ed.ac.uk/software/figtree/
        """
        from ._renderer import render_with_figtree

        output_path = Path(output_file)
        if output_path.exists() and output_path.is_dir():
            raise ExportError(
                f"Render output path must be a file, but '{output_path}' is a directory"
            )

        # Ensure the output directory exists so that both the image and any
        # kept intermediate Nexus file can be written.
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Auto-detect format from extension when not explicitly provided.
        ext = os.path.splitext(output_file)[1].lower()
        format_map = {".png": "PNG", ".pdf": "PDF", ".svg": "SVG", ".jpg": "JPEG", ".jpeg": "JPEG"}
        if format is None:
            format = format_map.get(ext, "PNG")
        format = format.upper()

        # Export to temporary or permanent Nexus file
        if keep_nex:
            nex_file = str(Path(output_file).with_suffix('.nex'))
            self.export(nex_file, include_taxa_block=include_taxa_block)
        else:
            import tempfile
            tmp_f = tempfile.NamedTemporaryFile(
                mode='w', suffix='.nex', delete=False,
                encoding='utf-8', newline='\n',
            )
            nex_file = tmp_f.name
            tmp_f.close()
            os.chmod(nex_file, 0o600)
            try:
                self.export(nex_file, include_taxa_block=include_taxa_block)
            except BaseException:
                if os.path.exists(nex_file):
                    os.unlink(nex_file)
                raise

        try:
            render_with_figtree(
                nex_file, output_file, format, width, height, jar_path,
                timeout=timeout,
            )
        finally:
            if not keep_nex and os.path.exists(nex_file):
                os.unlink(nex_file)

        return self
