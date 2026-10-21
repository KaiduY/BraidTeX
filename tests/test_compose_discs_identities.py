import itertools
import math
import warnings

import pytest

from braidtex import (Braid, BraidValidationError, Cache, Style, TransformError, build_geometry,
                      count_intersections, parse_config)
from braidtex.discs import disc_layout, tree_height
from braidtex.geometry import bez_point, max_join_error
from braidtex.identities import make_scene, tree_math
from braidtex.layout import normalized_positions
from braidtex.transform import transform_text


# ----------------------------------------------------------------- layers
def test_layers_must_be_reduced_and_sum_to_word():
    with pytest.raises(BraidValidationError, match="twice"):
        Braid([1, 1], "a b", groups=[2])
    with pytest.raises(BraidValidationError, match="sum"):
        Braid([1, 1], "a b", groups=[1])
    b = Braid([1, 3], "a b c d", groups=[2])         # commuting crossings side by side
    assert len(b.layers) == 1 and b.permutation == (2, 1, 4, 3)
    assert count_intersections(build_geometry(b)) == 2


# ------------------------------------------------------------ composition
def reference_cabled_permutation(outer, k, m):
    """Independent: strand k becomes m parallel strands; permutation of the cable."""
    n = outer.n
    widths = [m if i == k else 1 for i in range(1, n + 1)]
    start, pos = {}, 0
    for i, w in enumerate(widths, 1):
        start[i] = pos
        pos += w
    perm_out, pos = {}, 0
    for slot_strand in outer.strand_at_output:
        perm_out[slot_strand] = pos
        pos += widths[slot_strand - 1]
    res = [0] * pos
    for i in range(1, n + 1):
        for t in range(widths[i - 1]):
            res[start[i] + t] = perm_out[i] + t + 1
    return tuple(res)


@pytest.mark.parametrize("word", [[1], [1, 2], [2, -1, 2], [-1, -2, 1], []])
@pytest.mark.parametrize("k", [1, 2, 3])
@pytest.mark.parametrize("at", ["top", "bottom"])
def test_cabling_permutation_and_boundaries(word, k, at):
    outer = Braid(word, "x y z")
    inner = Braid([], "a b")
    c = outer.compose_at(k, inner, at)
    assert c.n == 4
    assert c.permutation == reference_cabled_permutation(outer, k, 2)
    assert count_intersections(build_geometry(c)) == len(c.word)
    # every outer crossing becomes 1*2 elementary crossings if it involves the cable
    assert len(c.word) == sum(2 if k in (cr.over, cr.under) else 1 for cr in outer.crossings)


def test_composite_boundaries_and_nesting():
    outer = Braid([1], "x y z")
    inner = Braid([1], "a b")
    c = outer.compose_at(2, inner)
    assert c.source.to_json() == ["x", ["a", "b"], "z"]
    assert c.target.to_json() == [["b", "a"], "x", "z"]
    assert c.source.labels() == ["x", "a", "b", "z"]
    assert c.target.labels() == ["b", "a", "x", "z"]


def test_composition_independent_of_insertion_point():
    outer = Braid([1, 2, 1], "x y z")
    inner = Braid([1, -1, 1], "a b")
    ref = outer.compose_at(2, inner, "top")
    for at in ("bottom", "0", "1", "2", "3"):
        c = outer.compose_at(2, inner, at)
        assert (c.source, c.target, c.permutation) == (ref.source, ref.target, ref.permutation)
        assert sorted(c.word, key=abs) != [] and len(c.word) == len(ref.word)


def test_inner_braid_word_is_shifted_into_place():
    outer = Braid([], "x y z")
    c = outer.compose_at(3, Braid([1], "a b"), "top")
    assert c.word == (3,)                          # sigma_1 of the cable at offset 2
    c = outer.compose_at(1, Braid([-1], "a b"))
    assert c.word == (-1,)


def test_colors_follow_ribbon_and_inner_overrides():
    outer = Braid([1], "x y z", colors={2: "red", 1: "blue"})
    c = outer.compose_at(2, Braid([], "a b", colors={2: "green"}))
    assert c.colors == {1: "blue", 2: "red", 3: "green"}
    assert c.strand_color(4) == "black"


