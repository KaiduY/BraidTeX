from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from braidtex import Braid
from braidtex_model import AuxiliaryPath, Connector, CoordinateFrame, Region, Separator
from braidtex_operations import DiagramSum, stack, substitute
from braidtex_transform import BraidTransformError, _options_to_braid, transform_source
from braidtex_parser import parse_braid_body


class PrimitiveModelTests(unittest.TestCase):
    def test_frame_ticks_are_independent_of_endpoints(self):
        frame = CoordinateFrame(top_ticks=(0.3, 1.2), bottom_ticks=(0.6,),
                                right_boundary=False, left_axis=True)
        braid = Braid(3, [], frame=frame)
        tex = braid.tikz(inline=False)
        self.assertIn("0.3", tex)
        self.assertIn("1.2", tex)
        self.assertIn("0.6", tex)
        self.assertNotIn("densely dotted", tex)

    def test_connector_legacy_tuple_coercion_preserves_color_and_nodes(self):
        braid = Braid(3, [], connectors=[(1, 3, 0, "red", False)])
        self.assertEqual(braid.connectors[0].color, "red")
        self.assertFalse(braid.connectors[0].nodes)
        self.assertEqual(braid.connectors[0].line_width, 0.75)

    def test_connector_uses_persistent_strand_identities(self):
        braid = Braid(3, [1], connectors=[Connector(1, 3, level=1)])
        tex = braid.tikz(inline=False)
        # Connector at level 1 sees strand 1 in lane 2 after the crossing, and
        # strand 3 in lane 3. It has precisely two connector nodes.
        self.assertIn("(0.9,0) -- (1.8,0)", tex)
        self.assertEqual(tex.count("circle[radius=0.045]"), 2)

    def test_intermediate_strands_do_not_receive_connector_nodes(self):
        braid = Braid(4, [], connectors=[Connector(1, 4, level=0)])
        tex = braid.tikz(inline=False)
        self.assertEqual(tex.count("circle[radius=0.045]"), 2)

    def test_auxiliary_paths_are_annotations_not_braid_strands(self):
        braid = Braid(3, [1, 2, -1], auxiliary_paths=[
            AuxiliaryPath(follow_strand=2, offset=0.16),
            AuxiliaryPath(points=((0.1, 1.2), (0.5, 0.6), (0.9, 0.2)), style="densely dotted"),
        ])
        self.assertEqual(braid.permutation, Braid(3, [1, 2, -1]).permutation)
        tex = braid.tikz(inline=False)
        self.assertIn("plot[smooth] coordinates", tex)
        self.assertIn("densely dotted", tex)

    def test_regions_render_with_braces(self):
        braid = Braid(3, [1, -2], regions=[Region(0, 1, "u"), Region(1, 2, "g", side="right")])
        tex = braid.tikz(inline=False)
        self.assertIn("decoration={brace", tex)
        self.assertIn("{$u$}", tex)
        self.assertIn("{$g$}", tex)
        self.assertIn("decorations.pathreplacing", braid.standalone_tex())

    def test_latex_frame_elements_and_connector_separator_styles(self):
        parsed = parse_braid_body(
            r"\btin{a b}\btcross{1}\btframe"
            r"\btsep[style={densely dotted},line_width=0.45,offset_down=0.1,ticks={0.2,0.8}]{1}"
            r"\btconnector[color=red,line_width=1.2,node_radius=0.06,nodes=false,visible=true,offset_down=0.15,name={join}]{1}{2}{1}",
            outer_options=(
                "frame_top=false,frame_bottom=true,frame_left=false,frame_right=false,"
                "frame_axis_color=blue,frame_axis_width=0.9,"
                "frame_boundary_style={dotted},frame_boundary_width=0.4,frame_tick_half_height=0.12"
            ),
        )
        braid = _options_to_braid(parsed)
        self.assertFalse(braid.frame.top_axis)
        self.assertTrue(braid.frame.bottom_axis)
        self.assertFalse(braid.frame.left_axis)
        self.assertFalse(braid.frame.right_boundary)
        self.assertEqual(braid.frame.axis_color, "blue")
        self.assertEqual(braid.frame.axis_width, 0.9)
        self.assertEqual(braid.frame.boundary_style, "dotted")
        self.assertEqual(braid.frame.boundary_width, 0.4)
        self.assertEqual(braid.frame.tick_half_height, 0.12)
        self.assertEqual(braid.frame.separators[0].ticks, (0.2, 0.8))
        self.assertEqual(braid.connectors[0].color, "red")
        self.assertEqual(braid.connectors[0].line_width, 1.2)
        self.assertFalse(braid.connectors[0].nodes)
        self.assertEqual(braid.connectors[0].offset_down, 0.15)
        self.assertEqual(braid.connectors[0].name, "join")

    def test_custom_frame_serializes_and_roundtrips(self):
        b = Braid(3, [1], frame=CoordinateFrame(top_ticks=(0.2,), separators=(Separator(1, ticks=(0.5,)),)))
        rebuilt = Braid.from_dict(b.to_dict())
        self.assertEqual(rebuilt.frame, b.frame)
        self.assertIn("densely dotted", rebuilt.tikz())


