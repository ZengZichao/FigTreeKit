"""Mock-based tests for the rendering and FigTree-setup modules.

These tests cover the Java/network-dependent paths of ``_renderer.py`` and
``_figtree_setup.py`` without requiring a Java runtime or network access:
subprocess calls, PATH lookups, and JAR discovery are all mocked.
"""

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from figtreekit import RenderError
from figtreekit._renderer import (
    check_java_available,
    find_figtree_jar,
    render_multiple,
    render_with_figtree,
)
from figtreekit import _figtree_setup as fs


# ── _renderer.find_figtree_jar ───────────────────────────────────────────

class TestFindFigtreeJar:
    def test_env_var_wins(self, monkeypatch, tmp_path):
        jar = tmp_path / "figtree.jar"
        jar.write_bytes(b"jar")
        monkeypatch.setenv("FIGTREE_JAR", str(jar))
        assert find_figtree_jar() == str(jar)

    def test_env_var_missing_file_ignored(self, monkeypatch, tmp_path):
        monkeypatch.setenv("FIGTREE_JAR", str(tmp_path / "nope.jar"))
        # falls through to bundled patched JAR shipped with the package
        result = find_figtree_jar()
        assert result is None or result.endswith("figtree_patched.jar")

    def test_bundled_jar_found(self, monkeypatch):
        monkeypatch.delenv("FIGTREE_JAR", raising=False)
        monkeypatch.delenv("FIGTREE_HOME", raising=False)
        monkeypatch.setattr(
            "figtreekit._figtree_setup.get_saved_figtree_path", lambda: None
        )
        result = find_figtree_jar()
        assert result is not None and result.endswith("figtree_patched.jar")

    def test_bundled_patched_jar_shipped(self):
        """The patched JAR must ship inside the installed package."""
        jar = Path(__file__).parent.parent / "figtreekit" / "figtree_patched.jar"
        assert jar.is_file() and jar.stat().st_size > 1_000_000


class TestCheckJavaAvailable:
    def test_true_when_java_on_path(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/java")
        assert check_java_available() is True

    def test_false_when_java_missing(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        assert check_java_available() is False


# ── _renderer.render_with_figtree ────────────────────────────────────────

class TestRenderWithFigtree:
    def test_missing_input_raises_filenotfound(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            render_with_figtree(str(tmp_path / "no.nex"), str(tmp_path / "o.png"))

    def test_java_missing_raises_rendererror(self, monkeypatch, tmp_path):
        src = tmp_path / "in.nex"
        src.write_text("#NEXUS")
        monkeypatch.setattr(
            "figtreekit._renderer.check_java_available", lambda: False
        )
        with pytest.raises(RenderError, match="Java"):
            render_with_figtree(str(src), str(tmp_path / "o.png"))

    def test_jar_missing_raises_rendererror(self, monkeypatch, tmp_path):
        src = tmp_path / "in.nex"
        src.write_text("#NEXUS")
        monkeypatch.setattr(
            "figtreekit._renderer.check_java_available", lambda: True
        )
        monkeypatch.setattr("figtreekit._renderer.find_figtree_jar", lambda: None)
        with pytest.raises(RenderError, match="JAR"):
            render_with_figtree(str(src), str(tmp_path / "o.png"))

    def _patch_prereqs(self, monkeypatch, tmp_path):
        src = tmp_path / "in.nex"
        src.write_text("#NEXUS")
        jar = tmp_path / "figtree.jar"
        jar.write_bytes(b"jar")
        monkeypatch.setattr(
            "figtreekit._renderer.check_java_available", lambda: True
        )
        return src, jar

    def test_success_path(self, monkeypatch, tmp_path):
        src, jar = self._patch_prereqs(monkeypatch, tmp_path)
        out = tmp_path / "o.png"

        def fake_run(cmd, **kw):
            out.write_bytes(b"png")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)
        assert render_with_figtree(str(src), str(out), jar_path=str(jar)) is True

    def test_nonzero_exit_raises(self, monkeypatch, tmp_path):
        src, jar = self._patch_prereqs(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="Error: boom"
            ),
        )
        with pytest.raises(RenderError, match="exited with code 1"):
            render_with_figtree(str(src), str(tmp_path / "o.png"), jar_path=str(jar))

    def test_empty_output_raises(self, monkeypatch, tmp_path):
        src, jar = self._patch_prereqs(monkeypatch, tmp_path)
        out = tmp_path / "o.png"
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: (out.touch(),
                               subprocess.CompletedProcess(cmd, 0, "", ""))[1],
        )
        with pytest.raises(RenderError, match="empty output"):
            render_with_figtree(str(src), str(out), jar_path=str(jar))

    def test_timeout_raises_with_value(self, monkeypatch, tmp_path):
        src, jar = self._patch_prereqs(monkeypatch, tmp_path)

        def fake_run(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 120))

        monkeypatch.setattr("subprocess.run", fake_run)
        with pytest.raises(RenderError, match="300 seconds"):
            render_with_figtree(str(src), str(tmp_path / "o.png"),
                                jar_path=str(jar), timeout=300)

    def test_java_opts_split(self, monkeypatch, tmp_path):
        src, jar = self._patch_prereqs(monkeypatch, tmp_path)
        out = tmp_path / "o.png"
        seen = {}

        def fake_run(cmd, **kw):
            seen["cmd"] = cmd
            out.write_bytes(b"png")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr("subprocess.run", fake_run)
        render_with_figtree(str(src), str(out), jar_path=str(jar),
                            java_opts="-Xmx1g -XX:+UseG1GC")
        assert "-Xmx1g" in seen["cmd"] and "-XX:+UseG1GC" in seen["cmd"]


