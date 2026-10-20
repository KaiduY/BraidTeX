from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from braidtex import Braid
from braidtex_parser import BraidSyntaxError, parse_braid_body, parse_configuration
from braidtex_transform import clean_cache, transform_file, transform_source


class ConfigurationParserTests(unittest.TestCase):
    def test_flat_configuration(self):
        self.assertEqual(parse_configuration(r"x_1 x_{2} \mathcal{A} V/W"),
                         (r"x_1", r"x_{2}", r"\mathcal{A}", "V/W"))

    def test_nested_parenthesization(self):
        self.assertEqual(parse_configuration(r"((x_1 x_2) x_3) x_4"),
                         ((('x_1', 'x_2'), 'x_3'), 'x_4'))

    def test_outer_parentheses_are_implicit_root(self):
        self.assertEqual(parse_configuration(r"(x_1 x_2 x_3)"), ('x_1', 'x_2', 'x_3'))

    def test_protected_atom_with_spaces(self):
        self.assertEqual(parse_configuration(r"{\text{some label}} x_2"),
                         (r"{\text{some label}}", "x_2"))

    def test_unclosed_config_rejected(self):
        with self.assertRaises(BraidSyntaxError):
            parse_configuration("(x_1 x_2")

    def test_arity_inference_and_signs(self):
        parsed = parse_braid_body(r"\btin{(a b) c}\btcross{1}\btcross{-2}\btout{a (b c)}")
        self.assertEqual(parsed.n, 3)
        self.assertEqual(parsed.word, [1, -2])

    def test_identity_arity(self):
        parsed = parse_braid_body(r"\btid{4}")
        self.assertEqual(parsed.n, 4)
        self.assertEqual(parsed.word, [])

    def test_bad_generator_range(self):
        with self.assertRaisesRegex(BraidSyntaxError, "invalid for n=2"):
            parse_braid_body(r"\btin{a b}\btcross{2}")

    def test_incompatible_endpoint_arities(self):
        with self.assertRaisesRegex(BraidSyntaxError, "Input configuration has 2 strands"):
            parse_braid_body(r"\btin{a b}\btout{a b c}")

    def test_unknown_commands_rejected(self):
        with self.assertRaisesRegex(BraidSyntaxError, "Unsupported command"):
            parse_braid_body(r"\btin{a b}\unknown{x}")

    def test_identity_marker_cannot_include_crossings(self):
        with self.assertRaisesRegex(BraidSyntaxError, "cannot be combined with crossings"):
            parse_braid_body(r"\btid{2}\btcross{1}")


