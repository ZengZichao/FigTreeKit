"""Regression tests for renderer, CLI, and styler fixes."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from figtreekit import FigTreeStyler
from figtreekit._cli import _iter_sequence_ids
from figtreekit._renderer import render_with_figtree
from figtreekit.validators import cross_validate_tree_sequence


class TestRenderWithFigTreeJavaOpts:
    """Verify that java_opts strings are split into separate arguments."""

    def _make_fake_run(self, captured):
        def _fake_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = "Creating PNG\n"
                stderr = ""
            captured["cmd"] = cmd
            return Result
        return _fake_run

    def test_single_java_opt(self):
        captured = {}
        with patch("figtreekit._renderer.shutil.which", return_value="/usr/bin/java"), \
             patch("figtreekit._renderer.os.path.isfile", return_value=True), \
             patch("figtreekit._renderer.os.path.getsize", return_value=100), \
             patch("figtreekit._renderer.subprocess.run", side_effect=self._make_fake_run(captured)):
            render_with_figtree("in.nex", "out.png", jar_path="figtree.jar", java_opts="-Xmx512m")
            cmd = captured["cmd"]
            assert "-Xmx512m" in cmd
            # Must be passed as a single argument, not as two characters.
            assert cmd[cmd.index("-Xmx512m")] == "-Xmx512m"

    def test_multiple_java_opts(self):
        captured = {}
        with patch("figtreekit._renderer.shutil.which", return_value="/usr/bin/java"), \
             patch("figtreekit._renderer.os.path.isfile", return_value=True), \
             patch("figtreekit._renderer.os.path.getsize", return_value=100), \
             patch("figtreekit._renderer.subprocess.run", side_effect=self._make_fake_run(captured)):
            render_with_figtree(
                "in.nex", "out.png", jar_path="figtree.jar",
                java_opts="-Xmx1g -XX:+UseG1GC",
            )
            cmd = captured["cmd"]
            assert "java" in cmd
            assert "-Xmx1g" in cmd
            assert "-XX:+UseG1GC" in cmd
            # Both options must appear before -jar.
            jar_idx = cmd.index("-jar")
            assert cmd.index("-Xmx1g") < jar_idx
            assert cmd.index("-XX:+UseG1GC") < jar_idx


class TestStylerRenderFormat:
    """Verify explicit format is respected and extension auto-detection works."""

    def test_explicit_format_overrides_extension(self):
        with patch("figtreekit._renderer.render_with_figtree") as mock_render:
            styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
            styler.render("tree.pdf", format="PNG")
            # render_with_figtree is called positionally:
            # (nex_file, output_file, format, width, height, jar_path)
            assert mock_render.call_args[0][2] == "PNG"

    def test_extension_auto_detection(self):
        with patch("figtreekit._renderer.render_with_figtree") as mock_render:
            styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
            styler.render("tree.svg")
            assert mock_render.call_args[0][2] == "SVG"

    def test_case_normalization(self):
        with patch("figtreekit._renderer.render_with_figtree") as mock_render:
            styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
            styler.render("tree.png", format="png")
            assert mock_render.call_args[0][2] == "PNG"

    def test_render_rejects_directory_output(self, tmp_path):
        from figtreekit.exceptions import ExportError
        styler = FigTreeStyler().load_content("((A:0.1,B:0.2):0.3,C:0.4);")
        with pytest.raises(ExportError, match="directory"):
            styler.render(str(tmp_path))


class TestIterSequenceIds:
    """Verify lazy sequence ID extraction for low-memory cross-validation."""

    def test_fasta_ids(self, tmp_path):
        f = tmp_path / "seqs.fasta"
        f.write_text(
            ">seq_1 extra info\nACGT\n"
            ">seq_2\nTGCA\n"
            ">seq_3 with space\nAATT\n"
        )
        assert list(_iter_sequence_ids(f)) == ["seq_1", "seq_2", "seq_3"]

    def test_fastq_ids(self, tmp_path):
        f = tmp_path / "reads.fastq"
        f.write_text(
            "@read_1 comment\nACGT\n+\n!!!!\n"
            "@read_2\nTGCA\n+\n!!!!\n"
        )
        assert list(_iter_sequence_ids(f)) == ["read_1", "read_2"]

    def test_unsupported_extension_raises(self, tmp_path):
        f = tmp_path / "seqs.txt"
        f.write_text(">seq_1\nACGT\n")
        with pytest.raises(ValueError, match="unsupported sequence format"):
            list(_iter_sequence_ids(f))


class TestCrossValidateIterable:
    """Verify cross_validate_tree_sequence accepts iterables (e.g. generators)."""

    def test_generator_sequence_ids(self):
        def gen():
            yield "A"
            yield "B"
            yield "C"

        result = cross_validate_tree_sequence(["A", "B", "C"], gen())
        assert result["errors"] == []
        assert result["matched"] == 3

    def test_empty_iterable(self):
        result = cross_validate_tree_sequence(["A", "B"], iter([]))
        assert len(result["errors"]) == 1
        assert result["matched"] == 0


class TestRenderSuccessDetection:
    """Verify render_with_figtree does not rely on a fragile stdout string."""

    def _make_fake_run(self, captured, returncode=0, stdout="", stderr=""):
        def _fake_run(cmd, **kwargs):
            class Result:
                pass
            Result.returncode = returncode
            Result.stdout = stdout
            Result.stderr = stderr
            captured["cmd"] = cmd
            return Result
        return _fake_run

    def test_success_without_creating_stdout_marker(self):
        captured = {}
        with patch("figtreekit._renderer.shutil.which", return_value="/usr/bin/java"), \
             patch("figtreekit._renderer.os.path.isfile", return_value=True), \
             patch("figtreekit._renderer.os.path.getsize", return_value=100), \
             patch("figtreekit._renderer.subprocess.run", side_effect=self._make_fake_run(
                 captured, returncode=0, stdout="Done\n", stderr=""
             )):
            assert render_with_figtree("in.nex", "out.png", jar_path="figtree.jar") is True

    def test_failure_on_nonzero_returncode(self):
        captured = {}
        with patch("figtreekit._renderer.shutil.which", return_value="/usr/bin/java"), \
             patch("figtreekit._renderer.os.path.isfile", return_value=True), \
             patch("figtreekit._renderer.os.path.getsize", return_value=100), \
             patch("figtreekit._renderer.subprocess.run", side_effect=self._make_fake_run(
                 captured, returncode=1, stdout="", stderr="Some error\n"
             )):
            from figtreekit.exceptions import ExportError
            with pytest.raises(ExportError):
                render_with_figtree("in.nex", "out.png", jar_path="figtree.jar")