class TestRenderMultiple:
    def test_aggregates_success_and_failure(self, monkeypatch, tmp_path):
        a = tmp_path / "a.nex"
        b = tmp_path / "b.nex"
        a.write_text("#NEXUS")
        b.write_text("#NEXUS")

        def fake_render(input_file, output_file, fmt, w, h, jar, timeout=120):
            if input_file.endswith("b.nex"):
                raise RenderError("boom")
            Path(output_file).write_bytes(b"img")
            return True

        monkeypatch.setattr("figtreekit._renderer.render_with_figtree", fake_render)
        result = render_multiple([str(a), str(b)], str(tmp_path / "out"),
                                 formats=["PNG"])
        assert len(result["success"]) == 1
        assert len(result["failed"]) == 1
        assert result["failed"][0]["format"] == "PNG"


# ── _figtree_setup checks ────────────────────────────────────────────────

class TestSetupChecks:
    def test_check_java_not_on_path(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        ok, msg = fs.check_java()
        assert ok is False and "not found" in msg

    def test_check_java_version(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/java")
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 0, stdout="", stderr='openjdk version "17.0.1"'
            ),
        )
        ok, msg = fs.check_java()
        assert ok is True and "17" in msg

    def test_check_java_subprocess_error(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/java")
        monkeypatch.setattr(
            "subprocess.run",
            mock.Mock(side_effect=OSError("nope")),
        )
        ok, msg = fs.check_java()
        assert ok is False and "Error" in msg

    def test_check_ant_not_on_path(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        ok, msg = fs.check_ant()
        assert ok is False and "not found" in msg

    def test_check_ant_version(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ant")
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 0, stdout="Apache Ant(TM) version 1.10.12", stderr=""
            ),
        )
        ok, msg = fs.check_ant()
        assert ok is True and "Ant" in msg

    def test_check_figtree_jar_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(fs, "get_saved_figtree_path", lambda: None)
        monkeypatch.setattr(
            fs, "get_figtree_jar_path", lambda: tmp_path / "none" / "figtree.jar"
        )
        ok, msg = fs.check_figtree()
        assert ok is False and "not found" in msg

    def test_check_figtree_java_required(self, monkeypatch, tmp_path):
        jar = tmp_path / "figtree.jar"
        jar.write_bytes(b"jar")
        monkeypatch.setattr(fs, "check_java", lambda: (False, "no java"))
        ok, msg = fs.check_figtree(jar_path=str(jar))
        assert ok is False and "Java required" in msg

    def test_check_figtree_ok(self, monkeypatch, tmp_path):
        jar = tmp_path / "figtree.jar"
        jar.write_bytes(b"jar")
        monkeypatch.setattr(fs, "check_java", lambda: (True, "17"))
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 0, stdout="FigTree version 1.4.4", stderr=""
            ),
        )
        ok, msg = fs.check_figtree(jar_path=str(jar))
        assert ok is True and "1.4.4" in msg

    def test_check_figtree_corrupted_jar(self, monkeypatch, tmp_path):
        jar = tmp_path / "figtree.jar"
        jar.write_bytes(b"jar")
        monkeypatch.setattr(fs, "check_java", lambda: (True, "17"))
        monkeypatch.setattr(
            "subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="???", stderr=""),
        )
        ok, msg = fs.check_figtree(jar_path=str(jar))
        assert ok is False and "corrupted" in msg


