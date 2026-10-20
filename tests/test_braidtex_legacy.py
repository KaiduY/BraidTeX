import unittest
from braidtex import Braid, Group, parenthesization_groups


class BraidTests(unittest.TestCase):
    def test_permutation_for_generator(self):
        self.assertEqual(Braid(3, [1]).permutation, (2, 1, 3))
        self.assertEqual(Braid(3, [-2]).permutation, (1, 3, 2))

    def test_pure_braid(self):
        self.assertEqual(Braid(3, [1, 2, 2, -1]).permutation, (1, 2, 3))

    def test_labels_follow_strands(self):
        b = Braid(2, [1], input_labels=["A", "B"])
        self.assertEqual(b.output_labels, ("B", "A"))

    def test_explicit_output_labels(self):
        b = Braid(2, [1], input_labels=["A", "B"], output_labels=["C", "D"])
        self.assertEqual(b.output_labels, ("C", "D"))

    def test_parenthesization_tree(self):
        groups, leaves = parenthesization_groups((("a", "b"), "c"))
        self.assertEqual([(g.start, g.end) for g in groups], [(1, 2)])
        self.assertEqual(leaves, ["a", "b", "c"])

    def test_invalid_generator(self):
        with self.assertRaises(ValueError):
            Braid(2, [2])

    def test_crossing_group_intervals_rejected(self):
        with self.assertRaises(ValueError):
            Braid(4, [], top_groups=[Group(1, 3), Group(2, 4)])

    def test_tikz_has_crossing_mask(self):
        tikz = Braid(2, [1], strand_colors=["blue", "red"]).tikz()
        self.assertIn("draw=white", tikz)
        self.assertIn("draw=blue", tikz)
        self.assertIn("draw=red", tikz)

    def test_json_string_color_key(self):
        b = Braid(2, [1], input_labels=["a", "b"], strand_colors={"1": "blue"})
        self.assertIn("draw=blue", b.tikz())

    def test_scale_transforms_geometry_and_labels_together(self):
        tikz = Braid(2, [1], diagram_scale=0.8).tikz()
        self.assertIn("scale=0.8,transform shape", tikz)

    def test_standalone_document(self):
        tex = Braid(2, [1]).standalone_tex()
        self.assertIn(r"\documentclass[tikz,border=4pt]{standalone}", tex)
        self.assertIn(r"\end{document}", tex)

    def test_inline_baseline_defaults_to_visual_center(self):
        self.assertIn("baseline=(braid-center)", Braid(2, [1]).tikz())
        # Preserve the pre-0.7 option for documents that intentionally need it.
        self.assertIn("baseline=(braid-base)", Braid(2, [1], baseline="(braid-base)").tikz())

    def test_identity_strands_are_each_emitted_as_one_coherent_path(self):
        tex = Braid(4, []).tikz(inline=False)
        self.assertEqual(tex.count("\\draw[draw=black,line width=1.15pt,line cap=round,line join=round]"), 4)

    def test_tick_ports_follow_custom_endpoint_positions(self):
        from braidtex_model import CoordinateFrame
        braid = Braid(
            3, [], top_positions=(0.0, 1.0, 3.0), bottom_positions=(0.0, 1.0, 3.0),
            frame=CoordinateFrame(top_tick_ports=(2, 3), bottom_tick_ports=(1, 3)),
        )
        tex = braid.tikz(inline=False)
        self.assertIn("(1,", tex)
        self.assertIn("(3,", tex)
        self.assertIn("(0,", tex)


if __name__ == "__main__":
    unittest.main()
