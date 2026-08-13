"""
Supplemental tests for figtreekit.validators module.

These tests cover the public interfaces of the figtreekit.validators module:

- deep_validate_newick: well-formed, malformed, empty, and edge-case input
- scan_for_anomalous_content: control chars, BiDi overrides, mixed content
- cross_validate_tree_sequence: match, mismatch, partial match
- validate_biological_plausibility: single-taxon, all-zero branch lengths,
  large tree warning
"""

import os
import tempfile

import pytest

from figtreekit.validators import (
    TreeValidator,
    deep_validate_newick,
    deep_validate_fasta,
    deep_validate_fastq,
    scan_for_anomalous_content,
    scan_node_names_for_anomalous,
    validate_input_file,
    cross_validate_tree_sequence,
)


# ══════════════════════════════════════════════════════════════════════
# deep_validate_newick
# ══════════════════════════════════════════════════════════════════════

class TestDeepValidateNewick:

    def test_valid_simple_tree(self):
        result = deep_validate_newick("(A:0.1,B:0.2);", label="test")
        assert result["errors"] == []
        assert result["leaf_count"] == 2

    def test_valid_nested_tree(self):
        result = deep_validate_newick(
            "(((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6):0.7,E:0.8);",
            label="test",
        )
        assert result["errors"] == []
        assert result["leaf_count"] == 5

    def test_empty_content(self):
        result = deep_validate_newick("", label="test")
        assert len(result["errors"]) > 0
        assert "empty" in result["errors"][0].lower()

    def test_whitespace_only(self):
        result = deep_validate_newick("   \n  ", label="test")
        assert len(result["errors"]) > 0

    def test_missing_semicolon(self):
        result = deep_validate_newick("(A:0.1,B:0.2)", label="test")
        errors = [e.lower() for e in result["errors"]]
        assert any("semicolon" in e or "does not end with ';'" in e for e in errors)

    def test_unbalanced_parentheses_extra_open(self):
        result = deep_validate_newick("((A:0.1,B:0.2);", label="test")
        errors = [e.lower() for e in result["errors"]]
        assert any("unmatched" in e and "(" in e for e in errors)

    def test_unbalanced_parentheses_extra_close(self):
        result = deep_validate_newick("(A:0.1,B:0.2));", label="test")
        errors = [e.lower() for e in result["errors"]]
        assert any("unmatched" in e and ")" in e for e in errors)

    def test_unbalanced_square_brackets(self):
        result = deep_validate_newick("(A:0.1,B:0.2)[&;", label="test")
        warns = [w.lower() for w in result["warnings"]]
        assert any("unclosed" in w and "[" in w for w in warns)

    def test_unterminated_quote(self):
        result = deep_validate_newick("('Species A:0.1,B:0.2);", label="test")
        errors = [e.lower() for e in result["errors"]]
        assert any("unterminated" in e or "quote" in e for e in errors)

    def test_negative_branch_length(self):
        result = deep_validate_newick("((A:-0.1,B:0.2):0.3,C:0.4);", label="test")
        errors = [e.lower() for e in result["errors"]]
        assert any("negative" in e for e in errors)

    def test_duplicate_tip_names(self):
        result = deep_validate_newick("((A:0.1,A:0.2):0.3,B:0.4);", label="test")
        errors = [e.lower() for e in result["errors"]]
        assert any("duplicate" in e for e in errors)

    def test_empty_node_names(self):
        result = deep_validate_newick("(A:0.1,,B:0.2);", label="test")
        errors = [e.lower() for e in result["errors"]]
        assert any("empty" in e for e in errors)

    def test_empty_node_name_after_paren(self):
        result = deep_validate_newick("(,A:0.1,B:0.2);", label="test")
        errors = [e.lower() for e in result["errors"]]
        assert any("empty" in e for e in errors)

    def test_quoted_taxon_names_preserved(self):
        """Quoted taxon names should be parsed without errors."""
        result = deep_validate_newick(
            "('Species A':0.1,'Genus B':0.2);", label="test"
        )
        # Quoted names themselves are fine; just check no false positives
        assert result["leaf_count"] >= 2

    def test_single_taxon_tree(self):
        """Single-taxon tree: A:0.1; — not syntactically valid Newick but
        validate_biological_plausibility handles this separately."""
        result = deep_validate_newick("A:0.1;", label="test")
        # Should have bracket-related errors since no parentheses
        assert "unmatched" not in str(result["errors"]).lower()  # no brackets at all

    def test_all_zero_branch_lengths(self):
        result = deep_validate_newick("((A:0.0,B:0.0):0.0,C:0.0);", label="test")
        # deep_validate_newick itself may not catch this (it's caught by
        # validate_biological_plausibility), but it should not crash
        assert isinstance(result["leaf_count"], int)


# ══════════════════════════════════════════════════════════════════════
# scan_for_anomalous_content
# ══════════════════════════════════════════════════════════════════════