class TransformTests(unittest.TestCase):
    def test_preserves_ordinary_math_and_comments(self):
        source = (r"\documentclass{article}" "\n"
                  r"% \braid{\btid{2}}" "\n"
                  r"\begin{document}$f_i^2+\braid{\btin{a b}\btcross{1}}+g$\end{document}")
        output, assets = transform_source(source, source_path="/tmp/project/main.tex")
        self.assertIn(r"f_i^2+\braidasset{braids/bt-", output)
        self.assertIn(r"% \braid{\btid{2}}", output)
        self.assertIn(r"\end{document}", output)
        self.assertEqual(len(assets), 1)
        self.assertIn(r"\usepackage{braidtex}", output)

    def test_verbatim_examples_are_left_untouched(self):
        source = (r"\documentclass{article}" + "\n" +
                  r"\begin{document}\verb|\braid{\btid{2}}|" + "\n" +
                  r"\begin{verbatim}" + "\n" +
                  r"\braid{\btid{3}}" + "\n" +
                  r"\end{verbatim}\end{document}")
        output, assets = transform_source(source, source_path="/tmp/literal.tex")
        self.assertEqual(assets, [])
        self.assertIn(r"\verb|\braid{\btid{2}}|", output)
        self.assertIn(r"\braid{\btid{3}}", output)

    def test_comments_inside_braid_body_do_not_break_parsing(self):
        source = "\\braid{\\btin{a b}% a comment containing } and {\n\\btcross{1}}"
        output, assets = transform_source(source, source_path="/tmp/commented-body.tex")
        self.assertIn(r"\braidasset{", output)
        self.assertEqual(len(assets), 1)

    def test_multiple_braids_and_braidexpr(self):
        source = r"\documentclass{article}\begin{document}\braid{\btid{1}} + \braidexpr{\btin{a b}\btcross{-1}}\end{document}"
        output, assets = transform_source(source, source_path="/tmp/project/main.tex")
        self.assertEqual(len(assets), 2)
        self.assertEqual(output.count(r"\braidasset{"), 2)

    def test_bad_expression_has_line_diagnostic(self):
        source = "line 1\n\\braid{\\btin{a b}\\btcross{0}}"
        with self.assertRaisesRegex(ValueError, "line 2"):
            transform_source(source, source_path="/tmp/bad.tex")

    def test_source_transform_file_keeps_original(self):
        with tempfile.TemporaryDirectory(prefix="braidtex project ") as tmp:
            project = Path(tmp)
            source = project / "my thesis.tex"
            original = r"\documentclass{article}\begin{document}$\braid{\btid{2}}$\end{document}"
            source.write_text(original, encoding="utf-8")
            target, generated = transform_file(source)
            self.assertNotEqual(source, target)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertTrue(target.exists())
            self.assertTrue(generated[0].exists())

    def test_endpoint_labels_can_be_suppressed_without_losing_structure(self):
        source = r"\documentclass{article}\begin{document}\braid[input_labels=false,output_labels=false]{\btin{(a b) c}\btout{a (b c)}}\end{document}"
        _, assets = transform_source(source, source_path="/tmp/unlabeled.tex")
        tikz = assets[0].read_text(encoding="utf-8")
        self.assertNotIn("$a$", tikz)
        self.assertNotIn("$b$", tikz)
        self.assertIn("\\draw[line width=0.55pt]", tikz)

    def test_document_defaults_and_local_override(self):
        source = (r"\documentclass{article}" + "\n" +
                  r"\braiddefaults{color=blue,strand_sep=1.1}" + "\n" +
                  r"\begin{document}$\braid{\btin{a b}\btcross{1}}$" + "\n" +
                  r"$\braid[color=red]{\btin{a b}\btcross{1}}$\end{document}")
        output, assets = transform_source(source, source_path="/tmp/defaults.tex")
        self.assertEqual(output.count(r"\braidasset{"), 2)
        self.assertNotEqual(assets[0], assets[1])
        first = assets[0].read_text(encoding="utf-8")
        second = assets[1].read_text(encoding="utf-8")
        self.assertIn("draw=blue", first)
        self.assertIn("draw=red", second)
        self.assertIn("x=1cm", first)
        self.assertNotIn(r"\braiddefaults", output)

    def test_cache_key_changes_with_rendering_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.tex"
            source.write_text(r"\documentclass{article}\begin{document}\braid{\btid{2}}\end{document}", encoding="utf-8")
            _, first_assets = transform_file(source)
            source.write_text(r"\documentclass{article}\begin{document}\braid[scale=0.8]{\btid{2}}\end{document}", encoding="utf-8")
            _, second_assets = transform_file(source)
            self.assertNotEqual(first_assets[0].name, second_assets[0].name)

    def test_cache_reuse_and_force_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "main.tex"
            source.write_text(r"\documentclass{article}\begin{document}\braid{\btid{2}}\end{document}", encoding="utf-8")
            _, assets = transform_file(source)
            asset = assets[0]
            first_text = asset.read_text(encoding="utf-8")
            meta = asset.parent / ".cache" / (asset.stem + ".json")
            first_meta = json.loads(meta.read_text(encoding="utf-8"))
            _, assets2 = transform_file(source)
            self.assertEqual(asset, assets2[0])
            self.assertEqual(asset.read_text(encoding="utf-8"), first_text)
            self.assertEqual(json.loads(meta.read_text(encoding="utf-8")), first_meta)
            _, _ = transform_file(source, force=True)
            self.assertTrue(asset.exists())
            self.assertEqual(clean_cache("braids", project_dir=root), 2)
            self.assertFalse(asset.exists())


