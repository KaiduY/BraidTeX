"""Surface braids: the sphere and the torus."""
import itertools
import random
import warnings

import pytest

from braidtex import (Braid, BraidValidationError, Cache, Loop, Style, TransformError,
                      build_geometry, cache_key, count_intersections, render_tikz)
from braidtex import surface as sf
from braidtex.geometry import bez_point, max_join_error
from braidtex.identities import make_scene
from braidtex.transform import transform_text


# ================================================================ the algebra (motion model)
@pytest.mark.parametrize("n", [2, 3, 4])
def test_bellingeri_relations_hold_in_the_drawn_conventions(n):
    """BR, R1, R2, R4 and TR of B_n(T^2) hold for the loops exactly as BraidTeX draws them."""
    res = sf.check_relations(n)
    assert res and all(res.values()), [k for k, v in res.items() if not v]


def test_only_four_of_the_32_conventions_satisfy_the_presentation():
    good = sf.find_conventions()
    assert len(good) == 4 and sf.DEFAULT in good      # the drawn one: front loop, rightwards, ...


@pytest.mark.parametrize("left,right,n", [
    (["1", "a1", "1", "a1"], ["a1", "1", "a1", "1"], 2),                 # R2 with +s1
    (["-1", "a1", "-1", "b1"], ["b1", "-1", "a1", "-1"], 2),             # R4 mirrored
    (["-1", "b1", "-1", "a1"], ["a1", "-1", "b1", "1"], 2),              # R4 with a,b swapped
    (["a1", "b1", "-a1", "-b1"], ["1", "1"], 2),                         # wrong commutator
    (["a1", "-b1", "-a1", "b1"], ["-1", "-1"], 2),                       # TR with s1^-2
    (["a1", "-b1", "-a1", "b1"], ["1"], 2),                              # TR without the square
    (["a1", "b1"], ["b1", "a1"], 2),                                     # a, b do not commute
    (["a1", "1"], ["1", "a1"], 2),                                       # a does not commute with s1
])
def test_wrong_relations_are_rejected(left, right, n):
    assert not sf.equal(left, right, n)


def test_invariants_are_consistent():
    assert sf.equal(["1", "-1"], [], 3) and sf.equal(["a1", "-a1"], [], 2) and sf.equal(["b2", "-b2"], [], 3)
    assert sf.equal(["-1", "a1", "1"], ["a2"], 3)                        # a_2 = s1^-1 a_1 s1
    assert not sf.equal(["1", "a1", "-1"], ["a2"], 3)
    assert not sf.equal(["-1", "b1", "1"], ["b2"], 3)                    # b_2 is NOT s1^-1 b_1 s1 ...
    assert sf.equal(["-a1", "1", "b1", "-1", "a1"], ["b2"], 3)           # ... but (a1^-1 s1) b_1 (..)^-1


def test_loops_of_far_apart_strands():
    assert sf.equal(["b1", "b3"], ["b3", "b1"], 3)                        # depth loops avoid each other
    assert not sf.equal(["a1", "b3"], ["b3", "a1"], 3)                    # an a-loop sweeps over b3's strand
    assert not sf.equal(["a1", "a3"], ["a3", "a1"], 3)


# ================================================================== model
def test_loop_tokens_and_validation():
    b = Braid([1, "a1", "-b2", Loop("a", 3, -1)], "x y z", surface="torus")
    assert [str(g) for g in b.word if isinstance(g, Loop)] == ["a1", "-b2", "-a3"]
    assert b.permutation == (2, 1, 3) and b.n_projected_crossings == 1 + 2 + 2
    assert [e.kind + str(e.slot + 1) for e in b.loops] == ["a1", "b2", "a3"]
    assert Braid.from_json(b.to_json()).word == b.word and Braid.from_json(b.to_json()).surface == "torus"
    for bad, frag in ((dict(word=["a1"], surface="plane"), "torus"),
                      (dict(word=["a1"], surface="sphere"), "sphere"),
                      (dict(word=["a4"], surface="torus"), "invalid"),
                      (dict(word=["c1"], surface="torus"), "bad generator"),
                      (dict(word=[], surface="klein"), "surface must be")):
        with pytest.raises(BraidValidationError, match=frag):
            Braid(bad["word"], "x y z", surface=bad["surface"])
    with pytest.raises(BraidValidationError, match="gap"):
        Braid(["a2"], "x ... y", surface="torus")


def test_loops_do_not_change_the_permutation_or_boundaries():
    b = Braid(["a1", "1", "b2", "-a2"], "x y z", surface="torus")
    assert b.target.labels() == ["y", "x", "z"] and b.permutation == (2, 1, 3)
    c = Braid([1], "x y z", surface="torus")
    assert c.permutation == b.permutation


