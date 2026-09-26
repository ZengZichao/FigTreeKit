"""Taxonomy-aware collapse: biological-correctness benchmark.

Simulated trees with *known* ground truth cover:

* monophyletic groups        → must collapse;
* paraphyletic groups        → must be refused (intruder taxa reported);
* polyphyletic groups        → must be refused (extra taxa reported);
* polytomy-rooted clades     → monophyly still detectable;
* rooting dependence         → same tip set, different verdict;
* incomplete taxonomy mapping → unmapped tips reported, verdict qualified
  as "monophyletic among mapped sampled tips".
"""

import os
import re
import tempfile

import pytest

from figtreekit import FigTreeStyler
from figtreekit.exceptions import CompatibilityWarning


def _write_mapping(tmp_path, rows):
    path = tmp_path / "mapping.tsv"
    path.write_text("\n".join(f"{t}\t{tax}" for t, tax in rows) + "\n")
    return str(path)


def _export_tree_line(styler):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.nex")
        styler.export(path)
        with open(path) as fh:
            text = fh.read()
    for line in text.splitlines():
        if re.match(r"\s*tree\s+\S+\s*=", line, re.IGNORECASE):
            return line
    raise AssertionError("no tree line")


class TestMonophyleticCollapse:
    TREE = "(((f1:1,f2:1):1,f3:1):1,(o1:1,o2:1):2);"

    def test_monophyletic_detected_and_collapsed(self, tmp_path):
        mapping = _write_mapping(tmp_path, [
            ("f1", "d__Bacteria;p__Firmicutes"),
            ("f2", "d__Bacteria;p__Firmicutes"),
            ("f3", "d__Bacteria;p__Firmicutes"),
            ("o1", "d__Bacteria;p__Otherota"),
            ("o2", "d__Bacteria;p__Otherota"),
        ])
        s = FigTreeStyler().load_content(self.TREE)
        result = s.analyze_taxonomy(
            mapping_file=mapping, rank="phylum", style_monophyletic=False)
        assert "Firmicutes" in result["monophyletic"]
        assert result["summary"]["monophyletic"] == 2

        s2 = FigTreeStyler().load_content(self.TREE)
        s2.collapse_by_group("Firmicutes", mapping_file=mapping, label="Firmi")
        line = _export_tree_line(s2)
        # Collapse is a FigTree display attribute: the label annotation is
        # attached to the clade while the topology stays intact.
        assert "[&!collapse={Firmi" in line


class TestParaphyleticRefusal:
    # f3 sits outside the (f1,f2,o1) clade → Firmicutes is PARAPHYLETIC
    # because the MRCA of {f1,f2,f3} also contains o1 (an intruder).
    TREE = "((f1:1,(f2:1,o1:1):1):1,(f3:1,o2:1):2);"

    def test_paraphyletic_refused_with_intruder_report(self, tmp_path):
        mapping = _write_mapping(tmp_path, [
            ("f1", "d__Bacteria;p__Firmicutes"),
            ("f2", "d__Bacteria;p__Firmicutes"),
            ("f3", "d__Bacteria;p__Firmicutes"),
            ("o1", "d__Bacteria;p__Otherota"),
            ("o2", "d__Bacteria;p__Otherota"),
        ])
        s = FigTreeStyler().load_content(self.TREE)
        result = s.analyze_taxonomy(
            mapping_file=mapping, rank="phylum", style_monophyletic=False)
        assert "Firmicutes" in result["non_monophyletic"]
        issue = result["non_monophyletic"]["Firmicutes"]
        assert "o1" in issue.get("intruder_taxa", [])

        s2 = FigTreeStyler().load_content(self.TREE)
        with pytest.warns(CompatibilityWarning):
            s2.collapse_by_group("Firmicutes", mapping_file=mapping)
        assert len(s2.get_collapses()) == 0  # refusal: nothing registered


