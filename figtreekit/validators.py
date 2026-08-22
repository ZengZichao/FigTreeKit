# SPDX-License-Identifier: GPL-2.0-or-later
# This file is part of FigTreeKit; see LICENSE and NOTICE for licensing terms.
"""Validation utilities for phylogenetic tree data and FigTree settings."""

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

import bisect
import os
import re
import warnings
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple, Union

from ._parser import strip_square_bracket_comments
from .exceptions import ValidationError


TREE_EXTENSIONS = {
    '.newick', '.nwk', '.tree', '.tre', '.treefile',
    '.nexus', '.nex', '.nx',
    '.phyloxml', '.xml',
    '.nh', '.nhy',
}

SEQUENCE_EXTENSIONS = {
    '.fasta', '.fa', '.fas', '.fna', '.faa', '.ffn', '.frn',
    '.fastq', '.fq',
    '.gb', '.gbk', '.genbank',
    '.embl',
    '.stockholm', '.sto',
    '.phylip', '.phy',
    '.clustal', '.aln',
}

ALL_KNOWN_EXTENSIONS = TREE_EXTENSIONS | SEQUENCE_EXTENSIONS

_EXT_FORMAT_MAP = {
    '.newick': 'newick', '.nwk': 'newick', '.tree': 'newick',
    '.tre': 'newick', '.treefile': 'newick', '.nh': 'newick', '.nhy': 'newick',
    '.nexus': 'nexus', '.nex': 'nexus', '.nx': 'nexus',
    '.phyloxml': 'phyloxml', '.xml': 'phyloxml',
    '.fasta': 'fasta', '.fa': 'fasta', '.fas': 'fasta', '.fna': 'fasta',
    '.faa': 'fasta', '.ffn': 'fasta', '.frn': 'fasta',
    '.fastq': 'fastq', '.fq': 'fastq',
    '.gb': 'genbank', '.gbk': 'genbank', '.genbank': 'genbank',
    '.embl': 'embl',
    '.stockholm': 'stockholm', '.sto': 'stockholm',
    '.phylip': 'phylip', '.phy': 'phylip',
    '.clustal': 'clustal', '.aln': 'clustal',
}


class TreeValidator:
    """Validator for phylogenetic tree data and FigTree settings.

    Provides static methods for validating colors, taxon names, font styles,
    and file format strings before they are processed or exported.
    """

    @staticmethod
    def validate_color(color: str) -> bool:
        """Validate a hex color string.

        Accepts standard 6-digit hex (``#RRGGBB``) and FigTree's old-style
        decimal format (``#-16711681``).

        Args:
            color: Color string to validate (e.g., ``"#FF0000"``).

        Returns:
            ``True`` if valid, ``False`` otherwise.

        Examples:
            >>> TreeValidator.validate_color("#FF0000")
            True
            >>> TreeValidator.validate_color("red")
            False
            >>> TreeValidator.validate_color("#-16711681")
            True
        """
        if not isinstance(color, str):
            return False
        if re.match(r'^#[0-9A-Fa-f]{6}$', color):
            return True
        if re.match(r'^#-\d+$', color):
            val = int(color[1:])
            # Java RGB range: -2^24 to 2^24-1
            return -16777216 <= val <= 16777215
        return False

    @staticmethod
    def validate_taxon_names(taxon_names: Union[List[str], Sequence[str]]) -> bool:
        """Validate a list of taxon names.

        Args:
            taxon_names: List or tuple of taxon names to validate.

        Returns:
            ``True`` if the list is non-empty and all names are non-empty strings.
        """
        if not isinstance(taxon_names, (list, tuple)):
            return False
        if len(taxon_names) == 0:
            return False
        for name in taxon_names:
            if not isinstance(name, str) or len(name.strip()) == 0:
                return False
        return True

    @staticmethod
    def validate_font_style(font_style: int) -> bool:
        """Validate a font style integer.

        Args:
            font_style: Font style code (0=plain, 1=bold, 2=italic, 3=bold italic).

        Returns:
            ``True`` if in range [0, 3].
        """
        return isinstance(font_style, int) and 0 <= font_style <= 3

    @staticmethod
    def validate_newick(newick: str) -> bool:
        """Basic validation of a Newick format string.

        Checks bracket balance and trailing semicolon. Does **not** validate
        full Newick grammar — use Bio.Phylo for complete parsing.

        Args:
            newick: Newick string to validate.

        Returns:
            ``True`` if the string appears structurally valid.
        """
        if not isinstance(newick, str):
            return False
        newick = newick.strip()
        if not newick:
            return False
        if newick.count('(') != newick.count(')'):
            return False
        if newick.count('[') != newick.count(']'):
            return False
        if not newick.endswith(';'):
            return False
        return True

    @staticmethod
    def validate_nexus(content: str) -> bool:
        """Basic validation of a Nexus format string.

        Checks for ``#NEXUS`` header and at least one ``begin ... end;`` block.

        Args:
            content: Nexus content to validate.

        Returns:
            ``True`` if the string appears structurally valid.
        """
        if not isinstance(content, str):
            return False
        content_upper = content.upper().strip()
        if not content_upper.startswith('#NEXUS'):
            return False
        collapsed = re.sub(r'\s+', ' ', content_upper)
        if not re.search(r'\bBEGIN\b.*?\bEND\s*;', collapsed):
            return False
        return True

    @staticmethod
    def validate_biological_plausibility(
        newick: str,
        max_taxa_warning_threshold: int = 10000,
    ) -> List[str]:
        """Check for biologically implausible tree structures.

        Unlike :meth:`validate_newick` (which checks syntactic validity),
        this method emits advisory warnings for trees that are technically
        valid but may produce misleading or empty visualizations.

        Args:
            newick: Newick string to check.
            max_taxa_warning_threshold: Taxa count threshold for large tree
                warning. Default is 10000. Set to 0 to disable the warning.

        Returns:
            List of warning message strings. Empty list means no issues.
        """
        issues: List[str] = []
        if not isinstance(newick, str) or not newick.strip():
            return issues

        # Check for single taxon (degenerate tree)
        stripped = newick.strip().rstrip(';').strip()
        if stripped and '(' not in stripped:
            issues.append(
                "Tree contains a single taxon — this is degenerate and "
                "will produce an uninformative visualization."
            )

        # Check for all-zero branch lengths
        branch_lengths = re.findall(r':([\d.eE+-]+)', newick)
        if branch_lengths:
            parsed_lengths: List[float] = []
            malformed = False
            for b in branch_lengths:
                if not b:
                    continue
                try:
                    parsed_lengths.append(float(b))
                except ValueError:
                    # Unparseable branch length (e.g. a dangling "e"); treat
                    # the all-zero check as untrusted rather than crashing.
                    warnings.warn(
                        f"Unparseable branch length '{b}' in Newick string; "
                        f"skipping all-zero branch-length check.",
                        stacklevel=2,
                    )
                    malformed = True
                    break
            if not malformed and parsed_lengths and all(
                abs(v) < 1e-15 for v in parsed_lengths
            ):
                issues.append(
                    "All branch lengths are zero or near-zero — the tree will "
                    "render as a single point in FigTree."
                )

        # Count taxa to warn about very large trees.
        # NOTE: validate_biological_plausibility only receives the raw Newick
        # string — callers (e.g. FigTreeStyler.load_content) do not pass a
        # pre-parsed tree — so we deliberately re-parse here via
        # extract_taxa_from_newick. This is a full Bio.Phylo parse, but it is
        # the canonical, edge-case-safe way to enumerate terminal taxa (with a
        # regex fallback). If a caller already holds a parsed tree it should
        # pass the taxon list in instead to avoid the redundant parse (future
        # refactor). The cost is acceptable because load_content caches the
        # parsed tree for subsequent export.
        if max_taxa_warning_threshold > 0:
            from ._parser import extract_taxa_from_newick
            taxa = extract_taxa_from_newick(newick)
            taxa_count = len(taxa)

            if taxa_count > max_taxa_warning_threshold:
                issues.append(
                    f"Tree has approximately {taxa_count} taxa — FigTree's Java "
                    f"renderer may exhaust memory on very large trees."
                )

        return issues


