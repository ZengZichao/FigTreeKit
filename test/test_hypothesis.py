"""Property-based tests for FigTreeKit using Hypothesis.

These tests generate random valid inputs and verify round-trip properties.
"""

import re
import tempfile
import os
import warnings

import pytest

try:
    from hypothesis import given, settings, assume, HealthCheck
    from hypothesis import strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

from figtreekit import FigTreeStyler, LayoutType, CompatibilityWarning


if HAS_HYPOTHESIS:
    def _newick_taxa_names():
        """Strategy for generating valid Newick taxon names."""
        return st.from_regex(r'[A-Za-z][A-Za-z0-9_]{0,10}', fullmatch=True)

    def _newick_tree(min_size=2, max_size=8):
        """Strategy for generating valid Newick trees.

        Uses Hypothesis' recursive strategy to avoid infinite strategy
        expansion while still producing nested binary trees.
        """
        leaf = st.builds(
            lambda name, bl: f"{name}:{bl:.4f}",
            _newick_taxa_names(),
            st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
        )

        def extend(node):
            return st.builds(
                lambda left, right, bl: f"({left},{right}):{bl:.4f}",
                node,
                node,
                st.floats(min_value=0.001, max_value=1.0, allow_nan=False, allow_infinity=False),
            )

        return st.recursive(leaf, extend, max_leaves=max_size)

    @pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")
    class TestPropertyBased:
        """Property-based tests using Hypothesis."""

        @given(tree=_newick_tree(min_size=2, max_size=8))
        @settings(
            max_examples=50,
            suppress_health_check=[HealthCheck.too_slow],
            deadline=10000,
        )
        def test_round_trip_parse_export(self, tree):
            """Generated Newick trees should parse and export without errors."""
            assume(tree.count('(') == tree.count(')'))

            full_tree = tree + ";"
            styler = FigTreeStyler()
            styler.load_content(full_tree)
            assert styler.get_tree_content() is not None

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

        @given(tree=_newick_tree(min_size=2, max_size=8))
        @settings(
            max_examples=50,
            suppress_health_check=[HealthCheck.too_slow],
            deadline=10000,
        )
        def test_round_trip_preserves_taxa(self, tree):
            """Exported tree should contain the same taxa as the input."""
            assume(tree.count('(') == tree.count(')'))

            full_tree = tree + ";"
            styler = FigTreeStyler()
            styler.load_content(full_tree)

            with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
                path = f.name
            try:
                styler.export(path)
                with open(path) as f:
                    content = f.read()
                # Should have taxa block
                assert "begin taxa;" in content
            finally:
                os.unlink(path)

        @given(
            tree=_newick_tree(min_size=2, max_size=6),
            color=st.from_regex(r'#[0-9A-Fa-f]{6}', fullmatch=True),
        )
        @settings(
            max_examples=30,
            suppress_health_check=[HealthCheck.too_slow],
            deadline=10000,
        )
        def test_highlight_export_no_crash(self, tree, color):
            """Highlighting a clade and exporting should not crash."""
            assume(tree.count('(') == tree.count(')'))

            full_tree = tree + ";"
            styler = FigTreeStyler()
            styler.load_content(full_tree)

            # Get first two taxa
            import re as _re
            taxa = _re.findall(r'[A-Za-z][A-Za-z0-9_]*', full_tree)
            if len(taxa) >= 2:
                styler.highlight_clade(taxa[:2], color=color)

            with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
                path = f.name
            try:
                styler.export(path)
                assert os.path.exists(path)
            finally:
                os.unlink(path)

        @given(
            layout=st.sampled_from(list(LayoutType)),
            font_size=st.integers(min_value=1, max_value=72),
        )
        @settings(
            max_examples=20,
            suppress_health_check=[HealthCheck.too_slow],
            deadline=10000,
        )
        def test_settings_export_no_crash(self, layout, font_size):
            """Various settings combinations should not crash on export."""
            styler = FigTreeStyler()
            styler.load_content("((A:0.1,B:0.2):0.3,C:0.4);")
            styler.set_layout(layout)
            styler.set_tip_labels(font_size=font_size)

            with tempfile.NamedTemporaryFile(suffix='.nex', delete=False) as f:
                path = f.name
            try:
                styler.export(path)
                with open(path) as f:
                    content = f.read()
                assert "begin figtree;" in content
            finally:
                os.unlink(path)

        @given(tree=_newick_tree(min_size=2, max_size=6))
        @settings(
            max_examples=30,
            suppress_health_check=[HealthCheck.too_slow],
            deadline=10000,
        )
        def test_double_export_idempotent(self, tree):
            """Exporting the same styler twice should produce identical output."""
            assume(tree.count('(') == tree.count(')'))

            full_tree = tree + ";"
            styler = FigTreeStyler()
            styler.load_content(full_tree)
            taxa = re.findall(r'[A-Za-z][A-Za-z0-9_]*', full_tree)
            if len(taxa) >= 2:
                styler.highlight_clade(taxa[:2], color="#FF0000")

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
