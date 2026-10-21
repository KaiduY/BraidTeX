import pytest
from braidtex import ConfigSyntaxError, normalized_positions, parse_config
from braidtex.layout import gap_weights


def J(s):
    return parse_config(s).to_json()


def test_core_structures_are_distinct():
    assert J("x_1 x_2 x_3") == ["x_1", "x_2", "x_3"]
    assert J("(x_1 x_2) x_3") == [["x_1", "x_2"], "x_3"]
    assert J("x_1 (x_2 x_3)") == ["x_1", ["x_2", "x_3"]]
    assert J("(x_1 x_2)(x_3 x_4)") == [["x_1", "x_2"], ["x_3", "x_4"]]
    assert J("((x_1 x_2) x_3) x_4") == [[["x_1", "x_2"], "x_3"], "x_4"]


def test_unbalanced_trees_and_arity():
    t = parse_config("(a (b c d)) e (f g)")
    assert t.arity == 7 and t.labels() == list("abcdefg")


@pytest.mark.parametrize("raw", [r"x_1", "A", "V/W", r"X^{\otimes 2}", r"\frac{A}{B}",
                                 "x_{12}", r"x'_1", r"\mathbb{R}^{n}"])
def test_atoms(raw):
    t = parse_config(f"{raw} y")
    assert t.labels() == [raw, "y"]


def test_braces_protect_parentheses():
    assert parse_config("{V(W)} x").labels() == ["{V(W)}", "x"]
    assert parse_config(r"\atom{f(x, y)} z").labels() == ["f(x, y)", "z"]
    assert parse_config(r"\atom{ ((a ) } z").labels() == ["((a )", "z"]
    assert parse_config(r"\( x").labels() == [r"\(", "x"]       # escaped paren is part of atom


def test_redundant_wrappers_and_roundtrip():
    assert J("((x y))") == ["x", "y"] and J("(x) y") == ["x", "y"]
    assert J("(((a b)) c)") == [["a", "b"], "c"]
    for s in ["a b c", "(a b) c", r"\atom{f(x)} (y z)", "* (* *)"]:
        t = parse_config(s)
        assert parse_config(t.to_string()) == t


def test_unlabeled_star_and_empty():
    assert parse_config("* *").labels() == [None, None]
    assert parse_config("   ").arity == 0


@pytest.mark.parametrize("bad,frag", [("(a b", "missing"), ("a b)", "unmatched"), ("()", "empty"),
                                      ("a {b", "unbalanced"), ("a } b", "unmatched"),
                                      (r"\atom{}", "empty"), (r"\atom x", "\\atom")])
def test_syntax_errors(bad, frag):
    with pytest.raises(ConfigSyntaxError) as e:
        parse_config(bad)
    assert frag in str(e.value) and "^" in str(e.value)


# ----------------------------------------------------------------- layout
def pos(s, **kw):
    return normalized_positions(parse_config(s), **kw)


def gaps(p):
    return [b - a for a, b in zip(p, p[1:])]


def test_flat_is_uniform():
    for n in (2, 3, 5, 8):
        g = gaps(pos(" ".join(f"x{i}" for i in range(n))))
        assert max(g) - min(g) < 1e-12
        assert g[0] == pytest.approx(1 / (n - 1))


def test_clusters():
    g = gaps(pos("(a b) c"))
    assert g[0] < g[1]
    g = gaps(pos("a (b c)"))
    assert g[0] > g[1]
    g = gaps(pos("(a b)(c d)"))
    assert g[1] > g[0] and g[0] == pytest.approx(g[2])


def test_left_and_right_nesting_differ():
    assert pos("(a b) c") != pos("a (b c)")
    assert pos("(a b) c") == pytest.approx([1 - x for x in reversed(pos("a (b c)"))])


def test_nesting_hierarchy_monotone():
    g = gaps(pos("(((a b) c) d) e"))
    assert g == sorted(g) and g[0] < g[-1]


def test_bounds_determinism_and_deep_nesting():
    s = "x"
    for _ in range(40):
        s = f"({s} y)"
    p = pos(s)
    assert p[0] == 0 and p[-1] == pytest.approx(1)
    assert all(b > a for a, b in zip(p, p[1:]))
    assert p == pos(s)
    assert min(gaps(p)) > 0


def test_single_and_empty_and_custom():
    assert pos("a") == [0.5] and pos("") == []
    assert pos("a b c", custom=[0, 0.1, 1]) == [0, 0.1, 1]
    with pytest.raises(Exception):
        pos("a b", custom=[0.5, 0.2])
    with pytest.raises(Exception):
        pos("a b", custom=[0.5])