def _detect_format_by_content(content: str) -> Optional[str]:
    """Detect file format by inspecting content.

    Returns:
        Format string (e.g. ``"newick"``, ``"nexus"``, ``"fasta"``, ...) or
        ``None`` if the format cannot be determined.
    """
    stripped = content.lstrip()
    if not stripped:
        return None

    upper = stripped.upper()

    # Nexus
    if upper.startswith('#NEXUS'):
        return 'nexus'

    # PhyloXML
    if stripped.startswith('<?xml') and '<phyloxml' in upper:
        return 'phyloxml'

    # FASTA
    if stripped.startswith('>'):
        return 'fasta'

    # FASTQ — requires @ header AND a separate '+' line with a quality header.
    # Must NOT match FASTA files whose sequence lines happen to start with '@'.
    if stripped.startswith('@'):
        lines = content[:4096].split('\n')
        for i, line in enumerate(lines):
            if i > 0 and line.startswith('+'):
                rest = line[1:].strip()
                if not rest or rest == lines[0].lstrip('@').strip():
                    return 'fastq'

    # GenBank
    if upper.startswith('LOCUS ') or upper.startswith('ID   '):
        return 'genbank'

    # EMBL
    if upper.startswith('ID   ') and 'SQ ' in content[:8192]:
        return 'embl'

    # Stockholm
    if upper.startswith('# STOCKHOLM') or upper.startswith('#STOCKHOLM'):
        return 'stockholm'

    # Clustal
    if upper.startswith('CLUSTAL'):
        return 'clustal'

    # Phylip — starts with integer (ntax) then whitespace then another integer
    if re.match(r'^\d+\s+\d+', stripped):
        return 'phylip'

    # Newick — must contain parentheses and end with semicolon
    if '(' in stripped and stripped.rstrip().endswith(';'):
        return 'newick'

    return None


def validate_input_file(
    file_path: str,
    expected_format: Optional[str] = None,
) -> Dict[str, object]:
    """Validate an input file for existence, readability, and format.

    Checks (in order):
      1. Path exists and is a regular file.
      2. File is not empty.
      3. File is readable (permission check).
      4. Format is detected from extension and/or content.
      5. Content is structurally valid for the detected format.

    Args:
        file_path: Path to the input file.
        expected_format: If provided, assert the file matches this format.
            Use format names like ``"newick"``, ``"nexus"``, ``"fasta"``,
            ``"phyloxml"``, etc.

    Returns:
        Dictionary with:
            - ``valid`` (bool): Whether the file passed all checks.
            - ``path`` (str): Absolute path.
            - ``format`` (str or None): Detected format name.
            - ``extension`` (str): File extension.
            - ``size_bytes`` (int): File size.
            - ``errors`` (list): Fatal error messages (empty if valid).
            - ``warnings`` (list): Advisory warnings.

    Example:
        .. code-block:: python

            result = validate_input_file("tree.nwk")
            if not result["valid"]:
                for err in result["errors"]:
                    print(err)
    """
    result: Dict[str, object] = {
        "valid": True,
        "path": os.path.abspath(file_path),
        "format": None,
        "extension": "",
        "size_bytes": 0,
        "errors": [],
        "warnings": [],
    }
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    warns: List[str] = result["warnings"]  # type: ignore[assignment]

    path = Path(file_path)

    # --- 1. Existence ---
    if not path.exists():
        errors.append(f"File not found: {file_path}")
        result["valid"] = False
        return result

    # --- 2. Is file ---
    if not path.is_file():
        errors.append(f"Path is not a regular file: {file_path}")
        result["valid"] = False
        return result

    ext = path.suffix.lower()
    result["extension"] = ext  # type: ignore[assignment]

    # --- 3. Size ---
    try:
        size = path.stat().st_size
    except OSError as e:
        errors.append(f"Cannot stat file: {e}")
        result["valid"] = False
        return result

    result["size_bytes"] = size  # type: ignore[assignment]
    if size == 0:
        errors.append(f"File is empty: {file_path}")
        result["valid"] = False
        return result

    # --- 4. Readability ---
    if not os.access(file_path, os.R_OK):
        errors.append(f"File is not readable (permission denied): {file_path}")
        result["valid"] = False
        return result

    # --- 5. Format detection ---
    detected_format: Optional[str] = None

    # Try extension first
    if ext in _EXT_FORMAT_MAP:
        detected_format = _EXT_FORMAT_MAP[ext]
    elif ext in ALL_KNOWN_EXTENSIONS:
        detected_format = ext.lstrip('.')

    # Try content-based detection.  Read only the HEAD (first 8 KiB) so we
    # never load a multi-GB file into memory just to sniff its format; the
    # streaming malware scan below bounds memory independently.
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(8192)
    except (OSError, UnicodeDecodeError) as e:
        errors.append(f"Cannot read file content: {e}")
        result["valid"] = False
        return result
    content_format = _detect_format_by_content(head)

    # Resolve conflicts / confirm
    if content_format:
        if detected_format and detected_format != content_format:
            warns.append(
                f"Extension suggests '{detected_format}' but content "
                f"looks like '{content_format}'. Using content-based detection."
            )
        detected_format = content_format
    elif not detected_format:
        warns.append(
            f"Unrecognized file extension '{ext}' and content format "
            f"could not be determined."
        )

    result["format"] = detected_format  # type: ignore[assignment]

    # --- 6. Early anomalous content scan (streaming, bounded memory) ---
    mal_errors = scan_for_anomalous_content_stream(
        file_path, label=file_path,
    )
    errors.extend(mal_errors)

    # --- 7. Format-specific validation ---
    if detected_format == 'newick':
        _validate_newick_file(file_path, result, content=None)
    elif detected_format == 'nexus':
        _validate_nexus_file(file_path, result)
    elif detected_format == 'phyloxml':
        _validate_phyloxml_file(file_path, result)
    elif detected_format == 'fasta':
        _validate_fasta_file(file_path, result)
    elif detected_format == 'fastq':
        _validate_fastq_file(file_path, result)
    elif detected_format in ('genbank', 'embl'):
        _validate_flatfile(file_path, result)
    elif detected_format == 'phylip':
        _validate_phylip_file(file_path, result)
    elif detected_format == 'stockholm':
        _validate_stockholm_file(file_path, result)
    elif detected_format == 'clustal':
        _validate_clustal_file(file_path, result)

    # --- 8. Expected format check ---
    if expected_format and detected_format and detected_format != expected_format:
        errors.append(
            f"Expected format '{expected_format}' but detected '{detected_format}'"
        )
        result["valid"] = False

    if errors:
        result["valid"] = False

    return result


