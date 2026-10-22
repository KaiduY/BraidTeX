"""The 'natural' geometry mode: strings instead of snakes."""
import math
import random
import warnings

import pytest

from braidtex import (Braid, BraidValidationError, Cache, Point, Style, build_geometry,
                      cache_key, count_intersections, parse_config)
from braidtex.geometry import bez_point, max_join_error
from braidtex.transform import transform_text

NAT = dict(geometry="natural")


def kappa(b, s):
    u = 1 - s
    x = 3 * u * u * (b.c1[0] - b.p0[0]) + 6 * u * s * (b.c2[0] - b.c1[0]) + 3 * s * s * (b.p3[0] - b.c2[0])
    y = 3 * u * u * (b.c1[1] - b.p0[1]) + 6 * u * s * (b.c2[1] - b.c1[1]) + 3 * s * s * (b.p3[1] - b.c2[1])
    xx = 6 * u * (b.c2[0] - 2 * b.c1[0] + b.p0[0]) + 6 * s * (b.p3[0] - 2 * b.c2[0] + b.c1[0])
    yy = 6 * u * (b.c2[1] - 2 * b.c1[1] + b.p0[1]) + 6 * s * (b.c2[1] * 0 + b.p3[1] - 2 * b.c2[1] + b.c1[1])
    n = x * x + y * y
    return ((x * yy - y * xx) / n ** 1.5 if n > 1e-18 else 0.0), math.sqrt(n)


def bending(g):
    """(bending energy, number of inflections, total path length / chord length)."""
    energy, infl, stretch = 0.0, 0, 0.0
    for st in g.strands:
        last, length = 0, 0.0
        for sg in st.segments:
            prev = bez_point(sg, 0)
            for i in range(1, 41):
                s = i / 40
                k, sp = kappa(sg, s)
                energy += k * k * sp / 40
                if abs(k) > 0.05:
                    sgn = 1 if k > 0 else -1
                    if last and sgn != last:
                        infl += 1
                    last = sgn
                p = bez_point(sg, s)
                length += math.dist(prev, p)
                prev = p
        chord = math.dist(st.segments[0].p0, st.segments[-1].p3)
        stretch += length / chord
    return energy, infl, stretch / len(g.strands)


def geom(word, src, **kw):
    return build_geometry(Braid(word, src, style=Style(**kw)))


CHAINS = [([1, 2, 3], "a b c d"), ([1, 2, 3, 4], "a b c d e"), ([3, 2, 1], "a b c d"),
          ([1, 2, 1, 1, 2, 1], "a b c"), ([1, 2, 3, -1, -2, 1], "a b c d")]


@pytest.mark.parametrize("word,src", CHAINS)
def test_natural_strings_are_less_bent_than_default(word, src):
    e0, i0, s0 = bending(geom(word, src))
    e1, i1, _ = bending(geom(word, src, **NAT))                 # default tension and wrap
    _, _, s1 = bending(geom(word, src, **NAT, wrap=0.0))        # straightness without extra swing
    assert e1 < 0.85 * e0                    # clearly lower bending energy
    assert i1 <= i0                          # no more inflections
    assert s1 <= s0 * 1.01                   # and not meaningfully longer than the snakes


def test_consecutive_crossings_run_straight():
    """sigma1 sigma2 sigma3: strand 1 crosses three strands in a row -> one straight run."""
    g = geom([1, 2, 3], "a b c d", **NAT)
    a = next(s for s in g.strands if s.ident == 1)
    # tangent direction at the two inner level points is (almost) the same: no stop between
    t1 = [(sg.p3[0] - sg.c2[0], sg.p3[1] - sg.c2[1]) for sg in a.segments[1:4]]
    ang = [math.atan2(t[0], -t[1]) for t in t1[:2]]
    assert abs(ang[0] - ang[1]) < 1e-9 and abs(ang[0]) > 0.5       # same, clearly diagonal
    d = build_geometry(Braid([1, 2, 3], "a b c d"))
    ad = next(s for s in d.strands if s.ident == 1)
    assert abs(ad.segments[1].p3[0] - ad.segments[1].c2[0]) < 1e-12   # default stops (vertical)


def test_turning_back_still_turns():
    """sigma1 sigma1: a back-and-forth twist must keep a genuine turn (vertical tangent)."""
    g = geom([1, 1], "a b", **NAT)
    a = next(s for s in g.strands if s.ident == 1)
    seg = a.segments[1]
    assert abs(seg.p3[0] - seg.c2[0]) < 1e-12


def test_wrap_loosens_twists_and_keeps_topology():
    tight = geom([1, 1, 1], "a b", **NAT, wrap=0.0)
    loose = geom([1, 1, 1], "a b", **NAT, wrap=0.15)
    def span(g):
        xs = [bez_point(sg, i / 20)[0] for s in g.strands for sg in s.segments for i in range(21)]
        return max(xs) - min(xs)
    assert span(loose) > span(tight) + 0.2
    assert count_intersections(loose) == 3


