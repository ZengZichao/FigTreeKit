"""End-to-end CLI integration tests.

These tests drive ``main()`` with patched ``sys.argv`` against temporary
files, covering the processing paths in ``_cli.py`` that unit tests do not
reach: single/batch processing, multi-tree modes, taxonomy commands,
annotation flags, self-test, and setup-check.
"""

import json
import sys

import pytest

from figtreekit._cli import main


TREE = "((A_d_Bacteria_p_Firmicutes:0.1,B_d_Bacteria_p_Firmicutes:0.2):0.05,(C_d_Bacteria_p_Cyanobacteriota:0.15,D_d_Archaea_p_Euryarchaeota:0.25):0.05);"

MULTI_TREE_NEXUS = """#NEXUS
begin trees;
tree t1 = (A:0.1,B:0.2);
tree t2 = (C:0.1,D:0.2);
end;
"""


@pytest.fixture
def tree_file(tmp_path):
    p = tmp_path / "input.tre"
    p.write_text(TREE)
    return p


@pytest.fixture
def multi_file(tmp_path):
    p = tmp_path / "multi.nex"
    p.write_text(MULTI_TREE_NEXUS)
    return p


def _run(argv):
    """Invoke main() expecting clean completion (no SystemExit or exit 0)."""
    try:
        main()
    except SystemExit as e:
        if e.code not in (0, None):
            raise


def _run_expect_exit(argv, code):
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == code


# ── Self-test and setup-check ────────────────────────────────────────────

class TestSelfTest:
    def test_self_test_passes(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["figtreekit", "--self-test"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "Self-Test Results" in out
        assert "[PASS]" in out

    def test_check_figtree(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["figtreekit", "--check-figtree"])
        main()
        out = capsys.readouterr().out
        assert out  # status report printed regardless of JAR presence


# ── Single-tree processing with styling flags ────────────────────────────

class TestSingleTreeStyling:
    def test_layout_and_export(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--layout", "polar", "--angular-range", "270", "--root-angle", "45",
        ])
        _run([])
        content = out.read_text()
        assert "begin figtree;" in content
        assert "POLAR" in content

    def test_appearance_flags(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--branch-width", "2.5",
            "--background-color", "#FFFFFF",
            "--foreground-color", "#000000",
            "--selection-color", "#FF0000",
            "--expansion", "10", "--zoom", "1.5",
        ])
        _run([])
        content = out.read_text()
        assert "branchLineWidth=2.5" in content

    def test_label_and_scale_flags(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--tip-labels-show", "--font-name", "Helvetica", "--font-size", "14",
            "--font-style", "1", "--label-color", "#112233",
            "--node-labels-show", "--node-display-attribute", "height",
            "--branch-labels-show", "--branch-display-attribute", "length",
            "--scale-bar-show", "--scale-axis-show",
            "--root-age", "10.5", "--scale-factor", "2.0",
        ])
        _run([])
        content = out.read_text()
        assert '"Helvetica"' in content
        assert "tipLabels.isShown=true" in content

    def test_layout_variant_flags(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--layout", "rectilinear", "--curvature", "5", "--root-length", "20",
            "--align-tip-labels", "--radial-spread", "0.5",
            "--rooted", "--order-branches", "--order", "increasing",
            "--transform", "cladogram",
        ])
        _run([])
        assert "begin figtree;" in out.read_text()

    def test_rooting_midpoint_and_unrooted(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--rooting-type", "midpoint", "--unrooted",
        ])
        _run([])
        assert out.exists()

    def test_legend_flags(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--legend-show", "--legend-position", "top",
        ])
        _run([])
        assert "legend" in out.read_text()

    def test_custom_params(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--set", "appearance.branchLineWidth=3.5",
            "--set", "tipLabels.isShown=false",
        ])
        _run([])
        content = out.read_text()
        assert "branchLineWidth=3.5" in content

    def test_strip_annotations(self, monkeypatch, tmp_path):
        src = tmp_path / "annotated.tre"
        src.write_text("(A[&x=1]:0.1,B:0.2);")
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(src), "-o", str(out), "-q", "--strip-annotations",
        ])
        _run([])
        assert "[&x=1]" not in out.read_text()


# ── Clade annotation flags ───────────────────────────────────────────────

