import json
import os
from pathlib import Path

import pytest

from braidtex import Braid, Cache, TransformError, cache_key, Style
from braidtex.cli import main as cli
from braidtex.transform import mask, transform_text

BR = r"\braid{\bin{x_1 x_2 x_3}\bcr{1}\bcr{-2}\bout{x_2 x_3 x_1}}"


def tx(text, tmp_path, **kw):
    return transform_text(text, "t.tex", Cache(tmp_path / "braids", **kw), "braids")


def test_replaces_only_braids_and_preserves_surroundings(tmp_path):
    src = "\\[\n  f \\circ " + BR + " \\circ g_{12}^{\\vee} % keep\n\\]\n"
    r = tx(src, tmp_path)
    assert r.text.startswith("\\[\n  f \\circ \\braidfig{braids/bt-")
    assert r.text.endswith("} \\circ g_{12}^{\\vee} % keep\n\\]\n")
    assert len(r.items) == 1 and r.items[0].status == "generated"
    assert Path(r.items[0].path).is_file()


def test_multiple_and_multiline_and_nested_braces(tmp_path):
    src = ("$" + BR + "$ and\n\\braid{\n  \\bin{ \\frac{A}{B} X^{\\otimes 2} }\n  \\bcr{1}\n}\n"
           + BR)
    r = tx(src, tmp_path)
    assert r.text.count("\\braidfig") == 3 and "\\braid{" not in r.text
    assert r.items[0].key == r.items[2].key            # identical spec -> same asset


def test_comments_verbatim_and_verb_untouched(tmp_path):
    src = ("% \\braid{\\bcr{1}}\n\\begin{verbatim}\n\\braid{\\bcr{1}}\n\\end{verbatim}\n"
           "\\verb|\\braid{\\bcr{1}}| 50\\% \\braid{\\bcr{1}} % \\braid{x}\n"
           "\\begin{lstlisting}\n\\braid{\\bcr{9}}\n\\end{lstlisting}\n")
    r = tx(src, tmp_path)
    assert len(r.items) == 1
    assert r.text.count("\\braid{") == 5 and r.text.count("\\braidfig") == 1
    assert len(mask(src)) == len(src)


def test_braidfig_and_braidsetup_not_confused(tmp_path):
    src = "\\braidsetup{lw=1.2pt}\n\\braidfig{x} \\braid{\\bcr{1}}"
    r = tx(src, tmp_path)
    assert r.text.startswith("\\braidsetup{lw=1.2pt}\n\\braidfig{x} \\braidfig{braids/bt-")


def test_braidsetup_affects_key_and_is_global(tmp_path):
    a = tx("\\braid{\\bcr{1}}", tmp_path).items[0].key
    b = tx("\\braidsetup{color=red}\\braid{\\bcr{1}}", tmp_path).items[0].key
    assert a != b
    c = tx("\\braidsetup{color=red}\\braid{\\bcr{1}\\bset{color=black}}", tmp_path).items[0].key
    assert c == a


@pytest.mark.parametrize("bad,frag,line", [
    ("x\n\\braid{\\bin{a b}\\bcr{1}\\bcr{5}}", "generator #2 = 5", 2),
    ("\\braid{\\bin{a b}\\bout{a b}\\bcr{1}}", "output endpoint 1", 1),
    ("\\braid{\\bin{(a b}}", "missing", 1),
    ("\\braid{\\bcr{x}}", "not an integer", 1),
    ("\\braid{\\foo{1}}", "unknown command \\foo", 1),
    ("\\braid{\\bcr{1}", "unbalanced", 1),
    ("a\n\n\\braid \\bcr{1}", "must be followed", 3),
    ("\\braid{\\bin{a b}\\bin{c d}}", "given twice", 1),
    ("\\braid{\\bcr{1}\\bcol{1}{red;bad}}", "unsupported color", 1),
    ("\\braid{\\bset{nonsense=1}\\bcr{1}}", "unknown option", 1),
    ("\\braid{}", "cannot infer", 1),
])
def test_diagnostics(bad, frag, line, tmp_path):
    with pytest.raises(TransformError) as e:
        tx(bad, tmp_path)
    assert frag in str(e.value) and e.value.line == line and e.value.file == "t.tex"


def test_error_position_inside_config(tmp_path):
    with pytest.raises(TransformError) as e:
        tx("\\braid{\n  \\bin{a (b\n c}\n}", tmp_path)
    assert e.value.line in (2, 3)


