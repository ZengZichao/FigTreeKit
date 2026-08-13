"""Golden conformance corpus for FigTreeKit.

This module complements statement-coverage testing with *behavioural*
conformance checks:

* annotation strings follow the exact FigTree 1.4.4 serialization format;
* topology, tip set and branch lengths survive styling round-trips;
* BEAST translate blocks are preserved (IDs, not names, in output);
* bracket-comment preservation is verified per attachment position
  (the position support matrix reported in Supplementary Section S1);
* node-depth semantics are pinned on a non-ultrametric tree;
* (optionally) the bundled patched FigTree JAR accepts the annotated
  Nexus and produces valid PNG/PDF output.
"""

import os
import re
import shutil
import subprocess
import tempfile
import warnings
from io import StringIO
from pathlib import Path

import pytest
from Bio import Phylo

from figtreekit import FigTreeStyler
from figtreekit._parser import strip_square_bracket_comments
from figtreekit.exceptions import CompatibilityWarning


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _export_text(styler: FigTreeStyler) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out.nex")
        styler.export(path)
        with open(path) as fh:
            return fh.read()


def _tree_line(nexus_text: str) -> str:
    for line in nexus_text.splitlines():
        if re.match(r"\s*tree\s+\S+\s*=", line, re.IGNORECASE):
            return line
    raise AssertionError("no tree declaration in exported Nexus")


def _newick_from_export(nexus_text: str) -> str:
    """Return the Newick value of the first tree, annotations stripped."""
    line = _tree_line(nexus_text)
    value = re.sub(r"^\s*tree\s+\S+\s*=\s*", "", line, flags=re.IGNORECASE)
    value = value.strip().rstrip(";")
    return strip_square_bracket_comments(value)


def _tip_set(newick: str) -> set:
    tree = Phylo.read(StringIO(newick), "newick")
    return {t.name for t in tree.get_terminals()}


def _splits(newick: str) -> set:
    """Bipartition representation of a tree (tip-name frozensets)."""
    tree = Phylo.read(StringIO(newick), "newick")
    return frozenset(
        frozenset(t.name for t in clade.get_terminals())
        for clade in tree.find_clades()
    )


def _branch_lengths(newick: str) -> dict:
    tree = Phylo.read(StringIO(newick), "newick")
    lengths = {}
    for clade in tree.find_clades():
        if clade.name:
            lengths[clade.name] = clade.branch_length
    return lengths


# ---------------------------------------------------------------------------
# 1. Golden annotation formats (FigTree 1.4.4 serialization)
# ---------------------------------------------------------------------------

class TestAnnotationFormatGolden:
    TREE = "((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);"

    def test_color_annotation_lowercase_hex_unquoted(self):
        s = FigTreeStyler().load_content(self.TREE)
        s.set_clade_color(["A", "B"], "#FF0000")
        out = _export_text(s)
        assert "[&!color=#ff0000]" in out

    def test_hilight_annotation_three_parameter_format(self):
        s = FigTreeStyler().load_content(self.TREE)
        s.highlight_clade(["C", "D"], color="#00ff00")
        out = _export_text(s)
        m = re.search(r"\[&!hilight=\{(\d+),([\d.]+),#00ff00\}\]", out)
        assert m is not None, out
        assert m.group(1) == "2"  # tip count of the clade

    def test_font_annotation_java_font_decode_format(self):
        s = FigTreeStyler().load_content(self.TREE)
        s.set_clade_font(["A", "B"], font_name="Arial", font_style=1, font_size=14)
        out = _export_text(s)
        # Java Font.decode() format: Name-STYLE-size (quotes optional —
        # FigTree's Nexus tokenizer accepts the unquoted token).
        assert re.search(r'\[&!font="?Arial-BOLD-14"?\]', out), out

    def test_stroke_written_but_warns(self):
        s = FigTreeStyler().load_content(self.TREE)
        with pytest.warns(CompatibilityWarning, match="silently ignored"):
            s.set_clade_stroke(["A", "B"], stroke_width=2.0)
        out = _export_text(s)
        assert "[&!stroke=2]" in out

    def test_integer_float_serialized_without_decimal(self):
        # Prevents Java Integer.parseInt("1.0") ClassCastException.
        from figtreekit._serializer import serialize_value
        assert serialize_value(1.0) == "1"
        assert serialize_value(2.5) == "2.5"
        assert serialize_value(True) == "true"


