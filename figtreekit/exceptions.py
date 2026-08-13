"""Exception hierarchy for FigTreeKit."""

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

from typing import Optional


class FigTreeKitError(Exception):
    """Base exception for all FigTreeKit errors."""
    pass


class ParseError(FigTreeKitError):
    """Raised when Newick/Nexus parsing fails.

    Attributes:
        line: Approximate line number where the error occurred, if known.
        column: Approximate column number, if known.
    """

    def __init__(self, message: str, line: Optional[int] = None, column: Optional[int] = None):
        self.line = line
        self.column = column
        if line is not None or column is not None:
            position = "line"
            if line is not None:
                position += f" {line}"
            if column is not None:
                position += f", column {column}"
            super().__init__(f"Parse error at {position}: {message}")
        else:
            super().__init__(message)


class ValidationError(FigTreeKitError):
    """Raised when input validation fails (e.g., invalid color, empty taxon list)."""
    pass


class ExportError(FigTreeKitError):
    """Raised when Nexus file export fails."""
    pass


class RenderError(ExportError):
    """Raised when FigTree JAR rendering or renderer setup fails.

    Covers renderer-lifecycle failures such as a missing Java runtime,
    a failed FigTree source download, a failed Ant compilation, or a
    non-zero exit from the headless ``-graphic`` rendering call. Callers
    that only need the core Nexus-export functionality never touch this
    exception, since rendering is an optional, Java-dependent feature.

    Subclasses :class:`ExportError` so existing ``except ExportError``
    handlers continue to catch rendering failures.
    """
    pass


class CompatibilityWarning(UserWarning):
    """Warning for issues that may cause FigTree to render incorrectly."""
    pass


# ── Standardized aliases for library-mode API (§8.2) ───────────────────
# These provide the exception names required by the development spec,
# mapped to the existing hierarchy for backward compatibility.

class PhyloFormatError(ParseError):
    """Raised when a phylogenetic file format is invalid or unrecognized.

    Alias of :class:`ParseError` for the standardized library API. Despite
    the name, this is a *parse-level* failure (the file cannot be read as
    Newick/Nexus at all), not a semantic validation failure — content-level
    problems (negative branches, duplicate tips, ...) raise
    :class:`ValidationError` instead.
    """
    pass


class TaxonomyConflictError(ValidationError):
    """Raised when taxonomy data conflicts (e.g., circular dependencies).

    Alias of :class:`ValidationError` for the standardized library API.
    """
    pass


class MonophylyError(ValidationError):
    """Raised when monophyly analysis fails (e.g., taxa not found on tree).

    Alias of :class:`ValidationError` for the standardized library API.
    """
    pass
