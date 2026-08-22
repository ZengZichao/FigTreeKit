# SPDX-License-Identifier: GPL-2.0-or-later
# This file is part of FigTreeKit; see LICENSE and NOTICE for licensing terms.
"""Taxonomy mapping and monophyly analysis for phylogenetic trees.

This module provides functionality to:
1. Parse taxonomy information from node labels
2. Map taxa to taxonomic groups using user-provided tables
3. Identify monophyletic groups automatically
4. Handle incomplete or inconsistent taxonomy data
5. Resolve taxon group names and special identifiers (LUCA/LACA/LBCA)
6. Unified handling of embedded and table-based taxonomy formats
"""

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

import csv
import logging
import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .exceptions import CompatibilityWarning, ValidationError

_log = logging.getLogger("figtreekit")


SPECIAL_IDENTIFIERS = {
    "LUCA": {"description": "Last Universal Common Ancestor of Bacteria and Archaea",
             "domains": ["Bacteria", "Archaea"]},
    "LACA": {"description": "Last Archaeal Common Ancestor",
             "domains": ["Archaea"]},
    "LBCA": {"description": "Last Bacterial Common Ancestor",
             "domains": ["Bacteria"]},
    "root": {"description": "Root of the tree (all terminal taxa)",
             "domains": None},
}

# Canonical set of special identifiers (uppercase-only for LUCA/LACA/LBCA)
_SPECIAL_IDS_UPPER = {"LUCA", "LACA", "LBCA"}
_SPECIAL_IDS_ALL = _SPECIAL_IDS_UPPER | {"root"}

# ── Configurable rank prefixes ──────────────────────────────────────────
# This is the single source of truth for prefix → rank mapping.
# Both format A (_X_) and format B (X__) are derived from this.
# Users can extend it via --taxonomy-levels CLI flag or programmatically.

_RANK_PREFIXES: Dict[str, str] = {
    "k": "kingdom",
    "d": "domain",
    "p": "phylum",
    "c": "class",
    "o": "order",
    "f": "family",
    "g": "genus",
    "s": "species",
    "ss": "subspecies",
}

_TAXONOMY_RANKS = list(_RANK_PREFIXES.values())


def get_rank_prefixes() -> Dict[str, str]:
    """Return a copy of the current rank-prefix configuration."""
    return dict(_RANK_PREFIXES)


def set_rank_prefixes(prefixes: Dict[str, str]) -> None:
    """Replace the rank-prefix configuration.

    .. warning::
        This mutates module-level globals (``_RANK_PREFIXES``,
        ``_TAXONOMY_RANKS`` and the derived ``_GTDB_RANK_PREFIXES`` /
        ``_EMBEDDED_RANK_PREFIXES`` maps).  It is **not thread-safe**:
        concurrent calls, or concurrent parsing while a call is in flight,
        may observe a partially-updated configuration.  Configure prefixes
        once at startup in long-running servers.

    .. note::
        **Prefer the instance-scoped alternative in parallel pipelines**
        (Snakemake/Nextflow workers, threads, async tasks):
        ``TaxonomyMapper(prefixes={...})`` and
        ``parse_taxonomy_auto(..., prefixes={...})`` apply a per-call
        configuration without touching module state, eliminating the race
        condition entirely.  This global function is retained for
        CLI-style single-process configuration and backward compatibility.

    Args:
        prefixes: Mapping from short prefix (e.g. ``"d"``) to rank name
            (e.g. ``"domain"``).
    """
    global _RANK_PREFIXES, _TAXONOMY_RANKS, _GTDB_RANK_PREFIXES, _EMBEDDED_RANK_PREFIXES
    _RANK_PREFIXES = dict(prefixes)
    _TAXONOMY_RANKS = list(_RANK_PREFIXES.values())
    _GTDB_RANK_PREFIXES = {f"{k}__": v for k, v in _RANK_PREFIXES.items()}
    _EMBEDDED_RANK_PREFIXES = {f"_{k}_": v for k, v in _RANK_PREFIXES.items()}


def extend_rank_prefixes(extra: Dict[str, str]) -> None:
    """Add additional rank prefixes without replacing existing ones.

    Args:
        extra: Additional prefix → rank mappings to merge.
    """
    merged = dict(_RANK_PREFIXES)
    merged.update(extra)
    set_rank_prefixes(merged)


def get_domain_rank_name() -> str:
    """Return the configured rank name for the domain level.

    The domain rank is the value mapped from the ``"d"`` prefix in
    :data:`_RANK_PREFIXES`.  Resolving the special identifiers
    ``LUCA``/``LACA``/``LBCA`` must look up each taxon's domain value, so the
    rank name must be derived from the active configuration rather than
    hard-coded as ``"domain"``.  This keeps special-identifier resolution
    correct when users remap the domain rank (e.g. via
    :func:`set_rank_prefixes` with ``{"d": "superkingdom"}``).
    """
    return _RANK_PREFIXES.get("d", "domain")


# Derived mappings (auto-rebuilt by set_rank_prefixes)
_GTDB_RANK_PREFIXES: Dict[str, str] = {f"{k}__": v for k, v in _RANK_PREFIXES.items()}
_EMBEDDED_RANK_PREFIXES: Dict[str, str] = {f"_{k}_": v for k, v in _RANK_PREFIXES.items()}

# Delimiter parsing modes for format A
_DELIMITER_MODES = ("reverse", "greedy", "segment")


def _build_prefix_maps(
    prefixes: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], List[str]]:
    """Build ``(rank_prefixes, embedded_map, gtdb_map, ranks_list)``.

    When *prefixes* is ``None`` the active module-level configuration is
    returned unchanged, preserving the historical global behaviour.
    Passing an explicit mapping gives callers a thread-safe,
    instance-scoped configuration (e.g. ``TaxonomyMapper(prefixes=...)``)
    without mutating module state.
    """
    if prefixes is None:
        return _RANK_PREFIXES, _EMBEDDED_RANK_PREFIXES, _GTDB_RANK_PREFIXES, _TAXONOMY_RANKS
    rp = dict(prefixes)
    return (
        rp,
        {f"_{k}_": v for k, v in rp.items()},
        {f"{k}__": v for k, v in rp.items()},
        list(rp.values()),
    )


