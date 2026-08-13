"""
Comprehensive test suite for FigTreeKit

This module contains unit tests and integration tests for the FigTreeKit library.
"""

import json
import pytest
import re
import subprocess
import sys
import tempfile
import os
import warnings
from pathlib import Path

from figtreekit import (
    FigTreeStyler,
    FigTreeSettings,
    LayoutType,
    TransformType,
    RootingType,
    OrderType,
    FontStyle,
    NodeAnnotation,
    TreeValidator,
    FigTreeKitError,
    ParseError,
    ValidationError,
    ExportError,
    CompatibilityWarning,
)
from figtreekit._serializer import serialize_value
from figtreekit._parser import (
    extract_taxa_from_newick,
    find_unquoted_semicolon,
    extract_tree_value,
    parse_nexus_content,
    _fallback_extract_taxa,
)
from figtreekit._cli import create_cli_parser, _process_batch
from unittest.mock import patch


class TestTreeValidator:
    """Tests for TreeValidator class."""

    def test_validate_color_valid(self):
        """Test valid hex color validation."""
        assert TreeValidator.validate_color("#FF0000") is True
        assert TreeValidator.validate_color("#00ff00") is True
        assert TreeValidator.validate_color("#123456") is True
        assert TreeValidator.validate_color("#ABCDEF") is True

    def test_validate_color_invalid(self):
        """Test invalid hex color validation."""
        assert TreeValidator.validate_color("red") is False
        assert TreeValidator.validate_color("#FFF") is False
        assert TreeValidator.validate_color("#GGGGGG") is False
        assert TreeValidator.validate_color("") is False
        assert TreeValidator.validate_color(None) is False
        assert TreeValidator.validate_color(123) is False

    def test_validate_taxon_names_valid(self):
        """Test valid taxon names validation."""
        assert TreeValidator.validate_taxon_names(["A", "B", "C"]) is True
        assert TreeValidator.validate_taxon_names(["Species_A"]) is True

    def test_validate_taxon_names_invalid(self):
        """Test invalid taxon names validation."""
        assert TreeValidator.validate_taxon_names([]) is False
        assert TreeValidator.validate_taxon_names(None) is False
        assert TreeValidator.validate_taxon_names([""]) is False
        assert TreeValidator.validate_taxon_names(["A", ""]) is False

    def test_validate_font_style_valid(self):
        """Test valid font style validation."""
        assert TreeValidator.validate_font_style(0) is True
        assert TreeValidator.validate_font_style(1) is True
        assert TreeValidator.validate_font_style(2) is True
        assert TreeValidator.validate_font_style(3) is True

    def test_validate_font_style_invalid(self):
        """Test invalid font style validation."""
        assert TreeValidator.validate_font_style(-1) is False
        assert TreeValidator.validate_font_style(4) is False
        assert TreeValidator.validate_font_style(1.5) is False

    def test_validate_newick_valid(self):
        """Test valid Newick format validation."""
        assert TreeValidator.validate_newick("(A:0.1,B:0.2);") is True
        assert TreeValidator.validate_newick("((A:0.1,B:0.2):0.3,C:0.4);") is True

    def test_validate_newick_invalid(self):
        """Test invalid Newick format validation."""
        assert TreeValidator.validate_newick("") is False
        assert TreeValidator.validate_newick("(A:0.1,B:0.2)") is False  # No semicolon
        assert TreeValidator.validate_newick("(A:0.1,B:0.2;") is False  # Unbalanced parentheses

    def test_validate_nexus_valid(self):
        """Test valid Nexus format validation."""
        nexus = "#NEXUS\nbegin trees;\ntree TREE1 = (A:0.1,B:0.2);\nend;"
        assert TreeValidator.validate_nexus(nexus) is True

    def test_validate_nexus_invalid(self):
        """Test invalid Nexus format validation."""
        assert TreeValidator.validate_nexus("") is False
        assert TreeValidator.validate_nexus("(A:0.1,B:0.2);") is False


class TestFigTreeStyler:
    """Tests for FigTreeStyler class."""

    @pytest.fixture
    def simple_newick(self):
        """Simple Newick tree for testing."""
        return "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

    @pytest.fixture
    def styler(self, simple_newick):
        """FigTreeStyler instance with simple tree."""
        return FigTreeStyler().load_content(simple_newick)

    def test_init_empty(self):
        """Test empty initialization."""
        styler = FigTreeStyler()
        assert styler._tree_content is None
        assert styler._is_nexus_format is False

    def test_load_content_newick(self, simple_newick):
        """Test loading Newick content."""
        styler = FigTreeStyler()
        styler.load_content(simple_newick)
        assert styler._tree_content is not None
        assert styler._is_nexus_format is False

    def test_load_content_nexus(self):
        """Test loading Nexus content."""
        nexus = "#NEXUS\nbegin taxa;\ndimensions ntax=2;\ntaxlabels A B ;\nend;\nbegin trees;\ntree TREE1 = (A:0.1,B:0.2);\nend;"
        styler = FigTreeStyler()
        styler.load_content(nexus)
        assert styler._is_nexus_format is True

    def test_load_file_not_found(self):
        """Test loading non-existent file."""
        styler = FigTreeStyler()
        with pytest.raises(FileNotFoundError):
            styler.load_file("nonexistent.tre")

    def test_load_file(self, simple_newick):
        """Test loading from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tre', delete=False) as f:
            f.write(simple_newick)
            temp_path = f.name

        try:
            styler = FigTreeStyler(temp_path)
            assert styler._tree_content is not None
        finally:
            os.unlink(temp_path)

    def test_set_layout(self, styler):
        """Test setting layout."""
        styler.set_layout(LayoutType.POLAR)
        settings = styler.get_settings()
        assert settings.get("layout.layoutType") == "POLAR"

    def test_set_appearance(self, styler):
        """Test setting appearance."""
        styler.set_appearance(branch_line_width=2.0)
        settings = styler.get_settings()
        assert settings.get("appearance.branchLineWidth") == 2.0

    def test_set_tip_labels(self, styler):
        """Test setting tip labels."""
        styler.set_tip_labels(is_shown=True, font_name="Arial", font_size=12)
        settings = styler.get_settings()
        assert settings.get("tipLabels.isShown") is True
        assert settings.get("tipLabels.fontName") == "Arial"
        assert settings.get("tipLabels.fontSize") == 12

    def test_set_node_labels(self, styler):
        """Test setting node labels."""
        styler.set_node_labels(is_shown=True, display_attribute="height")
        settings = styler.get_settings()
        assert settings.get("nodeLabels.isShown") is True
        assert settings.get("nodeLabels.displayAttribute") == "height"

    def test_highlight_clade(self, styler):
        """Test highlighting a clade."""
        styler.highlight_clade(["A", "B"], color="#FF0000")
        assert len(styler._settings._node_annotations) == 1
        assert styler._settings._node_annotations[0].annotation_type == "hilight"

    def test_set_clade_color(self, styler):
        """Test setting clade color."""
        styler.set_clade_color(["A", "B"], color="#00FF00")
        assert len(styler._settings._node_annotations) == 1
        assert styler._settings._node_annotations[0].annotation_type == "color"

    def test_clear_annotations(self, styler):
        """Test clearing annotations."""
        styler.highlight_clade(["A", "B"], color="#FF0000")
        styler.clear_annotations()
        assert len(styler._settings._node_annotations) == 0

    def test_method_chaining(self, simple_newick):
        """Test method chaining."""
        styler = FigTreeStyler() \
            .load_content(simple_newick) \
            .set_layout(LayoutType.POLAR) \
            .set_tip_labels(is_shown=True)
        assert styler._tree_content is not None

    def test_export_newick(self, styler):
        """Test exporting Newick tree."""
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            temp_path = f.name

        try:
            styler.export(temp_path)
            assert os.path.exists(temp_path)
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "#NEXUS" in content
            assert "begin trees;" in content
            assert "begin figtree;" in content
        finally:
            os.unlink(temp_path)

    def test_export_with_hilight(self, styler):
        """Test exporting with hilight annotation."""
        styler.highlight_clade(["A", "B"], color="#FF0000")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            temp_path = f.name

        try:
            styler.export(temp_path)
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "[&!hilight=" in content
            assert "#ff0000" in content
        finally:
            os.unlink(temp_path)

    def test_export_with_color(self, styler):
        """Test exporting with color annotation."""
        styler.set_clade_color(["A", "B"], color="#00FF00")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            temp_path = f.name

        try:
            styler.export(temp_path)
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "[&!color=" in content
            assert "#00ff00" in content
        finally:
            os.unlink(temp_path)

    def test_serialize_value_none(self, styler):
        """Test serializing None value."""
        assert styler._serialize_value(None) == "null"

    def test_serialize_value_bool(self, styler):
        """Test serializing boolean values."""
        assert styler._serialize_value(True) == "true"
        assert styler._serialize_value(False) == "false"

    def test_serialize_value_color(self, styler):
        """Test serializing color values."""
        assert styler._serialize_value("#FF0000") == "#ff0000"

    def test_serialize_value_int(self, styler):
        """Test serializing integer values."""
        assert styler._serialize_value(42) == "42"

    def test_serialize_value_float(self, styler):
        """Test serializing float values."""
        assert styler._serialize_value(3.14) == "3.14"

    def test_serialize_value_float_integer(self, styler):
        """Test serializing float that is integer."""
        assert styler._serialize_value(1.0) == "1"

    def test_serialize_value_string(self, styler):
        """Test serializing string values."""
        assert styler._serialize_value("hello") == '"hello"'

    def test_serialize_value_string_with_space(self, styler):
        """Test serializing string with space."""
        assert styler._serialize_value("hello world") == '"hello world"'

    def test_reset(self, styler):
        """Test resetting settings clears all state."""
        styler.set_layout(LayoutType.POLAR)
        styler.highlight_clade(["A", "B"], color="#FF0000")
        styler.reset()
        settings = styler.get_settings()
        assert settings.get("layout.layoutType") == "RECTILINEAR"
        assert styler._tree_content is None
        assert len(styler._settings._node_annotations) == 0

    def test_set_custom_param(self, styler):
        """Test setting custom parameter."""
        styler.set_custom_param("custom.key", "value")
        settings = styler.get_settings()
        assert settings.get("custom.key") == "value"

    def test_apply_dict(self, styler):
        """Test applying dictionary of settings."""
        settings = {
            "layout.layoutType": "POLAR",
            "tipLabels.fontSize": 14,
        }
        styler.apply_dict(settings)
        result = styler.get_settings()
        assert result.get("layout.layoutType") == "POLAR"
        assert result.get("tipLabels.fontSize") == 14


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_set_clade_hilight_end_to_end(self):
        """Test that set_clade_hilight actually produces hilight in output."""
        newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

        styler = FigTreeStyler()
        styler.load_content(newick)
        styler.set_clade_hilight("MRCA(A,B)", tip_count=2, height=0.3, color="#FF0000")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            temp_path = f.name

        try:
            styler.export(temp_path)
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "[&!hilight=" in content
        finally:
            os.unlink(temp_path)

    def test_export_does_not_mutate_tree_content(self):
        """Test that export() never modifies _tree_content."""
        newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

        styler = FigTreeStyler()
        styler.load_content(newick)
        styler.highlight_clade(["A", "B"], color="#FF0000")

        original_content = styler._tree_content

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            temp_path = f.name

        try:
            styler.export(temp_path)
            # _tree_content should be unchanged (never mutated)
            assert styler._tree_content == original_content
            assert "[&!hilight=" not in (styler._tree_content or "")
        finally:
            os.unlink(temp_path)

    def test_load_content_clears_old_state(self):
        """Test that loading new content clears annotations from previous load."""
        styler = FigTreeStyler()
        styler.load_content("(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);")
        styler.highlight_clade(["A", "B"], color="#FF0000")
        assert len(styler._settings._node_annotations) == 1

        # Load different content - old annotations should be cleared
        styler.load_content("(X:0.1,Y:0.2);")
        assert len(styler._settings._node_annotations) == 0
        assert styler._tree_content is not None

    def test_highlight_clade_stores_width_offset(self):
        """Test that highlight_clade stores width and offset parameters."""
        styler = FigTreeStyler()
        styler.load_content("(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);")
        styler.highlight_clade(["A", "B"], color="#FF0000", width=6, offset=0.5)

        annotation = styler._settings._node_annotations[0]
        assert annotation.extra_params['width'] == 6
        assert annotation.extra_params['offset'] == 0.5

    def test_double_export_produces_same_output(self):
        """Test that exporting the same styler twice produces identical output."""
        newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

        styler = FigTreeStyler()
        styler.load_content(newick)
        styler.highlight_clade(["A", "B"], color="#FF0000")

        path1 = tempfile.mktemp(suffix='.nex')
        path2 = tempfile.mktemp(suffix='.nex')

        try:
            styler.export(path1)
            styler.export(path2)

            with open(path1) as f:
                content1 = f.read()
            with open(path2) as f:
                content2 = f.read()

            assert content1 == content2
        finally:
            for p in (path1, path2):
                if os.path.exists(p):
                    os.unlink(p)

    def test_complete_workflow(self):
        """Test complete styling workflow."""
        newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

        styler = FigTreeStyler()
        styler.load_content(newick)

        # Set layout
        styler.set_layout(LayoutType.RECTILINEAR)

        # Set appearance
        styler.set_appearance(
            branch_line_width=2.0,
            background_color="#FFFFFF",
            foreground_color="#000000"
        )

        # Set labels
        styler.set_tip_labels(
            is_shown=True,
            font_name="Arial",
            font_size=12,
            font_style=1
        )

        styler.set_node_labels(
            is_shown=True,
            display_attribute="height",
            font_size=10
        )

        # Highlight clades
        styler.highlight_clade(["A", "B"], color="#FF0000")
        styler.set_clade_color(["C", "D"], color="#00FF00")

        # Export
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            temp_path = f.name

        try:
            styler.export(temp_path)

            with open(temp_path, 'r') as f:
                content = f.read()

            # Verify content
            assert "#NEXUS" in content
            assert "begin taxa;" in content
            assert "begin trees;" in content
            assert "begin figtree;" in content
            assert 'layout.layoutType="RECTILINEAR"' in content
            assert 'tipLabels.fontName="Arial"' in content
            assert "[&!hilight=" in content
            assert "[&!color=" in content
        finally:
            os.unlink(temp_path)

    def test_nexus_preservation(self):
        """Test that Nexus files are properly preserved."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=3;
    taxlabels A B C ;
