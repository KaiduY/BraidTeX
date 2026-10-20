"""Generate TikZ braid diagrams from Artin braid words.

Convention: a word is drawn from top to bottom. Generator +i means sigma_i
and generator -i means sigma_i^{-1}. By default, +i draws the strand entering
at position i over the strand entering at position i+1. The convention can be
reversed with ``positive_over='right'``.

The module uses only Python's standard library. Generated snippets require
TikZ and xcolor, and are designed to work both in math mode and as standalone
figures.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from braidtex_geometry import GeometryMixin
from braidtex_layout import endpoint_positions as _tree_positions
import argparse
import json
import math

__all__ = ["Braid", "Group", "parenthesization_groups", "from_dict"]
RENDERER_VERSION = "0.3.0"


@dataclass(frozen=True, order=True)
class Group:
    """A parenthesized interval of endpoint positions (1-based, inclusive).

    Nested intervals are allowed; partially overlapping intervals are not.
    ``label`` is optional TeX (math-mode by default) placed over/under the group.
    """

    start: int
    end: int
    label: str | None = None


def _flatten_tree(tree: Any) -> list[Any]:
    """Return the leaves of a nested tuple/list parenthesization tree."""
    if isinstance(tree, (tuple, list)):
        leaves: list[Any] = []
        for child in tree:
            leaves.extend(_flatten_tree(child))
        return leaves
    return [tree]


def parenthesization_groups(
    tree: Any, *, include_root: bool = False
) -> tuple[list[Group], list[Any]]:
    """Convert a nested list/tuple tree to endpoint groups and ordered leaves.

    Example::

        parenthesization_groups(((r"x_1", r"x_2"), r"x_3"))
        # -> ([Group(1, 2)], [r"x_1", r"x_2", r"x_3"])

    Every nested tuple/list denotes a parenthesized subexpression. The outer
    root is omitted by default, since outermost parentheses are often implicit.
    Set ``include_root=True`` to draw it as well. A node with just one leaf is
    not drawn as a group.
    """
    leaves = _flatten_tree(tree)
    groups: list[Group] = []
    cursor = 1

    def visit(node: Any, is_root: bool = False) -> tuple[int, int]:
        nonlocal cursor
        if not isinstance(node, (tuple, list)):
            index = cursor
            cursor += 1
            return index, index
        if len(node) == 0:
            raise ValueError("A parenthesization tree cannot contain an empty group")
        start = cursor
        for child in node:
            visit(child, False)
        end = cursor - 1
        if end > start and (include_root or not is_root):
            groups.append(Group(start, end))
        return start, end

    visit(tree, True)
    # Sorting makes groups stable and gives deterministic rendering.
    groups.sort(key=lambda g: (g.end - g.start, g.start, g.end))
    return groups, leaves


def _coerce_group(group: Group | Sequence[Any]) -> Group:
    if isinstance(group, Group):
        return group
    if not isinstance(group, (tuple, list)) or len(group) not in (2, 3):
        raise TypeError("Each group must be Group(start, end, label) or (start, end[, label])")
    return Group(int(group[0]), int(group[1]), None if len(group) == 2 else group[2])


def _validate_groups(groups: Sequence[Group], n: int, where: str) -> list[Group]:
    result = list(groups)
    for group in result:
        if not (1 <= group.start < group.end <= n):
            raise ValueError(
                f"{where} group {group!r} must satisfy 1 <= start < end <= n={n}"
            )
    for idx, a in enumerate(result):
        for b in result[idx + 1 :]:
            overlap = max(a.start, b.start) <= min(a.end, b.end)
            nested = (a.start <= b.start and b.end <= a.end) or (
                b.start <= a.start and a.end <= b.end
            )
            if overlap and not nested:
                raise ValueError(
                    f"{where} groups {a!r} and {b!r} partially overlap; "
                    "a parenthesization must be nested or disjoint"
                )
            if (a.start, a.end) == (b.start, b.end):
                raise ValueError(f"Duplicate {where} group interval {a.start}:{a.end}")
    return result


class Braid(GeometryMixin):
    """A colored, labeled braid represented by an Artin generator word.

    Parameters
    ----------
    n:
        Number of strands (the braid arity); must be positive.
    word:
        Sequence of signed, 1-based generator indices. ``1`` is sigma_1,
        ``-2`` is sigma_2^{-1}, and so on. Entries are read top-to-bottom.
    input_labels, output_labels:
        Optional TeX labels at top and bottom ports. If only ``input_labels``
        is given, bottom labels are propagated along the strands according to
        the braid permutation. An explicit ``output_labels`` labels bottom
        *positions* exactly as given (useful when labeling source/target objects).
    strand_colors:
        Optional sequence of n colors, indexed by input strand, or a mapping
        keyed by 1-based input-strand index and/or its input label. Colors travel
        with strands. Fall back to ``color`` for unspecified entries.
    top_parenthesization, bottom_parenthesization:
        Nested tuples/lists describing the endpoint parenthesization. Leaves are
        ordered ports; each nested tuple/list draws a group. The outermost group
        is omitted by default. Leaf values also supply endpoint labels unless
        explicit labels are passed. For more control, use ``top_groups`` and
        ``bottom_groups`` with ``Group(start, end, label)``.
    color:
        Main/fallback TikZ color expression, e.g. ``'black'`` or ``'blue!70!black'``.

    Notes
    -----
    Positive-crossing convention is documented at the top of this module.
    Styling dimensions ``strand_sep``, ``layer_height``, and ``cluster_gap`` are in
    centimetres; ``line_width`` and ``crossing_gap`` are in points. Nested endpoint
    configurations automatically receive hierarchical horizontal spacing. Optional
    axis and boundary points are specified in the same TikZ coordinate system.
    """

    def __init__(
        self,
        n: int,
        word: Sequence[int] = (),
        *,
        input_labels: Sequence[Any] | None = None,
        output_labels: Sequence[Any] | None = None,
        strand_colors: Sequence[str | None] | Mapping[Any, str] | None = None,
        color: str = "black",
        positive_over: str = "left",
        top_groups: Sequence[Group | Sequence[Any]] | None = None,
        bottom_groups: Sequence[Group | Sequence[Any]] | None = None,
        top_parenthesization: Any | None = None,
        bottom_parenthesization: Any | None = None,
        include_root_parentheses: bool = False,
        label_mode: str = "math",
        strand_sep: float = 0.9,
        layer_height: float = 0.95,
        identity_height: float = 1.5,
        line_width: float = 1.15,
        crossing_gap: float = 0.85,
        background_color: str | None = "white",
        endpoint_dots: bool = False,
        show_generators: bool = False,
        baseline: str = "(braid-base)",
        group_spacing: float = 0.30,
        label_offset: float = 0.27,
        cluster_gap: float = 0.45,
        diagram_scale: float = 1.0,
        top_positions: Sequence[float] | None = None,
        bottom_positions: Sequence[float] | None = None,
        axis: bool = False,
        axis_y: float = 0.0,
        axis_extent: Sequence[float] | None = None,
        axis_color: str = "gray!60",
        axis_front: bool = False,
        boundary_points: Sequence[Mapping[str, Any] | Sequence[Any]] | None = None,
        annotations: Sequence[Mapping[str, Any] | Sequence[Any]] | None = None,
    ) -> None:
        if not isinstance(n, int) or n < 1:
            raise ValueError("n must be a positive integer")
        self.n = n
        self.word = tuple(int(g) for g in word)
        for g in self.word:
            if g == 0 or abs(g) >= n:
                raise ValueError(f"Generator {g} invalid for {n} strands; require 1 <= |g| < n")
        if positive_over not in ("left", "right"):
            raise ValueError("positive_over must be 'left' or 'right'")
        if label_mode not in ("math", "text"):
            raise ValueError("label_mode must be 'math' or 'text'")
        for name, value in (("strand_sep", strand_sep), ("layer_height", layer_height),
                            ("identity_height", identity_height), ("line_width", line_width),
                            ("group_spacing", group_spacing), ("label_offset", label_offset),
                            ("cluster_gap", cluster_gap), ("diagram_scale", diagram_scale)):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number")
        if not isinstance(crossing_gap, (int, float)) or crossing_gap < 0 or not math.isfinite(crossing_gap):
            raise ValueError("crossing_gap must be a non-negative finite number")

        top_tree_groups: list[Group] = []
        bottom_tree_groups: list[Group] = []
        top_leaves: list[Any] | None = None
        bottom_leaves: list[Any] | None = None
        self.top_parenthesization = top_parenthesization
        self.bottom_parenthesization = bottom_parenthesization
        self.include_root_parentheses = bool(include_root_parentheses)
        if top_parenthesization is not None:
            if top_groups:
                raise ValueError("Use top_parenthesization or top_groups, not both")
            top_tree_groups, top_leaves = parenthesization_groups(
                top_parenthesization, include_root=include_root_parentheses
            )
            top_groups = top_tree_groups
            if len(top_leaves) != n:
                raise ValueError(f"Top parenthesization has {len(top_leaves)} leaves, expected n={n}")
        if bottom_parenthesization is not None:
            if bottom_groups:
                raise ValueError("Use bottom_parenthesization or bottom_groups, not both")
            bottom_tree_groups, bottom_leaves = parenthesization_groups(
                bottom_parenthesization, include_root=include_root_parentheses
            )
            bottom_groups = bottom_tree_groups
            if len(bottom_leaves) != n:
                raise ValueError(f"Bottom parenthesization has {len(bottom_leaves)} leaves, expected n={n}")

        if input_labels is None and top_leaves is not None:
            input_labels = top_leaves
        if input_labels is not None:
            if len(input_labels) != n:
                raise ValueError(f"input_labels must have length n={n}")
            self.input_labels = tuple(input_labels)
        else:
            self.input_labels = None

        self._bottom_order = self._compute_bottom_order()
        if output_labels is None and bottom_leaves is not None:
            output_labels = bottom_leaves
        elif output_labels is None and self.input_labels is not None:
            output_labels = tuple(self.input_labels[i] for i in self._bottom_order)
        if output_labels is not None:
            if len(output_labels) != n:
                raise ValueError(f"output_labels must have length n={n}")
            self.output_labels = tuple(output_labels)
        else:
            self.output_labels = None

        self.color = str(color)
        self.positive_over = positive_over
        self.label_mode = label_mode
        self.top_groups = _validate_groups(
            [_coerce_group(g) for g in (top_groups or ())], n, "top"
        )
        self.bottom_groups = _validate_groups(
            [_coerce_group(g) for g in (bottom_groups or ())], n, "bottom"
        )
        if isinstance(strand_colors, Mapping):
            self.strand_colors: Sequence[str | None] | Mapping[Any, str] = dict(strand_colors)
        elif strand_colors is None:
            self.strand_colors = tuple([None] * n)
        else:
            if len(strand_colors) != n:
                raise ValueError(f"strand_colors must have length n={n}")
            self.strand_colors = tuple(strand_colors)
        self.strand_sep = float(strand_sep)
        self.layer_height = float(layer_height)
        self.identity_height = float(identity_height)
        self.line_width = float(line_width)
        self.crossing_gap = float(crossing_gap)
        self.background_color = background_color
        self.endpoint_dots = bool(endpoint_dots)
        self.show_generators = bool(show_generators)
        self.baseline = str(baseline)
        self.group_spacing = float(group_spacing)
        self.label_offset = float(label_offset)
        self.cluster_gap = float(cluster_gap)
        self.diagram_scale = float(diagram_scale)
        self.top_positions = self._validate_positions(top_positions, "top_positions")
        self.bottom_positions = self._validate_positions(bottom_positions, "bottom_positions")
        self.axis = bool(axis)
        if not isinstance(axis_y, (int, float)) or not math.isfinite(axis_y):
            raise ValueError("axis_y must be a finite number")
        self.axis_y = float(axis_y)
        if axis_extent is not None:
            if len(axis_extent) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in axis_extent) or axis_extent[0] >= axis_extent[1]:
                raise ValueError("axis_extent must be an increasing pair of finite numbers")
            self.axis_extent = (float(axis_extent[0]), float(axis_extent[1]))
        else:
            self.axis_extent = None
        self.axis_color = str(axis_color)
        self.axis_front = bool(axis_front)
        self.boundary_points = tuple(self._coerce_boundary_point(p) for p in (boundary_points or ()))
        self.annotations = tuple(self._coerce_annotation(a) for a in (annotations or ()))
        self._top_xs = self.top_positions or _tree_positions(self.top_parenthesization, self.n, self.strand_sep, self.cluster_gap)
        self._bottom_xs = self.bottom_positions or _tree_positions(self.bottom_parenthesization, self.n, self.strand_sep, self.cluster_gap)
        if len(self._top_xs) != self.n:
            raise ValueError(f"top_positions must have length n={self.n}")
        if len(self._bottom_xs) != self.n:
            raise ValueError(f"bottom_positions must have length n={self.n}")

    @staticmethod
    def _validate_positions(positions: Sequence[float] | None, name: str) -> tuple[float, ...] | None:
        if positions is None:
            return None
        values = tuple(float(v) for v in positions)
        if not values or not all(math.isfinite(v) for v in values):
            raise ValueError(f"{name} must contain finite coordinates")
        if any(a >= b for a, b in zip(values, values[1:])):
            raise ValueError(f"{name} must be strictly increasing")
        return values

    @staticmethod
    def _coerce_boundary_point(point: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
        if isinstance(point, Mapping):
            item = dict(point)
        elif isinstance(point, (tuple, list)) and 1 <= len(point) <= 3:
            item = {"x": point[0]}
            if len(point) >= 2:
                item["label"] = point[1]
            if len(point) >= 3:
                item["color"] = point[2]
        else:
            raise TypeError("A boundary point must be a mapping or (x[, label[, color]])")
        if "x" not in item and "port" not in item:
            raise ValueError("A boundary point requires either 'x' or 'port'")
        if "x" in item and not isinstance(item["x"], (int, float)):
            raise ValueError("Boundary point x must be numeric")
        if "port" in item and (not isinstance(item["port"], int) or item["port"] < 1):
            raise ValueError("Boundary point port must be a positive 1-based integer")
        item.setdefault("label", None)
        item.setdefault("color", "black")
        item.setdefault("radius", 0.045)
        return item

    def _coerce_annotation(self, annotation: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
        """Normalize an annotation on a top-identity strand at an integer crossing level."""
        if isinstance(annotation, Mapping):
            item = dict(annotation)
        elif isinstance(annotation, (tuple, list)) and len(annotation) in (3, 4):
            item = {"strand": annotation[0], "level": annotation[1], "label": annotation[2]}
            if len(annotation) == 4:
                item["color"] = annotation[3]
        else:
            raise TypeError("An annotation must be a mapping or (strand, level, label[, color])")
        if not isinstance(item.get("strand"), int) or not 1 <= item["strand"] <= self.n:
            raise ValueError(f"Annotation strand must be a 1-based index between 1 and n={self.n}")
        if not isinstance(item.get("level"), int) or not 0 <= item["level"] <= len(self.word):
            raise ValueError(f"Annotation level must be an integer from 0 to {len(self.word)}")
        if "label" not in item:
            raise ValueError("An annotation requires a label")
        item["label"] = str(item["label"])
        item["color"] = str(item.get("color") or self._strand_color(item["strand"] - 1))
        return item

    @property
    def permutation(self) -> tuple[int, ...]:
        """Input-strand identities at bottom positions, as 1-based indices."""
        return tuple(i + 1 for i in self._bottom_order)

    def compose(self, below: "Braid", *, check_labels: bool = True) -> "Braid":
        """Compose this braid vertically with ``below`` (this braid first).

        Generator words are concatenated in top-to-bottom order. The two objects
        must have equal arity; when both intermediate label lists or structured
        parenthesizations are specified, they must agree. Styling follows the
        strands from the top braid; use a fresh ``strand_colors`` override on the
        result when a composed diagram should have a different palette.
        """
        if not isinstance(below, Braid):
            raise TypeError("below must be a Braid")
        if self.n != below.n:
            raise ValueError(f"Cannot compose braids with arities {self.n} and {below.n}")
        if check_labels:
            if self.output_labels is not None and below.input_labels is not None and self.output_labels != below.input_labels:
                raise ValueError("Cannot compose braids: lower input labels do not match upper output labels")
            if self.bottom_parenthesization is not None and below.top_parenthesization is not None:
                if self.bottom_parenthesization != below.top_parenthesization:
                    raise ValueError("Cannot compose braids: intermediate parenthesizations do not match")
        kwargs: dict[str, Any] = {
            "n": self.n,
            "word": self.word + below.word,
            "input_labels": self.input_labels,
            "output_labels": below.output_labels,
            "strand_colors": [self._strand_color(i) for i in range(self.n)],
            "color": self.color,
            "positive_over": self.positive_over,
            "label_mode": self.label_mode,
            "top_parenthesization": self.top_parenthesization,
            "bottom_parenthesization": below.bottom_parenthesization,
            "top_groups": self.top_groups if self.top_parenthesization is None else None,
            "bottom_groups": below.bottom_groups if below.bottom_parenthesization is None else None,
            "include_root_parentheses": False,
            "strand_sep": self.strand_sep,
            "layer_height": self.layer_height,
            "identity_height": self.identity_height,
            "line_width": self.line_width,
            "crossing_gap": self.crossing_gap,
            "background_color": self.background_color,
            "endpoint_dots": self.endpoint_dots,
            "show_generators": self.show_generators,
            "baseline": self.baseline,
            "group_spacing": self.group_spacing,
            "label_offset": self.label_offset,
            "cluster_gap": self.cluster_gap,
            "diagram_scale": self.diagram_scale,
            "axis": self.axis,
            "axis_y": self.axis_y,
            "axis_extent": self.axis_extent,
            "axis_color": self.axis_color,
            "axis_front": self.axis_front,
            "boundary_points": self.boundary_points,
            "annotations": list(self.annotations) + [
                {
                    **annotation,
                    "strand": self._bottom_order[annotation["strand"] - 1] + 1,
                    "level": annotation["level"] + len(self.word),
                }
                for annotation in below.annotations
            ],
        }
        # Preserve custom endpoint positions only when no corresponding tree
        # exists. If a lower diagram has explicit output labels, retain them.
        if self.top_parenthesization is None:
            kwargs["top_positions"] = self.top_positions
        if below.bottom_parenthesization is None:
            kwargs["bottom_positions"] = below.bottom_positions
        if below.bottom_parenthesization is None and below.output_labels is not None:
            kwargs["output_labels"] = below.output_labels
        return Braid(**kwargs)

    def _compute_bottom_order(self) -> tuple[int, ...]:
        order = list(range(self.n))
        for g in self.word:
            i = abs(g) - 1
            order[i], order[i + 1] = order[i + 1], order[i]
        return tuple(order)

    def _strand_color(self, strand_id: int) -> str:
        colors = self.strand_colors
        if isinstance(colors, Mapping):
            label = None if self.input_labels is None else self.input_labels[strand_id]
            if strand_id + 1 in colors:
                candidate = colors[strand_id + 1]
            elif str(strand_id + 1) in colors:
                candidate = colors[str(strand_id + 1)]
            elif label in colors:
                candidate = colors[label]
            else:
                candidate = None
        else:
            candidate = colors[strand_id]
        return self.color if candidate is None else str(candidate)

    def standalone_tex(self, *, border: str = "4pt", document_class: str = "standalone") -> str:
        """Return a complete compilable LaTeX document containing the diagram."""
        return (
            f"\\documentclass[tikz,border={border}]{{{document_class}}}\n"
            "\\usepackage{xcolor}\n"
            "\\begin{document}\n"
            + self.tikz(inline=False)
            + "\n\\end{document}\n"
        )

    def write(self, path: str | Path, *, format: str = "inline", border: str = "4pt") -> Path:
        """Write ``inline`` (.tikz snippet), ``picture`` (.tex environment), or ``standalone`` TeX."""
        path = Path(path)
        if format == "inline":
            content = self.tikz(inline=True)
        elif format == "picture":
            content = self.tikz(inline=False)
        elif format == "standalone":
            content = self.standalone_tex(border=border)
        else:
            raise ValueError("format must be 'inline', 'picture', or 'standalone'")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        return path

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly description (for the simple CLI input format)."""
        if isinstance(self.strand_colors, Mapping):
            colors: Any = {str(k): v for k, v in self.strand_colors.items()}
        else:
            colors = list(self.strand_colors)
        return {
            "n": self.n,
            "word": list(self.word),
            "input_labels": None if self.input_labels is None else list(self.input_labels),
            "output_labels": None if self.output_labels is None else list(self.output_labels),
            "strand_colors": colors,
            "color": self.color,
            "positive_over": self.positive_over,
            "top_groups": [] if self.top_parenthesization is not None else [[g.start, g.end, g.label] for g in self.top_groups],
            "bottom_groups": [] if self.bottom_parenthesization is not None else [[g.start, g.end, g.label] for g in self.bottom_groups],
            "label_mode": self.label_mode,
            "baseline": self.baseline,
            "group_spacing": self.group_spacing,
            "label_offset": self.label_offset,
            "include_root_parentheses": self.include_root_parentheses,
            "strand_sep": self.strand_sep,
            "layer_height": self.layer_height,
            "identity_height": self.identity_height,
            "line_width": self.line_width,
            "crossing_gap": self.crossing_gap,
            "background_color": self.background_color,
            "endpoint_dots": self.endpoint_dots,
            "show_generators": self.show_generators,
            "cluster_gap": self.cluster_gap,
            "diagram_scale": self.diagram_scale,
            "top_parenthesization": self.top_parenthesization,
            "bottom_parenthesization": self.bottom_parenthesization,
            "top_positions": self.top_positions,
            "bottom_positions": self.bottom_positions,
            "axis": self.axis,
            "axis_y": self.axis_y,
            "axis_extent": self.axis_extent,
            "axis_color": self.axis_color,
            "axis_front": self.axis_front,
            "boundary_points": list(self.boundary_points),
            "annotations": list(self.annotations),
        }


