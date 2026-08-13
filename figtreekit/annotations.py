"""Node annotation data structures for FigTree metadata."""

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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# Values can be a list (hilight: a list of int/float/str), a string
# (color/font), or a number (stroke). Matches the value shapes that the
# FigTree Java TreePane serializer understands.
AnnotationValue = Union[List[Union[int, float, str]], str, float]


@dataclass
class NodeAnnotation:
    """A FigTree-compatible annotation for a tree node.

    According to FigTree Java source (``TreePane.java``), annotations are stored as:

    - ``!hilight``: ``[tipCount, height, color]``
    - ``!color``: ``"#RRGGBB"``
    - ``!font``: ``"name-style-size"``

    These are serialized in Newick format as ``[&!annotation=value]``.

    Attributes:
        annotation_type: Type of annotation (``'hilight'``, ``'color'``, ``'font'``, etc.).
        values: Annotation value; type depends on ``annotation_type``.
        target_taxa: Taxon names used to find the MRCA node for injection.
        extra_params: Additional parameters (e.g., ``width``, ``offset`` for hilight).
    """
    annotation_type: str
    values: AnnotationValue
    target_taxa: Optional[List[str]] = None
    extra_params: Optional[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class CladeCollapse:
    """A pending clade collapse operation.

    Attributes:
        target_taxa: Taxon names that define the clade to collapse.
        label: Display label for the collapsed node.  If ``None``, a
            default label is generated from the taxon names.
        group_name: If the collapse was requested by group name, store
            the original group name for reporting.
        collapse_type: Either ``"collapse"`` (default) or ``"cartoon"``.
            FigTree supports two clade-folding styles:
            - ``"collapse"``: ``!collapse={tipName, height}`` — the clade
              is drawn as a triangle whose tip carries *label*; the original
              tip labels are hidden.
            - ``"cartoon"``: ``!cartoon={tipCount, height}`` — the clade
              is drawn as a triangle spanning the original tip vertical
              range; original tip labels may still be shown.
    """
    target_taxa: List[str]
    label: Optional[str] = None
    group_name: Optional[str] = None
    collapse_type: str = "collapse"