class TestPolyphyleticRefusal:
    # Firmicutes members in two separate clades.
    TREE = "((f1:1,o1:1):1,(f2:1,o2:1):1);"

    def test_polyphyletic_refused(self, tmp_path):
        mapping = _write_mapping(tmp_path, [
            ("f1", "d__Bacteria;p__Firmicutes"),
            ("f2", "d__Bacteria;p__Firmicutes"),
            ("o1", "d__Bacteria;p__Otherota"),
            ("o2", "d__Bacteria;p__Otherota"),
        ])
        s = FigTreeStyler().load_content(self.TREE)
        result = s.analyze_taxonomy(
            mapping_file=mapping, rank="phylum", style_monophyletic=False)
        assert "Firmicutes" in result["non_monophyletic"]

        s2 = FigTreeStyler().load_content(self.TREE)
        with pytest.warns(CompatibilityWarning):
            s2.collapse_by_group("Firmicutes", mapping_file=mapping)
        assert len(s2.get_collapses()) == 0


class TestPolytomyMonophyly:
    # Multifurcating root that still contains a genuine subclade {m1,m2}.
    TREE = "((m1:1,m2:1):0,m3:1,out:1);"

    def test_clade_inside_polytomy_detected(self, tmp_path):
        mapping = _write_mapping(tmp_path, [
            ("m1", "d__A;p__Mono"),
            ("m2", "d__A;p__Mono"),
            ("m3", "d__A;p__Other"),
            ("out", "d__B;p__Other"),
        ])
        s = FigTreeStyler().load_content(self.TREE)
        result = s.analyze_taxonomy(
            mapping_file=mapping, rank="phylum", style_monophyletic=False)
        assert "Mono" in result["monophyletic"]


class TestRootingDependence:
    """Monophyly depends on root placement: identical tip set, opposite
    verdicts under two rootings. Callers must therefore provide a rooted
    tree with the intended outgroup."""

    MAPPING_ROWS = [
        ("g1", "d__A;p__G"),
        ("g2", "d__A;p__G"),
        ("out", "d__B;p__O"),
    ]

    def test_rooted_correctly_monophyletic(self, tmp_path):
        mapping = _write_mapping(tmp_path, self.MAPPING_ROWS)
        s = FigTreeStyler().load_content("((g1:1,g2:1):1,out:2);")
        result = s.analyze_taxonomy(
            mapping_file=mapping, rank="phylum", style_monophyletic=False)
        assert "G" in result["monophyletic"]

    def test_misrooted_paraphyletic(self, tmp_path):
        mapping = _write_mapping(tmp_path, self.MAPPING_ROWS)
        s = FigTreeStyler().load_content("(g1:1,(g2:1,out:2):1);")
        result = s.analyze_taxonomy(
            mapping_file=mapping, rank="phylum", style_monophyletic=False)
        assert "G" in result["non_monophyletic"]


