"""Tests for the Library-mode API (figtreekit.__init__) and CLI helpers.

Targets coverage of:
- __init__.py: parse_taxonomy, is_monophyletic, load_tree, cross_validate
- _cli.py: type validators, _parse_collapse_taxa_spec, _coerce_value,
           _color_groups_by_result, setup_logger, _StepTimer, _GracefulTerminator
"""

import logging
import os
import signal
import tempfile
import textwrap
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from figtreekit import (
    FigTreeStyler,
    LayoutType,
    MonophylyError,
    PhyloFormatError,
    ValidationError,
    parse_taxonomy,
    is_monophyletic,
    load_tree,
    cross_validate,
)
from figtreekit._cli import (
    ExitCode,
    _positive_int,
    _non_negative_int,
    _positive_float,
    _non_negative_float,
    _existing_file_or_dir,
    _font_style_int,
    _parse_collapse_taxa_spec,
    _coerce_value,
    _color_groups_by_result,
    _looks_like_taxon,
    _StepTimer,
    _GracefulTerminator,
    _FlushStreamHandler,
    _FigTreeKitFormatter,
    setup_logger,
    create_cli_parser,
)
import argparse


# ── Fixtures ──────────────────────────────────────────────────────────────

SIMPLE_NEWICK = "((A_d__Bacteria_p__Firmicutes:0.1,B_d__Bacteria_p__Firmicutes:0.2):0.3,C_d__Archaea_p__Euryarchaeota:0.4);"

TAXONOMY_NEWICK = (
    "((tax1_d__Bacteria_p__Proteobacteria_c__Gamma_o__Enter_f__Ent_g__Esch,"
    "tax2_d__Bacteria_p__Proteobacteria_c__Gamma_o__Enter_f__Ent_g__Sal):0.1,"
    "(tax3_d__Bacteria_p__Firmicutes_c__Bacilli_o__Lacto_f__Lacto_g__Lacto,"
    "tax4_d__Archaea_p__Euryarchaeota_c__Methano_o__Methano_f__Methano_g__Methano):0.2);"
)


@pytest.fixture
def simple_tree_file(tmp_path):
    """Create a temporary Newick tree file."""
    p = tmp_path / "simple.tre"
    p.write_text(SIMPLE_NEWICK)
    return str(p)


@pytest.fixture
def taxonomy_tree_file(tmp_path):
    """Create a temporary Newick tree with embedded taxonomy."""
    p = tmp_path / "taxonomy.tre"
    p.write_text(TAXONOMY_NEWICK)
    return str(p)


@pytest.fixture
def nexus_tree_file(tmp_path):
    """Create a temporary Nexus tree file."""
    content = textwrap.dedent("""\
        #NEXUS
        BEGIN TAXA;
            DIMENSIONS NTAX=3;
            TAXLABELS A B C;
        END;
        BEGIN TREES;
            TREE tree1 = ((A:0.1,B:0.2):0.3,C:0.4);
        END;
    """)
    p = tmp_path / "tree.nex"
    p.write_text(content)
    return str(p)


@pytest.fixture
def fasta_file(tmp_path):
    """Create a temporary FASTA file matching tree taxa."""
    content = ">A\nACGT\n>B\nACGT\n>C\nACGT\n"
    p = tmp_path / "seqs.fasta"
    p.write_text(content)
    return str(p)


@pytest.fixture
def fasta_file_mismatch(tmp_path):
    """Create a FASTA file with IDs that don't match tree."""
    content = ">X\nACGT\n>Y\nACGT\n"
    p = tmp_path / "seqs_bad.fasta"
    p.write_text(content)
    return str(p)


# ── parse_taxonomy tests ──────────────────────────────────────────────────

class TestParseTaxonomy:
    def test_format_b_basic(self):
        result = parse_taxonomy("d__Bacteria;p__Proteobacteria;c__Gamma")
        assert result.get("domain") == "Bacteria"
        assert result.get("phylum") == "Proteobacteria"

    def test_format_a_embedded(self):
        label = "GCA_001_d__Archaea_p__Euryarchaeota_c__Methano"
        result = parse_taxonomy(label, mode="reverse")
        assert "domain" in result or "phylum" in result

    def test_empty_label(self):
        result = parse_taxonomy("")
        assert result == {} or isinstance(result, dict)

    def test_no_taxonomy(self):
        result = parse_taxonomy("just_a_name_without_taxonomy")
        assert isinstance(result, dict)

    def test_greedy_mode(self):
        result = parse_taxonomy("d__Bacteria;p__Firmicutes", mode="greedy")
        assert isinstance(result, dict)

    def test_segment_mode(self):
        result = parse_taxonomy("d__Bacteria;p__Firmicutes", mode="segment")
        assert isinstance(result, dict)