class TestScanForAnomalousContent:

    def test_clean_content(self):
        errors = scan_for_anomalous_content(
            "(A:0.1,B:0.2);", label="tree.nwk"
        )
        assert errors == []

    def test_null_byte(self):
        content = "tree\x00content"
        errors = scan_for_anomalous_content(content, label="test")
        assert len(errors) > 0
        assert any("U+0000" in e for e in errors)

    def test_bidi_override_lre(self):
        """Left-to-Right Embedding U+202A."""
        content = f"({'A' if True else 'B'}:\u202A0.1,B:0.2);"
        errors = scan_for_anomalous_content(content, label="test")
        assert len(errors) > 0
        assert any("U+202A" in e for e in errors)

    def test_bidi_override_rlo(self):
        """Right-to-Left Override U+202E."""
        content = f"(A:0.1,\u202EB:0.2);"
        errors = scan_for_anomalous_content(content, label="test")
        assert len(errors) > 0
        assert any("U+202E" in e for e in errors)

    def test_bidi_isolate_rli(self):
        """Right-to-Left Isolate U+2067."""
        content = f"(A:\u20670.1,B:0.2);"
        errors = scan_for_anomalous_content(content, label="test")
        assert len(errors) > 0
        assert any("U+2067" in e for e in errors)

    def test_control_character_bell(self):
        """Bell character U+0007."""
        content = "(A:0.1,\x07B:0.2);"
        errors = scan_for_anomalous_content(content, label="test")
        assert len(errors) > 0

    def test_multiple_control_chars_truncated(self):
        """Many control chars — should limit to 5 + suppression msg."""
        content = "\x00\x01\x02\x03\x04\x05\x06" * 10
        errors = scan_for_anomalous_content(content, label="test")
        assert len(errors) >= 5
        # Last error should indicate suppression
        assert any("suppressed" in e.lower() for e in errors) or len(errors) == 6

    def test_label_in_error_message(self):
        content = "(A:\x00.1,B:0.2);"
        errors = scan_for_anomalous_content(content, label="myfile.nwk")
        assert len(errors) > 0
        assert "myfile.nwk" in errors[0]


# ══════════════════════════════════════════════════════════════════════
# scan_node_names_for_anomalous
# ══════════════════════════════════════════════════════════════════════

class TestScanNodeNamesForAnomalous:

    def test_clean_names(self):
        errors = scan_node_names_for_anomalous(
            ["A", "B", "C"], label="test"
        )
        assert errors == []

    def test_control_char_in_name(self):
        errors = scan_node_names_for_anomalous(
            ["A", "B\x00ad"], label="test"
        )
        assert len(errors) > 0
        assert any("U+0000" in e for e in errors)

    def test_bidi_in_name(self):
        errors = scan_node_names_for_anomalous(
            ["Good", "\u202EBad"], label="test"
        )
        assert len(errors) > 0
        assert any("U+202E" in e for e in errors)


# ══════════════════════════════════════════════════════════════════════
# cross_validate_tree_sequence
# ══════════════════════════════════════════════════════════════════════

class TestCrossValidateTreeSequence:

    def test_perfect_match(self):
        result = cross_validate_tree_sequence(
            ["A", "B", "C"], ["A", "B", "C"], label="test"
        )
        assert result["errors"] == []
        assert result["matched"] == 3

    def test_tree_has_extra_tips(self):
        result = cross_validate_tree_sequence(
            ["A", "B", "C", "D"], ["A", "B", "C"], label="test"
        )
        assert len(result["errors"]) > 0
        assert "D" in result["only_in_tree"]

    def test_seq_has_extra_ids(self):
        result = cross_validate_tree_sequence(
            ["A", "B"], ["A", "B", "C", "D"], label="test"
        )
        assert len(result["errors"]) > 0
        assert result["only_in_sequences"] == ["C", "D"]

    def test_complete_mismatch(self):
        result = cross_validate_tree_sequence(
            ["X", "Y"], ["A", "B"], label="test"
        )
        assert len(result["errors"]) == 2
        assert result["matched"] == 0

    def test_partial_overlap(self):
        result = cross_validate_tree_sequence(
            ["A", "B", "C"], ["B", "C", "D"], label="test"
        )
        assert result["matched"] == 2
        assert "A" in result["only_in_tree"]
        assert "D" in result["only_in_sequences"]

    def test_empty_tree_labels(self):
        result = cross_validate_tree_sequence(
            [], ["A", "B"], label="test"
        )
        assert len(result["errors"]) > 0
        assert result["matched"] == 0

    def test_empty_sequence_ids(self):
        result = cross_validate_tree_sequence(
            ["A", "B"], [], label="test"
        )
        assert len(result["errors"]) > 0
        assert result["matched"] == 0

    def test_match_warning(self):
        """When everything matches, there should be a warning (not error)."""
        result = cross_validate_tree_sequence(
            ["A", "B"], ["A", "B"], label="test"
        )
        assert len(result["warnings"]) >= 1
        assert "match" in result["warnings"][0].lower()


# ══════════════════════════════════════════════════════════════════════
# validate_biological_plausibility
# ══════════════════════════════════════════════════════════════════════

