from __future__ import annotations

from .core import Braid, Configuration


def _compute_positions(config: Configuration, start: float, end: float) -> list[float]:
    if config is None:
        return []

    def visit(node, left: float, right: float) -> list[float]:
        if node.kind == "leaf":
            return [(left + right) / 2.0]
        if not node.children:
            return []
        if len(node.children) == 1:
            return visit(node.children[0], left, right)
        total = sum(max(1, len(child.leaf_labels)) for child in node.children)
        results: list[float] = []
        current_left = left
        for child in node.children:
            child_count = max(1, len(child.leaf_labels))
            child_width = (right - left) * (child_count / total)
            results.extend(visit(child, current_left, current_left + child_width))
            current_left += child_width
        return results

    leaves = config.leaf_labels
    if not leaves:
        return []
    if len(leaves) == 1:
        return [((start + end) / 2.0)]
    return visit(config.root, start, end)


def render_svg(braid: Braid, width: int = 420, height: int = 220) -> str:
    in_labels = braid.input_config.leaf_labels if braid.input_config else []
    out_labels = braid.output_config.leaf_labels if braid.output_config else []
    input_positions = _compute_positions(braid.input_config, 40, width - 40) if braid.input_config else []
    output_positions = _compute_positions(braid.output_config, 40, width - 40) if braid.output_config else []

    if len(in_labels) != braid.n:
        raise ValueError(f"Input configuration has {len(in_labels)} labels but the braid uses {braid.n} strands.")
    if len(out_labels) != braid.n:
        raise ValueError(f"Output configuration has {len(out_labels)} labels but the braid uses {braid.n} strands.")

    perm = braid.permutation
    path_elements: list[str] = []
    y_top = 45
    y_bottom = height - 45
    y_mid = (y_top + y_bottom) / 2.0

    for strand_id in range(braid.n):
        source_x = input_positions[strand_id]
        target_x = output_positions[perm[strand_id]]
        stroke = braid.colors.get(strand_id + 1, braid.colors.get(strand_id, "black"))
        control = abs(target_x - source_x) * 0.6
        d = (
            f"M {source_x:.2f} {y_top} "
            f"C {source_x + control:.2f} {y_mid}, {target_x - control:.2f} {y_mid}, {target_x:.2f} {y_bottom}"
        )
        path_elements.append(f'<path d="{d}" stroke="{stroke}" stroke-width="2.2" fill="none"/>')

    crossing_nodes: list[str] = []
    if braid.word:
        crossing_count = len(braid.word)
        for idx, crossing in enumerate(braid.crossings):
            x_left = input_positions[crossing.left_index]
            x_right = input_positions[crossing.right_index]
            if idx < len(input_positions):
                x_left = input_positions[crossing.left_index]
                x_right = input_positions[crossing.right_index]
            y = y_top + (idx + 1) * (y_bottom - y_top) / (crossing_count + 1)
            if crossing.sign > 0:
                over_path = f"M {x_left:.2f} {y - 9:.2f} Q {(x_left + x_right) / 2:.2f} {y - 18:.2f}, {x_right:.2f} {y + 9:.2f}"
                under_path = f"M {x_right:.2f} {y - 9:.2f} Q {(x_left + x_right) / 2:.2f} {y + 18:.2f}, {x_left:.2f} {y + 9:.2f}"
            else:
                over_path = f"M {x_right:.2f} {y - 9:.2f} Q {(x_left + x_right) / 2:.2f} {y - 18:.2f}, {x_left:.2f} {y + 9:.2f}"
                under_path = f"M {x_left:.2f} {y - 9:.2f} Q {(x_left + x_right) / 2:.2f} {y + 18:.2f}, {x_right:.2f} {y + 9:.2f}"
            crossing_nodes.append(f'<path d="{over_path}" stroke="black" stroke-width="2.0" fill="none" stroke-linecap="round"/>')
            crossing_nodes.append(f'<path d="{under_path}" stroke="white" stroke-width="1.8" fill="none" stroke-linecap="round"/>')
            crossing_nodes.append(f'<text x="{(x_left + x_right) / 2:.2f}" y="{y - 18:.2f}" text-anchor="middle" font-size="9">σ{abs(crossing.generator)}</text>')

    label_nodes: list[str] = []
    for i, label in enumerate(in_labels):
        x = input_positions[i]
        label_nodes.append(f'<text x="{x:.2f}" y="{y_top - 10}" text-anchor="middle" font-size="12">{label}</text>')
    for i, label in enumerate(out_labels):
        x = output_positions[i]
        label_nodes.append(f'<text x="{x:.2f}" y="{y_bottom + 18}" text-anchor="middle" font-size="12">{label}</text>')

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        '<rect width="100%" height="100%" fill="white"/>'
        '{paths}'
        '{crossings}'
        '{labels}'
        '</svg>'
    ).format(
        w=width,
        h=height,
        paths="".join(path_elements),
        crossings="".join(crossing_nodes),
        labels="".join(label_nodes),
    )
    return svg
