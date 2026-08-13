"""FigTree rendering integration for FigTreeKit.

This module provides functionality to render Nexus files to images
using FigTree's command-line interface.

Note:
    Rendering requires a compiled FigTree JAR file. The patched FigTree
    JAR included with FigTreeKit is licensed under GPL-2.0-or-later (and
    includes iText, licensed under AGPL-3.0, for PDF export). Users can
    either use the bundled patched JAR, run ``figtreekit setup-figtree``
    to download and compile FigTree from source, or set the
    ``FIGTREE_JAR`` environment variable to an existing JAR path.

    See: http://tree.bio.ed.ac.uk/software/figtree/
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

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from .exceptions import ExportError, RenderError


def find_figtree_jar() -> Optional[str]:
    """Attempt to locate the FigTree JAR file.

    Searches in the following order:
    1. ``FIGTREE_JAR`` environment variable
    2. Saved path from ``figtreekit setup-figtree``
    3. Bundled patched JAR shipped with FigTreeKit (``figtreekit/figtree_patched.jar``)
    4. ``FIGTREE_HOME`` environment variable / ``dist/figtree.jar``
    5. Default install location (``~/.figtreekit/figtree/dist/figtree.jar``)
    6. Current working directory / ``FigTree-1.4.4/dist/figtree.jar``
    7. FigTreeKit package directory / ``FigTree-1.4.4/dist/figtree.jar``

    Returns:
        Path to figtree.jar if found, ``None`` otherwise.
    """
    # 1. Environment variable (highest priority)
    env_jar = os.environ.get("FIGTREE_JAR")
    if env_jar and os.path.isfile(env_jar):
        return env_jar

    # 2. Saved path from setup-figtree
    try:
        from ._figtree_setup import get_saved_figtree_path
        saved = get_saved_figtree_path()
        if saved and saved.is_file():
            return str(saved)
    except ImportError:
        pass

    # 3. Bundled patched FigTree JAR shipped with FigTreeKit
    bundled_jar = Path(__file__).with_name("figtree_patched.jar")
    if bundled_jar.is_file():
        return str(bundled_jar)

    # 4. FIGTREE_HOME
    figtree_home = os.environ.get("FIGTREE_HOME")
    if figtree_home:
        candidate = os.path.join(figtree_home, "dist", "figtree.jar")
        if os.path.isfile(candidate):
            return candidate

    # 5. Default install location
    default_install = Path.home() / ".figtreekit" / "figtree" / "dist" / "figtree.jar"
    if default_install.is_file():
        return str(default_install)

    # 6. Current working directory
    cwd_candidate = os.path.join(os.getcwd(), "FigTree-1.4.4", "dist", "figtree.jar")
    if os.path.isfile(cwd_candidate):
        return cwd_candidate

    # 7. FigTreeKit package directory / FigTree-1.4.4/dist/figtree.jar
    pkg_dir = Path(__file__).parent
    pkg_candidate = pkg_dir / "FigTree-1.4.4" / "dist" / "figtree.jar"
    if pkg_candidate.is_file():
        return str(pkg_candidate)

    return None


def check_java_available() -> bool:
    """Check if Java is available on the system."""
    return shutil.which("java") is not None


def get_figtree_not_found_message() -> str:
    """Get a helpful error message when FigTree JAR is not found."""
    return (
        "FigTree JAR not found. To enable rendering:\n\n"
        "Option 1: Use the patched JAR bundled with FigTreeKit\n"
        "  Ensure figtreekit/figtree_patched.jar is present, or reinstall FigTreeKit.\n\n"
        "Option 2: Auto-setup\n"
        "  figtreekit setup-figtree\n\n"
        "Option 3: Use existing JAR\n"
        "  figtreekit setup-figtree --path /path/to/figtree.jar\n"
        "  # or set environment variable:\n"
        "  export FIGTREE_JAR=/path/to/figtree.jar\n\n"
        "Option 4: Compile manually\n"
        "  1. Download FigTree: https://github.com/rambaut/figtree\n"
        "  2. Install Apache Ant: brew install ant (macOS)\n"
        "  3. Compile: cd figtree-1.4.4 && ant dist\n"
        "  4. Set FIGTREE_JAR environment variable\n\n"
        "Note: FigTreeKit core features work without FigTree.\n"
        "Only --render requires FigTree (GPL-2.0-or-later) + Java 8+.\n\n"
        "FigTree citation: Rambaut (2018) FigTree v1.4.4\n"
        "http://tree.bio.ed.ac.uk/software/figtree/"
    )


def render_with_figtree(
    input_file: str,
    output_file: str,
    format: str = "PNG",
    width: int = 1200,
    height: int = 800,
    jar_path: Optional[str] = None,
    java_opts: str = "-Xmx512m",
    timeout: int = 120,
) -> bool:
    """Render a Nexus file to an image using FigTree.

    Args:
        input_file: Path to input Nexus file.
        output_file: Path to output image file.
        format: Output format (``"PNG"``, ``"PDF"``, ``"SVG"``, ``"JPEG"``).
        width: Image width in pixels.
        height: Image height in pixels.
        jar_path: Path to ``figtree.jar``. If ``None``, auto-detect.
        java_opts: Java JVM options as a single string (e.g. ``"-Xmx512m"``
            or ``"-Xmx1g -XX:+UseG1GC"``).  The string is parsed with
            ``shlex.split`` so that multi-word options are passed as separate
            arguments to ``java``.
        timeout: Maximum wall-clock seconds for the JVM rendering call
            (default ``120``).  Increase this for very large trees (e.g.
            >100,000 taxa), where layout and rasterization can exceed the
            default.

    Returns:
        ``True`` if successful.

    Raises:
        RenderError: If FigTree JAR not found or rendering fails.
    """
    # Validate the input tree file exists before doing any work.
    if not input_file or not os.path.isfile(input_file):
        raise FileNotFoundError(f"Input tree file not found: {input_file!r}")

    # Check Java
    if not check_java_available():
        raise RenderError(
            "Java is not installed or not in PATH.\n"
            "FigTree rendering requires Java 8+.\n"
            "Install from: https://adoptium.net/\n\n"
            "Note: FigTreeKit core features work without Java.\n"
            "Only --render requires Java + FigTree."
        )

    # Find FigTree JAR
    if jar_path is None:
        jar_path = find_figtree_jar()

    if jar_path is None or not os.path.isfile(jar_path):
        raise RenderError(get_figtree_not_found_message())

    # Build command
    cmd = [
        "java",
        *shlex.split(java_opts),
        "-jar", jar_path,
        "-graphic", format,
        "-width", str(width),
        "-height", str(height),
        input_file,
        output_file,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # A render is considered successful only when FigTree exits cleanly
        # AND a non-empty output file was produced. Stdout/stderr may
        # legitimately contain the words "Error"/"Exception" (e.g. a benign
        # log line such as "0 errors found") without indicating failure, so
        # their mere presence must NOT override a valid output.
        success = (
            result.returncode == 0
            and os.path.isfile(output_file)
            and os.path.getsize(output_file) > 0
        )

        if success:
            return True

        # Rendering did not produce a valid output. Surface a helpful error,
        # preferring the most specific signal available.
        error_lines = [
            line.strip()
            for line in (result.stdout + result.stderr).split('\n')
            if 'Exception' in line or 'Error' in line
        ]
        detail = "\n".join(error_lines) if error_lines else (
            f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
        )

        if result.returncode != 0:
            raise RenderError(
                f"FigTree exited with code {result.returncode}\n{detail}"
            )

        if not os.path.isfile(output_file):
            raise RenderError(
                f"FigTree rendering produced no output file: {output_file}\n{detail}"
            )

        if os.path.getsize(output_file) == 0:
            raise RenderError(
                f"FigTree rendering produced an empty output file: {output_file}\n{detail}"
            )

        return True

    except subprocess.TimeoutExpired:
        raise RenderError(f"FigTree rendering timed out after {timeout} seconds")
    except ExportError:
        raise
    except Exception as e:
        raise RenderError(f"FigTree rendering failed: {e}")


def render_multiple(
    input_files: List[str],
    output_dir: str,
    formats: Optional[List[str]] = None,
    width: int = 1200,
    height: int = 800,
    jar_path: Optional[str] = None,
    timeout: int = 120,
) -> dict:
    """Render multiple Nexus files to images.

    Args:
        input_files: List of input Nexus file paths.
        output_dir: Output directory for images.
        formats: List of output formats (default: ``["PNG", "PDF"]``).
        width: Image width in pixels.
        height: Image height in pixels.
        jar_path: Path to ``figtree.jar``. If ``None``, auto-detect.

    Returns:
        Dictionary with ``success`` and ``failed`` lists.
    """
    if formats is None:
        formats = ["PNG", "PDF"]

    os.makedirs(output_dir, exist_ok=True)

    results = {"success": [], "failed": []}

    for input_file in input_files:
        basename = os.path.splitext(os.path.basename(input_file))[0]

        for fmt in formats:
            output_file = os.path.join(output_dir, f"{basename}.{fmt.lower()}")
            try:
                render_with_figtree(
                    input_file, output_file, fmt, width, height, jar_path,
                    timeout=timeout,
                )
                results["success"].append(output_file)
            except ExportError as e:
                results["failed"].append({"file": input_file, "format": fmt, "error": str(e)})

    return results
