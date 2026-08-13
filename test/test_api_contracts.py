"""Tests targeting uncovered paths in _cli.py and validators.py.

Covers:
- _cli.py: _detect_tree_count, _resolve_tree_indices, _iter_sequence_ids,
           apply_cli_args, _process_single_tree (via subprocess)
- validators.py: format-specific validators (FASTQ, GenBank, EMBL, Phylip,
                 Stockholm, Clustal, PhyloXML), deep_validate_fasta/fastq
"""

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from figtreekit._cli import (
    _detect_tree_count,
    _resolve_tree_indices,
    _UsageError,
    apply_cli_args,
    create_cli_parser,
)
from figtreekit import FigTreeStyler, LayoutType
from figtreekit.validators import (
    validate_input_file,
    deep_validate_newick,
    deep_validate_fasta,
    deep_validate_fastq,
    scan_for_anomalous_content,
    cross_validate_tree_sequence,
    read_text_with_fallback,
    extract_sequence_ids,
)


# ── _detect_tree_count tests ──────────────────────────────────────────────

class TestDetectTreeCount:
    def test_single_newick(self, tmp_path):
        p = tmp_path / "single.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        assert _detect_tree_count(p) == 1

    def test_multi_newick(self, tmp_path):
        p = tmp_path / "multi.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);\n((D:0.1,E:0.2):0.3,F:0.4);")
        assert _detect_tree_count(p) == 2

    def test_nexus_single(self, tmp_path):
        p = tmp_path / "single.nex"
        p.write_text(textwrap.dedent("""\
            #NEXUS
            BEGIN TREES;
                TREE t1 = ((A:0.1,B:0.2):0.3,C:0.4);
            END;
        """))
        assert _detect_tree_count(p) == 1

    def test_nexus_multi(self, tmp_path):
        p = tmp_path / "multi.nex"
        p.write_text(textwrap.dedent("""\
            #NEXUS
            BEGIN TREES;
                TREE t1 = ((A:0.1,B:0.2):0.3,C:0.4);
                TREE t2 = ((D:0.1,E:0.2):0.3,F:0.4);
                TREE t3 = ((G:0.1,H:0.2):0.3,I:0.4);
            END;
        """))
        assert _detect_tree_count(p) == 3

    def test_nonexistent_file(self, tmp_path):
        p = tmp_path / "nonexistent.tre"
        assert _detect_tree_count(p) == -1

    def test_newick_with_bracket_comments(self, tmp_path):
        p = tmp_path / "bracket.tre"
        p.write_text("((A:0.1[&note=has;semicolon],B:0.2):0.3,C:0.4);")
        assert _detect_tree_count(p) == 1

    def test_newick_with_quotes(self, tmp_path):
        p = tmp_path / "quoted.tre"
        p.write_text("(('A;B':0.1,C:0.2):0.3,D:0.4);")
        assert _detect_tree_count(p) == 1


# ── _resolve_tree_indices tests ───────────────────────────────────────────

class TestResolveTreeIndices:
    def test_single_tree(self):
        assert _resolve_tree_indices(None, 1, "test.nex") == [0]

    def test_first_strategy(self):
        assert _resolve_tree_indices("first", 5, "test.nex") == [0]

    def test_last_strategy(self):
        assert _resolve_tree_indices("last", 5, "test.nex") == [4]

    def test_random_strategy_with_seed(self):
        result = _resolve_tree_indices("random", 10, "test.nex", seed=42)
        assert len(result) == 1
        assert 0 <= result[0] < 10
        # Reproducible with same seed
        result2 = _resolve_tree_indices("random", 10, "test.nex", seed=42)
        assert result == result2

    def test_random_strategy_without_seed(self):
        result = _resolve_tree_indices("random", 10, "test.nex")
        assert len(result) == 1
        assert 0 <= result[0] < 10

    def test_all_strategy(self):
        assert _resolve_tree_indices("all", 3, "test.nex") == [0, 1, 2]

    def test_split_strategy(self):
        assert _resolve_tree_indices("split", 4, "test.nex") == [0, 1, 2, 3]

    def test_ask_strategy_raises(self):
        with pytest.raises(_UsageError):
            _resolve_tree_indices("ask", 3, "test.nex")

    def test_none_strategy_multi_raises(self):
        with pytest.raises(_UsageError):
            _resolve_tree_indices(None, 3, "test.nex")