class TestValidateBiologicalPlausibility:

    def test_normal_tree_no_issues(self):
        issues = TreeValidator.validate_biological_plausibility(
            "((A:0.1,B:0.2):0.3,C:0.4);"
        )
        assert issues == []

    def test_single_taxon_degenerate(self):
        issues = TreeValidator.validate_biological_plausibility("A:0.1;")
        assert len(issues) > 0
        assert any("single" in i.lower() for i in issues)

    def test_all_zero_branch_lengths(self):
        issues = TreeValidator.validate_biological_plausibility(
            "((A:0.0,B:0.0):0.0,C:0.0);"
        )
        assert len(issues) > 0
        assert any("zero" in i.lower() for i in issues)

    def test_large_tree_warning(self):
        """Tree with many taxa should warn (threshold=10 for test)."""
        taxa_list = ",".join(f"T{i}:0.1" for i in range(15))
        newick = f"({taxa_list});"
        issues = TreeValidator.validate_biological_plausibility(
            newick, max_taxa_warning_threshold=10
        )
        assert len(issues) > 0
        assert any("15" in i for i in issues)

    def test_large_tree_warning_disabled(self):
        """threshold=0 disables large tree warning."""
        taxa_list = ",".join(f"T{i}:0.1" for i in range(15))
        newick = f"({taxa_list});"
        issues = TreeValidator.validate_biological_plausibility(
            newick, max_taxa_warning_threshold=0
        )
        # No large-taxa warning should appear
        assert not any("memory" in i.lower() for i in issues)

    def test_non_string_input(self):
        issues = TreeValidator.validate_biological_plausibility(None)
        assert issues == []

    def test_empty_string_input(self):
        issues = TreeValidator.validate_biological_plausibility("")
        assert issues == []


# ══════════════════════════════════════════════════════════════════════
# validate_input_file (existing public API)
# ══════════════════════════════════════════════════════════════════════

class TestValidateInputFile:

    def test_valid_newick_file(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.nwk', delete=False
        ) as f:
            f.write("((A:0.1,B:0.2):0.3,C:0.4);")
            path = f.name
        try:
            result = validate_input_file(path)
            assert result["valid"] is True
            assert result["format"] == "newick"
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        result = validate_input_file("/nonexistent/path.tre")
        assert result["valid"] is False
        assert any("not found" in e.lower() for e in result["errors"])

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.tre', delete=False
        ) as f:
            path = f.name
        try:
            result = validate_input_file(path)
            assert result["valid"] is False
            assert any("empty" in e.lower() for e in result["errors"])
        finally:
            os.unlink(path)

    def test_format_mismatch_extension_vs_content(self):
        """Extension says .nex but content is Newick."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.nex', delete=False
        ) as f:
            f.write("((A:0.1,B:0.2):0.3,C:0.4);")
            path = f.name
        try:
            result = validate_input_file(path)
            assert result["valid"] is True  # content-based wins
            assert any(
                "content" in w.lower() or "extension" in w.lower()
                for w in result["warnings"]
            )
        finally:
            os.unlink(path)

    def test_content_based_detection_overrides_extension(self):
        """Content-based detection should override unrecognized extension."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.xyz', delete=False
        ) as f:
            f.write("((A:0.1,B:0.2):0.3,C:0.4);")
            path = f.name
        try:
            result = validate_input_file(path)
            # Content-based detection succeeds: format is "newick" despite .xyz ext
            assert result["format"] == "newick"
            assert result["valid"] is True
        finally:
            os.unlink(path)

    def test_unrecognized_extension_no_content_match(self):
        """Completely unrecognized content + extension should warn."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.xyz', delete=False
        ) as f:
            f.write("This is not any known format whatsoever.")
            path = f.name
        try:
            result = validate_input_file(path)
            # Either a warning about unrecognized or content couldn't be determined
            all_msgs = [w.lower() for w in result["warnings"]]
            all_msgs.extend([e.lower() for e in result["errors"]])
            assert any(
                "unrecognized" in m or "could not" in m or "determine" in m
                for m in all_msgs
            ) or result["format"] is None
        finally:
            os.unlink(path)


# ══════════════════════════════════════════════════════════════════════
# deep_validate_fasta (supplementary coverage)
# ══════════════════════════════════════════════════════════════════════

class TestDeepValidateFasta:

    def test_valid_simple_fasta(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.fa', delete=False
        ) as f:
            f.write(">seq1\nATCG\n>seq2\nGCTA\n")
            path = f.name
        try:
            result = deep_validate_fasta(path)
            assert result["sequence_count"] == 2
            assert result["alphabet"] == "DNA"
        finally:
            os.unlink(path)

    def test_duplicate_ids(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.fa', delete=False
        ) as f:
            f.write(">seq1\nATCG\n>seq1\nGCTA\n")
            path = f.name
        try:
            result = deep_validate_fasta(path)
            assert len(result["errors"]) > 0
            assert any("duplicate" in e.lower() for e in result["errors"])
        finally:
            os.unlink(path)

    def test_length_mismatch(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.fa', delete=False
        ) as f:
            f.write(">seq1\nATCG\n>seq2\nGCTAAA\n")
            path = f.name
        try:
            result = deep_validate_fasta(path)
            assert result["length_mismatch"] is True
            assert len(result["warnings"]) > 0
        finally:
            os.unlink(path)
