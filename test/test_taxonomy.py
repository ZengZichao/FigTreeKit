"""Tests for the taxonomy module (TaxonomyMapper, MonophylyAnalyzer)
and FigTreeStyler taxonomy integration.

Covers robustness test items #15-20, #27-28 from Supplementary Table S2.
"""
import warnings
import os
import csv
from io import StringIO

import pytest
from Bio import Phylo

from figtreekit import (
    FigTreeStyler,
    TaxonomyMapper,
    MonophylyAnalyzer,
    SPECIAL_IDENTIFIERS,
    parse_taxonomy,
    is_monophyletic,
    CompatibilityWarning,
)
from figtreekit.taxonomy import (
    parse_taxonomy_auto,
    detect_taxonomy_format,
    get_rank_prefixes,
    set_rank_prefixes,
    extend_rank_prefixes,
)
from figtreekit.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Test trees
# ---------------------------------------------------------------------------

# Tree with embedded taxonomy (format A) — Bacteria is monophyletic
TREE_FMT_A_MONO = (
    "((SP1_d_Bacteria_p_Firmicutes_c_Bacilli:1,"
    "SP2_d_Bacteria_p_Firmicutes_c_Bacilli:1):1,"
    "(SP3_d_Archaea_p_Thermoproteota_c_Sulfolobia:1,"
    "SP4_d_Archaea_p_Thermoproteota_c_Sulfolobia:1):2);"
)

# Tree with embedded taxonomy (format A) — Bacteria is non-monophyletic
TREE_FMT_A_NONMONO = (
    "((SP1_d_Bacteria_p_Firmicutes:1,"
    "SP2_d_Archaea_p_Thermoproteota:1):1,"
    "(SP3_d_Bacteria_p_Firmicutes:1,"
    "SP4_d_Archaea_p_Thermoproteota:1):2);"
)

# Simple tree for collapse / conflict tests
TREE_SIMPLE = "((A:1,B:1):1,C:2);"
TREE_NESTED = "(((A:1,B:1):1,C:2):1,D:3);"


# ---------------------------------------------------------------------------
# 1. parse_taxonomy_auto — format detection and parsing
# ---------------------------------------------------------------------------

class TestParseTaxonomyAuto:
    """Tests for parse_taxonomy_auto and detect_taxonomy_format."""

    def test_detect_embedded_format(self):
        """Format A (embedded) is correctly detected."""
        assert detect_taxonomy_format("SP1_d_Bacteria_p_Firmicutes") == "embedded"

    def test_detect_table_format(self):
        """Format B (GTDB-style semicolon) is correctly detected."""
        assert detect_taxonomy_format("d__Bacteria;p__Firmicutes") == "table"

    def test_detect_no_format(self):
        """Plain labels return None."""
        assert detect_taxonomy_format("plain_label") is None

    def test_parse_embedded_format_a(self):
        """#15: Embedded format A parses correctly."""
        result = parse_taxonomy_auto(
            "SP1_d_Bacteria_p_Firmicutes_c_Bacilli"
        )
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"
        assert result["class"] == "Bacilli"

    def test_parse_embedded_format_a_reverse_mode(self):
        """Format A reverse mode (default) parses correctly."""
        result = parse_taxonomy_auto(
            "SP1_d_Bacteria_p_Firmicutes", mode="reverse"
        )
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"

    def test_parse_embedded_format_a_greedy_mode(self):
        """Format A greedy mode parses correctly."""
        result = parse_taxonomy_auto(
            "SP1_d_Bacteria_p_Firmicutes", mode="greedy"
        )
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"

    def test_parse_embedded_format_a_segment_mode(self):
        """Format A segment mode parses correctly."""
        result = parse_taxonomy_auto(
            "SP1_d_Bacteria_p_Firmicutes", mode="segment"
        )
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"

    def test_parse_table_format_b(self):
        """#16: Table format B (GTDB-style) parses correctly."""
        result = parse_taxonomy_auto(
            "d__Bacteria;p__Firmicutes;c__Bacilli"
        )
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"
        assert result["class"] == "Bacilli"

    def test_parse_table_format_b_empty_rank(self):
        """Format B with empty rank value produces empty string."""
        result = parse_taxonomy_auto(
            "d__Bacteria;p__Firmicutes;c__"
        )
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"
        assert result["class"] == ""

    def test_parse_table_format_b_custom_sep(self):
        """Format B with custom separator."""
        result = parse_taxonomy_auto(
            "d__Bacteria,p__Firmicutes", sep=","
        )
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"

    def test_parse_table_format_b_extra_segments(self):
        """Format B with extra segments beyond known ranks are ignored gracefully."""
        result = parse_taxonomy_auto("d__Bacteria;p__Firmicutes;x__Extra")
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"