# ---------------------------------------------------------------------------
# Per-format content validators
# ---------------------------------------------------------------------------

def _validate_newick_file(
    file_path: str,
    result: Dict[str, object],
    content: Optional[str] = None,
) -> None:
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    warns: List[str] = result["warnings"]  # type: ignore[assignment]
    try:
        if content is None:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        content = content.strip()
        if not content:
            errors.append("Newick file is empty")
            return
        if not content.endswith(';'):
            errors.append("Newick content does not end with ';'")
        if content.count('(') != content.count(')'):
            errors.append("Unbalanced parentheses in Newick content")
        if content.count('[') != content.count(']'):
            warns.append("Unbalanced square brackets in Newick content")
    except OSError as e:
        errors.append(f"Error reading Newick file: {e}")


def _validate_nexus_file(file_path: str, result: Dict[str, object]) -> None:
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    warns: List[str] = result["warnings"]  # type: ignore[assignment]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        content_upper = content.upper().strip()
        if not content_upper.startswith('#NEXUS'):
            errors.append("Nexus file does not start with '#NEXUS'")
        # Collapse whitespace so "BEGIN\nTREES;" also matches
        collapsed = re.sub(r'\s+', ' ', content_upper)
        if not re.search(r'\bBEGIN\b.*?\bEND\s*;', collapsed):
            errors.append("Nexus file has no 'begin ... end;' block")
        if 'BEGIN TREES' not in collapsed:
            warns.append("Nexus file has no 'begin trees' block")
    except OSError as e:
        errors.append(f"Error reading Nexus file: {e}")


def _validate_phyloxml_file(file_path: str, result: Dict[str, object]) -> None:
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(16384)
        if '<phyloxml' not in content.lower():
            errors.append("PhyloXML file does not contain '<phyloxml>' root element")
    except OSError as e:
        errors.append(f"Error reading PhyloXML file: {e}")


def _validate_fasta_file(file_path: str, result: Dict[str, object]) -> None:
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    warns: List[str] = result["warnings"]  # type: ignore[assignment]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            first_line = f.readline()
        if not first_line.startswith('>'):
            errors.append("FASTA file does not start with '>' header line")
        # Count sequences for advisory info
        seq_count = 0
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if line.startswith('>'):
                    seq_count += 1
        if seq_count == 0:
            warns.append("FASTA file appears to contain no sequences")
    except OSError as e:
        errors.append(f"Error reading FASTA file: {e}")


def _validate_fastq_file(file_path: str, result: Dict[str, object]) -> None:
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = [f.readline() for _ in range(4)]
        if not lines[0].startswith('@'):
            errors.append("FASTQ file does not start with '@' header line")
        if len(lines) >= 3 and not lines[2].startswith('+'):
            errors.append("FASTQ file: third line does not start with '+'")
    except OSError as e:
        errors.append(f"Error reading FASTQ file: {e}")


def _validate_flatfile(file_path: str, result: Dict[str, object]) -> None:
    """Validate GenBank / EMBL flat files."""
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(512)
        fmt = result.get("format")
        if fmt == 'genbank' and not head.upper().startswith('LOCUS'):
            errors.append("GenBank file does not start with 'LOCUS' line")
        elif fmt == 'embl' and not head.upper().startswith('ID   '):
            errors.append("EMBL file does not start with 'ID' line")
    except OSError as e:
        errors.append(f"Error reading {result.get('format', 'flat')} file: {e}")


def _validate_phylip_file(file_path: str, result: Dict[str, object]) -> None:
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    warns: List[str] = result["warnings"]  # type: ignore[assignment]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            first_line = f.readline().strip()
        parts = first_line.split()
        if len(parts) < 2:
            errors.append("Phylip file: first line must contain ntax and nchar")
        else:
            try:
                ntax = int(parts[0])
                if ntax <= 0:
                    errors.append(f"Phylip file: invalid ntax={ntax}")
            except ValueError:
                errors.append(f"Phylip file: cannot parse ntax from '{parts[0]}'")
    except OSError as e:
        errors.append(f"Error reading Phylip file: {e}")


def _validate_stockholm_file(file_path: str, result: Dict[str, object]) -> None:
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(4096)
        if '# STOCKHOLM' not in head.upper() and '#STOCKHOLM' not in head.upper():
            errors.append("Stockholm file does not start with '# STOCKHOLM' header")
    except OSError as e:
        errors.append(f"Error reading Stockholm file: {e}")


def _validate_clustal_file(file_path: str, result: Dict[str, object]) -> None:
    errors: List[str] = result["errors"]  # type: ignore[assignment]
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(4096)
        if not head.upper().startswith('CLUSTAL'):
            errors.append("Clustal file does not start with 'CLUSTAL' header")
    except OSError as e:
        errors.append(f"Error reading Clustal file: {e}")


# ── .nhx extension support ──────────────────────────────────────────────

_EXT_FORMAT_MAP['.nhx'] = 'newick'
TREE_EXTENSIONS.add('.nhx')


# ════════════════════════════════════════════════════════════════════════
# Adversarial input protection
# ════════════════════════════════════════════════════════════════════════

# Unicode bidi override characters that can hide malicious content
_BIDI_CHARS = {
    '\u202A',  # LEFT-TO-RIGHT EMBEDDING
    '\u202B',  # RIGHT-TO-LEFT EMBEDDING
    '\u202C',  # POP DIRECTIONAL FORMATTING
    '\u202D',  # LEFT-TO-RIGHT OVERRIDE
    '\u202E',  # RIGHT-TO-LEFT OVERRIDE
    '\u2066',  # LEFT-TO-RIGHT ISOLATE
    '\u2067',  # RIGHT-TO-LEFT ISOLATE
    '\u2068',  # FIRST STRONG ISOLATE
    '\u2069',  # POP DIRECTIONAL ISOLATE
    '\u061C',  # ARABIC LETTER MARK
}