class StackingTests(unittest.TestCase):
    def test_stacking_concatenates_models_not_images(self):
        upper = Braid(3, [1, -2], layer_heights=(0.7, 1.1), connectors=[Connector(1, 3, 1)])
        lower = Braid(3, [2, -1], layer_heights=(0.8, 1.2))
        combined = stack(upper, lower, separators=True, labels=("u", "g"), check_labels=False)
        self.assertIsInstance(combined, Braid)
        self.assertEqual(combined.word, (1, -2, 2, -1))
        self.assertEqual(combined.layer_heights, (0.7, 1.1, 0.8, 1.2))
        self.assertEqual(len(combined.frame.separators), 1)
        self.assertEqual([r.label for r in combined.regions], ["u", "g"])
        self.assertIn("{$u$}", combined.tikz())
        self.assertIn("{$g$}", combined.tikz())

    def test_lower_top_connector_is_shifted_into_its_component_after_stack_gap(self):
        upper = Braid(2, [], identity_height=0.7)
        lower = Braid(2, [], identity_height=0.5, connectors=[Connector(1, 2, level=0)])
        combined = upper.compose(lower, check_labels=False)
        self.assertAlmostEqual(combined.connectors[0].offset_down, 0.7)
        self.assertAlmostEqual(combined.level_gaps[0], 1.2)
        # The connector is placed at the lower component's top boundary, not
        # incorrectly at the top of the full composite identity region.
        self.assertIn("(0,0.5) -- (0.9,0.5)", combined.tikz(inline=False))

    def test_lower_annotations_and_regions_follow_merged_stack_gap(self):
        upper = Braid(2, [], identity_height=0.7)
        lower = Braid(
            2, [], identity_height=0.5,
            annotations=[{"strand": 1, "level": 0, "label": "q"}],
            regions=[Region(0, 0, "g", end_offset=0.4)],
        )
        combined = upper.compose(lower, check_labels=False)
        self.assertAlmostEqual(combined.annotations[0]["offset_down"], 0.7)
        lower_region = next(r for r in combined.regions if r.label == "g")
        self.assertAlmostEqual(lower_region.start_offset, 0.7)
        self.assertAlmostEqual(lower_region.end_offset, 1.1)
        self.assertAlmostEqual(lower_region.end_offset - lower_region.start_offset, 0.4)

    def test_identity_components_keep_vertical_height(self):
        top = Braid(2, [], identity_height=0.6)
        middle = Braid(2, [], identity_height=1.0)
        bottom = Braid(2, [1])
        combined = stack(top, middle, bottom, labels=("u", "v", "g"), separators=True, check_labels=False)
        self.assertEqual(combined.word, (1,))
        self.assertEqual(combined.level_gaps[0], 1.6)
        regions = {r.label: r for r in combined.regions}
        self.assertAlmostEqual(regions["u"].end_offset - regions["u"].start_offset, 0.6)
        self.assertAlmostEqual(regions["v"].end_offset - regions["v"].start_offset, 1.0)

    def test_stack_checks_arities(self):
        with self.assertRaisesRegex(ValueError, "arities"):
            stack(Braid(2, []), Braid(3, []))

    def test_stack_checks_intermediate_labels(self):
        with self.assertRaisesRegex(ValueError, "labels do not match"):
            stack(Braid(2, [], input_labels=("a", "b")), Braid(2, [], input_labels=("q", "r")))

    def test_stacking_distributes_over_sums(self):
        summand = DiagramSum([Braid(2, [], input_labels=("a", "b"), output_labels=("c", "d")), Braid(2, [1], input_labels=("a", "b"), output_labels=("c", "d"))])
        result = stack(summand, Braid(2, [], input_labels=("a", "b")), check_labels=False)
        self.assertIsInstance(result, DiagramSum)
        self.assertEqual(len(result), 2)
        self.assertEqual([term.word for term in result], [(), (1,)])