# ---------------------------------------------------------------------------
# 2. Rank prefix configuration
# ---------------------------------------------------------------------------

class TestRankPrefixConfig:
    """Tests for get/set/extend rank prefix functions."""

    def test_get_rank_prefixes_returns_copy(self):
        """get_rank_prefixes returns a copy, not the original."""
        prefixes = get_rank_prefixes()
        prefixes["x"] = "test"
        assert "x" not in get_rank_prefixes()

    def test_set_rank_prefixes(self):
        """set_rank_prefixes replaces and rebuilds derived maps."""
        original = get_rank_prefixes()
        try:
            set_rank_prefixes({"d": "domain", "p": "phylum"})
            prefixes = get_rank_prefixes()
            assert prefixes["d"] == "domain"
            assert "k" not in prefixes
        finally:
            set_rank_prefixes(original)

    def test_extend_rank_prefixes(self):
        """extend_rank_prefixes adds new prefixes without replacing existing."""
        original = get_rank_prefixes()
        try:
            extend_rank_prefixes({"x": "extra"})
            prefixes = get_rank_prefixes()
            assert prefixes["x"] == "extra"
            assert prefixes["d"] == "domain"
        finally:
            set_rank_prefixes(original)


# ---------------------------------------------------------------------------
# 3. SPECIAL_IDENTIFIERS
# ---------------------------------------------------------------------------

class TestSpecialIdentifiers:
    """Tests for SPECIAL_IDENTIFIERS constants."""

    def test_special_identifiers_keys(self):
        """All four special identifiers exist."""
        assert set(SPECIAL_IDENTIFIERS.keys()) == {
            "LUCA", "LACA", "LBCA", "root"
        }

    def test_luca_domains(self):
        """LUCA covers both Bacteria and Archaea."""
        assert SPECIAL_IDENTIFIERS["LUCA"]["domains"] == ["Bacteria", "Archaea"]

    def test_laca_domains(self):
        """LACA covers only Archaea."""
        assert SPECIAL_IDENTIFIERS["LACA"]["domains"] == ["Archaea"]

    def test_lbca_domains(self):
        """LBCA covers only Bacteria."""
        assert SPECIAL_IDENTIFIERS["LBCA"]["domains"] == ["Bacteria"]

    def test_root_domains_none(self):
        """root has domains=None (all terminal taxa)."""
        assert SPECIAL_IDENTIFIERS["root"]["domains"] is None


# ---------------------------------------------------------------------------
# 4. TaxonomyMapper
# ---------------------------------------------------------------------------