@pytest.mark.parametrize("tension", [0.0, 0.3, 1.0])
@pytest.mark.parametrize("wrap", [0.0, 0.08, 0.25])
def test_random_words_keep_exact_crossings(tension, wrap):
    rng = random.Random(11)
    trees = ["a b c d e", "(a b) c d e", "((a b) c) (d e)", "a (b (c (d e)))"]
    for _ in range(12):
        w = [rng.choice([-1, 1]) * rng.randint(1, 4) for _ in range(rng.randint(0, 12))]
        src = rng.choice(trees)
        b = Braid(w, src)
        tgt = parse_config(rng.choice(trees)).relabel(b.target.labels())
        b = Braid(w, src, tgt, style=Style(geometry="natural", tension=tension, wrap=wrap))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g = build_geometry(b)
        assert count_intersections(g) == len(w)
        pos, ang = max_join_error(g)
        assert pos < 1e-9 and ang < 1e-9                       # continuous, tangent continuous


def test_every_strand_is_a_function_of_height_and_smooth():
    for word, src in CHAINS:
        g = geom(word, src, **NAT)
        for s in g.strands:
            for sg in s.segments:
                ys = [bez_point(sg, i / 60)[1] for i in range(61)]
                assert all(b <= a + 1e-12 for a, b in zip(ys, ys[1:]))      # no loops
                assert max(abs(kappa(sg, i / 100)[0]) for i in range(101)) < 6.0


def test_fallback_keeps_the_braid_correct_under_hostile_settings():
    # very narrow, very tall tension+wrap: natural verification must fall back, not break
    for st in (dict(width=1.3, wrap=0.6), dict(width=1.5, spacing=0.3, minspan=0.3, wrap=0.5)):
        b = Braid([1, 2, 1, 1, 2, 3, 3], "a b c d", style=Style(geometry="natural", **st))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g = build_geometry(b)
        assert count_intersections(g) == 7


def test_natural_with_ribbons_discs_and_axes():
    c = Braid([1, 2, -1], "x y z").compose_at(2, Braid([1, -1, 1], "a b"))
    for comp in ("shadow", "separator"):
        b = c.replace(style=Style(geometry="natural", compose=comp, discs="both", extent="full"))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            g = build_geometry(b)
        assert count_intersections(g) == len(c.word)
        (rg,) = g.regions
        ribbon = [s for s in g.strands if s.ident in rg.strands]
        for idx in range(len(rg.left)):
            for u in (0.0, 0.5, 1.0):
                for s in ribbon:
                    p = bez_point(s.segments[idx], u)[0]
                    assert bez_point(rg.left[idx], u)[0] < p < bez_point(rg.right[idx], u)[0]


def test_gaps_are_still_clean_in_natural_mode():
    g = geom([1, 2, 3, -1, -2, 1], "a b c d", **NAT, palette=True)
    need = (0.07 + 0.9 * 2.54 / 72.27) * 0.9
    for cx in g.crossings:
        under = next(s for s in g.strands if s.ident == cx.under)
        over = next(s for s in g.strands if s.ident == cx.over)
        from braidtex.geometry import polyline
        opts = polyline(over, 120)
        for run in under.runs:
            for bz in run:
                for i in range(11):
                    p = bez_point(bz, i / 10)
                    if math.dist(p, cx.center) < 0.35:
                        assert min(math.dist(p, q) for q in opts) >= need
        assert not cx.clamped


def test_options_validation_serialization_cache():
    st = Style.from_options({"geometry": "natural", "tension": "0.6", "wrap": "1mm"})
    assert (st.geometry, st.tension, st.wrap) == ("natural", 0.6, pytest.approx(0.1))
    assert Style.from_options({"geometry": "strings"}).geometry == "natural"
    for bad in ({"geometry": "wavy"}, {"tension": "1.5"}, {"wrap": "5cm"}, {"tension": "x"}):
        with pytest.raises(BraidValidationError):
            Style.from_options(bad)
    b = Braid([1, 2], "a b c", style=st)
    assert Braid.from_json(b.to_json()).style == st
    assert cache_key(b) != cache_key(b.replace(style=Style()))
    assert cache_key(b) != cache_key(b.replace(style=Style(geometry="natural", tension=0.5)))


def test_semantics_unaffected_by_geometry_mode():
    d = Braid([1, -2, 1], "(a b) c", colors={1: "red"})
    n = d.replace(style=Style(geometry="natural"))
    assert (d.word, d.source, d.target, d.permutation, d.colors) == \
           (n.word, n.source, n.target, n.permutation, n.colors)


def test_transform_accepts_geometry_option(tmp_path):
    r = transform_text(r"\braidsetup{geometry=natural}\braid{\bin{a b c}\bcr{1 2}}"
                       r"\braid{\bin{a b c}\bcr{1 2}\bset{geometry=default}}",
                       "t.tex", Cache(tmp_path / "br"), "br")
    assert len(r.items) == 2 and r.items[0].key != r.items[1].key