# ── apply_cli_args tests ──────────────────────────────────────────────────

class TestApplyCliArgs:
    def test_apply_layout(self, tmp_path):
        p = tmp_path / "tree.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        styler = FigTreeStyler(str(p))
        parser = create_cli_parser()
        args = parser.parse_args([str(p), "--layout", "polar"])
        result = apply_cli_args(styler, args)
        assert result is styler

    def test_apply_tip_labels_hide(self, tmp_path):
        p = tmp_path / "tree.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        styler = FigTreeStyler(str(p))
        parser = create_cli_parser()
        args = parser.parse_args([str(p), "--tip-labels-hide"])
        result = apply_cli_args(styler, args)
        assert result is styler

    def test_apply_custom_params(self, tmp_path):
        p = tmp_path / "tree.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        styler = FigTreeStyler(str(p))
        parser = create_cli_parser()
        args = parser.parse_args([str(p), "--set", "tipLabels.fontSize=8"])
        result = apply_cli_args(styler, args)
        assert result is styler

    def test_apply_rooted(self, tmp_path):
        p = tmp_path / "tree.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        styler = FigTreeStyler(str(p))
        parser = create_cli_parser()
        args = parser.parse_args([str(p), "--rooted"])
        result = apply_cli_args(styler, args)
        assert result is styler

    def test_apply_unrooted(self, tmp_path):
        p = tmp_path / "tree.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        styler = FigTreeStyler(str(p))
        parser = create_cli_parser()
        args = parser.parse_args([str(p), "--unrooted"])
        result = apply_cli_args(styler, args)
        assert result is styler

    def test_apply_font_options(self, tmp_path):
        p = tmp_path / "tree.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        styler = FigTreeStyler(str(p))
        parser = create_cli_parser()
        args = parser.parse_args([
            str(p), "--font-name", "Arial", "--font-size", "10", "--font-style", "1"
        ])
        result = apply_cli_args(styler, args)
        assert result is styler

    def test_apply_branch_width(self, tmp_path):
        p = tmp_path / "tree.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        styler = FigTreeStyler(str(p))
        parser = create_cli_parser()
        args = parser.parse_args([str(p), "--branch-width", "2.5"])
        result = apply_cli_args(styler, args)
        assert result is styler

    def test_apply_background_color(self, tmp_path):
        p = tmp_path / "tree.tre"
        p.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        styler = FigTreeStyler(str(p))
        parser = create_cli_parser()
        args = parser.parse_args([str(p), "--background-color", "#FAFAFA"])
        result = apply_cli_args(styler, args)
        assert result is styler


# ── CLI subprocess integration tests ─────────────────────────────────────