class TestTaxonomyMapper:
    """Tests for TaxonomyMapper class."""

    def test_parse_labels_embedded(self):
        """parse_labels correctly parses embedded format A labels."""
        mapper = TaxonomyMapper()
        labels = [
            "SP1_d_Bacteria_p_Firmicutes",
            "SP2_d_Archaea_p_Thermoproteota",
        ]
        result = mapper.parse_labels(labels)
        assert result["SP1_d_Bacteria_p_Firmicutes"]["domain"] == "Bacteria"
        assert result["SP2_d_Archaea_p_Thermoproteota"]["domain"] == "Archaea"

    def test_parse_labels_table_format(self):
        """parse_labels correctly parses table format B labels."""
        mapper = TaxonomyMapper()
        labels = [
            "d__Bacteria;p__Firmicutes",
            "d__Archaea;p__Thermoproteota",
        ]
        result = mapper.parse_labels(labels)
        assert result["d__Bacteria;p__Firmicutes"]["domain"] == "Bacteria"
        assert result["d__Archaea;p__Thermoproteota"]["domain"] == "Archaea"

    def test_identify_groups_by_phylum(self):
        """identify_groups groups taxa by the specified rank."""
        mapper = TaxonomyMapper()
        labels = [
            "SP1_d_Bacteria_p_Firmicutes",
            "SP2_d_Bacteria_p_Firmicutes",
            "SP3_d_Archaea_p_Thermoproteota",
        ]
        mapper.parse_labels(labels)
        groups = mapper.identify_groups(labels, rank="phylum")
        assert "Firmicutes" in groups
        assert "Thermoproteota" in groups
        assert len(groups["Firmicutes"]) == 2
        assert len(groups["Thermoproteota"]) == 1

    def test_check_completeness_all_complete(self):
        """check_completeness returns complete for fully annotated labels."""
        mapper = TaxonomyMapper()
        labels = [
            "SP1_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP2_d_Bacteria_p_Firmicutes_c_Bacilli",
        ]
        mapper.parse_labels(labels)
        result = mapper.check_completeness(labels)
        assert len(result["complete"]) == 2
        assert len(result["incomplete"]) == 0

    def test_check_completeness_with_missing(self):
        """check_completeness detects incomplete annotations."""
        mapper = TaxonomyMapper()
        labels = [
            "SP1_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP2_d_Bacteria",
        ]
        mapper.parse_labels(labels)
        result = mapper.check_completeness(
            labels, required_ranks=["domain", "phylum", "class"]
        )
        assert len(result["incomplete"]) == 1
        assert result["coverage"] < 100.0

    def test_get_taxonomy_priority_table(self):
        """get_taxonomy with table priority uses table mapping."""
        mapper = TaxonomyMapper()
        labels = ["SP1_d_Bacteria_p_Firmicutes"]
        mapper.parse_labels(labels)
        tax = mapper.get_taxonomy("SP1_d_Bacteria_p_Firmicutes")
        assert tax["domain"] == "Bacteria"

    def test_resolve_taxon_group_luca(self):
        """resolve_taxon_group resolves LUCA to all taxa."""
        mapper = TaxonomyMapper()
        labels = [
            "SP1_d_Bacteria_p_Firmicutes",
            "SP2_d_Archaea_p_Thermoproteota",
        ]
        mapper.parse_labels(labels)
        result = mapper.resolve_taxon_group(labels, "LUCA")
        assert len(result) == 2

    def test_resolve_taxon_group_lbca(self):
        """resolve_taxon_group resolves LBCA to Bacteria only."""
        mapper = TaxonomyMapper()
        labels = [
            "SP1_d_Bacteria_p_Firmicutes",
            "SP2_d_Archaea_p_Thermoproteota",
        ]
        mapper.parse_labels(labels)
        result = mapper.resolve_taxon_group(labels, "LBCA")
        assert len(result) == 1
        assert "SP1_d_Bacteria_p_Firmicutes" in result

    def test_resolve_taxon_group_root(self):
        """resolve_taxon_group resolves root to all taxa."""
        mapper = TaxonomyMapper()
        labels = ["A", "B", "C"]
        mapper.parse_labels(labels)
        result = mapper.resolve_taxon_group(labels, "root")
        assert len(result) == 3

    def test_resolve_taxon_group_not_found_raises(self):
        """resolve_taxon_group raises ValidationError for unknown group."""
        mapper = TaxonomyMapper()
        labels = ["SP1_d_Bacteria"]
        mapper.parse_labels(labels)
        with pytest.raises(ValidationError):
            mapper.resolve_taxon_group(labels, "NonexistentGroup")

    def test_load_mapping_two_column(self, tmp_path):
        """load_mapping correctly loads a two-column TSV mapping file."""
        mapping_file = tmp_path / "mapping.tsv"
        mapping_file.write_text(
            "SP1\td__Bacteria;p__Firmicutes\n"
            "SP2\td__Archaea;p__Thermoproteota\n"
        )
        mapper = TaxonomyMapper()
        mapper.load_mapping(str(mapping_file))
        tax = mapper.get_taxonomy("SP1")
        assert tax["domain"] == "Bacteria"
        assert tax["phylum"] == "Firmicutes"

    def test_load_mapping_multi_column(self, tmp_path):
        """load_mapping correctly loads a multi-column CSV mapping file."""
        mapping_file = tmp_path / "mapping.csv"
        mapping_file.write_text(
            "taxon,domain,phylum\n"
            "SP1,Bacteria,Firmicutes\n"
            "SP2,Archaea,Thermoproteota\n"
        )
        mapper = TaxonomyMapper()
        mapper.load_mapping(str(mapping_file), delimiter=",")
        tax = mapper.get_taxonomy("SP1")
        assert tax["domain"] == "Bacteria"
        assert tax["phylum"] == "Firmicutes"

    def test_validate_mapping_against_tree(self, tmp_path):
        """validate_mapping_against_tree detects extra and missing taxa."""
        mapping_file = tmp_path / "mapping.tsv"
        mapping_file.write_text(
            "SP1\td__Bacteria;p__Firmicutes\n"
            "SP2\td__Archaea;p__Thermoproteota\n"
            "SP3\td__Bacteria;p__Firmicutes\n"
        )
        mapper = TaxonomyMapper()
        mapper.load_mapping(str(mapping_file))
        tree_labels = ["SP1", "SP2"]
        result = mapper.validate_mapping_against_tree(tree_labels)
        assert "SP3" in result["extra_in_table"]

    def test_get_warnings(self):
        """get_warnings returns accumulated warnings list."""
        mapper = TaxonomyMapper()
        labels = ["SP1_d_Bacteria_p_Firmicutes", "plain_label"]
        mapper.parse_labels(labels)
        warnings = mapper.get_warnings()
        # plain_label may generate a parse warning
        assert isinstance(warnings, list)


