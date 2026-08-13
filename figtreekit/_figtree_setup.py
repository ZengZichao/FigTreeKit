"""FigTree setup utilities for FigTreeKit.

This module provides functionality to download and compile FigTree
for use with FigTreeKit's rendering features.

FigTree is licensed under GPL-2.0-or-later (GNU General Public License
v2.0 or later). The patched FigTree JAR distributed with FigTreeKit is a
derivative work and is also licensed under GPL-2.0-or-later. The JAR
includes iText (com.itextpdf.text.*) for PDF export, which is licensed
under AGPL-3.0.

- Source: https://github.com/rambaut/figtree
- License: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html

Compliance notes for academic publication:
- FigTree source code is downloaded from its official GitHub repository
- Compilation is performed locally on the user's machine when using
  ``figtreekit setup-figtree``
- A pre-built patched JAR is also provided for convenience; its source
  modifications are included in this distribution
- Users should cite FigTree in publications: Rambaut (2018) FigTree v1.4.4

Usage:
    # Command line
    figtreekit setup-figtree                    # Download and compile
    figtreekit setup-figtree --check            # Check if FigTree is available
    figtreekit setup-figtree --path /path/to/figtree.jar  # Use existing JAR

    # Python API
    from figtreekit._figtree_setup import setup_figtree, check_figtree
    setup_figtree()
    check_figtree()
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

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from .exceptions import RenderError

# FigTree GitHub repository
FIGTREE_REPO = "https://github.com/rambaut/figtree/archive/refs/tags/v1.4.4.zip"
FIGTREE_VERSION = "1.4.4"

# Default installation directory
DEFAULT_INSTALL_DIR = Path.home() / ".figtreekit" / "figtree"


def get_figtree_jar_path() -> Path:
    """Get the default path where FigTree JAR is stored."""
    return DEFAULT_INSTALL_DIR / "dist" / "figtree.jar"


def check_java() -> Tuple[bool, str]:
    """Check if Java is available and get version."""
    java_path = shutil.which("java")
    if not java_path:
        return False, "Java not found in PATH"
    
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True, text=True, timeout=10
        )
        version_info = result.stderr.strip() or result.stdout.strip()
        return True, version_info
    except Exception as e:
        return False, f"Error checking Java: {e}"


def check_ant() -> Tuple[bool, str]:
    """Check if Apache Ant is available and get version."""
    ant_path = shutil.which("ant")
    if not ant_path:
        return False, "Apache Ant not found in PATH"
    
    try:
        result = subprocess.run(
            ["ant", "-version"],
            capture_output=True, text=True, timeout=10
        )
        version_info = result.stdout.strip().split('\n')[0]
        return True, version_info
    except Exception as e:
        return False, f"Error checking Ant: {e}"


def check_figtree(jar_path: Optional[str] = None) -> Tuple[bool, str]:
    """Check if FigTree JAR is available.
    
    Args:
        jar_path: Optional path to figtree.jar. If None, searches in:
                  1. Saved path from previous setup
                  2. Default install location
    
    Returns:
        Tuple of (is_available, message)
    """
    if jar_path is None:
        # Try saved path first
        saved = get_saved_figtree_path()
        if saved and saved.exists():
            jar_path = saved
        else:
            jar_path = get_figtree_jar_path()
    else:
        jar_path = Path(jar_path)
    
    if not jar_path.exists():
        return False, f"FigTree JAR not found at {jar_path}"
    
    # Try to run FigTree
    java_ok, java_msg = check_java()
    if not java_ok:
        return False, f"Java required: {java_msg}"
    
    try:
        result = subprocess.run(
            ["java", "-jar", str(jar_path), "-help"],
            capture_output=True, text=True, timeout=10
        )
        if "FigTree" in result.stdout:
            return True, f"FigTree v{FIGTREE_VERSION} available at {jar_path}"
        else:
            return False, "FigTree JAR exists but may be corrupted"
    except Exception as e:
        return False, f"Error running FigTree: {e}"


def download_figtree(target_dir: Path, verbose: bool = False) -> Path:
    """Download FigTree source code from GitHub.
    
    Args:
        target_dir: Directory to download to.
        verbose: Print progress messages.
    
    Returns:
        Path to downloaded source directory.
    
    Raises:
        RenderError: If download fails.
    """
    import urllib.request
    
    zip_url = FIGTREE_REPO
    zip_file = target_dir / f"figtree-{FIGTREE_VERSION}.zip"
    source_dir = target_dir / f"figtree-{FIGTREE_VERSION}"
    
    # Skip if already downloaded
    if source_dir.exists():
        if verbose:
            print(f"FigTree source already exists at {source_dir}")
        return source_dir
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    if verbose:
        print(f"Downloading FigTree v{FIGTREE_VERSION} from GitHub...")
        print(f"  URL: {zip_url}")
    
    try:
        import ssl
        # Verify the server certificate against the system trust store so the
        # download cannot be silently MITM'd. To opt out (e.g. behind a
        # corporate TLS-inspecting proxy) users may pass a custom context:
        #   ctx = ssl.create_default_context()
        #   ctx.check_hostname = False
        #   ctx.verify_mode = ssl.CERT_NONE
        # and replace ssl_context below.
        ssl_context = ssl.create_default_context()
        with urllib.request.urlopen(zip_url, context=ssl_context) as resp:
            zip_file.write_bytes(resp.read())

        if verbose:
            print(f"  Extracting to {target_dir}...")
        
        with zipfile.ZipFile(zip_file, 'r') as zf:
            # Validate all paths to prevent zip slip attacks
            for member in zf.namelist():
                member_path = (target_dir / member).resolve()
                if not str(member_path).startswith(str(target_dir.resolve())):
                    raise RenderError(
                        f"Zip entry '{member}' would extract outside target directory"
                    )
            zf.extractall(target_dir)
        
        # Clean up zip file
        zip_file.unlink(missing_ok=True)
        
        if verbose:
            print(f"  Download complete: {source_dir}")
        
        return source_dir
        
    except Exception as e:
        raise RenderError(f"Failed to download FigTree: {e}")


def apply_figtree_patches(source_dir: Path, verbose: bool = False) -> None:
    """Apply FigTreeKit-specific patches to downloaded FigTree source.

    The patched Java sources live in ``_figtree_patch/src/figtree/`` at the
    repository root. They are copied into the downloaded FigTree source tree
    before compilation so that ``figtreekit setup-figtree`` produces a JAR
    equivalent to the pre-built ``figtreekit/figtree_patched.jar``.

    Args:
        source_dir: Path to the downloaded FigTree source directory.
        verbose: Print progress messages.

    Raises:
        RenderError: If a patch file is missing or cannot be copied.
    """
    # Locate the local patch source directory: two levels up from this file
    # (figtreekit/_figtree_setup.py -> figtreekit/ -> repo root).
    patch_root = Path(__file__).resolve().parent.parent / "_figtree_patch" / "src"
    if not patch_root.exists():
        raise RenderError(f"Patch source directory not found: {patch_root}")

    target_src = source_dir / "src"
    if not target_src.exists():
        raise RenderError(f"Expected FigTree source tree at {target_src}")

    patched_files = list(patch_root.rglob("*.java"))
    if not patched_files:
        raise RenderError(f"No patched .java files found in {patch_root}")

    for patch_file in patched_files:
        relative = patch_file.relative_to(patch_root)
        target = target_src / relative
        if not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        if verbose:
            print(f"  Applying patch: {relative}")
        shutil.copy2(patch_file, target)


def compile_figtree(source_dir: Path, verbose: bool = False) -> Path:
    """Compile FigTree from source using Apache Ant.
    
    Args:
        source_dir: Path to FigTree source directory.
        verbose: Print progress messages.
    
    Returns:
        Path to compiled figtree.jar.
    
    Raises:
        RenderError: If compilation fails.
    """
    build_xml = source_dir / "build.xml"
    if not build_xml.exists():
        raise RenderError(f"build.xml not found in {source_dir}")
    
    # Check Ant
    ant_ok, ant_msg = check_ant()
    if not ant_ok:
        raise RenderError(
            f"Apache Ant is required to compile FigTree.\n"
            f"Install it with:\n"
            f"  - macOS: brew install ant\n"
            f"  - Ubuntu/Debian: sudo apt-get install ant\n"
            f"  - Windows: https://ant.apache.org/bindownload.cgi\n"
            f"\n{ant_msg}"
        )
    
    # Fix Java source/target version for modern JDK
    build_xml_content = build_xml.read_text(encoding='utf-8')
    original_xml_content = build_xml_content
    if 'source="1.6"' in build_xml_content or 'source="1.8"' in build_xml_content:
        if verbose:
            print("  Patching build.xml for modern JDK...")
        build_xml_content = build_xml_content.replace('source="1.6"', 'source="1.8"')
        build_xml_content = build_xml_content.replace('target="1.6"', 'target="1.8"')
    else:
        # Modern JDKs (Java 9+) may ship a build.xml that declares a `release`
        # attribute or a source/target of 1.7/1.9/11/17/etc. A `release`
        # attribute is incompatible with explicit source/target on older Ant,
        # and legacy source levels can be rejected by the active JDK. We must
        # not silently rewrite unrelated configurations, so we only warn and
        # let the user intervene if compilation then fails.
        uses_release = 'release=' in build_xml_content
        modern_target = re.search(r'(?:source|target)="(1\.[7-9]|[2-9]\d*)"', build_xml_content)
        if uses_release or modern_target:
            level = modern_target.group(1) if modern_target else "release"
            msg = (
                f"FigTree build.xml targets a modern JDK level ({level}). "
                "If compilation fails, pin source/target to \"1.8\" in build.xml."
            )
            if verbose:
                print(f"  Warning: {msg}")
            logging.getLogger(__name__).warning(msg)
    if build_xml_content != original_xml_content:
        build_xml.write_text(build_xml_content, encoding='utf-8', newline='\n')
    
    # Fix javax.activation issue for Java 9+
    dialog_file = source_dir / "src" / "figtree" / "treeviewer" / "DiscreteColourScaleDialog.java"
    if dialog_file.exists():
        content = dialog_file.read_text(encoding='utf-8')
        if "import javax.activation.DataHandler;" in content:
            if verbose:
                print("  Patching DiscreteColourScaleDialog.java for Java 9+...")
            # Remove the import
            content = content.replace("import javax.activation.DataHandler;\n", "")
            # Replace DataHandler usage with inline Transferable
            old_code = "return new DataHandler(selectedRows, localObjectFlavor.getMimeType());"
            new_code = """return new Transferable() {
                public DataFlavor[] getTransferDataFlavors() { return new DataFlavor[] { localObjectFlavor }; }
                public boolean isDataFlavorSupported(DataFlavor flavor) { return localObjectFlavor.equals(flavor); }
                public Object getTransferData(DataFlavor flavor) { return selectedRows; }
            };"""
            content = content.replace(old_code, new_code)
            dialog_file.write_text(content, encoding='utf-8', newline='\n')
    
    # Compile
    if verbose:
        print("  Compiling FigTree...")
    
    try:
        result = subprocess.run(
            ["ant", "dist"],
            cwd=str(source_dir),
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            raise RenderError(f"Compilation failed:\n{error_msg}")
        
        jar_path = source_dir / "dist" / "figtree.jar"
        if not jar_path.exists():
            raise RenderError("figtree.jar not found after compilation")
        
        if verbose:
            print(f"  Compilation successful: {jar_path}")
        
        return jar_path
        
    except subprocess.TimeoutExpired:
        raise RenderError("Compilation timed out after 120 seconds")
    except Exception as e:
        raise RenderError(f"Compilation error: {e}")


def setup_figtree(
    install_dir: Optional[Path] = None,
    jar_path: Optional[str] = None,
    verbose: bool = True,
) -> Path:
    """Setup FigTree for use with FigTreeKit.
    
    This function either:
    1. Downloads and compiles FigTree from source, or
    2. Validates an existing JAR path
    
    Args:
        install_dir: Directory to install FigTree. Default: ~/.figtreekit/figtree
        jar_path: Path to existing figtree.jar. If provided, skips download/compile.
        verbose: Print progress messages.
    
    Returns:
        Path to figtree.jar.
    
    Raises:
        RenderError: If setup fails.
    """
    # If user provides existing JAR path
    if jar_path:
        jar_path = Path(jar_path)
        if not jar_path.exists():
            raise RenderError(f"Specified JAR not found: {jar_path}")
        if verbose:
            print(f"Using existing FigTree JAR: {jar_path}")
        
        # Save path for future use
        _save_figtree_path(jar_path)
        return jar_path
    
    # Check if already installed
    default_jar = get_figtree_jar_path()
    if default_jar.exists():
        ok, msg = check_figtree()
        if ok:
            if verbose:
                print(f"FigTree already installed: {msg}")
            return default_jar
    
    # Check prerequisites
    java_ok, java_msg = check_java()
    if not java_ok:
        raise RenderError(
            f"Java is required to use FigTree rendering.\n"
            f"Install Java 8+ from: https://adoptium.net/\n"
            f"\n{java_msg}\n"
            f"\nNote: FigTreeKit core features work without Java."
            f"Only rendering requires FigTree + Java."
        )
    
    ant_ok, ant_msg = check_ant()
    if not ant_ok:
        raise RenderError(
            f"Apache Ant is required to compile FigTree.\n"
            f"Install with:\n"
            f"  - macOS: brew install ant\n"
            f"  - Ubuntu/Debian: sudo apt-get install ant\n"
            f"  - Windows: https://ant.apache.org/bindownload.cgi\n"
            f"\n{ant_msg}\n"
            f"\nAlternatively, compile FigTree manually and use:"
            f"  figtreekit setup-figtree --path /path/to/figtree.jar"
        )
    
    # Download and compile
    if install_dir is None:
        install_dir = DEFAULT_INSTALL_DIR
    
    if verbose:
        print(f"Setting up FigTree v{FIGTREE_VERSION}...")
        print(f"  Install directory: {install_dir}")
        print(f"  Java: {java_msg}")
        print(f"  Ant: {ant_msg}")
        print()
    
    # Download
    source_dir = download_figtree(install_dir, verbose=verbose)
    
    # Apply FigTreeKit patches before compiling
    apply_figtree_patches(source_dir, verbose=verbose)
    
    # Compile
    jar_path = compile_figtree(source_dir, verbose=verbose)
    
    # Save path
    _save_figtree_path(jar_path)
    
    if verbose:
        print()
        print(f"FigTree setup complete!")
        print(f"  JAR location: {jar_path}")
        print(f"  Environment: FIGTREE_JAR={jar_path}")
        print()
        print("You can now use rendering features:")
        print("  figtreekit input.tre -o output.nex --render output.png")
        print("  figtreekit input.tre -o output.nex --render output.pdf")
    
    return jar_path


def _save_figtree_path(jar_path: Path) -> None:
    """Save FigTree JAR path for future use."""
    config_dir = Path.home() / ".figtreekit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "figtree_path.txt"
    # Always save absolute path
    config_file.write_text(str(Path(jar_path).resolve()), encoding='utf-8', newline='\n')


def get_saved_figtree_path() -> Optional[Path]:
    """Get previously saved FigTree JAR path."""
    config_file = Path.home() / ".figtreekit" / "figtree_path.txt"
    if config_file.exists():
        path = Path(config_file.read_text(encoding='utf-8').strip())
        if path.exists():
            return path
    return None


def print_setup_status() -> None:
    """Print current FigTree setup status."""
    print("FigTreeKit FigTree Integration Status")
    print("=" * 50)
    
    # Check Java
    java_ok, java_msg = check_java()
    print(f"Java: {'✓' if java_ok else '✗'} {java_msg}")
    
    # Check Ant
    ant_ok, ant_msg = check_ant()
    print(f"Ant:  {'✓' if ant_ok else '✗'} {ant_msg}")
    
    # Check FigTree JAR
    jar_path = get_figtree_jar_path()
    saved_path = get_saved_figtree_path()
    
    # Check environment variable
    env_jar = os.environ.get("FIGTREE_JAR")
    
    print()
    print("FigTree JAR locations:")
    print(f"  Default:     {jar_path} {'✓' if jar_path.exists() else '✗'}")
    if saved_path:
        print(f"  Saved:       {saved_path} {'✓' if saved_path.exists() else '✗'}")
    if env_jar:
        print(f"  Environment: {env_jar} {'✓' if Path(env_jar).exists() else '✗'}")
    
    # Check if rendering is available
    print()
    figtree_ok, figtree_msg = check_figtree()
    if figtree_ok:
        print(f"Rendering: ✓ Ready ({figtree_msg})")
    else:
        print(f"Rendering: ✗ Not available")
        print(f"  Reason: {figtree_msg}")
        print()
        print("To enable rendering:")
        print("  figtreekit setup-figtree              # Download and compile")
        print("  figtreekit setup-figtree --path JAR   # Use existing JAR")


if __name__ == "__main__":
    print_setup_status()