# Control characters that should never appear in node/sequence names
_CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')

# Bidi override characters compiled as a single character class so the scan
# can use a regex pass (O(n) in C) instead of a per-character Python loop.
_BIDI_CLASS_RE = re.compile("[" + re.escape("".join(_BIDI_CHARS)) + "]")


def scan_for_anomalous_content(
    content: str,
    *,
    label: str = "<string>",
    source: str = "file",
) -> List[str]:
    """Scan content for control characters and Unicode bidi overrides.

    Args:
        content: Text content to scan.
        label: Label for error messages (e.g. filename).
        source: Description of the source type (e.g. "tree", "sequence").

    Returns:
        List of error message strings.  Empty means content is clean.
    """
    errors: List[str] = []

    # Pre-compute the start offset of every line ONCE (O(n)) so that each
    # match's line number is found in O(log n) via bisect instead of the
    # previous O(n) ``content[:pos].count('\n')`` slice that made the whole
    # scan O(n²) for content with many matches.
    line_starts: List[int] = [0]
    for ln in content.split('\n')[:-1]:
        line_starts.append(line_starts[-1] + len(ln) + 1)

    # Check for control characters
    for m in _CONTROL_RE.finditer(content):
        ch = m.group(0)
        pos = m.start()
        line_num = bisect.bisect_right(line_starts, pos)
        errors.append(
            f"{label}: CRITICAL — {source} contains control character "
            f"U+{ord(ch):04X} at line {line_num}, position {pos} — "
            f"possible injection, rejecting"
        )
        if len(errors) >= 5:
            errors.append(f"{label}: (further control character warnings suppressed)")
            break

    # Check for bidi overrides (regex pass — O(n) in C, replaces the previous
    # per-character Python loop which was needlessly slow on large content).
    for m in _BIDI_CLASS_RE.finditer(content):
        pos = m.start()
        line_num = bisect.bisect_right(line_starts, pos)
        errors.append(
            f"{label}: CRITICAL — {source} contains Unicode bidi "
            f"override U+{ord(m.group(0)):04X} at line {line_num} — "
            f"possible spoofing, rejecting"
        )
        if len(errors) >= 10:
            break

    return errors


def scan_for_anomalous_content_stream(
    file_path: str,
    *,
    label: str = "<file>",
    chunk_size: int = 1 << 20,
    max_findings: int = 50,
) -> List[str]:
    """Streaming variant of :func:`scan_for_anomalous_content` for large files.

    Reads *file_path* in fixed-size chunks so memory stays bounded even for
    multi-GB inputs, while still reporting control characters and Unicode
    bidi overrides with their line numbers.

    Args:
        file_path: Path to the file to scan.
        label: Label for error messages.
        chunk_size: Bytes per read chunk (default 1 MiB).
        max_findings: Stop after this many findings (caps scan cost).

    Returns:
        List of error message strings.  Empty means content is clean.
    """
    errors: List[str] = []
    line_starts: List[int] = [0]
    abs_pos = 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            while True:
                if len(errors) >= max_findings:
                    break
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                # Control characters
                for m in _CONTROL_RE.finditer(chunk):
                    pos = abs_pos + m.start()
                    line_num = bisect.bisect_right(line_starts, pos)
                    errors.append(
                        f"{label}: CRITICAL — file contains control character "
                        f"U+{ord(m.group(0)):04X} at line {line_num}, "
                        f"position {pos} — possible injection, rejecting"
                    )
                    if len(errors) >= 5:
                        errors.append(
                            f"{label}: (further control character warnings suppressed)"
                        )
                        break
                if len(errors) >= max_findings:
                    break
                # Bidi overrides
                for m in _BIDI_CLASS_RE.finditer(chunk):
                    pos = abs_pos + m.start()
                    line_num = bisect.bisect_right(line_starts, pos)
                    errors.append(
                        f"{label}: CRITICAL — file contains Unicode bidi "
                        f"override U+{ord(m.group(0)):04X} at line {line_num} "
                        f"— possible spoofing, rejecting"
                    )
                    if len(errors) >= 10:
                        break
                # Track line starts across chunks for line-number reporting.
                for nl in re.finditer(r"\n", chunk):
                    line_starts.append(abs_pos + nl.start() + 1)
                abs_pos += len(chunk)
    except OSError as e:
        errors.append(f"{label}: cannot read file for scanning: {e}")
    return errors


def scan_node_names_for_anomalous(
    names: List[str],
    *,
    label: str = "<string>",
) -> List[str]:
    """Scan a list of node/sequence names for anomalous characters.

    Args:
        names: List of node or sequence names.
        label: Label for error messages.

    Returns:
        List of error message strings.
    """
    errors: List[str] = []
    for name in names:
        # Control characters
        ctrl = _CONTROL_RE.findall(name)
        if ctrl:
            chars = ', '.join(f'U+{ord(c):04X}' for c in ctrl[:3])
            errors.append(
                f"{label}: node name '{name[:40]}' contains control "
                f"character(s) [{chars}] — rejecting"
            )
        # Bidi overrides
        bidi = [c for c in name if c in _BIDI_CHARS]
        if bidi:
            chars = ', '.join(f'U+{ord(c):04X}' for c in bidi[:3])
            errors.append(
                f"{label}: node name '{name[:40]}' contains bidi "
                f"override(s) [{chars}] — rejecting"
            )
    return errors


# Canonical taxonomic rank order (highest → lowest).  Used only to decide
# edge direction when building the containment graph in
# :func:`detect_taxonomy_circular_deps`.  Unknown ranks fall back to a stable
# ordering so the detector still works with custom rank configurations.
_STD_RANK_PRIORITY: Dict[str, int] = {
    "domain": 0,
    "superkingdom": 0,
    "kingdom": 1,
    "phylum": 2,
    "class": 3,
    "order": 4,
    "family": 5,
    "genus": 6,
    "species": 7,
    "subspecies": 8,
    "strain": 9,
}


def _rank_priority(rank: str) -> int:
    """Return a canonical priority for a taxonomic rank (lower = higher level)."""
    if rank in _STD_RANK_PRIORITY:
        return _STD_RANK_PRIORITY[rank]
    # Unknown rank: keep it ordered after the standard ranks but deterministic.
    return 100 + (hash(rank) % 1000)