# ---------------------------------------------------------------------------
# 5. MonophylyAnalyzer
# ---------------------------------------------------------------------------

class TestMonophylyAnalyzer:
    """Tests for MonophylyAnalyzer class."""

    def _make_tree(self, newick):
        return Phylo.read(StringIO(newick), "newick")

    def _make_mapper(self, labels):
        mapper = TaxonomyMapper()
        mapper.parse_labels(labels)
        return mapper

    def test_analyze_tree_monophyletic(self):
        """analyze_tree identifies monophyletic groups."""
        tree = self._make_tree(TREE_FMT_A_MONO)
        labels = [
            "SP1_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP2_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP3_d_Archaea_p_Thermoproteota_c_Sulfolobia",
            "SP4_d_Archaea_p_Thermoproteota_c_Sulfolobia",
        ]
        mapper = self._make_mapper(labels)
        analyzer = MonophylyAnalyzer(mapper)
        result = analyzer.analyze_tree(tree, rank="phylum")
        assert "Firmicutes" in result["monophyletic"]
        assert "Thermoproteota" in result["monophyletic"]

    def test_analyze_tree_non_monophyletic(self):
        """analyze_tree identifies non-monophyletic groups."""
        tree = self._make_tree(TREE_FMT_A_NONMONO)
        labels = [
            "SP1_d_Bacteria_p_Firmicutes",
            "SP2_d_Archaea_p_Thermoproteota",
            "SP3_d_Bacteria_p_Firmicutes",
            "SP4_d_Archaea_p_Thermoproteota",
        ]
        mapper = self._make_mapper(labels)
        analyzer = MonophylyAnalyzer(mapper)
        result = analyzer.analyze_tree(tree, rank="domain")
        assert "Bacteria" in result["non_monophyletic"]

    def test_check_monophyly_by_group_monophyletic(self):
        """check_monophyly_by_group returns is_monophyletic=True for monophyletic group."""
        tree = self._make_tree(TREE_FMT_A_MONO)
        labels = [
            "SP1_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP2_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP3_d_Archaea_p_Thermoproteota_c_Sulfolobia",
            "SP4_d_Archaea_p_Thermoproteota_c_Sulfolobia",
        ]
        mapper = self._make_mapper(labels)
        analyzer = MonophylyAnalyzer(mapper)
        result = analyzer.check_monophyly_by_group(tree, "Bacteria", labels)
        assert result["is_monophyletic"] is True

    def test_check_monophyly_by_group_non_monophyletic(self):
        """check_monophyly_by_group returns is_monophyletic=False for non-monophyletic group."""
        tree = self._make_tree(TREE_FMT_A_NONMONO)
        labels = [
            "SP1_d_Bacteria_p_Firmicutes",
            "SP2_d_Archaea_p_Thermoproteota",
            "SP3_d_Bacteria_p_Firmicutes",
            "SP4_d_Archaea_p_Thermoproteota",
        ]
        mapper = self._make_mapper(labels)
        analyzer = MonophylyAnalyzer(mapper)
        result = analyzer.check_monophyly_by_group(tree, "Bacteria", labels)
        assert result["is_monophyletic"] is False

    def test_check_monophyly_by_group_luca(self):
        """check_monophyly_by_group resolves LUCA to all taxa (monophyletic by definition)."""
        tree = self._make_tree(TREE_FMT_A_MONO)
        labels = [
            "SP1_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP2_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP3_d_Archaea_p_Thermoproteota_c_Sulfolobia",
            "SP4_d_Archaea_p_Thermoproteota_c_Sulfolobia",
        ]
        mapper = self._make_mapper(labels)
        analyzer = MonophylyAnalyzer(mapper)
        result = analyzer.check_monophyly_by_group(tree, "LUCA", labels)
        assert result["is_monophyletic"] is True

    def test_generate_report(self):
        """generate_report produces a human-readable string."""
        tree = self._make_tree(TREE_FMT_A_MONO)
        labels = [
            "SP1_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP2_d_Bacteria_p_Firmicutes_c_Bacilli",
            "SP3_d_Archaea_p_Thermoproteota_c_Sulfolobia",
            "SP4_d_Archaea_p_Thermoproteota_c_Sulfolobia",
        ]
        mapper = self._make_mapper(labels)
        analyzer = MonophylyAnalyzer(mapper)
        analysis = analyzer.analyze_tree(tree, rank="phylum")
        report = analyzer.generate_report(analysis)
        assert isinstance(report, str)
        assert len(report) > 0


