"""Quality-regression tests covering key behavioural contracts.

Each test class locks one capability of the public API:

- numeric tip names survive the Newick round-trip (BEAST / translate IDs)
- FASTA / FASTQ validation does not emit a DeprecationWarning
- styler hilight band height uses the minimum tip height (jebl convention)
- taxonomy circular-dependency detection on directed containment graphs
- annotation application via a single shared engine (colour / font)
- node_count semantics (leaf count + internal nodes)
- configurable domain rank name for special identifiers (LUCA / LACA / LBCA)
- file paths containing parentheses are treated as files, not inline Newick

Run with::

    cd <project root>
    python -m pytest test/ -q -o addopts=""
    python -m pytest test/ -q            # with --cov-fail-under=60
"""

import warnings
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from figtreekit import (
    FigTreeStyler,
    NodeAnnotation,
    deep_validate_newick,
    deep_validate_fasta,
    deep_validate_fastq,
    detect_taxonomy_circular_deps,
    TaxonomyMapper,
    set_rank_prefixes,
    get_rank_prefixes,
    is_monophyletic,
)
from figtreekit.taxonomy import get_domain_rank_name
from figtreekit.validators import scan_node_names_for_anomalous
from figtreekit.exceptions import ValidationError


# ===========================================================================
# 数字末端名必须在 Newick 往返中保留
# ===========================================================================

class TestNumericTipPreserved:
    """Numeric leaf labels (BEAST style, and translate IDs) must be preserved."""

    def test_numeric_tips_in_plain_newick_serialize(self):
        s = FigTreeStyler()
        s.load_content("((1:0.1,2:0.2):0.3,3:0.4);")
        tree = s._parse_tree_with_biopython(s._tree_content)
        out = s._serialize_tree_to_newick(tree)
        assert out is not None
        # All three numeric leaf labels survive (followed by their branch lengths)
        assert "1:0.1" in out
        assert "2:0.2" in out
        assert "3:0.4" in out

    def test_numeric_tips_via_full_export(self, tmp_path):
        s = FigTreeStyler()
        s.load_content("((1:0.1,2:0.2):0.3,3:0.4);")
        out_file = tmp_path / "numeric.nex"
        s.export(str(out_file))
        content = out_file.read_text()
        assert "1:0.1" in content
        assert "2:0.2" in content
        assert "3:0.4" in content

    def test_numeric_ids_with_translate_block(self):
        nexus = (
            "#NEXUS\n"
            "begin trees;\n"
            "  translate\n"
            "    1 A,\n"
            "    2 B,\n"
            "    3 C;\n"
            "  tree T = ((1:0.1,2:0.2):0.3,3:0.4);\n"
            "end;\n"
        )
        s = FigTreeStyler()
        s.load_content(nexus)
        out = s._resolve_annotations_copy()
        # The numeric IDs are correctly restored (not the translate names A/B/C)
        assert "1:0.1" in out
        assert "2:0.2" in out
        assert "3:0.4" in out
        # The translate names must NOT leak into the tree topology
        assert "A:0.1" not in out
        assert "(A:0.1" not in out


# ===========================================================================
# FASTA/FASTQ 校验不得触发 DeprecationWarning
# ===========================================================================

