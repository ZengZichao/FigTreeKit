# SPDX-License-Identifier: GPL-2.0-or-later
# This file is part of FigTreeKit; see LICENSE and NOTICE for licensing terms.
"""Command-line interface for FigTreeKit."""

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

import argparse
import atexit
from enum import IntEnum
import json
import logging
import os
import random
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple

from .enums import LayoutType, OrderType, RootingType, TransformType
from .exceptions import CompatibilityWarning, ExportError, ParseError, RenderError, ValidationError
from ._parser import extract_taxa_from_newick
from .styler import FigTreeStyler
from .enums import FontStyle
from .validators import (
    validate_input_file,
    deep_validate_newick, deep_validate_fasta, deep_validate_fastq,
    summarize_nexus_trees, extract_sequence_ids,
)


# ── Internal exceptions ─────────────────────────────────────────────────

class _UsageError(Exception):
    """Raised for CLI usage errors that should produce exit code 2."""


class ExitCode(IntEnum):
    """Unified CLI exit codes. Numeric values are part of the public
    contract — do NOT change them, external scripts may depend on them."""
    SUCCESS = 0
    GENERAL_ERROR = 1
    USAGE_ERROR = 2
    DATA_ERROR = 3
    INTERRUPTED = 130


# ── Graceful termination on SIGINT / SIGTERM ────────────────────────────

class _GracefulTerminator:
    """Tracks state for cooperative cancellation and resource cleanup."""

    def __init__(self) -> None:
        self.interrupted: bool = False
        self.current_step: str = ""
        self.files_processed: int = 0
        self.files_total: int = 0
        self._temp_files: Set[str] = set()
        self._original_handlers: dict = {}

    def register(self) -> None:
        """Install signal handlers for SIGINT and SIGTERM."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._original_handlers[sig] = signal.signal(sig, self._handler)
            except (OSError, ValueError):
                # signal() may fail on some platforms (e.g. non-main thread)
                pass
        atexit.register(self._cleanup_temps)

    def unregister(self) -> None:
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except (OSError, ValueError):
                pass

    def track_temp(self, path: str) -> None:
        """Register a temporary file for cleanup on abort."""
        self._temp_files.add(path)

    def untrack_temp(self, path: str) -> None:
        """Remove a temporary file from the cleanup set (it was finalized)."""
        self._temp_files.discard(path)

    def _handler(self, signum: int, frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        self.interrupted = True
        if logger:
            logger.warning(f"Received {sig_name} — terminating gracefully ...")
            logger.warning(
                f"Progress: {self.files_processed}/{self.files_total} file(s) completed"
            )
            if self.current_step:
                logger.warning(f"Interrupted during: {self.current_step}")
        self._cleanup_temps()
        sys.exit(ExitCode.INTERRUPTED)

    def _cleanup_temps(self) -> None:
        for path in list(self._temp_files):
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass
        self._temp_files.clear()


_terminator = _GracefulTerminator()


# ── Custom logging handler — always flushes ─────────────────────────────

class _FlushStreamHandler(logging.StreamHandler):
    """StreamHandler that flushes after every record for real-time output."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + "\n")
            stream.flush()
        except Exception:
            self.handleError(record)


class _FigTreeKitFormatter(logging.Formatter):
    """Formatter with ISO 8601 timestamp, level badge, and aligned output."""

    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created))
        ts_ms = f"{ts}.{record.msecs:03.0f}"
        level = record.levelname
        badge = f"[{level:>8}]"
        msg = record.getMessage()
        return f"{ts_ms} | {badge} | {msg}"


# ── Memory usage helper (optional psutil) ───────────────────────────────

def _log_memory(label: str = "") -> None:
    """Log current process memory at DEBUG level if psutil is available."""
    try:
        import psutil
        proc = psutil.Process()
        mem = proc.memory_info()
        rss_mb = mem.rss / (1024 * 1024)
        logger.debug(f"Memory {label}: RSS={rss_mb:.1f} MB")
    except ImportError:
        pass  # psutil not installed — silently skip
    except Exception:
        pass


# ── Step timer helper ───────────────────────────────────────────────────

class _StepTimer:
    """Context manager that logs a step's start and elapsed time."""

    def __init__(self, step_name: str, parent_logger: logging.Logger):
        self._name = step_name
        self._log = parent_logger
        self._start: float = 0.0

    def __enter__(self) -> "_StepTimer":
        self._log.info(f">>> {self._name} ...")
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        elapsed = time.perf_counter() - self._start
        if elapsed < 1.0:
            t = f"{elapsed * 1000:.0f} ms"
        else:
            t = f"{elapsed:.2f} s"
        self._log.info(f"<<< {self._name} ({t})")
        _log_memory(f"after {self._name}")


# ── Logger setup ────────────────────────────────────────────────────────