def from_dict(config: Mapping[str, Any]) -> Braid:
    """Create a Braid from a JSON-like configuration dictionary."""
    allowed = {
        "n", "word", "input_labels", "output_labels", "strand_colors", "color",
        "positive_over", "top_groups", "bottom_groups", "top_parenthesization",
        "bottom_parenthesization", "include_root_parentheses", "label_mode", "strand_sep",
        "layer_height", "identity_height", "line_width", "crossing_gap", "background_color",
        "endpoint_dots", "show_generators", "baseline", "group_spacing", "label_offset",
        "cluster_gap", "diagram_scale", "top_positions", "bottom_positions", "axis", "axis_y", "axis_extent",
        "axis_color", "axis_front", "boundary_points", "annotations",
    }
    unexpected = set(config) - allowed
    if unexpected:
        raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unexpected))}")
    return Braid(**dict(config))


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Render a braid JSON description as TikZ/LaTeX.")
    parser.add_argument("config", nargs="?", help="JSON configuration file")
    parser.add_argument("-o", "--output", help="output file (stdout if omitted)")
    parser.add_argument("--format", choices=("inline", "picture", "standalone"), default="inline")
    parser.add_argument("--border", default="4pt", help="standalone document border, e.g. 4pt")
    args = parser.parse_args()
    if not args.config:
        parser.error("provide a JSON configuration file")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    braid = from_dict(config)
    if args.output:
        braid.write(args.output, format=args.format, border=args.border)
    else:
        if args.format == "inline":
            print(braid.tikz(inline=True))
        elif args.format == "picture":
            print(braid.tikz(inline=False))
        else:
            print(braid.standalone_tex(border=args.border))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