# ---------------------------------------------------------------------------
# 2. Topology / branch-length preservation round-trips
# ---------------------------------------------------------------------------

class TestTopologyPreservation:
    TREE = "((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6,(E:0.7,F:0.8):0.9);"

    def _round_trip(self, style):
        input_newick = strip_square_bracket_comments(self.TREE)
        s = FigTreeStyler().load_content(self.TREE)
        style(s)
        out_newick = _newick_from_export(_export_text(s))
        return input_newick, out_newick

    def test_color_round_trip_preserves_topology(self):
        inp, out = self._round_trip(lambda s: s.set_clade_color(["A", "B"], "#123456"))
        assert _tip_set(inp) == _tip_set(out)
        assert _splits(inp) == _splits(out)

    def test_highlight_round_trip_preserves_branch_lengths(self):
        inp, out = self._round_trip(lambda s: s.highlight_clade(["C", "D"]))
        lin, lout = _branch_lengths(inp), _branch_lengths(out)
        assert set(lin) == set(lout)
        max_err = max(abs(lin[k] - lout[k]) for k in lin)
        assert max_err < 1e-6

    def test_collapse_is_display_attribute_topology_unchanged(self):
        """FigTree's collapse is a *display* attribute: the underlying
        topology is preserved (all tips remain) and FigTree draws a
        triangle for the collapsed clade.  This is the correct FigTree
        semantics and is what makes the export lossless."""
        s = FigTreeStyler().load_content(self.TREE)
        s.collapse_clade(["A", "B"], label="clade_AB")
        out = _newick_from_export(_export_text(s))
        tips = _tip_set(out)
        assert tips == {"A", "B", "C", "D", "E", "F"}
        raw = _tree_line(_export_text(s))
        assert "[&!collapse={clade_AB" in raw


# ---------------------------------------------------------------------------
# 3. Bracket-comment preservation — position support matrix (S1.5)
#
# Since Biopython >= 1.80 round-trips bracket comments through
# ``Clade.comment``, FigTreeKit preserves comments at every node-level
# position (tip, internal node, branch-length attached) and merges newly
# injected FigTree attributes into the existing comment.
# ---------------------------------------------------------------------------

class TestCommentPositionMatrix:
    def test_tip_attached_comment_preserved(self):
        s = FigTreeStyler().load_content(
            "((A[&posterior=0.95]:0.1,B:0.2):0.3,C:0.4);")
        s.set_clade_color(["A", "B"], "#00ff00")
        out = _tree_line(_export_text(s))
        assert "[&posterior=0.95]" in out

    def test_internal_node_comment_preserved_and_merged(self):
        s = FigTreeStyler().load_content(
            "((A:0.1,B:0.2)[&support=90]:0.3,C:0.4);")
        s.set_clade_color(["A", "B"], "#00ff00")
        with warnings.catch_warnings():
            warnings.simplefilter("error", CompatibilityWarning)
            out = _tree_line(_export_text(s))
        # Original metadata and injected attribute coexist in one comment.
        assert "&support=90" in out
        assert "!color=#00ff00" in out

    def test_branch_length_comment_preserved(self):
        s = FigTreeStyler().load_content(
            "((A:0.1[&note=x],B:0.2):0.3,C:0.4);")
        s.set_clade_color(["A", "B"], "#00ff00")
        out = _tree_line(_export_text(s))
        assert "[&note=x]" in out

    def test_root_attribute_preserved(self):
        s = FigTreeStyler().load_content(
            "[&R] ((A:0.1,B:0.2):0.3,C:0.4);")
        s.set_clade_color(["A", "B"], "#00ff00")
        out = _tree_line(_export_text(s))
        assert "[&R]" in out


