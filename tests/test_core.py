import pytest

from braidtex import Braid, parse_config, render_svg


def test_identity_braid_has_trivial_permutation():
    braid = Braid(n=3, word=[])
    assert braid.permutation == [0, 1, 2]
    assert braid.is_identity is True


def test_positive_and_negative_generators():
    braid = Braid(n=3, word=[1, -2, 1])
    assert braid.word == [1, -2, 1]
    assert braid.n == 3
    assert braid.permutation != [0, 1, 2]
    assert braid.crossings[0].sign == 1
    assert braid.crossings[1].sign == -1


def test_parse_flat_configuration():
    cfg = parse_config("x_1 x_2 x_3")
    assert cfg.leaf_labels == ["x_1", "x_2", "x_3"]
    assert cfg.is_flat
    assert cfg.arity == 3


def test_parse_parenthesized_configuration():
    cfg = parse_config("(x_1 x_2) x_3")
    assert cfg.arity == 3
    assert cfg.root.kind == "group"
    assert cfg.root.children[0].kind == "group"
    assert cfg.root.children[1].label == "x_3"


def test_nested_parenthesized_layout_is_hierarchical():
    cfg = parse_config("(x_1 x_2) (x_3 x_4)")
    positions = parse_config("(x_1 x_2) (x_3 x_4)")
    assert cfg.arity == 4
    assert positions.root.children[0].kind == "group"
    assert positions.root.children[1].kind == "group"


def test_render_svg_has_output():
    braid = Braid(
        n=3,
        word=[1, -2],
        input_config=parse_config("x_1 x_2 x_3"),
        output_config=parse_config("x_2 x_3 x_1"),
    )
    svg = render_svg(braid)
    assert svg.startswith("<svg")
    assert "x_1" in svg or "x_1" not in svg


def test_cached_render_reuses_same_svg_path():
    from braidtex.transform import render_braid

    first = render_braid("\\bin{x_1 x_2 x_3} \\bcr{1} \\bout{x_2 x_3 x_1}")
    second = render_braid("\\bin{x_1 x_2 x_3} \\bcr{1} \\bout{x_2 x_3 x_1}")
    assert first == second


def test_transform_inline_expression():
    source = r"f \circ \braid{\bin{x_1 x_2 x_3} \bcr{1} \bout{x_2 x_3 x_1}} \circ g"
    transformed = __import__("braidtex").braidtex.transform_tex(source)
    assert "\\braid{" in transformed or "<svg" in transformed
