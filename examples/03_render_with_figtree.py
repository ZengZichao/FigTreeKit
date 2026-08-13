"""Batch render all FigTreeKit-generated Nexus files using FigTree.

This script calls FigTree's command-line interface to render all .nex files
in the results directory to PNG and PDF images.

Requirements:
    - Compiled FigTree JAR (FigTree-1.4.4/dist/figtree.jar)
    - Java 8+

Usage:
    python examples/03_render_with_figtree.py
    python examples/03_render_with_figtree.py -f PNG PDF
    python examples/03_render_with_figtree.py -W 1600 -H 1000
"""

import os
import sys
import glob
import subprocess
import argparse
from pathlib import Path


def find_figtree_jar() -> str:
    """Find the compiled FigTree JAR file."""
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    
    candidates = [
        project_dir / "FigTree-1.4.4" / "dist" / "figtree.jar",
        project_dir / "dist" / "figtree.jar",
        Path("FigTree-1.4.4/dist/figtree.jar"),
        Path("dist/figtree.jar"),
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    
    return None


def render_with_figtree(
    jar_path: str,
    nexus_file: str,
    output_file: str,
    format: str = "PNG",
    width: int = 1200,
    height: int = 800,
    java_opts: str = "-Xmx512m",
) -> bool:
    """Render a Nexus file to an image using FigTree."""
    cmd = [
        "java",
        java_opts,
        "-jar", jar_path,
        "-graphic", format,
        "-width", str(width),
        "-height", str(height),
        nexus_file,
        output_file,
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if f"Creating {format}" in result.stdout:
            return True
        
        if "Exception" in result.stderr or "Error" in result.stdout:
            for line in (result.stdout + result.stderr).split('\n'):
                if 'Exception' in line or 'Error' in line:
                    print(f"      {line.strip()}")
            return False
        
        return True
        
    except subprocess.TimeoutExpired:
        print(f"      Timeout")
        return False
    except Exception as e:
        print(f"      Error: {e}")
        return False


def render_all_trees(
    input_dir: str,
    output_dir: str,
    formats: list = None,
    width: int = 1200,
    height: int = 800,
):
    """Render all Nexus files in a directory to multiple formats."""
    if formats is None:
        formats = ["PNG", "PDF"]
    
    jar_path = find_figtree_jar()
    if not jar_path:
        print("Error: Could not find figtree.jar")
        print("Please compile FigTree first: cd FigTree-1.4.4 && ant dist")
        return
    
    print(f"FigTree JAR: {jar_path}")
    
    nexus_files = sorted(glob.glob(os.path.join(input_dir, '*.nex')))
    
    if not nexus_files:
        print(f"No .nex files found in {input_dir}")
        return
    
    print(f"Input: {len(nexus_files)} Nexus files")
    print(f"Output: {output_dir}")
    print(f"Formats: {', '.join(formats)}")
    print(f"Size: {width}x{height}")
    print("=" * 70)
    
    os.makedirs(output_dir, exist_ok=True)
    
    total_success = 0
    total_fail = 0
    failed_files = []
    
    for i, nexus_file in enumerate(nexus_files, 1):
        basename = os.path.splitext(os.path.basename(nexus_file))[0]
        print(f"[{i:2d}/{len(nexus_files)}] {basename}")
        
        for fmt in formats:
            output_file = os.path.join(output_dir, f"{basename}.{fmt.lower()}")
            status = "✓" if render_with_figtree(jar_path, nexus_file, output_file, fmt, width, height) else "✗"
            print(f"      {fmt}: {status}")
            
            if status == "✓":
                total_success += 1
            else:
                total_fail += 1
                failed_files.append(f"{basename}.{fmt}")
    
    print("=" * 70)
    print(f"Total: {total_success} success, {total_fail} failed")
    
    if failed_files:
        print(f"\nFailed ({len(failed_files)}):")
        for f in failed_files:
            print(f"  - {f}")


def main():
    parser = argparse.ArgumentParser(
        description='Render FigTreeKit Nexus files to images using FigTree'
    )
    parser.add_argument(
        'input_dir',
        nargs='?',
        default='examples/results',
        help='Directory containing Nexus files (default: examples/results)'
    )
    parser.add_argument(
        '-o', '--output-dir',
        default='examples/rendered',
        help='Output directory for images (default: examples/rendered)'
    )
    parser.add_argument(
        '-f', '--format',
        nargs='+',
        choices=['PNG', 'PDF', 'SVG', 'JPEG'],
        default=['PNG', 'PDF'],
        help='Output formats (default: PNG PDF)'
    )
    parser.add_argument(
        '-W', '--width',
        type=int,
        default=1200,
        help='Image width in pixels (default: 1200)'
    )
    parser.add_argument(
        '-H', '--height',
        type=int,
        default=800,
        help='Image height in pixels (default: 800)'
    )
    parser.add_argument(
        '-j', '--java-opts',
        default='-Xmx512m',
        help='Java JVM options (default: -Xmx512m)'
    )
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent.parent
    input_dir = base_dir / args.input_dir if not os.path.isabs(args.input_dir) else Path(args.input_dir)
    output_dir = base_dir / args.output_dir if not os.path.isabs(args.output_dir) else Path(args.output_dir)
    
    print("=" * 70)
    print("FigTreeKit Batch Renderer (FigTree)")
    print("=" * 70)
    
    render_all_trees(
        str(input_dir),
        str(output_dir),
        args.format,
        args.width,
        args.height,
    )


if __name__ == "__main__":
    main()
