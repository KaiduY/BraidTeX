"""TikZ vector geometry for BraidTeX's structured braid model.

Each crossing path has vertical endpoint tangents. Monotone fan paths connect
hierarchically spaced boundary ports to standard braid lanes without introducing
extra crossings. The model and its permutation remain independent of these paths.
"""
from __future__ import annotations
from typing import Any, Sequence

def _tex_num(x: float) -> str:
    # Keep snippets neat and deterministic without scientific notation.
    return f"{x:.5f}".rstrip("0").rstrip(".") or "0"


def _tex_label(label: Any, mode: str) -> str:
    if label is None:
        return ""
    text = str(label)
    if mode == "math":
        return f"${text}$"
    if mode == "text":
        return text
    raise ValueError("label_mode must be 'math' or 'text'")


class GeometryMixin:
    def _group_levels(self, groups: Sequence[Any]) -> dict[Any, int]:
        """Nest outer groups farther from the endpoint row than inner groups."""
        levels: dict[Any, int] = {}
        # Compute narrowest intervals first, so every contained group's level exists.
        for group in sorted(groups, key=lambda g: (g.end - g.start, g.start)):
            children = [
                other for other in groups
                if (group.start <= other.start and other.end <= group.end)
                and (group.start, group.end) != (other.start, other.end)
            ]
            levels[group] = 0 if not children else 1 + max(levels[c] for c in children)
        return levels

    def _group_tex(self, group: Any, y: float, top: bool, level: int, xs: Sequence[float]) -> list[str]:
        x0 = xs[group.start - 1] - 0.17
        x1 = xs[group.end - 1] + 0.17
        xm = (x0 + x1) / 2
        curl = min(0.13, max(0.055, (x1 - x0) * 0.10))
        peak = 0.16
        if top:
            path = (
                f"({ _tex_num(x0)},{_tex_num(y)}) .. controls "
                f"({ _tex_num(x0)},{_tex_num(y + peak*0.75)}) and "
                f"({ _tex_num(xm - curl)},{_tex_num(y + peak*0.65)}) .. "
                f"({ _tex_num(xm)},{_tex_num(y + peak)}) .. controls "
                f"({ _tex_num(xm + curl)},{_tex_num(y + peak*0.65)}) and "
                f"({ _tex_num(x1)},{_tex_num(y + peak*0.75)}) .. "
                f"({ _tex_num(x1)},{_tex_num(y)})"
            )
            lines = [f"\\draw[line width=0.55pt] {path};"]
            if group.label is not None:
                label = _tex_label(group.label, self.label_mode)
                lines.append(
                    f"\\node[inner sep=1pt,anchor=south] at ({_tex_num(xm)},{_tex_num(y + peak + 0.015)}) {{{label}}};"
                )
        else:
            path = (
                f"({ _tex_num(x0)},{_tex_num(y)}) .. controls "
                f"({ _tex_num(x0)},{_tex_num(y - peak*0.75)}) and "
                f"({ _tex_num(xm - curl)},{_tex_num(y - peak*0.65)}) .. "
                f"({ _tex_num(xm)},{_tex_num(y - peak)}) .. controls "
                f"({ _tex_num(xm + curl)},{_tex_num(y - peak*0.65)}) and "
                f"({ _tex_num(x1)},{_tex_num(y - peak*0.75)}) .. "
                f"({ _tex_num(x1)},{_tex_num(y)})"
            )
            lines = [f"\\draw[line width=0.55pt] {path};"]
            if group.label is not None:
                label = _tex_label(group.label, self.label_mode)
                lines.append(
                    f"\\node[inner sep=1pt,anchor=north] at ({_tex_num(xm)},{_tex_num(y - peak - 0.015)}) {{{label}}};"
                )
        return lines

    def _diagram_body(self) -> tuple[list[str], float, float]:
        """Build a single coherent TikZ geometry with monotone endpoint fans.

        Endpoint configurations determine the top/bottom x-coordinates. Ordered,
        crossing-free fan segments connect those coordinates to the standard lanes;
        every crossing segment has vertical endpoint tangents, so adjacent segments
        meet continuously and with matching first derivatives.
        """
        n, length = self.n, len(self.word)
        core_top = max(length * self.layer_height, self.identity_height if length == 0 else 0.0)
        core_bottom = 0.0
        align_h = max(0.48, min(0.85, self.layer_height * 0.62))
        y_top = core_top + align_h
        y_bottom = core_bottom - align_h
        top_xs = list(self._top_xs)
        bottom_xs = list(self._bottom_xs)
        lane_xs = [i * self.strand_sep for i in range(n)]
        point_xs = [float(point["x"]) for point in self.boundary_points if "x" in point]
        all_xs = top_xs + bottom_xs + lane_xs + point_xs
        min_x, max_x = min(all_xs), max(all_xs)
        axis_min, axis_max = self.axis_extent or (min_x - 0.35, max_x + 0.35)
        lines: list[str] = []
        front_axis: list[str] = []
        center_x = (min(top_xs[0], bottom_xs[0], lane_xs[0]) + max(top_xs[-1], bottom_xs[-1], lane_xs[-1])) / 2
        lines.append(f"\\coordinate (braid-base) at ({_tex_num(center_x)},{_tex_num(y_bottom)});")

        def axis_tex(destination: list[str]) -> None:
            if not self.axis:
                return
            destination.append(
                f"\\draw[draw={self.axis_color},line width=0.45pt] "
                f"({_tex_num(axis_min)},{_tex_num(self.axis_y)}) -- ({_tex_num(axis_max)},{_tex_num(self.axis_y)});"
            )
            for point in self.boundary_points:
                if "port" in point:
                    port = point["port"]
                    if port > n:
                        raise ValueError(f"Boundary point port {port} exceeds strand count n={n}")
                    px = top_xs[port - 1]
                else:
                    px = float(point["x"])
                color = point["color"]
                radius = float(point["radius"])
                destination.append(
                    f"\\fill[draw={color},fill={color}] ({_tex_num(px)},{_tex_num(self.axis_y)}) "
                    f"circle[radius={_tex_num(radius)}];"
                )
                if point.get("label") is not None:
                    label = _tex_label(point["label"], self.label_mode)
                    destination.append(
                        f"\\node[anchor=south,inner sep=1pt] at ({_tex_num(px)},{_tex_num(self.axis_y + radius + 0.025)}) {{{label}}};"
                    )

        # Axis behind strands unless explicitly requested in front.
        if not self.axis_front:
            axis_tex(lines)

        # Smooth, order-preserving fan from the structural input layout to braid lanes.
        for pos in range(n):
            x0, x1 = top_xs[pos], lane_xs[pos]
            c1y = core_top + align_h * 0.62
            c2y = core_top + align_h * 0.38
            path = (
                f"({_tex_num(x0)},{_tex_num(y_top)}) .. controls "
                f"({_tex_num(x0)},{_tex_num(c1y)}) and ({_tex_num(x1)},{_tex_num(c2y)}) .. "
                f"({_tex_num(x1)},{_tex_num(core_top)})"
            )
            lines.append(f"\\draw[draw={self._strand_color(pos)},line width={_tex_num(self.line_width)}pt] {path};")

        order = list(range(n))
        if length == 0:
            for pos, strand_id in enumerate(order):
                lines.append(
                    f"\\draw[draw={self._strand_color(strand_id)},line width={_tex_num(self.line_width)}pt] "
                    f"({_tex_num(lane_xs[pos])},{_tex_num(core_top)}) -- ({_tex_num(lane_xs[pos])},{_tex_num(core_bottom)});"
                )
        else:
            for step, generator in enumerate(self.word):
                yt = length * self.layer_height - step * self.layer_height
                yb = yt - self.layer_height
                i = abs(generator) - 1
                left_id, right_id = order[i], order[i + 1]

                for pos, strand_id in enumerate(order):
                    if pos in (i, i + 1):
                        continue
                    lines.append(
                        f"\\draw[draw={self._strand_color(strand_id)},line width={_tex_num(self.line_width)}pt] "
                        f"({_tex_num(lane_xs[pos])},{_tex_num(yt)}) -- ({_tex_num(lane_xs[pos])},{_tex_num(yb)});"
                    )

                def curve(x_start: float, x_end: float) -> str:
                    c1y = yt - self.layer_height * 0.31
                    c2y = yb + self.layer_height * 0.31
                    return (
                        f"({_tex_num(x_start)},{_tex_num(yt)}) .. controls "
                        f"({_tex_num(x_start)},{_tex_num(c1y)}) and ({_tex_num(x_end)},{_tex_num(c2y)}) .. "
                        f"({_tex_num(x_end)},{_tex_num(yb)})"
                    )

                left_path = curve(lane_xs[i], lane_xs[i + 1])
                right_path = curve(lane_xs[i + 1], lane_xs[i])
                left_is_over = generator > 0 if self.positive_over == "left" else generator < 0
                if left_is_over:
                    over_id, under_id = left_id, right_id
                    over_path, under_path = left_path, right_path
                else:
                    over_id, under_id = right_id, left_id
                    over_path, under_path = right_path, left_path
                lines.append(
                    f"\\draw[draw={self._strand_color(under_id)},line width={_tex_num(self.line_width)}pt] {under_path};"
                )
                if self.background_color:
                    halo_width = self.line_width + 2 * self.crossing_gap
                    lines.append(
                        f"\\draw[draw={self.background_color},line width={_tex_num(halo_width)}pt] {over_path};"
                    )
                lines.append(
                    f"\\draw[draw={self._strand_color(over_id)},line width={_tex_num(self.line_width)}pt] {over_path};"
                )
                if self.show_generators:
                    sign = "" if generator > 0 else "^{-1}"
                    lines.append(
                        f"\\node[anchor=east,inner sep=1pt,font=\\scriptsize] at "
                        f"({_tex_num(lane_xs[0] - 0.18)},{_tex_num((yt+yb)/2)}) {{$\\sigma_{{{i+1}}}{sign}$}};"
                    )
                order[i], order[i + 1] = order[i + 1], order[i]

        # Smooth fan from braid lanes back to the independent output configuration.
        for pos, strand_id in enumerate(order):
            x0, x1 = lane_xs[pos], bottom_xs[pos]
            c1y = core_bottom - align_h * 0.38
            c2y = core_bottom - align_h * 0.62
            path = (
                f"({_tex_num(x0)},{_tex_num(core_bottom)}) .. controls "
                f"({_tex_num(x0)},{_tex_num(c1y)}) and ({_tex_num(x1)},{_tex_num(c2y)}) .. "
                f"({_tex_num(x1)},{_tex_num(y_bottom)})"
            )
            lines.append(f"\\draw[draw={self._strand_color(strand_id)},line width={_tex_num(self.line_width)}pt] {path};")

        if self.endpoint_dots:
            for pos, strand_id in enumerate(range(n)):
                lines.append(
                    f"\\fill[draw=none,fill={self._strand_color(strand_id)}] "
                    f"({_tex_num(top_xs[pos])},{_tex_num(y_top)}) circle[radius=0.035];"
                )
            for pos, strand_id in enumerate(self._bottom_order):
                lines.append(
                    f"\\fill[draw=none,fill={self._strand_color(strand_id)}] "
                    f"({_tex_num(bottom_xs[pos])},{_tex_num(y_bottom)}) circle[radius=0.035];"
                )

        if self.input_labels is not None:
            for pos, label_value in enumerate(self.input_labels):
                if label_value is None:
                    continue
                label = _tex_label(label_value, self.label_mode)
                lines.append(
                    f"\\node[inner sep=1pt,anchor=south] at "
                    f"({_tex_num(top_xs[pos])},{_tex_num(y_top + self.label_offset)}) {{{label}}};"
                )
        # Annotations reference input-strand identities and a horizontal level
        # counted from the top (0 before any generator, len(word) after all).
        for annotation in self.annotations:
            order_at_level = list(range(n))
            for generator in self.word[:annotation["level"]]:
                index = abs(generator) - 1
                order_at_level[index], order_at_level[index + 1] = order_at_level[index + 1], order_at_level[index]
            strand_id = annotation["strand"] - 1
            position = order_at_level.index(strand_id)
            x_annot = lane_xs[position] + 0.12
            y_annot = (core_top if length == 0 else
                       length * self.layer_height - annotation["level"] * self.layer_height)
            label = _tex_label(annotation["label"], self.label_mode)
            lines.append(
                f"\\node[anchor=west,inner sep=1pt,font=\\scriptsize,text={annotation['color']}] at "
                f"({_tex_num(x_annot)},{_tex_num(y_annot)}) {{{label}}};"
            )

        if self.output_labels is not None:
            for pos, label_value in enumerate(self.output_labels):
                if label_value is None:
                    continue
                label = _tex_label(label_value, self.label_mode)
                lines.append(
                    f"\\node[inner sep=1pt,anchor=north] at "
                    f"({_tex_num(bottom_xs[pos])},{_tex_num(y_bottom - self.label_offset)}) {{{label}}};"
                )

        top_start = y_top + (self.label_offset + 0.25 if self.input_labels is not None else 0.28)
        bottom_start = y_bottom - (self.label_offset + 0.25 if self.output_labels is not None else 0.28)
        top_levels = self._group_levels(self.top_groups)
        bottom_levels = self._group_levels(self.bottom_groups)
        for group in self.top_groups:
            y = top_start + top_levels[group] * self.group_spacing
            lines.extend(self._group_tex(group, y, True, top_levels[group], top_xs))
        for group in self.bottom_groups:
            y = bottom_start - bottom_levels[group] * self.group_spacing
            lines.extend(self._group_tex(group, y, False, bottom_levels[group], bottom_xs))

        if self.axis_front:
            axis_tex(front_axis)
            lines.extend(front_axis)
        return lines, y_top, y_bottom

    def tikz(self, *, inline: bool = True) -> str:
        """Return a TikZ snippet.

        ``inline=True`` returns a single ``\\tikz{...}`` command that can be
        inserted directly in inline/display math. ``inline=False`` returns a
        ``tikzpicture`` environment for use as a figure or inside other TeX.
        """
        body, _, _ = self._diagram_body()
        options = "x=1cm,y=1cm,line cap=round,line join=round"
        if self.diagram_scale != 1.0:
            options += f",scale={_tex_num(self.diagram_scale)},transform shape"
        if inline:
            opts = options + f",baseline={self.baseline}"
            return "\\tikz[" + opts + "]{\n" + "\n".join(body) + "\n}"
        return "\\begin{tikzpicture}[" + options + "]\n" + "\n".join(body) + "\n\\end{tikzpicture}"