# --------------------------------------------------------------- cache
def test_cache_reuse_and_invalidation(tmp_path):
    c = Cache(tmp_path / "b")
    b = Braid([1, -2], "x_1 x_2 x_3")
    a1 = c.ensure(b)
    assert a1.status == "generated"
    mtime = a1.path.stat().st_mtime_ns
    a2 = c.ensure(b)
    assert a2.status == "reused" and a2.path.stat().st_mtime_ns == mtime
    variants = [Braid([1, 2], "x_1 x_2 x_3"),                       # crossing
                Braid([1, -2], "(x_1 x_2) x_3"),                   # parenthesization
                Braid([1, -2], "x_1 x_2 x_3", style=Style(lw=1.5)),  # style
                Braid([1, -2], "x_1 x_2 x_3", colors={1: "red"}),
                Braid([1, -2], "x_1 x_2 x_3", in_labels=["a", "b", "c"])]
    keys = {cache_key(v) for v in variants} | {cache_key(b)}
    assert len(keys) == 6
    for v in variants:
        assert c.ensure(v).status == "generated"
    assert Cache(tmp_path / "b", force=True).ensure(b).status == "generated"


def test_equivalent_specs_share_key():
    a = Braid([1, -2], "x_1  x_2\n x_3", "x_2 x_3 x_1")
    b = Braid([1, -2], "x_1 x_2 x_3")
    assert cache_key(a) == cache_key(b)
    assert cache_key(a, "tikz") != cache_key(a, "svg")


def test_corrupt_or_partial_assets_regenerate(tmp_path):
    c = Cache(tmp_path)
    b = Braid([1], n=2)
    p = c.ensure(b).path
    p.write_text("\\begin{tikzpicture}")             # truncated, wrong header
    assert c.ensure(b).status == "generated"
    p.write_text("")
    assert c.ensure(b).status == "generated"
    assert "\\end{tikzpicture}" in p.read_text()


def test_atomic_write_leaves_no_temp_on_failure(tmp_path, monkeypatch):
    from braidtex import cache as cm
    c = Cache(tmp_path)
    monkeypatch.setattr(cm.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        c.ensure(Braid([1], n=2))
    assert [p for p in tmp_path.iterdir()] == []


def test_clean(tmp_path):
    c = Cache(tmp_path / "b")
    c.ensure(Braid([1], n=2))
    (tmp_path / "b" / "keep.txt").write_text("mine")
    assert len(c.clean()) == 1
    assert (tmp_path / "b" / "keep.txt").exists()          # foreign files untouched


# ----------------------------------------------------------------- CLI
def test_cli_render_and_json(tmp_path, capsys):
    assert cli(["render", "--expr", r"\bin{a b}\bcr{1}"]) == 0
    assert "\\begin{tikzpicture}" in capsys.readouterr().out
    spec = tmp_path / "s.json"
    spec.write_text(json.dumps({"word": [1, 2], "source": "(a b) c", "target": "b (c a)"}))
    out = tmp_path / "o.svg"
    assert cli(["render", "--json", str(spec), "--format", "svg", "-o", str(out)]) == 0
    assert out.read_text().startswith("<svg")


def test_cli_errors_have_nonzero_status(tmp_path, capsys):
    assert cli(["render", "--expr", r"\bin{a b}\bcr{3}"]) == 2
    assert "generator" in capsys.readouterr().err
    assert cli(["render", "--expr", r"\bin{a b}\bout{a b}\bcr{1}"]) == 2


def test_cli_expr(tmp_path, capsys):
    assert cli(["expr", "f \\circ " + BR, "--assets", str(tmp_path / "br")]) == 0
    assert "\\braidfig{" in capsys.readouterr().out


def test_cli_identity_render(tmp_path, capsys):
    assert cli(["render", "--identity", "pentagon", "--opts", "objects={a b c d},scale=0.8"]) == 0
    assert "\\begin{tikzpicture}" in capsys.readouterr().out
    out = tmp_path / "h.tex"
    assert cli(["render", "--identity", "hexagon", "--format", "standalone", "-o", str(out)]) == 0
    assert "\\documentclass" in out.read_text()
    assert cli(["render", "--identity", "nonsense"]) == 2
    assert cli(["render", "--identity", "ybe", "--opts", "labels={a b}"]) == 2