class SubstitutionTests(unittest.TestCase):
    def test_substitution_arity_and_permutation_left_bundle(self):
        result = substitute(Braid(2, [1]), 1, Braid(2, []))
        self.assertEqual(result.n, 3)
        self.assertEqual(result.word, (2, 1))
        self.assertEqual(result.permutation, (3, 1, 2))

    def test_substitution_arity_and_permutation_right_bundle(self):
        result = substitute(Braid(2, [1]), 2, Braid(2, []))
        self.assertEqual(result.n, 3)
        self.assertEqual(result.word, (1, 2))
        self.assertEqual(result.permutation, (2, 3, 1))

    def test_negative_cabling_preserves_block_order(self):
        left = substitute(Braid(2, [-1]), 1, Braid(2, []))
        right = substitute(Braid(2, [-1]), 2, Braid(2, []))
        self.assertEqual(left.word, (-2, -1))
        self.assertEqual(right.word, (-1, -2))
        self.assertEqual(left.permutation, (3, 1, 2))
        self.assertEqual(right.permutation, (2, 3, 1))

    def test_outer_cancellation_cables_to_identity_permutation(self):
        result = substitute(Braid(2, [1, -1]), 1, Braid(2, []))
        self.assertEqual(result.permutation, (1, 2, 3))
        self.assertEqual(result.word, (2, 1, -1, -2))

    def test_inner_crossings_are_shifted_to_inserted_bundle(self):
        result = substitute(Braid(3, []), 2, Braid(2, [-1]))
        self.assertEqual(result.n, 4)
        self.assertEqual(result.word, (-2,))
        self.assertEqual(result.permutation, (1, 3, 2, 4))

    def test_connector_attachment_requires_explicit_policy(self):
        outer = Braid(2, [1], connectors=[Connector(1, 2, 0)])
        with self.assertRaisesRegex(ValueError, "connector_policy"):
            substitute(outer, 1, Braid(2, []))

    def test_connector_policy_all_creates_alternative_terms(self):
        outer = Braid(2, [1], connectors=[Connector(1, 2, 0)])
        result = substitute(outer, 1, Braid(2, []), connector_policy="all")
        self.assertIsInstance(result, DiagramSum)
        self.assertEqual(len(result), 2)
        self.assertEqual([term.n for term in result], [3, 3])
        self.assertEqual([term.connectors[0].strand_a for term in result], [1, 2])
        self.assertEqual([term.connectors[0].strand_b for term in result], [3, 3])

    def test_outer_top_connector_annotation_and_region_follow_inserted_gap(self):
        outer = Braid(
            3, [], identity_height=0.4,
            connectors=[Connector(2, 3, level=0)],
            annotations=[{"strand": 3, "level": 0, "label": "t"}],
            regions=[Region(0, 0, "outer", end_offset=0.25)],
        )
        inner = Braid(2, [], identity_height=0.65)
        result = substitute(outer, 1, inner)
        self.assertAlmostEqual(result.connectors[0].offset_down, 0.65)
        self.assertAlmostEqual(result.annotations[0]["offset_down"], 0.65)
        region = next(r for r in result.regions if r.label == "outer")
        self.assertAlmostEqual(region.start_offset, 0.65)
        self.assertAlmostEqual(region.end_offset, 0.9)
        self.assertAlmostEqual(region.end_offset - region.start_offset, 0.25)

    def test_connector_policy_explicit_index(self):
        outer = Braid(2, [1], connectors=[Connector(1, 2, 0)])
        result = substitute(outer, 1, Braid(2, []), connector_policy=2)
        self.assertEqual((result.connectors[0].strand_a, result.connectors[0].strand_b), (2, 3))

    def test_substitution_composes_with_sums(self):
        outer_sum = DiagramSum([Braid(2, []), Braid(2, [1])])
        result = substitute(outer_sum, 1, Braid(2, []))
        self.assertIsInstance(result, DiagramSum)
        self.assertEqual(len(result), 2)
        self.assertEqual([term.n for term in result], [3, 3])

    def test_diagram_sum_checks_boundary_arity(self):
        with self.assertRaisesRegex(ValueError, "same arity"):
            DiagramSum([Braid(2, []), Braid(3, [])])