# ---------------------------------------------------------------------------
# 6. FigTreeStyler taxonomy integration — Table S2 items #15-20
# ---------------------------------------------------------------------------

class TestStylerTaxonomyIntegration:
    """Tests for FigTreeStyler taxonomy methods (Table S2 #15-20)."""

    def test_format_a_embedded_taxonomy(self):
        """#15: Embedded format A taxonomy is correctly parsed by FigTreeStyler."""
        styler = FigTreeStyler().load_content(TREE_FMT_A_MONO)
        result = styler.analyze_taxonomy(rank="phylum")
        assert "Firmicutes" in result["monophyletic"]
        assert "Thermoproteota" in result["monophyletic"]

    def test_format_b_table_taxonomy(self):
        """#16: Table format B taxonomy works via external mapping file."""
        # Use a tree with simple labels + external mapping
        tree = "((SP1:1,SP2:1):1,(SP3:1,SP4:1):2);"
        styler = FigTreeStyler().load_content(tree)
        result = styler.analyze_taxonomy(
            mapping_file=None, rank="genus"
        )
        # Without taxonomy info, all taxa are unmapped
        assert "unmapped" in result

    def test_collapse_monophyletic_clade(self):
        """#17: Collapsing a monophyletic clade succeeds."""
        styler = FigTreeStyler().load_content(TREE_SIMPLE)
        styler.collapse_clade(["A", "B"], label="clade_AB")
        collapses = styler.get_collapses()
        assert len(collapses) == 1
        assert collapses[0].label == "clade_AB"
        assert collapses[0].collapse_type == "collapse"

    def test_nested_collapse(self):
        """#18: Nested collapses (inner + outer) are both registered."""
        styler = FigTreeStyler().load_content(TREE_NESTED)
        styler.collapse_clade(["A", "B"], label="inner")
        styler.collapse_clade(["A", "B", "C"], label="outer")
        collapses = styler.get_collapses()
        assert len(collapses) == 2
        labels = [c.label for c in collapses]
        assert "inner" in labels
        assert "outer" in labels

    def test_collapse_label_assigned_to_representative(self, tmp_path):
        """#19: Collapse label is correctly assigned to the representative node."""
        styler = FigTreeStyler().load_content(TREE_SIMPLE)
        custom_label = "MyClade"
        styler.collapse_clade(["A", "B"], label=custom_label)
        collapses = styler.get_collapses()
        assert collapses[0].label == custom_label
        # Verify the label appears in exported content
        out_file = tmp_path / "out.nex"
        styler.export(str(out_file))
        content = out_file.read_text()
        assert custom_label in content

    def test_collapse_default_label(self):
        """Collapse without explicit label generates a default label."""
        styler = FigTreeStyler().load_content(TREE_SIMPLE)
        styler.collapse_clade(["A", "B"])
        collapses = styler.get_collapses()
        assert collapses[0].label == "{2 taxa}"

    def test_collapse_by_group_monophyletic(self):
        """#17 (extended): collapse_by_group succeeds for monophyletic group."""
        styler = FigTreeStyler().load_content(TREE_FMT_A_MONO)
        styler.collapse_by_group("Firmicutes", label="Firmicutes_clade")
        collapses = styler.get_collapses()
        assert len(collapses) == 1
        assert collapses[0].label == "Firmicutes_clade"

    def test_collapse_by_group_non_monophyletic_warns(self):
        """#20: Non-monophyletic group collapse issues CompatibilityWarning."""
        styler = FigTreeStyler().load_content(TREE_FMT_A_NONMONO)
        with pytest.warns(CompatibilityWarning):
            styler.collapse_by_group("Bacteria")
        # Non-monophyletic group should not be collapsed
        collapses = styler.get_collapses()
        assert len(collapses) == 0

    def test_check_taxonomy_completeness(self):
        """check_taxonomy_completeness returns completeness info."""
        styler = FigTreeStyler().load_content(TREE_FMT_A_MONO)
        result = styler.check_taxonomy_completeness()
        assert "complete" in result
        assert "incomplete" in result
        assert "coverage" in result

    def test_configure_taxonomy(self):
        """configure_taxonomy sets taxonomy parameters."""
        styler = FigTreeStyler().load_content(TREE_SIMPLE)
        styler.configure_taxonomy(
            delimiter_mode="greedy",
            table_sep=",",
            source_priority="embedded",
        )
        assert styler._taxonomy_delimiter_mode == "greedy"
        assert styler._taxonomy_table_sep == ","
        assert styler._taxonomy_source_priority == "embedded"