# ── is_monophyletic tests ─────────────────────────────────────────────────

class TestIsMonophyletic:
    def test_with_styler_instance(self, taxonomy_tree_file):
        """Test is_monophyletic with a FigTreeStyler instance (covers line 119)."""
        styler = FigTreeStyler(taxonomy_tree_file)
        # The embedded format A parser extracts domains with underscore prefix
        result = is_monophyletic(styler, "_Bacteria")
        assert isinstance(result, bool)

    def test_with_file_path(self, taxonomy_tree_file):
        """Test is_monophyletic with a file path (covers lines 121-125)."""
        result = is_monophyletic(taxonomy_tree_file, "_Bacteria")
        assert isinstance(result, bool)

    def test_with_newick_string(self):
        """Test is_monophyletic with inline Newick content (covers lines 127-128)."""
        result = is_monophyletic(TAXONOMY_NEWICK, "_Bacteria")
        assert isinstance(result, bool)

    def test_invalid_tree_type(self):
        """Test TypeError for invalid tree argument (covers line 130-132)."""
        with pytest.raises(TypeError):
            is_monophyletic(12345, "Proteobacteria")

    def test_taxon_not_found(self, taxonomy_tree_file):
        """Test error for non-existent taxon (covers line 136-139)."""
        with pytest.raises((MonophylyError, ValidationError)):
            is_monophyletic(taxonomy_tree_file, "NonExistentPhylum")


# ── load_tree tests ───────────────────────────────────────────────────────

class TestLoadTree:
    def test_load_newick(self, simple_tree_file):
        styler = load_tree(simple_tree_file)
        assert isinstance(styler, FigTreeStyler)

    def test_load_nexus(self, nexus_tree_file):
        styler = load_tree(nexus_tree_file)
        assert isinstance(styler, FigTreeStyler)

    def test_load_nonexistent(self):
        with pytest.raises(PhyloFormatError, match="not found"):
            load_tree("/nonexistent/path/tree.tre")

    def test_load_without_validation(self, simple_tree_file):
        styler = load_tree(simple_tree_file, validate=False)
        assert isinstance(styler, FigTreeStyler)

    def test_load_invalid_content(self, tmp_path):
        p = tmp_path / "bad.tre"
        p.write_text("this is not a tree at all")
        with pytest.raises((ValidationError, PhyloFormatError)):
            load_tree(str(p))

    def test_load_fasta_as_tree(self, fasta_file):
        """Loading a FASTA file as a tree should fail validation."""
        with pytest.raises((ValidationError, PhyloFormatError)):
            load_tree(fasta_file)


# ── cross_validate tests ──────────────────────────────────────────────────

class TestCrossValidate:
    def test_matching(self, simple_tree_file, fasta_file):
        result = cross_validate(simple_tree_file, fasta_file, strict=False)
        assert "valid" in result
        assert "matched" in result
        assert "tree_only" in result
        assert "seq_only" in result

    def test_mismatch_strict(self, simple_tree_file, fasta_file_mismatch):
        with pytest.raises(PhyloFormatError):
            cross_validate(simple_tree_file, fasta_file_mismatch, strict=True)

    def test_mismatch_non_strict(self, simple_tree_file, fasta_file_mismatch):
        result = cross_validate(simple_tree_file, fasta_file_mismatch, strict=False)
        assert result["valid"] is False
        assert len(result["tree_only"]) > 0 or len(result["seq_only"]) > 0

    def test_invalid_tree_path(self, fasta_file):
        with pytest.raises(PhyloFormatError):
            cross_validate("/nonexistent/tree.tre", fasta_file)

    def test_invalid_seq_path(self, simple_tree_file):
        with pytest.raises((PhyloFormatError, FileNotFoundError, OSError)):
            cross_validate(simple_tree_file, "/nonexistent/seqs.fasta")