class TestCLISubprocess:
    """Test CLI via subprocess to cover main() and _process_single_tree."""

    def _run_cli(self, args, cwd=None):
        cmd = [sys.executable, "-m", "figtreekit"] + args
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            cwd=cwd or str(Path(__file__).parent.parent),
        )

    def test_version(self):
        result = self._run_cli(["--version"])
        assert result.returncode == 0
        assert "figtreekit" in result.stdout.lower() or "1.0.0" in result.stdout

    def test_self_test(self):
        result = self._run_cli(["--self-test"])
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_no_input(self):
        result = self._run_cli([])
        assert result.returncode == 2

    def test_nonexistent_input(self):
        result = self._run_cli(["/nonexistent/tree.tre", "-o", "/tmp/out.nex"])
        assert result.returncode in (1, 2, 3)

    def test_basic_export(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = self._run_cli([str(tree_file), "-o", str(out_file), "--force"])
        assert result.returncode == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "#NEXUS" in content
        assert "begin figtree" in content.lower() or "BEGIN FIGTREE" in content

    def test_validate_mode(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        result = self._run_cli([str(tree_file), "--validate"])
        assert result.returncode == 0

    def test_layout_polar(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file), "--layout", "polar", "--force"
        ])
        assert result.returncode == 0
        assert out_file.exists()

    def test_layout_radial(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file), "--layout", "radial", "--force"
        ])
        assert result.returncode == 0

    def test_multi_tree_first(self, tmp_path):
        tree_file = tmp_path / "multi.nex"
        tree_file.write_text(textwrap.dedent("""\
            #NEXUS
            BEGIN TREES;
                TREE t1 = ((A:0.1,B:0.2):0.3,C:0.4);
                TREE t2 = ((D:0.1,E:0.2):0.3,F:0.4);
            END;
        """))
        out_file = tmp_path / "output.nex"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file), "--multi-tree", "first", "--force"
        ])
        assert result.returncode == 0

    def test_multi_tree_no_strategy(self, tmp_path):
        tree_file = tmp_path / "multi.nex"
        tree_file.write_text(textwrap.dedent("""\
            #NEXUS
            BEGIN TREES;
                TREE t1 = ((A:0.1,B:0.2):0.3,C:0.4);
                TREE t2 = ((D:0.1,E:0.2):0.3,F:0.4);
            END;
        """))
        out_file = tmp_path / "output.nex"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file), "--force"
        ])
        assert result.returncode == 2

    def test_set_param(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file),
            "--set", "tipLabels.fontSize=8",
            "--set", "appearance.branchLineWidth=2.0",
            "--force"
        ])
        assert result.returncode == 0

    def test_tip_labels_hide(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file), "--tip-labels-hide", "--force"
        ])
        assert result.returncode == 0

    def test_quiet_mode(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file), "-q", "--force"
        ])
        assert result.returncode == 0

    def test_verbose_mode(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file), "-v", "--force"
        ])
        assert result.returncode == 0

    def test_no_clobber_existing(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        out_file.write_text("existing")
        result = self._run_cli([
            str(tree_file), "-o", str(out_file), "--no-clobber"
        ])
        # --no-clobber should refuse to overwrite (exit 0 with skip or exit 2)
        assert result.returncode in (0, 2)

    def test_batch_directory(self, tmp_path):
        in_dir = tmp_path / "trees"
        in_dir.mkdir()
        (in_dir / "t1.tre").write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        (in_dir / "t2.tre").write_text("((D:0.1,E:0.2):0.3,F:0.4);")
        out_dir = tmp_path / "output"
        result = self._run_cli([str(in_dir), "-o", str(out_dir), "--force"])
        assert result.returncode == 0
        assert out_dir.exists()

    def test_sequences_cross_validation(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        seq_file = tmp_path / "seqs.fasta"
        seq_file.write_text(">A\nACGT\n>B\nACGT\n>C\nACGT\n")
        result = self._run_cli([
            str(tree_file), "--validate", "--sequences", str(seq_file)
        ])
        assert result.returncode == 0

    def test_log_file(self, tmp_path):
        tree_file = tmp_path / "input.tre"
        tree_file.write_text("((A:0.1,B:0.2):0.3,C:0.4);")
        out_file = tmp_path / "output.nex"
        log_file = tmp_path / "run.log"
        result = self._run_cli([
            str(tree_file), "-o", str(out_file),
            "--log-file", str(log_file), "-v", "--force"
        ])
        assert result.returncode == 0
        assert log_file.exists()


# ── validators.py format-specific tests ───────────────────────────────────

class TestFormatValidators:
    def test_validate_fastq_valid(self, tmp_path):
        p = tmp_path / "reads.fastq"
        p.write_text("@read1\nACGT\n+\nIIII\n@read2\nTGCA\n+\nIIII\n")
        result = validate_input_file(str(p))
        assert result["valid"] is True
        assert result["format"] == "fastq"

    def test_validate_fastq_invalid(self, tmp_path):
        p = tmp_path / "bad.fastq"
        p.write_text("not a fastq\nACGT\nX\nIIII\n")
        result = validate_input_file(str(p))
        assert result["valid"] is False

    def test_validate_genbank_valid(self, tmp_path):
        p = tmp_path / "seq.gb"
        p.write_text("LOCUS       test_seq    100 bp    DNA\nORIGIN\n//\n")
        result = validate_input_file(str(p))
        assert result["format"] == "genbank"

    def test_validate_genbank_invalid(self, tmp_path):
        p = tmp_path / "bad.gb"
        p.write_text("NOT A GENBANK FILE\n")
        result = validate_input_file(str(p))
        assert result["valid"] is False

    def test_validate_embl_valid(self, tmp_path):
        p = tmp_path / "seq.embl"
        p.write_text("ID   test_seq; SV 1; linear; DNA; STD; UNC; 100 BP.\nXX\n//\n")
        result = validate_input_file(str(p))
        # EMBL may be detected as genbank or embl depending on content heuristics
        assert result["format"] in ("embl", "genbank")

    def test_validate_phylip_valid(self, tmp_path):
        p = tmp_path / "align.phylip"
        p.write_text(" 3 42\nseq1 ACGTACGTACGT\nseq2 ACGTACGTACGT\nseq3 ACGTACGTACGT\n")
        result = validate_input_file(str(p))
        assert result["format"] == "phylip"

    def test_validate_phylip_invalid(self, tmp_path):
        p = tmp_path / "bad.phylip"
        p.write_text("not_a_number 42\n")
        result = validate_input_file(str(p))
        assert result["valid"] is False

    def test_validate_stockholm_valid(self, tmp_path):
        p = tmp_path / "align.sto"
        p.write_text("# STOCKHOLM 1.0\nseq1 ACGT\nseq2 ACGT\n//\n")
        result = validate_input_file(str(p))
        assert result["format"] == "stockholm"

    def test_validate_stockholm_invalid(self, tmp_path):
        p = tmp_path / "bad.sto"
        p.write_text("NOT STOCKHOLM\n")
        result = validate_input_file(str(p))
        assert result["valid"] is False

    def test_validate_clustal_valid(self, tmp_path):
        p = tmp_path / "align.aln"
        p.write_text("CLUSTAL W (1.83) multiple sequence alignment\n\nseq1 ACGT\nseq2 ACGT\n")
        result = validate_input_file(str(p))
        assert result["format"] == "clustal"

    def test_validate_clustal_invalid(self, tmp_path):
        p = tmp_path / "bad.aln"
        p.write_text("NOT CLUSTAL\n")
        result = validate_input_file(str(p))
        assert result["valid"] is False

    def test_validate_phyloxml_valid(self, tmp_path):
        p = tmp_path / "tree.xml"
        p.write_text('<?xml version="1.0"?>\n<phyloxml>\n<phylogeny>\n</phylogeny>\n</phyloxml>\n')
        result = validate_input_file(str(p))
        assert result["format"] == "phyloxml"

    def test_validate_phyloxml_invalid(self, tmp_path):
        p = tmp_path / "bad.xml"
        p.write_text("<?xml version='1.0'?>\n<not_phyloxml>\n</not_phyloxml>\n")
        result = validate_input_file(str(p))
        assert result["valid"] is False

    def test_validate_fasta_no_header(self, tmp_path):
        p = tmp_path / "bad.fasta"
        p.write_text("ACGTACGT\nno header here\n")
        result = validate_input_file(str(p))
        assert result["valid"] is False

    def test_validate_empty_newick(self, tmp_path):
        p = tmp_path / "empty.tre"
        p.write_text("")
        result = validate_input_file(str(p))
        assert result["valid"] is False

    def test_validate_nexus_no_trees_block(self, tmp_path):
        p = tmp_path / "no_trees.nex"
        p.write_text("#NEXUS\nBEGIN DATA;\nEND;\n")
        result = validate_input_file(str(p))
        # Should have warning about missing trees block
        assert len(result.get("warnings", [])) > 0 or result["valid"] is True


# ── deep_validate_fasta tests ─────────────────────────────────────────────

class TestDeepValidateFasta:
    def test_valid_dna(self, tmp_path):
        p = tmp_path / "dna.fasta"
        p.write_text(">seq1\nACGTACGT\n>seq2\nTGCATGCA\n")
        result = deep_validate_fasta(str(p), expected_alphabet="DNA")
        assert not result["errors"]

    def test_valid_protein(self, tmp_path):
        p = tmp_path / "prot.fasta"
        p.write_text(">seq1\nMVLSPADKTN\n>seq2\nMVHLTPEEK\n")
        result = deep_validate_fasta(str(p), expected_alphabet="protein")
        assert not result["errors"]

    def test_invalid_characters(self, tmp_path):
        p = tmp_path / "bad.fasta"
        p.write_text(">seq1\nACGT123XYZ\n")
        result = deep_validate_fasta(str(p), expected_alphabet="DNA")
        assert result["errors"] or result["invalid_chars"]

    def test_auto_detect_alphabet(self, tmp_path):
        p = tmp_path / "auto.fasta"
        p.write_text(">seq1\nACGTACGT\n")
        result = deep_validate_fasta(str(p))
        assert not result["errors"]
        assert "DNA" in result.get("alphabet", "")

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.fasta"
        p.write_text("")
        result = deep_validate_fasta(str(p))
        assert result["errors"] or result["sequence_count"] == 0


# ── deep_validate_fastq tests ─────────────────────────────────────────────

class TestDeepValidateFastq:
    def test_valid_fastq(self, tmp_path):
        p = tmp_path / "reads.fastq"
        p.write_text("@read1\nACGT\n+\nIIII\n@read2\nTGCA\n+\nIIII\n")
        result = deep_validate_fastq(str(p))
        assert not result["errors"]

    def test_invalid_fastq_header(self, tmp_path):
        p = tmp_path / "bad.fastq"
        p.write_text("not_a_header\nACGT\n+\nIIII\n")
        result = deep_validate_fastq(str(p))
        assert result["errors"]


# ── scan_for_anomalous_content tests ──────────────────────────────────────

class TestScanAnomalousContent:
    def test_clean_content(self):
        result = scan_for_anomalous_content("((A:0.1,B:0.2):0.3,C:0.4);")
        # Returns empty list when clean
        assert result == []

    def test_control_characters(self):
        result = scan_for_anomalous_content("tree\x00with\x01nulls")
        # Returns non-empty list with issues
        assert len(result) > 0

    def test_bidi_override(self):
        result = scan_for_anomalous_content("tree\u202ewith\u202abidi")
        assert len(result) > 0

    def test_normal_unicode(self):
        result = scan_for_anomalous_content("tree_with_émojis_ñ")
        assert result == []


# ── cross_validate_tree_sequence tests ────────────────────────────────────

class TestCrossValidateTreeSequence:
    def test_perfect_match(self):
        result = cross_validate_tree_sequence(["A", "B", "C"], ["A", "B", "C"])
        assert result["matched"] == 3
        assert not result.get("errors")

    def test_tree_only(self):
        result = cross_validate_tree_sequence(["A", "B", "C"], ["A", "B"])
        assert "C" in result.get("only_in_tree", [])

    def test_seq_only(self):
        result = cross_validate_tree_sequence(["A", "B"], ["A", "B", "X"])
        assert "X" in result.get("only_in_sequences", [])

    def test_empty_inputs(self):
        result = cross_validate_tree_sequence([], [])
        assert result["matched"] == 0


# ── read_text_with_fallback tests ─────────────────────────────────────────

class TestReadTextWithFallback:
    def test_utf8_file(self, tmp_path):
        p = tmp_path / "utf8.txt"
        p.write_text("hello world", encoding="utf-8")
        content, warnings = read_text_with_fallback(str(p))
        assert content == "hello world"
        assert warnings == []

    def test_latin1_file(self, tmp_path):
        p = tmp_path / "latin1.txt"
        p.write_bytes(b"caf\xe9")
        content, warnings = read_text_with_fallback(str(p))
        assert "caf" in content
        assert len(warnings) > 0  # Should warn about fallback

    def test_bom_file(self, tmp_path):
        p = tmp_path / "bom.txt"
        p.write_bytes(b"\xef\xbb\xbfhello")
        content, warnings = read_text_with_fallback(str(p))
        assert "hello" in content


# ── extract_sequence_ids tests ────────────────────────────────────────────

class TestExtractSequenceIds:
    def test_fasta_ids(self, tmp_path):
        p = tmp_path / "seqs.fasta"
        p.write_text(">seq1 desc\nACGT\n>seq2\nTGCA\n")
        ids = list(extract_sequence_ids(str(p)))
        assert "seq1" in ids
        assert "seq2" in ids

    def test_fastq_ids(self, tmp_path):
        p = tmp_path / "reads.fastq"
        p.write_text("@read1\nACGT\n+\nIIII\n@read2\nTGCA\n+\nIIII\n")
        ids = list(extract_sequence_ids(str(p)))
        assert "read1" in ids
        assert "read2" in ids