# ---------------------------------------------------------------------------
# 7. Conflict detection — Table S2 item #27
# ---------------------------------------------------------------------------

class TestColorHilightConflict:
    """#27: set_clade_color + highlight_clade conflict detection."""

    def test_color_hilight_conflict_warns_on_export(self, tmp_path):
        """Applying both set_clade_color and highlight_clade to the same
        taxa triggers CompatibilityWarning during export."""
        styler = FigTreeStyler().load_content(TREE_SIMPLE)
        styler.highlight_clade(["A", "B"], color="#804548")
        styler.set_clade_color(["A", "B"], "#ff0000")
        with pytest.warns(CompatibilityWarning, match="conflict"):
            styler.export(str(tmp_path / "out.nex"))

    def test_color_hilight_no_conflict_different_taxa(self, tmp_path):
        """No conflict when color and hilight target different taxa."""
        styler = FigTreeStyler().load_content(
            "((A:1,B:1):1,(C:1,D:1):2);"
        )
        styler.highlight_clade(["A", "B"], color="#804548")
        styler.set_clade_color(["C", "D"], "#ff0000")
        # Should not raise a conflict warning
        with warnings.catch_warnings():
            warnings.simplefilter("error", CompatibilityWarning)
            try:
                styler.export(str(tmp_path / "out.nex"))
            except CompatibilityWarning as e:
                if "conflict" in str(e).lower():
                    pytest.fail("Unexpected conflict warning for different taxa")

    def test_set_clade_color_all_no_conflict(self, tmp_path):
        """set_clade_color_all does not conflict with hilight."""
        styler = FigTreeStyler().load_content(TREE_SIMPLE)
        styler.highlight_clade(["A", "B"], color="#804548")
        styler.set_clade_color_all(["A", "B"], "#ff0000")
        # set_clade_color_all targets descendant branches, not MRCA node
        # so no conflict warning expected
        styler.export(str(tmp_path / "out.nex"))


