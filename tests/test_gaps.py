"""Gaps ("..."): placeholders for omitted strands, and mixes of labeled/unlabeled strands."""
import math
import random
import warnings

import pytest

from braidtex import (Braid, BraidValidationError, Cache, IncompatibleBoundaryError, Point, Style,
                      TransformError, build_geometry, count_intersections, parse_config,
                      render_svg, render_tikz)
from braidtex.config import GAP
from braidtex.geometry import _x_at_height, polyline
from braidtex.transform import transform_text

LAB = "x_1 ... x_n"


# ------------------------------------------------------------------ parsing
@pytest.mark.parametrize("tok", ["...", r"\dots", r"\cdots", r"\ldots", "\u2026"])
def test_gap_tokens(tok):
    t = parse_config(f"a {tok} b")
    assert t.labels() == ["a", GAP, "b"] and t.leaves()[1].is_gap and t.arity == 3


def test_gap_in_groups_and_roundtrip():
    t = parse_config(r"(a \cdots b) * c ...")
    assert t.to_json() == [["a", GAP, "b"], None, "c", GAP]
    assert parse_config(t.to_string()) == t
    assert parse_config(t.to_string()).to_json() == t.to_json()
    assert Braid([], t).to_dict()["source"] == t.to_json()
    assert Braid.from_json(Braid([], t).to_json()).source == t


def test_dots_inside_atoms_are_not_gaps():
    assert parse_config("x_{...} a..").labels() == ["x_{...}", "a.."]
    # a *labeled* strand that displays dots is written with an explicit atom of a different spelling
    lit = parse_config(r"\atom{\ldots} b")
    assert lit.labels() == [r"\ldots", "b"] and not lit.leaves()[0].is_gap


# ------------------------------------------------------------------- model
def test_gap_is_a_position_and_permutes_like_a_strand():
    b = Braid([1, 2], LAB)
    assert b.n == 3 and b.gap_ids == frozenset({2})
    assert b.target.labels() == [GAP, "x_n", "x_1"]            # x_1 passed the dots and x_n
    assert b.permutation == (3, 1, 2)
    assert b.display_in() == ["x_1", None, "x_n"] and b.display_out() == [None, "x_n", "x_1"]


def test_boundary_validation_includes_gaps():
    with pytest.raises(IncompatibleBoundaryError):
        Braid([1, 2], LAB, "x_n ... x_1")                      # gap must stay where the word puts it
    with pytest.raises(IncompatibleBoundaryError):
        Braid([1], "a b c", "a ... c")                         # a strand cannot become a gap
    assert Braid([1], "a ... b", "... a b").permutation == (2, 1, 3)    # sigma_1: a passes the gap
    with pytest.raises(IncompatibleBoundaryError):
        Braid([1], "a ... b", "a ... b")                       # ... so the output cannot be unchanged
    assert Braid([1, 2], LAB, "... x_n x_1").target.labels() == [GAP, "x_n", "x_1"]


def test_decorations_on_gaps_are_rejected():
    with pytest.raises(BraidValidationError, match="gap"):
        Braid([], LAB, colors={2: "red"})
    with pytest.raises(BraidValidationError, match="gap"):
        Braid([], LAB, notes={2: "A"})
    with pytest.raises(BraidValidationError, match="gap"):
        Braid([], LAB, points=[Point("in", 2)])
    with pytest.raises(BraidValidationError, match="gap"):
        Braid([], LAB).compose_at(2, Braid([], "a b"))
    # ... but the neighbours are fine
    Braid([], LAB, colors={1: "red", 3: "blue"}, points=[Point("in", 3, "p")])


def test_mixed_labeled_and_unlabeled_strands():
    b = Braid([1, 3, 2], "x * y z")
    assert b.source.labels() == ["x", None, "y", "z"]
    assert [b.source.labels()[k - 1] for k in b.strand_at_output] == b.target.labels()
    assert b.display_in() == ["x", None, "y", "z"]
    with pytest.raises(IncompatibleBoundaryError):
        Braid([1], "x * y", "x * y")                           # labeled/unlabeled swapped in place
    c = Braid([1], "x * y").compose_at(2, Braid([1], "a *"))
    assert c.source.labels() == ["x", "a", None, "y"]


def test_substituting_into_neighbours_of_gaps_and_gaps_in_inner_braids():
    inner = Braid([1], "a ... b")                              # inner braid containing a gap
    c = Braid([1], "x y z").compose_at(2, inner)
    assert c.gap_ids == frozenset({3}) and c.n == 5
    g = build_geometry(c)
    assert count_intersections(g) == len(c.word)


def test_layout_gives_the_gap_a_position():
    g = build_geometry(Braid([], LAB))
    assert len(g.in_x) == 3 and g.in_x[0] < g.in_x[1] < g.in_x[2]
    flat = build_geometry(Braid([], "a ... b c")).in_x
    wide = build_geometry(Braid([], "a ... b c", style=Style(gapspan=2.0))).in_x
    ratio = lambda x: (x[1] - x[0]) / (x[3] - x[2])            # next to the gap vs. ordinary gap
    assert ratio(flat) == pytest.approx(1.0) and ratio(wide) == pytest.approx(2.0)


# ----------------------------------------------------------------- geometry
def words(rng, n, L):
    return [rng.choice([-1, 1]) * rng.randint(1, n - 1) for _ in range(L)]