def test_regions_recorded_and_remapped():
    outer = Braid([1], "x y z")
    c = outer.compose_at(2, Braid([1], "a b"))
    (r,) = c.regions
    assert r.strands == (2, 3) and (r.first, r.last) == (1, 1)
    c2 = c.compose_at(1, Braid([], "p q"))          # strand 1 -> two strands; ribbon shifts
    assert {tuple(r.strands) for r in c2.regions} == {(3, 4), (1, 2)}


def test_substitution_rejects_bad_input():
    o = Braid([1], "x y")
    with pytest.raises(BraidValidationError):
        o.compose_at(3, Braid([], "a b"))
    with pytest.raises(BraidValidationError):
        o.compose_at(1, Braid([], "a b"), at="7")
    with pytest.raises(BraidValidationError):
        Braid([1], "x y", points=[__import__("braidtex").Point("in", 1)]).compose_at(
            1, Braid([], "a b"))


def test_json_roundtrip_with_regions_and_groups():
    c = Braid([1, 2], "x y z").compose_at(2, Braid([1], "a b"))
    again = Braid.from_json(c.to_json())
    assert again.to_dict() == c.to_dict() and again.regions == c.regions


def test_region_geometry_modes():
    base = Braid([1], "x y z").compose_at(2, Braid([1], "a b"))
    for mode in ("shadow", "separator"):
        g = build_geometry(base.replace(style=Style(compose=mode, extent='full')))
        (rg,) = g.regions
        assert rg.left[0].p0[0] < rg.right[0].p0[0]
        assert rg.left[0].p0[1] == rg.right[0].p0[1] == g.height   # both start at the top edge
    assert build_geometry(base.replace(style=Style(compose="none"))).regions == []
    sep = build_geometry(base.replace(style=Style(compose="separator")))
    shadow = build_geometry(base.replace(style=Style(compose="shadow")))
    assert len(sep.regions[0].left) < len(shadow.regions[0].left)        # inner vs full extent
    full = build_geometry(base.replace(style=Style(compose="separator", extent="full")))
    assert len(full.regions[0].left) == len(shadow.regions[0].left)


def test_ribbon_guides_enclose_ribbon_strands_everywhere():
    c = Braid([1, 2, -1], "x y z").compose_at(2, Braid([1, -1, 1], "a b"))
    g = build_geometry(c.replace(style=Style(compose="shadow")))
    (rg,) = g.regions
    ribbon = [s for s in g.strands if s.ident in rg.strands]
    segs_per = len(rg.left)
    for idx in range(segs_per):
        for u in (0.0, 0.25, 0.5, 0.75, 1.0):
            yl = bez_point(rg.left[idx], u)
            for s in ribbon:
                p = bez_point(s.segments[idx], u)
                assert abs(p[1] - yl[1]) < 1e-9
                assert yl[0] < p[0] - 0.05
                assert p[0] < bez_point(rg.right[idx], u)[0] - 0.05


def test_inner_layers_do_not_drift():
    c = Braid([1], "x y z").compose_at(2, Braid([1], "a b"), "top")
    g = build_geometry(c)
    # layer 1 is the inner braid: strands in slots 1,2 keep their x at layer ends up to crossing
    for ident, (a, b) in ((2, (1, 2)), (3, (2, 1))):       # ribbon strands swap slots 1 <-> 2
        band = next(s for s in g.strands if s.ident == ident).segments[1]
        assert band.p0[0] == pytest.approx(g.in_x[a]) and band.p3[0] == pytest.approx(g.in_x[b])
    assert max_join_error(g)[0] < 1e-12


def test_crossing_counts_for_composites():
    for word in ([1], [1, 2], [2, 1, 2]):
        for at in ("top", "bottom"):
            c = Braid(word, "x y z").compose_at(2, Braid([1, -1], "a b"), at)
            assert count_intersections(build_geometry(c)) == len(c.word)


# --------------------------------------------------------------------- discs
TREES = ["a b c", "(a b) c", "a (b c)", "((a b) c) d", "(a b)(c d)", "a ((b c) d) e",
         "((a b) (c d)) (e f)", "(((a b) c) d) e"]


def nodes(tree):
    """(lo, hi, depth) for every node, in leaf-index terms."""
    out = []
    counter = [0]

    def rec(n, d):
        lo = counter[0]
        if n.is_leaf:
            counter[0] += 1
        else:
            for c in n.children:
                rec(c, d + 1)
        out.append((lo, counter[0] - 1, d, n.is_leaf))

    rec(tree, 0)
    return out