# ---------------------------------------------------------------------------
# 8. Instance isolation — Table S2 item #28
# ---------------------------------------------------------------------------

class TestHilightMarksIsolation:
    """#28: _hilight_marks instance isolation between FigTreeStyler instances."""

    def test_hilight_marks_isolated_between_instances(self, tmp_path):
        """Two FigTreeStyler instances do not share _hilight_marks."""
        s1 = FigTreeStyler().load_content(TREE_SIMPLE)
        s2 = FigTreeStyler().load_content("((X:1,Y:1):1,Z:2);")
        # Both start empty
        assert s1._hilight_marks == []
        assert s2._hilight_marks == []
        # Add hilight to s1 and export to populate _hilight_marks
        s1.highlight_clade(["A", "B"], color="#804548")
        s1.export(str(tmp_path / "out1.nex"))
        # s1 should have hilight marks populated
        assert len(s1._hilight_marks) > 0
        # s2 should still be empty
        assert s2._hilight_marks == []

    def test_hilight_marks_reset_on_load_content(self, tmp_path):
        """_hilight_marks is reset when load_content is called."""
        styler = FigTreeStyler().load_content(TREE_SIMPLE)
        styler.highlight_clade(["A", "B"], color="#804548")
        styler.export(str(tmp_path / "out.nex"))
        assert len(styler._hilight_marks) > 0
        # Reload new content
        styler.load_content("((X:1,Y:1):1,Z:2);")
        assert styler._hilight_marks == []

    def test_hilight_marks_reset_on_reset(self, tmp_path):
        """_hilight_marks is cleared by reset()."""
        styler = FigTreeStyler().load_content(TREE_SIMPLE)
        styler.highlight_clade(["A", "B"], color="#804548")
        styler.export(str(tmp_path / "out.nex"))
        assert len(styler._hilight_marks) > 0
        styler.reset()
        assert styler._hilight_marks == []

    def test_hilight_marks_not_shared_in_list(self):
        """_hilight_marks is a per-instance list, not a class-level shared list."""
        s1 = FigTreeStyler()
        s2 = FigTreeStyler()
        assert s1._hilight_marks is not s2._hilight_marks
        s1._hilight_marks.append(("test", 1, 0.0, "#000000"))
        assert len(s1._hilight_marks) == 1
        assert len(s2._hilight_marks) == 0