class LayoutAndCompositionTests(unittest.TestCase):
    def test_hierarchical_positions_cluster(self):
        b = Braid(3, [], top_parenthesization=(("a", "b"), "c"))
        xs = b._top_xs
        self.assertAlmostEqual(xs[1] - xs[0], 0.9)
        self.assertGreater(xs[2] - xs[1], xs[1] - xs[0])

    def test_nested_positions_have_increasing_outer_gaps(self):
        b = Braid(4, [], top_parenthesization=((("a", "b"), "c"), "d"))
        gaps = [b._top_xs[i + 1] - b._top_xs[i] for i in range(3)]
        self.assertLess(gaps[0], gaps[1])
        self.assertLess(gaps[1], gaps[2])

    def test_custom_positions_validation(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            Braid(3, [], top_positions=[0, 1, 1])
        with self.assertRaisesRegex(ValueError, "length n=2"):
            Braid(2, [], bottom_positions=[0, 1, 2])

    def test_compose_words_and_labels(self):
        top = Braid(2, [1], input_labels=["a", "b"])
        below = Braid(2, [-1], input_labels=["b", "a"])
        composite = top.compose(below)
        self.assertEqual(composite.word, (1, -1))
        self.assertEqual(composite.permutation, (1, 2))

    def test_compose_shifts_annotations_with_strand_identity(self):
        top = Braid(2, [1], annotations=[(1, 0, "top mark")])
        below = Braid(2, [-1], annotations=[(1, 1, "bottom mark")])
        combined = top.compose(below)
        self.assertEqual(combined.annotations[0]["level"], 0)
        self.assertEqual(combined.annotations[1]["level"], 2)
        self.assertEqual(combined.annotations[1]["strand"], 2)
        self.assertIn("bottom mark", combined.tikz())

    def test_compose_rejects_boundary_label_mismatch(self):
        top = Braid(2, [1], input_labels=["a", "b"])
        below = Braid(2, [], input_labels=["a", "b"])
        with self.assertRaisesRegex(ValueError, "labels do not match"):
            top.compose(below)

    def test_explicit_axis_point_and_strand_annotation(self):
        source = r"\braid{\btin{a b}\btcross{1}\btpointx{-1.25}{q}\btannot{1}{1}{marked}}"
        with tempfile.TemporaryDirectory(prefix="braidtex annotation ") as tmp:
            transformed, assets = transform_source(source, source_path=Path(tmp) / "inline.tex")
            self.assertIn(r"\braidasset{", transformed)
            rendered = assets[0].read_text(encoding="utf-8")
            self.assertIn("circle[radius", rendered)
            self.assertIn("text=black", rendered)
            self.assertIn("marked", rendered)

    def test_identity_annotation_is_placed_at_top_layer(self):
        braid = Braid(2, [], annotations=[(1, 0, "top")])
        self.assertIn("(0.12,1.5) { $top$ }".replace(" ", ""), braid.tikz().replace(" ", ""))

    def test_annotation_level_is_validated(self):
        with self.assertRaisesRegex(BraidSyntaxError, "exceeds 1 crossing levels"):
            parse_braid_body(r"\btin{a b}\btcross{1}\btannot{1}{2}{too far}")

    def test_axis_and_points_render(self):
        b = Braid(2, [1], axis=True, boundary_points=[{"port": 1, "label": "p"}])
        tikz = b.tikz()
        self.assertIn("gray!60", tikz)
        self.assertIn("circle[radius=0.045]", tikz)
        self.assertIn("$p$", tikz)


if __name__ == "__main__":
    unittest.main()