# ── CLI type validator tests ──────────────────────────────────────────────

class TestCLITypeValidators:
    def test_positive_int_valid(self):
        assert _positive_int("5") == 5
        assert _positive_int("1") == 1

    def test_positive_int_invalid(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _positive_int("0")
        with pytest.raises(argparse.ArgumentTypeError):
            _positive_int("-1")

    def test_non_negative_int_valid(self):
        assert _non_negative_int("0") == 0
        assert _non_negative_int("10") == 10

    def test_non_negative_int_invalid(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _non_negative_int("-1")

    def test_positive_float_valid(self):
        assert _positive_float("1.5") == 1.5
        assert _positive_float("0.1") == 0.1

    def test_positive_float_invalid(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _positive_float("0")
        with pytest.raises(argparse.ArgumentTypeError):
            _positive_float("-0.5")

    def test_non_negative_float_valid(self):
        assert _non_negative_float("0") == 0.0
        assert _non_negative_float("2.5") == 2.5

    def test_non_negative_float_invalid(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _non_negative_float("-0.1")

    def test_existing_file_or_dir_valid(self, tmp_path):
        assert _existing_file_or_dir(str(tmp_path)) == str(tmp_path)

    def test_existing_file_or_dir_invalid(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _existing_file_or_dir("/nonexistent/path")

    def test_font_style_int_valid(self):
        assert _font_style_int("0") == 0
        assert _font_style_int("1") == 1
        assert _font_style_int("2") == 2
        assert _font_style_int("3") == 3

    def test_font_style_int_invalid(self):
        with pytest.raises(argparse.ArgumentTypeError):
            _font_style_int("4")
        with pytest.raises(argparse.ArgumentTypeError):
            _font_style_int("-1")


# ── _parse_collapse_taxa_spec tests ───────────────────────────────────────

class TestParseCollapseTaxaSpec:
    def test_basic_taxa(self):
        taxa, label, ctype = _parse_collapse_taxa_spec("A,B,C")
        assert taxa == ["A", "B", "C"]
        assert label is None
        assert ctype == "collapse"

    def test_with_label(self):
        taxa, label, ctype = _parse_collapse_taxa_spec("A,B,label=MyClade")
        assert taxa == ["A", "B"]
        assert label == "MyClade"
        assert ctype == "collapse"

    def test_with_type_cartoon(self):
        taxa, label, ctype = _parse_collapse_taxa_spec("A,B,type=cartoon")
        assert taxa == ["A", "B"]
        assert ctype == "cartoon"

    def test_with_label_and_type(self):
        taxa, label, ctype = _parse_collapse_taxa_spec("A,B,label=X,type=cartoon")
        assert taxa == ["A", "B"]
        assert label == "X"
        assert ctype == "cartoon"

    def test_bare_reserved_type(self):
        taxa, label, ctype = _parse_collapse_taxa_spec("A,B,cartoon")
        assert taxa == ["A", "B"]
        assert ctype == "cartoon"

    def test_empty_spec(self):
        with pytest.raises(ValueError, match="empty"):
            _parse_collapse_taxa_spec("")

    def test_no_taxa(self):
        with pytest.raises(ValueError, match="at least one taxon"):
            _parse_collapse_taxa_spec("label=OnlyLabel")

    def test_invalid_type(self):
        with pytest.raises(ValueError, match="invalid type"):
            _parse_collapse_taxa_spec("A,B,type=invalid")

    def test_taxon_named_like_label(self):
        """A taxon named 'my_label' should NOT be treated as a label."""
        taxa, label, ctype = _parse_collapse_taxa_spec("A,my_label")
        assert "my_label" in taxa
        assert label is None


# ── _coerce_value tests ───────────────────────────────────────────────────

class TestCoerceValue:
    def test_bool_true(self):
        assert _coerce_value("true") is True
        assert _coerce_value("True") is True
        assert _coerce_value("TRUE") is True

    def test_bool_false(self):
        assert _coerce_value("false") is False
        assert _coerce_value("False") is False

    def test_null(self):
        assert _coerce_value("null") is None
        assert _coerce_value("none") is None
        assert _coerce_value("None") is None

    def test_int(self):
        assert _coerce_value("42") == 42
        assert _coerce_value("0") == 0
        assert _coerce_value("-5") == -5

    def test_float(self):
        assert _coerce_value("3.14") == 3.14
        assert _coerce_value("1e5") == 100000.0
        assert _coerce_value("2.5E-3") == 0.0025

    def test_quoted_string(self):
        assert _coerce_value('"Arial"') == "Arial"
        assert _coerce_value("'Helvetica'") == "Helvetica"

    def test_plain_string(self):
        assert _coerce_value("Arial") == "Arial"
        assert _coerce_value("#FF0000") == "#FF0000"


# ── _looks_like_taxon tests ───────────────────────────────────────────────

class TestLooksLikeTaxon:
    def test_normal_name(self):
        assert _looks_like_taxon("Escherichia_coli") is True

    def test_quoted_name(self):
        assert _looks_like_taxon('"taxon"') is False
        assert _looks_like_taxon("'taxon'") is False

    def test_comma_name(self):
        assert _looks_like_taxon("A,B") is False


# ── _color_groups_by_result tests ─────────────────────────────────────────

class TestColorGroupsByResult:
    def test_monophyletic_coloring(self, taxonomy_tree_file):
        styler = FigTreeStyler(taxonomy_tree_file)
        result = {
            "monophyletic": {
                "Proteobacteria": {"taxa": ["tax1_d__Bacteria_p__Proteobacteria_c__Gamma_o__Enter_f__Ent_g__Esch",
                                             "tax2_d__Bacteria_p__Proteobacteria_c__Gamma_o__Enter_f__Ent_g__Sal"]},
            },
            "non_monophyletic": {},
        }
        test_logger = logging.getLogger("test_color")
        group_taxa, color_map = _color_groups_by_result("test.tre", styler, result, test_logger)
        assert "Proteobacteria" in group_taxa

    def test_non_monophyletic_coloring(self, taxonomy_tree_file):
        styler = FigTreeStyler(taxonomy_tree_file)
        result = {
            "monophyletic": {},
            "non_monophyletic": {
                "Firmicutes": {"taxa": ["tax3_d__Bacteria_p__Firmicutes_c__Bacilli_o__Lacto_f__Lacto_g__Lacto"]},
            },
        }
        test_logger = logging.getLogger("test_color2")
        group_taxa, color_map = _color_groups_by_result("test.tre", styler, result, test_logger)
        assert "Firmicutes" in group_taxa

    def test_empty_result(self, taxonomy_tree_file):
        styler = FigTreeStyler(taxonomy_tree_file)
        result = {"monophyletic": {}, "non_monophyletic": {}}
        test_logger = logging.getLogger("test_color3")
        group_taxa, color_map = _color_groups_by_result("test.tre", styler, result, test_logger)
        assert group_taxa == {}

    def test_empty_taxa_skipped(self, taxonomy_tree_file):
        styler = FigTreeStyler(taxonomy_tree_file)
        result = {
            "monophyletic": {"EmptyGroup": {"taxa": []}},
            "non_monophyletic": {},
        }
        test_logger = logging.getLogger("test_color4")
        group_taxa, color_map = _color_groups_by_result("test.tre", styler, result, test_logger)
        assert "EmptyGroup" not in group_taxa


# ── setup_logger tests ────────────────────────────────────────────────────

class TestSetupLogger:
    def test_default_level(self):
        log = setup_logger()
        assert log.level == logging.WARNING

    def test_quiet_mode(self):
        log = setup_logger(quiet=True)
        assert log.level == logging.ERROR

    def test_verbose_1(self):
        log = setup_logger(verbose=1)
        assert log.level == logging.INFO

    def test_verbose_2(self):
        log = setup_logger(verbose=2)
        assert log.level == logging.DEBUG

    def test_log_file(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        log = setup_logger(log_file=log_file)
        log.error("test message")
        assert os.path.exists(log_file)
        content = Path(log_file).read_text()
        assert "test message" in content


# ── _StepTimer tests ──────────────────────────────────────────────────────

class TestStepTimer:
    def test_basic_timing(self):
        test_logger = logging.getLogger("test_timer")
        test_logger.setLevel(logging.DEBUG)
        with _StepTimer("test step", test_logger):
            time.sleep(0.01)
        # No exception means success

    def test_fast_step_ms(self):
        test_logger = logging.getLogger("test_timer_fast")
        test_logger.setLevel(logging.DEBUG)
        with _StepTimer("fast step", test_logger):
            pass  # < 1 second → ms format


# ── _GracefulTerminator tests ─────────────────────────────────────────────

class TestGracefulTerminator:
    def test_initial_state(self):
        gt = _GracefulTerminator()
        assert gt.interrupted is False
        assert gt.files_processed == 0
        assert gt.files_total == 0

    def test_track_and_untrack_temp(self, tmp_path):
        gt = _GracefulTerminator()
        temp_file = str(tmp_path / "temp.nex")
        Path(temp_file).write_text("temp")
        gt.track_temp(temp_file)
        assert temp_file in gt._temp_files
        gt.untrack_temp(temp_file)
        assert temp_file not in gt._temp_files

    def test_cleanup_temps(self, tmp_path):
        gt = _GracefulTerminator()
        temp_file = str(tmp_path / "cleanup_test.nex")
        Path(temp_file).write_text("temp")
        gt.track_temp(temp_file)
        gt._cleanup_temps()
        assert not os.path.exists(temp_file)
        assert len(gt._temp_files) == 0

    def test_register_unregister(self):
        gt = _GracefulTerminator()
        gt.register()
        assert signal.SIGINT in gt._original_handlers
        gt.unregister()


# ── _FlushStreamHandler and _FigTreeKitFormatter tests ─────────────────────

class TestLoggingComponents:
    def test_formatter_output(self):
        formatter = _FigTreeKitFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None,
        )
        output = formatter.format(record)
        assert "test message" in output
        assert "[    INFO]" in output
        assert "|" in output

    def test_flush_handler(self):
        import io
        stream = io.StringIO()
        handler = _FlushStreamHandler(stream)
        handler.setFormatter(_FigTreeKitFormatter())
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="flush test", args=(), exc_info=None,
        )
        handler.emit(record)
        assert "flush test" in stream.getvalue()


# ── create_cli_parser tests ───────────────────────────────────────────────

class TestCreateCLIParser:
    def test_parser_creation(self):
        parser = create_cli_parser()
        assert parser is not None

    def test_parse_basic_args(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "-o", "out.nex"])
        assert args.input == simple_tree_file
        assert args.output == "out.nex"

    def test_parse_layout(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--layout", "polar"])
        assert args.layout == "polar"

    def test_parse_set_option(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--set", "tipLabels.fontSize=8"])
        assert "tipLabels.fontSize=8" in args.custom_params

    def test_parse_collapse_taxa(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--collapse-taxa", "A,B,label=X"])
        assert "A,B,label=X" in args.collapse_taxa

    def test_parse_validate_flag(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--validate"])
        assert args.validate is True

    def test_parse_force_flag(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--force"])
        assert args.force is True

    def test_parse_multi_tree(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--multi-tree", "first"])
        assert args.multi_tree == "first"

    def test_parse_render(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--render", "out.png"])
        assert args.render == "out.png"

    def test_parse_taxonomy_levels(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--taxonomy-levels", "d:domain,p:phylum"])
        assert args.taxonomy_levels == "d:domain,p:phylum"

    def test_parse_auto_color(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--auto-color", "phylum"])
        assert args.auto_color == "phylum"

    def test_parse_collapse_rank(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--collapse-rank", "class"])
        assert args.collapse_rank == "class"

    def test_parse_highlight(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--highlight", "A,B:#FF0000"])
        assert "A,B:#FF0000" in args.highlight

    def test_parse_color_clade(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--color-clade", "A,B:#00FF00"])
        assert "A,B:#00FF00" in args.color_clade

    def test_parse_tip_labels(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([simple_tree_file, "--tip-labels-hide"])
        assert args.tip_labels_show is False

    def test_parse_font_options(self, simple_tree_file):
        parser = create_cli_parser()
        args = parser.parse_args([
            simple_tree_file,
            "--font-name", "Arial",
            "--font-size", "12",
            "--font-style", "1",
        ])
        assert args.font_name == "Arial"
        assert args.font_size == 12
        assert args.font_style == 1