def detect_taxonomy_circular_deps(
    taxonomy_rows: List[Tuple[str, Dict[str, str]]],
) -> List[str]:
    """Detect circular rank-value dependencies in taxonomy mappings.

    A circular dependency means the rank→value assignments are mutually
    contradictory.  For example::

        Row 1: d__A;p__B
        Row 2: d__B;p__A

    Taxon 1 says domain=A, phylum=B and taxon 2 says domain=B, phylum=A.
    Following the containment ``domain ⊃ phylum`` we get A ⊃ B and B ⊃ A —
    a contradiction (directed cycle A → B → A).

    The implementation builds a **directed graph** over the taxon values:

    * Within each row, every higher-level rank value points to every
      lower-level rank value it contains (e.g. ``domain=A`` → ``phylum=B``).
    * Because edge direction encodes containment, a value that appears at a
      *higher* rank in one row and a *lower* rank in another row closes a
      cycle across rows.

    A depth-first search with three-color marking reports every directed
    cycle.  This correctly detects both the simple two-row swap shown above
    and longer chains (A→B, B→C, C→A) that the old pairwise-swap heuristic
    missed.

    .. note::
        The graph is built on raw values.  A value that legitimately appears
        at two different ranks across taxa (a rare label collision, e.g. a
        genus and a family sharing the same string) will be reported as a
        potential cycle.  This is intentionally conservative: such a
        collision is almost always a genuine taxonomy inconsistency, but if
        your data uses the same label at multiple ranks by design you may
        treat these reports as advisory.

    Args:
        taxonomy_rows: List of ``(taxon_name, taxonomy_dict)`` tuples, where
            each ``taxonomy_dict`` maps rank name → value.

    Returns:
        List of error message strings describing each cycle found.
    """
    # 1. Build the directed containment graph (value -> value).
    graph: Dict[str, List[str]] = {}
    for _name, tax in taxonomy_rows:
        if not tax:
            continue
        ranks = list(tax.keys())
        for a in range(len(ranks)):
            for b in range(len(ranks)):
                if a == b:
                    continue
                rank_a, rank_b = ranks[a], ranks[b]
                # Only connect a higher-level (lower priority) rank value to a
                # lower-level rank value so the edge direction encodes
                # containment (parent → child).
                if _rank_priority(rank_a) < _rank_priority(rank_b):
                    val_a = tax[rank_a]
                    val_b = tax[rank_b]
                    if not val_a or not val_b or val_a == val_b:
                        continue
                    graph.setdefault(val_a, [])
                    if val_b not in graph[val_a]:
                        graph[val_a].append(val_b)

    # 2. Detect directed cycles via iterative DFS three-color marking.
    #    Implemented with an explicit stack (instead of recursion) so deeply
    #    nested containment chains cannot blow Python's recursion limit.
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {node: WHITE for node in graph}
    cycles: List[List[str]] = []

    for start in list(graph.keys()):
        if color[start] != WHITE:
            continue
        stack: List[Tuple[str, List[str]]] = []
        path: List[str] = []
        color[start] = GRAY
        stack.append((start, list(graph.get(start, ()))))
        path.append(start)
        while stack:
            node, neighbours = stack[-1]
            if neighbours:
                nxt = neighbours.pop(0)
                if color.get(nxt, WHITE) == WHITE:
                    color[nxt] = GRAY
                    stack.append((nxt, list(graph.get(nxt, ()))))
                    path.append(nxt)
                elif color[nxt] == GRAY:
                    # Back-edge nxt -> node closes a cycle along the path.
                    idx = path.index(nxt)
                    cycles.append(path[idx:] + [nxt])
            else:
                color[node] = BLACK
                stack.pop()
                path.pop()

    # 3. Deduplicate cycles (same set of nodes reported from different starts)
    #    and format human-readable messages.
    errors: List[str] = []
    seen_cycles: Set[frozenset] = set()
    for cyc in cycles:
        key = frozenset(cyc)
        if key in seen_cycles:
            continue
        seen_cycles.add(key)
        chain = " → ".join(cyc)
        errors.append(
            f"Circular taxonomy dependency detected: {chain} "
            f"(a value is its own ancestor across ranks)"
        )

    return errors


# ════════════════════════════════════════════════════════════════════════
# Deep tree validation
# ════════════════════════════════════════════════════════════════════════