@pytest.mark.parametrize("src", TREES)
def test_disc_nesting_matches_parenthesization(src):
    t = parse_config(src)
    xs = [0.5 + 3.0 * p for p in normalized_positions(t)]
    ds = disc_layout(t, xs)
    spans = {(d.lo, d.hi) for d in ds}
    assert spans == {(lo, hi) for lo, hi, _, _ in nodes(t)}              # one disc per node
    for d in ds:
        for e in ds:
            if d is e:
                continue
            if d.lo <= e.lo and e.hi <= d.hi and (d.lo, d.hi) != (e.lo, e.hi):
                assert d.contains(e) and d.rho > e.rho                  # ancestor contains
                assert not e.contains(d)
            elif e.hi < d.lo or d.hi < e.lo:
                assert not d.intersects(e)                              # unrelated: disjoint
    for i, x in enumerate(xs):                                          # a leaf point lies in
        inside = {(d.lo, d.hi) for d in ds if d.contains_point(x)}      # exactly its ancestors
        assert inside == {(d.lo, d.hi) for d in ds if d.lo <= i <= d.hi}


def test_issue_example_ab_c():
    t = parse_config("((a b) c)")
    assert t.to_json() == [["a", "b"], "c"]
    xs = [0.5 + 2.0 * p for p in normalized_positions(t)]
    ds = disc_layout(t, xs)
    inner = next(d for d in ds if (d.lo, d.hi) == (0, 1) and not d.is_leaf)
    outer = next(d for d in ds if (d.lo, d.hi) == (0, 2) and d.depth == 0)
    assert inner.contains_point(xs[0]) and inner.contains_point(xs[1])
    assert not inner.contains_point(xs[2])
    assert outer.contains(inner) and outer.contains_point(xs[2])


def test_discs_in_geometry_and_padding():
    b = Braid([1], "((a b) c)", style=Style(discs="both"))
    g = build_geometry(b)
    assert len(g.discs_in) == 5 and len(g.discs_out) == 5          # 3 leaves + 2 groups
    assert g.pad_top >= max(d.rho for d in g.discs_in) + 0.1
    assert build_geometry(Braid([1], "a b")).discs_in == []
    assert Style.from_options({"discs": ""}).discs == "both"
    assert Style.from_options({"discs": "in"}).discs == "in"


def test_disc_radii_are_positive_even_when_crowded():
    t = parse_config("(((((a b) c) d) e) f) g")
    xs = [0.5 + 2.0 * p for p in normalized_positions(t)]
    assert all(d.rho > 0 for d in disc_layout(t, xs))


# ----------------------------------------------------------------- identities
def test_ybe_pictures_have_equal_permutation_and_labels():
    sc = make_scene("ybe", {}, {})
    tex = sc.render("k")
    assert tex.count("\\begin{scope}") == 2 and "tikzpicture" in tex
    a, b = Braid([1, 2, 1], "a b c"), Braid([2, 1, 2], "a b c")
    assert a.permutation == b.permutation and a.target == b.target
    assert [c.over for c in a.crossings] != [c.over for c in b.crossings]


@pytest.mark.parametrize("name,expected_scopes", [("ybe", 2), ("far", 2), ("inverse", 3),
                                                  ("crossings", 2), ("assoc", 2)])
def test_braid_scenes_render(name, expected_scopes):
    tex = make_scene(name, {}, {}).render("k")
    assert tex.count("\\begin{scope}") == expected_scopes


def test_scene_options_and_validation():
    tex = make_scene("ybe", {"labels": "x_1 x_2 x_3", "colors": "red blue green", "sign": "-"},
                     {}).render("k")
    assert "color=red" in tex and "$x_1$" in tex
    with pytest.raises(BraidValidationError):
        make_scene("ybe", {"labels": "a b"}, {})
    with pytest.raises(BraidValidationError):
        make_scene("ybe", {"colors": "red;bad"}, {})
    with pytest.raises(BraidValidationError):
        make_scene("nonsense", {}, {})
    with pytest.raises(BraidValidationError):
        make_scene("pentagon", {"nodestyle": "draw\\write18"}, {})
    assert make_scene("ybe", {"lw": "1.2pt"}, {}).key() != make_scene("ybe", {}, {}).key()


