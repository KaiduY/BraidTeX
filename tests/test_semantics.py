import itertools
import pytest
from braidtex import (Braid, BraidValidationError, IncompatibleBoundaryError, Point, Axis,
                      Style, parse_config)


def perm_of(word, n):
    """Independent reference: compose transpositions acting on positions."""
    pos = list(range(n))                       # pos[k] = slot of strand k
    for g in word:
        i = abs(g) - 1
        for k in range(n):
            if pos[k] == i:
                pos[k] = i + 1
            elif pos[k] == i + 1:
                pos[k] = i
    return tuple(p + 1 for p in pos)


@pytest.mark.parametrize("word,n", [([], 3), ([1], 2), ([1, -2, 1], 3), ([2, 2, 2], 3),
                                    ([1, 2, 3, -1, -2, 1], 4), ([3, 1, 2, -3, 1], 5)])
def test_permutation_matches_reference(word, n):
    b = Braid(word, n=n)
    assert b.permutation == perm_of(word, n)
    assert sorted(b.permutation) == list(range(1, n + 1))


def test_sign_does_not_change_permutation():
    for w in itertools.product([1, -1, 2, -2], repeat=3):
        assert Braid(w, n=3).permutation == Braid([abs(g) for g in w], n=3).permutation


def test_over_under_convention():
    b = Braid([1, -2], n=3)
    c1, c2 = b.crossings
    assert (c1.over, c1.under) == (1, 2)           # positive: left-entering strand over
    # after sigma_1 slots are [2,1,3]; sigma_2^{-1}: right-entering strand (3) over
    assert (c2.over, c2.under) == (3, 1)
    assert [c.sign for c in b.crossings] == [1, -1]


def test_identity_and_small():
    assert Braid(n=3).word == ()
    assert Braid(n=1).permutation == (1,)
    assert Braid(source="").n == 0
    with pytest.raises(BraidValidationError):
        Braid([1], n=1)


@pytest.mark.parametrize("word,n", [([0], 3), ([3], 3), ([-4], 4), ([1.5], 3)])
def test_invalid_generators(word, n):
    with pytest.raises(BraidValidationError):
        Braid(word, n=n)


def test_cannot_infer_arity():
    with pytest.raises(BraidValidationError, match="cannot infer"):
        Braid()
    assert Braid([2]).n == 3          # inferred from the word


def test_arity_inferred_from_config():
    assert Braid(source="x_1 x_2 x_3 x_4").n == 4
    assert Braid(source="(a b) c").n == 3


def test_output_labels_follow_strands():
    b = Braid([1, 2], "a b c")
    assert b.target.labels() == ["b", "c", "a"]
    assert b.strand_at_output == (2, 3, 1)


def test_output_validation_errors_are_informative():
    with pytest.raises(IncompatibleBoundaryError) as e:
        Braid([1], "x_1 x_2 x_3", "x_1 x_2 x_3")
    assert "output endpoint 1" in str(e.value) and "x_2" in str(e.value)
    with pytest.raises(IncompatibleBoundaryError, match="arity"):
        Braid([1], "a b", "a b c")
    with pytest.raises(IncompatibleBoundaryError):
        Braid([1], "a b", "* *")           # labeled vs unlabeled


def test_source_inferred_from_target():
    b = Braid([1, 2], target="b c a")
    assert b.source.labels() == ["a", "b", "c"]


def test_different_parenthesizations():
    b = Braid([2, 1], "(x_1 x_2) x_3", "x_3 (x_1 x_2)")
    assert b.source.to_json() == [["x_1", "x_2"], "x_3"]
    assert b.target.to_json() == ["x_3", ["x_1", "x_2"]]


def test_default_target_keeps_shape():
    b = Braid([2], "(a b) c")
    assert b.target.to_json() == [["a", "c"], "b"]


def test_omitted_empty_unlabeled_distinct():
    assert Braid(n=2).source.labels() == [None, None]          # unlabeled
    assert Braid(source="").n == 0                              # explicitly empty
    with pytest.raises(BraidValidationError):
        Braid()                                                 # omitted, nothing to infer


def test_colors_follow_identity_and_style_is_separate():
    b = Braid([1, 2], n=3, colors={1: "red"})
    assert b.strand_color(1) == "red" and b.strand_color(2) == "black"
    b2 = b.replace(style=Style(lw=2.0, labels="none"))
    assert (b2.word, b2.source, b2.target, b2.permutation) == \
        (b.word, b.source, b.target, b.permutation)
    with pytest.raises(BraidValidationError):
        Braid([], n=2, colors={3: "red"})
    with pytest.raises(BraidValidationError):
        Braid([], n=2, colors={1: "red; \\write18"})


def test_display_labels_do_not_change_model():
    b = Braid([1], "a b")
    d = b.replace(in_labels=["p", "q"], out_labels=["*", "r"])
    assert d.source == b.source and d.target == b.target
    assert d.display_out() == [None, "r"]
    with pytest.raises(BraidValidationError):
        b.replace(in_labels=["p"])


def test_points_validated():
    with pytest.raises(BraidValidationError):
        Braid([], n=2, points=[Point("in", 3)])


def test_composition():
    a = Braid([1], "x y z")
    c = Braid([2], "y x z")
    ab = a.compose(c)
    assert ab.word == (1, 2) and ab.source == a.source and ab.target == c.target
    assert ab.permutation == Braid([1, 2], n=3).permutation
    with pytest.raises(IncompatibleBoundaryError):
        a.compose(Braid([2], "x y z"))
    with pytest.raises(IncompatibleBoundaryError):                  # shape differs
        Braid([], "(a b) c").compose(Braid([], "a b c"))


def test_json_roundtrip_and_friendly_spec():
    b = Braid([1, -2], "(x_1 x_2) x_3", colors={2: "teal!75!black"}, notes={1: "A"},
              points=[Point("in", 2, "p")], axis=Axis("frame"), style=Style(width=3.0, sigma=True),
              in_labels=["a", "b", "c"])
    again = Braid.from_json(b.to_json())
    assert again.to_dict() == b.to_dict()
    friendly = Braid.from_dict({"word": [1], "source": "a b"})
    assert friendly.target.labels() == ["b", "a"]
    with pytest.raises(BraidValidationError):
        Braid.from_dict({"word": [1], "source": "a b", "bogus": 1})