@pytest.mark.parametrize("geometry", ["default", "natural"])
@pytest.mark.parametrize("through", ["solid", "dotted"])
def test_exact_crossings_and_clean_dots(geometry, through):
    rng = random.Random(5)
    srcs = ["a ... b", "a ... b c", "a * ... b ... c", "(a ... b) c ... d", "a b ... c d"]
    for _ in range(14):
        src = rng.choice(srcs)
        n = parse_config(src).arity
        w = words(rng, n, rng.randint(0, 9)) if n > 1 else []
        st = Style(geometry=geometry, gapthrough=through)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g = build_geometry(Braid(w, src, style=st))
        assert count_intersections(g) == len(w)
        for s in g.strands:
            assert s.hidden == (s.ident in Braid(w, src).gap_ids)
            assert not (s.hidden and (s.runs or s.dotted_runs))


def test_dots_are_aligned_centred_and_clear_of_strands():
    b = Braid([1, 2, -3, -4, 2], "x_1 ... x_i * x_j ... x_n")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        g = build_geometry(b)
    assert len(g.gaps) == 2 and g.gap_rows
    ys = [sorted({round(y, 6) for _, y in gp.dots}) for gp in g.gaps]
    assert ys[0] == ys[1] == [round(y, 6) for y in sorted(g.gap_rows)]      # same rows: aligned
    real = [polyline(s, 24) for s in g.strands if not s.hidden]
    segs = {s.ident: s.segments for s in g.strands}
    for gp in g.gaps:
        for y in g.gap_rows:
            row = [(x, yy) for x, yy in gp.dots if abs(yy - y) < 1e-9]
            assert len(row) == 3
            cx = _x_at_height(segs[gp.ident], y)
            assert sum(x for x, _ in row) / 3 == pytest.approx(cx, abs=1e-6)  # centred on its gap
            for px, py in row:
                dmin = min(math.dist((px, py), q) for poly in real for q in poly)
                assert dmin > 0.09                                           # no collision


def test_dotted_traversal_only_inside_the_region():
    b = Braid([1, 2], LAB, style=Style(gapthrough="dotted"))
    g = build_geometry(b)
    solid = build_geometry(Braid([1, 2], LAB))
    assert any(s.dotted_runs for s in g.strands if not s.hidden)
    assert not any(s.dotted_runs for s in solid.strands)
    gp = g.gaps[0]
    segs = {s.ident: s.segments for s in g.strands}
    from braidtex.geometry import bez_point
    for s in g.strands:
        for run in s.dotted_runs:
            for sg in run:
                for i in range(11):
                    x, y = bez_point(sg, i / 10)
                    assert abs(x - _x_at_height(segs[gp.ident], y)) <= gp.halfwidth + 1e-6
    # nothing is cut where a strand passes a gap (no under/over mask for placeholders)
    assert all(c.gap == (0.0, 0.0) for c in g.crossings if 2 in (c.over, c.under))


def test_gap_with_ribbons_discs_axes_and_natural():
    inner = Braid([1], "a ... b")
    c = Braid([1, 2], "x y z").compose_at(2, inner)
    for geometry in ("default", "natural"):
        st = Style(geometry=geometry, discs="both", compose="shadow", extent="full",
                   gapthrough="dotted")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g = build_geometry(c.replace(style=st))
        assert count_intersections(g) == len(c.word)
        tikz = render_tikz(c.replace(style=st))
        assert "circle (1.1pt)" in tikz and tikz.count("\\draw[color=black!55") >= 1


def test_no_endpoint_marks_at_gaps():
    from braidtex import Axis
    b = Braid([], LAB, axis=Axis("h"), style=Style(dots=True))
    t = render_tikz(b)
    ticks = [l for l in t.splitlines() if "-- " in l and "line width" in l and "->" not in l]
    assert len(ticks) == 4                                     # 2 real endpoints top + bottom
    assert t.count("circle (1.3pt)") == 4                      # endpoint markers: not at the gap


def test_discs_skip_gap_leaves():
    t = render_tikz(Braid([], "(a ... b) c", style=Style(discs="in")))
    assert t.count("circle (1.2pt)") == 3                      # a, b, c only


def test_svg_has_dots():
    assert "<circle" in render_svg(Braid([1, 2], LAB, style=Style(gapthrough="dotted")))


def test_options_validation_and_roundtrip():
    st = Style.from_options({"gapdots": "5", "gaprows": "3", "gapthrough": "dotted",
                             "gapcolor": "gray", "gapspan": "1.5"})
    assert (st.gapdots, st.gaprows, st.gapthrough, st.gapspan) == (5, "3", "dotted", 1.5)
    for bad in ({"gapdots": "0"}, {"gaprows": "x"}, {"gapthrough": "none"}, {"gapspan": "9"},
                {"gapdots": "x"}):
        with pytest.raises(BraidValidationError):
            Style.from_options(bad)
    b = Braid([1], LAB, style=st)
    assert Braid.from_json(b.to_json()).style == st


def test_row_count_option_and_fallback_when_crowded():
    g3 = build_geometry(Braid([], "a ... b", style=Style(height=6.0, gaprows="3")))
    assert len(g3.gap_rows) == 3
    # a gap crossed in every layer still shows its dots somewhere (never silently empty)
    w = [1, 2, -2, -1] * 3
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        g = build_geometry(Braid(w, "a ... b", style=Style(gapthrough="dotted")))
    assert g.gaps[0].dots


# ---------------------------------------------------------------- transform
def test_latex_source_with_gaps(tmp_path):
    r = transform_text(r"\braid{\bin{x_1 \cdots x_n}\bcr{1 2}\bset{gapthrough=dotted}}"
                       r"\braid{\bin{x_1 ... x_n}\bcr{1 2}}", "t.tex", Cache(tmp_path / "b"), "b")
    assert len(r.items) == 2 and r.items[0].key != r.items[1].key
    with pytest.raises(TransformError, match="gap"):
        transform_text(r"\braid{\bin{x ... y}\bcol{2}{red}}", "t.tex", None)
    with pytest.raises(TransformError, match="generator"):
        transform_text(r"\braid{\bin{x ... y}\bcr{3}}", "t.tex", None)