def test_pentagon_and_hexagon_vertices_are_the_right_parenthesizations():
    pent = make_scene("pentagon", {}, {}).render("k")
    for txt in ["((a \\otimes b) \\otimes c) \\otimes d", "(a \\otimes (b \\otimes c)) \\otimes d",
                "a \\otimes ((b \\otimes c) \\otimes d)", "a \\otimes (b \\otimes (c \\otimes d))",
                "(a \\otimes b) \\otimes (c \\otimes d)"]:
        assert txt in pent
    assert pent.count("\\draw[") == 5 and pent.count("\\node[") == 5
    hexa = make_scene("hexagon", {"objects": "X Y Z", "op": ""}, {}).render("k")
    for txt in ["(X\\,Y)\\,Z", "X\\,(Y\\,Z)", "(Y\\,Z)\\,X", "Y\\,(Z\\,X)", "(Y\\,X)\\,Z", "Y\\,(X\\,Z)"]:
        assert txt in hexa
    assert hexa.count("\\draw[") == 6


def test_pentagon_commutes_in_the_free_monoidal_sense():
    """Both paths from ((ab)c)d to a(b(cd)) pass through trees whose leaf order is unchanged."""
    ts = ["((a b) c) d", "(a (b c)) d", "a ((b c) d)", "a (b (c d))", "(a b) (c d)"]
    for t in ts:
        assert parse_config(t).labels() == list("abcd")
    assert len({str(parse_config(t).to_json()) for t in ts}) == 5


def test_tree_math():
    assert tree_math(parse_config("(a b) c"), "\\otimes") == "(a \\otimes b) \\otimes c"
    assert tree_math(parse_config("* x"), "") == "\\bullet\\,x"


# ------------------------------------------------- transformer integration
def tx(src, tmp_path):
    return transform_text(src, "t.tex", Cache(tmp_path / "br"), "br")


def test_bsub_and_braidid_in_source(tmp_path):
    src = (r"\braid{\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{1}}\bset{compose=separator}}"
           "\n" r"\braidid{ybe}{labels={p q r}} \braidid{pentagon}{}")
    r = tx(src, tmp_path)
    assert r.text.count("\\braidfig{br/bt-") == 3 and len(r.items) == 3
    assert r.items[0].key != r.items[1].key


def test_modes_change_the_cache_key(tmp_path):
    body = r"\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{1}}"
    keys = {tx(r"\braid{" + body + extra + "}", tmp_path).items[0].key
            for extra in ("", r"\bset{compose=separator}", r"\bset{compose=none}",
                          r"\bset{extent=full,compose=separator}", r"\bset{at=bottom}",
                          r"\bset{shadowcolor=red}")}
    assert len(keys) == 6


@pytest.mark.parametrize("bad,frag", [
    (r"\braid{\bin{x y}\bsub{3}{\bin{a b}}}", "cannot substitute"),
    (r"\braid{\bin{x y}\bsub{1}{\bax{h}}}", "unknown command \\bax inside \\bsub"),
    (r"\braid{\bin{x y}\bsub{0}{\bin{a b}}}", ">= 1"),
    (r"\braid{\bin{x y}\bsub{1}{\bin{a b}\bcr{4}}}", "generator"),
    (r"\braid{\bin{x y}\bsub{1}{\bin{a b}}\bset{at=9}}", "layer"),
    (r"\braid{\bin{a b}\bset{compose=weird}}", "compose"),
    (r"\braidid{ybe}", "two braced"),
    (r"\braidid{nope}{}", "unknown identity"),
    (r"\braidid{ybe}{labels={a}}", "exactly 3"),
])
def test_new_diagnostics(bad, frag, tmp_path):
    with pytest.raises(TransformError) as e:
        tx(bad, tmp_path)
    assert frag in str(e.value)


def test_comments_hide_new_commands(tmp_path):
    r = tx("% \\braidid{ybe}{}\n\\begin{verbatim}\\braidid{ybe}{}\\end{verbatim}", tmp_path)
    assert r.items == [] and not r.changed


def test_inline_preset():
    st = Style.from_options({"inline": "true", "lw": "1pt"})
    assert st.band < 0.5 and st.lw == pytest.approx(1.0)