def test_loop_layers_and_groups():
    with pytest.raises(BraidValidationError, match="alone"):
        Braid([1, "a1"], "x y", surface="torus", groups=[2])
    b = Braid([1, "a1", 1], "x y", surface="torus")
    assert len(b.layers) == 3 and b.crossings[1].level == 3


def test_composition_module_structure():
    outer = Braid([1, "a3", "b2"], "x y z", surface="torus")      # after s1: positions y x z
    c = outer.compose_at(2, Braid([1], "p q"))                   # strand 2 = y becomes the ribbon
    assert c.surface == "torus" and c.n == 4
    assert [(e.kind, e.slot + 1) for e in c.loops] == [("a", 4), ("b", 3)]   # shifted past the ribbon
    with pytest.raises(BraidValidationError, match="planar"):
        outer.compose_at(2, Braid([], "p q", surface="sphere"))
    with pytest.raises(BraidValidationError, match="loop"):
        Braid(["a2"], "x y", surface="torus").compose_at(2, Braid([], "p q"))
    with pytest.raises(BraidValidationError, match="surfaces"):
        Braid([1], "x y", surface="torus").compose(Braid([1], "y x", surface="plane"))


# ================================================================ geometry
def torus_words(rng, n, L):
    out = []
    for _ in range(L):
        r = rng.random()
        if r < 0.5 and n > 1:
            out.append(rng.choice([-1, 1]) * rng.randint(1, n - 1))
        else:
            out.append(Loop(rng.choice("ab"), rng.randint(1, n), rng.choice([-1, 1])))
    return out


@pytest.mark.parametrize("geometry", ["default", "natural"])
def test_projected_crossings_are_exact_for_random_torus_words(geometry):
    rng = random.Random(3)
    for _ in range(14):
        n = rng.randint(2, 4)
        w = torus_words(rng, n, rng.randint(1, 6))
        b = Braid(w, " ".join("xyzu"[:n]), surface="torus", style=Style(geometry=geometry))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            g = build_geometry(b)
        assert count_intersections(g) == b.n_projected_crossings
        pos, ang = max_join_error(g)
        assert pos < 1e-9 and ang < 1e-9
        assert len(g.seams) == sum(1 for e in b.loops if e.kind == "a")
        assert len(g.marks) == sum(1 for e in b.loops if e.kind == "b")


def test_a_loop_passes_in_front_of_everything_and_changes_sides():
    g = build_geometry(Braid(["a2"], "x y z", surface="torus"))
    mover = g.strands[1]
    assert mover.jumps and len(mover.runs) == 2                      # two pieces: exit / entry
    first, second = mover.runs[0][-1].p3, mover.runs[1][0].p0
    assert first[0] == pytest.approx(g.width) and second[0] == pytest.approx(0.0)
    assert first[1] == pytest.approx(second[1])                      # same height: identified edges
    over = [c for c in g.crossings if c.over == 2]
    assert sorted(c.under for c in over) == [1, 3] and all(c.over == 2 for c in g.crossings)
    # leftwards for the inverse loop
    h = build_geometry(Braid(["-a2"], "x y z", surface="torus"))
    assert h.strands[1].runs[0][-1].p3[0] == pytest.approx(0.0)
    assert h.strands[1].runs[1][0].p0[0] == pytest.approx(h.width)