def deep_validate_newick(
    content: str,
    *,
    label: str = "<string>",
) -> Dict[str, object]:
    """Perform deep structural validation of a Newick string.

    Checks beyond syntax: negative branch lengths, empty node names,
    duplicate leaf names, multiple roots, quote escaping.

    Args:
        content: Newick string to validate.
        label: Label for error messages (e.g. filename).

    Returns:
        Dictionary with keys:
            - ``errors`` (list[str]): Fatal issues.
            - ``warnings`` (list[str]): Non-fatal issues.
            - ``node_count`` (int): Total node count.
            - ``leaf_count`` (int): Leaf node count.
            - ``leaf_names`` (list[str]): All leaf names.
    """
    errors: List[str] = []
    warns: List[str] = []
    node_count = 0
    open_paren_count = 0
    leaf_names: List[str] = []

    text = content.strip()
    if not text:
        errors.append(f"{label}: empty Newick content")
        return {"errors": errors, "warnings": warns, "node_count": 0,
                "leaf_count": 0, "leaf_names": []}

    # ── Anomalous content scan ──
    errors.extend(scan_for_anomalous_content(text, label=label, source="tree"))

    # ── Bracket balance with position ──
    paren_depth = 0
    bracket_depth = 0
    in_quote = False
    quote_char = None
    for i, ch in enumerate(text):
        if in_quote:
            if ch == quote_char:
                if i + 1 < len(text) and text[i + 1] == quote_char:
                    pass  # doubled escape
                else:
                    in_quote = False
            continue
        if ch in ("'", '"'):
            in_quote = True
            quote_char = ch
        elif ch == '(':
            paren_depth += 1
            open_paren_count += 1
        elif ch == ')':
            paren_depth -= 1
            if paren_depth < 0:
                errors.append(f"{label}: unmatched ')' at position {i}")
        elif ch == '[':
            bracket_depth += 1
        elif ch == ']':
            bracket_depth -= 1
            if bracket_depth < 0:
                errors.append(f"{label}: unmatched ']' at position {i}")

    if paren_depth > 0:
        errors.append(f"{label}: unmatched '(' — {paren_depth} unclosed")
    if bracket_depth > 0:
        warns.append(f"{label}: {bracket_depth} unclosed '[' bracket comment(s)")
    if in_quote:
        errors.append(f"{label}: unterminated quote starting at end of string")

    # ── Trailing semicolon ──
    if not text.endswith(';'):
        errors.append(f"{label}: Newick content does not end with ';'")

    # ── Negative branch lengths (CRITICAL) ──
    neg_bl = re.findall(r'([A-Za-z0-9_.\'\]\)]*):(-[\d.eE+]+)', text)
    for node_ctx, bl_str in neg_bl:
        try:
            bl = float(bl_str)
            if bl < 0:
                errors.append(
                    f"{label}: CRITICAL — negative branch length {bl} "
                    f"near '{node_ctx[-30:]}'"
                )
        except ValueError:
            pass

    # ── Extract node names and separate terminals from internal nodes ──
    # Prefer Bio.Phylo for an accurate terminal/internal split so that
    # duplicate detection and counts only consider true tips.  Fall back to a
    # regex heuristic when Bio.Phylo cannot parse the (possibly malformed)
    # tree.
    clean = strip_square_bracket_comments(text)
    clean = re.sub(r':[^(),;]+', '', clean)

    terminals: List[str] = []
    internal_names: List[str] = []
    found_names: List[str] = []
    bio_ok = False
    try:
        from io import StringIO
        from Bio import Phylo
        tree = Phylo.read(StringIO(text), "newick")
        terminals = [c.name for c in tree.get_terminals() if c.name]
        internal_names = [c.name for c in tree.get_nonterminals() if c.name]
        found_names = list(terminals) + list(internal_names)
        bio_ok = True
    except Exception:
        bio_ok = False

    if bio_ok:
        leaf_names = list(terminals)
        leaf_count = len(terminals)
        # Accurate total: every clade (terminals + internal nodes, root
        # included) counts once.  ``get_nonterminals()`` enumerates all
        # internal clades (root included).
        node_count = tree.count_terminals() + len(tree.get_nonterminals())
    else:
        # Regex fallback: re-extract names; a node name immediately preceded
        # by ')' is an internal (parent) name, everything else is a tip.
        found_names = []
        name_pattern = r'([(),;])\s*([^\(\),;]+?)\s*([),;])'
        for m in re.finditer(name_pattern, clean):
            name = m.group(2).strip().strip("'\"")
            if not name:
                continue
            found_names.append(name)
            if m.group(1) == ')':
                internal_names.append(name)
        terminals = [n for n in found_names if n not in set(internal_names)]
        leaf_names = list(terminals)
        leaf_count = len(terminals)
        # Approximate total (only used when Bio.Phylo parsing fails): every
        # '(' opens exactly one internal node.
        node_count = leaf_count + open_paren_count

    # ── Empty node names (ERROR) ──
    if re.search(r',\s*,', clean) or re.search(r'\(\s*,', clean):
        errors.append(f"{label}: contains empty node names (consecutive commas)")

    # ── Duplicate TIP names (ERROR — fatal for taxonomy mapping) ──
    # Only terminal (tip) names are checked; internal node names may
    # legitimately repeat across different clades.
    name_counts: Dict[str, int] = {}
    for name in terminals:
        name_counts[name] = name_counts.get(name, 0) + 1
    for name, count in name_counts.items():
        if count > 1:
            errors.append(
                f"{label}: duplicate tip name '{name}' appears {count} times"
            )

    # ── Self-loop detection ──
    # Check if any parenthesized group has the same taxon appearing as
    # both a child and a pseudo-parent (e.g. "(A,(A,B))" or "(A,A)")
    if re.search(r'\(\s*([^(),]+)\s*,\s*\1\s*[,)]', clean):
        errors.append(
            f"{label}: possible self-loop — same taxon appears multiple "
            f"times in a single clade"
        )

    # ── Anomalous node name scan ──
    errors.extend(scan_node_names_for_anomalous(found_names, label=label))

    return {
        "errors": errors,
        "warnings": warns,
        "node_count": node_count,
        "leaf_count": leaf_count,
        "leaf_names": leaf_names,
    }


def summarize_nexus_trees(file_path: str) -> List[Dict[str, object]]:
    """Parse a Nexus file and return a summary for each tree.

    Args:
        file_path: Path to the Nexus file.

    Returns:
        List of dicts, one per tree, with keys:
            ``name``, ``node_count``, ``leaf_count``, ``has_negative_bl``.
    """
    summaries: List[Dict[str, object]] = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError:
        return summaries

    # Find begin trees ... end;
    trees_match = re.search(
        r'\bbegin\s+trees\s*;(.*?)\bend\s*;', content, re.DOTALL | re.IGNORECASE
    )
    if not trees_match:
        return summaries

    trees_block = trees_match.group(1)

    # Find each tree declaration
    for m in re.finditer(
        r'\btree\s+(\S+)\s*=\s*(.*?)\s*;', trees_block, re.DOTALL | re.IGNORECASE
    ):
        tree_name = m.group(1)
        tree_body = m.group(2)

        # Strip [&...] annotations
        clean_body = re.sub(r'\[&[^\]]*\]', '', tree_body)

        leaf_count = len(re.findall(r'[,(]\s*([A-Za-z0-9_.\'"][^,():;]*?)\s*:', clean_body))
        if leaf_count == 0:
            leaf_count = len(re.findall(r'[,(]\s*([A-Za-z0-9_.\'"][^,():;]*?)\s*[),;]', clean_body))

        has_neg = bool(re.search(r':-[\d.]+', clean_body))

        summaries.append({
            "name": tree_name,
            "leaf_count": leaf_count,
            "has_negative_bl": has_neg,
        })

    return summaries


# ════════════════════════════════════════════════════════════════════════
# Deep sequence validation
# ════════════════════════════════════════════════════════════════════════

_DNA_CHARS = set("ACGTacgtNnRrYySsWwKkMmBbDdHhVv-")
_RNA_CHARS = set("ACGUacguNnRrYySsWwKkMmBbDdHhVv-")
_PROTEIN_CHARS = set("ACDEFGHIKLMNPQRSTVWYacdefghiklmnpqrstvwyXx*-")

_ALPHABET_MAP = {
    "DNA": _DNA_CHARS,
    "RNA": _RNA_CHARS,
    "protein": _PROTEIN_CHARS,
}


def _detect_alphabet(seq_lines: List[str]) -> str:
    """Guess alphabet from a list of sequence strings."""
    all_chars: set = set()
    for line in seq_lines:
        all_chars.update(line.strip())

    if all_chars <= _DNA_CHARS:
        return "DNA"
    if all_chars <= _RNA_CHARS:
        return "RNA"
    if all_chars <= _PROTEIN_CHARS:
        return "protein"
    return "unknown"