class TestIncompleteMapping:
    """With an unmapped tip in the tree, verdicts are qualified as
    'monophyletic among mapped sampled tips' and the unmapped tips are
    surfaced so users can audit completeness."""

    TREE = "((f1:1,mystery:1):1,f2:1);"

    def test_unmapped_tip_reported(self, tmp_path):
        mapping = _write_mapping(tmp_path, [
            ("f1", "d__A;p__Firmi"),
            ("f2", "d__A;p__Firmi"),
            ("o1", "d__A;p__Other"),
        ])
        s = FigTreeStyler().load_content(self.TREE)
        result = s.analyze_taxonomy(
            mapping_file=mapping, rank="phylum", style_monophyletic=False)
        assert "mystery" in result["unmapped"]
        # With the unmapped tip nested INSIDE the MRCA of the mapped
        # members, FigTreeKit conservatively treats it as an intruder and
        # refuses the collapse — exactly the safe behaviour required when
        # taxonomy mapping is incomplete.
        assert "Firmi" in result["non_monophyletic"]
        issue = result["non_monophyletic"]["Firmi"]
        assert "mystery" in issue.get("intruder_taxa", [])

    def test_unmapped_tip_outside_mrca_verdict_qualified(self, tmp_path):
        # When the unmapped tip sits OUTSIDE the group's MRCA the verdict
        # is 'monophyletic among mapped sampled tips'; the completeness
        # audit is what tells the user the qualification applies.
        mapping = _write_mapping(tmp_path, [
            ("f1", "d__A;p__Firmi"),
            ("f2", "d__A;p__Firmi"),
            ("o1", "d__A;p__Other"),
        ])
        tree = "(((f1:1,f2:1):1,o1:1):1,mystery:2);"
        s = FigTreeStyler().load_content(tree)
        result = s.analyze_taxonomy(
            mapping_file=mapping, rank="phylum", style_monophyletic=False)
        assert "mystery" in result["unmapped"]
        assert "Firmi" in result["monophyletic"]

    def test_completeness_check_flags_missing(self, tmp_path):
        mapping = _write_mapping(tmp_path, [
            ("f1", "d__A;p__Firmi"),
            ("f2", "d__A;p__Firmi"),
            ("o1", "d__A;p__Other"),
        ])
        s = FigTreeStyler().load_content("(((f1:1,f2:1):1,o1:1):1,mystery:2);")
        comp = s.check_taxonomy_completeness(mapping_file=mapping)
        # The completeness report must expose that one tip lacks mapping.
        text = str(comp)
        assert "mystery" in text or comp.get("unmapped") or comp.get("missing")


class TestMonophylyRateAccounting:
    """The monophyly rate must exclude single-taxon groups from both sides.

    Regression for a denominator-only exclusion that reported rates above
    100% on trees with many singleton groups (e.g. the 700-tip LACA test
    tree: 125 groups, 66 singletons, 119 exclusive -> 119/59 = 201.7%).
    """

    def _analyse(self, newick, labels):
        import tempfile, os
        from figtreekit import FigTreeStyler
        with tempfile.TemporaryDirectory() as tmp:
            tree = os.path.join(tmp, "t.nwk")
            with open(tree, "w", encoding="utf-8") as fh:
                fh.write(newick)
            styler = FigTreeStyler(tree)
            mapping = os.path.join(tmp, "map.tsv")
            with open(mapping, "w", encoding="utf-8") as fh:
                fh.write("taxon\ttaxonomy\n")
                for name, tax in labels.items():
                    fh.write(f"{name}\td__Bacteria;p__{tax}\n")
            return styler.analyze_taxonomy(mapping_file=mapping, rank="phylum")["summary"]

    def test_rate_never_exceeds_100(self):
        newick = "((A1,A2)X,B,C,D,E,F)R;"
        labels = {"A1": "Alpha", "A2": "Alpha", "B": "Beta", "C": "Gamma",
                  "D": "Delta", "E": "Epsilon", "F": "Zeta"}
        s = self._analyse(newick, labels)
        assert s["monophyly_rate"] <= 100.0
        assert s["total_groups"] == 6
        assert s["single_taxon_groups"] == 5
        assert s["multi_tip_groups"] == 1
        assert s["monophyly_rate"] == pytest.approx(100.0)

    def test_singleton_and_multi_tip_counts_are_consistent(self):
        newick = "((A1,A2)X,(B1,B2)Y,Z)R;"
        labels = {"A1": "Alpha", "A2": "Alpha", "B1": "Beta", "B2": "Beta",
                  "Z": "Gamma"}
        s = self._analyse(newick, labels)
        assert s["multi_tip_groups"] == 2
        assert s["multi_tip_monophyletic"] == 2
        assert s["monophyly_rate"] == pytest.approx(100.0)
        # raw counts are preserved so nothing is hidden by the rate
        assert s["monophyletic"] == 3
        assert s["single_taxon_groups"] == 1

    def test_rate_is_zero_when_every_group_is_a_singleton(self):
        newick = "(A,B,C)R;"
        labels = {"A": "Alpha", "B": "Beta", "C": "Gamma"}
        s = self._analyse(newick, labels)
        assert s["multi_tip_groups"] == 0
        assert s["monophyly_rate"] == 0.0
