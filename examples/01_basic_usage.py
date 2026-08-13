#!/usr/bin/env python3
"""
Basic usage examples for FigTreeKit

This script demonstrates the core functionality of FigTreeKit
for styling phylogenetic trees. All output is written to a
temporary directory and cleaned up on exit.

Usage:
    python examples/01_basic_usage.py
"""

import sys
import tempfile
import os

from figtreekit import FigTreeStyler, LayoutType, FontStyle


def example_basic_styling(output_dir: str) -> None:
    """Example 1: Basic tree styling with method chaining."""
    print("=" * 60)
    print("Example 1: Basic Tree Styling")
    print("=" * 60)

    newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

    styler = FigTreeStyler() \
        .load_content(newick) \
        .set_layout(LayoutType.RECTILINEAR) \
        .set_tip_labels(is_shown=True, font_name="Arial", font_size=12,
                        font_style=FontStyle.PLAIN) \
        .set_appearance(branch_line_width=2.0)

    output_file = os.path.join(output_dir, "basic_styled_tree.nex")
    styler.export(output_file)
    print(f"  Exported to: {output_file}")
    print()


def example_polar_layout(output_dir: str) -> None:
    """Example 2: Polar layout with branch coloring."""
    print("=" * 60)
    print("Example 2: Polar Layout")
    print("=" * 60)

    newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

    styler = FigTreeStyler() \
        .load_content(newick) \
        .set_layout(LayoutType.POLAR) \
        .set_polar_layout(align_tip_labels=True, angular_range=360,
                          root_angle=0, show_root=True) \
        .set_appearance(branch_line_width=1.5,
                        branch_color_attribute="height") \
        .set_tip_labels(is_shown=True, font_name="Helvetica",
                        font_size=10, font_style=FontStyle.BOLD)

    output_file = os.path.join(output_dir, "polar_styled_tree.nex")
    styler.export(output_file)
    print(f"  Exported to: {output_file}")
    print()


def example_clade_highlighting(output_dir: str) -> None:
    """Example 3: Highlighting specific clades with colors."""
    print("=" * 60)
    print("Example 3: Clade Highlighting")
    print("=" * 60)

    newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

    styler = FigTreeStyler() \
        .load_content(newick) \
        .set_layout(LayoutType.RECTILINEAR) \
        .set_tip_labels(is_shown=True, font_size=12) \
        .set_appearance(branch_line_width=2.0) \
        .highlight_clade(["A", "B"], color="#FF0000") \
        .highlight_clade(["C", "D"], color="#00FF00") \
        .set_clade_color(["A", "B", "C", "D"], color="#0000FF")

    output_file = os.path.join(output_dir, "highlighted_tree.nex")
    styler.export(output_file)
    print(f"  Exported to: {output_file}")
    print()


def example_font_annotation(output_dir: str) -> None:
    """Example 4: Custom font annotations on clades."""
    print("=" * 60)
    print("Example 4: Font Annotations")
    print("=" * 60)

    newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

    styler = FigTreeStyler() \
        .load_content(newick) \
        .set_layout(LayoutType.RECTILINEAR) \
        .set_clade_font(["A", "B"], "Arial", FontStyle.BOLD, 14) \
        .set_clade_font(["C", "D"], "Courier", FontStyle.ITALIC, 10)

    output_file = os.path.join(output_dir, "font_annotated_tree.nex")
    styler.export(output_file)
    print(f"  Exported to: {output_file}")
    print()


def example_validation(output_dir: str) -> None:
    """Example 5: Validate tree before export."""
    print("=" * 60)
    print("Example 5: Validation")
    print("=" * 60)

    newick = "((A:-0.1,B:0.2):0.3,C:0.4);"

    styler = FigTreeStyler().load_content(newick)
    issues = styler.validate()
    if issues:
        for issue in issues:
            print(f"  Warning: {issue}")
    else:
        print("  Tree is valid.")
    print()


def main() -> None:
    """Run all examples in a temporary directory."""
    print("FigTreeKit Usage Examples")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory(prefix="figtreekit_example_") as tmpdir:
        example_basic_styling(tmpdir)
        example_polar_layout(tmpdir)
        example_clade_highlighting(tmpdir)
        example_font_annotation(tmpdir)
        example_validation(tmpdir)

        # List generated files
        generated = sorted(os.listdir(tmpdir))
        print(f"Generated {len(generated)} Nexus file(s) in {tmpdir}:")
        for f in generated:
            size = os.path.getsize(os.path.join(tmpdir, f))
            print(f"  {f} ({size} bytes)")

    print()
    print("All examples completed. Temporary files cleaned up.")


if __name__ == "__main__":
    main()