# ---------------------------------------------------------------------------
# 4. BEAST translate-block round-trip
# ---------------------------------------------------------------------------

class TestTranslateRoundTrip:
    NEXUS = """#NEXUS
begin taxa;
    dimensions ntax=3;
    taxlabels 1 2 3;
end;
begin trees;
    translate
        1 'Taxon, one',
        2 Taxon2,
        3 Taxon3;
    tree TREE1 = ((1:0.1,2:0.2):0.3,3:0.4);
end;
"""

    def test_translate_mapping_parsed(self):
        s = FigTreeStyler().load_content(self.NEXUS)
        mapping = s._parse_translate_block()
        assert mapping == {"Taxon, one": "1", "Taxon2": "2", "Taxon3": "3"}

    def test_export_keeps_translate_ids_and_block(self):
        s = FigTreeStyler().load_content(self.NEXUS)
        # Annotation targets use the translate IDs (the names the parsed
        # tree actually carries); the mapping above documents the
        # ID↔name correspondence.
        s.set_clade_color(["1", "2"], "#0000ff")
        out = _export_text(s)
        assert "translate" in out.lower()
        line = _tree_line(out)
        # Output tree must reference translate IDs, not the full names.
        assert "Taxon2" not in line
        assert "[&!color=#0000ff]" in line
        # The translate mapping itself must survive verbatim (names kept).
        assert "'Taxon, one'" in out

    def test_escaped_quotes_in_translate(self):
        block = "translate\n1 'It''s taxon',\n2 Other;\n"
        s = FigTreeStyler().load_content(
            "#NEXUS\nbegin taxa;\ndimensions ntax=2;\ntaxlabels 1 2;\nend;\n"
            "begin trees;\n" + block +
            "tree T1 = (1:0.1,2:0.2);\nend;\n")
        mapping = s._parse_translate_block()
        assert mapping == {"It's taxon": "1", "Other": "2"}

    def test_double_quoted_names_with_comma(self):
        block = 'translate\n1 "Homo sapiens, lineage A",\n2 B;\n'
        s = FigTreeStyler().load_content(
            "#NEXUS\nbegin taxa;\ndimensions ntax=2;\ntaxlabels 1 2;\nend;\n"
            "begin trees;\n" + block +
            "tree T1 = (1:0.1,2:0.2);\nend;\n")
        mapping = s._parse_translate_block()
        assert mapping["Homo sapiens, lineage A"] == "1"


# ---------------------------------------------------------------------------
# 5. Node-depth semantics pinned on a non-ultrametric tree
# ---------------------------------------------------------------------------

class TestNonUltrametricNodeHeight:
    TREE = "((A:0.5,B:0.1):0.2,C:2.0);"

    def test_calculate_node_height_is_root_to_node_depth(self):
        """``_calculate_node_height`` returns the cumulative root-to-node
        branch length (depth), NOT the number of edges to the farthest tip.
        On this non-ultrametric tree the two notions differ: depth of
        MRCA(A,B) is 0.2 while its edge-distance to the farthest tip is 1.
        """
        s = FigTreeStyler().load_content(self.TREE)
        tree = s._parse_tree_with_biopython(self.TREE)
        mrca_ab = tree.common_ancestor("A", "B")
        depth = s._calculate_node_height(tree, mrca_ab)
        assert abs(depth - 0.2) < 1e-9
        tip_a = next(t for t in tree.get_terminals() if t.name == "A")
        assert abs(s._calculate_node_height(tree, tip_a) - 0.7) < 1e-9

    def test_tip_height_uses_farthest_tip_distance(self):
        """``_get_min_tip_height`` implements jebl's time-backward height,
        which does depend on the farthest tip — the semantic distinction
        required by polar/radial collapsed-clade triangles."""
        s = FigTreeStyler().load_content(self.TREE)
        tree = s._parse_tree_with_biopython(self.TREE)
        mrca_ab = tree.common_ancestor("A", "B")
        h = s._get_min_tip_height(tree, mrca_ab)
        # maxHeight = 2.0 (tip C); depth(MRCA) = 0.2; farthest tip in the
        # clade is A at depth 0.7 → height = 2.0 - 0.7 = 1.3
        assert abs(h - 1.3) < 1e-9