class CompositeParserTests(unittest.TestCase):
    def test_parser_primitives_connectors_frame_and_auxiliary(self):
        source = r"""\documentclass{article}\begin{document}
$\braid{\btin{a b c}\btcross{1}\btframe\btticks{top}{0,0.9}\btsep{1}\btconnector{1}{3}{1}\btfollow{2}{0.15}\btregion{0}{1}{u}}$
\end{document}"""
        output, assets = transform_source(source, source_path="/tmp/primitives.tex")
        rendered = assets[0].read_text()
        self.assertIn(r"\braidasset{", output)
        self.assertIn("circle[radius=0.045]", rendered)
        self.assertIn("densely dotted", rendered)
        self.assertIn("decoration={brace", rendered)

    def test_stack_expression_transforms(self):
        source = r"\documentclass{article}\begin{document}$\btstack[labels={u|g}]{\braid{\btid{2}}\btsep\braid{\btin{a b}\btcross{1}}}$\end{document}"
        output, assets = transform_source(source, source_path="/tmp/stack.tex")
        self.assertEqual(len(assets), 1)
        tex = assets[0].read_text()
        self.assertIn("{$u$}", tex)
        self.assertIn("{$g$}", tex)
        self.assertIn("densely dotted", tex)
        self.assertIn(r"\braidasset{", output)

    def test_substitution_expression_transforms_and_expands_arity(self):
        source = r"\documentclass{article}\begin{document}$\btsubbraid[position=1,connector=all]{\btouter{\braid{\btin{a b}\btcross{1}}}\btinner{\braid{\btin{x y}}}}$\end{document}"
        _, assets = transform_source(source, source_path="/tmp/sub.tex")
        tex = assets[0].read_text()
        # outer sigma_1 with its left strand expanded to a two-strand bundle
        # becomes sigma_2 sigma_1: three distinct strands, two crossings.
        self.assertEqual(tex.count("draw=white,line width=2.85pt"), 2)  # two crossings in the expanded cable

    def test_sum_expressions_keep_terms_separate(self):
        source = r"\documentclass{article}\begin{document}$\btalternatives[operator=-]{\braid{\btid{2}}\btplus\braid{\btin{a b}\btcross{1}}}$\end{document}"
        _, assets = transform_source(source, source_path="/tmp/sum.tex")
        self.assertIn(r"\mathbin{-}", assets[0].read_text())

    @unittest.skipUnless(shutil.which("pdflatex"), "pdflatex is not installed")
    def test_real_latex_compilation_of_composed_features(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="braidtex composed build ") as tmp:
            project = Path(tmp)
            source = project / "main.tex"
            source.write_text(r"""\documentclass{article}
\usepackage{amsmath}
\begin{document}
\[
 \btstack[labels={u|g}]{
   \braid{\btin{a b}\btcross{1}\btout{b a}\btregion{0}{1}{u}}
   \btsep
   \braid{\btin{b a}\btcross{-1}\btout{a b}\btconnector{1}{2}{1}\btframe}
 }
\]
\[
 \btsubbraid[position=1,connector=all]{
   \btouter{\braid{\btin{a b}\btcross{1}\btconnector{1}{2}{0}}}
   \btinner{\braid{\btin{x y}}}
 }
\]
\end{document}
""", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(root / "braidtex_cli.py"), "build", str(source), "--engine", "pdflatex"],
                cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout[-6000:])
            self.assertTrue((project / "main.pdf").exists())


if __name__ == "__main__":
    unittest.main()