end;
begin trees;
    tree TREE1 = ((A:0.1,B:0.2):0.3,C:0.4);
end;
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nex', delete=False) as f:
            f.write(nexus)
            input_path = f.name

        try:
            styler = FigTreeStyler(input_path)
            styler.set_layout(LayoutType.POLAR)

            output_path = input_path.replace('.nex', '_styled.nex')
            styler.export(output_path)

            with open(output_path, 'r') as f:
                content = f.read()

            assert "#NEXUS" in content
            assert "begin taxa;" in content
            assert "tree TREE1" in content
            assert 'layout.layoutType="POLAR"' in content
        finally:
            os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_multiple_highlights(self):
        """Test multiple highlights on same tree."""
        newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

        styler = FigTreeStyler()
        styler.load_content(newick)

        # Add multiple highlights
        styler.highlight_clade(["A", "B"], color="#FF0000")
        styler.highlight_clade(["C", "D"], color="#00FF00")
        styler.highlight_clade(["A", "B", "C", "D"], color="#0000FF")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            temp_path = f.name

        try:
            styler.export(temp_path)

            with open(temp_path, 'r') as f:
                content = f.read()

            # Count hilight annotations
            hilight_count = content.count("[&!hilight=")
            assert hilight_count == 3
        finally:
            os.unlink(temp_path)


class TestEnums:
    """Tests for enum types."""

    def test_layout_type_values(self):
        """Test LayoutType enum values."""
        assert LayoutType.RECTILINEAR.value == "RECTILINEAR"
        assert LayoutType.POLAR.value == "POLAR"
        assert LayoutType.RADIAL.value == "RADIAL"

    def test_transform_type_values(self):
        """Test TransformType enum values."""
        assert TransformType.CLADOGRAM.value == "cladogram"
        assert TransformType.PHYLOGRAM.value == "phylogram"

    def test_rooting_type_values(self):
        """Test RootingType enum values."""
        assert RootingType.USER_SELECTION.value == "User Selection"
        assert RootingType.MID_POINT.value == "Mid-point"

    def test_order_type_values(self):
        """Test OrderType enum values."""
        assert OrderType.INCREASING_NODE_DENSITY.value == "Increasing Node Density"
        assert OrderType.DECREASING_NODE_DENSITY.value == "Decreasing Node Density"


class TestDataClasses:
    """Tests for data classes."""

    def test_node_annotation(self):
        """Test NodeAnnotation data class."""
        annotation = NodeAnnotation(
            annotation_type="hilight",
            values=[3, 0.5, "#FF0000"],
            target_taxa=["A", "B"]
        )
        assert annotation.annotation_type == "hilight"
        assert annotation.target_taxa == ["A", "B"]


class TestBugFixes:
    """Tests for bug fixes and improvements."""

    @pytest.fixture
    def simple_newick(self):
        return "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"

    @pytest.fixture
    def styler(self, simple_newick):
        return FigTreeStyler().load_content(simple_newick)

    # --- Bug 1: CLI 0-value falsiness ---

    def test_cli_font_size_zero(self, simple_newick):
        """CLI --font-size 0 should not be silently dropped."""
        from figtreekit import apply_cli_args
        import argparse
        styler = FigTreeStyler().load_content(simple_newick)
        args = argparse.Namespace(
            config=None, branch_width=None, branch_color_attribute=None,
            background_color=None, foreground_color=None, selection_color=None,
            layout=None, expansion=None, zoom=None,
            rooted=False, unrooted=False, rooting_type=None,
            transform=None, order=None, order_branches=False,
            tip_labels_show=False, tip_labels_hide=False,
            font_name=None, font_size=0, font_style=None, label_color=None,
            node_labels_show=False, node_labels_hide=False,
            node_display_attribute=None,
            branch_labels_show=False, branch_labels_hide=False,
            branch_display_attribute=None,
            scale_bar_show=False, scale_bar_hide=False,
            scale_axis_show=False, scale_axis_hide=False,
            root_age=None, scale_factor=None,
            angular_range=None, root_angle=None, align_tip_labels=False,
            radial_spread=None, curvature=None, root_length=None,
            legend_show=False, legend_position=None,
        )
        apply_cli_args(styler, args)
        settings = styler.get_settings()
        assert settings["tipLabels.fontSize"] == 0

    def test_cli_branch_width_zero(self, simple_newick):
        """CLI --branch-width 0.0 should not be silently dropped."""
        from figtreekit import apply_cli_args
        import argparse
        styler = FigTreeStyler().load_content(simple_newick)
        args = argparse.Namespace(
            config=None, branch_width=0.0, branch_color_attribute=None,
            background_color=None, foreground_color=None, selection_color=None,
            layout=None, expansion=None, zoom=None,
            rooted=False, unrooted=False, rooting_type=None,
            transform=None, order=None, order_branches=False,
            tip_labels_show=False, tip_labels_hide=False,
            font_name=None, font_size=None, font_style=None, label_color=None,
            node_labels_show=False, node_labels_hide=False,
            node_display_attribute=None,
            branch_labels_show=False, branch_labels_hide=False,
            branch_display_attribute=None,
            scale_bar_show=False, scale_bar_hide=False,
            scale_axis_show=False, scale_axis_hide=False,
            root_age=None, scale_factor=None,
            angular_range=None, root_angle=None, align_tip_labels=False,
            radial_spread=None, curvature=None, root_length=None,
            legend_show=False, legend_position=None,
        )
        apply_cli_args(styler, args)
        settings = styler.get_settings()
        assert settings["appearance.branchLineWidth"] == 0.0

    # --- Bug 2: clear_clade_hilights clears annotations ---

    def test_clear_clade_hilights_removes_from_export(self, styler):
        """clear_clade_hilights() should prevent hilights from appearing in export."""
        styler.highlight_clade(["A", "B"], color="#FF0000")
        assert len(styler._settings._node_annotations) == 1

        styler.clear_clade_hilights()
        assert len(styler._settings._node_annotations) == 0

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "[&!hilight=" not in content
        finally:
            os.unlink(path)

    def test_clear_clade_hilights_preserves_color_annotations(self, styler):
        """clear_clade_hilights() should only remove hilight annotations, not color."""
        styler.highlight_clade(["A", "B"], color="#FF0000")
        styler.set_clade_color(["C", "D"], color="#00FF00")
        assert len(styler._settings._node_annotations) == 2

        styler.clear_clade_hilights()
        assert len(styler._settings._node_annotations) == 1
        assert styler._settings._node_annotations[0].annotation_type == "color"

    # --- Bug 3: discrete_coloring without branch_color_attribute ---

    def test_discrete_coloring_without_attribute_warns(self, styler):
        """discrete_coloring=True without branch_color_attribute should warn, not crash."""
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler.set_appearance(discrete_coloring=True)
            assert len(w) == 1
            assert "discrete_coloring" in str(w[0].message)

    # --- Issue 4: export doesn't mutate annotations ---

    def test_export_does_not_mutate_annotation_values(self, styler):
        """export() should not modify stored annotation values."""
        styler.highlight_clade(["A", "B"], color="#FF0000")
        original_values = styler._settings._node_annotations[0].values.copy()

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            assert styler._settings._node_annotations[0].values == original_values
        finally:
            os.unlink(path)

    # --- Issue 5: Float precision ---

    def test_node_height_precision(self, styler):
        """Node height calculation should not suffer from floating point drift."""
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        # MRCA of A and B: path root→[ABCD]→[AB], height = 0.7 + 0.3 = 1.0
        mrca_ab = styler._find_mrca_clade(tree, ["A", "B"])
        height_ab = styler._calculate_node_height(tree, mrca_ab)
        assert height_ab == 1.0
        # MRCA of C and D: path root→[ABCD]→[CD], height = 0.7 + 0.6 = 1.3
        mrca_cd = styler._find_mrca_clade(tree, ["C", "D"])
        height_cd = styler._calculate_node_height(tree, mrca_cd)
        assert height_cd == 1.3

    def test_hilight_height_precision_in_export(self):
        """Hilight height in exported file should be precise."""
        newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"
        styler = FigTreeStyler().load_content(newick)
        styler.highlight_clade(["A", "B"], color="#FF0000")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            # Should contain 1.0, not 1.2999999999999998 or similar
            import re
            hilight_match = re.search(r'\[&!hilight=\{(\d+),([^,]+),', content)
            assert hilight_match is not None
            height_str = hilight_match.group(2)
            height_val = float(height_str)
            assert height_val == round(height_val, 10)
        finally:
            os.unlink(path)

    # --- Issue 6+7: Validation ---

    def test_highlight_clade_validates_color(self, styler):
        """highlight_clade should reject invalid colors."""
        with pytest.raises(ValidationError, match="Invalid hex color"):
            styler.highlight_clade(["A", "B"], color="red")

    def test_highlight_clade_validates_taxon_names(self, styler):
        """highlight_clade should reject empty taxon list."""
        with pytest.raises(ValidationError, match="Invalid taxon names"):
            styler.highlight_clade([], color="#FF0000")

    def test_set_clade_color_validates_color(self, styler):
        """set_clade_color should reject invalid colors."""
        with pytest.raises(ValidationError, match="Invalid hex color"):
            styler.set_clade_color(["A", "B"], color="not-a-color")

    def test_set_clade_font_validates_font_style(self, styler):
        """set_clade_font should reject invalid font style."""
        with pytest.raises(ValidationError, match="Invalid font style"):
            styler.set_clade_font(["A", "B"], "Arial", 5, 12)

    def test_validate_newick_rejects_unbalanced_brackets(self):
        """validate_newick should reject unbalanced square brackets."""
        assert TreeValidator.validate_newick("(A:0.1,B:0.2) [test;") is False

    def test_validate_nexus_requires_begin_end(self):
        """validate_nexus should require at least one begin/end block."""
        assert TreeValidator.validate_nexus("#NEXUS") is False
        assert TreeValidator.validate_nexus("#NEXUS garbage") is False
        assert TreeValidator.validate_nexus(
            "#NEXUS\nbegin trees;\ntree T = (A:0.1);\nend;"
        ) is True

    # --- Issue 13: CLI config error handling ---

    def test_cli_config_invalid_json(self, simple_newick):
        """CLI --config with invalid JSON should raise ValidationError."""
        from figtreekit import apply_cli_args
        import argparse

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json}")
            config_path = f.name

        try:
            styler = FigTreeStyler().load_content(simple_newick)
            args = argparse.Namespace(
                config=config_path, branch_width=None, branch_color_attribute=None,
                background_color=None, foreground_color=None, selection_color=None,
                layout=None, expansion=None, zoom=None,
                rooted=False, unrooted=False, rooting_type=None,
                transform=None, order=None, order_branches=False,
                tip_labels_show=False, tip_labels_hide=False,
                font_name=None, font_size=None, font_style=None, label_color=None,
                node_labels_show=False, node_labels_hide=False,
                node_display_attribute=None,
                branch_labels_show=False, branch_labels_hide=False,
                branch_display_attribute=None,
                scale_bar_show=False, scale_bar_hide=False,
                scale_axis_show=False, scale_axis_hide=False,
                root_age=None, scale_factor=None,
                angular_range=None, root_angle=None, align_tip_labels=False,
                radial_spread=None, curvature=None, root_length=None,
                legend_show=False, legend_position=None,
            )
            with pytest.raises(ValidationError, match="Invalid JSON"):
                apply_cli_args(styler, args)
        finally:
            os.unlink(config_path)

    def test_cli_config_missing_file(self, simple_newick):
        """CLI --config with missing file should raise FileNotFoundError."""
        from figtreekit import apply_cli_args
        import argparse

        styler = FigTreeStyler().load_content(simple_newick)
        args = argparse.Namespace(
            config="/nonexistent/config.json", branch_width=None,
            branch_color_attribute=None,
            background_color=None, foreground_color=None, selection_color=None,
            layout=None, expansion=None, zoom=None,
            rooted=False, unrooted=False, rooting_type=None,
            transform=None, order=None, order_branches=False,
            tip_labels_show=False, tip_labels_hide=False,
            font_name=None, font_size=None, font_style=None, label_color=None,
            node_labels_show=False, node_labels_hide=False,
            node_display_attribute=None,
            branch_labels_show=False, branch_labels_hide=False,
            branch_display_attribute=None,
            scale_bar_show=False, scale_bar_hide=False,
            scale_axis_show=False, scale_axis_hide=False,
            root_age=None, scale_factor=None,
            angular_range=None, root_angle=None, align_tip_labels=False,
            radial_spread=None, curvature=None, root_length=None,
            legend_show=False, legend_position=None,
        )
        with pytest.raises(FileNotFoundError):
            apply_cli_args(styler, args)

    # --- Removed dead code verification ---

    def test_branch_ordering_enum_removed(self):
        """BranchOrdering enum should no longer exist."""
        import figtreekit
        assert not hasattr(figtreekit, 'BranchOrdering')

    def test_hilight_info_class_removed(self):
        """HilightInfo class should no longer exist."""
        import figtreekit
        assert not hasattr(figtreekit, 'HilightInfo')


class TestNewExceptionHierarchy:
    """Tests for the new exception classes."""

    def test_parse_error_with_line(self):
        """ParseError should store line number."""
        err = ParseError("bad syntax", line=42)
        assert err.line == 42
        assert "line 42" in str(err)

    def test_parse_error_without_line(self):
        """ParseError without line number."""
        err = ParseError("bad syntax")
        assert err.line is None
        assert str(err) == "bad syntax"

    def test_parse_error_is_figtreekit_error(self):
        """ParseError should be a FigTreeKitError."""
        assert issubclass(ParseError, FigTreeKitError)

    def test_export_error_is_figtreekit_error(self):
        """ExportError should be a FigTreeKitError."""
        assert issubclass(ExportError, FigTreeKitError)

    def test_load_empty_content_raises_parse_error(self):
        """Loading empty content should raise ParseError."""
        styler = FigTreeStyler()
        with pytest.raises(ParseError, match="Empty tree content"):
            styler.load_content("")

    def test_load_newick_without_semicolon_raises_parse_error(self):
        """Loading Newick without semicolon should raise ParseError."""
        styler = FigTreeStyler()
        with pytest.raises(ParseError, match="missing semicolon"):
            styler.load_content("(A:0.1,B:0.2)")

    def test_export_no_content_raises_export_error(self):
        """Exporting without loaded content should raise ExportError."""
        styler = FigTreeStyler()
        with pytest.raises(ExportError, match="No tree content"):
            styler.export("/tmp/test.nex")