def setup_logger(
    quiet: bool = False,
    verbose: int = 0,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Configure the figtreekit logger with real-time flushed output.

    Args:
        quiet: Suppress all output below ERROR.
        verbose: 0 = WARNING, 1 = INFO, 2+ = DEBUG.
        log_file: If provided, also write logs to this file (UTF-8, flush).

    Returns:
        Configured logger instance.
    """
    log = logging.getLogger("figtreekit")

    # Remove existing handlers to avoid duplicates
    log.handlers.clear()

    if quiet:
        level = logging.ERROR
    elif verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    log.setLevel(level)

    # Console handler → stdout (not stderr)
    console_handler = _FlushStreamHandler(sys.stdout)
    console_handler.setFormatter(_FigTreeKitFormatter())
    console_handler.setLevel(level)
    log.addHandler(console_handler)

    # File handler (if --log-file)
    if log_file:
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(_FigTreeKitFormatter())
        file_handler.setLevel(logging.DEBUG)  # file gets all levels
        log.addHandler(file_handler)

    return log


logger = logging.getLogger("figtreekit")


# ── CLI parser ──────────────────────────────────────────────────────────

def _get_version_string() -> str:
    """Build a rich version string with commit hash and dependency info."""
    from . import __version__, __git_hash__, __version_date__

    parts = [f"%(prog)s {__version__}"]

    # Git commit hash (prefer setuptools_scm, fall back to git subprocess)
    git_hash = __git_hash__
    if not git_hash:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            if result.returncode == 0 and result.stdout.strip():
                git_hash = result.stdout.strip()
        except Exception:
            pass
    if git_hash:
        parts.append(f"commit: {git_hash}")
    if __version_date__:
        parts.append(f"date: {__version_date__}")

    # Dependency versions
    deps = []
    try:
        import Bio
        deps.append(f"biopython {Bio.__version__}")
    except Exception:
        pass
    parts.append(f"python {sys.version.split()[0]}")
    if deps:
        parts.append(f"deps: {', '.join(deps)}")

    return "\n".join(parts)


def _positive_int(value: str) -> int:
    """argparse type: positive integer (> 0)."""
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value}")
    return ivalue


def _non_negative_int(value: str) -> int:
    """argparse type: non-negative integer (>= 0)."""
    ivalue = int(value)
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"must be a non-negative integer, got {value}")
    return ivalue


def _positive_float(value: str) -> float:
    """argparse type: positive float (> 0)."""
    fvalue = float(value)
    if fvalue <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive number, got {value}")
    return fvalue


def _non_negative_float(value: str) -> float:
    """argparse type: non-negative float (>= 0)."""
    fvalue = float(value)
    if fvalue < 0:
        raise argparse.ArgumentTypeError(f"must be a non-negative number, got {value}")
    return fvalue


def _existing_file_or_dir(value: str) -> str:
    """argparse type: path must exist as a file or directory."""
    if not os.path.exists(value):
        raise argparse.ArgumentTypeError(f"path does not exist: {value}")
    return value


def _font_style_int(value: str) -> int:
    """argparse type: font style 0-3."""
    ivalue = int(value)
    if ivalue not in (0, 1, 2, 3):
        raise argparse.ArgumentTypeError(
            f"font style must be 0 (plain), 1 (bold), 2 (italic), or 3 (bold-italic), got {value}"
        )
    return ivalue


def _looks_like_taxon(name: str) -> bool:
    """Heuristic: detect whether a --collapse-taxa token looks like a taxon."""
    if '"' in name or "'" in name or ',' in name:
        return False
    return True


# Reserved --collapse-taxa collapse-style tokens.  A bare trailing token equal
# to one of these unambiguously denotes the collapse style (legacy shorthand);
# anything else is treated as an ordinary taxon name — never silently as a label.
_COLLAPSE_RESERVED_TYPES = ('collapse', 'cartoon')


def _parse_collapse_taxa_spec(spec: str) -> Tuple[List[str], Optional[str], str]:
    """Parse a single ``--collapse-taxa`` spec into ``(taxa, label, collapse_type)``.

    Accepted (explicit, unambiguous) format::

        TAXON[,TAXON...][,label=NAME][,type=TYPE]

    where ``TYPE`` is ``collapse`` (default) or ``cartoon``.  For backward
    compatibility a bare trailing token equal to a reserved type
    (``collapse``/``cartoon``) is still accepted as the collapse style.

    Crucially, a trailing token that is neither a reserved type nor prefixed
    with ``label=`` is treated as a real taxon name — so names such as
    ``my_label`` are never misclassified as a collapse label.  Any malformed
    spec raises ``ValueError`` with a clear message instead of being guessed.
    """
    parts = [p.strip() for p in spec.split(',') if p.strip()]
    if not parts:
        raise ValueError(f"--collapse-taxa spec '{spec}' is empty")

    label: Optional[str] = None
    collapse_type = "collapse"
    taxa: List[str] = []

    for part in parts:
        low = part.lower()
        if low.startswith('label='):
            label = part[len('label='):].strip() or None
            continue
        if low.startswith('type='):
            t = part[len('type='):].strip().lower()
            if t not in _COLLAPSE_RESERVED_TYPES:
                raise ValueError(
                    f"--collapse-taxa '{spec}': invalid type '{t}' "
                    f"(expected one of {_COLLAPSE_RESERVED_TYPES})"
                )
            collapse_type = t
            continue
        # Bare reserved-type token (legacy shorthand) denotes collapse style.
        if part in _COLLAPSE_RESERVED_TYPES:
            collapse_type = part
            continue
        # Everything else is an ordinary taxon name.
        taxa.append(part)

    if not taxa:
        raise ValueError(
            f"--collapse-taxa '{spec}' must include at least one taxon name"
        )
    return taxa, label, collapse_type


def _color_groups_by_result(
    fname: str,
    styler: FigTreeStyler,
    result: Dict[str, Any],
    logger: logging.Logger,
) -> Dict[str, Set[str]]:
    """Color every monophyletic/non-monophyletic group from an analysis result.

    Previously duplicated verbatim by ``--auto-color`` and ``--collapse-rank``.
    Monophyletic groups are colored across the whole clade
    (``set_clade_color_all``); non-monophyletic groups are colored
    terminal-by-terminal (``set_clade_color``), matching FigTree's
    gold-standard rendering.

    Args:
        fname: Source file name (for log messages).
        styler: The :class:`FigTreeStyler` being styled.
        result: Result dict from ``analyze_taxonomy`` (keys ``monophyletic``
            and ``non_monophyletic`` are dicts of group name -> clade info).
        logger: Logger for diagnostics.

    Returns:
        Tuple of (group name -> set of member taxa, group name -> color),
        so callers that need to look a group's members or assigned color up
        later (e.g. to find a parent phylum after collapsing) can do so
        without re-running the analysis.
    """
    mono = result.get('monophyletic', {})
    non_mono = result.get('non_monophyletic', {})
    all_groups = list(mono.keys()) + list(non_mono.keys())
    colors = styler._generate_group_colors(len(all_groups)) if all_groups else []
    color_map = dict(zip(all_groups, colors))
    group_taxa: Dict[str, Set[str]] = {}

    # Monophyletic groups: color ALL branches in the clade.
    for group_name, entry in mono.items():
        taxa = entry.get('taxa', [])
        if not taxa:
            continue
        group_taxa[group_name] = set(taxa)
        clean_name = group_name.strip('_')
        try:
            styler.set_clade_color_all(
                taxon_names=taxa, color=color_map.get(group_name, '#999999'),
            )
            logger.debug(f"{fname}: colored mono group '{clean_name}'")
        except Exception as e:
            logger.warning(f"{fname}: cannot color '{clean_name}': {e}")

    # Non-monophyletic groups: color each terminal individually.
    for group_name, entry in non_mono.items():
        taxa = entry.get('taxa', [])
        if not taxa:
            continue
        group_taxa[group_name] = set(taxa)
        clean_name = group_name.strip('_')
        color = color_map.get(group_name, '#999999')
        for taxon in taxa:
            try:
                styler.set_clade_color(taxon_names=[taxon], color=color)
            except Exception as e:
                logger.debug(f"{fname}: cannot color taxon '{taxon}': {e}")
        logger.debug(f"{fname}: colored non-mono group '{clean_name}' ({len(taxa)} terminals)")

    return group_taxa, color_map


def _coerce_value(raw: str):
    """Try to convert a --set value to int, float, bool, or keep as str."""
    raw = raw.strip()
    if raw.lower() in ('true', 'false'):
        return raw.lower() == 'true'
    if raw.lower() in ('null', 'none'):
        return None
    if (raw.startswith('"') and raw.endswith('"')) or \
       (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    try:
        if '.' in raw or 'e' in raw.lower():
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def create_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='figtreekit',
        description=(
            'Style phylogenetic trees for FigTree visualization.\n\n'
            'Reads Newick or Nexus tree files, applies aesthetic configurations\n'
            '(layout, colors, highlights, labels), and exports FigTree-compatible\n'
            'Nexus files.  Can also render to images via FigTree JAR.'
        ),
        epilog="""\
examples:
  # Style and export tree
  figtreekit input.tre -o output.nex --layout polar --tip-labels-show

  # Validate tree file
  figtreekit input.nex --validate

  # Batch processing
  figtreekit trees_dir/ -o styled/ --config style.json

  # Export and render to image (requires FigTree)
  figtreekit input.tre -o output.nex --render output.png
  figtreekit input.tre -o output.nex --render output.pdf --render-width 1600

  # Handle multi-tree files
  figtreekit multi.nex -o out.nex --multi-tree first
  figtreekit multi.nex -o out.nex --multi-tree all

  # Setup FigTree for rendering
  figtreekit --setup-figtree
  figtreekit --setup-figtree --check-figtree
  figtreekit --setup-figtree --figtree-jar /path/to/figtree.jar
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        'input', nargs='?',
        help='Input tree file (.tre/.nwk/.nex) or directory for batch processing',
    )
    parser.add_argument(
        '-o', '--output',
        help='Output Nexus file (or output directory for batch mode)',
    )
    parser.add_argument(
        '--validate', action='store_true',
        help='Check FigTree compatibility without exporting',
    )
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help='Increase verbosity (-v INFO, -vv DEBUG)',
    )
    parser.add_argument(
        '-q', '--quiet', action='store_true',
        help='Suppress all non-error output',
    )
    parser.add_argument(
        '--version', action='version',
        version=_get_version_string(),
    )
    parser.add_argument(
        '--config', metavar='FILE',
        help='JSON config file with style settings (see documentation for format)',
    )

    # Multi-tree handling
    parser.add_argument(
        '--multi-tree', choices=['ask', 'split', 'first', 'last', 'random', 'all'],
        metavar='MODE',
        help=(
            'Mode when input contains multiple trees:\n'
            '  ask    - (default) print summary and abort (exit 2)\n'
            '  split  - process each tree, output with numeric suffixes\n'
            '  first  - process only the first tree\n'
            '  last   - process only the last tree\n'
            '  random - process a randomly selected tree\n'
            '  all    - same as split\n'
            'If omitted and multiple trees are detected, behaves as ask.'
        ),
    )
    parser.add_argument(
        '--seed', type=int, default=None, metavar='N',
        help=(
            'Optional random seed for --multi-tree random, making the '
            'selected tree reproducible. Both the chosen tree index and the '
            'seed are logged.'
        ),
    )

    # Taxonomy level extensions
    parser.add_argument(
        '--taxonomy-levels', metavar='SPEC',
        help=(
            'Extend taxonomy rank prefixes. SPEC is a comma-separated list '
            'of prefix:rank pairs, e.g. "k:kingdom,ss:subspecies". '
            'These are added to the built-in set '
            '(d:domain,p:phylum,c:class,o:order,f:family,g:genus,s:species).'
        ),
    )
    parser.add_argument(
        '--taxonomy-delimiter-mode',
        choices=['reverse', 'greedy', 'segment'], default='reverse',
        help='Parsing strategy for embedded taxonomy (format A). '
             'reverse: right-to-left strict order (default); '
             'greedy: left-to-right first match; '
             'segment: from first _d_ onward.',
    )
    parser.add_argument(
        '--taxonomy-table-sep', metavar='CHAR', default=';',
        help='Separator for format B taxonomy strings (default: ";").',
    )
    parser.add_argument(
        '--taxonomy-source-priority',
        choices=['embedded', 'table'], default='table',
        help='When both embedded and table taxonomy exist for a node, '
             'which takes priority (default: table).',
    )
    parser.add_argument(
        '--ignore-malformed', action='store_true',
        help='Skip malformed taxonomy rows instead of aborting.',
    )
    parser.add_argument(
        '--taxonomy-mapping-file', metavar='FILE',
        help='Path to taxonomy mapping file (TSV/CSV) for labels '
             'that lack embedded taxonomy.',
    )
    parser.add_argument(
        '--table-sep', metavar='CHAR',
        help='Force column delimiter for taxonomy mapping file '
             '(default: auto-detect from extension).',
    )
    parser.add_argument(
        '--mol-type', choices=['DNA', 'RNA', 'protein'],
        help='Expected molecule type for sequence validation. '
             'If omitted, auto-detected.',
    )
    parser.add_argument(
        '--no-cross-check', action='store_true',
        help='Skip tree-sequence label cross-validation.',
    )
    parser.add_argument(
        '--sequences', metavar='FILE',
        help='Sequence file (FASTA/FASTQ) for cross-validation against tree tips.',
    )
    parser.add_argument(
        '--skip-length-check', action='store_true',
        help='Skip sequence length consistency check.',
    )
    parser.add_argument(
        '--low-memory', action='store_true',
        help='Reduce memory usage for large files (streaming mode).',
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Overwrite existing output files.',
    )
    parser.add_argument(
        '--no-clobber', action='store_true',
        help='Skip writing if output file already exists.',
    )
    parser.add_argument(
        '--strip-annotations', action='store_true',
        help='Strip all bracket comments (NHX, bootstrap, posterior) from '
             'the tree to reduce output file size.',
    )
    parser.add_argument(
        '--log-file', metavar='FILE',
        help='Write logs to this file (UTF-8, all levels).',
    )

    # FigTree setup
    setup = parser.add_argument_group('FigTree Setup')
    setup.add_argument(
        '--setup-figtree', action='store_true',
        help='Download and compile FigTree JAR for rendering (GPLv2)',
    )
    setup.add_argument(
        '--check-figtree', action='store_true',
        help='Check if FigTree JAR is available and exit',
    )
    setup.add_argument(
        '--figtree-jar', metavar='PATH',
        help='Explicit path to figtree.jar (for setup or rendering)',
    )

    # Self-test
    parser.add_argument(
        '--self-test', action='store_true',
        help='Run self-diagnostic checks (dependencies, example parsing, '
             'monophyly logic) and exit with [PASS]/[FAIL] table.',
    )

    # Rendering options
    render = parser.add_argument_group('Rendering (requires FigTree JAR)')
    render.add_argument(
        '--render', metavar='FILE',
        help='Render tree to image file (PNG/PDF/SVG/JPEG)',
    )
    render.add_argument(
        '--render-format', choices=['PNG', 'PDF', 'SVG', 'JPEG'],
        help='Render format (default: auto-detected from --render file extension)',
    )
    render.add_argument(
        '--render-width', type=_positive_int, default=1200, metavar='PX',
        help='Render width in pixels (default: 1200, must be > 0)',
    )
    render.add_argument(
        '--render-height', type=_positive_int, default=800, metavar='PX',
        help='Render height in pixels (default: 800, must be > 0)',
    )

    # Appearance
    app = parser.add_argument_group('Appearance')
    app.add_argument(
        '--branch-width', type=_positive_float, metavar='FLOAT',
        help='Branch line width (must be > 0)',
    )
    app.add_argument(
        '--branch-color-attribute', metavar='ATTR',
        help='Attribute name for branch coloring (e.g. "height")',
    )
    app.add_argument(
        '--background-color', metavar='#RRGGBB',
        help='Background color as hex RGB (e.g. #FFFFFF)',
    )
    app.add_argument(
        '--foreground-color', metavar='#RRGGBB',
        help='Foreground color as hex RGB (e.g. #000000)',
    )
    app.add_argument(
        '--selection-color', metavar='#RRGGBB',
        help='Selection highlight color as hex RGB',
    )

    # Layout
    lay = parser.add_argument_group('Layout')
    lay.add_argument(
        '--layout', choices=['rectilinear', 'polar', 'radial'],
        help='Tree layout type (default: rectilinear)',
    )
    lay.add_argument(
        '--expansion', type=_non_negative_int, metavar='INT',
        help='Layout expansion value (>= 0)',
    )
    lay.add_argument(
        '--zoom', type=_positive_float, metavar='FLOAT',
        help='Layout zoom factor (must be > 0)',
    )

    # Tree
    tree = parser.add_argument_group('Tree')
    tree.add_argument(
        '--rooted', action='store_true',
        help='Display tree as rooted',
    )
    tree.add_argument(
        '--unrooted', action='store_true',
        help='Display tree as unrooted',
    )
    tree.add_argument(
        '--rooting-type', choices=['user', 'midpoint'],
        help='Rooting method (user selection or mid-point)',
    )
    tree.add_argument(
        '--transform', choices=['cladogram', 'phylogram'],
        help='Transform type: cladogram (equal branches) or phylogram (proportional)',
    )
    tree.add_argument(
        '--order', choices=['increasing', 'decreasing'],
        help='Branch ordering by node density',
    )
    tree.add_argument(
        '--order-branches', action='store_true',
        help='Enable branch ordering (by increasing node density)',
    )
    tree.add_argument(
        '--clade', metavar='NAME', action='append',
        help='Collapse a clade by taxonomic group name (e.g. "Cyanobacteriota"). '
             'Checks monophyly first; if not monophyletic, warns and skips '
             '(or aborts with --strict). Can be specified multiple times.',
    )
    tree.add_argument(
        '--strict', action='store_true',
        help='Abort on non-monophyletic clades instead of skipping.',
    )

    # ── Clade annotations ────────────────────────────────────────────
    tree.add_argument(
        '--collapse-taxa', metavar='TAXA', action='append',
        help='Collapse a clade by specific taxon names (comma-separated). '
             'Optionally append explicit "label=NAME" and/or "type=TYPE" tokens '
             '— e.g. "A,B,label=my_label,type=cartoon". TYPE is "collapse" '
             '(default) or "cartoon"; a bare trailing "collapse"/"cartoon" is '
             'still accepted as the type. Taxon names are NEVER treated as '
             'labels, so names containing underscores (e.g. "my_label") work '
             'as expected. Can be specified multiple times.',
    )
    tree.add_argument(
        '--collapse-rank', metavar='RANK',
        help='Collapse ALL monophyletic groups at the given taxonomic rank. '
             'Requires taxonomy info in labels or --taxonomy-mapping-file. '
             'Respects --strict for non-monophyletic groups. '
             'Use --collapse-style to choose cartoon vs collapse.',
    )
    tree.add_argument(
        '--collapse-style', choices=['collapse', 'cartoon'], default='collapse',
        help='Clade collapse style for --collapse-rank. '
             '"collapse" (default) draws a triangle with the group label; '
             '"cartoon" draws a triangle preserving the branch span.',
    )
    tree.add_argument(
        '--auto-color', metavar='RANK', const='phylum', nargs='?',
        help='Auto-assign colors to all monophyletic groups at the given '
             'taxonomic rank (default: phylum). Runs monophyly analysis and '
             'applies per-group colors. Useful for fully-expanded trees.',
    )

    tree.add_argument(
        '--highlight', metavar='SPEC', action='append',
        help='Highlight a clade, format: "A,B,C[:#RRGGBB[:width[:offset]]]". '
             'Can be specified multiple times.',
    )
    tree.add_argument(
        '--color-clade', metavar='SPEC', action='append',
        help='Color a clade, format: "A,B,C:#RRGGBB". '
             'Affects MRCA branch only. Can be specified multiple times.',
    )
    tree.add_argument(
        '--color-all', action='store_true',
        help='With --color-clade, color all descendant branches '
             '(calls set_clade_color_all instead of set_clade_color).',
    )
    tree.add_argument(
        '--font-clade', metavar='SPEC', action='append',
        help='Set font for a clade, format: '
             '"A,B,C:FONTNAME[-STYLE[-SIZE]]". '
             'STYLE: PLAIN, BOLD, ITALIC, or BOLD_ITALIC. '
             'Can be specified multiple times.',
    )
    tree.add_argument(
        '--clear-hilights', action='store_true',
        help='Clear all clade highlight annotations (--highlight).',
    )

    # ── Taxonomy analysis commands ────────────────────────────────────
    tree.add_argument(
        '--analyze-taxonomy', nargs='?', const='phylum', metavar='RANK',
        help='Analyze taxonomy for the input tree and print a monophyly '
             'report. Default rank: phylum. Prints a structured report to '
             'stdout and exits (implies --validate).',
    )
    tree.add_argument(
        '--check-monophyly', metavar='NAME', action='append',
        help='Check whether a taxonomic group is monophyletic. '
             'NAME can be a taxon name (e.g. "Cyanobacteriota") or a '
             'special identifier (LUCA/LACA/LBCA/root). '
             'Can be specified multiple times.',
    )
    tree.add_argument(
        '--check-taxonomy', action='store_true',
        help='Check taxonomy completeness for all tip labels and exit '
             '(implies --validate). Reports the proportion of taxa with '
             'missing information at each rank.',
    )

    # ── Custom params ─────────────────────────────────────────────────
    adv = parser.add_argument_group('Advanced')
    adv.add_argument(
        '--set', metavar='KEY=VALUE', action='append', dest='custom_params',
        help='Set an arbitrary FigTree parameter (e.g. "--set '
             'appearance.branchLineWidth=2.5"). Can be specified multiple times.',
    )

    # Tip Labels
    lbl = parser.add_argument_group('Tip Labels')
    tip_labels_group = lbl.add_mutually_exclusive_group()
    tip_labels_group.add_argument(
        '--tip-labels-show', action='store_true',
        help='Show tip labels',
    )
    tip_labels_group.add_argument(
        '--tip-labels-hide', action='store_true',
        help='Hide tip labels',
    )
    lbl.add_argument(
        '--font-name', metavar='NAME',
        help='Font family name for tip labels (e.g. "Arial")',
    )
    lbl.add_argument(
        '--font-size', type=_positive_int, metavar='PT',
        help='Font size in points (must be > 0)',
    )
    lbl.add_argument(
        '--font-style', type=_font_style_int, metavar='0-3',
        help='Font style: 0=plain, 1=bold, 2=italic, 3=bold-italic',
    )
    lbl.add_argument(
        '--label-color', metavar='#RRGGBB',
        help='Tip label color as hex RGB',
    )

    # Node Labels
    nl = parser.add_argument_group('Node Labels')
    node_labels_group = nl.add_mutually_exclusive_group()
    node_labels_group.add_argument(
        '--node-labels-show', action='store_true',
        help='Show node labels',
    )
    node_labels_group.add_argument(
        '--node-labels-hide', action='store_true',
        help='Hide node labels',
    )
    nl.add_argument(
        '--node-display-attribute', metavar='ATTR',
        help='Attribute to display as node label (e.g. "height", "support")',
    )

    # Branch Labels
    bl = parser.add_argument_group('Branch Labels')
    branch_labels_group = bl.add_mutually_exclusive_group()
    branch_labels_group.add_argument(
        '--branch-labels-show', action='store_true',
        help='Show branch labels',
    )
    branch_labels_group.add_argument(
        '--branch-labels-hide', action='store_true',
        help='Hide branch labels',
    )
    bl.add_argument(
        '--branch-display-attribute', metavar='ATTR',
        help='Attribute to display as branch label (e.g. "length", "posterior")',
    )

    # Scale
    sc = parser.add_argument_group('Scale')
    scale_bar_group = sc.add_mutually_exclusive_group()
    scale_bar_group.add_argument(
        '--scale-bar-show', action='store_true',
        help='Show scale bar',
    )
    scale_bar_group.add_argument(
        '--scale-bar-hide', action='store_true',
        help='Hide scale bar',
    )
    scale_axis_group = sc.add_mutually_exclusive_group()
    scale_axis_group.add_argument(
        '--scale-axis-show', action='store_true',
        help='Show scale axis',
    )
    scale_axis_group.add_argument(
        '--scale-axis-hide', action='store_true',
        help='Hide scale axis',
    )
    sc.add_argument(
        '--root-age', type=_non_negative_float, metavar='FLOAT',
        help='Root age for time scale (>= 0)',
    )
    sc.add_argument(
        '--scale-factor', type=_positive_float, metavar='FLOAT',
        help='Scale factor multiplier (must be > 0)',
    )

    # Polar Layout
    po = parser.add_argument_group('Polar Layout')
    po.add_argument(
        '--angular-range', type=_non_negative_int, metavar='DEG',
        help='Angular range in degrees (0-360, default: 360)',
    )
    po.add_argument(
        '--root-angle', type=_non_negative_int, metavar='DEG',
        help='Root angle in degrees (0-360)',
    )
    po.add_argument(
        '--align-tip-labels', action='store_true',
        help='Align tip labels radially in polar/rectilinear layout',
    )

    # Radial Layout
    ra = parser.add_argument_group('Radial Layout')
    ra.add_argument(
        '--radial-spread', type=_non_negative_float, metavar='FLOAT',
        help='Radial spread factor (>= 0)',
    )

    # Rectilinear Layout
    re_ = parser.add_argument_group('Rectilinear Layout')
    re_.add_argument(
        '--curvature', type=_non_negative_int, metavar='INT',
        help='Branch curvature value (>= 0)',
    )
    re_.add_argument(
        '--root-length', type=_non_negative_int, metavar='INT',
        help='Root branch length in pixels (>= 0)',
    )

    # Legend
    lg = parser.add_argument_group('Legend')
    lg.add_argument(
        '--legend-show', action='store_true',
        help='Show legend',
    )
    lg.add_argument(
        '--legend-position', choices=['top', 'bottom', 'left', 'right'],
        help='Legend position (default: bottom)',
    )

    return parser


