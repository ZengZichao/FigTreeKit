"""Regression tests for the JPEG render format: the CLI advertises four output
formats and JPEG previously had support but no test."""

import os
import shutil
import tempfile
import unittest

from figtreekit import FigTreeStyler

SIMPLE = "((A:0.1,B:0.2)C:0.3,D:0.4)E;"


def _write_sample_image(path: str) -> None:
    """Write a small valid JPEG the way the JAR would (FigTree emits RGB)."""
    try:
        from PIL import Image
    except Exception:  # pragma: no cover - Pillow is optional
        with open(path, "wb") as fh:
            fh.write(b"\xff\xd8\xff\xe0" + b"0" * 512)
        return
    Image.new("RGB", (16, 16), (255, 255, 255)).save(path, format="JPEG")


JAR_OK = shutil.which("java") is not None and os.path.exists(
    os.path.join(os.path.dirname(__file__), os.pardir, "figtreekit", "figtree_patched.jar")
)


class TestJpegFormatDeclared(unittest.TestCase):
    def test_cli_accepts_jpeg(self):
        import figtreekit._cli as cli

        parser = cli.create_cli_parser()
        rendered = [a for a in parser._actions if "--render-format" in a.option_strings]
        self.assertTrue(rendered, "--render-format option missing")
        self.assertIn("JPEG", rendered[0].choices)

    def test_format_map_contains_jpeg(self):
        from figtreekit import styler as st

        with open(st.__file__, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("JPEG", text)


class TestJpegRender(unittest.TestCase):
    """End-to-end JPEG render through the bundled patched JAR, plus a mocked
    variant that runs anywhere Java is absent."""

    def _write_inputs(self, tmp):
        tree = os.path.join(tmp, "in.nex")
        with open(tree, "w", encoding="utf-8") as fh:
            fh.write("#NEXUS\nBEGIN TREES;\nTREE 1 = %s\nEND;\n" % SIMPLE)
        return tree

    def test_render_jpeg_mocked(self):
        """A JPEG request must reach the JAR as format=JPEG, not be rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            tree = self._write_inputs(tmp)
            out = os.path.join(tmp, "out.jpg")
            styler = FigTreeStyler(tree)
            captured = {}

            def fake_run(cmd, *a, **kw):
                captured["cmd"] = list(cmd)

                class R:
                    returncode = 0
                    stdout = ""
                    stderr = ""

                # emulate the JAR writing a real, readable image file
                out_path = captured["cmd"][-1]
                _write_sample_image(out_path)
                return R()

            with unittest.mock.patch("subprocess.run", side_effect=fake_run):
                styler.render(out, format="JPEG")
            self.assertTrue(os.path.isfile(out), "no output written")
            self.assertIn("JPEG", captured["cmd"], "JPEG was not passed through to the JAR")

    @unittest.skipUnless(JAR_OK, "java or the patched JAR is unavailable")
    def test_render_jpeg_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = self._write_inputs(tmp)
            out = os.path.join(tmp, "out.jpg")
            FigTreeStyler(tree).render(out, format="JPEG", width=400, height=300)
            self.assertTrue(os.path.isfile(out))
            with open(out, "rb") as fh:
                self.assertEqual(fh.read(3), b"\xff\xd8\xff", "not a JPEG stream")


if __name__ == "__main__":
    unittest.main()