def test_loops_with_gaps_ribbons_discs():
    b = Braid(["a1", 3, "b4"], "x ... y z", surface="torus",
              style=Style(gapthrough="dotted", geometry="natural", discs="in"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        g = build_geometry(b)
    assert count_intersections(g) == b.n_projected_crossings and g.gaps[0].dots
    # a loop of another strand sweeps over a ribbon (cabling keeps the module structure)
    c = Braid(["a3", 1], "x y z", surface="torus").compose_at(2, Braid([1], "p q"))
    assert count_intersections(build_geometry(c)) == c.n_projected_crossings
    for compose in ("shadow", "separator"):
        d = c.replace(style=Style(compose=compose, geometry="natural"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert count_intersections(build_geometry(d)) == d.n_projected_crossings


# ================================================================ drawing
def test_torus_frame_marks_and_loop_decorations():
    t = render_tikz(Braid(["a1", "-b2"], "x y", surface="torus"))
    assert t.count("-- (") > 0 and t.count("$T^2$") == 1
    assert t.count(") -- (") >= 8                                     # frame edges + chevrons
    assert "$b^{-1}$" in t and "$a$" in t
    assert "$T^2$" not in render_tikz(Braid(["a1"], "x y", surface="torus", style=Style(surfacelabel=False)))
    assert "$b$" not in render_tikz(Braid(["b1"], "x y", surface="torus", style=Style(looplabels=False)))
    # inverse a-loop is labelled a^{-1} at the left edge
    assert "a^{-1}" in render_tikz(Braid(["-a1"], "x y", surface="torus"))


def test_sphere_frame_and_disc_variants():
    t = render_tikz(Braid([1], "x y", surface="sphere"))
    assert "$S^2$" in t and t.count("$\\infty$") == 2 and "dashed" in t   # one arc per axis
    d = render_tikz(Braid([1, 2], "(x y) z", surface="sphere", style=Style(discs="both")))
    assert "$\\infty$" in d and d.count("dashed") >= 2                    # dashed root disc, no arcs
    assert "$S^2$" in d
    pl = render_tikz(Braid([1], "x y"))
    assert "$S^2$" not in pl and "$T^2$" not in pl and "infty" not in pl


def test_torus_has_no_root_disc():
    tikz = render_tikz(Braid([1], "(x y) z", surface="torus", style=Style(discs="in")))
    plain = render_tikz(Braid([1], "(x y) z", style=Style(discs="in")))
    assert tikz.count("arc[start angle=-90") == plain.count("arc[start angle=-90") - 1


def test_axis_override_and_none():
    t = render_tikz(Braid([1], "x y", surface="torus", axis=__import__("braidtex").Axis("none")))
    assert ") -- (" not in t.split("\\draw[color")[0]                      # no frame lines
    assert "$T^2$" in t                                                    # the tag stays (surfacelabel)


# ============================================================ identities & transform
@pytest.mark.parametrize("name,n", [("torus-r1", 3), ("torus-r1", 4), ("torus-r2", 2), ("torus-r2", 3),
                                    ("torus-r4", 2), ("torus-r4", 3), ("torus-tr", 2),
                                    ("torus-tr", 3), ("torus-conj", 3)])
def test_surface_identities_draw_true_relations(name, n):
    """Every relation pictured is verified by the motion model."""
    for loop in "ab":
        scene = make_scene(name, {"n": str(n), "loop": loop}, {})
        assert scene.render("k").count("\\begin{scope}") == 2
        if name == "torus-conj":
            left, right = (["a2"], ["-1", "a1", "1"]) if loop == "a" else \
                (["b2"], ["-a1", "1", "b1", "-1", "a1"])
            assert sf.equal(left, right, n)
    rel = {"torus-r1": "R1 a s2", "torus-r2": "R2 a", "torus-r4": "R4", "torus-tr": "TR"}
    if name in rel:
        left, right = sf.relations(n)[rel[name]]
        assert sf.equal(left, right, n)


def test_sphere_identities():
    s = make_scene("sphere", {"n": "4"}, {}).render("k")
    assert s.count("$S^2$") == 2 and s.count("\\begin{scope}") == 2
    t = make_scene("sphere-twist", {}, {}).render("k")
    assert t.count("\\begin{scope}") == 2
    with pytest.raises(BraidValidationError):
        make_scene("torus-r1", {"n": "2"}, {})
    with pytest.raises(BraidValidationError):
        make_scene("torus-tr", {"loop": "c"}, {})
    # the sphere relation word: s1 s2 s3 s3 s2 s1 is a pure braid, the twist word is the full twist
    lhs = Braid([1, 2, 3, 3, 2, 1], "a b c d")
    assert lhs.permutation == (1, 2, 3, 4)
    delta2 = Braid([1, 2, 3] * 4, "a b c d")
    assert delta2.permutation == (1, 2, 3, 4)


def test_latex_source_with_surfaces(tmp_path):
    src = (r"\braidsetup{surface=torus}\braid{\bin{x y}\bcr{1 a1 -b2}}"
           r"\braid{\bin{x y}\bcr{1}\bset{surface=sphere}}"
           r"\braid{\bin{x y}\bcr{1}\bset{surface=plane}}\braidid{torus-tr}{}\braidid{sphere}{}")
    r = transform_text(src, "t.tex", Cache(tmp_path / "b"), "b")
    assert len(r.items) == 5 and len({i.key for i in r.items}) == 5
    for bad, frag in ((r"\braid{\bin{x y}\bcr{a1}}", "torus"),
                      (r"\braid{\bin{x y}\bcr{a9}\bset{surface=torus}}", "invalid"),
                      (r"\braid{\bin{x y}\bcr{1}\bset{surface=klein}}", "surface must be"),
                      (r"\braidsetup{surface=moebius}\braid{\bcr{1}}", "surface must be"),
                      (r"\braid{\bin{x y}\bcr{q1}}", "not a generator")):
        with pytest.raises(TransformError, match=frag):
            transform_text(bad, "t.tex", None)


def test_surface_changes_the_cache_key():
    plane = Braid([1], "x y")
    assert len({cache_key(plane), cache_key(plane.replace(surface="sphere")),
                cache_key(plane.replace(surface="torus"))}) == 3