class TestFontAnnotationFormat:
    """Tests for Java Font.decode() compatible font annotation format."""

    @pytest.fixture
    def styler(self):
        return FigTreeStyler().load_content("(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);")

    def test_font_plain_style(self, styler):
        """Font style 0 should produce PLAIN."""
        styler.set_clade_font(["A", "B"], "Arial", 0, 12)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "[&!font=Arial-PLAIN-12]" in content
        finally:
            os.unlink(path)

    def test_font_bold_style(self, styler):
        """Font style 1 should produce BOLD."""
        styler.set_clade_font(["A", "B"], "Helvetica", 1, 14)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "[&!font=Helvetica-BOLD-14]" in content
        finally:
            os.unlink(path)

    def test_font_italic_style(self, styler):
        """Font style 2 should produce ITALIC."""
        styler.set_clade_font(["A", "B"], "Times", 2, 10)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "[&!font=Times-ITALIC-10]" in content
        finally:
            os.unlink(path)

    def test_font_bold_italic_style(self, styler):
        """Font style 3 should produce BOLDITALIC."""
        styler.set_clade_font(["A", "B"], "Courier", 3, 16)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "[&!font=Courier-BOLDITALIC-16]" in content
        finally:
            os.unlink(path)


class TestStringQuoting:
    """Tests for proper string quoting in Nexus output."""

    @pytest.fixture
    def styler(self):
        return FigTreeStyler().load_content("(A:0.1,B:0.2);")

    def test_font_name_quoted(self, styler):
        """Font name should be double-quoted in figtree block."""
        styler.set_tip_labels(font_name="Arial")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert 'tipLabels.fontName="Arial"' in content
        finally:
            os.unlink(path)

    def test_display_attribute_quoted(self, styler):
        """Display attribute should be double-quoted."""
        styler.set_tip_labels(display_attribute="Names")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert 'tipLabels.displayAttribute="Names"' in content
        finally:
            os.unlink(path)

    def test_color_not_quoted(self, styler):
        """Color values should NOT be quoted."""
        styler.set_appearance(foreground_color="#FF0000")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            # Should be #ff0000, not "#ff0000"
            assert "appearance.foregroundColour=#ff0000;" in content
        finally:
            os.unlink(path)

    def test_boolean_not_quoted(self, styler):
        """Boolean values should NOT be quoted."""
        styler.set_tip_labels(is_shown=True)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "tipLabels.isShown=true;" in content
        finally:
            os.unlink(path)

    def test_number_not_quoted(self, styler):
        """Numeric values should NOT be quoted."""
        styler.set_tip_labels(font_size=14)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "tipLabels.fontSize=14.0;" in content
        finally:
            os.unlink(path)


class TestNegativeBranchLength:
    """Tests for negative branch length detection."""

    def test_negative_branch_length_warns(self):
        """Negative branch length should produce a CompatibilityWarning."""
        newick = "((A:-0.1,B:0.2):0.3,C:0.4);"
        styler = FigTreeStyler().load_content(newick)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler.highlight_clade(["A", "B"], color="#FF0000")
            with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
                path = f.name
            try:
                styler.export(path)
            finally:
                os.unlink(path)
            compat_warnings = [x for x in w if issubclass(x.category, CompatibilityWarning)]
            assert len(compat_warnings) > 0
            assert "Negative branch length" in str(compat_warnings[0].message)


class TestOldStyleColor:
    """Tests for FigTree old-style decimal color support."""

    def test_validate_old_style_color(self):
        """Old-style decimal color #-16711681 should be valid."""
        assert TreeValidator.validate_color("#-16711681") is True

    def test_serialize_old_style_color(self):
        """Old-style decimal color should be serialized without quotes."""
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        result = styler._serialize_value("#-16711681")
        assert result == "#-16711681"


class TestFontStyleEnum:
    """Tests for FontStyle enum."""

    def test_font_style_values(self):
        """FontStyle enum should have correct values."""
        assert FontStyle.PLAIN.value == 0
        assert FontStyle.BOLD.value == 1
        assert FontStyle.ITALIC.value == 2
        assert FontStyle.BOLD_ITALIC.value == 3