# ── Apply CLI args ──────────────────────────────────────────────────────

def apply_cli_args(styler: FigTreeStyler, args: argparse.Namespace) -> FigTreeStyler:
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {args.config}")
        try:
            config = json.loads(config_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON in config file {args.config}: {e}") from e
        styler.apply_dict(config)

    _LAYOUT_MAP = {'rectilinear': LayoutType.RECTILINEAR, 'polar': LayoutType.POLAR,
                   'radial': LayoutType.RADIAL}
    _ROOTING_MAP = {'user': RootingType.USER_SELECTION, 'midpoint': RootingType.MID_POINT}
    _TRANSFORM_MAP = {'cladogram': TransformType.CLADOGRAM, 'phylogram': TransformType.PHYLOGRAM}
    _ORDER_MAP = {'increasing': OrderType.INCREASING_NODE_DENSITY,
                  'decreasing': OrderType.DECREASING_NODE_DENSITY}

    _CLI_CONFIG = [
        ('branch_width',          'set_appearance',    {'branch_line_width': None}),
        ('branch_color_attribute','set_appearance',    {'branch_color_attribute': None}),
        ('background_color',      'set_appearance',    {'background_color': None}),
        ('foreground_color',      'set_appearance',    {'foreground_color': None}),
        ('selection_color',       'set_appearance',    {'selection_color': None}),
        ('layout',        'set_layout',  {'layout_type': _LAYOUT_MAP}),
        ('expansion',     'set_layout',  {'expansion': None}),
        ('zoom',          'set_layout',  {'zoom': None}),
        ('unrooted',       'set_trees', {'rooting': False}),
        ('rooted',         'set_trees', {'rooting': True}),
        ('rooting_type',   'set_trees', {'rooting': True, 'rooting_type': _ROOTING_MAP}),
        ('transform',      'set_trees', {'transform': True, 'transform_type': _TRANSFORM_MAP}),
        ('order',          'set_trees', {'order': True, 'order_type': _ORDER_MAP}),
        ('order_branches', 'set_trees', {'order': None}),
        ('tip_labels_show', 'set_tip_labels', {'is_shown': None}),
        ('tip_labels_hide', 'set_tip_labels', {'is_shown': False}),
        ('font_name',       'set_tip_labels', {'font_name': None}),
        ('font_size',       'set_tip_labels', {'font_size': None}),
        ('font_style',      'set_tip_labels', {'font_style': None}),
        ('label_color',     'set_tip_labels', {'color_attribute': None}),
        ('node_labels_show',       'set_node_labels', {'is_shown': None}),
        ('node_labels_hide',       'set_node_labels', {'is_shown': False}),
        ('node_display_attribute', 'set_node_labels', {'display_attribute': None, 'is_shown': True}),
        ('branch_labels_show',       'set_branch_labels', {'is_shown': None}),
        ('branch_labels_hide',       'set_branch_labels', {'is_shown': False}),
        ('branch_display_attribute', 'set_branch_labels', {'display_attribute': None, 'is_shown': True}),
        ('scale_bar_show', 'set_scale_bar', {'is_shown': None}),
        ('scale_bar_hide', 'set_scale_bar', {'is_shown': False}),
        ('scale_axis_show', 'set_scale_axis', {'is_shown': None}),
        ('scale_axis_hide', 'set_scale_axis', {'is_shown': False}),
        ('root_age',     'set_scale', {'root_age': None}),
        ('scale_factor', 'set_scale', {'scale_factor': None}),
        ('angular_range', 'set_polar_layout', {'angular_range': None}),
        ('root_angle',    'set_polar_layout', {'root_angle': None}),
        ('align_tip_labels', 'set_align_tip_labels', {'align': True}),
        ('radial_spread', 'set_radial_layout', {'spread': None}),
        ('curvature',   'set_rectilinear_layout', {'curvature': None}),
        ('root_length', 'set_rectilinear_layout', {'root_length': None}),
        ('legend_show',     'set_legend', {'is_shown': None}),
        ('legend_position', 'set_legend', {'position': None}),
    ]

    for arg_name, method_name, api_kwargs in _CLI_CONFIG:
        value = getattr(args, arg_name, None)
        if value is None:
            continue
        # Boolean flags that are store_true default to False (or are None when
        # absent).  We only ever *act* on an explicit True; a False/None value
        # would re-assert the default and is therefore skipped on purpose.
        if isinstance(value, bool) and not value:
            continue

        if arg_name == 'rooted' and getattr(args, 'unrooted', False):
            continue
        if arg_name == 'unrooted' and getattr(args, 'rooted', False):
            pass

        resolved = {}
        for kwarg_key, value_map in api_kwargs.items():
            if isinstance(value_map, dict):
                resolved[kwarg_key] = value_map[value]
            elif value_map is not None:
                resolved[kwarg_key] = value_map
            else:
                resolved[kwarg_key] = value

        method = getattr(styler, method_name)
        method(**resolved)

    return styler


# ── Single file processing ──────────────────────────────────────────────

def _detect_tree_count(input_path: Path) -> int:
    """Quickly count how many trees are in a file without full parsing.

    Notes on consistency:
      * Nexus files encode multiple named trees natively, so a count > 1 is
        meaningful and the trees can be split/selected downstream.
      * Newick files cannot encode multiple *named* trees.  A count > 1 there
        only means "concatenated Newick trees were detected" — FigTreeKit does
        NOT support extracting them, and the caller
        (``_process_single``) must reject Newick multi-tree input with a clear
        suggestion to use Nexus.  This count is therefore used purely for
        detection + rejection, never for actual splitting of Newick input.
    """
    try:
        content = input_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return -1

    content_upper = content.upper().strip()

    if content_upper.startswith('#NEXUS'):
        return len(re.findall(
            r'\btree\s+\S+\s*=', content, re.IGNORECASE
        ))
    else:
        # Newick: count top-level semicolons (each terminates a tree)
        in_quote = False
        bracket_depth = 0
        count = 0
        for ch in content:
            if ch == "'":
                in_quote = not in_quote
            elif ch == '[' and not in_quote:
                bracket_depth += 1
            elif ch == ']' and not in_quote and bracket_depth > 0:
                bracket_depth -= 1
            elif ch == ';' and not in_quote and bracket_depth == 0:
                count += 1
        return count


def _resolve_tree_indices(
    strategy: Optional[str], tree_count: int, fname: str, seed: Optional[int] = None
) -> Optional[List[int]]:
    """Resolve which tree indices to process.

    Args:
        strategy: Multi-tree mode (``first``/``last``/``random``/``all``/``split``).
        tree_count: Number of trees detected in the file.
        fname: Source file name (for logging).
        seed: Optional random seed. When provided together with the
            ``random`` strategy, the selected tree is reproducible.

    Returns:
        List of 0-based indices, or ``None`` to signal an error (caller should abort).
    """
    if tree_count <= 1:
        return [0]

    if strategy is None or strategy == "ask":
        logger.error(
            f"{fname}: detected {tree_count} trees in the input file, "
            f"but default mode expects exactly 1 tree."
        )
        logger.error("Please re-run with one of the following options:")
        logger.error("  --multi-tree first   Process only the first tree")
        logger.error("  --multi-tree last    Process only the last tree")
        logger.error("  --multi-tree random  Process a randomly selected tree")
        logger.error("  --multi-tree split   Process all trees, output with numeric suffixes")
        raise _UsageError(f"{fname}: multiple trees detected without --multi-tree")

    if strategy == "first":
        logger.info(f"{fname}: multiple trees detected, using first tree (index 0)")
        return [0]
    elif strategy == "last":
        idx = tree_count - 1
        logger.info(f"{fname}: multiple trees detected, using last tree (index {idx})")
        return [idx]
    elif strategy == "random":
        if seed is not None:
            random.seed(seed)
            logger.info(f"{fname}: seeding RNG with --seed {seed} for reproducibility")
        idx = random.randint(0, tree_count - 1)
        logger.info(
            f"{fname}: multiple trees detected, randomly selected tree "
            f"{idx + 1}/{tree_count}"
            + (f" (seed={seed})" if seed is not None else "")
        )
        return [idx]
    elif strategy in ("all", "split"):
        logger.info(f"{fname}: multiple trees detected, processing all {tree_count} trees")
        return list(range(tree_count))

    return [0]


def _iter_sequence_ids(seq_path: Path) -> Iterator[str]:
    """Lazily yield sequence IDs from a FASTA or FASTQ file.

    Delegates to :func:`figtreekit.validators.extract_sequence_ids` so the CLI
    and the library ``cross_validate`` API share one canonical implementation
    (single source of truth — the two paths can no longer diverge).
    """
    yield from extract_sequence_ids(seq_path)


def _process_single_tree(
    input_path: Path,
    args: argparse.Namespace,
    tree_index: int,
    output_override: Optional[str] = None,
    single_tree: bool = False,
) -> bool:
    """Process a single tree from a (possibly multi-tree) file.

    Args:
        input_path: Input file path.
        args: CLI arguments.
        tree_index: 0-based index of the tree to process.
        output_override: If set, use this as the output path instead of args.output.
        single_tree: If True, write the tree as the sole tree in the output.

    Returns:
        True on success.
    """
    fname = input_path.name

    with _StepTimer("Parsing tree file", logger):
        try:
            styler = FigTreeStyler(str(input_path), tree_index=tree_index)
        except (ParseError, FileNotFoundError, ValidationError, ExportError) as e:
            # ParseError/FileNotFoundError/ValidationError/ExportError are all
            # data/content problems → surface as a DATA_ERROR (exit 3) upstream
            # rather than the generic GENERAL_ERROR (exit 1) "unexpected error".
            logger.error(f"{fname}: {e}")
            return False
        # Wire taxonomy CLI args
        styler.configure_taxonomy(
            delimiter_mode=getattr(args, 'taxonomy_delimiter_mode', None),
            table_sep=getattr(args, 'taxonomy_table_sep', None),
            source_priority=getattr(args, 'taxonomy_source_priority', None),
            mapping_file=getattr(args, 'taxonomy_mapping_file', None),
            ignore_malformed=getattr(args, 'ignore_malformed', False),
            file_delimiter=getattr(args, 'table_sep', None),
        )
        taxa: List[str] = []
        tree_content = styler.get_tree_content()
        if tree_content:
            taxa = extract_taxa_from_newick(tree_content)
            # If the Nexus tree used a translate block, the extracted taxa are
            # translate IDs. Map them back to the original taxon names so that
            # downstream cross-validation and logging make sense.
            if styler._translate_block:
                translate_map = styler._parse_translate_block()
                id_to_name = {tid: name for name, tid in translate_map.items()}
                taxa = [id_to_name.get(t, t) for t in taxa]
            n_taxa = len(taxa)
            logger.info(f"{fname}: parsed successfully, {n_taxa} taxa detected")
            if n_taxa > 10000:
                logger.warning(
                    f"{fname}: large tree ({n_taxa} tips) — "
                    f"FigTree rendering may require significant memory. "
                    f"Consider using --low-memory mode."
                )
            _log_memory(f"after parsing {fname}")
        else:
            logger.warning(f"{fname}: parsed but no tree content found")

    # Low-memory mode acknowledgement
    if getattr(args, 'low_memory', False):
        logger.info(f"{fname}: low-memory mode enabled")

    # ── Analysis commands (print results and exit) ────────────────────
    analyze_rank = getattr(args, 'analyze_taxonomy', None)
    check_mono = getattr(args, 'check_monophyly', None)
    check_tax = getattr(args, 'check_taxonomy', False)

    if analyze_rank:
        # analyze_taxonomy() returns monophyletic / non_monophyletic as *dicts*
        # mapping group name -> clade info (not lists).  Pass the requested
        # rank so the analysis actually targets it (previously the rank was
        # ignored, and iterating the dict keys as if they were dicts crashed
        # with AttributeError when calling .get('group_name') on a string).
        result = styler.analyze_taxonomy(rank=analyze_rank)
        summary = result.get('summary', {})
        monophyletic = result.get('monophyletic', {})
        non_mono = result.get('non_monophyletic', {})
        print(f"\n=== Taxonomy Analysis Report (rank: {analyze_rank}) ===\n")
        print(f"Total labels: {summary.get('total_labels', 0)}")
        print(f"Mapped labels: {summary.get('mapped_labels', 0)}")
        print(f"Total groups: {summary.get('total_groups', 0)}")
        print(f"Monophyletic: {summary.get('monophyletic', 0)}")
        print(f"Non-monophyletic: {summary.get('non_monophyletic', 0)}")
        print(f"Monophyly rate: {summary.get('monophyly_rate', 0):.1f}%\n")
        if monophyletic:
            print("Monophyletic groups:")
            for name, info in monophyletic.items():
                n_taxa = len(info.get('resolved_taxa', info.get('taxa', [])))
                print(f"  {name} ({n_taxa} taxa)")
        if non_mono:
            print("\nNon-monophyletic groups:")
            for name, info in non_mono.items():
                n_taxa = len(info.get('resolved_taxa', info.get('taxa', [])))
                print(f"  {name} ({n_taxa} taxa)")
        print()
        return True

    if check_tax:
        completeness = styler.check_taxonomy_completeness()
        print(f"\n=== Taxonomy Completeness Report ===\n")
        total = completeness.get('coverage', 0)
        print(f"  Overall coverage: {total:.1f}%")
        print(f"  Complete: {len(completeness.get('complete', []))}")
        print(f"  Incomplete: {len(completeness.get('incomplete', []))}")
        print(f"  Missing: {len(completeness.get('missing', []))}\n")
        rank_cov = completeness.get('rank_coverage', {})
        if rank_cov:
            print("  Per-rank coverage:")
            for rank, pct in sorted(rank_cov.items()):
                bar = '#' * int(pct // 5) + '-' * (20 - int(pct // 5))
                print(f"    {rank:12s}  [{bar}]  {pct:.1f}%")
        print()
        return True

    if check_mono:
        import warnings as _cw
        print(f"\n=== Monophyly Check ===\n")
        for name in check_mono:
            with _cw.catch_warnings(record=True) as w:
                _cw.simplefilter("always")
                try:
                    res = styler.check_monophyly_by_group(name)
                    status = "MONOPHYLETIC" if res.get('is_monophyletic') else "NON-MONOPHYLETIC"
                    # 'group_size' is not a real key in the result; derive the
                    # size from the resolved taxa list instead.
                    size = len(res.get('resolved_taxa', []))
                    print(f"  {name}: {status} (group size: {size})")
                    for cwarn in w:
                        if issubclass(cwarn.category, CompatibilityWarning):
                            print(f"    ⚠ {cwarn.message}")
                except Exception as e:
                    print(f"  {name}: ERROR — {e}")
        print()
        return True

    if args.validate:
        with _StepTimer("Validating tree", logger):
            issues = styler.validate()
            if issues:
                for issue in issues:
                    logger.warning(f"{fname}: {issue}")
                return False
        # In validate-only mode, skip cross-validation and export
        if not getattr(args, 'sequences', None):
            return True

    # Cross-validation: tree tips vs sequence IDs
    seq_file = getattr(args, 'sequences', None)
    if seq_file and not getattr(args, 'no_cross_check', False):
        with _StepTimer("Cross-validating tree vs sequences", logger):
            from .validators import cross_validate_tree_sequence as cv
            seq_path = Path(seq_file)
            if not seq_path.exists():
                logger.error(f"{fname}: sequence file not found: {seq_file}")
                return False
            seq_ext = seq_path.suffix.lower()
            supported_seq_exts = {
                '.fasta', '.fa', '.fna', '.faa', '.ffn', '.frn',
                '.fastq', '.fq',
            }
            if seq_ext not in supported_seq_exts:
                logger.warning(f"{fname}: unsupported sequence format '{seq_ext}' for cross-validation")
            elif taxa:
                low_memory = getattr(args, 'low_memory', False)
                if low_memory:
                    logger.info(f"{fname}: streaming sequence IDs for cross-validation")
                    seq_ids: Iterator[str] = _iter_sequence_ids(seq_path)
                else:
                    seq_ids = list(_iter_sequence_ids(seq_path))
                cv_result = cv(taxa, seq_ids, label=fname)
                for err in cv_result["errors"]:
                    logger.error(f"{fname}: {err}")
                for w in cv_result["warnings"]:
                    logger.info(f"{fname}: {w}")
                if cv_result["errors"]:
                    logger.error(f"{fname}: tree-sequence cross-validation FAILED")
                    return False
                logger.info(f"{fname}: cross-validation passed ({cv_result['matched']} taxa matched)")

    # In validate-only mode (with or without cross-validation), return success
    if args.validate:
        return True

    if not output_override and not args.output:
        logger.error("--output is required when not using --validate")
        return False

    with _StepTimer("Applying style settings", logger):
        try:
            apply_cli_args(styler, args)
            settings = styler.get_settings()
            logger.debug(f"{fname}: {len(settings)} settings configured")
        except Exception as e:
            logger.error(f"{fname}: failed to apply style settings: {e}")
            return False

    # ── Custom params (--set) ─────────────────────────────────────────
    custom_params = getattr(args, 'custom_params', None)
    if custom_params:
        for cp in custom_params:
            if '=' not in cp:
                logger.error(f"{fname}: invalid --set format '{cp}' (expected KEY=VALUE)")
                return False
            key, val = cp.split('=', 1)
            try:
                styler.set_custom_param(key.strip(), _coerce_value(val.strip()))
            except Exception as e:
                logger.error(f"{fname}: failed to set '{key}': {e}")
                return False

    # ── Clade annotations: highlight / color / font / clear-hilights ──
    highlights = getattr(args, 'highlight', None)
    if highlights:
        for spec in highlights:
            parts = spec.split(':')
            taxa = [t.strip() for t in parts[0].split(',')]
            color = parts[1] if len(parts) > 1 else "#804548"
            width = float(parts[2]) if len(parts) > 2 else None
            offset = int(parts[3]) if len(parts) > 3 else None
            kw = dict(taxon_names=taxa, color=color)
            if width is not None:
                kw['width'] = width
            if offset is not None:
                kw['offset'] = offset
            styler.highlight_clade(**kw)

    color_clades = getattr(args, 'color_clade', None)
    if color_clades:
        color_all = getattr(args, 'color_all', False)
        for spec in color_clades:
            if ':' not in spec:
                logger.error(f"{fname}: --color-clade requires 'TAXA:HEXCOLOR' format")
                return False
            taxa_str, color = spec.rsplit(':', 1)
            taxa = [t.strip() for t in taxa_str.split(',')]
            if color_all:
                styler.set_clade_color_all(taxon_names=taxa, color=color)
            else:
                styler.set_clade_color(taxon_names=taxa, color=color)

    font_clades = getattr(args, 'font_clade', None)
    if font_clades:
        for spec in font_clades:
            if ':' not in spec:
                logger.error(f"{fname}: --font-clade requires 'TAXA:FONTNAME' format")
                return False
            taxa_str, font_spec = spec.rsplit(':', 1)
            taxa = [t.strip() for t in taxa_str.split(',')]
            fparts = font_spec.split('-')
            font_name = fparts[0]
            font_style = FontStyle.PLAIN
            font_size = None
            if len(fparts) > 1:
                style_map = {'PLAIN': FontStyle.PLAIN, 'BOLD': FontStyle.BOLD,
                             'ITALIC': FontStyle.ITALIC, 'BOLD_ITALIC': FontStyle.BOLD_ITALIC}
                font_style = style_map.get(fparts[1].upper(), FontStyle.PLAIN)
            if len(fparts) > 2:
                font_size = int(fparts[2])
            kw = dict(taxon_names=taxa, font_name=font_name, font_style=font_style)
            if font_size is not None:
                kw['font_size'] = font_size
            styler.set_clade_font(**kw)

    if getattr(args, 'clear_hilights', False):
        styler.clear_clade_hilights()

    # ── Auto-color by taxonomy rank ───────────────────────────────────
    auto_color_rank = getattr(args, 'auto_color', None)
    if auto_color_rank:
        with _StepTimer(f"Auto-coloring by rank '{auto_color_rank}'", logger):
            # Don't let analyze_taxonomy style anything (it would add
            # unwanted hilights and only color the MRCA branch); we apply
            # a unified palette ourselves via _color_groups_by_result so both
            # monophyletic and non-monophyletic groups get colored, matching
            # the gold standard's set_clade_color_all + per-terminal approach.
            result = styler.analyze_taxonomy(
                rank=auto_color_rank, style_monophyletic=False,
            )
            _color_groups_by_result(fname, styler, result, logger)

    # ── Taxon-level collapses (--collapse-taxa) ───────────────────────
    collapse_taxa = getattr(args, 'collapse_taxa', None)
    if collapse_taxa:
        for spec in collapse_taxa:
            try:
                taxa, label, collapse_type = _parse_collapse_taxa_spec(spec)
            except ValueError as e:
                logger.error(f"{fname}: {e}")
                return False
            styler.collapse_clade(
                taxon_names=taxa, label=label, collapse_type=collapse_type
            )

    # ── Rank-level collapses (--collapse-rank) ────────────────────────
    collapse_rank = getattr(args, 'collapse_rank', None)
    if collapse_rank:
        strict = getattr(args, 'strict', False)
        collapse_style = getattr(args, 'collapse_style', 'collapse')

        # Step 1: auto-color terminals by phylum so collapsed
        # subtrees inherit the color annotations from the original ref_test.
        # Use style_monophyletic=False to avoid analyze_taxonomy adding
        # unwanted hilights; we apply a unified palette ourselves below so
        # both monophyletic and non-monophyletic phyla get colored.
        with _StepTimer(f"Auto-coloring by phylum before collapse", logger):
            # Step 1: auto-color terminals by phylum so collapsed subtrees
            # inherit the color annotations from the original ref_test.
            # Use style_monophyletic=False to avoid analyze_taxonomy adding
            # unwanted hilights; _color_groups_by_result applies a unified
            # palette so both monophyletic and non-monophyletic phyla get
            # colored.  The returned mapping (phylum -> member taxa) is used
            # by Step 2 to find each collapsed group's parent phylum.
            color_result = styler.analyze_taxonomy(
                rank='phylum', style_monophyletic=False,
            )
            phylum_taxa_sets, color_map = _color_groups_by_result(
                fname, styler, color_result, logger
            )

        # Step 2: collapse at the target rank.
        # For embedded format A group names (e.g. "_Halobacteria"),
        # use the raw name for taxonomy lookup but strip underscores
        # from the display label so FigTree annotation parsing succeeds.
        with _StepTimer(f"Collapsing all groups at rank '{collapse_rank}'", logger):
            import warnings as _warnings
            # style_monophyletic=False: we only need the monophyly result to
            # decide which groups to collapse; no styling side-effects wanted.
            result = styler.analyze_taxonomy(
                rank=collapse_rank, style_monophyletic=False,
            )
            for group_name, entry in result.get('monophyletic', {}).items():
                if _terminator.interrupted:
                    return False
                display_label = group_name.strip('_')
                if display_label != group_name:
                    pass  # will pass strip-ed label to collapse

                _terminator.current_step = f"collapsing '{group_name}'"
                _collapse_succeeded = False
                with _warnings.catch_warnings(record=True) as w:
                    _warnings.simplefilter("always")
                    try:
                        styler.collapse_by_group(
                            group_name, collapse_type=collapse_style,
                            label=display_label if display_label != group_name else None
                        )
                        _collapse_succeeded = True
                    except ValidationError as e:
                        if strict:
                            logger.error(f"{fname}: cannot collapse '{group_name}': {e}")
                            return False
                        logger.warning(f"{fname}: cannot collapse '{group_name}': {e} — skipping")
                    compat = [x for x in w if issubclass(x.category, CompatibilityWarning)]
                    if compat:
                        msg = str(compat[0].message)
                        if strict:
                            logger.error(f"{fname}: {msg}")
                            return False
                        logger.warning(f"{fname}: {msg} — skipping collapse")
                        _collapse_succeeded = False
                    else:
                        logger.info(f"{fname}: collapsed group '{group_name}'")

                # ── Post-color the collapse node ──
                # After collapse_by_group, read the actual target_taxa that
                # check_monophyly_by_group resolved (which may differ from
                # analyze_taxonomy's taxa — e.g. 'Hydrothermarchaeota' as a
                # class has 1 taxon, but check_monophyly_by_group also picks
                # up the phylum-level taxon). Use the ACTUAL collapse taxa to
                # paint the MRCA, so the collapsed triangle gets a !color.
                if _collapse_succeeded and styler._settings._collapses:
                    actual_taxa = styler._settings._collapses[-1].target_taxa
                    if actual_taxa:
                        actual_set = set(actual_taxa)
                        parent_phylum = ''
                        for phylum_name, ptaxa in phylum_taxa_sets.items():
                            if actual_set.issubset(ptaxa):
                                parent_phylum = phylum_name
                                break
                        # Fallback: if taxa span multiple phyla, use the
                        # phylum of the first taxon (matches gold standard's
                        # behavior of coloring by the clade's dominant phylum)
                        if not parent_phylum:
                            for phylum_name, ptaxa in phylum_taxa_sets.items():
                                if actual_set & ptaxa:
                                    parent_phylum = phylum_name
                                    break
                        clade_color = color_map.get(parent_phylum, '#999999') if parent_phylum else '#999999'
                        try:
                            styler.set_clade_color_all(
                                taxon_names=actual_taxa, color=clade_color,
                            )
                        except Exception:
                            pass

    # Apply clade collapses (requires taxonomy-aware pattern or mapping)
    clade_names = getattr(args, 'clade', None)
    if clade_names:
        strict = getattr(args, 'strict', False)
        with _StepTimer("Collapsing clades", logger):
            import warnings as _warnings
            for clade_name in clade_names:
                if _terminator.interrupted:
                    return False
                _terminator.current_step = f"collapsing '{clade_name}'"
                with _warnings.catch_warnings(record=True) as w:
                    _warnings.simplefilter("always")
                    try:
                        styler.collapse_by_group(clade_name)
                    except ValidationError as e:
                        logger.error(f"{fname}: cannot collapse '{clade_name}': {e}")
                        return False
                    compat = [x for x in w if issubclass(x.category, CompatibilityWarning)]
                    if compat:
                        msg = str(compat[0].message)
                        if strict:
                            logger.error(f"{fname}: {msg}")
                            return False
                        else:
                            logger.warning(f"{fname}: {msg} — skipping collapse")
                    else:
                        logger.info(f"{fname}: collapsed clade '{clade_name}'")

    output_path = output_override or args.output
    output = Path(output_path)

    # Strip annotations if requested (before export, after all processing)
    if getattr(args, 'strip_annotations', False):
        with _StepTimer("Stripping annotations", logger):
            styler.strip_annotations()
            logger.info(f"{fname}: stripped bracket annotations from tree")

    if output.exists() and output.is_dir():
        logger.error(
            f"{fname}: output path must be a file, but '{output}' is a directory"
        )
        return False

    # --force / --no-clobber handling
    force = getattr(args, 'force', False)
    no_clobber = getattr(args, 'no_clobber', False)
    if output.exists() and not force:
        if no_clobber:
            logger.info(f"{fname}: output {output} exists, skipping (--no-clobber)")
            return True
        else:
            logger.error(
                f"{fname}: output file already exists: {output}. "
                f"Use --force to overwrite or --no-clobber to skip."
            )
            return False

    # Auto-create output directory
    output.parent.mkdir(parents=True, exist_ok=True)

    with _StepTimer(f"Exporting to {output.name}", logger):
        try:
            styler.export(str(output), single_tree=single_tree)
            logger.info(f"{fname} -> {output}")
        except ExportError as e:
            logger.error(f"{fname}: export failed: {e}")
            return False
        except Exception as e:
            logger.error(f"{fname}: unexpected export error: {e}")
            return False

    if args.render:
        render_path = Path(args.render)
        if render_path.exists() and render_path.is_dir():
            logger.error(
                f"{fname}: render path must be a file, but '{render_path}' is a directory"
            )
            return False
        with _StepTimer("Rendering image", logger):
            try:
                render_format = args.render_format
                if not render_format:
                    ext = os.path.splitext(args.render)[1].upper()
                    format_map = {'.PNG': 'PNG', '.PDF': 'PDF', '.SVG': 'SVG',
                                  '.JPG': 'JPEG', '.JPEG': 'JPEG'}
                    render_format = format_map.get(ext, 'PNG')
                styler.render(
                    args.render,
                    format=render_format,
                    width=args.render_width,
                    height=args.render_height,
                    jar_path=args.figtree_jar,
                    keep_nex=False,
                )
                logger.info(f"{fname} -> {args.render}")
            except ExportError as e:
                logger.error(f"Rendering failed: {e}")
                return False

    return True


def _add_suffix_to_path(output_path: str, suffix: str) -> str:
    """Append a suffix before the file extension.

    Examples:
        ``_add_suffix_to_path("out.nex", "_tree2")`` → ``"out_tree2.nex"``
    """
    p = Path(output_path)
    return str(p.with_stem(p.stem + suffix))


def _process_single(input_path: Path, args: argparse.Namespace) -> bool:
    """Process a single tree file. Returns True on success."""
    fname = input_path.name
    total_start = time.perf_counter()

    if _terminator.interrupted:
        return False

    # Step 1: Basic input file validation
    _terminator.current_step = f"validating {fname}"
    with _StepTimer("Input file validation", logger):
        vresult = validate_input_file(str(input_path))
        if not vresult["valid"]:
            for err in vresult["errors"]:
                logger.error(f"{fname}: {err}")
            return False
        for w in vresult["warnings"]:
            logger.warning(f"{fname}: {w}")
        fmt = vresult["format"]
        size = vresult["size_bytes"]
        logger.debug(f"{fname}: detected format={fmt}, size={size} bytes")

    if _terminator.interrupted:
        return False

    # Step 2: Deep format-specific validation
    _terminator.current_step = f"deep-validating {fname}"
    summaries: list = []
    if fmt == 'newick':
        with _StepTimer("Deep Newick validation", logger):
            with open(input_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            dv = deep_validate_newick(content, label=fname)
            for err in dv["errors"]:
                logger.error(f"{fname}: {err}")
            for w in dv["warnings"]:
                logger.warning(f"{fname}: {w}")
            if dv["errors"]:
                return False
            logger.info(
                f"{fname}: {dv['leaf_count']} leaves, "
                f"{dv['node_count']} nodes"
            )

    elif fmt == 'nexus':
        with _StepTimer("Deep Nexus validation", logger):
            summaries = summarize_nexus_trees(str(input_path))
            if len(summaries) > 1:
                logger.warning(
                    f"{fname}: Nexus file contains {len(summaries)} trees"
                )
                for ts in summaries:
                    neg_tag = " [has NEGATIVE branch lengths!]" if ts["has_negative_bl"] else ""
                    logger.warning(
                        f"  tree '{ts['name']}': "
                        f"{ts['leaf_count']} leaves{neg_tag}"
                    )
            for ts in summaries:
                if ts["has_negative_bl"]:
                    logger.error(
                        f"{fname}: tree '{ts['name']}' has negative branch "
                        f"lengths — CRITICAL, aborting"
                    )
                    return False

    elif fmt == 'fasta':
        with _StepTimer("Deep FASTA validation", logger):
            mol_type = getattr(args, 'mol_type', None)
            skip_len = getattr(args, 'skip_length_check', False)
            dv = deep_validate_fasta(
                str(input_path),
                expected_alphabet=mol_type,
                check_alignment=not skip_len,
            )
            for err in dv["errors"]:
                logger.error(f"{fname}: {err}")
            for w in dv["warnings"]:
                logger.warning(f"{fname}: {w}")
            if dv["errors"]:
                return False
            logger.info(
                f"{fname}: {dv['sequence_count']} sequences, "
                f"alphabet={dv['alphabet']}"
            )

    elif fmt == 'fastq':
        with _StepTimer("Deep FASTQ validation", logger):
            mol_type = getattr(args, 'mol_type', None)
            dv = deep_validate_fastq(
                str(input_path), expected_alphabet=mol_type,
            )
            for err in dv["errors"]:
                logger.error(f"{fname}: {err}")
            for w in dv["warnings"]:
                logger.warning(f"{fname}: {w}")
            if dv["errors"]:
                return False
            logger.info(
                f"{fname}: {dv['read_count']} reads, "
                f"alphabet={dv['alphabet']}"
            )

    if fmt not in ('newick', 'nexus'):
        # When --validate is used with a sequence file (FASTA/FASTQ) and the
        # deep validation passed (no errors returned above), the user's intent
        # was to validate the sequence file — return success rather than
        # failing because it's not a tree format.
        if args.validate and fmt in ('fasta', 'fastq'):
            logger.info(
                f"{fname}: sequence validation passed "
                f"(format={fmt})"
            )
            return True
        logger.error(
            f"{fname}: detected format '{fmt}' is not a tree format. "
            f"FigTreeKit requires a Newick or Nexus tree file as the main input."
        )
        return False

    if _terminator.interrupted:
        return False

    # Step 3: Multi-tree detection
    if fmt != 'nexus':
        with _StepTimer("Scanning for multiple trees", logger):
            tree_count = _detect_tree_count(input_path)
            if tree_count < 0:
                logger.error(f"{fname}: could not read file to count trees")
                return False
            if tree_count == 0:
                logger.error(f"{fname}: no trees found in the file")
                return False
            logger.debug(f"{fname}: found {tree_count} tree(s)")
    else:
        tree_count = len(summaries) if summaries else 1

    # Newick files cannot encode multiple named trees, so multi-tree extraction
    # modes are only valid for Nexus inputs.  A concatenated Newick file with
    # several semicolon-terminated trees is detected by _detect_tree_count but
    # is explicitly unsupported here (consistent with the documented model).
    if fmt == 'newick' and tree_count > 1 and args.multi_tree:
        logger.error(
            f"{fname}: --multi-tree is not supported for Newick files "
            f"(found {tree_count} concatenated tree(s)). "
            f"Convert the input to Nexus format to process multiple trees."
        )
        return False

    single_tree_mode = tree_count > 1 and args.multi_tree is not None

    # Step 4: Resolve tree indices
    indices = _resolve_tree_indices(
        args.multi_tree, tree_count, fname, seed=getattr(args, 'seed', None)
    )
    if indices is None:
        return False

    # Step 5: Process each selected tree
    if len(indices) == 1:
        _terminator.current_step = f"processing {fname}"
        ok = _process_single_tree(
            input_path, args, indices[0], single_tree=single_tree_mode
        )
    else:
        ok_count = 0
        fail_count = 0
        for i, idx in enumerate(indices):
            if _terminator.interrupted:
                logger.warning(f"Interrupted after {ok_count} tree(s) completed")
                return False
            _terminator.current_step = f"tree {idx + 1}/{tree_count} of {fname}"
            logger.info(
                f"--- Processing tree {idx + 1}/{tree_count} (index {idx})"
            )
            suffix = f"_tree{idx + 1}"
            if args.output:
                out = _add_suffix_to_path(args.output, suffix)
            else:
                out = None
            if _process_single_tree(
                input_path, args, idx, output_override=out, single_tree=single_tree_mode
            ):
                ok_count += 1
            else:
                fail_count += 1
        if fail_count:
            logger.warning(
                f"Multi-tree: {ok_count} succeeded, {fail_count} failed "
                f"out of {len(indices)} trees"
            )
        else:
            logger.info(
                f"Multi-tree: all {len(indices)} trees processed successfully"
            )
        ok = fail_count == 0

    total_elapsed = time.perf_counter() - total_start
    status = "DONE" if ok else "FAILED"
    logger.info(f"{fname}: {status} (total {total_elapsed:.2f} s)")
    if ok:
        _terminator.files_processed += 1
    _terminator.current_step = ""
    return ok


# ── Batch processing ────────────────────────────────────────────────────

def _process_batch(input_dir: Path, args: argparse.Namespace) -> bool:
    """Process all tree files in a directory. Returns True on success."""
    extensions = {'.tre', '.tree', '.nwk', '.newick', '.nex', '.nexus'}
    tree_files = sorted(
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in extensions
    )
    if not tree_files:
        logger.error(f"No tree files found in {input_dir}")
        raise FileNotFoundError(f"No tree files found in {input_dir}")

    _terminator.files_total = len(tree_files)
    logger.info(f"Found {len(tree_files)} tree file(s) in {input_dir}")

    if args.validate:
        output_dir = None
    elif args.output:
        output_dir = Path(args.output)
        if output_dir.exists() and not output_dir.is_dir():
            logger.error(
                f"Batch output path must be a directory, but '{output_dir}' is a file"
            )
            return False
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = input_dir / "styled"
        output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from tqdm import tqdm
        iterator = tqdm(tree_files, desc="Processing", unit="file")
    except ImportError:
        iterator = tree_files

    batch_start = time.perf_counter()
    ok, fail = 0, 0
    for tree_file in iterator:
        if _terminator.interrupted:
            logger.warning(
                f"Interrupted — {ok} completed, {fail} failed, "
                f"{len(tree_files) - ok - fail} skipped"
            )
            break
        if args.validate:
            if _process_single(tree_file, args):
                ok += 1
            else:
                fail += 1
        else:
            args_copy = argparse.Namespace(**vars(args))
            args_copy.output = str(output_dir / f"{tree_file.stem}.nex")
            if args.render:
                render_path = Path(args.render)
                args_copy.render = str(
                    render_path.parent / f"{tree_file.stem}{render_path.suffix}"
                )
            if _process_single(tree_file, args_copy):
                ok += 1
            else:
                fail += 1

    batch_elapsed = time.perf_counter() - batch_start
    if fail:
        logger.warning(
            f"Batch complete: {ok} succeeded, {fail} failed "
            f"out of {len(tree_files)} in {batch_elapsed:.2f} s"
        )
    else:
        logger.info(
            f"Batch complete: all {len(tree_files)} files processed "
            f"in {batch_elapsed:.2f} s"
        )
    return fail == 0


# ── Self-test ───────────────────────────────────────────────────────────

# Built-in example trees for self-test
_EXAMPLE_NEWICK = (
    "((GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota_c_Cyanobacteriia"
    "_o_Cyanobacteriales_f_Prochloraceae_g_Prochloron:0.1,"
    "GB_GCA_000317225.1_d_Bacteria_p_Cyanobacteriota_c_Cyanobacteriia"
    "_o_Cyanobacteriales_f_Prochloraceae_g_Prochlorococcus:0.2):0.3,"
    "RS_GCF_000013425.1_d_Archaea_p_Euryarchaeota_c_Methanomicrobia"
    "_o_Methanosarcinales_f_Methanosarcinaceae_g_Methanosarcina:0.4);"
)

_EXAMPLE_FASTA = ">seq1\nACGTACGT\n>seq2\nACGTACGT\n>seq3\nTTTTCCCC\n"


def _run_self_test() -> None:
    """Run self-diagnostic checks and print [PASS]/[FAIL] table."""
    results: List[List[str]] = []

    def _check(name: str, func):
        """Run a check function and record the result."""
        try:
            ok, detail = func()
            status = "PASS" if ok else "FAIL"
        except Exception as e:
            status = "FAIL"
            detail = str(e)
        results.append([name, status, detail])

    # 1. Dependency: biopython
    def _check_biopython_fallback():
        try:
            import Bio
            ver = Bio.__version__
            major, minor = ver.split(".")[:2]
            ok = int(major) >= 1 and int(minor) >= 80
            return ok, f"biopython {ver} (requires >=1.80,<2.0)"
        except Exception as e:
            return False, f"import failed: {e}"

    _check("Dependency: biopython", _check_biopython_fallback)

    # 2. Dependency: python version
    def _check_python():
        ver = sys.version.split()[0]
        major, minor = sys.version_info[:2]
        ok = (major, minor) >= (3, 11)
        return ok, f"python {ver} (requires >=3.11)"

    _check("Dependency: python", _check_python)

    # 3. Newick parsing
    def _check_newick_parse():
        from Bio import Phylo
        import io
        tree = list(Phylo.parse(io.StringIO(_EXAMPLE_NEWICK), "newick"))
        ok = len(tree) == 1
        leaves = [t.name for t in tree[0].get_terminals()]
        return ok, f"parsed {len(leaves)} leaves from example Newick"

    _check("Parse: Newick example", _check_newick_parse)

    # 4. Taxonomy extraction (format A embedded)
    def _check_taxonomy_extract():
        from .taxonomy import parse_taxonomy_auto
        label = (
            "GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota"
            "_c_Cyanobacteriia_o_Cyanobacteriales"
            "_f_Prochloraceae_g_Prochloron"
        )
        tax = parse_taxonomy_auto(label)
        ok = (
            tax.get("domain") == "Bacteria"
            and tax.get("phylum") == "Cyanobacteriota"
            and tax.get("genus") == "Prochloron"
        )
        return ok, f"domain={tax.get('domain')}, genus={tax.get('genus')}"

    _check("Taxonomy: embedded format extraction", _check_taxonomy_extract)

    # 5. Taxonomy extraction (format B table)
    def _check_taxonomy_table():
        from .taxonomy import parse_taxonomy_auto
        label = "d__Archaea;p__Euryarchaeota;c__Methanomicrobia;o__Methanosarcinales;f__Methanosarcinaceae;g__Methanosarcina;s__"
        tax = parse_taxonomy_auto(label)
        ok = (
            tax.get("domain") == "Archaea"
            and tax.get("phylum") == "Euryarchaeota"
            and tax.get("species", "") == ""
        )
        return ok, f"domain={tax.get('domain')}, species_empty={tax.get('species', '') == ''}"

    _check("Taxonomy: table format extraction", _check_taxonomy_table)

    # 6. Monophyly check — Cyanobacteriales should be monophyletic
    def _check_monophyly_mono():
        styler = FigTreeStyler().load_content(_EXAMPLE_NEWICK)
        result = styler.check_monophyly_by_group("Cyanobacteriales")
        ok = result["is_monophyletic"] and len(result["resolved_taxa"]) == 2
        return ok, f"monophyletic={result['is_monophyletic']}, taxa={len(result['resolved_taxa'])}"

    _check("Monophyly: Cyanobacteriales (monophyletic)", _check_monophyly_mono)

    # 7. Monophyly check — LUCA should resolve to Bacteria+Archaea
    def _check_luca():
        styler = FigTreeStyler().load_content(_EXAMPLE_NEWICK)
        result = styler.check_monophyly_by_group("LUCA")
        ok = result["is_monophyletic"] and len(result["resolved_taxa"]) == 3
        return ok, f"resolved {len(result['resolved_taxa'])} taxa (all 3 = Bacteria+Archaea)"

    _check("Special ID: LUCA resolves all taxa", _check_luca)

    # 8. Monophyly check — LACA should resolve to Archaea only
    def _check_laca():
        styler = FigTreeStyler().load_content(_EXAMPLE_NEWICK)
        result = styler.check_monophyly_by_group("LACA")
        ok = len(result["resolved_taxa"]) == 1
        return ok, f"resolved {len(result['resolved_taxa'])} taxon (Archaea only)"

    _check("Special ID: LACA resolves Archaea only", _check_laca)

    # 9. Export round-trip
    def _check_export():
        import tempfile, os
        styler = FigTreeStyler().load_content(_EXAMPLE_NEWICK)
        styler.set_layout(LayoutType.POLAR)
        styler.highlight_clade(
            ["GB_GCA_000252485.1_d_Bacteria_p_Cyanobacteriota_c_Cyanobacteriia"
             "_o_Cyanobacteriales_f_Prochloraceae_g_Prochloron",
             "GB_GCA_000317225.1_d_Bacteria_p_Cyanobacteriota_c_Cyanobacteriia"
             "_o_Cyanobacteriales_f_Prochloraceae_g_Prochlorococcus"],
            color="#FF0000",
        )
        with tempfile.NamedTemporaryFile(suffix=".nex", delete=False) as f:
            path = f.name
        os.chmod(path, 0o600)
        try:
            styler.export(path)
            content = open(path, encoding="utf-8").read()
            ok = "#NEXUS" in content and "begin figtree;" in content
            return ok, f"exported {len(content)} bytes, has Nexus structure"
        finally:
            os.unlink(path)

    _check("Export: Newick → Nexus round-trip", _check_export)

    # 10. FASTA validation
    def _check_fasta():
        import tempfile, os
        from .validators import deep_validate_fasta
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fasta", delete=False) as f:
            f.write(_EXAMPLE_FASTA)
            path = f.name
        os.chmod(path, 0o600)
        try:
            result = deep_validate_fasta(path)
            ok = result["sequence_count"] == 3 and result["alphabet"] == "DNA"
            return ok, f"{result['sequence_count']} seqs, alphabet={result['alphabet']}"
        finally:
            os.unlink(path)

    _check("Validation: FASTA example", _check_fasta)

    # 11. Adversarial: control char detection
    def _check_adversarial():
        from .validators import scan_for_anomalous_content
        errors = scan_for_anomalous_content("Hello\x00World", label="test", source="test")
        ok = len(errors) > 0 and "U+0000" in errors[0]
        return ok, f"detected {len(errors)} issue(s)"

    _check("Security: control char detection", _check_adversarial)

    # ── Print results ──
    print()
    print("=" * 70)
    print("  FigTreeKit Self-Test Results")
    print("=" * 70)
    print()

    max_name = max(len(r[0]) for r in results)
    max_detail = max(len(r[2]) for r in results)

    for name, status, detail in results:
        status_str = f"[{status}]"
        print(f"  {status_str:<8} {name:<{max_name}}  {detail}")

    print()
    print("-" * 70)

    pass_count = sum(1 for r in results if r[1] == "PASS")
    fail_count = sum(1 for r in results if r[1] == "FAIL")
    total = len(results)

    if fail_count == 0:
        print(f"  All {total} checks passed.")
    else:
        print(f"  {pass_count}/{total} passed, {fail_count} FAILED.")

    print("=" * 70)
    print()

    sys.exit(ExitCode.SUCCESS if fail_count == 0 else ExitCode.GENERAL_ERROR)


# ── FigTree setup ───────────────────────────────────────────────────────

def _handle_setup_figtree(args: argparse.Namespace) -> None:
    """Handle --setup-figtree flag."""
    from ._figtree_setup import (
        setup_figtree, print_setup_status,
        DEFAULT_INSTALL_DIR
    )
    
    if args.check_figtree:
        print_setup_status()
        return
    
    try:
        setup_figtree(
            install_dir=DEFAULT_INSTALL_DIR,
            jar_path=args.figtree_jar,
            verbose=True,
        )
    except RenderError as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(ExitCode.GENERAL_ERROR)


# ── Logo ────────────────────────────────────────────────────────────────

def _build_logo() -> str:
    from . import __version__, __license__, __version_date__, __git_hash__
    import datetime
    date_str = __version_date__ or datetime.date.today().isoformat()
    version_str = f"v{__version__}"
    if __git_hash__:
        version_str += f" (git: {__git_hash__})"
    return (
        "\n"
        "  ███████╗██╗ ██████╗ ████████╗██████╗ ███████╗███████╗██╗  ██╗██╗████████╗\n"
        "  ██╔════╝██║██╔════╝ ╚══██╔══╝██╔══██╗██╔════╝██╔════╝██║ ██╔╝██║╚══██╔══╝\n"
        "  █████╗  ██║██║  ███╗   ██║   ██████╔╝█████╗  █████╗  █████╔╝ ██║   ██║\n"
        "  ██╔══╝  ██║██║   ██║   ██║   ██╔══██╗██╔══╝  ██╔══╝  ██╔═██╗ ██║   ██║\n"
        "  ██║     ██║╚██████╔╝   ██║   ██║  ██║███████╗███████╗██║  ██╗██║   ██║\n"
        "  ╚═╝     ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝\n"
        f"\n  {__license__} License | {version_str} | {date_str}"
        "\n"
        "\n  Dependencies:"
        "\n    biopython  BSD-3-Clause  (required)"
        "\n    psutil     BSD-3-Clause  (optional, memory logging)"
        "\n    tqdm       MIT           (optional, progress bars)"
        "\n    FigTree    GPLv2         (optional, image rendering)"
        "\n"
    )


LOGO = _build_logo()


# ── Main entry point ────────────────────────────────────────────────────

def main() -> None:
    parser = create_cli_parser()
    args = parser.parse_args()

    # Register signal handlers for graceful termination
    _terminator.register()

    # Show logo unless in quiet mode
    if not args.quiet and not (args.setup_figtree or args.check_figtree):
        sys.stdout.write(LOGO + "\n")
        sys.stdout.flush()

    # Handle setup-figtree
    if args.setup_figtree or args.check_figtree:
        _handle_setup_figtree(args)
        return

    # Handle --self-test
    if args.self_test:
        _run_self_test()
        return
    
    # Require input for main command
    if not args.input:
        parser.print_help()
        sys.exit(ExitCode.USAGE_ERROR)  # exit 2: parameter/usage error

    # Configure real-time logger
    global logger
    logger = setup_logger(
        quiet=args.quiet, verbose=args.verbose,
        log_file=getattr(args, 'log_file', None),
    )

    # Apply custom taxonomy level extensions
    if args.taxonomy_levels:
        from .taxonomy import extend_rank_prefixes
        extra: dict = {}
        for pair in args.taxonomy_levels.split(","):
            pair = pair.strip()
            if ":" in pair:
                prefix, rank = pair.split(":", 1)
                extra[prefix.strip()] = rank.strip()
            elif pair:
                logger.warning(f"Ignoring invalid taxonomy-level spec: '{pair}'")
        if extra:
            extend_rank_prefixes(extra)
            logger.info(f"Extended taxonomy levels: {extra}")

    try:
        input_path = Path(args.input)
        if input_path.is_dir():
            if not _process_batch(input_path, args):
                sys.exit(ExitCode.DATA_ERROR)  # exit 3: data/content error
        else:
            _terminator.files_total = 1
            if not _process_single(input_path, args):
                sys.exit(ExitCode.DATA_ERROR)  # exit 3: data/content error
    except _UsageError:
        sys.exit(ExitCode.USAGE_ERROR)  # exit 2: usage/parameter error
    except FileNotFoundError as e:
        logger.error(f"{e}")
        sys.exit(ExitCode.DATA_ERROR)  # exit 3: data/content error
    except SystemExit:
        raise  # preserve explicit sys.exit() codes
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(ExitCode.GENERAL_ERROR)  # exit 1: unexpected/internal error
    finally:
        _terminator.unregister()