class TestNoDeprecationWarning:
    """deep_validate_fasta / deep_validate_fastq must use the non-deprecated
    scanner and must not trigger a DeprecationWarning."""

    def test_fasta_no_deprecation_warning(self, tmp_path):
        fasta = tmp_path / "seqs.fasta"
        fasta.write_text(">seq1\nACGTACGT\n>seq2\nACGTACGT\n")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            res = deep_validate_fasta(str(fasta))
        deprecations = [w for w in caught
                        if issubclass(w.category, DeprecationWarning)]
        assert not deprecations, (
            "deep_validate_fasta emitted DeprecationWarning(s): "
            + str([str(w.message) for w in deprecations])
        )
        assert isinstance(res, dict)

    def test_fastq_no_deprecation_warning(self, tmp_path):
        fastq = tmp_path / "reads.fastq"
        fastq.write_text(
            "@read1\nACGTACGT\n+\n!!!!!!!!\n"
            "@read2\nACGTACGT\n+\n!!!!!!!!\n"
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            res = deep_validate_fastq(str(fastq))
        deprecations = [w for w in caught
                        if issubclass(w.category, DeprecationWarning)]
        assert not deprecations, (
            "deep_validate_fastq emitted DeprecationWarning(s): "
            + str([str(w.message) for w in deprecations])
        )
        assert isinstance(res, dict)

    def test_anomalous_scanner_still_detects(self):
        """Positive control: the non-deprecated scanner still flags anomalies."""
        errs = scan_node_names_for_anomalous(["\x07trojan"])  # 0x07 = bell (control char)
        assert len(errs) >= 1


# ===========================================================================
# hilight 高度须使用 _get_min_tip_height（jebl 约定）
# ===========================================================================

class TestHilightHeight:
    """hilight band height must be computed with the same jebl time-backward
    convention as collapse (RootedTreeUtils.getMinTipHeight)."""

    TREE = "((A:0.5,B:0.3):0.2,(C:0.1,D:0.4):0.1);"

    @staticmethod
    def _independent_min_tip_height(styler, newick, clade_taxa):
        """Recompute FigTree's getMinTipHeight independently from the spec:

            getMinTipHeight(node) = maxHeight - maxTipDepthInSubtree
        where maxHeight is the deepest tip in the whole tree and
        maxTipDepthInSubtree = depth(node) + maxDistToFarthestTipInSubtree.
        """
        tree = styler._parse_tree_with_biopython(newick)
        mrca = styler._find_mrca_clade(tree, clade_taxa)

        def max_tip_depth_from_root(node, depth=0.0):
            is_term = not getattr(node, "clades", None) or not node.clades
            if is_term:
                return depth
            return max(
                max_tip_depth_from_root(ch, depth + (ch.branch_length or 0.0))
                for ch in node.clades
            )

        def max_dist_in_subtree(node, depth=0.0):
            is_term = not getattr(node, "clades", None) or not node.clades
            if is_term:
                return depth
            return max(
                max_dist_in_subtree(ch, depth + (ch.branch_length or 0.0))
                for ch in node.clades
            )

        node_depth = styler._calculate_node_height(tree, mrca)
        max_tip_depth_in_subtree = node_depth + max_dist_in_subtree(mrca)
        max_height = max_tip_depth_from_root(tree.root)
        return round(max(0.0, max_height - max_tip_depth_in_subtree), 10)

    def test_hilight_height_matches_min_tip_height(self, tmp_path):
        s = FigTreeStyler()
        s.load_content(self.TREE)
        s.highlight_clade(["C", "D"], color="#FF0000")
        out_file = tmp_path / "hilight.nex"
        s.export(str(out_file))
        content = out_file.read_text()

        m = re.search(r"!hilight=\{([^}]+)\}", content)
        assert m, "Expected !hilight annotation in exported tree"
        tip_count, height, _color = m.group(1).split(",")
        height = float(height)
        assert int(tip_count) == 2  # {C,D} has 2 terminals

        # (a) matches the shared implementation
        tree = s._parse_tree_with_biopython(s._tree_content)
        mrca = s._find_mrca_clade(tree, ["C", "D"])
        assert height == s._get_min_tip_height(tree, mrca)

        # (b) matches an independent recomputation of the FigTree formula
        expected = self._independent_min_tip_height(s, self.TREE, ["C", "D"])
        assert height == expected

        # (c) it must NOT equal the (wrong) raw depth — proves the fix took effect
        assert height != s._calculate_node_height(tree, mrca)

    def test_collapse_height_uses_min_tip_height(self, tmp_path):
        s = FigTreeStyler()
        s.load_content(self.TREE)
        s.collapse_clade(["A", "B"], label="AB")
        out_file = tmp_path / "collapse.nex"
        s.export(str(out_file))
        content = out_file.read_text()

        m = re.search(r"!collapse=\{([^}]+)\}", content)
        assert m, "Expected !collapse annotation in exported tree"
        _label, height = m.group(1).split(",")
        height = float(height)

        tree = s._parse_tree_with_biopython(s._tree_content)
        mrca = s._find_mrca_clade(tree, ["A", "B"])
        assert height == s._get_min_tip_height(tree, mrca)
        # cross-check against the independent formula
        expected = self._independent_min_tip_height(s, self.TREE, ["A", "B"])
        assert height == expected

    def test_both_paths_use_shared_min_tip_height(self, tmp_path):
        """Both highlight and collapse must resolve their band height through the
        SAME shared method (_get_min_tip_height)."""
        real_impl = FigTreeStyler._get_min_tip_height
        calls = []

        def spy(self, tree, node):
            calls.append((self, tree, node))
            return real_impl(self, tree, node)

        with patch.object(FigTreeStyler, "_get_min_tip_height", spy):
            s1 = FigTreeStyler()
            s1.load_content(self.TREE)
            s1.highlight_clade(["C", "D"], color="#FF0000")
            s1.export(str(tmp_path / "h.nex"))

            s2 = FigTreeStyler()
            s2.load_content(self.TREE)
            s2.collapse_clade(["A", "B"], label="AB")
            s2.export(str(tmp_path / "c.nex"))

        assert len(calls) >= 2


# ===========================================================================
# 分类学表格环依赖检测（有向图）
# ===========================================================================

class TestCircularDeps:
    """detect_taxonomy_circular_deps must (a) find genuine chained cycles and
    (b) not report normal GTDB tables."""

    def test_chained_cycle_detected(self):
        rows = [
            ("rowA", {"domain": "X", "phylum": "Y"}),
            ("rowB", {"domain": "Y", "phylum": "Z"}),
            ("rowC", {"domain": "Z", "phylum": "X"}),
        ]
        res = detect_taxonomy_circular_deps(rows)
        assert res, "Chained cycle X→Y→Z→X should be detected"
        assert any("X" in r and "Y" in r and "Z" in r for r in res)

    def test_normal_gtdb_no_false_positive(self):
        rows = [
            ("t1", {"domain": "Bacteria", "phylum": "Firmicutes"}),
            ("t2", {"domain": "Archaea", "phylum": "Thermoproteota"}),
            ("t3", {"domain": "Bacteria", "phylum": "Actinobacteria"}),
        ]
        assert detect_taxonomy_circular_deps(rows) == []

    def test_symmetric_swap_flagged_as_conservative(self):
        # The implemented directed-graph detector (consistent with its own
        # docstring example d__A;p__B / d__B;p__A) treats a value-level rank
        # swap as a (conservative) circular dependency, so it is reported
        # rather than returning empty.  This test locks that behaviour.
        rows = [
            ("t1", {"genus": "X", "family": "F"}),
            ("t2", {"genus": "F", "family": "X"}),
        ]
        res = detect_taxonomy_circular_deps(rows)
        assert len(res) >= 1


# ===========================================================================
# 注解应用统一引擎
# ===========================================================================

class TestAnnotationMerge:
    """color / font annotations must behave identically whether applied via the
    public _apply_annotations_to_tree path or the full _resolve_annotations_copy
    (export) path."""

    TREE = "((A:1,B:1):1,C:2);"

    def test_color_via_internal_and_export_paths_consistent(self):
        # Path 1: direct _apply_annotations_to_tree
        s1 = FigTreeStyler()
        s1.load_content(self.TREE)
        ann = NodeAnnotation(annotation_type="color", values="#ff0000",
                             target_taxa=["A", "B"])
        tree = s1._parse_tree_with_biopython(s1._tree_content)
        s1._apply_annotations_to_tree(tree, [ann])
        mrca1 = s1._find_mrca_clade(tree, ["A", "B"])
        path1_comment = mrca1.comment

        # Path 2: public set_clade_color + full export resolve
        s2 = FigTreeStyler()
        s2.load_content(self.TREE)
        s2.set_clade_color(["A", "B"], "#ff0000")
        out2 = s2._resolve_annotations_copy()

        assert path1_comment is not None
        assert "!color=#ff0000" in path1_comment
        assert "!color=#ff0000" in out2

    def test_font_annotation_still_works(self):
        s = FigTreeStyler()
        s.load_content(self.TREE)
        s.set_clade_font(["A", "B"], font_name="Arial",
                         font_style=1, font_size=12)
        out = s._resolve_annotations_copy()
        assert "!font=" in out


# ===========================================================================
# node_count 语义
# ===========================================================================

class TestNodeCount:
    """node_count must be the TOTAL node count (leaf + internal)."""

    def test_simple_tree_node_count(self):
        r = deep_validate_newick("((A,B),(C,D));")
        assert r["leaf_count"] == 4
        assert r["node_count"] == 7  # 4 leaves + 3 internal

    def test_larger_tree_node_count(self):
        r = deep_validate_newick("(((A,B),(C,D)),((E,F),(G,H)));")
        assert r["leaf_count"] == 8
        assert r["node_count"] == 15  # 8 leaves + 7 internal

    def test_named_root_node_count_correct(self):
        # With Bio.Phylo-based counting, named internal/root nodes are no
        # longer mis-counted as leaves: 4 true leaves (A,B,C,D) + 3 internal
        # nodes (X, the unnamed (C,D) parent, and root Y) = 7 total.
        r = deep_validate_newick("((A,B)X,(C,D))Y;")
        assert r["leaf_count"] == 4
        assert r["node_count"] == 7


# ===========================================================================
# 可配置 domain 等级名（特殊标识符）
# ===========================================================================

@pytest.fixture
def rank_prefix_restore():
    """Restore the global rank-prefix configuration after each test."""
    original = get_rank_prefixes()
    yield
    set_rank_prefixes(original)


class TestConfigurableDomain:
    """resolve_taxon_group special identifiers (LUCA/LACA/LBCA) must resolve via
    the configurable domain rank name, not a hardcoded 'domain' literal."""

    LABELS = ["SP1_d_Bacteria_p_Firmicutes", "SP2_d_Archaea_p_Thermoproteota"]

    def test_default_config_resolves_special_ids(self, rank_prefix_restore):
        mapper = TaxonomyMapper()
        mapper.parse_labels(self.LABELS)
        assert get_domain_rank_name() == "domain"
        assert len(mapper.resolve_taxon_group(self.LABELS, "LUCA")) == 2
        assert mapper.resolve_taxon_group(self.LABELS, "LBCA") == [
            "SP1_d_Bacteria_p_Firmicutes"
        ]

    def test_after_remap_domain_rank(self, rank_prefix_restore):
        # Remap d -> superkingdom (keep other ranks so parsing still works)
        full = dict(get_rank_prefixes())
        full["d"] = "superkingdom"
        set_rank_prefixes(full)
        assert get_domain_rank_name() == "superkingdom"

        mapper = TaxonomyMapper()
        mapper.parse_labels(self.LABELS)
        # Special identifiers must still resolve correctly after remapping
        assert len(mapper.resolve_taxon_group(self.LABELS, "LUCA")) == 2
        assert mapper.resolve_taxon_group(self.LABELS, "LBCA") == [
            "SP1_d_Bacteria_p_Firmicutes"
        ]


# ===========================================================================
# 含括号路径须当作文件而非内联 Newick 处理
# ===========================================================================

class TestIsMonophyleticPath:
    """is_monophyletic must treat an existing file path (even one containing
    parentheses) as a file, not as inline Newick content."""

    TREE_MONO = (
        "((SP1_d_Bacteria_p_Firmicutes:1,SP2_d_Bacteria_p_Firmicutes:1):1,"
        "(SP3_d_Archaea_p_Thermoproteota:1,SP4_d_Archaea_p_Thermoproteota:1):2);"
    )
    TREE_NONMONO = (
        "((SP1_d_Bacteria_p_Firmicutes:1,SP2_d_Archaea_p_Thermoproteota:1):1,"
        "(SP3_d_Bacteria_p_Firmicutes:1,SP4_d_Archaea_p_Thermoproteota:1):2);"
    )

    def _write_tree_file(self, tmp_path, newick):
        d = tmp_path / "sub(dir)"
        d.mkdir()
        fp = d / "my(tree).tre"
        fp.write_text(newick)
        return str(fp)

    def test_file_path_with_parentheses_monophyletic(self, tmp_path):
        fp = self._write_tree_file(tmp_path, self.TREE_MONO)
        assert is_monophyletic(fp, "Bacteria") is True
        assert is_monophyletic(fp, "Archaea") is True

    def test_file_path_with_parentheses_non_monophyletic(self, tmp_path):
        fp = self._write_tree_file(tmp_path, self.TREE_NONMONO)
        assert is_monophyletic(fp, "Bacteria") is False

    def test_inline_newick_still_works(self):
        assert is_monophyletic(self.TREE_MONO, "Bacteria") is True
        assert is_monophyletic(self.TREE_MONO, "Archaea") is True
        assert is_monophyletic(self.TREE_NONMONO, "Bacteria") is False