# ---------------------------------------------------------------------------
# 6. Multi-tree replacement semantics (scanner-based)
# ---------------------------------------------------------------------------

class TestMultiTreeReplacementConformance:
    NEXUS_TEMPLATE = (
        "#NEXUS\nbegin taxa;\ndimensions ntax=3;\ntaxlabels A B C;\nend;\n"
        "begin trees;\n{trees}\nend;\n"
    )

    def _three_tree_nexus(self):
        trees = (
            "tree T1 = [&lnP=-100] (A:0.1,B:0.1,C:0.1);\n"
            "tree 'T;2' = (A:0.2,B:0.2,C:0.2);\n"
            "tree T3[[nested;[deep]]] = (A:0.3,B:0.3,C:0.3);\n"
        )
        return self.NEXUS_TEMPLATE.format(trees=trees)

    def test_replace_middle_tree_keeps_others(self):
        s = FigTreeStyler(tree_index=1).load_content(self._three_tree_nexus())
        s.set_clade_color(["A", "B"], "#ff0000")
        out = _export_text(s)
        assert out.count("tree ") >= 3
        assert "[&lnP=-100]" in out  # tree 1 untouched
        assert "[&!color=#ff0000]" in out

    def test_quoted_tree_name_with_semicolon(self):
        from figtreekit._parser import find_tree_declaration_spans
        spans = find_tree_declaration_spans(
            "tree 'T;2' = (A:0.2,B:0.2);\ntree T3 = (A:0.3,B:0.3);")
        assert len(spans) == 2


# ---------------------------------------------------------------------------
# 7. Rendering acceptance with the bundled patched FigTree JAR
# ---------------------------------------------------------------------------

def _jar_path() -> Path:
    import figtreekit
    return Path(figtreekit.__file__).parent / "figtree_patched.jar"


_HAVE_JAVA = shutil.which("java") is not None and _jar_path().exists()


@pytest.mark.skipif(not _HAVE_JAVA, reason="java or patched JAR unavailable")
class TestRenderAcceptance:
    """Stock-FigTree-style acceptance test: the patched JAR (FigTree 1.4.4
    plus one radial-layout fix) must parse the annotated Nexus and produce a
    valid image.  A render failure would indicate non-FigTree-compatible
    annotations."""

    def _styled_file(self, tmp_path):
        s = FigTreeStyler().load_content(
            "((A:0.1,B:0.2):0.3,(C:0.4,D:0.5):0.6);")
        s.set_clade_color(["A", "B"], "#ff0000")
        s.highlight_clade(["C", "D"], color="#00ff00")
        path = tmp_path / "styled.nex"
        s.export(str(path))
        return path

    def test_png_render_accepted(self, tmp_path):
        nex = self._styled_file(tmp_path)
        png = tmp_path / "out.png"
        result = subprocess.run(
            ["java", "-jar", str(_jar_path()), "-graphic", "PNG",
             str(nex), str(png)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr[-500:]
        assert png.exists() and png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_pdf_render_accepted(self, tmp_path):
        nex = self._styled_file(tmp_path)
        pdf = tmp_path / "out.pdf"
        result = subprocess.run(
            ["java", "-jar", str(_jar_path()), "-graphic", "PDF",
             str(nex), str(pdf)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr[-500:]
        assert pdf.exists() and pdf.read_bytes()[:5] == b"%PDF-"

    def test_svg_render_accepted(self, tmp_path):
        nex = self._styled_file(tmp_path)
        svg = tmp_path / "out.svg"
        result = subprocess.run(
            ["java", "-jar", str(_jar_path()), "-graphic", "SVG",
             str(nex), str(svg)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr[-500:]
        assert svg.exists()
        head = svg.read_bytes()[:200]
        assert head.startswith(b"<?xml") or b"<svg" in head