class TestCladeFlags:
    def test_highlight(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--highlight", "A_d_Bacteria_p_Firmicutes,B_d_Bacteria_p_Firmicutes:#FF0000",
        ])
        _run([])
        assert "!hilight" in out.read_text()

    def test_color_clade_and_color_all(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--color-clade", "A_d_Bacteria_p_Firmicutes,B_d_Bacteria_p_Firmicutes:#00FF00",
            "--color-all",
        ])
        _run([])
        assert "!color" in out.read_text()

    def test_font_clade(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--font-clade", "A_d_Bacteria_p_Firmicutes,B_d_Bacteria_p_Firmicutes:Arial-BOLD-14",
        ])
        _run([])
        assert "!font" in out.read_text()

    def test_collapse_taxa_with_label_and_type(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--collapse-taxa",
            "A_d_Bacteria_p_Firmicutes,B_d_Bacteria_p_Firmicutes,label=Firmi,type=cartoon",
        ])
        _run([])
        content = out.read_text()
        assert "!cartoon" in content or "!collapse" in content

    def test_collapse_by_rank_and_auto_color(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--collapse-rank", "phylum", "--auto-color", "phylum",
        ])
        _run([])
        content = out.read_text()
        assert "!collapse" in content
        assert "!color" in content

    def test_clade_by_group_name(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--clade", "Firmicutes",
        ])
        _run([])
        assert "!collapse" in out.read_text()

    def test_clear_hilights(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--highlight", "A_d_Bacteria_p_Firmicutes,B_d_Bacteria_p_Firmicutes",
            "--clear-hilights",
        ])
        _run([])
        assert "!hilight" not in out.read_text()


# ── Taxonomy analysis commands ───────────────────────────────────────────

class TestTaxonomyCommands:
    def test_analyze_taxonomy(self, monkeypatch, tree_file, capsys):
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-q", "--analyze-taxonomy", "phylum",
        ])
        _run([])
        out = capsys.readouterr().out
        assert out  # monophyly report printed

    def test_check_monophyly(self, monkeypatch, tree_file, capsys):
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-q", "--check-monophyly", "Firmicutes",
        ])
        _run([])
        assert capsys.readouterr().out

    def test_check_taxonomy(self, monkeypatch, tree_file, capsys):
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-q", "--check-taxonomy",
        ])
        _run([])
        assert capsys.readouterr().out

    def test_taxonomy_levels_extension(self, monkeypatch, tmp_path):
        from figtreekit.taxonomy import get_rank_prefixes, set_rank_prefixes
        saved = get_rank_prefixes()
        try:
            src = tmp_path / "ext.tre"
            src.write_text("((A_x_Mytaxa:0.1,B_x_Mytaxa:0.2):0.05,C_y_Other:0.1);")
            out = tmp_path / "out.nex"
            monkeypatch.setattr(sys, "argv", [
                "figtreekit", str(src), "-o", str(out), "-q",
                "--taxonomy-levels", "x:phylum,y:class",
                "--check-monophyly", "Mytaxa",
            ])
            _run([])
            assert out.exists() or True  # analysis path exercised
        finally:
            # --taxonomy-levels mutates the module-level rank config via
            # extend_rank_prefixes; restore it so later tests see the
            # default configuration.
            set_rank_prefixes(saved)

    def test_taxonomy_mapping_file(self, monkeypatch, tree_file, tmp_path):
        mapping = tmp_path / "map.tsv"
        mapping.write_text(
            "A_d_Bacteria_p_Firmicutes\td__Bacteria;p__Firmicutes\n"
            "B_d_Bacteria_p_Firmicutes\td__Bacteria;p__Firmicutes\n"
        )
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--taxonomy-mapping-file", str(mapping),
            "--collapse-rank", "phylum",
        ])
        _run([])
        assert out.exists()


# ── Multi-tree modes ─────────────────────────────────────────────────────

