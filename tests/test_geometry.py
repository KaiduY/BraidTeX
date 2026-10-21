import math
import random
import pytest
from braidtex import Braid, Style, build_geometry, count_intersections
from braidtex.geometry import bez_point, max_join_error, polyline


def rand_word(rng, n, L):
    return [rng.choice([-1, 1]) * rng.randint(1, n - 1) for _ in range(L)]


CASES = [([1], "a b"), ([-1], "a b"), ([1, 2, 1], "a b c"), ([1, 1, 1, 1], "a b"),
         ([1, -1], "a b"), ([2, 1, -3, 2], "(a b)(c d)"), ([1, 2, 3, -1, -2, 1], "a ((b c) d) e"),
         ([], "a b c"), ([], "a"), ([1, -2, 3, -4, 5], "(a b) (c d) e f"),
         ([2, 2], "(a b) c")]


@pytest.mark.parametrize("word,src", CASES)
def test_exactly_len_word_crossings(word, src):
    b = Braid(word, src)
    assert count_intersections(build_geometry(b)) == len(word)


def test_random_words_and_uneven_spacings():
    rng = random.Random(7)
    trees = ["a b c d e", "(a b) c d e", "((a b) c) (d e)", "a (b (c (d e)))"]
    for _ in range(25):
        w = rand_word(rng, 5, rng.randint(0, 14))
        src = rng.choice(trees)
        b = Braid(w, src)
        out_tree = rng.choice(trees)
        labs = b.target.labels()
        from braidtex import parse_config
        tgt = parse_config(out_tree).relabel(labs)
        b = Braid(w, src, tgt)
        assert count_intersections(build_geometry(b)) == len(w)


def test_joins_continuous_and_tangent_continuous():
    b = Braid([1, -2, 1, 1, -2], "(a b) c")
    g = build_geometry(b)
    pos, ang = max_join_error(g)
    assert pos < 1e-12 and ang < 1e-9


def test_endpoint_mapping():
    b = Braid([1, 2], "a b c")
    g = build_geometry(b)
    for s in g.strands:
        start, end = s.segments[0].p0, s.segments[-1].p3
        assert start == (g.in_x[s.ident - 1], g.height)
        assert end == (g.out_x[b.permutation[s.ident - 1] - 1], 0.0)


def test_over_strand_is_unbroken_and_under_is_cut_at_every_crossing():
    b = Braid([1, -2, 1], "a b c")
    g = build_geometry(b)
    by_id = {s.ident: s for s in g.strands}
    for c in b.crossings:
        assert len(by_id[c.over].runs) >= 1
    # each crossing cuts exactly one strand once -> total runs = n + len(word) - (cuts at ends)
    assert sum(len(s.runs) for s in g.strands) == b.n + len(b.word)
    for cx in g.crossings:
        lo, hi = cx.gap
        assert 0 < lo < hi < 1 and not cx.clamped


def test_gap_clearance_is_respected():
    st = Style(gap=0.1)
    b = Braid([1], "a b", style=st)
    g = build_geometry(b)
    cx = g.crossings[0]
    under = next(s for s in g.strands if s.ident == cx.under)
    over = next(s for s in g.strands if s.ident == cx.over)
    over_pts = polyline(over, 200)
    # strict: every drawn point of the under strand keeps at least gap + lw from the over curve
    need = (0.1 + st.lw * 2.54 / 72.27) * 0.97
    for run in under.runs:
        for bz in run:
            for i in range(21):
                p = bez_point(bz, i / 20)
                near_cross = math.dist(p, cx.center) < 0.5
                if near_cross:
                    assert min(math.dist(p, q) for q in over_pts) >= need


def test_wide_narrow_many_crossings_no_clamping():
    for st in (Style(width=1.4), Style(width=8.0), Style(band=1.4)):
        b = Braid([1, 1, 1, 1, 1, 1], "a b", style=st)
        g = build_geometry(b)
        assert count_intersections(g) == 6
        assert not any(c.clamped for c in g.crossings)


