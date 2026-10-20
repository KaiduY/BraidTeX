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

    @staticmethod
    def _lerp_point(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    @classmethod
    def _split_cubic(cls, points: Sequence[tuple[float, float]], t: float):
        p0, p1, p2, p3 = points
        p01 = cls._lerp_point(p0, p1, t)
        p12 = cls._lerp_point(p1, p2, t)
        p23 = cls._lerp_point(p2, p3, t)
        p012 = cls._lerp_point(p01, p12, t)
        p123 = cls._lerp_point(p12, p23, t)
        p0123 = cls._lerp_point(p012, p123, t)
        return (p0, p01, p012, p0123), (p0123, p123, p23, p3)

    @classmethod
    def _cubic_subsegment(cls, points: Sequence[tuple[float, float]], t0: float, t1: float):
        """Return an exact cubic Bézier subcurve on the parameter interval [t0,t1]."""
        if not (0.0 <= t0 < t1 <= 1.0):
            raise ValueError("Bezier subsegment requires 0 <= t0 < t1 <= 1")
        left, _ = cls._split_cubic(points, t1)
        _, segment = cls._split_cubic(left, t0 / t1)
        return segment

    @staticmethod
    def _curve_points(x0: float, x1: float, y0: float, y1: float, height: float):
        """Crossing cubic with vertical endpoint tangents and a smooth lateral shift."""
        bend = 0.285 * height
        return (
            (x0, y0),
            (x0, y0 - bend),
            (x1, y1 + bend),
            (x1, y1),
        )

    @staticmethod
    def _curve_tex(points: Sequence[tuple[float, float]], *, dx: float = 0.0) -> str:
        p0, p1, p2, p3 = points
        return (
            f"({_tex_num(p0[0] + dx)},{_tex_num(p0[1])}) .. controls "
            f"({_tex_num(p1[0] + dx)},{_tex_num(p1[1])}) and "
            f"({_tex_num(p2[0] + dx)},{_tex_num(p2[1])}) .. "
            f"({_tex_num(p3[0] + dx)},{_tex_num(p3[1])})"
        )

    def _diagram_body(self) -> tuple[list[str], float, float]:
        """Render coherent strand paths, then locally resolve their crossings.

        Each input strand is emitted as one continuous TikZ path.  Crossing
        knockouts are short exact Bézier subsegments of the overpassing path,
        rather than white strokes along the entire crossing arc.  This keeps
        neighboring strands intact and makes joins C1-smooth by construction.
        """
        n, length = self.n, len(self.word)
        core_top = sum(self.layer_heights) + sum(self.level_gaps)
        core_bottom = 0.0
        align_scale = self.layer_height if not self.layer_heights else min(self.layer_heights)
        align_h = max(0.42, min(0.85, align_scale * 0.62))
        y_top = core_top + align_h
        y_bottom = core_bottom - align_h
        top_xs = list(self._top_xs)
        bottom_xs = list(self._bottom_xs)
        lane_xs = [i * self.strand_sep for i in range(n)]
        point_xs = [float(point["x"]) for point in self.boundary_points if "x" in point]
        all_xs = top_xs + bottom_xs + lane_xs + point_xs
        min_x, max_x = min(all_xs), max(all_xs)
        axis_min, axis_max = self.axis_extent or (min_x - 0.35, max_x + 0.35)
        frame_left, frame_right = min_x - 0.35, max_x + 0.35
        center_x = (min(top_xs[0], bottom_xs[0], lane_xs[0]) +
                    max(top_xs[-1], bottom_xs[-1], lane_xs[-1])) / 2
        lines: list[str] = []
        front_axis: list[str] = []

        # Level k is the top of the straight gap before generator k+1.  The
        # strand order is tracked by persistent input identity, never relabeled
        # from a current left-to-right position.
        level_y = [core_top]
        for i in range(length):
            level_y.append(level_y[-1] - self.level_gaps[i] - self.layer_heights[i])
        orders_by_level = [list(range(n))]
        order = list(range(n))
        for generator in self.word:
            idx = abs(generator) - 1
            order[idx], order[idx + 1] = order[idx + 1], order[idx]
            orders_by_level.append(order.copy())

        top_levels = self._group_levels(self.top_groups)
        bottom_levels = self._group_levels(self.bottom_groups)
        top_label_extent = self.label_offset if self.input_labels is not None else 0.0
        bottom_label_extent = self.label_offset if self.output_labels is not None else 0.0
        top_group_start = y_top + (self.label_offset + 0.25 if self.input_labels is not None else 0.28)
        bottom_group_start = y_bottom - (self.label_offset + 0.25 if self.output_labels is not None else 0.28)
        if self.top_groups:
            top_label_extent = max(
                top_label_extent,
                top_group_start - y_top + max(top_levels.values(), default=0) * self.group_spacing + 0.34,
            )
        if self.bottom_groups:
            bottom_label_extent = max(
                bottom_label_extent,
                y_bottom - bottom_group_start + max(bottom_levels.values(), default=0) * self.group_spacing + 0.34,
            )
        visual_top = y_top + top_label_extent
        visual_bottom = y_bottom - bottom_label_extent
        if self.axis:
            visual_top = max(visual_top, self.axis_y + 0.12)
            visual_bottom = min(visual_bottom, self.axis_y - 0.12)
        baseline_y = (visual_top + visual_bottom) / 2
        lines.append(f"\\coordinate (braid-base) at ({_tex_num(center_x)},{_tex_num(y_bottom)});")
        lines.append(f"\\coordinate (braid-center) at ({_tex_num(center_x)},{_tex_num(baseline_y)});")

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
                        f"\\node[anchor=south,inner sep=1pt] at "
                        f"({_tex_num(px)},{_tex_num(self.axis_y + radius + 0.025)}) {{{label}}};"
                    )

        def frame_tex() -> list[str]:
            frame = self.frame
            if frame is None:
                return []
            out: list[str] = []
            style = f"draw={frame.axis_color},line width={_tex_num(frame.axis_width)}pt"
            if frame.top_axis:
                out.append(f"\\draw[{style},->] ({_tex_num(frame_left)},{_tex_num(y_top)}) -- ({_tex_num(frame_right)},{_tex_num(y_top)});")
            if frame.bottom_axis:
                out.append(f"\\draw[{style},->] ({_tex_num(frame_left)},{_tex_num(y_bottom)}) -- ({_tex_num(frame_right)},{_tex_num(y_bottom)});")
            if frame.left_axis:
                out.append(f"\\draw[{style},->] ({_tex_num(frame_left)},{_tex_num(y_top)}) -- ({_tex_num(frame_left)},{_tex_num(y_bottom)});")
            if frame.right_boundary:
                out.append(
                    f"\\draw[{frame.boundary_style},line width={_tex_num(frame.boundary_width)}pt] "
                    f"({_tex_num(frame_right)},{_tex_num(y_top)}) -- ({_tex_num(frame_right)},{_tex_num(y_bottom)});"
                )
            top_tick_positions = list(frame.top_ticks)
            bottom_tick_positions = list(frame.bottom_ticks)
            for port in frame.top_tick_ports:
                if port > n:
                    raise ValueError(f"Top frame tick port {port} exceeds strand count n={n}")
                top_tick_positions.append(top_xs[port - 1])
            for port in frame.bottom_tick_ports:
                if port > n:
                    raise ValueError(f"Bottom frame tick port {port} exceeds strand count n={n}")
                bottom_tick_positions.append(bottom_xs[port - 1])
            for x in top_tick_positions:
                out.append(f"\\draw[{style}] ({_tex_num(x)},{_tex_num(y_top-frame.tick_half_height)}) -- ({_tex_num(x)},{_tex_num(y_top+frame.tick_half_height)});")
            for x in bottom_tick_positions:
                out.append(f"\\draw[{style}] ({_tex_num(x)},{_tex_num(y_bottom-frame.tick_half_height)}) -- ({_tex_num(x)},{_tex_num(y_bottom+frame.tick_half_height)});")
            for separator in frame.separators:
                if separator.level > length:
                    raise ValueError(f"Separator level {separator.level} exceeds braid level count {length}")
                yy = level_y[separator.level] - separator.offset_down
                out.append(
                    f"\\draw[{separator.style},line width={_tex_num(separator.line_width)}pt] "
                    f"({_tex_num(frame_left)},{_tex_num(yy)}) -- ({_tex_num(frame_right)},{_tex_num(yy)});"
                )
                tick_positions = list(separator.ticks)
                for port in separator.tick_ports:
                    if port > n:
                        raise ValueError(f"Separator tick port {port} exceeds strand count n={n}")
                    tick_positions.append(lane_xs[port - 1])
                for x in tick_positions:
                    out.append(
                        f"\\draw[draw={frame.axis_color},line width={_tex_num(frame.axis_width)}pt] "
                        f"({_tex_num(x)},{_tex_num(yy-frame.tick_half_height)}) -- ({_tex_num(x)},{_tex_num(yy+frame.tick_half_height)});"
                    )
            return out

        # Frame and axis are behind the actual braid.  An annotation connector's
        # default layer is also behind strands, so an intersection is never
        # mistaken for an additional braid crossing.  Endpoint nodes are redrawn
        # after strands so that the connector's attachments remain visible.
        lines.extend(frame_tex())
        if not self.axis_front:
            axis_tex(lines)

        connector_data = []
        for connector in self.connectors:
            if not connector.visible:
                continue
            if connector.offset_down > self.level_gaps[connector.level] + 1e-8:
                raise ValueError(
                    f"Connector at level {connector.level} has offset_down={connector.offset_down:g}, "
                    f"but the available straight gap is {self.level_gaps[connector.level]:g}; "
                    "increase that level gap or move the connector to another level"
                )
            order_at = orders_by_level[connector.level]
            pos_a = order_at.index(connector.strand_a - 1)
            pos_b = order_at.index(connector.strand_b - 1)
            xa, xb = lane_xs[pos_a], lane_xs[pos_b]
            yy = level_y[connector.level] - connector.offset_down
            connector_data.append((connector, xa, xb, yy))
            if connector.layer == "back":
                lines.append(
                    f"\\draw[draw={connector.color},line width={_tex_num(connector.line_width)}pt] "
                    f"({_tex_num(xa)},{_tex_num(yy)}) -- ({_tex_num(xb)},{_tex_num(yy)});"
                )

        # Geometry is shared across semantics: a segment list is built for each
        # strand identity, then emitted as one continuous TikZ path.  This avoids
        # independent arc joins and guarantees a vertical tangent at each port.
        def add_line(segments, x: float, y: float) -> None:
            segments.append(("line", (x, y)))

        def add_curve(segments, cubic) -> None:
            segments.append(("curve", tuple(cubic)))

        strand_segments: dict[int, list[tuple[str, Any]]] = {sid: [] for sid in range(n)}
        crossing_records = []
        for step, generator in enumerate(self.word):
            i = abs(generator) - 1
            yt = level_y[step] - self.level_gaps[step]
            yb = level_y[step + 1]
            left_id, right_id = orders_by_level[step][i], orders_by_level[step][i + 1]
            left_is_over = generator > 0 if self.positive_over == "left" else generator < 0
            over_id = left_id if left_is_over else right_id
            over_start = lane_xs[i] if left_is_over else lane_xs[i + 1]
            over_end = lane_xs[i + 1] if left_is_over else lane_xs[i]
            over_cubic = self._curve_points(over_start, over_end, yt, yb, self.layer_heights[step])
            crossing_records.append((step, generator, over_id, over_cubic))

        def add_segment_path(segments, start_x, start_y, *, x_offset: float = 0.0) -> str:
            path = f"({_tex_num(start_x+x_offset)},{_tex_num(start_y)})"
            for kind, data in segments:
                if kind == "line":
                    x, y = data
                    path += f" -- ({_tex_num(x+x_offset)},{_tex_num(y)})"
                else:
                    p0, p1, p2, p3 = data
                    path += (
                        f" .. controls ({_tex_num(p1[0]+x_offset)},{_tex_num(p1[1])}) and "
                        f"({_tex_num(p2[0]+x_offset)},{_tex_num(p2[1])}) .. "
                        f"({_tex_num(p3[0]+x_offset)},{_tex_num(p3[1])})"
                    )
            return path

        for strand_id in range(n):
            segments = strand_segments[strand_id]
            # Input fan: boundary point -> first lane, with vertical endpoint tangents.
            x0, x1 = top_xs[strand_id], lane_xs[strand_id]
            c1y = y_top - align_h * 0.38
            c2y = core_top + align_h * 0.38
            add_curve(segments, ((x0, y_top), (x0, c1y), (x1, c2y), (x1, core_top)))

            if length == 0:
                # Identity braid: its whole component is one continuous vertical segment.
                add_line(segments, lane_xs[strand_id], core_bottom)
            else:
                for step, generator in enumerate(self.word):
                    yt = level_y[step] - self.level_gaps[step]
                    yb = level_y[step + 1]
                    order_at = orders_by_level[step]
                    position = order_at.index(strand_id)
                    x_here = lane_xs[position]
                    if self.level_gaps[step] > 1e-10:
                        add_line(segments, x_here, yt)
                    i = abs(generator) - 1
                    left_id, right_id = order_at[i], order_at[i + 1]
                    height = self.layer_heights[step]
                    if strand_id == left_id:
                        add_curve(segments, self._curve_points(lane_xs[i], lane_xs[i+1], yt, yb, height))
                    elif strand_id == right_id:
                        add_curve(segments, self._curve_points(lane_xs[i+1], lane_xs[i], yt, yb, height))
                    else:
                        add_line(segments, x_here, yb)
                if self.level_gaps[length] > 1e-10:
                    final_pos = orders_by_level[-1].index(strand_id)
                    add_line(segments, lane_xs[final_pos], core_bottom)

            # Output fan: final lane -> output port associated with this strand identity.
            output_pos = orders_by_level[-1].index(strand_id)
            x0, x1 = lane_xs[output_pos], bottom_xs[output_pos]
            c1y = core_bottom - align_h * 0.38
            c2y = y_bottom + align_h * 0.38
            add_curve(segments, ((x0, core_bottom), (x0, c1y), (x1, c2y), (x1, y_bottom)))
            path = add_segment_path(segments, top_xs[strand_id], y_top)
            lines.append(
                f"\\draw[draw={self._strand_color(strand_id)},line width={_tex_num(self.line_width)}pt," 
                f"line cap=round,line join=round] {path};"
            )

        # Resolve each crossing locally.  The knockout is only a short exact
        # subcurve around t=1/2, so it masks the understrand at the intersection
        # without whitening neighboring vertical pieces or other crossing layers.
        for step, generator, over_id, over_cubic in crossing_records:
            crossing_segment = self._cubic_subsegment(over_cubic, 0.482, 0.518)
            if self.background_color:
                halo_width = self.line_width + 2 * self.crossing_gap
                halo = self._curve_tex(crossing_segment)
                lines.append(
                    f"\\draw[draw={self.background_color},line width={_tex_num(halo_width)}pt," 
                    f"line cap=round,line join=round] {halo};"
                )
            over = self._curve_tex(crossing_segment)
            lines.append(
                f"\\draw[draw={self._strand_color(over_id)},line width={_tex_num(self.line_width)}pt," 
                f"line cap=round,line join=round] {over};"
            )
            if self.show_generators:
                i = abs(generator) - 1
                sign = "" if generator > 0 else "^{-1}"
                y_mid = (level_y[step] - self.level_gaps[step] + level_y[step + 1]) / 2
                lines.append(
                    f"\\node[anchor=east,inner sep=1pt,font=\\scriptsize] at "
                    f"({_tex_num(lane_xs[0] - 0.18)},{_tex_num(y_mid)}) {{$\\sigma_{{{i+1}}}{sign}$}};"
                )

        # Connectors are explicit annotation lines, not braid crossings.  Back-layer
        # lines were drawn underneath; front-layer lines are drawn after strands.
        for connector, xa, xb, yy in connector_data:
            if connector.layer == "front":
                lines.append(
                    f"\\draw[draw={connector.color},line width={_tex_num(connector.line_width)}pt] "
                    f"({_tex_num(xa)},{_tex_num(yy)}) -- ({_tex_num(xb)},{_tex_num(yy)});"
                )
        for connector, xa, xb, yy in connector_data:
            if connector.nodes and connector.node_radius > 0:
                for xx in (xa, xb):
                    lines.append(f"\\fill[draw={connector.color},fill={connector.color}] ({_tex_num(xx)},{_tex_num(yy)}) circle[radius={_tex_num(connector.node_radius)}];")

        # Auxiliary trajectories are non-topological annotations.  Following a
        # strand now uses the exact strand segment model and translates it by the
        # requested horizontal offset, rather than fitting a new smooth plot through
        # just the generator endpoints (which could cut randomly through crossings).
        for auxiliary in self.auxiliary_paths:
            if not auxiliary.visible:
                continue
            if auxiliary.points:
                pts = list(auxiliary.points)
                coordinates = " ".join(f"({_tex_num(x)},{_tex_num(y)})" for x, y in pts)
                if len(pts) >= 3:
                    path_code = f"plot[smooth] coordinates {{{coordinates}}}"
                else:
                    path_code = " -- ".join(f"({_tex_num(x)},{_tex_num(y)})" for x, y in pts)
            else:
                sid = auxiliary.follow_strand - 1
                end_level = length if auxiliary.end_level is None else auxiliary.end_level
                if auxiliary.start_level == 0 and end_level == length:
                    # The strand's complete path is an exact parallel translation.
                    path_code = add_segment_path(strand_segments[sid], top_xs[sid], y_top, x_offset=auxiliary.offset)
                else:
                    # Partial trajectories terminate at requested generator levels.
                    pts = []
                    if auxiliary.start_level == 0:
                        pts.append((top_xs[sid] + auxiliary.offset, y_top))
                    for lev in range(auxiliary.start_level, end_level + 1):
                        pos = orders_by_level[lev].index(sid)
                        pts.append((lane_xs[pos] + auxiliary.offset, level_y[lev]))
                    if end_level == length:
                        pos = orders_by_level[-1].index(sid)
                        pts.append((bottom_xs[pos] + auxiliary.offset, y_bottom))
                    coordinates = " ".join(f"({_tex_num(x)},{_tex_num(y)})" for x, y in pts)
                    path_code = f"plot[smooth] coordinates {{{coordinates}}}" if len(pts) >= 3 else " -- ".join(f"({_tex_num(x)},{_tex_num(y)})" for x, y in pts)
            lines.append(
                f"\\draw[draw={auxiliary.color},line width={_tex_num(auxiliary.line_width)}pt,{auxiliary.style},line cap=round,line join=round] {path_code};"
            )

        # Region braces are tied to the same level model, so their location survives
        # stacking and substitution.  Side mirroring is explicit to keep both sides
        # visually symmetric and keep the brace open towards the diagram.
        for region in self.regions:
            y0 = level_y[region.start_level] - region.start_offset
            y1 = level_y[region.end_level] - region.end_offset
            x_base = min_x - region.offset if region.side == "left" else max_x + region.offset
            # TikZ's default brace on a top-to-bottom path bulges to the left.
            # A left-hand brace must bulge right (toward the diagram), while a
            # right-hand brace must bulge left; therefore only the left is mirrored.
            mirror = "" if region.side == "right" else ",mirror"
            lines.append(
                f"\\draw[decorate,decoration={{brace,amplitude=4pt{mirror}}},draw={region.color},line width={_tex_num(region.line_width)}pt] "
                f"({_tex_num(x_base)},{_tex_num(y0)}) -- ({_tex_num(x_base)},{_tex_num(y1)});"
            )
            label_x = x_base - 0.12 if region.side == "left" else x_base + 0.12
            anchor = "east" if region.side == "left" else "west"
            label = _tex_label(region.label, self.label_mode)
            lines.append(f"\\node[anchor={anchor},inner sep=1pt] at ({_tex_num(label_x)},{_tex_num((y0+y1)/2)}) {{{label}}};")

        if self.endpoint_dots:
            for pos, strand_id in enumerate(range(n)):
                lines.append(f"\\fill[draw=none,fill={self._strand_color(strand_id)}] ({_tex_num(top_xs[pos])},{_tex_num(y_top)}) circle[radius=0.035];")
            for pos, strand_id in enumerate(orders_by_level[-1]):
                lines.append(f"\\fill[draw=none,fill={self._strand_color(strand_id)}] ({_tex_num(bottom_xs[pos])},{_tex_num(y_bottom)}) circle[radius=0.035];")

        if self.input_labels is not None:
            for pos, label_value in enumerate(self.input_labels):
                if label_value is None:
                    continue
                label = _tex_label(label_value, self.label_mode)
                lines.append(f"\\node[inner sep=1pt,anchor=south] at ({_tex_num(top_xs[pos])},{_tex_num(y_top + self.label_offset)}) {{{label}}};")

        for annotation in self.annotations:
            strand_id = annotation["strand"] - 1
            order_at_level = orders_by_level[annotation["level"]]
            position = order_at_level.index(strand_id)
            x_annot = lane_xs[position] + 0.12
            y_annot = level_y[annotation["level"]] - annotation.get("offset_down", 0.0)
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
                lines.append(f"\\node[inner sep=1pt,anchor=north] at ({_tex_num(bottom_xs[pos])},{_tex_num(y_bottom - self.label_offset)}) {{{label}}};")

        for group in self.top_groups:
            y = top_group_start + top_levels[group] * self.group_spacing
            lines.extend(self._group_tex(group, y, True, top_levels[group], top_xs))
        for group in self.bottom_groups:
            y = bottom_group_start - bottom_levels[group] * self.group_spacing
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