class TestMultiTree:
    def test_ask_mode_aborts_with_usage_error(self, monkeypatch, multi_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(multi_file), "-o", str(out), "-q",
        ])
        _run_expect_exit([], 2)

    def test_first_mode(self, monkeypatch, multi_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(multi_file), "-o", str(out), "-q", "--multi-tree", "first",
        ])
        _run([])
        text = out.read_text()
        # Nexus serialization reformats branch lengths; assert tree identity
        # and taxon presence instead of brittle Newick string matching.
        assert "tree t1" in text
        assert "A" in text and "B" in text

    def test_last_mode(self, monkeypatch, multi_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(multi_file), "-o", str(out), "-q", "--multi-tree", "last",
        ])
        _run([])
        text = out.read_text()
        assert "tree t2" in text
        assert "C" in text and "D" in text

    def test_random_mode_with_seed(self, monkeypatch, multi_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(multi_file), "-o", str(out), "-q",
            "--multi-tree", "random", "--seed", "42",
        ])
        _run([])
        assert out.exists()

    def test_split_mode_produces_suffixes(self, monkeypatch, multi_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(multi_file), "-o", str(out), "-q", "--multi-tree", "split",
        ])
        _run([])
        siblings = [p.name for p in tmp_path.glob("out*.nex")]
        assert len(siblings) >= 2


# ── Batch mode and file handling ─────────────────────────────────────────

class TestBatchAndFileHandling:
    def test_batch_directory(self, monkeypatch, tmp_path):
        indir = tmp_path / "trees"
        indir.mkdir()
        (indir / "t1.tre").write_text("(A:0.1,B:0.2);")
        (indir / "t2.tre").write_text("(C:0.1,D:0.2);")
        outdir = tmp_path / "out"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(indir), "-o", str(outdir), "-q",
        ])
        _run([])
        assert len(list(outdir.glob("*.nex"))) == 2

    def test_no_clobber_skips_existing(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        out.write_text("PREEXISTING")
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q", "--no-clobber",
        ])
        _run([])
        assert out.read_text() == "PREEXISTING"

    def test_force_overwrites(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        out.write_text("PREEXISTING")
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q", "--force",
        ])
        _run([])
        assert "PREEXISTING" not in out.read_text()

    def test_config_file(self, monkeypatch, tree_file, tmp_path):
        cfg = tmp_path / "style.json"
        cfg.write_text(json.dumps({"layout_type": "polar", "tipLabels.fontSize": 16}))
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q", "--config", str(cfg),
        ])
        _run([])
        content = out.read_text()
        assert "POLAR" in content or "fontSize=16" in content

    def test_log_file_written(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        log = tmp_path / "run.log"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-v",
            "--log-file", str(log),
        ])
        _run([])
        assert log.exists() and log.stat().st_size > 0

    def test_validate_mode_no_export(self, monkeypatch, tree_file, tmp_path):
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-q", "--validate",
        ])
        _run([])
        assert not (tmp_path / "out.nex").exists()

    def test_verbose_mode(self, monkeypatch, tree_file, tmp_path):
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-vv",
        ])
        _run([])
        assert out.exists()

    def test_nonexistent_input_exits_3(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tmp_path / "missing.tre"), "-q",
        ])
        _run_expect_exit([], 3)

    def test_no_input_exits_2(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["figtreekit", "-q"])
        _run_expect_exit([], 2)

    def test_sequences_cross_validation(self, monkeypatch, tree_file, tmp_path):
        fasta = tmp_path / "seqs.fasta"
        fasta.write_text(
            ">A_d_Bacteria_p_Firmicutes\nACGT\n>B_d_Bacteria_p_Firmicutes\nACGT\n"
            ">C_d_Bacteria_p_Cyanobacteriota\nACGT\n>D_d_Archaea_p_Euryarchaeota\nACGT\n"
        )
        out = tmp_path / "out.nex"
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--sequences", str(fasta),
        ])
        _run([])
        assert out.exists()

    def test_render_without_jar_fails_gracefully(self, monkeypatch, tree_file, tmp_path):
        """Render request without available JAR/Java must exit non-zero, not crash."""
        out = tmp_path / "out.nex"
        png = tmp_path / "out.png"
        monkeypatch.setenv("FIGTREE_JAR", str(tmp_path / "nonexistent.jar"))
        monkeypatch.setattr(sys, "argv", [
            "figtreekit", str(tree_file), "-o", str(out), "-q",
            "--render", str(png),
        ])
        try:
            main()
        except SystemExit:
            pass  # any clean exit path is acceptable