def deep_validate_fasta(
    file_path: str,
    *,
    expected_alphabet: Optional[str] = None,
    check_alignment: bool = True,
) -> Dict[str, object]:
    """Deep validation of a FASTA file.

    Checks:
      - Duplicate sequence IDs (ERROR).
      - Alphabet detection and invalid character reporting with line numbers.
      - Alignment length consistency (WARNING if inconsistent).

    Args:
        file_path: Path to the FASTA file.
        expected_alphabet: If set (``"DNA"``, ``"RNA"``, ``"protein"``),
            validate all characters against this alphabet.
        check_alignment: If ``True``, warn when sequence lengths differ.

    Returns:
        Dictionary with:
            ``errors``, ``warnings``, ``sequence_count``, ``alphabet``,
            ``duplicate_ids``, ``invalid_chars``, ``length_mismatch``.
    """
    errors: List[str] = []
    warns: List[str] = []
    duplicate_ids: List[str] = []
    invalid_chars: List[Dict[str, object]] = []
    seq_count = 0
    lengths: List[int] = []

    seen_ids: Dict[str, int] = {}  # id -> first line number
    current_id: Optional[str] = None
    current_line: int = 0
    seq_lines_for_alpha: List[str] = []
    seq_line_numbers: List[int] = []  # file line of each sequence's header
    current_seq_chars: List[str] = []
    expected_set: Optional[set] = None
    if expected_alphabet and expected_alphabet in _ALPHABET_MAP:
        expected_set = _ALPHABET_MAP[expected_alphabet]

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, start=1):
                line_stripped = line.rstrip('\n\r')
                if not line_stripped:
                    continue

                if line_stripped.startswith('>'):
                    # Save previous sequence
                    if current_id is not None:
                        seq_str = ''.join(current_seq_chars)
                        lengths.append(len(seq_str))
                        seq_lines_for_alpha.append(seq_str)
                        seq_line_numbers.append(current_line)

                    # Parse new header
                    header = line_stripped[1:].strip()
                    seq_id = header.split()[0] if header else f"unnamed_{line_num}"
                    current_line = line_num
                    current_seq_chars = []

                    if seq_id in seen_ids:
                        duplicate_ids.append(
                            f"line {line_num}: duplicate ID '{seq_id}' "
                            f"(first seen at line {seen_ids[seq_id]})"
                        )
                    else:
                        seen_ids[seq_id] = line_num
                    # Scan header for anomalous content
                    id_errors = scan_node_names_for_anomalous(
                        [seq_id], label=f"line {line_num}"
                    )
                    errors.extend(id_errors)
                    seq_count += 1
                    current_id = seq_id
                else:
                    # Sequence data
                    current_seq_chars.append(line_stripped)

                    if expected_set is not None:
                        for i, ch in enumerate(line_stripped):
                            if ch not in expected_set and len(invalid_chars) < 20:
                                invalid_chars.append({
                                    "line": line_num,
                                    "column": i + 1,
                                    "char": ch,
                                    "seq_id": current_id,
                                })

        # Finalize last sequence
        if current_id is not None:
            seq_str = ''.join(current_seq_chars)
            lengths.append(len(seq_str))
            seq_lines_for_alpha.append(seq_str)
            seq_line_numbers.append(current_line)

    except OSError as e:
        errors.append(f"Error reading FASTA file: {e}")
        return {"errors": errors, "warnings": warns, "sequence_count": 0,
                "alphabet": "unknown", "duplicate_ids": [],
                "invalid_chars": [], "length_mismatch": False}

    if seq_count == 0:
        warns.append("FASTA file contains no sequences")

    # Alphabet detection
    alphabet = _detect_alphabet(seq_lines_for_alpha) if seq_lines_for_alpha else "unknown"

    # If no expected alphabet but we can detect it, check against detected
    if expected_set is None and alphabet in _ALPHABET_MAP and seq_lines_for_alpha:
        auto_set = _ALPHABET_MAP[alphabet]
        for idx, seq_str in enumerate(seq_lines_for_alpha):
            file_line = seq_line_numbers[idx]
            for i, ch in enumerate(seq_str):
                if ch not in auto_set and len(invalid_chars) < 20:
                    # This shouldn't happen if detection is correct, but warn
                    warns.append(
                        f"FASTA: character '{ch}' at position {i+1} "
                        f"(sequence starting at file line {file_line}) does "
                        f"not match the detected alphabet '{alphabet}'"
                    )

    # Duplicate IDs are fatal
    for dup_msg in duplicate_ids:
        errors.append(f"FASTA: {dup_msg}")

    # Invalid chars — batch report (max 10 lines)
    if invalid_chars:
        char_summary: Dict[str, List[int]] = {}
        for entry in invalid_chars:
            ch = entry["char"]
            if ch not in char_summary:
                char_summary[ch] = []
            char_summary[ch].append(entry["line"])

        for ch, lines_list in list(char_summary.items())[:10]:
            line_refs = ", ".join(str(l) for l in lines_list[:5])
            if len(lines_list) > 5:
                line_refs += f" ... ({len(lines_list)} total)"
            errors.append(
                f"FASTA: invalid character '{ch}' for {expected_alphabet or alphabet} "
                f"alphabet at line(s) {line_refs}"
            )

    # Alignment check
    length_mismatch = False
    if check_alignment and lengths:
        unique_lengths = set(lengths)
        if len(unique_lengths) > 1:
            length_mismatch = True
            min_l, max_l = min(lengths), max(lengths)
            warns.append(
                f"FASTA: sequences are not aligned — lengths range from "
                f"{min_l} to {max_l} ({len(unique_lengths)} distinct lengths)"
            )

    return {
        "errors": errors,
        "warnings": warns,
        "sequence_count": seq_count,
        "alphabet": alphabet,
        "duplicate_ids": duplicate_ids,
        "invalid_chars": invalid_chars[:20],
        "length_mismatch": length_mismatch,
    }


