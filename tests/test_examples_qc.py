"""Quality control over every diagram that ships in the showcase and the manual."""
import re
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from braidtex import build_geometry, count_intersections
from braidtex.geometry import bez_point, max_join_error
from braidtex.transform import Source, _TOKEN, _match, mask, parse_body
from braidtex.style import split_options
from braidtex.errors import BraidTeXError

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "examples" / "showcase" / "showcase.tex", ROOT / "docs" / "manual" / "manual.tex",
         ROOT / "examples" / "minimal" / "main.tex"]


def braids_in(path):
    text = path.read_text()
    m, src = mask(text), Source(text, path.name)
    defaults = {}
    for mt in _TOKEN.finditer(m):
        j = mt.end()
        while m[j].isspace():
            j += 1
        end = _match(m, j, src)
        if mt.group(1) == "setup":
            defaults.update(split_options(m[j + 1:end]))
        elif not mt.group(1):
            yield src.loc(mt.start())[0], parse_body(m, j + 1, end, defaults, src, mt.start())


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_example_braid_is_exact_and_clean(path):
    n = 0
    for line, b in braids_in(path):
        n += 1
        with warnings.catch_warnings():
            warnings.simplefilter("error")                      # any geometry warning fails
            g = build_geometry(b)
        assert count_intersections(g) == b.n_projected_crossings, f"{path.name}:{line}"
        pos, ang = max_join_error(g)
        assert pos < 1e-9 and ang < 1e-9, f"{path.name}:{line}"
        # all path points inside the box, strands strictly ordered at the top and bottom
        assert g.in_x == sorted(g.in_x) and g.out_x == sorted(g.out_x)
        for s in g.strands:
            for seg in s.segments:
                for p in (seg.p0, seg.c1, seg.c2, seg.p3):
                    assert -1e-9 <= p[0] <= g.width + 1e-9 and -1e-9 <= p[1] <= g.height + 1e-9
        # output labels follow the permutation (the Braid constructor validated them; re-check)
        sl, tl = b.source.labels(), b.target.labels()
        assert [sl[k - 1] for k in b.strand_at_output] == tl
        # ribbons: the (full-extent) guides lie strictly outside every ribbon strand
        if g.regions:
            from braidtex import Style
            import dataclasses
            full = build_geometry(b.replace(style=dataclasses.replace(
                b.style, compose="shadow", extent="full")))
            for rg in full.regions:
                ribbon = [t for t in full.strands if t.ident in rg.strands]
                for idx in range(len(rg.left)):
                    for u in (0.0, 0.5, 1.0):
                        left, right = bez_point(rg.left[idx], u), bez_point(rg.right[idx], u)
                        for t in ribbon:
                            p = bez_point(t.segments[idx], u)
                            assert left[0] < p[0] < right[0], f"{path.name}:{line}"
    assert n > 0


def test_manual_tex_is_up_to_date():
    gen = ROOT / "docs" / "manual" / "make_manual.py"
    cur = (ROOT / "docs" / "manual" / "manual.tex").read_text()
    out = subprocess.run([sys.executable, str(gen)], capture_output=True, text=True, cwd=gen.parent)
    assert out.returncode == 0
    assert (ROOT / "docs" / "manual" / "manual.tex").read_text() == cur


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex not installed")
@pytest.mark.parametrize("rel", ["examples/showcase/showcase.tex", "docs/manual/manual.tex"])
def test_showcase_and_manual_compile_cleanly(rel, tmp_path):
    from braidtex.build import compile_document
    proj = tmp_path / "proj dir"
    shutil.copytree(ROOT / Path(rel).parent, proj, ignore=shutil.ignore_patterns(
        "braids", ".braidtex-build", "*.pdf"))
    name = Path(rel).name
    pdf, items = compile_document(proj / name)
    assert pdf.read_bytes()[:5] == b"%PDF-" and items
    log = (proj / ".braidtex-build" / (Path(rel).stem + ".log")).read_text()
    assert "Overfull" not in log and "Missing braid asset" not in log
    assert "LaTeX Warning: Reference" not in log or "undefined" not in log