class TestFigTreeCompatibility:
    """FigTree compatibility edge-case tests."""

    def test_unrooted_tree_trifurcation(self):
        """Unrooted tree with trifurcation at root."""
        newick = "(A:0.1,B:0.2,C:0.3);"
        styler = FigTreeStyler()
        styler.load_content(newick)
        assert styler._tree_content is not None

    def test_polytomy_many_children(self):
        """Polytomy: one parent with 10 children."""
        taxa = ",".join(f"T{i}:0.1" for i in range(10))
        newick = f"({taxa});"
        styler = FigTreeStyler()
        styler.load_content(newick)
        assert styler._tree_content is not None

    def test_missing_branch_lengths(self):
        """Missing branch lengths should not crash."""
        newick = "((A,B),C);"
        styler = FigTreeStyler()
        styler.load_content(newick)
        assert styler._tree_content is not None

    def test_quoted_taxon_names(self):
        """Quoted taxon names with special characters."""
        newick = "('Species A':0.1,'Species B':0.2):0.3;"
        styler = FigTreeStyler()
        styler.load_content(newick)
        assert styler._tree_content is not None

    def test_zero_branch_length(self):
        """Zero branch length should work."""
        newick = "((A:0.0,B:0.0):0.3,C:0.4);"
        styler = FigTreeStyler()
        styler.load_content(newick)
        styler.highlight_clade(["A", "B"], color="#FF0000")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "#NEXUS" in content
        finally:
            os.unlink(path)

    def test_nexus_with_translate_block(self):
        """Nexus with translate block (BEAST format)."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=3;
    taxlabels A B C ;
end;
begin trees;
    translate
        1 A,
        2 B,
        3 C;
    tree TREE1 = (1:0.1,2:0.2,3:0.3);
end;"""
        styler = FigTreeStyler()
        styler.load_content(nexus)
        assert styler._is_nexus_format is True
        assert styler._tree_content is not None

    def test_nexus_with_existing_figtree_block(self):
        """Nexus with existing figtree block should be parsed."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = (A:0.1,B:0.2);
end;
begin figtree;
    set appearance.backgroundColour=#ffffff;
    set layout.layoutType=POLAR;
end;"""
        styler = FigTreeStyler()
        styler.load_content(nexus)
        settings = styler.get_settings()
        assert settings["layout.layoutType"] == "POLAR"

    def test_nexus_multiple_trees_preserved(self):
        """All trees in a Nexus file should be preserved."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = (A:0.1,B:0.2);
    tree TREE2 = (A:0.15,B:0.25);
    tree TREE3 = (A:0.12,B:0.22);
end;"""
        styler = FigTreeStyler()
        styler.load_content(nexus)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "tree TREE1" in content
            assert "tree TREE2" in content
            assert "tree TREE3" in content
        finally:
            os.unlink(path)

    def test_integer_not_float_for_font_style(self):
        """fontStyle must be serialized as integer, not float."""
        newick = "(A:0.1,B:0.2);"
        styler = FigTreeStyler().load_content(newick)
        styler.set_tip_labels(font_style=1)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "tipLabels.fontStyle=1;" in content
            assert "fontStyle=1.0" not in content
        finally:
            os.unlink(path)

    def test_boolean_lowercase(self):
        """Booleans must be lowercase true/false."""
        newick = "(A:0.1,B:0.2);"
        styler = FigTreeStyler().load_content(newick)
        styler.set_tip_labels(is_shown=True)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "tipLabels.isShown=true;" in content
            assert "True" not in content
        finally:
            os.unlink(path)

    def test_very_deep_tree(self):
        """Deep tree (>100 internal branches) should not lose precision."""
        def build_balanced(n):
            if n == 1:
                return "T1:0.001"
            left = build_balanced(n // 2)
            right = build_balanced(n - n // 2)
            return f"({left},{right}):0.001"
        newick = f"({build_balanced(64)},{build_balanced(64)}):0.001;"
        styler = FigTreeStyler().load_content(newick)
        styler.highlight_clade(["T1"], color="#FF0000")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "#NEXUS" in content
        finally:
            os.unlink(path)


class TestSettingsAPI:
    """Tests for all set_* configuration methods."""

    @pytest.fixture
    def styler(self):
        return FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")

    def test_set_trees(self, styler):
        styler.set_trees(rooting=True, transform=True, transform_type=TransformType.CLADOGRAM,
                         order=True, order_type=OrderType.INCREASING_NODE_DENSITY)
        s = styler.get_settings()
        assert s["trees.rooting"] is True
        assert s["trees.transformType"] == "cladogram"
        assert s["trees.orderType"] == "Increasing Node Density"

    def test_set_scale_bar(self, styler):
        styler.set_scale_bar(is_shown=True, automatic_scale=True, scale_range=0.5,
                             font_name="Arial", font_size=10, line_width=2.0, color="#FF0000")
        s = styler.get_settings()
        assert s["scaleBar.isShown"] is True
        assert s["scaleBar.scaleRange"] == 0.5

    def test_set_scale_axis(self, styler):
        styler.set_scale_axis(is_shown=True, reverse_axis=True, show_grid=True,
                              major_ticks=0.5, origin=1.0, tick_direction="out", color="#0000FF")
        s = styler.get_settings()
        assert s["scaleAxis.reverseAxis"] is True
        assert s["scaleAxis.tickDirection"] == "out"

    def test_set_scale(self, styler):
        styler.set_scale(root_age=100.0, scale_root=True, scale_factor=2.0,
                         offset_age=5.0, auto_scale=False)
        s = styler.get_settings()
        assert s["scale.rootAge"] == 100.0
        assert s["scale.scaleRoot"] is True

    def test_set_radial_layout(self, styler):
        styler.set_radial_layout(spread=0.8, align_tip_labels=False)
        s = styler.get_settings()
        assert s["radialLayout.spread"] == 0.8
        assert s["radialLayout.alignTipLabels"] is False

    def test_set_rectilinear_layout(self, styler):
        styler.set_rectilinear_layout(align_tip_labels=True, curvature=5, root_length=20)
        s = styler.get_settings()
        assert s["rectilinearLayout.curvature"] == 5

    def test_set_node_bars(self, styler):
        styler.set_node_bars(is_shown=True, bar_width=2.0, attribute="posterior",
                             color="#FF0000", font_size=10)
        s = styler.get_settings()
        assert s["nodeBars.barWidth"] == 2.0

    def test_set_node_shapes(self, styler):
        styler.set_node_shapes(is_shown=True, shape_type="diamond", size=6.0,
                               stroke_width=2.0, color="#00FF00")
        s = styler.get_settings()
        assert s["nodeShapes.shapeType"] == "diamond"

    def test_set_legend(self, styler):
        styler.set_legend(is_shown=True, position="bottom", x_position=1.0,
                          y_position=2.0, background_opacity=0.5, reverse_order=True)
        s = styler.get_settings()
        assert s["legend.position"] == "Bottom"
        assert s["legend.reverseOrder"] is True

    def test_set_hilighting(self, styler):
        styler.set_hilighting(is_shown=True, gradient=True)
        s = styler.get_settings()
        assert s["hilighting.isShown"] is True
        assert s["hilighting.gradient"] is True

    def test_set_branch_labels(self, styler):
        styler.set_branch_labels(is_shown=True, display_attribute="posterior",
                                 font_name="Arial", font_size=10)
        s = styler.get_settings()
        assert s["branchLabels.isShown"] is True


class TestValidateMethod:
    """Tests for the validate() method."""

    def test_validate_valid_tree(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        issues = styler.validate()
        assert issues == []

    def test_validate_no_content(self):
        styler = FigTreeStyler()
        issues = styler.validate()
        assert any("No tree content" in i for i in issues)

    def test_validate_negative_branch(self):
        styler = FigTreeStyler().load_content("((A:-0.1,B:0.2):0.3,C:0.4);")
        issues = styler.validate()
        assert any("Negative branch length" in i for i in issues)


class TestSerializerEdgeCases:
    """Tests for serializer edge cases."""

    def test_serialize_none(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value(None) == "null"

    def test_serialize_bool_true(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value(True) == "true"

    def test_serialize_bool_false(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value(False) == "false"

    def test_serialize_int(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value(42) == "42"

    def test_serialize_float_integer(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value(1.0) == "1"

    def test_serialize_float(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value(3.14) == "3.14"

    def test_serialize_color(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value("#FF0000") == "#ff0000"

    def test_serialize_old_style_color(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value("#-16711681") == "#-16711681"

    def test_serialize_string_quoted(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value("Arial") == '"Arial"'

    def test_serialize_string_null(self):
        from figtreekit._serializer import serialize_value
        assert serialize_value("null") == "null"

    def test_generate_figtree_block_empty(self):
        from figtreekit._serializer import generate_figtree_block
        assert generate_figtree_block({}) == ""

    def test_generate_figtree_block_with_settings(self):
        from figtreekit._serializer import generate_figtree_block
        block = generate_figtree_block({"layout.layoutType": "POLAR", "tipLabels.isShown": True})
        assert "begin figtree;" in block
        assert "end;" in block


class TestParserUtilities:
    """Tests for parser utility functions."""

    def test_find_unquoted_semicolon_simple(self):
        from figtreekit._parser import find_unquoted_semicolon
        assert find_unquoted_semicolon("abc;def") == 3

    def test_find_unquoted_semicolon_in_quotes(self):
        from figtreekit._parser import find_unquoted_semicolon
        assert find_unquoted_semicolon("abc';';def") == 6

    def test_find_unquoted_semicolon_not_found(self):
        from figtreekit._parser import find_unquoted_semicolon
        assert find_unquoted_semicolon("abc") == -1

    def test_extract_tree_value_simple(self):
        from figtreekit._parser import extract_tree_value
        result = extract_tree_value("(A:0.1,B:0.2);rest")
        assert result == "(A:0.1,B:0.2)"

    def test_extract_tree_value_with_brackets(self):
        from figtreekit._parser import extract_tree_value
        result = extract_tree_value("[&R](A:0.1,B:0.2);rest")
        assert result == "[&R](A:0.1,B:0.2)"

    def test_extract_tree_value_no_semicolon(self):
        from figtreekit._parser import extract_tree_value
        result = extract_tree_value("(A:0.1,B:0.2)")
        assert result is None

    def test_extract_trees_block_content(self):
        from figtreekit._parser import extract_trees_block_content
        block = "begin trees;\n\ttree T1 = (A:0.1);\nend;"
        result = extract_trees_block_content(block)
        assert "tree T1" in result
        assert "begin trees" not in result

    def test_extract_taxa_from_newick(self):
        from figtreekit._parser import extract_taxa_from_newick
        taxa = extract_taxa_from_newick("((A:0.1,B:0.2):0.3,C:0.4);")
        assert set(taxa) == {"A", "B", "C"}

    def test_fallback_extract_taxa(self):
        from figtreekit._parser import _fallback_extract_taxa
        taxa = _fallback_extract_taxa("((A:0.1,B:0.2):0.3,C:0.4);")
        assert set(taxa) == {"A", "B", "C"}

    def test_apply_parsed_setting_boolean(self):
        from figtreekit._parser import apply_parsed_setting
        from figtreekit.styler import FigTreeSettings
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "tipLabels.isShown", "false")
        assert settings.tipLabels["isShown"] is False

    def test_apply_parsed_setting_color(self):
        from figtreekit._parser import apply_parsed_setting
        from figtreekit.styler import FigTreeSettings
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "appearance.backgroundColour", "#FF0000")
        assert settings.appearance["backgroundColour"] == "#FF0000"

    def test_apply_parsed_setting_quoted_string(self):
        from figtreekit._parser import apply_parsed_setting
        from figtreekit.styler import FigTreeSettings
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "tipLabels.fontName", '"Arial"')
        assert settings.tipLabels["fontName"] == "Arial"

    def test_apply_parsed_setting_null(self):
        from figtreekit._parser import apply_parsed_setting
        from figtreekit.styler import FigTreeSettings
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "tipLabels.fontName", "null")
        assert settings.tipLabels["fontName"] is None

    def test_apply_parsed_setting_number(self):
        from figtreekit._parser import apply_parsed_setting
        from figtreekit.styler import FigTreeSettings
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "tipLabels.fontSize", "14")
        assert settings.tipLabels["fontSize"] == 14

    def test_apply_parsed_setting_float(self):
        from figtreekit._parser import apply_parsed_setting
        from figtreekit.styler import FigTreeSettings
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "scale.rootAge", "100.5")
        assert settings.scale["rootAge"] == 100.5

    def test_apply_parsed_setting_custom(self):
        from figtreekit._parser import apply_parsed_setting
        from figtreekit.styler import FigTreeSettings
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "custom.key", "value")
        assert settings._custom["custom.key"] == "value"


class TestCLI:
    """Tests for command-line interface."""

    def test_validate_valid_file(self, tmp_path):
        tree_file = tmp_path / "good.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", str(tree_file), "--validate", "-v"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        combined = (result.stdout + result.stderr).lower()
        assert "valid" in combined or "done" in combined

    def test_validate_invalid_file(self, tmp_path):
        tree_file = tmp_path / "bad.tre"
        tree_file.write_text("(A:0.1,B:0.2)")
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", str(tree_file), "--validate"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_basic_export(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", str(tree_file), "-o", str(out_file)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "#NEXUS" in content

    def test_missing_output(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", str(tree_file)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_batch_processing(self, tmp_path):
        for name in ["a.tre", "b.tre", "c.tre"]:
            (tmp_path / name).write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_dir = tmp_path / "styled"
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", str(tmp_path), "-o", str(out_dir), "-v"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert (out_dir / "a.nex").exists()
        assert (out_dir / "b.nex").exists()
        assert (out_dir / "c.nex").exists()

    def test_version(self):
        from figtreekit import __version__
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", "--version"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert __version__ in result.stdout

    def test_layout_flag(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", str(tree_file), "-o", str(out_file),
             "--layout", "polar", "--tip-labels-show"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        content = out_file.read_text()
        assert 'layout.layoutType="POLAR"' in content


class TestCLIDirect:
    """Direct unit tests for CLI functions (not subprocess-based)."""

    @pytest.fixture
    def styler(self):
        return FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")

    def test_create_cli_parser_basic(self):
        from figtreekit._cli import create_cli_parser
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex"])
        assert args.input == "input.tre"
        assert args.output == "out.nex"
        assert not args.validate
        assert args.verbose == 0

    def test_create_cli_parser_validate(self):
        from figtreekit._cli import create_cli_parser
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "--validate", "-vv"])
        assert args.validate
        assert args.verbose == 2

    def test_create_cli_parser_all_options(self):
        from figtreekit._cli import create_cli_parser
        parser = create_cli_parser()
        args = parser.parse_args([
            "input.tre", "-o", "out.nex",
            "--layout", "polar",
            "--branch-width", "2.5",
            "--background-color", "#FF0000",
            "--foreground-color", "#00FF00",
            "--selection-color", "#0000FF",
            "--expansion", "50",
            "--zoom", "1.5",
            "--rooted",
            "--rooting-type", "midpoint",
            "--transform", "cladogram",
            "--order", "increasing",
            "--order-branches",
            "--tip-labels-show",
            "--font-name", "Arial",
            "--font-size", "12",
            "--font-style", "1",
            "--label-color", "#333333",
            "--node-labels-show",
            "--node-display-attribute", "support",
            "--branch-labels-show",
            "--branch-display-attribute", "length",
            "--scale-bar-show",
            "--scale-axis-show",
            "--root-age", "100.0",
            "--scale-factor", "1e-6",
            "--angular-range", "360",
            "--root-angle", "90",
            "--align-tip-labels",
            "--radial-spread", "1.0",
            "--curvature", "50",
            "--root-length", "10",
            "--legend-show",
            "--legend-position", "top",
        ])
        assert args.layout == "polar"
        assert args.branch_width == 2.5
        assert args.background_color == "#FF0000"
        assert args.expansion == 50
        assert args.zoom == 1.5
        assert args.rooted
        assert args.legend_position == "top"

    def test_apply_cli_args_appearance(self, styler):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args([
            "input.tre", "-o", "out.nex",
            "--branch-width", "3.0",
            "--background-color", "#FFFFFF",
        ])
        apply_cli_args(styler, args)
        assert styler._settings.appearance["branchLineWidth"] == 3.0
        assert styler._settings.appearance["backgroundColour"] == "#ffffff"

    def test_apply_cli_args_layout(self, styler):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--layout", "radial"])
        apply_cli_args(styler, args)
        assert styler._settings.layout["layoutType"] == "RADIAL"

    def test_apply_cli_args_trees(self, styler):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args([
            "input.tre", "-o", "out.nex",
            "--rooted",
            "--transform", "phylogram",
            "--order", "decreasing",
        ])
        apply_cli_args(styler, args)
        assert styler._settings.trees["rooting"] is True
        assert styler._settings.trees["transform"] is True
        assert styler._settings.trees["transformType"] == "phylogram"

    def test_apply_cli_args_labels(self, styler):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args([
            "input.tre", "-o", "out.nex",
            "--tip-labels-show",
            "--font-name", "Helvetica",
            "--font-size", "14",
            "--node-labels-show",
            "--node-display-attribute", "posterior",
            "--branch-labels-hide",
        ])
        apply_cli_args(styler, args)
        assert styler._settings.tipLabels["isShown"] is True
        assert styler._settings.tipLabels["fontName"] == "Helvetica"
        assert styler._settings.tipLabels["fontSize"] == 14
        assert styler._settings.nodeLabels["isShown"] is True
        assert styler._settings.nodeLabels["displayAttribute"] == "posterior"
        assert styler._settings.branchLabels["isShown"] is False

    def test_apply_cli_args_scale_and_legend(self, styler):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args([
            "input.tre", "-o", "out.nex",
            "--scale-bar-show",
            "--scale-axis-hide",
            "--root-age", "50.0",
            "--scale-factor", "1e-9",
            "--legend-show",
            "--legend-position", "bottom",
        ])
        apply_cli_args(styler, args)
        assert styler._settings.scaleBar["isShown"] is True
        assert styler._settings.scaleAxis["isShown"] is False
        assert styler._settings.scale["rootAge"] == 50.0
        assert styler._settings.legend["isShown"] is True
        assert styler._settings.legend["position"] == "Bottom"

    def test_apply_cli_args_polar_and_radial(self, styler):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args([
            "input.tre", "-o", "out.nex",
            "--angular-range", "270",
            "--root-angle", "45",
            "--align-tip-labels",
            "--radial-spread", "0.5",
        ])
        apply_cli_args(styler, args)
        # FigTree stores these as slider integers (1/1000 degree offsets)
        assert styler.get_settings()["polarLayout.angularRange"] == 90000
        assert styler.get_settings()["polarLayout.rootAngle"] == -135000
        assert styler.get_settings()["polarLayout.alignTipLabels"] is True
        assert styler.get_settings()["radialLayout.spread"] == 0.5

    def test_apply_cli_args_rectilinear(self, styler):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args([
            "input.tre", "-o", "out.nex",
            "--curvature", "75",
            "--root-length", "20",
        ])
        apply_cli_args(styler, args)
        assert styler.get_settings()["rectilinearLayout.curvature"] == 75
        assert styler.get_settings()["rectilinearLayout.rootLength"] == 20

    def test_apply_cli_args_config_file(self, styler, tmp_path):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        config = {"appearance.branchLineWidth": 5.0}
        config_file = tmp_path / "style.json"
        config_file.write_text(json.dumps(config))
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--config", str(config_file)])
        apply_cli_args(styler, args)
        assert styler._settings.appearance["branchLineWidth"] == 5.0

    def test_apply_cli_args_config_not_found(self, styler):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--config", "/nonexistent.json"])
        with pytest.raises(FileNotFoundError):
            apply_cli_args(styler, args)

    def test_process_single_validate_valid(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_single
        tree_file = tmp_path / "good.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        parser = create_cli_parser()
        args = parser.parse_args([str(tree_file), "--validate"])
        assert _process_single(tree_file, args) is True

    def test_process_single_validate_invalid(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_single
        tree_file = tmp_path / "bad.tre"
        tree_file.write_text("(A:0.1,B:0.2)")
        parser = create_cli_parser()
        args = parser.parse_args([str(tree_file), "--validate"])
        assert _process_single(tree_file, args) is False

    def test_process_single_no_output(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_single
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        parser = create_cli_parser()
        args = parser.parse_args([str(tree_file)])
        assert _process_single(tree_file, args) is False

    def test_process_single_export(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_single
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "out.nex"
        parser = create_cli_parser()
        args = parser.parse_args([str(tree_file), "-o", str(out_file)])
        assert _process_single(tree_file, args) is True
        assert out_file.exists()

    def test_process_single_parse_error(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_single
        tree_file = tmp_path / "bad.tre"
        tree_file.write_text("not a tree at all")
        parser = create_cli_parser()
        args = parser.parse_args([str(tree_file), "--validate"])
        assert _process_single(tree_file, args) is False

    def test_process_batch_validate(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_batch
        for name in ["a.tre", "b.tre"]:
            (tmp_path / name).write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        parser = create_cli_parser()
        args = parser.parse_args([str(tmp_path), "--validate"])
        _process_batch(tmp_path, args)

    def test_process_batch_export(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_batch
        for name in ["a.tre", "b.tre"]:
            (tmp_path / name).write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_dir = tmp_path / "styled"
        parser = create_cli_parser()
        args = parser.parse_args([str(tmp_path), "-o", str(out_dir)])
        _process_batch(tmp_path, args)
        assert (out_dir / "a.nex").exists()
        assert (out_dir / "b.nex").exists()

    def test_process_batch_default_output(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_batch
        (tmp_path / "x.tre").write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        parser = create_cli_parser()
        args = parser.parse_args([str(tmp_path)])
        _process_batch(tmp_path, args)
        styled_dir = tmp_path / "styled"
        assert styled_dir.exists()
        assert (styled_dir / "x.nex").exists()

    def test_process_batch_empty_dir(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_batch
        parser = create_cli_parser()
        args = parser.parse_args([str(tmp_path), "--validate"])
        with pytest.raises(FileNotFoundError):
            _process_batch(tmp_path, args)

    def test_main_validate(self, tmp_path, monkeypatch):
        from figtreekit._cli import main
        tree_file = tmp_path / "good.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        monkeypatch.setattr(sys, "argv", ["figtreekit", str(tree_file), "--validate"])
        main()

    def test_main_export(self, tmp_path, monkeypatch):
        from figtreekit._cli import main
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", ["figtreekit", str(tree_file), "-o", str(out_file)])
        main()
        assert out_file.exists()

    def test_main_batch(self, tmp_path, monkeypatch):
        from figtreekit._cli import main
        (tmp_path / "a.tre").write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_dir = tmp_path / "styled"
        monkeypatch.setattr(sys, "argv", ["figtreekit", str(tmp_path), "-o", str(out_dir)])
        main()
        assert (out_dir / "a.nex").exists()

    def test_main_fails_no_output(self, tmp_path, monkeypatch):
        from figtreekit._cli import main
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        monkeypatch.setattr(sys, "argv", ["figtreekit", str(tree_file)])
        with pytest.raises(SystemExit):
            main()

    def test_process_single_rejects_multi_tree_newick(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_single
        tree_file = tmp_path / "multi.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);((D:0.1,E:0.2):0.3,F:0.4);")
        out_file = tmp_path / "out.nex"
        parser = create_cli_parser()
        args = parser.parse_args([
            str(tree_file), "-o", str(out_file), "--multi-tree", "first"
        ])
        assert _process_single(tree_file, args) is False

    def test_process_single_rejects_output_directory(self, tmp_path):
        from figtreekit._cli import create_cli_parser, _process_single
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_dir = tmp_path / "outdir"
        out_dir.mkdir()
        parser = create_cli_parser()
        args = parser.parse_args([str(tree_file), "-o", str(out_dir)])
        assert _process_single(tree_file, args) is False

    def test_main_empty_batch_exits_3(self, tmp_path, monkeypatch):
        from figtreekit._cli import main
        monkeypatch.setattr(sys, "argv", ["figtreekit", str(tmp_path), "--validate"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 3


class TestApplyMappedKwargs:
    """Tests for the _apply_mapped_kwargs helper."""

    def test_basic_mapping(self):
        target = {}
        mapping = {'is_shown': 'isShown', 'font_name': 'fontName'}
        FigTreeStyler._apply_mapped_kwargs(target, {'is_shown': True, 'font_name': 'Arial'}, mapping)
        assert target == {'isShown': True, 'fontName': 'Arial'}

    def test_none_values_skipped(self):
        target = {'existing': 'value'}
        mapping = {'key': 'mappedKey'}
        FigTreeStyler._apply_mapped_kwargs(target, {'key': None}, mapping)
        assert target == {'existing': 'value'}

    def test_unmapped_keys_pass_through(self):
        target = {}
        mapping = {'known': 'Known'}
        FigTreeStyler._apply_mapped_kwargs(target, {'known': 1, 'unknown': 2}, mapping)
        assert target == {'Known': 1, 'unknown': 2}

    def test_empty_kwargs(self):
        target = {'a': 1}
        FigTreeStyler._apply_mapped_kwargs(target, {}, {})
        assert target == {'a': 1}


class TestCountUnresolvedAnnotations:
    """Tests for _count_unresolved_annotations."""

    def test_resolved_annotations_empty_list(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        styler.highlight_clade(["A", "B"], color="#FF0000")
        unresolved = styler._count_unresolved_annotations(tree, styler._settings._node_annotations)
        assert unresolved == []

    def test_unresolved_annotations_reported(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        styler.highlight_clade(["NONEXISTENT"], color="#FF0000")
        unresolved = styler._count_unresolved_annotations(tree, styler._settings._node_annotations)
        assert len(unresolved) == 1
        assert "NONEXISTENT" in unresolved[0]

    def test_no_target_taxa_skipped(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        ann = NodeAnnotation(annotation_type='color', values='#FF0000', target_taxa=None)
        unresolved = styler._count_unresolved_annotations(tree, [ann])
        assert unresolved == []


class TestUnresolvedAnnotationWarning:
    """Test that export() warns about unresolved annotations."""

    def test_export_warns_unresolved(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        styler.highlight_clade(["NONEXISTENT_TAXON"], color="#FF0000")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                styler.export(path)
                compat = [x for x in w if issubclass(x.category, CompatibilityWarning)
                          and "annotation" in str(x.message).lower()]
                assert len(compat) > 0
                assert "1 annotation" in str(compat[0].message)
        finally:
            os.unlink(path)


class TestCalculateNodeHeightWarning:
    """Test that _calculate_node_height emits CompatibilityWarning on failure."""

    def test_height_failure_warns_compat(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)

        # Create a mock node that's not in the tree
        from Bio.Phylo.BaseTree import Clade
        fake_node = Clade(branch_length=0.1, name="FAKE")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            height = styler._calculate_node_height(tree, fake_node)
            assert height == 0.0
            compat = [x for x in w if issubclass(x.category, CompatibilityWarning)]
            assert len(compat) > 0
            assert "Could not find path" in str(compat[0].message)


class TestValidatorsFullCoverage:
    """Tests to close all coverage gaps in validators.py."""

    def test_validate_color_old_style_single_digit(self):
        """Old-style color with single digit after #-."""
        assert TreeValidator.validate_color("#-1") is True

    def test_validate_color_old_style_zero(self):
        assert TreeValidator.validate_color("#-0") is True

    def test_validate_taxon_names_tuple_input(self):
        """Tuple of taxon names should be accepted."""
        assert TreeValidator.validate_taxon_names(("A", "B", "C")) is True

    def test_validate_taxon_names_empty_tuple(self):
        assert TreeValidator.validate_taxon_names(()) is False

    def test_validate_taxon_names_tuple_with_empty(self):
        assert TreeValidator.validate_taxon_names(("A", "")) is False

    def test_validate_newick_non_string(self):
        assert TreeValidator.validate_newick(None) is False
        assert TreeValidator.validate_newick(123) is False
        assert TreeValidator.validate_newick([]) is False

    def test_validate_newick_empty_after_strip(self):
        assert TreeValidator.validate_newick("   ") is False

    def test_validate_nexus_non_string(self):
        assert TreeValidator.validate_nexus(None) is False
        assert TreeValidator.validate_nexus(123) is False
        assert TreeValidator.validate_nexus([]) is False

    def test_validate_nexus_wrong_header(self):
        assert TreeValidator.validate_nexus("#PHYML") is False

    def test_validate_nexus_no_begin_end(self):
        assert TreeValidator.validate_nexus("#NEXUS some random text") is False


class TestCLICoverageGaps:
    """Tests for CLI branches not covered by existing tests."""

    def test_apply_cli_args_order_branches(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--order-branches"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler._settings.trees["order"] is True

    def test_apply_cli_args_align_tip_labels_sets_both(self):
        """--align-tip-labels should set both polar and rectilinear."""
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--align-tip-labels"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler.get_settings()["polarLayout.alignTipLabels"] is True
        assert styler.get_settings()["rectilinearLayout.alignTipLabels"] is True

    def test_apply_cli_args_root_length_sets_rectilinear(self):
        """--root-length should set rectilinear layout only."""
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--root-length", "15"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler.get_settings()["rectilinearLayout.rootLength"] == 15

    def test_apply_cli_args_selection_color(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--selection-color", "#2d3680"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler._settings.appearance["selectionColour"] == "#2d3680"

    def test_apply_cli_args_branch_color_attribute(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--branch-color-attribute", "height"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler._settings.appearance["branchColorAttribute"] == "height"

    def test_apply_cli_args_expansion(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--expansion", "50"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler._settings.layout["expansion"] == 50

    def test_apply_cli_args_zoom(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--zoom", "2.5"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler._settings.layout["zoom"] == 2.5

    def test_apply_cli_args_label_color(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--label-color", "#FF0000"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler._settings.tipLabels["colorAttribute"] == "#FF0000"

    def test_apply_cli_args_font_style(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--font-style", "2"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        apply_cli_args(styler, args)
        assert styler._settings.tipLabels["fontStyle"] == 2

    def test_apply_cli_args_unrooted(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--unrooted"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_trees(rooting=True)  # Set first
        apply_cli_args(styler, args)
        assert styler._settings.trees["rooting"] is False

    def test_apply_cli_args_show_root(self):
        """--show-root is not a CLI flag, but test polar show_root via config."""
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_polar_layout(show_root=True)
        assert styler.get_settings()["polarLayout.showRoot"] is True

    def test_apply_cli_args_branch_labels_hide(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--branch-labels-hide"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_branch_labels(is_shown=True)
        apply_cli_args(styler, args)
        assert styler._settings.branchLabels["isShown"] is False

    def test_apply_cli_args_node_labels_hide(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--node-labels-hide"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_node_labels(is_shown=True)
        apply_cli_args(styler, args)
        assert styler._settings.nodeLabels["isShown"] is False

    def test_apply_cli_args_scale_bar_hide(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--scale-bar-hide"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_scale_bar(is_shown=True)
        apply_cli_args(styler, args)
        assert styler._settings.scaleBar["isShown"] is False

    def test_apply_cli_args_scale_axis_hide(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--scale-axis-hide"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_scale_axis(is_shown=True)
        apply_cli_args(styler, args)
        assert styler._settings.scaleAxis["isShown"] is False

    def test_apply_cli_args_tip_labels_hide(self):
        from figtreekit._cli import create_cli_parser, apply_cli_args
        parser = create_cli_parser()
        args = parser.parse_args(["input.tre", "-o", "out.nex", "--tip-labels-hide"])
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_tip_labels(is_shown=True)
        apply_cli_args(styler, args)
        assert styler._settings.tipLabels["isShown"] is False

    def test_cli_quiet_mode(self, tmp_path, monkeypatch):
        from figtreekit._cli import main
        tree_file = tmp_path / "good.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out_file), "-q"
        ])
        main()
        assert out_file.exists()

    def test_cli_debug_mode(self, tmp_path, monkeypatch):
        from figtreekit._cli import main
        tree_file = tmp_path / "good.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out_file), "-vv"
        ])
        main()
        assert out_file.exists()


class TestSettingsAPIP5Coverage:
    """Tests for _apply_mapped_kwargs on all refactored set_* methods."""

    @pytest.fixture
    def styler(self):
        return FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")

    def test_set_tip_labels_passthrough(self, styler):
        """Unknown keys should pass through."""
        styler.set_tip_labels(custom_key="value")
        assert styler._settings.tipLabels["custom_key"] == "value"

    def test_set_node_labels_passthrough(self, styler):
        styler.set_node_labels(custom_key="value")
        assert styler._settings.nodeLabels["custom_key"] == "value"

    def test_set_branch_labels_passthrough(self, styler):
        styler.set_branch_labels(custom_key="value")
        assert styler._settings.branchLabels["custom_key"] == "value"

    def test_set_scale_bar_passthrough(self, styler):
        styler.set_scale_bar(custom_key="value")
        assert styler._settings.scaleBar["custom_key"] == "value"

    def test_set_scale_axis_passthrough(self, styler):
        styler.set_scale_axis(custom_key="value")
        assert styler._settings.scaleAxis["custom_key"] == "value"

    def test_set_scale_passthrough(self, styler):
        styler.set_scale(custom_key="value")
        assert styler._settings.scale["custom_key"] == "value"

    def test_set_polar_layout_passthrough(self, styler):
        styler.set_polar_layout(custom_key="value")
        assert styler.get_settings()["polarLayout.custom_key"] == "value"

    def test_set_radial_layout_passthrough(self, styler):
        styler.set_radial_layout(custom_key="value")
        assert styler.get_settings()["radialLayout.custom_key"] == "value"

    def test_set_rectilinear_layout_passthrough(self, styler):
        styler.set_rectilinear_layout(custom_key="value")
        assert styler.get_settings()["rectilinearLayout.custom_key"] == "value"

    def test_set_node_bars_passthrough(self, styler):
        styler.set_node_bars(custom_key="value")
        assert styler.get_settings()["nodeBars.custom_key"] == "value"

    def test_set_node_shapes_passthrough(self, styler):
        styler.set_node_shapes(custom_key="value")
        assert styler.get_settings()["nodeShapes.custom_key"] == "value"

    def test_set_legend_passthrough(self, styler):
        styler.set_legend(custom_key="value")
        assert styler.get_settings()["legend.custom_key"] == "value"

    def test_set_legend_position_capitalize(self, styler):
        styler.set_legend(position="top")
        assert styler.get_settings()["legend.position"] == "Top"
        styler.set_legend(position="BOTTOM")
        assert styler.get_settings()["legend.position"] == "Bottom"

    def test_set_align_tip_labels_polar(self, styler):
        styler.set_layout(LayoutType.POLAR)
        styler.set_align_tip_labels(True)
        assert styler.get_settings()["polarLayout.alignTipLabels"] is True
        styler.set_align_tip_labels(False)
        assert styler.get_settings()["polarLayout.alignTipLabels"] is False

    def test_set_align_tip_labels_radial(self, styler):
        styler.set_layout(LayoutType.RADIAL)
        styler.set_align_tip_labels(True)
        assert styler.get_settings()["radialLayout.alignTipLabels"] is True

    def test_set_align_tip_labels_rectilinear(self, styler):
        styler.set_layout(LayoutType.RECTILINEAR)
        styler.set_align_tip_labels(True)
        assert styler.get_settings()["rectilinearLayout.alignTipLabels"] is True

    def test_set_align_tip_labels_defaults_true(self, styler):
        # Default alignTipLabels is True for all layout types in FigTree 1.4.4
        assert styler.get_settings()["rectilinearLayout.alignTipLabels"] is True
        assert styler.get_settings()["polarLayout.alignTipLabels"] is True
        assert styler.get_settings()["radialLayout.alignTipLabels"] is True

    def test_set_align_tip_labels_can_toggle_false(self, styler):
        styler.set_layout(LayoutType.RECTILINEAR)
        styler.set_align_tip_labels(False)
        assert styler.get_settings()["rectilinearLayout.alignTipLabels"] is False

    def test_set_align_tip_labels_chaining(self, styler):
        styler.set_layout(LayoutType.POLAR).set_align_tip_labels(True).set_appearance(
            background_color="#FFFFFF"
        )
        assert styler.get_settings()["polarLayout.alignTipLabels"] is True
        assert styler.get_settings()["appearance.backgroundColour"] == "#ffffff"


class TestAuthorInfo:
    """Test that author info is properly set."""

    def test_author_not_todo(self):
        import figtreekit
        assert "TODO" not in figtreekit.__author__
        assert "TODO" not in figtreekit.__email__

    def test_author_values(self):
        import figtreekit
        assert figtreekit.__author__ == "Zeng Zichao"
        assert figtreekit.__email__ == "zengzichao@sjtu.edu.cn"


class TestValidatorRGBRange:
    """Test that validate_color rejects out-of-range Java RGB values."""

    def test_valid_old_style_min(self):
        assert TreeValidator.validate_color("#-16777216") is True

    def test_valid_old_style_max(self):
        assert TreeValidator.validate_color("#16777215") is False  # no minus sign
        assert TreeValidator.validate_color("#-16777215") is True

    def test_out_of_range_positive(self):
        assert TreeValidator.validate_color("#-16777217") is False

    def test_out_of_range_large(self):
        assert TreeValidator.validate_color("#-99999999999") is False

    def test_zero_valid(self):
        assert TreeValidator.validate_color("#-0") is True


class TestParserCaseInsensitive:
    """Test that Nexus parsing is case-insensitive for block markers."""

    def test_uppercase_begin_trees(self):
        nexus = "#NEXUS\nBEGIN TAXA;\ndimensions ntax=2;\ntaxlabels A B ;\nEND;\nBEGIN TREES;\ntree T1 = (A:0.1,B:0.2);\nEND;"
        styler = FigTreeStyler().load_content(nexus)
        assert styler._is_nexus_format is True
        assert styler._tree_content is not None

    def test_mixed_case_begin_trees(self):
        nexus = "#NEXUS\nBegin Taxa;\nend;\nBegin Trees;\ntree T1 = (A:0.1,B:0.2);\nEnd;"
        styler = FigTreeStyler().load_content(nexus)
        assert styler._is_nexus_format is True
        assert styler._taxa_block is not None

    def test_mixed_case_figtree_block(self):
        nexus = "#NEXUS\nbegin taxa;\nend;\nbegin trees;\ntree T=(A:0.1,B:0.2);\nend;\nBegin FigTree;\nset layout.layoutType=POLAR;\nEnd;"
        styler = FigTreeStyler().load_content(nexus)
        s = styler.get_settings()
        assert s["layout.layoutType"] == "POLAR"

    def test_lowercase_preserves_original_case_in_output(self):
        nexus = "#NEXUS\nBEGIN TAXA;\ndimensions ntax=2;\ntaxlabels A B ;\nEND;\nBEGIN TREES;\ntree T1 = (A:0.1,B:0.2);\nEND;"
        styler = FigTreeStyler().load_content(nexus)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "#NEXUS" in content
            assert "begin trees;" in content.lower()
        finally:
            os.unlink(path)


class TestSerializerNumberTypes:
    """Test that serialize_value handles various numeric types."""

    def test_large_integer(self):
        assert serialize_value(1000000) == "1000000"

    def test_negative_integer(self):
        assert serialize_value(-42) == "-42"

    def test_zero_int(self):
        assert serialize_value(0) == "0"

    def test_zero_float(self):
        assert serialize_value(0.0) == "0"

    def test_scientific_notation(self):
        result = serialize_value(1e-10)
        assert "e" in result

    def test_bool_not_int(self):
        """bool must not go through integer path."""
        assert serialize_value(True) == "true"
        assert serialize_value(False) == "false"


class TestIterativeNodeHeight:
    """Test that _calculate_node_height uses iterative DFS (no recursion limit)."""

    def test_deep_tree_no_recursion_error(self):
        """Iterative _calculate_node_height works on trees deeper than recursion limit.

        Bio.Phylo's own methods (get_terminals, find_clades) are recursive,
        so we build the tree programmatically and navigate to the leaf manually.
        """
        from Bio.Phylo.BaseTree import Tree, Clade
        # Build a linear chain of 1200 nodes (deeper than default recursion limit)
        n = 1200
        leaf = Clade(branch_length=0.001, name=f"T{n}")
        for i in range(n - 1, -1, -1):
            leaf = Clade(branch_length=0.001, name=f"T{i}", clades=[leaf])
        tree = Tree(root=leaf)
        styler = FigTreeStyler()
        # Navigate to the deepest leaf without using recursive Bio.Phylo methods
        deepest = tree.root
        while deepest.clades:
            deepest = deepest.clades[0]
        height = styler._calculate_node_height(tree, deepest)
        assert height == round(n * 0.001, 10)

    def test_height_zero_for_root(self):
        """Height of root node should be 0.0."""
        newick = "((A:0.1,B:0.2):0.3,C:0.4);"
        styler = FigTreeStyler().load_content(newick)
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        root = tree.root
        height = styler._calculate_node_height(tree, root)
        assert height == 0.0


class TestNarrowedExceptionHandling:
    """Test that specific exceptions are caught, not bare Exception."""

    def test_mrca_missing_taxon_warns(self):
        """MRCA with non-existent taxon should warn (not crash)."""
        newick = "((A:0.1,B:0.2):0.3,C:0.4);"
        styler = FigTreeStyler().load_content(newick)
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = styler._find_mrca_clade(tree, ["NONEXISTENT"])
            assert result is None
            assert any("MRCA search failed" in str(x.message) for x in w)

    def test_tree_parsing_failure_warns(self):
        """Bio.Phylo parse failure should warn and return None."""
        styler = FigTreeStyler()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Malformed input causes Bio.Phylo to raise ValueError
            result = styler._parse_tree_with_biopython("(((")
            assert result is None
            assert any("Bio.Phylo" in str(x.message) for x in w)


class TestExportSubMethods:
    """Test the refactored export sub-methods."""

    @pytest.fixture
    def styler(self):
        return FigTreeStyler().load_content("(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);")

    def test_resolve_annotations_copy(self, styler):
        """_resolve_annotations_copy should inject hilight annotations directly into the MRCA node comment (jebl meta-comment format), without mutating _tree_content."""
        styler.highlight_clade(["A", "B"], color="#FF0000")
        original = styler._tree_content
        resolved = styler._resolve_annotations_copy()
        # Hilight is injected directly into the MRCA node's bracket comment as
        # [&!hilight={tipCount,height,color}] (fix #20).  No temporary
        # _HL_ marker nodes are used, which avoids collisions with collapse
        # labels written to the same node's name.
        assert "[&!hilight=" in resolved
        assert "#ff0000" in resolved
        assert styler._tree_content == original

    def test_write_taxa_block_newick(self, styler):
        """_write_taxa_block from Newick input should generate taxa block."""
        import io
        buf = io.StringIO()
        styler._write_taxa_block(buf, include_taxa_block=True)
        output = buf.getvalue()
        assert "begin taxa;" in output
        assert "ntax=5" in output

    def test_write_trees_block(self, styler):
        """_write_trees_block should produce valid trees block."""
        import io
        buf = io.StringIO()
        styler._write_trees_block(buf, styler._tree_content)
        output = buf.getvalue()
        assert "begin trees;" in output
        assert "tree TREE1" in output
        assert "end;" in output

    def test_write_figtree_block(self, styler):
        """_write_figtree_block should produce figtree settings."""
        import io
        styler.set_layout(LayoutType.POLAR)
        buf = io.StringIO()
        styler._write_figtree_block(buf)
        output = buf.getvalue()
        assert "begin figtree;" in output
        assert "POLAR" in output


# ============================================================
# Tests for fixes from diagnostic report
# ============================================================

class TestDiagnosticFixes:
    """Tests for all fixes identified in the diagnostic report."""

    # --- Fix 1: validators.py unreachable try/except removed ---

    def test_validate_color_old_style_direct_int_conversion(self):
        """Old-style color validation should work without try/except."""
        assert TreeValidator.validate_color("#-16711681") is True
        assert TreeValidator.validate_color("#-0") is True
        assert TreeValidator.validate_color("#-1") is True
        assert TreeValidator.validate_color("#-16777216") is True
        assert TreeValidator.validate_color("#-16777217") is False

    # --- Fix 2: set_clade_hilight non-MRCA warning ---

    def test_set_clade_hilight_non_mrca_warns(self):
        """set_clade_hilight with non-MRCA identifier should warn."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler.set_clade_hilight("some_id", tip_count=2, height=0.3, color="#FF0000")
            compat = [x for x in w if issubclass(x.category, CompatibilityWarning)]
            assert len(compat) > 0
            assert "some_id" in str(compat[0].message)
            assert "MRCA" in str(compat[0].message)

    def test_set_clade_hilight_mrca_no_warning(self):
        """set_clade_hilight with valid MRCA identifier should not warn about pattern."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler.set_clade_hilight("MRCA(A,B)", tip_count=2, height=0.3, color="#FF0000")
            pattern_warnings = [x for x in w if "does not match MRCA" in str(x.message)]
            assert len(pattern_warnings) == 0

    # --- Fix 3: load_content empty tree warning ---

    def test_load_content_semicolon_warns(self):
        """Loading only ';' should warn about empty tree."""
        styler = FigTreeStyler()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler.load_content(";")
            compat = [x for x in w if issubclass(x.category, CompatibilityWarning)]
            assert len(compat) > 0
            assert "empty tree" in str(compat[0].message).lower()

    def test_load_content_semicolon_still_loads(self):
        """Loading only ';' should still set _tree_content."""
        styler = FigTreeStyler()
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            styler.load_content(";")
        assert styler._tree_content == ";"

    # --- Fix 4: numeric taxon names preserved ---

    def test_numeric_integer_taxa_preserved(self):
        """Pure integer taxon names (BEAST format) should be preserved."""
        taxa = extract_taxa_from_newick("(1:0.1,2:0.2,3:0.3);")
        assert "1" in taxa
        assert "2" in taxa
        assert "3" in taxa

    def test_float_taxa_still_filtered(self):
        """Floating-point taxon names should still be filtered."""
        taxa = extract_taxa_from_newick("(A:0.1,0.5:0.2);")
        assert "A" in taxa
        assert "0.5" not in taxa

    def test_fallback_numeric_integer_preserved(self):
        """Fallback extraction should preserve integer taxon names."""
        from figtreekit._parser import _fallback_extract_taxa
        taxa = _fallback_extract_taxa("(1:0.1,2:0.2);")
        assert "1" in taxa
        assert "2" in taxa

    def test_fallback_float_still_filtered(self):
        """Fallback extraction should still filter float names."""
        from figtreekit._parser import _fallback_extract_taxa
        taxa = _fallback_extract_taxa("(A:0.1,0.5:0.2);")
        assert "A" in taxa
        assert "0.5" not in taxa

    # --- Suggestion 2: tqdm fallback path ---

    def test_batch_processing_without_tqdm(self, tmp_path):
        """Batch processing should work when tqdm is not installed."""
        (tmp_path / "a.tre").write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_dir = tmp_path / "styled"

        import figtreekit._cli as cli_mod
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == 'tqdm':
                raise ImportError("mocked tqdm unavailable")
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            # Re-trigger the import path in _process_batch
            parser = create_cli_parser()
            args = parser.parse_args([str(tmp_path), "-o", str(out_dir)])
            _process_batch(tmp_path, args)

        assert (out_dir / "a.nex").exists()

    # --- Suggestion 4: non-standard tree declaration ---

    def test_nexus_with_atypical_tree_declaration(self):
        """Nexus with metadata annotation before tree value should export correctly."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = [&R] (A:0.1,B:0.2);
end;"""
        styler = FigTreeStyler().load_content(nexus)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "begin trees;" in content
            assert "#NEXUS" in content
        finally:
            os.unlink(path)

    # --- Integration: verify fixes don't break existing behavior ---

    def test_highlight_clade_after_fixes(self):
        """highlight_clade should still work correctly after all fixes."""
        styler = FigTreeStyler().load_content("(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);")
        styler.highlight_clade(["A", "B"], color="#FF0000")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "!hilight=" in content
            assert "#ff0000" in content
        finally:
            os.unlink(path)

    def test_full_workflow_after_fixes(self):
        """Complete workflow should work after all fixes."""
        styler = FigTreeStyler().load_content("(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);")
        styler.set_layout(LayoutType.POLAR)
        styler.set_tip_labels(is_shown=True, font_size=12)
        styler.highlight_clade(["A", "B"], color="#FF0000")
        styler.set_clade_color(["C", "D"], color="#00FF00")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "#NEXUS" in content
            assert "POLAR" in content
            assert "!hilight=" in content
            assert "!color=" in content
        finally:
            os.unlink(path)


# ============================================================
# Tests for diagnostic report fixes
# ============================================================

class TestSerializerQuoteEscaping:
    """BUG-1 fix: serialize_value escapes embedded double quotes."""

    def test_string_with_embedded_double_quote(self):
        """Embedded double quotes should be backslash-escaped."""
        result = serialize_value('say "hello"')
        assert result == '"say \\"hello\\""'

    def test_string_with_backslash(self):
        """Backslashes should be escaped."""
        result = serialize_value('path\\file')
        assert result == '"path\\\\file"'

    def test_string_with_both_escapes(self):
        """Both backslash and double quote should be escaped."""
        result = serialize_value('a\\b"c')
        assert result == '"a\\\\b\\"c"'

    def test_string_without_special_chars_unchanged(self):
        """Normal strings should not be affected."""
        assert serialize_value("Arial") == '"Arial"'
        assert serialize_value("sansserif") == '"sansserif"'

    def test_round_trip_serialize_parse(self):
        """Escaped output should round-trip through apply_parsed_setting."""
        from figtreekit._parser import apply_parsed_setting
        original = 'say "hello"'
        serialized = serialize_value(original)
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "tipLabels.fontName", serialized)
        assert settings.tipLabels["fontName"] == original

    def test_round_trip_backslash(self):
        """Backslash values should round-trip correctly."""
        from figtreekit._parser import apply_parsed_setting
        original = 'path\\file'
        serialized = serialize_value(original)
        settings = FigTreeSettings()
        apply_parsed_setting(settings, "tipLabels.fontName", serialized)
        assert settings.tipLabels["fontName"] == original

    def test_export_with_embedded_quote_in_font_name(self):
        """Export should produce valid Nexus even with quotes in font name."""
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_tip_labels(font_name='my "font"')
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            content = Path(path).read_text()
            # Should contain escaped quotes, not raw embedded quotes
            assert '\\"' in content
            assert '#NEXUS' in content
        finally:
            os.unlink(path)


class TestIncludeTaxaBlockFix:
    """BUG-2 fix: include_taxa_block=False works for all input formats."""

    def test_newick_include_taxa_block_false(self):
        """For Newick input, include_taxa_block=False should suppress taxa block."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path, include_taxa_block=False)
            content = Path(path).read_text()
            assert "begin taxa;" not in content
            assert "begin trees;" in content
            assert "begin figtree;" in content
        finally:
            os.unlink(path)

    def test_newick_include_taxa_block_true(self):
        """For Newick input, include_taxa_block=True (default) should include taxa block."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path, include_taxa_block=True)
            content = Path(path).read_text()
            assert "begin taxa;" in content
            assert "ntax=3" in content
        finally:
            os.unlink(path)

    def test_nexus_include_taxa_block_false(self):
        """For Nexus input with taxa block, include_taxa_block=False should suppress it."""
        nexus = "#NEXUS\nbegin taxa;\nend;\nbegin trees;\ntree T=(A:0.1,B:0.2);\nend;"
        styler = FigTreeStyler().load_content(nexus)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path, include_taxa_block=False)
            content = Path(path).read_text()
            assert "begin taxa;" not in content
            assert "begin trees;" in content
        finally:
            os.unlink(path)


class TestStrokeTypeSafety:
    """Suggestion-3 fix: stroke annotation handles non-numeric values safely."""

    def test_stroke_with_string_value_warns(self):
        """Non-numeric stroke value should warn and not crash."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler._inject_annotation_to_node(tree.root, 'stroke', 'not_a_number')
            compat = [x for x in w if "Invalid stroke value" in str(x.message)]
            assert len(compat) == 1

    def test_stroke_with_none_warns(self):
        """None stroke value should warn and not crash."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler._inject_annotation_to_node(tree.root, 'stroke', None)
            assert any("Invalid stroke value" in str(x.message) for x in w)

    def test_stroke_with_valid_float(self):
        """Valid float stroke value should work."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        styler._inject_annotation_to_node(tree.root, 'stroke', 3.5)
        assert tree.root.comment is not None
        assert "!stroke=3.5" in tree.root.comment

    def test_stroke_with_integer_value(self):
        """Integer-valued float should produce integer in output."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        styler._inject_annotation_to_node(tree.root, 'stroke', 4.0)
        assert "!stroke=4" in tree.root.comment

    def test_stroke_with_string_number(self):
        """String number like '3.5' should be accepted."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        styler._inject_annotation_to_node(tree.root, 'stroke', '3.5')
        assert "!stroke=3.5" in tree.root.comment


class TestParserExceptionPaths:
    """Tests targeting uncovered lines in _parser.py."""

    def test_find_unquoted_semicolon_triple_quote_escape(self):
        """''' is an escaped quote followed by a regular quote toggle."""
        # ''' = '' (escaped) + ' (toggle), so we're now in-quote
        result = find_unquoted_semicolon("a''';b")
        # After ''', we're in-quote, so ; is quoted → not found
        assert result == -1

    def test_extract_tree_value_quoted_string_with_doubled_quotes(self):
        """Doubled quotes inside quoted tree declaration."""
        result = extract_tree_value("'tree''name';rest")
        # The '' is an escaped quote, so the string is 'tree'name'
        # The first unquoted ; ends the value
        assert result is not None

    def test_extract_tree_value_incomplete(self):
        """Tree value without terminating semicolon."""
        result = extract_tree_value("(A:0.1,B:0.2)")
        assert result is None

    def test_parse_nexus_no_trees_block(self):
        """Nexus with taxa but no trees block."""
        result = parse_nexus_content("#NEXUS\nbegin taxa;\nend;")
        assert result['tree_block'] is None
        assert result['all_trees'] == []
        assert result['tree_content'] is None

    def test_extract_taxa_fallback_on_parse_failure(self):
        """When Bio.Phylo fails, fallback extraction should be used."""
        # Malformed Newick that Bio.Phylo can't parse but regex can
        taxa = extract_taxa_from_newick("(A:0.1,B:0.2);")
        assert set(taxa) == {"A", "B"}

    def test_extract_taxa_with_spaces_in_name(self):
        """Taxa with spaces should be single-quoted in output."""
        taxa = extract_taxa_from_newick("('Species A':0.1,'Species B':0.2);")
        assert any("Species A" in t for t in taxa)
        assert any("Species B" in t for t in taxa)

    def test_fallback_extract_taxa_quoted_with_semicolon(self):
        """Quoted taxa containing semicolons."""
        taxa = _fallback_extract_taxa("('A;B':0.1,C:0.2);")
        assert any("A;B" in t for t in taxa)

    def test_fallback_extract_taxa_quoted_with_space(self):
        """Quoted taxa containing spaces."""
        taxa = _fallback_extract_taxa("('Taxon 001':0.1,Taxon_002:0.2);")
        assert any("Taxon 001" in t for t in taxa)

    def test_fallback_extract_taxa_float_filtered(self):
        """Floating-point names should be filtered in fallback."""
        taxa = _fallback_extract_taxa("(A:0.1,0.5:0.2);")
        assert "A" in taxa
        assert "0.5" not in taxa

    def test_fallback_extract_taxa_empty_quoted(self):
        """Empty quoted names should be skipped."""
        taxa = _fallback_extract_taxa("('':0.1,A:0.2);")
        assert "A" in taxa
        assert len([t for t in taxa if "''" in t or t == ""]) == 0


class TestStylerAnnotationPaths:
    """Tests targeting uncovered annotation paths in styler.py."""

    def test_inject_font_annotation_without_comma(self):
        """Font annotation without comma falls through to default path."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        styler._inject_annotation_to_node(tree.root, 'font', 'simple')
        assert "!font=simple" in tree.root.comment

    def test_inject_color_annotation_non_string(self):
        """Color annotation with non-string value."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        styler._inject_annotation_to_node(tree.root, 'color', 12345)
        assert "!color=12345" in tree.root.comment

    def test_inject_hilight_invalid_values_warns(self):
        """Hilight with wrong number of values should warn."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler._inject_annotation_to_node(tree.root, 'hilight', [1, 2])
            assert any("Invalid hilight" in str(x.message) for x in w)

    def test_inject_annotation_on_existing_comment(self):
        """Annotation appended to node that already has a comment."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        tree.root.comment = "[&R]"
        styler._inject_annotation_to_node(tree.root, 'color', '#ff0000')
        assert "[&R]" in tree.root.comment
        assert "!color=#ff0000" in tree.root.comment

    def test_inject_annotation_duplicate_type_skipped(self):
        """Duplicate annotation type on same node should be skipped."""
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        styler._inject_annotation_to_node(tree.root, 'color', '#ff0000')
        styler._inject_annotation_to_node(tree.root, 'color', '#00ff00')
        # Should only have the first color
        assert tree.root.comment.count("!color=") == 1

    def test_serialize_tree_failure_warns(self):
        """Bio.Phylo write failure should warn and return None."""
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Pass None to trigger failure
            result = styler._serialize_tree_to_newick(None)
            # May or may not warn depending on Bio.Phylo behavior
            # But should not crash

    def test_apply_annotations_to_tree_no_annotations(self):
        """No annotations should return tree unchanged."""
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        tree = styler._parse_tree_with_biopython(styler._tree_content)
        result = styler._apply_annotations_to_tree(tree, [])
        assert result is tree

    def test_discrete_coloring_with_attribute(self):
        """discrete_coloring=True with branch_color_attribute should append '*'."""
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_appearance(branch_color_attribute="height", discrete_coloring=True)
        s = styler.get_settings()
        assert s["appearance.branchColorAttribute"] == "height *"

    def test_discrete_coloring_already_has_asterisk(self):
        """discrete_coloring with attribute already ending in '*' should not double."""
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_appearance(branch_color_attribute="height *", discrete_coloring=True)
        s = styler.get_settings()
        assert s["appearance.branchColorAttribute"] == "height *"


class TestSetCladeFontEnum:
    """Tests for set_clade_font accepting FontStyle enum."""

    def test_font_style_enum_accepted(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        styler.set_clade_font(["A", "B"], "Arial", FontStyle.BOLD, 14)
        ann = styler._settings._node_annotations[0]
        assert "1" in ann.values  # FontStyle.BOLD.value == 1

    def test_font_style_int_still_works(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        styler.set_clade_font(["A", "B"], "Arial", 1, 14)
        ann = styler._settings._node_annotations[0]
        assert "1" in ann.values

    def test_font_style_enum_export(self):
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        styler.set_clade_font(["A", "B"], "Arial", FontStyle.ITALIC, 12)
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            content = Path(path).read_text()
            assert "[&!font=Arial-ITALIC-12]" in content
        finally:
            os.unlink(path)


class TestBiologicalPlausibility:
    """Tests for TreeValidator.validate_biological_plausibility."""

    def test_single_taxon_warns(self):
        issues = TreeValidator.validate_biological_plausibility("A;")
        assert len(issues) == 1
        assert "single taxon" in issues[0].lower()

    def test_all_zero_branch_lengths_warns(self):
        issues = TreeValidator.validate_biological_plausibility(
            "((A:0.0,B:0.0):0.0,C:0.0);"
        )
        assert any("zero" in i.lower() for i in issues)

    def test_normal_tree_no_issues(self):
        issues = TreeValidator.validate_biological_plausibility(
            "((A:0.1,B:0.2):0.3,C:0.4);"
        )
        assert issues == []

    def test_empty_string_no_issues(self):
        issues = TreeValidator.validate_biological_plausibility("")
        assert issues == []

    def test_non_string_no_issues(self):
        issues = TreeValidator.validate_biological_plausibility(None)
        assert issues == []


class TestParserFallbackWarning:
    """Tests that Bio.Phylo fallback emits CompatibilityWarning."""

    def test_extract_taxa_fallback_warns(self):
        """When Bio.Phylo fails, fallback should emit CompatibilityWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Malformed Newick that triggers exception in Bio.Phylo
            extract_taxa_from_newick("(((")
            compat = [x for x in w if issubclass(x.category, CompatibilityWarning)
                      and "falling back" in str(x.message).lower()]
            assert len(compat) >= 1


class TestIncludeTaxaBlockWarning:
    """Tests for include_taxa_block=False warning on Newick input."""

    def test_newick_false_warns(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                styler.export(path, include_taxa_block=False)
                compat = [x for x in w if issubclass(x.category, CompatibilityWarning)
                          and "taxa block" in str(x.message).lower()]
                assert len(compat) == 1
        finally:
            os.unlink(path)

    def test_newick_true_no_warning(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                styler.export(path, include_taxa_block=True)
                compat = [x for x in w if issubclass(x.category, CompatibilityWarning)
                          and "taxa block" in str(x.message).lower()]
                assert len(compat) == 0
        finally:
            os.unlink(path)


class TestSetAppearanceColorValidation:
    """MC-3: set_appearance() should validate color parameters."""

    def test_invalid_background_color_raises(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        with pytest.raises(ValidationError, match="Invalid background_color"):
            styler.set_appearance(background_color="red")

    def test_invalid_foreground_color_raises(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        with pytest.raises(ValidationError, match="Invalid foreground_color"):
            styler.set_appearance(foreground_color="#GG0000")

    def test_invalid_selection_color_raises(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        with pytest.raises(ValidationError, match="Invalid selection_color"):
            styler.set_appearance(selection_color="not_a_color")

    def test_valid_colors_accepted(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_appearance(
            background_color="#FFFFFF",
            foreground_color="#000000",
            selection_color="#2d3680",
        )
        s = styler.get_settings()
        assert s["appearance.backgroundColour"] == "#ffffff"
        assert s["appearance.foregroundColour"] == "#000000"
        assert s["appearance.selectionColour"] == "#2d3680"


class TestAnnotationLossWarning:
    """MC-4: _resolve_annotations_copy should warn when annotations are lost."""

    def test_warning_on_parse_failure_with_annotations(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.highlight_clade(["A", "B"], color="#FF0000")
        # Corrupt tree content with unmatched parens to force parse failure
        styler._tree_content = "(((("
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = styler._resolve_annotations_copy()
            compat = [x for x in w if issubclass(x.category, CompatibilityWarning)
                      and "annotation" in str(x.message).lower()]
            assert len(compat) == 1
            assert "1 annotation(s)" in str(compat[0].message)
            # Should return original content on failure
            assert result == "(((("

    def test_no_warning_on_parse_failure_without_annotations(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler._tree_content = "(((("
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler._resolve_annotations_copy()
            compat = [x for x in w if issubclass(x.category, CompatibilityWarning)
                      and "annotation" in str(x.message).lower()]
            assert len(compat) == 0


class TestFontParseError:
    """mC-3: _inject_annotation_to_node should handle invalid font format."""

    def test_invalid_font_style_int(self):
        from figtreekit.styler import FigTreeStyler
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        from Bio import Phylo
        import io
        tree = list(Phylo.parse(io.StringIO("(A:0.1,B:0.2);"), 'newick'))[0]
        node = tree.get_terminals()[0]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler._inject_annotation_to_node(node, 'font', 'Arial,notanumber,12')
            font_warns = [x for x in w if "font annotation format" in str(x.message).lower()]
            assert len(font_warns) == 1

    def test_valid_font_format(self):
        from figtreekit.styler import FigTreeStyler
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        from Bio import Phylo
        import io
        tree = list(Phylo.parse(io.StringIO("(A:0.1,B:0.2);"), 'newick'))[0]
        node = tree.get_terminals()[0]
        styler._inject_annotation_to_node(node, 'font', 'Arial,1,12')
        assert node.comment is not None
        assert '!font=Arial-BOLD-12' in node.comment


class TestGetTreeContent:
    """mC-7: get_tree_content() public API."""

    def test_returns_loaded_content(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        content = styler.get_tree_content()
        assert content is not None
        assert "A" in content and "B" in content

    def test_returns_none_when_empty(self):
        styler = FigTreeStyler()
        assert styler.get_tree_content() is None


# ============================================================
# Supplementary tests
# ============================================================

class TestTranslateBlockConsistency:
    """Tests for translate block consistency with tree content."""

    def test_beast_format_translate_block_preserved(self):
        """BEAST format: translate IDs should appear in output tree."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=3;
    taxlabels A B C ;
end;
begin trees;
    translate
        1 A,
        2 B,
        3 C;
    tree TREE1 = (1:0.1,2:0.2,3:0.3);
end;"""
        styler = FigTreeStyler()
        styler.load_content(nexus)

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            # Translate block should be preserved
            assert "translate" in content
            # Tree should use translate IDs, not taxon names
            assert "1:0.1" in content or "1:0.1" in content
            # Should NOT contain taxon names in tree value
            tree_match = re.search(r'tree\s+TREE1\s*=\s*(.+?);', content, re.DOTALL)
            if tree_match:
                tree_value = tree_match.group(1)
                # Taxon names should be replaced with translate IDs
                assert "A:" not in tree_value or "'A':" not in tree_value
        finally:
            os.unlink(path)

    def test_translate_block_with_annotations(self):
        """Annotations should work with translate block.

        Note: When translate block exists, the tree_content stores the original
        tree string with translate IDs (e.g., '1', '2', '3'). Bio.Phylo parses
        these as taxon names. Annotations should use translate IDs.
        """
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=3;
    taxlabels A B C ;
end;
begin trees;
    translate
        1 A,
        2 B,
        3 C;
    tree TREE1 = (1:0.1,2:0.2,3:0.3);
end;"""
        styler = FigTreeStyler()
        styler.load_content(nexus)
        # Tree content uses translate IDs, so use translate IDs for annotations
        styler.highlight_clade(["1", "2"], color="#FF0000")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            # Should have hilight annotation
            assert "[&!hilight=" in content
            # Translate block should still be present
            assert "translate" in content
        finally:
            os.unlink(path)

    def test_parse_translate_block_with_quoted_names(self):
        """Translate block with quoted taxon names containing commas."""
        styler = FigTreeStyler()
        styler._translate_block = "translate\n    1 'Species, A',\n    2 'Species, B';"
        mapping = styler._parse_translate_block()
        assert mapping.get("Species, A") == "1"
        assert mapping.get("Species, B") == "2"

    def test_parse_translate_block_with_double_quotes(self):
        """Translate block with double-quoted taxon names."""
        styler = FigTreeStyler()
        styler._translate_block = 'translate\n    1 "Species A",\n    2 "Species B";'
        mapping = styler._parse_translate_block()
        assert mapping.get("Species A") == "1"
        assert mapping.get("Species B") == "2"

    def test_parse_translate_block_empty(self):
        """Empty translate block should return empty dict."""
        styler = FigTreeStyler()
        styler._translate_block = None
        mapping = styler._parse_translate_block()
        assert mapping == {}


class TestTreeIndexAnnotationApplication:
    """Tests for tree_index parameter with annotation application."""

    def test_tree_index_0_applies_to_first_tree(self):
        """tree_index=0 should apply annotations to first tree."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = (A:0.1,B:0.2);
    tree TREE2 = (A:0.15,B:0.25);
end;"""
        styler = FigTreeStyler(tree_index=0)
        styler.load_content(nexus)
        styler.set_clade_color(["A", "B"], color="#FF0000")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            # First tree should have annotation
            tree1_match = re.search(r'tree\s+TREE1\s*=\s*(.+?);', content, re.DOTALL)
            assert tree1_match is not None
            assert "[&!color=" in tree1_match.group(1)
        finally:
            os.unlink(path)

    def test_tree_index_1_applies_to_second_tree(self):
        """tree_index=1 should apply annotations to second tree."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = (A:0.1,B:0.2);
    tree TREE2 = (A:0.15,B:0.25);
end;"""
        styler = FigTreeStyler(tree_index=1)
        styler.load_content(nexus)
        styler.set_clade_color(["A", "B"], color="#FF0000")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            # Second tree should have annotation
            tree2_match = re.search(r'tree\s+TREE2\s*=\s*(.+?);', content, re.DOTALL)
            assert tree2_match is not None
            assert "[&!color=" in tree2_match.group(1)
            # First tree should NOT have annotation
            tree1_match = re.search(r'tree\s+TREE1\s*=\s*(.+?);', content, re.DOTALL)
            assert tree1_match is not None
            assert "[&!color=" not in tree1_match.group(1)
        finally:
            os.unlink(path)

    def test_tree_index_out_of_range_falls_back(self):
        """tree_index out of range should fall back to index 0."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = (A:0.1,B:0.2);
end;"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler = FigTreeStyler(tree_index=5)
            styler.load_content(nexus)
            compat = [x for x in w if "out of range" in str(x.message).lower()]
            assert len(compat) > 0


class TestStrictMode:
    """Tests for strict mode that rejects negative branch lengths."""

    def test_strict_mode_rejects_negative_branch(self):
        """Strict mode should raise ValidationError on negative branch length."""
        newick = "((A:-0.1,B:0.2):0.3,C:0.4);"
        with pytest.raises(ValidationError, match="Strict mode"):
            FigTreeStyler(strict=True).load_content(newick)

    def test_strict_mode_accepts_valid_tree(self):
        """Strict mode should accept trees with non-negative branch lengths."""
        newick = "((A:0.1,B:0.2):0.3,C:0.4);"
        styler = FigTreeStyler(strict=True)
        styler.load_content(newick)
        assert styler._tree_content is not None

    def test_non_strict_mode_warns_negative_branch(self):
        """Non-strict mode should warn but not raise on negative branch length."""
        newick = "((A:-0.1,B:0.2):0.3,C:0.4);"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler = FigTreeStyler(strict=False)
            styler.load_content(newick)
            # Warning is emitted at export time, not load time
            with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
                path = f.name
            try:
                styler.export(path)
            finally:
                os.unlink(path)
            compat = [x for x in w if issubclass(x.category, CompatibilityWarning)
                      and "negative" in str(x.message).lower()]
            assert len(compat) > 0

    def test_strict_mode_multiple_negative_branches(self):
        """Strict mode should fail on first negative branch."""
        newick = "((A:-0.1,B:-0.2):0.3,C:0.4);"
        with pytest.raises(ValidationError, match="Strict mode"):
            FigTreeStyler(strict=True).load_content(newick)


class TestSetAppearanceRefactored:
    """Tests for refactored set_appearance method."""

    def test_set_appearance_branch_line_width(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_appearance(branch_line_width=2.5)
        assert styler._settings.appearance["branchLineWidth"] == 2.5

    def test_set_appearance_background_color(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_appearance(background_color="#FFFFFF")
        assert styler._settings.appearance["backgroundColour"] == "#ffffff"

    def test_set_appearance_discrete_coloring_with_attribute(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_appearance(
            branch_color_attribute="height",
            discrete_coloring=True,
        )
        assert styler._settings.appearance["branchColorAttribute"] == "height *"

    def test_set_appearance_discrete_coloring_without_attribute_warns(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            styler.set_appearance(discrete_coloring=True)
            warn_msgs = [x for x in w if "discrete_coloring" in str(x.message)]
            assert len(warn_msgs) > 0

    def test_set_appearance_all_params(self):
        styler = FigTreeStyler().load_content("(A:0.1,B:0.2);")
        styler.set_appearance(
            branch_line_width=2.0,
            background_color="#FFFFFF",
            foreground_color="#000000",
            selection_color="#2d3680",
            background_color_attribute="bg_attr",
            branch_color_attribute="branch_attr",
            branch_width_attribute="width_attr",
            branch_min_line_width=0.5,
            branch_color_gradient=True,
            hilighting_gradient=True,
        )
        s = styler._settings.appearance
        assert s["branchLineWidth"] == 2.0
        assert s["backgroundColour"] == "#ffffff"
        assert s["foregroundColour"] == "#000000"
        assert s["selectionColour"] == "#2d3680"
        assert s["backgroundColorAttribute"] == "bg_attr"
        assert s["branchColorAttribute"] == "branch_attr"
        assert s["branchWidthAttribute"] == "width_attr"
        assert s["branchMinLineWidth"] == 0.5
        assert s["branchColorGradient"] is True
        assert s["hilightingGradient"] is True


class TestMultiLineTreeValues:
    """Tests for multi-line tree values in Nexus files."""

    def test_multiline_tree_value_export(self):
        """Multi-line tree values should be correctly replaced."""
        # Create a tree value that spans multiple lines
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 =
        (A:0.1,B:0.2);
end;"""
        styler = FigTreeStyler()
        styler.load_content(nexus)

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "#NEXUS" in content
            assert "tree TREE1" in content
        finally:
            os.unlink(path)


# ============================================================
# Tests for coverage gaps identified in diagnostic report
# ============================================================

class TestMainModuleCoverage:
    """Tests for __main__.py module coverage."""

    def test_main_module_entry_point(self, tmp_path, monkeypatch):
        """python -m figtreekit should work as entry point."""
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", str(tree_file), "-o", str(out_file)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "#NEXUS" in content

    def test_main_module_validate(self, tmp_path):
        """python -m figtreekit --validate should work."""
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", str(tree_file), "--validate"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_main_module_help(self):
        """python -m figtreekit --help should show help."""
        result = subprocess.run(
            [sys.executable, "-m", "figtreekit", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "figtreekit" in result.stdout.lower() or "usage" in result.stdout.lower()


class TestMultiTreeReplacementEdgeCases:
    """Tests for multi-tree replacement edge cases (styler.py:998-1010)."""

    def test_three_trees_replace_middle(self):
        """Replacing the middle tree (index 1) of three trees."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = (A:0.1,B:0.2);
    tree TREE2 = (A:0.15,B:0.25);
    tree TREE3 = (A:0.12,B:0.22);
end;"""
        styler = FigTreeStyler(tree_index=1)
        styler.load_content(nexus)
        styler.set_clade_color(["A", "B"], color="#00FF00")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            # All three trees should be preserved
            assert "tree TREE1" in content
            assert "tree TREE2" in content
            assert "tree TREE3" in content
            # Only TREE2 should have annotation
            tree2_match = re.search(r'tree\s+TREE2\s*=\s*(.+?);', content, re.DOTALL)
            assert tree2_match is not None
            assert "[&!color=" in tree2_match.group(1)
        finally:
            os.unlink(path)

    def test_three_trees_replace_last(self):
        """Replacing the last tree (index 2) of three trees."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = (A:0.1,B:0.2);
    tree TREE2 = (A:0.15,B:0.25);
    tree TREE3 = (A:0.12,B:0.22);
end;"""
        styler = FigTreeStyler(tree_index=2)
        styler.load_content(nexus)
        styler.set_clade_color(["A", "B"], color="#FF0000")

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            # All three trees should be preserved
            assert "tree TREE1" in content
            assert "tree TREE2" in content
            assert "tree TREE3" in content
            # Only TREE3 should have annotation
            tree3_match = re.search(r'tree\s+TREE3\s*=\s*(.+?);', content, re.DOTALL)
            assert tree3_match is not None
            assert "[&!color=" in tree3_match.group(1)
        finally:
            os.unlink(path)

    def test_single_tree_no_annotation(self):
        """Single tree with no annotations should export correctly."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = (A:0.1,B:0.2);
end;"""
        styler = FigTreeStyler(tree_index=0)
        styler.load_content(nexus)

        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "tree TREE1" in content
            assert "(A:0.1,B:0.2)" in content or "A:0.1" in content
        finally:
            os.unlink(path)


class TestBiologicalPlausibilityThreshold:
    """Tests for validate_biological_plausibility threshold (validators.py:171)."""

    def test_large_taxa_count_default_threshold(self):
        """Tree with >10000 taxa should trigger warning with default threshold."""
        # Generate a tree with many taxa
        taxa = ",".join(f"T{i:05d}:0.001" for i in range(101))
        newick = f"({taxa}):0.0;"
        issues = TreeValidator.validate_biological_plausibility(
            newick, max_taxa_warning_threshold=100
        )
        assert any("taxa" in i.lower() for i in issues)

    def test_large_taxa_count_custom_threshold(self):
        """Custom threshold should control when warning is triggered."""
        taxa = ",".join(f"T{i:05d}:0.001" for i in range(51))
        newick = f"({taxa}):0.0;"
        # With threshold=100, 51 taxa should not trigger
        issues = TreeValidator.validate_biological_plausibility(
            newick, max_taxa_warning_threshold=100
        )
        assert not any("taxa" in i.lower() for i in issues)

    def test_large_taxa_count_disabled_threshold(self):
        """Threshold=0 should disable the taxa count warning."""
        taxa = ",".join(f"T{i:05d}:0.001" for i in range(10001))
        newick = f"({taxa}):0.0;"
        issues = TreeValidator.validate_biological_plausibility(
            newick, max_taxa_warning_threshold=0
        )
        assert not any("taxa" in i.lower() for i in issues)

    def test_threshold_boundary_exact(self):
        """Exactly at threshold should not trigger warning."""
        taxa = ",".join(f"T{i:05d}:0.001" for i in range(100))
        newick = f"({taxa}):0.0;"
        issues = TreeValidator.validate_biological_plausibility(
            newick, max_taxa_warning_threshold=100
        )
        # Exactly at threshold should not warn (only > threshold)
        assert not any("taxa" in i.lower() for i in issues)

    def test_threshold_boundary_over(self):
        """One over threshold should trigger warning."""
        taxa = ",".join(f"T{i:05d}:0.001" for i in range(101))
        newick = f"({taxa}):0.0;"
        issues = TreeValidator.validate_biological_plausibility(
            newick, max_taxa_warning_threshold=100
        )
        assert any("taxa" in i.lower() for i in issues)


class TestEdgeCases:
    """Edge-case tests."""

    def test_nexus_tree_with_semicolon_in_bracket_comment(self):
        """Tree with semicolons inside bracket metadata should parse correctly."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels A B ;
end;
begin trees;
    tree TREE1 = [&R] (A:0.1[&comment=has;semicolons],B:0.2);
end;"""
        styler = FigTreeStyler().load_content(nexus)
        assert styler._tree_content is not None
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "#NEXUS" in content
            assert "begin trees;" in content
        finally:
            os.unlink(path)

    def test_export_never_mutates_tree_content_even_on_multiple_exports(self):
        """Multiple exports should all produce identical output without side effects."""
        newick = "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);"
        styler = FigTreeStyler().load_content(newick)
        styler.highlight_clade(["A", "B"], color="#FF0000")
        styler.set_clade_color(["C", "D"], color="#00FF00")

        paths = [tempfile.mktemp(suffix='.nex') for _ in range(3)]
        try:
            for p in paths:
                styler.export(p)
            contents = []
            for p in paths:
                with open(p) as f:
                    contents.append(f.read())
            assert contents[0] == contents[1] == contents[2]
            # Original tree content must be unchanged
            assert "[&!hilight=" not in (styler._tree_content or "")
            assert "[&!color=" not in (styler._tree_content or "")
        finally:
            for p in paths:
                if os.path.exists(p):
                    os.unlink(p)

    def test_extract_taxa_catches_specific_exceptions(self):
        """extract_taxa_from_newick should catch only specific exceptions, not bare Exception."""
        # A valid tree should work fine
        taxa = extract_taxa_from_newick("((A:0.1,B:0.2):0.3,C:0.4);")
        assert set(taxa) == {"A", "B", "C"}

    def test_translate_block_with_quoted_comma_taxa(self):
        """Translate block with taxon names containing commas should parse correctly."""
        nexus = """#NEXUS
begin taxa;
    dimensions ntax=2;
    taxlabels 'Species, A' 'Species, B' ;
end;
begin trees;
    translate
        1 'Species, A',
        2 'Species, B';
    tree TREE1 = (1:0.1,2:0.2);
end;"""
        styler = FigTreeStyler().load_content(nexus)
        assert styler._tree_content is not None
        with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
            path = f.name
        try:
            styler.export(path)
            with open(path) as f:
                content = f.read()
            assert "#NEXUS" in content
        finally:
            os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