def deep_validate_fastq(
    file_path: str,
    *,
    expected_alphabet: Optional[str] = None,
) -> Dict[str, object]:
    """Deep validation of a FASTQ file.

    Checks:
      - Record structure (4-line blocks: header, seq, +, quality).
      - Duplicate read IDs (ERROR).
      - Alphabet detection with invalid character reporting.
      - Sequence/quality length consistency.

    Args:
        file_path: Path to the FASTQ file.
        expected_alphabet: If set, validate characters against this alphabet.

    Returns:
        Dictionary with:
            ``errors``, ``warnings``, ``read_count``, ``alphabet``,
            ``duplicate_ids``, ``invalid_chars``.
    """
    errors: List[str] = []
    warns: List[str] = []
    duplicate_ids: List[str] = []
    invalid_chars: List[Dict[str, object]] = []
    read_count = 0
    seen_ids: Dict[str, int] = {}
    seq_lines_for_alpha: List[str] = []

    expected_set: Optional[set] = None
    if expected_alphabet and expected_alphabet in _ALPHABET_MAP:
        expected_set = _ALPHABET_MAP[expected_alphabet]

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            while True:
                header = f.readline()
                if not header:
                    break
                seq_line = f.readline()
                plus_line = f.readline()
                qual_line = f.readline()

                line_base = read_count * 4 + 1

                if not header.startswith('@'):
                    errors.append(
                        f"FASTQ: expected '@' header at line {line_base}, "
                        f"got '{header[:20].strip()}'"
                    )
                    break

                if not plus_line or not plus_line.startswith('+'):
                    errors.append(
                        f"FASTQ: expected '+' separator at line {line_base + 2}"
                    )
                    break

                read_id = header[1:].strip().split()[0]
                seq = seq_line.strip()
                qual = qual_line.strip() if qual_line else ""

                if read_id in seen_ids:
                    duplicate_ids.append(
                        f"line {line_base}: duplicate read ID '{read_id}' "
                        f"(first seen at line {seen_ids[read_id]})"
                    )
                else:
                    seen_ids[read_id] = line_base

                # Scan read ID for anomalous content
                id_errors = scan_node_names_for_anomalous(
                    [read_id], label=f"line {line_base}"
                )
                errors.extend(id_errors)

                if len(seq) != len(qual):
                    errors.append(
                        f"FASTQ: sequence length ({len(seq)}) != quality length "
                        f"({len(qual)}) at line {line_base}"
                    )

                seq_lines_for_alpha.append(seq)

                if expected_set is not None:
                    for i, ch in enumerate(seq):
                        if ch not in expected_set:
                            invalid_chars.append({
                                "line": line_base + 1,
                                "column": i + 1,
                                "char": ch,
                                "read_id": read_id,
                            })

                read_count += 1

    except OSError as e:
        errors.append(f"Error reading FASTQ file: {e}")
        return {"errors": errors, "warnings": warns, "read_count": 0,
                "alphabet": "unknown", "duplicate_ids": [], "invalid_chars": []}

    if read_count == 0:
        warns.append("FASTQ file contains no reads")

    alphabet = _detect_alphabet(seq_lines_for_alpha) if seq_lines_for_alpha else "unknown"

    for dup_msg in duplicate_ids:
        errors.append(f"FASTQ: {dup_msg}")

    if invalid_chars:
        char_summary: Dict[str, int] = {}
        for entry in invalid_chars:
            ch = entry["char"]
            char_summary[ch] = char_summary.get(ch, 0) + 1
        for ch, count in list(char_summary.items())[:10]:
            errors.append(
                f"FASTQ: invalid character '{ch}' for {expected_alphabet or alphabet} "
                f"alphabet — {count} occurrence(s)"
            )

    return {
        "errors": errors,
        "warnings": warns,
        "read_count": read_count,
        "alphabet": alphabet,
        "duplicate_ids": duplicate_ids,
        "invalid_chars": invalid_chars[:20],
    }


# ── Sequence ID extraction (shared by CLI and library API) ──────────────
# These must stay in sync with _cli._iter_sequence_ids.  To avoid divergence
# the CLI helper now delegates to this function.
_FASTA_EXTS = {".fasta", ".fa", ".fna", ".faa", ".ffn", ".frn"}
_FASTQ_EXTS = {".fastq", ".fq"}


def extract_sequence_ids(file_path) -> Iterator[str]:
    """Lazily yield sequence IDs from a FASTA or FASTQ file.

    Reads the file line-by-line so memory stays roughly constant regardless
    of file size.  This is the single canonical implementation shared by the
    CLI cross-validation path and the library ``cross_validate`` API.

    Args:
        file_path: Path to a FASTA/FASTQ file (str, ``Path`` or
            ``os.PathLike``).

    Returns:
        Iterator over sequence IDs (the first whitespace-delimited token of
        each header line).

    Raises:
        ValueError: If the file extension is not a supported sequence format.
        OSError: If the file cannot be read.
    """
    p = Path(file_path)
    ext = p.suffix.lower()
    if ext in _FASTA_EXTS:
        with open(p, "r", encoding="utf-8", errors="replace") as sf:
            for line in sf:
                if line.startswith(">"):
                    yield line[1:].strip().split()[0]
    elif ext in _FASTQ_EXTS:
        with open(p, "r", encoding="utf-8", errors="replace") as sf:
            for i, line in enumerate(sf):
                if i % 4 == 0 and line.startswith("@"):
                    yield line[1:].strip().split()[0]
    else:
        raise ValueError(f"unsupported sequence format '{ext}'")


# ════════════════════════════════════════════════════════════════════════
# Cross-validation: tree tips ↔ sequence IDs
# ════════════════════════════════════════════════════════════════════════

def cross_validate_tree_sequence(
    tree_tip_labels: List[str],
    sequence_ids: Iterable[str],
    *,
    label: str = "",
) -> Dict[str, object]:
    """Cross-validate tree tip labels against sequence IDs.

    Checks that the two sets are equal.  Reports differences.

    Args:
        tree_tip_labels: Terminal node names from the tree.
        sequence_ids: Sequence IDs from FASTA/FASTQ.  May be a list or any
            iterable; the iterable is consumed exactly once when building the
            sequence set.
        label: Label for error messages.

    Returns:
        Dictionary with:
            ``errors``, ``warnings``, ``only_in_tree``, ``only_in_sequences``,
            ``matched``.
    """
    errors: List[str] = []
    warns: List[str] = []

    tree_set = set(tree_tip_labels)
    seq_set = set(sequence_ids)

    only_in_tree = sorted(tree_set - seq_set)
    only_in_seq = sorted(seq_set - tree_set)

    if only_in_tree:
        errors.append(
            f"{label}: {len(only_in_tree)} tip(s) in tree but not in "
            f"sequences: {', '.join(only_in_tree[:5])}"
            + ("..." if len(only_in_tree) > 5 else "")
        )
    if only_in_seq:
        errors.append(
            f"{label}: {len(only_in_seq)} sequence(s) not in tree tips: "
            + f"{', '.join(only_in_seq[:5])}"
            + ("..." if len(only_in_seq) > 5 else "")
        )

    matched = len(tree_set & seq_set)
    if not errors:
        warns.append(f"{label}: tree and sequences match ({matched} taxa)")

    return {
        "errors": errors,
        "warnings": warns,
        "only_in_tree": only_in_tree,
        "only_in_sequences": only_in_seq,
        "matched": matched,
    }


# ════════════════════════════════════════════════════════════════════════
# UTF-8-sig fallback reader
# ════════════════════════════════════════════════════════════════════════

def read_text_with_fallback(
    file_path: str,
    *,
    label: str = "",
) -> Tuple[str, List[str]]:
    """Read a text file with UTF-8, falling back to utf-8-sig or latin-1.

    Args:
        file_path: Path to the file.
        label: Label for warning messages.

    Returns:
        Tuple of ``(content, warnings)``.
    """
    warns: List[str] = []

    # Try utf-8 first
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            return f.read(), warns
    except UnicodeDecodeError:
        pass

    # Try utf-8-sig (BOM-aware)
    try:
        with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
            content = f.read()
        warns.append(
            f"{label}: file has UTF-8 BOM — decoded with utf-8-sig fallback"
        )
        return content, warns
    except UnicodeDecodeError:
        pass

    # Fallback to latin-1 (never fails)
    with open(file_path, 'r', encoding='latin-1', newline='') as f:
        content = f.read()
    warns.append(
        f"{label}: file is not valid UTF-8 — decoded with latin-1 fallback"
    )
    return content, warns
