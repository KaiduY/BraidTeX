from __future__ import annotations
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("pdflatex"), "pdflatex is not installed")
class LaTeXBuildIntegrationTests(unittest.TestCase):
    def test_expression_cli_emits_transformed_tex_and_asset(self):
        with tempfile.TemporaryDirectory(prefix="BraidTeX expr project ") as tmp:
            project = Path(tmp)
            expression = r"f\circ\braid{\btid{2}}\circ g"
            result = subprocess.run(
                [sys.executable, str(ROOT / "braidtex_cli.py"), "expr", expression,
                 "--asset-dir", "expression assets"],
                cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(r"f\circ\braidasset{expression assets/bt-", result.stdout)
            self.assertEqual(len(list((project / "expression assets").glob("bt-*.tikz"))), 1)

    def test_clean_build_in_project_and_asset_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="BraidTeX project with spaces ") as tmp:
            project = Path(tmp)
            source = project / "thesis sample.tex"
            source.write_text(r"""\documentclass{article}
\usepackage{amsmath}
\begin{document}
\[
 f\circ\braid{\btin{(x_1 x_2) x_3}\btcross{1}\btcross{-2}\btout{x_1 (x_2 x_3)}}\circ g
\]
\end{document}
""", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "braidtex_cli.py"), "build", str(source),
                 "--engine", "pdflatex", "--asset-dir", "generated braid assets"],
                cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout[-5000:])
            self.assertTrue((project / "thesis sample.pdf").exists())
            self.assertTrue((project / "thesis sample.braidtex.tex").exists())
            self.assertIn(r"\braidasset{generated braid assets/bt-", (project / "thesis sample.braidtex.tex").read_text(encoding="utf-8"))
            self.assertIn(r"\braid{", source.read_text(encoding="utf-8"), "the original .tex should remain unchanged")

    def test_includeonly_and_include_paths_are_rewritten(self):
        with tempfile.TemporaryDirectory(prefix="BraidTeX include project ") as tmp:
            project = Path(tmp)
            (project / "chapters").mkdir()
            root_source = project / "main.tex"
            child_source = project / "chapters" / "chapter.tex"
            root_source.write_text(r"""\documentclass{article}
\includeonly{chapters/chapter}
\begin{document}
\include{chapters/chapter}
\end{document}
""", encoding="utf-8")
            child_source.write_text(r"""A chapter braid: $\braid{\btin{a b}\btcross{-1}}$.
""", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "braidtex_cli.py"), "build", str(root_source),
                 "--engine", "pdflatex"],
                cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout[-6000:])
            self.assertTrue((project / "main.pdf").exists())
            transformed_root = (project / "main.braidtex.tex").read_text(encoding="utf-8")
            self.assertIn(r"\includeonly{chapters/chapter.braidtex}", transformed_root)
            self.assertIn(r"\include{chapters/chapter.braidtex}", transformed_root)

    def test_project_local_input_is_transformed_and_compiled(self):
        with tempfile.TemporaryDirectory(prefix="BraidTeX multi-file project ") as tmp:
            project = Path(tmp)
            chapters = project / "chapter files"
            chapters.mkdir()
            root_source = project / "main thesis.tex"
            child_source = chapters / "braid chapter.tex"
            root_source.write_text(r"""\documentclass{article}
\usepackage{amsmath}
\braiddefaults{color=blue!70!black,strand_sep=0.9}
\begin{document}
\input{chapter files/braid chapter}
\end{document}
""", encoding="utf-8")
            child_source.write_text(r"""A braid in a chapter: $f\circ\braid{\btin{(x_1 x_2) x_3}\btcross{1}\btout{x_1 (x_2 x_3)}\btpointx{-0.5}{q}\btannot{1}{1}{marked}}\circ g$.
""", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "braidtex_cli.py"), "build", str(root_source),
                 "--engine", "pdflatex", "--asset-dir", "generated braid assets"],
                cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout[-6000:])
            self.assertTrue((project / "main thesis.pdf").exists())
            self.assertTrue((project / "main thesis.braidtex.tex").exists())
            transformed_child = chapters / "braid chapter.braidtex.tex"
            self.assertTrue(transformed_child.exists())
            transformed_root_text = (project / "main thesis.braidtex.tex").read_text(encoding="utf-8")
            self.assertIn(r"\input{chapter files/braid chapter.braidtex.tex}", transformed_root_text)
            self.assertIn(r"\braidasset{generated braid assets/bt-", transformed_child.read_text(encoding="utf-8"))
            self.assertIn(r"\input{chapter files/braid chapter}", root_source.read_text(encoding="utf-8"))
            self.assertIn(r"\braid{", child_source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
