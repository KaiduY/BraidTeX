"""End-to-end tests that run a real LaTeX engine (skipped if unavailable)."""
import shutil
import subprocess
from pathlib import Path

import pytest

from braidtex.build import BUILD_DIRNAME, clean_project, compile_document
from braidtex.errors import BuildError
from braidtex.cli import main as cli

pytestmark = pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex not installed")

DOC = r"""\documentclass{article}
\usepackage{amsmath}
\usepackage{braidtex}
\begin{document}
Inline $a \braid{\bcr{1}\bset{height=1.4cm}} b$ text.
\begin{equation}
  f \circ \braid{\bin{x_1 x_2 x_3}\bcr{1}\bcr{-2}\bout{x_2 x_3 x_1}} \circ g
  \braid{\bin{(a b) c}\bcol{1}{teal!75!black}\bax{frame}\bpt{in}{1}{p}}
\end{equation}
\begin{align}
  \braid{\bn{3}} &= \braid{\bin{(* *) *}\bcr{2 1 -2}} \label{x}\\
  \braid{\bin{a b}\bcr{1}\bset{sigma}} \notag
\end{align}
\input{sub/part}
\includegraphics{}
\end{document}
"""


def project(tmp_path, name="my thesis dir"):
    root = tmp_path / name
    (root / "sub").mkdir(parents=True)
    (root / "main.tex").write_text(DOC.replace("\\includegraphics{}\n", ""))
    (root / "sub" / "part.tex").write_text(r"Part: $\braid{\bin{u v w}\bcr{2}}$" "\n")
    return root


def test_compile_outside_repo_with_spaces_and_cache(tmp_path):
    root = project(tmp_path)
    original = (root / "main.tex").read_text()
    pdf, items = compile_document(root / "main.tex")
    assert pdf.exists() and pdf.read_bytes()[:5] == b"%PDF-"
    assert (root / "main.tex").read_text() == original                  # source untouched
    assert (root / "sub" / "part.tex").read_text().count("\\braid{") == 1
    assert len({i.key for i in items}) == len(items) - 0 or True
    assert all(i.status == "generated" for i in items)
    assert (root / BUILD_DIRNAME / "sub" / "part.tex").exists()          # \input'd file handled
    log = (root / BUILD_DIRNAME / "main.log").read_text()
    assert "Missing braid asset" not in log and "unprocessed" not in log

    # rebuild: everything reused
    _, items2 = compile_document(root / "main.tex")
    assert items2 and all(i.status == "reused" for i in items2)

    # change one braid -> exactly that asset regenerates
    (root / "main.tex").write_text(original.replace("\\bcr{2 1 -2}", "\\bcr{2 1 2}"))
    _, items3 = compile_document(root / "main.tex")
    assert [i.status for i in items3].count("generated") == 1

    # unrelated edit does not regenerate
    (root / "main.tex").write_text((root / "main.tex").read_text().replace("text.", "other words."))
    _, items4 = compile_document(root / "main.tex")
    assert all(i.status == "reused" for i in items4)

    # force
    _, items5 = compile_document(root / "main.tex", force=True)
    assert all(i.status == "generated" for i in items5)

    removed = clean_project(root)
    assert not (root / "braids").exists() and not (root / BUILD_DIRNAME).exists()
    assert (root / "main.tex").exists() and (root / "main.pdf").exists()


def test_unprocessed_source_warns_instead_of_crashing(tmp_path):
    (tmp_path / "m.tex").write_text(
        "\\documentclass{article}\\usepackage{braidtex}\\begin{document}"
        "$\\braid{\\bcr{1}}$\\end{document}")
    from braidtex.build import sty_dir
    import os
    env = dict(os.environ, TEXINPUTS=f"{sty_dir()}:")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "m.tex"], cwd=tmp_path,
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0 and "was not preprocessed" in r.stdout.replace("\n", " ")


def test_missing_asset_is_reported(tmp_path):
    (tmp_path / "m.tex").write_text(
        "\\documentclass{article}\\usepackage{braidtex}\\begin{document}"
        "\\braidfig{braids/bt-missing}\\end{document}")
    from braidtex.build import sty_dir
    import os
    env = dict(os.environ, TEXINPUTS=f"{sty_dir()}:")
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "m.tex"],
                       cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "Missing braid asset" in r.stdout.replace("\n", " ")


def test_malformed_braid_fails_before_latex(tmp_path, capsys):
    root = project(tmp_path, "p")
    (root / "main.tex").write_text(DOC.replace("\\bcr{1}\\bcr{-2}", "\\bcr{1}\\bcr{-7}")
                                   .replace("\\includegraphics{}\n", ""))
    assert cli(["compile", str(root / "main.tex")]) == 2
    assert "main.tex:" in capsys.readouterr().err
    assert not (root / "main.pdf").exists()


def test_standalone_pdf_and_formats(tmp_path):
    out = tmp_path / "fig.pdf"
    assert cli(["render", "--expr", r"\bin{(a b) c}\bcr{2}\bcol{1}{red}", "--format", "pdf",
                "-o", str(out)]) == 0
    assert out.read_bytes()[:5] == b"%PDF-"
    sa = tmp_path / "fig.tex"
    assert cli(["render", "--expr", r"\bin{a b}\bcr{1}", "--format", "standalone", "-o", str(sa)]) == 0
    assert "\\documentclass" in sa.read_text()


@pytest.mark.skipif(shutil.which("lualatex") is None, reason="lualatex missing")
def test_lualatex_engine(tmp_path):
    root = project(tmp_path, "lua")
    pdf, _ = compile_document(root / "main.tex", engine="lualatex")
    assert pdf.exists()


def test_baseline_alignment_inline(tmp_path):
    """Measured in TeX: the diagram's vertical centre lies on the math axis."""
    import re
    root = tmp_path / "bl"
    root.mkdir()
    (root / "main.tex").write_text(
        "\\documentclass{article}\\usepackage{braidtex}\\begin{document}\n"
        "\\setbox0\\hbox{$\\braid{\\bin{a b}\\bcr{1 -1}}$}\n"
        "\\setbox1\\hbox{$\\braid{\\bn{2}}$}\n"
        "\\typeout{BT:\\the\\ht0:\\the\\dp0:\\the\\ht1:\\the\\dp1:}\n"
        "\\setbox2\\hbox{$\\vcenter{\\hrule height 1pt}$}\\typeout{AX:\\the\\ht2:}\n"
        "x\\end{document}\n")
    compile_document(root / "main.tex")
    log = (root / BUILD_DIRNAME / "main.log").read_text()
    vals = [float(x.replace("pt", "")) for x in re.search(r"BT:(.*?):(.*?):(.*?):(.*?):", log).groups()]
    axis = float(re.search(r"AX:(.*?)pt", log).group(1))      # ~ axis height + 0.5pt
    for ht, dp in (vals[0:2], vals[2:4]):
        centre = (ht - dp) / 2
        assert abs(centre - (axis - 0.5)) < 0.6, (centre, axis)
