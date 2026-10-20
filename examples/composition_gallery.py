"""Generate the composable BraidTeX operations gallery and its LaTeX source.

Run from the project root with ``python examples/composition_gallery.py``.
Every figure is assembled through the public Braid/Connector/Frame/Region API;
none of the diagrams is a hand-coded special-case drawing.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from braidtex import Braid
from braidtex_model import AuxiliaryPath, Connector, CoordinateFrame, Region, Separator
from braidtex_operations import DiagramSum, stack, substitute

OUT = Path(__file__).resolve().parent / "composition_generated"
OUT.mkdir(parents=True, exist_ok=True)


def save(name: str, diagram) -> None:
    diagram.write(OUT / f"{name}.tex", format="picture")


# 1. Smooth lateral shifts and a two-strand exchange, with endpoint layouts
# inferred from the source and target parenthesization trees.
shift_exchange = Braid(
    3,
    [1, -2, 1],
    input_labels=(r"x_1", r"x_2", r"x_3"),
    output_labels=(r"x_2", r"x_3", r"x_1"),
    top_parenthesization=((r"x_1", r"x_2"), r"x_3"),
    bottom_parenthesization=(r"x_2", (r"x_3", r"x_1")),
    strand_colors=("black", "black", "black"),
    layer_heights=(0.82, 1.05, 0.82),
    frame=CoordinateFrame(top_ticks=(0.0, 0.9, 2.0), bottom_ticks=(0.0, 0.9, 2.0)),
)
save("01_shift_exchange", shift_exchange)

# 2a. A simple horizontal connector in a four-strand identity diagram.
connector_simple = Braid(
    4,
    (),
    input_labels=(r"a", r"b", r"c", r"d"),
    output_labels=(r"a", r"b", r"c", r"d"),
    identity_height=1.15,
    connectors=(Connector(1, 3, level=0, color="black", node_radius=0.045),),
    frame=CoordinateFrame(top_ticks=(0.0, 0.9, 1.8, 2.7), bottom_ticks=(0.0, 0.9, 1.8, 2.7)),
)
save("02a_connector_simple", connector_simple)

# 2b. A connector joins persistent identities 1 and 4 after several crossings.
# Only its two selected endpoints receive circular nodes; it passes over the
# two intermediate strands without creating extra nodes or braid crossings.
connector_across = Braid(
    4,
    [1, 2, -1],
    input_labels=(r"a", r"b", r"c", r"d"),
    output_labels=(r"b", r"a", r"c", r"d"),
    connectors=(Connector(1, 4, level=3, color="black", node_radius=0.045),),
    layer_heights=(0.8, 0.85, 0.8),
    frame=CoordinateFrame(top_ticks=(0.0, 0.9, 1.8, 2.7), bottom_ticks=(0.0, 0.9, 1.8, 2.7)),
)
save("02b_connector_across", connector_across)

# 3. Vertical model composition; both components are Braid models. The
# connector and crossings are composed with strand identities remapped.
stack_top = Braid(
    3, [1, -2], layer_heights=(0.86, 1.08),
    connectors=(Connector(1, 3, level=2),),
    frame=CoordinateFrame(top_axis=True, bottom_axis=False, left_axis=True, right_boundary=True),
)
stack_bottom = Braid(
    3, [-1, 2, 1], layer_heights=(0.72, 0.86, 0.72),
    frame=CoordinateFrame(top_axis=False, bottom_axis=True, left_axis=False, right_boundary=True),
)
stacked = stack(stack_top, stack_bottom, separators=True, labels=(r"u", r"g"), check_labels=False)
save("03_stacked", stacked)

# 4. Cabling substitution: replace the first strand of a two-strand crossing
# with a two-strand braid. A connector attached to the replaced strand yields
# two distinct alternative terms, selected by an explicit policy.
outer = Braid(
    2, [1],
    input_labels=(r"a", r"b"), output_labels=(r"b", r"a"),
    connectors=(Connector(1, 2, level=0),),
    frame=CoordinateFrame(top_ticks=(0.0, 0.9), bottom_ticks=(0.0, 0.9)),
)
inner = Braid(
    2, [-1],
    input_labels=(r"x_1", r"x_2"), output_labels=(r"x_2", r"x_1"),
    auxiliary_paths=(AuxiliaryPath(follow_strand=1, offset=-0.16),),
)
substitution_alternatives = substitute(outer, 1, inner, connector_policy="all")
assert isinstance(substitution_alternatives, DiagramSum) and len(substitution_alternatives) == 2
save("04a_substitution_term_a", substitution_alternatives.terms[0])
save("04b_substitution_term_b", substitution_alternatives.terms[1])

# 5. Four strands, three connectors, a dotted separator, independently ordered
# input/output endpoint labels, frame ticks, and named vertical regions.
frame_four = CoordinateFrame(
    top_ticks=(0.0, 0.9, 1.8, 2.7),
    bottom_ticks=(0.0, 0.9, 1.8, 2.7),
    separators=(Separator(1, ticks=(0.45, 1.35, 2.25), style="densely dotted"),),
)
four_connectors = Braid(
    4,
    [1, 3, -2],
    input_labels=(r"x_1", r"x_2", r"x_3", r"x_4"),
    output_labels=(r"x_3", r"x_1", r"x_4", r"x_2"),
    connectors=(
        Connector(1, 4, level=0),
        Connector(2, 3, level=1),
        Connector(1, 4, level=3),
    ),
    frame=frame_four,
    regions=(Region(0, 1, r"u", side="left"), Region(1, 3, r"g", side="right")),
    layer_heights=(0.85, 0.9, 0.85),
)
save("05_four_strands_connectors_regions", four_connectors)

# 6. Repeated crossings with two dotted auxiliary trajectories. The dotted
# paths are rendering annotations only and do not affect the braid permutation.
repeated_aux = Braid(
    3,
    [1, 2, 1, -2, 1, 2],
    input_labels=(r"p", r"q", r"r"),
    output_labels=(r"q", r"r", r"p"),
    auxiliary_paths=(
        AuxiliaryPath(follow_strand=1, offset=-0.17, style="densely dotted"),
        AuxiliaryPath(follow_strand=3, offset=0.17, style="densely dotted", color="gray!70"),
        AuxiliaryPath(points=((0.16, 4.6), (0.26, 3.2), (0.18, 1.7), (0.24, 0.45)),
                      style="dotted", color="gray!60", line_width=0.5),
    ),
    layer_heights=(0.76, 0.88, 0.76, 0.88, 0.76, 0.88),
    frame=CoordinateFrame(top_axis=True, bottom_axis=True, left_axis=True, right_boundary=True,
                          separators=(Separator(3, style="densely dotted"),)),
)
save("06_repeated_crossings_auxiliary", repeated_aux)

# A TeX document sources the generated vector TikZ figures, so the gallery can
# be recompiled independently without needing Python once generated.
sections = [
    ("Smooth shifts and an exchange", "01_shift_exchange.tex", None),
    ("A connector with only its endpoint nodes", "02a_connector_simple.tex", None),
    ("A connector passing across intermediate strands", "02b_connector_across.tex", None),
    ("Vertical stacking as model composition", "03_stacked.tex", None),
    ("Operadic strand replacement: connector alternatives", "04a_substitution_term_a.tex", "04b_substitution_term_b.tex"),
    ("Four strands, connectors, separator, and regions", "05_four_strands_connectors_regions.tex", None),
    ("Repeated crossings and dotted auxiliary paths", "06_repeated_crossings_auxiliary.tex", None),
]
lines = [
    r"\documentclass[11pt]{article}",
    r"\usepackage[margin=1.6cm]{geometry}",
    r"\usepackage{amsmath,xcolor,graphicx,tikz,needspace}",
    r"\usetikzlibrary{decorations.pathreplacing}",
    r"\setlength{\parindent}{0pt}",
    r"\begin{document}",
    r"\begin{center}{\LARGE BraidTeX Composition Gallery}\end{center}",
    r"\small This gallery is generated from the public BraidTeX model API. The diagrams use model-level stacking, cabling substitution, persistent strand identities, and separate topological and annotation primitives.",
    r"\medskip",
]
for title, file_a, file_b in sections:
    lines += [r"\needspace{6.3cm}", r"\textbf{" + title + r"}\par", r"\smallskip"]
    if file_b is None:
        lines += [r"\begin{center}\resizebox{!}{5.0cm}{\input{composition_generated/" + file_a + r"}}\end{center}"]
    else:
        lines += [r"\begin{center}\resizebox{!}{4.2cm}{\input{composition_generated/" + file_a + r"}}\quad$+$\quad\resizebox{!}{4.2cm}{\input{composition_generated/" + file_b + r"}}\end{center}"]
    lines += [r"\smallskip"]
lines += [r"\end{document}"]
(ROOT / "examples" / "composition_gallery.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {len(sections)} gallery entries to {ROOT / 'examples' / 'composition_gallery.tex'}")