def test_layout_and_color_do_not_change_topology():
    w = [1, -2, 2, 1]
    base = Braid(w, "a b c")
    for st in (Style(width=5), Style(palette=True), Style(lw=2), Style(rho=0.3)):
        b = base.replace(style=st)
        assert b.permutation == base.permutation
        assert count_intersections(build_geometry(b)) == len(w)


def test_everything_inside_box_and_no_nan():
    b = Braid([1, 2, 1, -2], "(a b) (c d)")
    g = build_geometry(b)
    for s in g.strands:
        for bz in s.segments:
            for p in (bz.p0, bz.c1, bz.c2, bz.p3):
                assert 0 <= p[0] <= g.width and 0 <= p[1] <= g.height
                assert not any(math.isnan(v) for v in p)


def test_input_output_layouts_independent():
    b = Braid([1], "(a b) c", "b (a c)")
    g = build_geometry(b)
    gi = [y - x for x, y in zip(g.in_x, g.in_x[1:])]
    go = [y - x for x, y in zip(g.out_x, g.out_x[1:])]
    assert gi[0] < gi[1] and go[0] > go[1]
    assert g.in_x[0] == pytest.approx(g.out_x[0]) and g.in_x[-1] == pytest.approx(g.out_x[-1])


def test_custom_positions():
    b = Braid([], "a b c", style=Style(inpos=(0, 0.3, 1), outpos=(0, 0.5, 1)))
    g = build_geometry(b)
    assert g.in_x[1] < g.out_x[1]
    assert count_intersections(g) == 0


# ------------------------------------------------------------ smoothness
def curvature(b, s):
    u = 1 - s
    x = 3 * u * u * (b.c1[0] - b.p0[0]) + 6 * u * s * (b.c2[0] - b.c1[0]) + 3 * s * s * (b.p3[0] - b.c2[0])
    y = 3 * u * u * (b.c1[1] - b.p0[1]) + 6 * u * s * (b.c2[1] - b.c1[1]) + 3 * s * s * (b.p3[1] - b.c2[1])
    xx = 6 * u * (b.c2[0] - 2 * b.c1[0] + b.p0[0]) + 6 * s * (b.p3[0] - 2 * b.c2[0] + b.c1[0])
    yy = 6 * u * (b.c2[1] - 2 * b.c1[1] + b.p0[1]) + 6 * s * (b.p3[1] - 2 * b.c2[1] + b.c1[1])
    n = (x * x + y * y) ** 1.5
    return abs(x * yy - y * xx) / n if n > 1e-18 else 0.0


@pytest.mark.parametrize("word,src", [([1], "a b"), ([1, 2, 1], "a b c"), ([2, -1, 3], "(a b)(c d)"),
                                      ([1, 1, 1], "a b")])
def test_strands_are_smooth_monotone_and_loop_free(word, src):
    g = build_geometry(Braid(word, src))
    for s in g.strands:
        for sg in s.segments:
            ys = [bez_point(sg, i / 60)[1] for i in range(61)]
            assert all(b <= a + 1e-12 for a, b in zip(ys, ys[1:]))          # no loops / cusps
            assert max(curvature(sg, i / 100) for i in range(101)) < 6.0    # radius > 1.6 mm


def test_ribbon_and_wide_layouts_stay_smooth():
    c = Braid([1, 2], "x y z").compose_at(2, Braid([1], "a b"))
    g = build_geometry(c)
    assert max(curvature(sg, i / 100) for s in g.strands for sg in s.segments
               for i in range(101)) < 6.5


def test_line_widths_and_colours_are_uniform_in_tikz():
    from braidtex import render_tikz
    t = render_tikz(Braid([1, -2], "a b c", colors={1: "red"}, axis=__import__("braidtex").Axis("frame")))
    strand_lines = [l for l in t.splitlines() if l.startswith("\\draw[color=")]
    assert strand_lines and all("line width" not in l for l in strand_lines)   # picture-level width
    assert t.count("line width=0.900pt") == 1
    axis_widths = {l.split("line width=")[1].split("pt")[0] for l in t.splitlines()
                   if l.startswith("\\draw[") and "->" in l or "dotted" in l}
    assert len(axis_widths) == 1