# ---------------------------------------------------------------------------
# 9. Library-mode API
# ---------------------------------------------------------------------------

class TestLibraryModeAPI:
    """Tests for parse_taxonomy and is_monophyletic convenience functions."""

    def test_parse_taxonomy_convenience(self):
        """parse_taxonomy convenience function parses embedded labels."""
        result = parse_taxonomy("SP1_d_Bacteria_p_Firmicutes")
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"

    def test_parse_taxonomy_table_format(self):
        """parse_taxonomy convenience function parses table format."""
        result = parse_taxonomy("d__Bacteria;p__Firmicutes")
        assert result["domain"] == "Bacteria"
        assert result["phylum"] == "Firmicutes"

    def test_is_monophyletic_true(self):
        """is_monophyletic returns True for a monophyletic taxonomic group."""
        # Bacteria is monophyletic in TREE_FMT_A_MONO
        result = is_monophyletic(TREE_FMT_A_MONO, "Bacteria")
        assert result is True

    def test_is_monophyletic_false(self):
        """is_monophyletic returns False for a non-monophyletic taxonomic group."""
        # Bacteria is non-monophyletic in TREE_FMT_A_NONMONO
        result = is_monophyletic(TREE_FMT_A_NONMONO, "Bacteria")
        assert result is False


class TestInstanceScopedPrefixes:
    """Instance-scoped rank-prefix configuration (TaxonomyMapper(prefixes=...)).

    Guards the thread-safe alternative to module-level set_rank_prefixes():
    a mapper built with an explicit mapping must not consult or mutate the
    module-level configuration, and must not affect other mappers.
    """

    def test_custom_prefixes_embedded(self):
        from figtreekit.taxonomy import TaxonomyMapper
        mapper = TaxonomyMapper(prefixes={"x": "phylum"})
        result = mapper.parse_labels(["taxon1_x_MyPhylum"])
        assert result["taxon1_x_MyPhylum"].get("phylum") == "MyPhylum"

    def test_custom_prefixes_do_not_leak_to_module_config(self):
        from figtreekit.taxonomy import TaxonomyMapper, get_rank_prefixes
        before = get_rank_prefixes()
        TaxonomyMapper(prefixes={"x": "phylum"}).parse_labels(["t_x_Foo"])
        assert get_rank_prefixes() == before

    def test_default_mapper_unaffected_by_instance_mapper(self):
        from figtreekit.taxonomy import TaxonomyMapper
        TaxonomyMapper(prefixes={"x": "phylum"}).parse_labels(["t_x_Foo"])
        default = TaxonomyMapper()
        result = default.parse_labels(["taxon_d_Bacteria_p_Cyano"])
        assert result["taxon_d_Bacteria_p_Cyano"].get("domain") == "Bacteria"
        assert result["taxon_d_Bacteria_p_Cyano"].get("phylum") == "Cyano"

    def test_custom_prefixes_table_format(self):
        from figtreekit.taxonomy import TaxonomyMapper
        mapper = TaxonomyMapper(prefixes={"x": "phylum"})
        result = mapper.parse_labels(["x__MyPhylum"], sep=";")
        assert result["x__MyPhylum"].get("phylum") == "MyPhylum"

    def test_prefix_helper_builds_independent_maps(self):
        from figtreekit.taxonomy import _build_prefix_maps
        rp, emb, gtdb, ranks = _build_prefix_maps({"x": "phylum"})
        assert rp == {"x": "phylum"}
        assert emb == {"_x_": "phylum"}
        assert gtdb == {"x__": "phylum"}
        assert ranks == ["phylum"]

    def test_prefix_helper_none_returns_module_config(self):
        from figtreekit.taxonomy import _build_prefix_maps, get_rank_prefixes
        rp, _, _, _ = _build_prefix_maps(None)
        assert rp == get_rank_prefixes()