# ── Format A: Embedded taxonomy (_d_Bacteria_p_...) ─────────────────────

def _parse_taxonomy_embedded(
    text: str, mode: str = "reverse",
    prefixes: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Parse embedded taxonomy from a label suffix.

    Handles format A: ``..._d_Bacteria_p_Cyanobacteriota_c_...``

    Supports three parsing modes:
      - ``reverse`` (default): scan markers right-to-left, require strict
        descending rank order (g→f→o→c→p→d).  Safest for labels whose
        prefix may contain spurious ``_d_`` etc.
      - ``greedy``: left-to-right scan, take the first occurrence of each
        marker.
      - ``segment``: from the first ``_d_`` onward, extract all markers
        in the suffix segment only.

    Args:
        text: Full label string.
        mode: Parsing mode (``"reverse"``, ``"greedy"``, or ``"segment"``).
        prefixes: Optional instance-scoped rank-prefix mapping. When
            ``None``, the active module-level configuration is used.

    Returns:
        Dict mapping rank name to value (empty string for missing levels).
    """
    if mode == "segment":
        return _parse_taxonomy_embedded_segment(text, prefixes=prefixes)
    if mode == "greedy":
        return _parse_taxonomy_embedded_greedy(text, prefixes=prefixes)
    return _parse_taxonomy_embedded_reverse(text, prefixes=prefixes)


def _parse_taxonomy_embedded_reverse(
    text: str, prefixes: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Order-independent embedded parsing (default).

    Scans every ``_<rank>_`` marker in *text* regardless of the order in
    which ranks appear, mapping each marker to its rank and extracting the
    value up to the next marker (or end of string).  This fixes the legacy
    behaviour where labels with ascending rank order (domain → phylum → …)
    silently dropped all but the deepest rank.

    A :class:`~figtreekit.exceptions.CompatibilityWarning` is emitted when
    the number of distinct ranks parsed is smaller than the number of
    markers found (e.g. duplicate rank prefixes in the label).
    """
    result: Dict[str, str] = {}
    rank_prefixes, embedded_map, _, _ = _build_prefix_maps(prefixes)

    # Longest rank prefixes first so "ss" wins over "s", etc.
    ranked_keys = sorted(rank_prefixes, key=len, reverse=True)
    pattern = r"_(" + "|".join(ranked_keys) + r")_"
    markers = list(re.finditer(pattern, text))
    if not markers:
        _log.debug(f"Embedded taxonomy: no valid markers found in '{text}'")
        return result

    for i, m in enumerate(markers):
        prefix = m.group(1)
        rank = embedded_map.get(m.group(0), f"unknown_{prefix}")
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        value = text[start:end].strip().rstrip('_')
        if rank not in result:
            result[rank] = value
        else:
            _log.debug(
                f"Embedded taxonomy: duplicate rank '{rank}' in '{text}', "
                f"keeping first occurrence"
            )

    if len(result) < len(markers):
        warnings.warn(
            f"Embedded taxonomy parsing dropped "
            f"{len(markers) - len(result)} marker(s) from '{text}' "
            f"(duplicate or unrecognised rank prefixes).",
            CompatibilityWarning,
            stacklevel=2,
        )

    return result


def _parse_taxonomy_embedded_greedy(
    text: str, prefixes: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Left-to-right greedy parsing (first occurrence of each marker).

    Uses the *active* ``_RANK_PREFIXES`` configuration (via the dynamically
    built ``_EMBEDDED_RANK_PREFIXES`` map) rather than a hard-coded regex, so
    prefixes added through :func:`extend_rank_prefixes` /
    :func:`set_rank_prefixes` are honoured here too — matching the behaviour
    of the ``reverse`` mode.
    """
    result: Dict[str, str] = {}
    rank_prefixes, embedded_map, _, _ = _build_prefix_maps(prefixes)
    # Longest rank prefixes first so "ss" wins over "s", etc.
    ranked_keys = sorted(rank_prefixes, key=len, reverse=True)
    pattern = r"_(" + "|".join(ranked_keys) + r")_"
    markers = list(re.finditer(pattern, text))
    if not markers:
        return result

    seen_prefixes: set = set()
    for i, m in enumerate(markers):
        prefix = m.group(1)
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        rank = embedded_map.get(m.group(0), f"unknown_{prefix}")
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        value = text[start:end].strip().rstrip('_')
        if value:
            result[rank] = value
        else:
            result[rank] = ""
            _log.debug(f"Embedded taxonomy: rank '{rank}' is empty in '{text}'")

    return result


def _parse_taxonomy_embedded_segment(
    text: str, prefixes: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """From first _d_ onward, extract all markers in suffix segment."""
    result: Dict[str, str] = {}
    first_d = re.search(r'_d_', text)
    if not first_d:
        return result
    segment = text[first_d.start():]
    return _parse_taxonomy_embedded_greedy(segment, prefixes=prefixes)


# ── Format B: GTDB-style semicolon (d__Archaea;p__...) ──────────────────

def _parse_taxonomy_string(
    taxonomy_str: str,
    sep: str = ";",
    prefixes: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Parse a delimited taxonomy string with rank prefixes.

    Handles format B:
        ``d__Archaea;p__Thermoproteota;c__Korarchaeia;...;s__``

    Args:
        taxonomy_str: Delimited taxonomy string.
        sep: Separator between rank entries (default ``";"``).
        prefixes: Optional instance-scoped rank-prefix mapping. When
            ``None``, the active module-level configuration is used.

    Returns:
        Dictionary mapping rank name to value (empty string for missing).

    Raises:
        ValidationError: If a value contains ``;`` or ``__`` (malformed).
    """
    _, _, gtdb_map, _ = _build_prefix_maps(prefixes)
    result: Dict[str, str] = {}
    for part in taxonomy_str.split(sep):
        part = part.strip()
        if not part:
            continue
        matched = False
        for prefix, rank_name in gtdb_map.items():
            if part.startswith(prefix):
                value = part[len(prefix):].strip()
                # Validate: value must not contain separator or __
                if sep in value:
                    raise ValidationError(
                        f"Malformed taxonomy value: {rank_name}='{value}' "
                        f"contains separator '{sep}'"
                    )
                if '__' in value:
                    raise ValidationError(
                        f"Malformed taxonomy value: {rank_name}='{value}' "
                        f"contains '__'"
                    )
                result[rank_name] = value
                if not value:
                    _log.debug(f"Table taxonomy: rank '{rank_name}' is empty")
                matched = True
                break
        if not matched:
            _log.debug(f"Table taxonomy: unrecognized prefix in '{part}'")
    return result


# ── Unified auto-detection ──────────────────────────────────────────────

def detect_taxonomy_format(text: str, prefixes: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Detect which taxonomy format a string uses.

    Uses the rank-prefix tables (``_EMBEDDED_RANK_PREFIXES`` /
    ``_GTDB_RANK_PREFIXES``) so that the longest prefix always wins — e.g.
    ``ss__Bacteria`` is correctly recognised as a subspecies table entry
    instead of being mis-classified as genus (``s__``).

    Args:
        text: Label or taxonomy string.
        prefixes: Optional instance-scoped rank-prefix mapping. When
            ``None``, the active module-level configuration is used.

    Returns:
        ``"embedded"`` for format A (``_d_``, ``_p_``, ...),
        ``"table"`` for format B (``d__``, ``p__``, ...),
        or ``None`` if no taxonomy markers found.
    """
    rank_prefixes, _, _, _ = _build_prefix_maps(prefixes)
    # Longest rank prefixes first so "ss" wins over "s", etc.
    ranked_keys = sorted(rank_prefixes, key=len, reverse=True)
    embedded_pattern = r"_(" + "|".join(ranked_keys) + r")_"
    # A table prefix must not be preceded by another rank letter
    # (prevents the inner "s__" of "ss__Bacteria" from matching).
    table_pattern = r"(?<![A-Za-z])(" + "|".join(ranked_keys) + r")__"

    if re.search(embedded_pattern, text):
        return "embedded"
    if re.search(table_pattern, text):
        return "table"
    return None


def parse_taxonomy_auto(
    text: str,
    *,
    mode: str = "reverse",
    sep: str = ";",
    prefixes: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Auto-detect format and parse taxonomy into a unified dict.

    Tries format A (embedded) first, then format B (table/semicolon).

    Args:
        text: Label or taxonomy string.
        mode: Delimiter parsing mode for format A
            (``"reverse"``, ``"greedy"``, ``"segment"``).
        sep: Separator for format B (default ``";"``).
        prefixes: Optional instance-scoped rank-prefix mapping. When
            ``None``, the active module-level configuration is used.

    Returns:
        Dict mapping rank name to value.  Empty string for present-but-
        empty ranks.  Empty dict if no taxonomy detected.
    """
    fmt = detect_taxonomy_format(text, prefixes=prefixes)
    if fmt == "embedded":
        return _parse_taxonomy_embedded(text, mode=mode, prefixes=prefixes)
    if fmt == "table":
        return _parse_taxonomy_string(text, sep=sep, prefixes=prefixes)
    return {}


# Default label patterns for common formats
DEFAULT_PATTERNS = {
    "beast": r"^(?P<id>\d+)_(?P<species>.+)$",
    "genus_species": r"^(?P<genus>[A-Z][a-z]+)_(?P<species>[a-z]+)",
    "binomial": r"^(?P<genus>[A-Z][a-z]+)\s+(?P<species>[a-z]+)",
    "underscore_taxonomy": r"^(?P<phylum>[^_]+)_(?P<class>[^_]+)_(?P<order>[^_]+)",
    "bracket_taxonomy": r"^\[(?P<taxonomy>[^\]]+)\]",
    "paren_taxonomy": r"^\((?P<taxonomy>[^)]+)\)",
}


class TaxonomyMapper:
    """Map taxa to taxonomic groups and identify monophyletic clades.

    This class provides methods to:
    - Parse taxonomy information from node labels using regex patterns
    - Load taxonomy mappings from CSV/TSV files
    - Identify monophyletic groups based on taxonomy
    - Handle incomplete or inconsistent data with warnings

    Args:
        pattern: Regex pattern for parsing taxonomy from labels.
            Pattern should use named groups for taxonomic ranks.
        mapping_file: Path to CSV/TSV file with taxonomy mapping.
        delimiter: Delimiter for mapping file (default: auto-detect).

    Example:
        .. code-block:: python

            # Using built-in pattern
            mapper = TaxonomyMapper(pattern="genus_species")

            # Using custom pattern
            mapper = TaxonomyMapper(pattern=r"^(?P<genus>[A-Z][a-z]+)_(?P<species>[a-z]+)")

            # Using mapping file
            mapper = TaxonomyMapper(mapping_file="taxonomy.csv")

            # Parse labels
            taxonomy = mapper.parse_labels(["Taxon_001", "Taxon_002"])

            # Find monophyletic groups
            groups = mapper.find_monophyletic_groups(tree, taxonomy)
    """

    def __init__(
        self,
        pattern: Optional[str] = None,
        mapping_file: Optional[str] = None,
        delimiter: Optional[str] = None,
        priority: str = "table",
        prefixes: Optional[Dict[str, str]] = None,
    ):
        self._pattern = None
        self._pattern_name = None
        self._mapping = {}
        self._label_taxonomy = {}  # label -> taxonomy dict
        self._priority = priority
        self._warnings = []
        self._parse_warnings = []
        self._identify_warnings = []
        # Instance-scoped rank-prefix configuration. When None, parsing
        # falls back to the module-level configuration (backwards
        # compatible); when provided, this mapper is independent of any
        # set_rank_prefixes() calls in other threads or modules.
        self._prefixes = dict(prefixes) if prefixes is not None else None

        # Set pattern
        if pattern:
            self.set_pattern(pattern)

        # Load mapping file
        if mapping_file:
            self.load_mapping(mapping_file, delimiter)

    def set_pattern(self, pattern: str) -> "TaxonomyMapper":
        """Set regex pattern for parsing taxonomy from labels.

        Args:
            pattern: Regex pattern string with named groups, or name of
                built-in pattern (e.g., "beast", "genus_species").

        Returns:
            self for chaining.

        Example:
            .. code-block:: python

                # Built-in pattern
                mapper.set_pattern("beast")

                # Custom pattern
                mapper.set_pattern(r"^(?P<phylum>[^_]+)_(?P<class>[^_]+)")
        """
        if pattern in DEFAULT_PATTERNS:
            self._pattern_name = pattern
            self._pattern = re.compile(DEFAULT_PATTERNS[pattern])
        else:
            self._pattern_name = "custom"
            try:
                self._pattern = re.compile(pattern)
            except re.error as e:
                raise ValidationError(f"Invalid regex pattern: {e}")

        return self

    def load_mapping(
        self,
        file_path: str,
        delimiter: Optional[str] = None,
        taxonomy_sep: str = ";",
        ignore_malformed: bool = False,
    ) -> "TaxonomyMapper":
        """Load taxonomy mapping from CSV/TSV file.

        Supports two formats:

        **Multi-column format** (one rank per column)::

            taxon,phylum,class,order,family
            Taxon_001,Synthetic,Metazoa,GroupA,FamilyA

        **Two-column format** (taxonomy as a single delimited string with
        rank prefixes like ``d__``, ``p__``, etc.)::

            GB_GCA_000252485.1	d__Bacteria;p__Cyanobacteriota;c__Cyanobacteriia;o__Cyanobacteriales;f__Prochloraceae;g__Prochloron;s__

        The format is auto-detected: if exactly 2 columns and the second
        column contains ``d__``, it is parsed as a taxonomy string.
        Missing ranks (e.g. ``s__`` with no value) are silently skipped.

        Args:
            file_path: Path to mapping file.
            delimiter: Column delimiter. If ``None``, auto-detect from
                file extension (tab for ``.tsv``, comma otherwise).
            taxonomy_sep: Separator within format B taxonomy strings
                (default ``";"``).
            ignore_malformed: If ``True``, skip malformed rows instead
                of raising an error.

        Returns:
            self for chaining.

        Raises:
            ValidationError: If file cannot be read or parsed and
                *ignore_malformed* is ``False``.
        """
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(f"Mapping file not found: {file_path}")

        # Auto-detect delimiter
        if delimiter is None:
            if path.suffix.lower() == ".tsv":
                delimiter = "\t"
            else:
                delimiter = ","

        self._mapping = {}
        self._warnings = []

        try:
            with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.reader(f, delimiter=delimiter)
                header = next(reader, None)

                if header is None or len(header) < 2:
                    raise ValidationError(
                        "Mapping file must have at least 2 columns: taxon and taxonomy"
                    )

                # Detect 2-column taxonomy-string format (e.g. GTDB-style
                # "d__Archaea;p__Thermoproteota;...").  Two cases:
                #   1. No header: first row's col-2 starts with "d__".
                #      That row is data, not a header.
                #   2. Header present (e.g. "name\ttaxonomy"): peek at the
                #      first data row to check.
                first_data_row = None
                is_taxonomy_string_format = False
                _, _, gtdb_prefixes, _ = _build_prefix_maps(self._prefixes)

                if len(header) == 2 and any(
                    header[1].startswith(p) for p in gtdb_prefixes
                ):
                    # Case 1: no header — header IS the first data row
                    is_taxonomy_string_format = True
                    first_data_row = header
                elif len(header) == 2:
                    # Case 2: peek at first data row
                    first_data_row = next(reader, None)
                    if first_data_row and len(first_data_row) >= 2:
                        is_taxonomy_string_format = any(
                            first_data_row[1].startswith(p)
                            for p in gtdb_prefixes
                        )

                if is_taxonomy_string_format:
                    self._load_mapping_taxonomy_string(
                        reader, first_data_row,
                        sep=taxonomy_sep, ignore_malformed=ignore_malformed,
                    )
                else:
                    self._load_mapping_multi_column(header, reader)

        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Error reading mapping file: {e}")

        # Check for circular dependencies (§13: must be ERROR, refuse to load)
        from .validators import detect_taxonomy_circular_deps
        rows = [(name, tax) for name, tax in self._mapping.items()]
        circular = detect_taxonomy_circular_deps(rows)
        if circular:
            raise ValidationError(
                "Circular dependency detected in taxonomy mapping:\n"
                + "\n".join(circular)
            )

        return self

    def _load_mapping_taxonomy_string(
        self,
        reader: Any,
        first_data_row: Optional[List[str]] = None,
        sep: str = ";",
        ignore_malformed: bool = False,
    ) -> None:
        """Load mapping from 2-column format with taxonomy strings.

        Args:
            reader: CSV reader for remaining rows.
            first_data_row: If the file has no header, this is the first
                data row (which was read as the header).
            sep: Separator within taxonomy strings.
            ignore_malformed: If True, skip malformed rows.
        """
        start_line = 2

        if first_data_row is not None:
            taxon = first_data_row[0].strip()
            try:
                taxonomy = _parse_taxonomy_string(first_data_row[1], sep=sep, prefixes=self._prefixes)
            except ValidationError as e:
                if ignore_malformed:
                    self._warnings.append(f"Line 1: {e}")
                    taxonomy = {}
                else:
                    raise
            if taxonomy:
                self._mapping[taxon] = taxonomy
            else:
                self._warnings.append(
                    f"Line 1: No taxonomy data for '{taxon}'"
                )
            start_line = 3

        for line_num, row in enumerate(reader, start=start_line):
            if len(row) < 2:
                self._warnings.append(
                    f"Line {line_num}: Insufficient columns, skipped"
                )
                continue

            taxon = row[0].strip()
            try:
                taxonomy = _parse_taxonomy_string(row[1], sep=sep, prefixes=self._prefixes)
            except ValidationError as e:
                if ignore_malformed:
                    self._warnings.append(f"Line {line_num}: {e}")
                    continue
                else:
                    raise

            if taxonomy:
                self._mapping[taxon] = taxonomy
            else:
                self._warnings.append(
                    f"Line {line_num}: No taxonomy data for '{taxon}'"
                )

    def _load_mapping_multi_column(
        self, header: List[str], reader: Any
    ) -> None:
        """Load mapping from multi-column format (one rank per column)."""
        rank_names = [h.strip() for h in header[1:]]

        for line_num, row in enumerate(reader, start=2):
            if len(row) < 2:
                self._warnings.append(
                    f"Line {line_num}: Insufficient columns, skipped"
                )
                continue

            taxon = row[0].strip()
            taxonomy = {}
            for i, rank in enumerate(rank_names):
                if i + 1 < len(row):
                    value = row[i + 1].strip()
                    if value:
                        taxonomy[rank] = value

            if taxonomy:
                self._mapping[taxon] = taxonomy
            else:
                self._warnings.append(
                    f"Line {line_num}: No taxonomy data for '{taxon}'"
                )

    def parse_labels(
        self,
        labels: List[str],
        mode: str = "reverse",
        sep: str = ";",
    ) -> Dict[str, Dict[str, str]]:
        """Parse taxonomy information from node labels.

        If a regex pattern is set, uses that.  Otherwise falls back to
        :func:`parse_taxonomy_auto` which auto-detects embedded (format A)
        and table (format B) markers in each label.

        Args:
            labels: List of node labels to parse.
            mode: Parsing strategy for embedded taxonomy labels
                (``"reverse"``, ``"greedy"``, or ``"segment"``).
            sep: Separator for table-style (format B) taxonomy strings.

        Returns:
            Dictionary mapping label to taxonomy dict.
            Labels that cannot be parsed will have empty dict.

        Example:
            .. code-block:: python

                mapper = TaxonomyMapper(pattern="genus_species")
                taxonomy = mapper.parse_labels(["Taxon_001", "Taxon_002"])
                # Returns: {"Taxon_001": {"genus": "Taxon", "species": "001"}, ...}
        """
        result = {}
        self._parse_warnings = []

        if self._pattern is not None:
            for label in labels:
                match = self._pattern.match(label)
                if match:
                    result[label] = {k: v for k, v in match.groupdict().items() if v}
                else:
                    result[label] = {}
                    self._parse_warnings.append(
                        f"Label '{label}' does not match pattern"
                    )
        else:
            # Auto-detect mode: try embedded then table markers
            for label in labels:
                tax = parse_taxonomy_auto(label, mode=mode, sep=sep, prefixes=self._prefixes)
                if tax:
                    result[label] = tax
                else:
                    result[label] = {}

        self._label_taxonomy.update(result)
        return result

    def get_taxonomy(self, label: str, priority: Optional[str] = None) -> Dict[str, str]:
        """Get taxonomy for a label from all available sources.

        Args:
            label: Taxon label.
            priority: Which source takes precedence when both exist
                for the same label — ``"table"`` (default) or ``"embedded"``.
                If ``None``, uses the mapper's configured priority.

        Returns:
            Merged taxonomy dict, or empty dict if not found.
        """
        if priority is None:
            priority = self._priority
        has_embedded = label in self._label_taxonomy
        has_mapping = label in self._mapping

        if has_embedded and has_mapping:
            if priority == "embedded":
                merged = dict(self._mapping[label])
                merged.update(self._label_taxonomy[label])
            else:
                merged = dict(self._label_taxonomy[label])
                merged.update(self._mapping[label])
            return merged

        if has_mapping:
            return dict(self._mapping[label])

        if has_embedded:
            return dict(self._label_taxonomy[label])

        return {}

    def identify_groups(
        self,
        labels: List[str],
        rank: str = "genus",
    ) -> Dict[str, List[str]]:
        """Identify taxonomic groups based on a specific rank.

        Args:
            labels: List of taxon labels.
            rank: Taxonomic rank to group by (e.g., "genus", "family").

        Returns:
            Dictionary mapping group name to list of labels.

        Example:
            .. code-block:: python

                mapper = TaxonomyMapper(pattern="genus_species")
                groups = mapper.identify_groups(labels, rank="genus")
                # Returns: {"Taxon": ["Taxon_001", "Taxon_002", "Taxon_003"]}
        """
        groups = {}
        unmapped = []

        for label in labels:
            taxonomy = self.get_taxonomy(label)
            if taxonomy and rank in taxonomy:
                group = taxonomy[rank]
                if group not in groups:
                    groups[group] = []
                groups[group].append(label)
            else:
                unmapped.append(label)

        if unmapped:
            self._identify_warnings.append(
                f"{len(unmapped)} labels have no '{rank}' taxonomy: "
                + ", ".join(unmapped[:5])
                + ("..." if len(unmapped) > 5 else "")
            )

        return groups

    def check_completeness(
        self,
        labels: List[str],
        required_ranks: Optional[List[str]] = None,
    ) -> dict:
        """Check completeness of taxonomy data.

        Args:
            labels: List of taxon labels.
            required_ranks: List of required taxonomic ranks.
                If None, checks all available ranks.

        Returns:
            Dictionary with:
                - ``complete`` (list): Labels with complete taxonomy.
                - ``incomplete`` (list): Labels with incomplete taxonomy.
                - ``missing`` (list): Labels with no taxonomy data.
                - ``coverage`` (float): Percentage of labels with any taxonomy.
                - ``rank_coverage`` (dict): Coverage per rank.
        """
        complete = []
        incomplete = []
        missing = []
        rank_counts = {}

        for label in labels:
            taxonomy = self.get_taxonomy(label)

            if not taxonomy:
                missing.append(label)
                continue

            # Check required ranks
            if required_ranks:
                missing_ranks = [r for r in required_ranks if r not in taxonomy]
                if missing_ranks:
                    incomplete.append(label)
                else:
                    complete.append(label)
            else:
                complete.append(label)

            # Count ranks
            for rank in taxonomy:
                rank_counts[rank] = rank_counts.get(rank, 0) + 1

        total = len(labels)
        rank_coverage = {
            rank: count / total * 100 if total > 0 else 0
            for rank, count in rank_counts.items()
        }

        return {
            "complete": complete,
            "incomplete": incomplete,
            "missing": missing,
            "coverage": len(complete) / total * 100 if total > 0 else 0,
            "rank_coverage": rank_coverage,
        }

    def validate_mapping_against_tree(
        self, tree_labels: List[str]
    ) -> Dict[str, object]:
        """Check consistency between mapping file labels and tree tips.

        Args:
            tree_labels: List of terminal taxon labels from the tree.

        Returns:
            Dictionary with:
                - ``extra_in_table`` (list): Labels in mapping but not in tree.
                - ``missing_from_table`` (list): Tree labels not in mapping
                  and not parseable from label.
                - ``warnings`` (list): Warning messages.
        """
        tree_set = set(tree_labels)
        table_set = set(self._mapping.keys())
        parsed_set = set(self._label_taxonomy.keys())

        extra_in_table = sorted(table_set - tree_set)
        # Missing = not in mapping AND not successfully parsed from label
        missing = sorted(tree_set - table_set - parsed_set)

        warns: List[str] = []
        if extra_in_table:
            warns.append(
                f"{len(extra_in_table)} label(s) in mapping file not found "
                f"in tree: {', '.join(extra_in_table[:5])}"
                + ("..." if len(extra_in_table) > 5 else "")
            )

        return {
            "extra_in_table": extra_in_table,
            "missing_from_table": missing,
            "warnings": warns,
        }

    def get_warnings(self) -> List[str]:
        """Get list of warnings from all operations."""
        return self._warnings + self._parse_warnings + self._identify_warnings

    def resolve_taxon_group(
        self,
        labels: List[str],
        group_name: str,
    ) -> List[str]:
        """Resolve a taxon group name to a list of terminal taxa.

        Searches all parsed labels for taxa whose taxonomy at **any** rank
        matches *group_name*.  Also handles the special identifiers
        ``LUCA``, ``LACA``, ``LBCA`` (uppercase only), and ``root``.

        Args:
            labels: List of all terminal taxon labels in the tree.
            group_name: Taxon group name (e.g. ``"Bacteria"``,
                ``"Cyanobacteriales"``) or special identifier
                (``"LUCA"``, ``"LACA"``, ``"LBCA"``, ``"root"``).

        Returns:
            List of taxon labels belonging to the group.

        Raises:
            ValidationError: If *group_name* is not found in any taxon.
        """
        # The domain rank name is configurable (see get_domain_rank_name);
        # resolve it once so both the special-identifier path and the
        # error message below stay consistent with the active rank config.
        domain_rank = get_domain_rank_name()

        # Special identifiers are matched case-insensitively (LUCA == luca).
        group_upper = group_name.strip().upper()
        if group_upper in _SPECIAL_IDS_UPPER:
            info = SPECIAL_IDENTIFIERS[group_upper]
            domains = info["domains"]
            matched = []
            for label in labels:
                taxonomy = self.get_taxonomy(label)
                if not taxonomy:
                    continue
                domain_val = taxonomy.get(domain_rank, "")
                # Case-insensitive, trimmed domain comparison for tolerance.
                domain_norm = domain_val.strip().lower()
                if any(domain_norm == d.strip().lower() for d in domains):
                    matched.append(label)
            if not matched:
                raise ValidationError(
                    f"Special identifier '{group_name}' resolved to zero taxa. "
                    f"Searched for domain(s): {domains}"
                )
            return matched

        if group_name.strip().lower() == "root":
            return list(labels)

        # Search all ranks for a match.  Group matching is case-insensitive
        # (matching the special-identifier path above): a user-supplied
        # "Cyanobacteriales" should match a taxonomy value "cyanobacteriales".
        target = group_name.strip().lower()
        matched = []
        for label in labels:
            taxonomy = self.get_taxonomy(label)
            if not taxonomy:
                continue
            for rank in _TAXONOMY_RANKS:
                val = taxonomy.get(rank, "")
                if val and val.strip().lower() == target:
                    matched.append(label)
                    break

        if not matched:
            # Collect the set of distinct domain values actually present so
            # the user gets an actionable diagnostic.
            available_domains: Set[str] = set()
            for label in labels:
                tax = self.get_taxonomy(label)
                domain_val = tax.get(domain_rank, "") if tax else ""
                if domain_val:
                    available_domains.add(domain_val)
            raise ValidationError(
                f"Taxon group '{group_name}' not found in any label's taxonomy. "
                f"Available {domain_rank}s: {sorted(available_domains)}"
            )
        return matched


class MonophylyAnalyzer:
    """Analyze monophyly of taxonomic groups in phylogenetic trees.

    This class combines taxonomy mapping with tree analysis to
    identify monophyletic groups and report issues.

    Args:
        mapper: TaxonomyMapper instance for taxonomy resolution.

    Example:
        .. code-block:: python

            mapper = TaxonomyMapper(mapping_file="taxonomy.csv")
            analyzer = MonophylyAnalyzer(mapper)

            # Analyze all groups at genus level
            results = analyzer.analyze_tree(tree, rank="genus")

            # Get monophyletic groups
            mono = results["monophyletic"]

            # Get non-monophyletic groups with issues
            issues = results["non_monophyletic"]
    """

    def __init__(self, mapper: TaxonomyMapper):
        self._mapper = mapper
        self._warnings = []

    def analyze_tree(
        self,
        tree: Any,
        rank: str = "genus",
        labels: Optional[List[str]] = None,
    ) -> dict:
        """Analyze monophyly of all groups at specified rank.

        Args:
            tree: Bio.Phylo Tree object.
            rank: Taxonomic rank to analyze.
            labels: Optional list of labels to analyze.
                If None, uses all terminal labels from tree.

        Returns:
            Dictionary with:
                - ``monophyletic`` (dict): Group name -> clade info.
                - ``non_monophyletic`` (dict): Group name -> issue details.
                - ``unmapped`` (list): Labels with no taxonomy.
                - ``summary`` (dict): Summary statistics.
        """
        if tree is None:
            raise ValueError(
                "Cannot analyze monophyly: no tree has been loaded."
            )

        # Get labels from tree if not provided
        if labels is None:
            labels = [t.name for t in tree.get_terminals() if t.name]

        # Identify groups
        groups = self._mapper.identify_groups(labels, rank)

        monophyletic = {}
        non_monophyletic = {}
        self._warnings = []
        single_taxon_count = 0

        for group_name, group_labels in groups.items():
            if len(group_labels) < 2:
                # Single taxon cannot be monophyletic group
                single_taxon_count += 1
                monophyletic[group_name] = {
                    "taxa": group_labels,
                    "type": "single_taxon",
                    "mrca_found": True,
                }
                continue

            # Check monophyly using tree
            result = self._check_group_monophyly(tree, group_labels)

            if result["is_monophyletic"]:
                monophyletic[group_name] = {
                    "taxa": group_labels,
                    "type": "monophyletic",
                    "mrca_found": True,
                    "mrca_terminals": result["mrca_terminals"],
                    "clade_size": result.get("clade_size", 0),
                }
            else:
                non_monophyletic[group_name] = {
                    "taxa": group_labels,
                    "type": "non_monophyletic",
                    "mrca_found": result["mrca_found"],
                    "mrca_terminals": result["mrca_terminals"],
                    "intruder_taxa": result["intruder_taxa"],
                    "extra_taxa": result["extra_taxa"],
                }
                self._warnings.append(
                    f"Group '{group_name}' is not monophyletic. "
                    f"Intruders: {result['intruder_taxa']}"
                )

        # Get unmapped labels
        mapped_labels = set()
        for group_labels in groups.values():
            mapped_labels.update(group_labels)
        unmapped = [l for l in labels if l not in mapped_labels]

        # Summary
        total_groups = len(groups)
        mono_count = len(monophyletic)
        non_mono_count = len(non_monophyletic)
        # A single-taxon "group" is trivially mono but provides no signal;
        # exclude single-taxon groups from the monophyly rate denominator.
        comparable_groups = total_groups - single_taxon_count

        summary = {
            "total_labels": len(labels),
            "mapped_labels": len(mapped_labels),
            "unmapped_labels": len(unmapped),
            "total_groups": total_groups,
            "single_taxon_groups": single_taxon_count,
            "monophyletic": mono_count,
            "non_monophyletic": non_mono_count,
            "monophyly_rate": (
                mono_count / comparable_groups * 100
                if comparable_groups > 0 else 0
            ),
        }

        return {
            "monophyletic": monophyletic,
            "non_monophyletic": non_monophyletic,
            "unmapped": unmapped,
            "summary": summary,
        }

    def _check_group_monophyly(
        self, tree: Any, group_labels: List[str]
    ) -> dict:
        """Check if a group of taxa is monophyletic.

        Returns a dict with:
            - ``is_monophyletic`` (bool)
            - ``mrca_found`` (bool)
            - ``mrca_terminals`` (list): all terminal names under the MRCA
            - ``intruder_taxa`` (list): terminals under the MRCA that are
              **not** part of the target group (they break monophyly)
            - ``extra_taxa`` (list): target taxa that are **not** under the
              MRCA (could not be located)
            - ``clade_size`` (int): number of terminals under the MRCA
        """
        try:
            # Find MRCA.  Bio.Phylo raises ValueError when a target taxon is
            # absent; the except clause below converts that into a
            # structured mrca_found=False result, so no None check is needed.
            mrca = tree.common_ancestor(*group_labels)

            mrca_terminal_names = [t.name for t in mrca.get_terminals()]
            target_set = set(group_labels)
            mrca_set = set(mrca_terminal_names)

            is_monophyletic = (mrca_set == target_set)
            # Terminals under MRCA but outside the group are "intruders"
            # (they break monophyly); group taxa missing from the MRCA are
            # "extra" (could not be placed).
            intruders = list(mrca_set - target_set)
            extra = list(target_set - mrca_set)

            return {
                "is_monophyletic": is_monophyletic,
                "mrca_found": True,
                "mrca_terminals": mrca_terminal_names,
                "intruder_taxa": intruders,
                "extra_taxa": extra,
                "clade_size": len(mrca_terminal_names),
            }

        except (ValueError, AttributeError, KeyError) as e:
            self._warnings.append(f"Monophyly check failed for {group_labels}: {e}")
            return {
                "is_monophyletic": False,
                "mrca_found": False,
                "mrca_terminals": [],
                "intruder_taxa": list(group_labels),
                "extra_taxa": [],
                "clade_size": 0,
            }

    def get_warnings(self) -> List[str]:
        """Get list of warnings from last analysis."""
        return self._warnings.copy()

    def check_monophyly_by_group(
        self,
        tree: Any,
        group_name: str,
        labels: Optional[List[str]] = None,
    ) -> dict:
        """Check monophyly of a taxon group identified by name.

        Resolves *group_name* to a list of terminal taxa via the mapper,
        then checks whether those taxa form a monophyletic group.
        Supports special identifiers ``LUCA``, ``LACA``, and ``LBCA``.

        Args:
            tree: Bio.Phylo Tree object.
            group_name: Taxon group name (e.g. ``"Bacteria"``,
                ``"Cyanobacteriales"``) or special identifier
                (``"LUCA"``, ``"LACA"``, ``"LBCA"``).
            labels: Optional list of all terminal labels.
                If ``None``, uses all terminal labels from *tree*.

        Returns:
            Dictionary with:
                - ``group_name`` (str): The requested group name.
                - ``resolved_taxa`` (list): Taxa that belong to the group.
                - ``is_monophyletic`` (bool): Whether the group is monophyletic.
                - ``mrca_found`` (bool): Whether MRCA was found.
                - ``mrca_terminals`` (list): All terminals under the MRCA.
                - ``intruder_taxa`` (list): Taxa under the MRCA that are NOT
                  in the requested group (they break monophyly).
                - ``extra_taxa`` (list): Taxa in the group not under the MRCA.
                - ``warning`` (str or None): Warning message if not monophyletic.

        Raises:
            ValidationError: If *group_name* cannot be resolved to any taxon.
        """
        self._warnings = []

        if tree is None:
            raise ValueError(
                "Cannot check monophyly: no tree has been loaded."
            )

        if labels is None:
            labels = [t.name for t in tree.get_terminals() if t.name]

        # Resolve group name to taxa
        resolved = self._mapper.resolve_taxon_group(labels, group_name)

        result: Dict[str, Any] = {
            "group_name": group_name,
            "resolved_taxa": resolved,
            "is_monophyletic": False,
            "mrca_found": False,
            "mrca_terminals": [],
            "intruder_taxa": [],
            "extra_taxa": [],
            "warning": None,
        }

        if len(resolved) < 1:
            result["warning"] = f"Group '{group_name}' resolved to zero taxa."
            return result

        if len(resolved) == 1:
            result["is_monophyletic"] = True
            result["mrca_found"] = True
            result["mrca_terminals"] = resolved
            return result

        mono_result = self._check_group_monophyly(tree, resolved)
        result.update({
            "is_monophyletic": mono_result["is_monophyletic"],
            "mrca_found": mono_result["mrca_found"],
            "mrca_terminals": mono_result["mrca_terminals"],
            "intruder_taxa": mono_result["intruder_taxa"],
            "extra_taxa": mono_result["extra_taxa"],
        })

        if not mono_result["is_monophyletic"]:
            result["warning"] = (
                f"'{group_name}' is not a monophyletic group. "
                f"The MRCA also contains: {mono_result['intruder_taxa']}"
            )

        return result

    def generate_report(self, analysis_result: dict) -> str:
        """Generate human-readable report from analysis result.

        Args:
            analysis_result: Result from analyze_tree().

        Returns:
            Formatted report string.
        """
        lines = []
        summary = analysis_result["summary"]

        lines.append("=" * 60)
        lines.append("Monophyly Analysis Report")
        lines.append("=" * 60)
        lines.append("")

        # Summary
        lines.append("Summary:")
        lines.append(f"  Total labels: {summary['total_labels']}")
        lines.append(f"  Mapped labels: {summary['mapped_labels']}")
        lines.append(f"  Unmapped labels: {summary['unmapped_labels']}")
        lines.append(f"  Total groups: {summary['total_groups']}")
        lines.append(f"  Monophyletic: {summary['monophyletic']}")
        lines.append(f"  Non-monophyletic: {summary['non_monophyletic']}")
        lines.append(f"  Monophyly rate: {summary['monophyly_rate']:.1f}%")
        lines.append("")

        # Monophyletic groups
        if analysis_result["monophyletic"]:
            lines.append("Monophyletic Groups:")
            for name, info in analysis_result["monophyletic"].items():
                if info["type"] == "single_taxon":
                    lines.append(f"  {name}: Single taxon ({info['taxa'][0]})")
                else:
                    lines.append(
                        f"  {name}: {len(info['taxa'])} taxa, "
                        f"{info.get('clade_size', '?')} nodes"
                    )
            lines.append("")

        # Non-monophyletic groups
        if analysis_result["non_monophyletic"]:
            lines.append("Non-Monophyletic Groups:")
            for name, info in analysis_result["non_monophyletic"].items():
                lines.append(f"  {name}:")
                lines.append(f"    Input taxa: {info['taxa']}")
                lines.append(f"    MRCA terminals: {info['mrca_terminals']}")
                if info["intruder_taxa"]:
                    lines.append(f"    Intruders (in MRCA but not input): {info['intruder_taxa']}")
                if info["extra_taxa"]:
                    lines.append(f"    Extra (in input but not MRCA): {info['extra_taxa']}")
            lines.append("")

        # Unmapped labels
        if analysis_result["unmapped"]:
            lines.append("Unmapped Labels:")
            for label in analysis_result["unmapped"][:10]:
                lines.append(f"  - {label}")
            if len(analysis_result["unmapped"]) > 10:
                lines.append(f"  ... and {len(analysis_result['unmapped']) - 10} more")
            lines.append("")

        # Warnings
        warnings = self.get_warnings()
        if warnings:
            lines.append("Warnings:")
            for w in warnings[:10]:
                lines.append(f"  - {w}")
            if len(warnings) > 10:
                lines.append(f"  ... and {len(warnings) - 10} more")

        lines.append("=" * 60)
        return "\n".join(lines)