class TestSavedPath:
    def test_roundtrip(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        jar = tmp_path / "figtree.jar"
        jar.write_bytes(b"jar")
        fs._save_figtree_path(jar)
        assert fs.get_saved_figtree_path() == jar.resolve()

    def test_missing_config_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        assert fs.get_saved_figtree_path() is None

    def test_stale_path_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        cfg = tmp_path / ".figtreekit"
        cfg.mkdir()
        (cfg / "figtree_path.txt").write_text(str(tmp_path / "gone.jar"))
        assert fs.get_saved_figtree_path() is None


class TestPrintSetupStatus:
    def test_prints_sections(self, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(fs, "check_java", lambda: (True, "17"))
        monkeypatch.setattr(fs, "check_ant", lambda: (False, "no ant"))
        monkeypatch.setattr(fs, "get_saved_figtree_path", lambda: None)
        monkeypatch.setattr(fs, "get_figtree_jar_path",
                            lambda: tmp_path / "none.jar")
        monkeypatch.setattr(fs, "check_figtree", lambda: (False, "missing"))
        fs.print_setup_status()
        out = capsys.readouterr().out
        assert "Java:" in out and "Ant:" in out and "Rendering:" in out


# ── Nested bracket-comment regression (suggestion #17) ───────────────────

class TestNestedBracketTreeDecl:
    def test_tree_decl_with_nested_comment(self):
        from figtreekit._parser import find_tree_declaration_spans
        block = 'tree t1 = [&R] (A[&note=[x;y],meta=1]:0.1,B:0.2);'
        spans = find_tree_declaration_spans(block)
        assert len(spans) == 1
        matched = block[spans[0][0]:spans[0][1]]
        assert matched.rstrip().endswith(";")
        assert "(A[&note=[x;y],meta=1]:0.1,B:0.2);" in matched

    def test_tree_decl_with_semicolon_in_comment(self):
        from figtreekit._parser import find_tree_declaration_spans
        block = 'tree t1 = (A[&c=has;semi]:0.1,B:0.2);'
        spans = find_tree_declaration_spans(block)
        assert len(spans) == 1
        assert block[spans[0][0]:spans[0][1]].rstrip().endswith(");")

    def test_tree_decl_deep_nesting_beyond_regex_limit(self):
        # The legacy regex tolerated only 3 nesting levels; the character
        # scanner handles arbitrary depth.
        from figtreekit._parser import find_tree_declaration_spans
        block = 'tree t1 = (A[&n=[a=[b=[c=[d;e]]]]]]:0.1,B:0.2);\ntree t2 = (C:0.3,D:0.4);'
        spans = find_tree_declaration_spans(block)
        assert len(spans) == 2
        assert block[spans[0][0]:spans[0][1]].endswith("(A[&n=[a=[b=[c=[d;e]]]]]]:0.1,B:0.2);")
        assert block[spans[1][0]:spans[1][1]] == 'tree t2 = (C:0.3,D:0.4);'

    def test_tree_decl_quoted_name_with_semicolon(self):
        from figtreekit._parser import find_tree_declaration_spans
        block = "tree 'STATE_1;[&lnP=-123]' = (A:0.1,B:0.2);"
        spans = find_tree_declaration_spans(block)
        assert len(spans) == 1
        assert block[spans[0][0]:spans[0][1]].endswith("(A:0.1,B:0.2);")

    def test_strip_unlimited_nesting(self):
        from figtreekit._parser import strip_square_bracket_comments
        assert strip_square_bracket_comments("(A[[[[x]]]]:0.1,B);") == "(A:0.1,B);"
        assert strip_square_bracket_comments("(A:0.1,B);") == "(A:0.1,B);"
