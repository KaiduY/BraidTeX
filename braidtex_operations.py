"""Mathematical operations on BraidTeX models: stacks and cabling substitution."""
from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence

from braidtex import Braid, Group
from braidtex_layout import endpoint_positions
from braidtex_model import (
    AuxiliaryPath, Connector, CoordinateFrame, Region, Separator,
)


def replace_connector_level_and_identity(
    connector: Connector, upper_order: Sequence[int], level_offset: int, *, upper_trailing_gap: float = 0.0
) -> Connector:
    """Map a lower-component connector into the composed input-identity system.

    A connector at the lower component's top boundary is shifted past the
    upper component's trailing idle region, which is merged with the lower
    component's leading gap in the composite geometry.
    """
    a = upper_order[connector.strand_a - 1] + 1
    b = upper_order[connector.strand_b - 1] + 1
    offset = upper_trailing_gap if connector.level == 0 else 0.0
    return replace(connector, strand_a=a, strand_b=b, level=connector.level + level_offset,
                   offset_down=connector.offset_down + offset)


def translate_auxiliary_path(path: AuxiliaryPath, dy: float, _order: Sequence[int] | None = None) -> AuxiliaryPath:
    """Translate an upper-component explicit path upward in the stacked geometry."""
    if not path.points:
        return path
    return replace(path, points=tuple((x, y + dy) for x, y in path.points))


def map_lower_auxiliary_path(path: AuxiliaryPath, upper_order: Sequence[int], level_offset: int) -> AuxiliaryPath:
    fs = path.follow_strand
    if fs is not None:
        fs = upper_order[fs - 1] + 1
    return replace(path, follow_strand=fs, start_level=path.start_level + level_offset,
                   end_level=None if path.end_level is None else path.end_level + level_offset)


def compose_frames(upper: CoordinateFrame | None, lower: CoordinateFrame | None,
                   level_offset: int, *, upper_trailing_gap: float = 0.0) -> CoordinateFrame | None:
    if upper is None and lower is None:
        return None
    upper = upper or CoordinateFrame(top_axis=False, bottom_axis=False, left_axis=False, right_boundary=False)
    lower = lower or CoordinateFrame(top_axis=False, bottom_axis=False, left_axis=False, right_boundary=False)
    separators = tuple(upper.separators) + tuple(
        replace(s, level=s.level + level_offset,
                offset_down=s.offset_down + (upper_trailing_gap if s.level == 0 else 0.0))
        for s in lower.separators
    )
    return CoordinateFrame(
        top_axis=upper.top_axis, bottom_axis=lower.bottom_axis,
        left_axis=upper.left_axis or lower.left_axis,
        right_boundary=upper.right_boundary or lower.right_boundary,
        top_ticks=upper.top_ticks, bottom_ticks=lower.bottom_ticks,
        top_tick_ports=upper.top_tick_ports, bottom_tick_ports=lower.bottom_tick_ports,
        axis_color=upper.axis_color, axis_width=max(upper.axis_width, lower.axis_width),
        tick_half_height=max(upper.tick_half_height, lower.tick_half_height),
        boundary_style=upper.boundary_style,
        boundary_width=max(upper.boundary_width, lower.boundary_width),
        separators=separators,
    )


class DiagramSum:
    """A formal signed sum of compatible diagram models.

    Terms are kept as underlying ``Braid`` objects; they are never composited as
    images. ``operator='-'`` means the first term minus each subsequent term.
    An explicit ``signs`` tuple preserves coefficients under distributive
    stacking and substitution.
    """
    def __init__(self, terms: Sequence[Braid], *, operator: str = "+",
                 signs: Sequence[int] | None = None) -> None:
        if not terms:
            raise ValueError("DiagramSum needs at least one term")
        if operator not in ("+", "-"):
            raise ValueError("operator must be '+' or '-' ")
        if any(not isinstance(term, Braid) for term in terms):
            raise TypeError("Every DiagramSum term must be a Braid")
        first = terms[0]
        for term in terms[1:]:
            if term.n != first.n:
                raise ValueError("All terms in a diagram sum must have the same arity")
            for name, left, right in (
                ("input labels", first.input_labels, term.input_labels),
                ("output labels", first.output_labels, term.output_labels),
                ("input parenthesization", first.top_parenthesization, term.top_parenthesization),
                ("output parenthesization", first.bottom_parenthesization, term.bottom_parenthesization),
            ):
                if left is not None and right is not None and left != right:
                    raise ValueError(f"All terms in a diagram sum must have compatible {name}")
        self.terms = tuple(terms)
        self.operator = operator
        if signs is None:
            values = (1,) + ((-1,) * (len(terms) - 1) if operator == "-" else (1,) * (len(terms) - 1))
        else:
            values = tuple(int(s) for s in signs)
            if len(values) != len(terms) or any(s not in (-1, 1) for s in values):
                raise ValueError("signs must contain one +1 or -1 coefficient per term")
        self.signs = tuple(values)

    def tikz(self, *, inline: bool = True) -> str:
        rendered = [term.tikz(inline=inline) for term in self.terms]
        if not inline:
            return ("\n" + r"\par" + "\n").join(rendered)
        expression = rendered[0] if self.signs[0] > 0 else "-" + rendered[0]
        for sign, item in zip(self.signs[1:], rendered[1:]):
            expression += (r" \mathbin{+} " if sign > 0 else r" \mathbin{-} ") + item
        return expression

    def write(self, path, *, format: str = "inline", border: str = "4pt"):
        from pathlib import Path
        path = Path(path)
        if format == "inline":
            content = self.tikz(inline=True)
        elif format == "picture":
            content = self.tikz(inline=False)
        elif format == "standalone":
            content = ("\\documentclass[tikz,border=" + border + "]{standalone}\n"
                       "\\usepackage{xcolor}\n\\usetikzlibrary{decorations.pathreplacing}\n"
                       "\\begin{document}\n" + self.tikz(inline=False) + "\n\\end{document}\n")
        else:
            raise ValueError("format must be 'inline', 'picture', or 'standalone'")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")
        return path

    def __len__(self) -> int:
        return len(self.terms)

    def __iter__(self):
        return iter(self.terms)

def _stack_braids(*components: Braid, separators: bool = False,
                 labels: Sequence[str | None] | None = None,
                 check_labels: bool = True) -> Braid:
    if len(components) < 2:
        raise ValueError("stack requires at least two diagram components")
    if labels is not None and len(labels) != len(components):
        raise ValueError("labels must have one entry per component")
    result = components[0]
    for component in components[1:]:
        result = result.compose(component, check_labels=check_labels)

    running = 0
    gap_cursor = 0.0
    new_regions = list(result.regions)
    new_separators = list(result.frame.separators) if result.frame else []
    for index, component in enumerate(components):
        count = len(component.word)
        start_offset = gap_cursor
        if labels is not None and labels[index]:
            if count == 0:
                end_offset = start_offset + component.level_gaps[0]
                new_regions.append(Region(
                    start_level=running, end_level=running, label=labels[index],
                    start_offset=start_offset, end_offset=end_offset,
                ))
            else:
                new_regions.append(Region(
                    start_level=running, end_level=running + count, label=labels[index],
                    start_offset=start_offset, end_offset=component.level_gaps[-1],
                ))
        if count == 0:
            gap_cursor += component.level_gaps[0]
        else:
            running += count
            gap_cursor = component.level_gaps[-1]
        if index < len(components) - 1 and separators:
            # level_y[running] is the top of the inter-component gap; after
            # consumed identity heights/trailing gaps sits the true boundary.
            new_separators.append(Separator(running, offset_down=gap_cursor))
    if separators:
        frame = result.frame or CoordinateFrame(
            top_axis=False, bottom_axis=False, left_axis=False, right_boundary=False
        )
        result.frame = replace(frame, separators=tuple(new_separators))
    if labels is not None:
        result.regions = tuple(new_regions)
    return result


def stack(*components: Braid | DiagramSum, separators: bool = False,
          labels: Sequence[str | None] | None = None,
          check_labels: bool = True) -> Braid | DiagramSum:
    """Stack diagram models vertically, distributing over formal sums.

    Each branch is composed on its underlying Braid models. No rendered image is
    ever used as composition input. If any component is a DiagramSum, stacking
    distributes over all combinations of its terms.
    """
    if len(components) < 2:
        raise ValueError("stack requires at least two diagram components")
    term_groups: list[tuple[Braid, ...]] = []
    sign_groups: list[tuple[int, ...]] = []
    for component in components:
        if isinstance(component, Braid):
            term_groups.append((component,))
            sign_groups.append((1,))
        elif isinstance(component, DiagramSum):
            term_groups.append(component.terms)
            sign_groups.append(component.signs)
        else:
            raise TypeError("Every stacked component must be a Braid or DiagramSum")
    from itertools import product
    results: list[Braid] = []
    result_signs: list[int] = []
    for indices in product(*(range(len(group)) for group in term_groups)):
        choice = tuple(term_groups[j][i] for j, i in enumerate(indices))
        sign = 1
        for j, i in enumerate(indices):
            sign *= sign_groups[j][i]
        results.append(_stack_braids(*choice, separators=separators, labels=labels, check_labels=check_labels))
        result_signs.append(sign)
    return results[0] if len(results) == 1 and result_signs[0] == 1 else DiagramSum(results, signs=result_signs)

def _outer_to_cabled_word(outer: Braid, target: int, m: int) -> tuple[list[int], list[int]]:
    """Cable outer generators around a strand replaced by an m-strand bundle.

    Returns (expanded_word, boundary_levels), where boundary_levels[k] is the
    number of expanded generators completed after outer level k.
    """
    order = list(range(1, outer.n + 1))
    expanded: list[int] = []
    boundaries = [0]

    def start_position(original_identity: int) -> int:
        # The current ordered original strand gets a bundle width m iff it is target.
        pos = order.index(original_identity)
        return 1 + sum(m if identity == target else 1 for identity in order[:pos])

    for generator in outer.word:
        j = abs(generator)  # current adjacent original positions, 1-based
        left_identity, right_identity = order[j - 1], order[j]
        left_start = start_position(left_identity)
        right_start = start_position(right_identity)
        sign = 1 if generator > 0 else -1
        if left_identity == target and right_identity != target:
            # The bundle on the left passes the right strand as a block. Each
            # member swaps across the external strand in right-to-left order;
            # changing the crossing sign changes over/under, not this order.
            indices = range(left_start + m - 1, left_start - 1, -1)
            expanded.extend(sign * k for k in indices)
        elif right_identity == target and left_identity != target:
            # A left strand crosses each member of the bundle on its right.
            # The adjacent swaps run left-to-right for either crossing sign.
            indices = range(left_start, left_start + m)
            expanded.extend(sign * k for k in indices)
        else:
            # The target cannot be both identities in an ordinary braid crossing.
            expanded.append(sign * left_start)
        order[j - 1], order[j] = order[j], order[j - 1]
        boundaries.append(len(expanded))
    return expanded, boundaries


def _map_identity(identity: int, target: int, m: int, replacement_index: int | None) -> int:
    if identity == target:
        if replacement_index is None:
            raise ValueError("An explicit replacement strand is required for a connector attached to the substituted strand")
        if not 1 <= replacement_index <= m:
            raise ValueError(f"replacement strand index must be between 1 and {m}")
        return target + replacement_index - 1
    return identity if identity < target else identity + m - 1


def _replace_leaf(tree, index: int, replacement):
    """Graft a replacement configuration into one 1-based leaf of a tree."""
    cursor = 0
    def visit(node):
        nonlocal cursor
        if isinstance(node, (tuple, list)):
            return tuple(visit(child) for child in node)
        cursor += 1
        return replacement if cursor == index else node
    result = visit(tree)
    if cursor < index:
        raise ValueError(f"Configuration tree has only {cursor} leaves; cannot replace leaf {index}")
    return result


def _expanded_endpoint_labels(labels, target: int, replacements: Sequence, n: int):
    base = tuple(labels) if labels is not None else (None,) * n
    result = []
    for i, label in enumerate(base, start=1):
        result.extend(replacements if i == target else [label])
    return tuple(result) if labels is not None or any(x is not None for x in replacements) else None


def substitute(outer: Braid | DiagramSum, position: int, inner: Braid | DiagramSum, *,
               connector_policy: str | int = "error") -> Braid | DiagramSum:
    """Operadically insert ``inner`` into input strand ``position`` of ``outer``.

    This is a cabling operation on the word, not a geometric overlay. The inner
    braid is applied to the inserted bundle first, then every outer generator is
    expanded into the crossing word for that cable. The result has ``n+m-1``
    strands. When outer connectors touch the replaced strand, use
    ``connector_policy='error'`` (safe default), an integer replacement-strand
    index, or ``connector_policy='all'`` to return one alternative per strand.
    """
    outer_terms = outer.terms if isinstance(outer, DiagramSum) else (outer,)
    inner_terms = inner.terms if isinstance(inner, DiagramSum) else (inner,)
    outer_signs = outer.signs if isinstance(outer, DiagramSum) else (1,)
    inner_signs = inner.signs if isinstance(inner, DiagramSum) else (1,)
    if any(not isinstance(term, Braid) for term in (*outer_terms, *inner_terms)):
        raise TypeError("outer and inner must be Braid models or DiagramSum expressions")
    if isinstance(outer, DiagramSum) or isinstance(inner, DiagramSum):
        from itertools import product
        results: list[Braid] = []
        result_signs: list[int] = []
        for oi, outer_term in enumerate(outer_terms):
            for ii, inner_term in enumerate(inner_terms):
                result = substitute(outer_term, position, inner_term, connector_policy=connector_policy)
                if isinstance(result, DiagramSum):
                    results.extend(result.terms)
                    result_signs.extend([outer_signs[oi] * inner_signs[ii] * sign for sign in result.signs])
                else:
                    results.append(result)
                    result_signs.append(outer_signs[oi] * inner_signs[ii])
        return DiagramSum(results, signs=result_signs)
    outer = outer_terms[0]
    inner = inner_terms[0]
    if not isinstance(position, int) or not 1 <= position <= outer.n:
        raise ValueError(f"position must be a 1-based outer input strand index from 1 to {outer.n}")
    m, target = inner.n, position
    n_new = outer.n + m - 1
    outer_touching = [c for c in outer.connectors if target in (c.strand_a, c.strand_b)]
    outer_attachments = bool(outer_touching) or any(a["strand"] == target for a in outer.annotations)
    outer_attachments = outer_attachments or any(p.follow_strand == target for p in outer.auxiliary_paths)
    outer_attachments = outer_attachments or any(p.get("port") == target for p in outer.boundary_points)
    if outer_attachments:
        if connector_policy == "error":
            raise ValueError(
                f"An outer connector/annotation is attached to substituted strand {target}; "
                "choose connector_policy='all' or a 1-based replacement strand index"
            )
        if connector_policy == "all":
            return DiagramSum([
                _substitute_one(outer, target, inner, k) for k in range(1, m + 1)
            ])
        if not isinstance(connector_policy, int):
            raise ValueError("connector_policy must be 'error', 'all', or an integer replacement strand index")
        selected = connector_policy
    else:
        selected = None
        if connector_policy not in ("error", "all") and not isinstance(connector_policy, int):
            raise ValueError("connector_policy must be 'error', 'all', or an integer replacement strand index")
    if isinstance(selected, int) and not 1 <= selected <= m:
        raise ValueError(f"connector_policy index must be between 1 and inserted arity {m}")
    # A numeric policy with no touching connector is harmless but still validate.
    return _substitute_one(outer, target, inner, selected)



def _substitute_boundary_points(outer_points, inner_points, target: int, m: int, replacement_index: int | None):
    result = []
    for point in inner_points:
        item = dict(point)
        if "port" in item:
            item["port"] = target + item["port"] - 1
        result.append(item)
    for point in outer_points:
        item = dict(point)
        if "port" in item:
            port = item["port"]
            if port == target:
                if replacement_index is None:
                    raise ValueError("An outer boundary point lies on the substituted strand; choose a replacement index")
                item["port"] = target + replacement_index - 1
            elif port > target:
                item["port"] = port + m - 1
        result.append(item)
    return tuple(result)



def _groups_to_tree(leaves: Sequence, groups: Sequence[Group]):
    """Build a nested configuration tree from non-crossing interval groups."""
    n = len(leaves)
    intervals = sorted(
        {(int(g.start), int(g.end)) for g in groups},
        key=lambda item: (item[0], -item[1]),
    )

    def build(start: int, end: int):
        children = []
        cursor = start
        while cursor <= end:
            candidates = [
                (a, b) for a, b in intervals
                if a == cursor and b <= end and not (a == start and b == end)
            ]
            if candidates:
                # Choose the outermost interval starting here; nested intervals are
                # rebuilt recursively inside it.
                a, b = max(candidates, key=lambda pair: pair[1])
                children.append(build(a, b))
                cursor = b + 1
            else:
                children.append(leaves[cursor - 1])
                cursor += 1
        return tuple(children)

    return build(1, n)


def _expand_groups(groups: Sequence[Group], target: int, m: int) -> list[Group]:
    """Map visual endpoint intervals through replacing one port by m ports."""
    result = []
    for group in groups:
        if group.end < target:
            start, end = group.start, group.end
        elif group.start > target:
            start, end = group.start + m - 1, group.end + m - 1
        else:
            start = group.start if group.start < target else target
            end = group.end + m - 1 if group.end >= target else group.end
        if start < end:
            result.append(Group(start, end, group.label))
    return result

def _substitute_one(outer: Braid, target: int, inner: Braid,
                    replacement_index: int | None) -> Braid:
    m, n_new = inner.n, outer.n + inner.n - 1
    cable_word, outer_level_map = _outer_to_cabled_word(outer, target, m)
    inserted_word = [g + target - 1 if g > 0 else g - (target - 1) for g in inner.word]
    # If g is negative, shifting signed indices means -k -> -(k+offset), hence the
    # formula above; it intentionally preserves generator sign.
    word = tuple(inserted_word + cable_word)
    inserted_len = len(inserted_word)

    # Endpoint labels, semantic parenthesizations, and visual bundle layout are
    # separate.  If either operand supplies an actual parenthesization tree, graft
    # the inner configuration into that tree.  Otherwise we keep the mathematical
    # object flat but use a nested layout tree plus an explicit grouping arc to make
    # the inserted strand collection visible at both boundaries.
    top_replacement_labels = list(inner.input_labels) if inner.input_labels is not None else [None] * m
    top_labels = _expanded_endpoint_labels(outer.input_labels, target, top_replacement_labels, outer.n)
    inner_top = inner.top_parenthesization if inner.top_parenthesization is not None else tuple(top_replacement_labels)
    outer_top_tree = outer.top_parenthesization if outer.top_parenthesization is not None else tuple(outer.input_labels or (None,) * outer.n)
    top_tree = _replace_leaf(outer_top_tree, target, inner_top) if (
        outer.top_parenthesization is not None or inner.top_parenthesization is not None
    ) else None
    top_layout_tree = _replace_leaf(
        _groups_to_tree(tuple(outer.input_labels or (None,) * outer.n), outer.top_groups),
        target, inner_top,
    )

    outer_target_output_port = outer._bottom_order.index(target - 1) + 1
    bottom_replacement_labels = list(inner.output_labels) if inner.output_labels is not None else [None] * m
    output_labels = _expanded_endpoint_labels(outer.output_labels, outer_target_output_port, bottom_replacement_labels, outer.n)
    inner_bottom = inner.bottom_parenthesization if inner.bottom_parenthesization is not None else tuple(bottom_replacement_labels)
    outer_bottom_tree = outer.bottom_parenthesization if outer.bottom_parenthesization is not None else tuple(outer.output_labels or (None,) * outer.n)
    bottom_tree = _replace_leaf(outer_bottom_tree, outer_target_output_port, inner_bottom) if (
        outer.bottom_parenthesization is not None or inner.bottom_parenthesization is not None
    ) else None
    bottom_layout_tree = _replace_leaf(
        _groups_to_tree(tuple(outer.output_labels or (None,) * outer.n), outer.bottom_groups),
        outer_target_output_port, inner_bottom,
    )

    top_groups = _expand_groups(outer.top_groups, target, m)
    bottom_groups = _expand_groups(outer.bottom_groups, outer_target_output_port, m)
    if top_tree is None and m > 1:
        if not any((g.start, g.end) == (target, target + m - 1) for g in top_groups):
            top_groups.append(Group(target, target + m - 1))
    if bottom_tree is None and m > 1:
        if not any((g.start, g.end) == (outer_target_output_port, outer_target_output_port + m - 1) for g in bottom_groups):
            bottom_groups.append(Group(outer_target_output_port, outer_target_output_port + m - 1))

    # Colors of untouched strands are shifted; inserted strands inherit an explicit
    # inner color when supplied, otherwise the replaced outer strand's color.
    colors: list[str] = []
    for outer_id in range(1, outer.n + 1):
        if outer_id < target:
            colors.append(outer._strand_color(outer_id - 1))
        elif outer_id > target:
            colors.append(outer._strand_color(outer_id - 1))
        else:
            for inner_id in range(1, m + 1):
                explicit = None
                if isinstance(inner.strand_colors, dict):
                    explicit = inner.strand_colors.get(inner_id, inner.strand_colors.get(str(inner_id)))
                elif inner.strand_colors:
                    explicit = inner.strand_colors[inner_id - 1]
                colors.append(str(explicit) if explicit is not None else outer._strand_color(target - 1))
    final_colors = colors  # input-order indexed, with bundle entries in their block

    # Inner and outer connectors share one global level/identity system. Outer
    # connector levels are translated by both the inserted word length and the
    # number of cable crossings consumed at their original level.
    connectors: list[Connector] = []
    for c in inner.connectors:
        connectors.append(replace(c, strand_a=target + c.strand_a - 1,
                                  strand_b=target + c.strand_b - 1))
    inner_trailing_gap = inner.level_gaps[-1]
    for c in outer.connectors:
        a = _map_identity(c.strand_a, target, m, replacement_index)
        b = _map_identity(c.strand_b, target, m, replacement_index)
        connectors.append(replace(
            c, strand_a=a, strand_b=b,
            level=inserted_len + outer_level_map[c.level],
            offset_down=c.offset_down + (inner_trailing_gap if c.level == 0 else 0.0),
        ))

    # Existing inner annotations stay on the inserted strands; outer annotations
    # map untouched identities and have levels translated through expanded crossings.
    annotations = [dict(a, strand=target + a["strand"] - 1) for a in inner.annotations]
    for a in outer.annotations:
        new_strand = _map_identity(a["strand"], target, m, replacement_index)
        annotations.append(dict(
            a, strand=new_strand,
            level=inserted_len + outer_level_map[a["level"]],
            offset_down=a.get("offset_down", 0.0) +
                (inner_trailing_gap if a["level"] == 0 else 0.0),
        ))

    # Inner auxiliary paths that follow strands receive shifted identities; explicit
    # coordinates remain generic diagram annotations. Outer follows are mapped only
    # when they do not ambiguously follow the replaced strand.
    auxiliary: list[AuxiliaryPath] = []
    for path in inner.auxiliary_paths:
        # A strand-following path with no explicit stop belongs to the inserted
        # component, not to the entire composite braid.
        auxiliary.append(replace(
            path,
            follow_strand=(target + path.follow_strand - 1) if path.follow_strand else None,
            end_level=(len(inner.word) if path.follow_strand is not None and path.end_level is None
                       else path.end_level),
        ))
    for path in outer.auxiliary_paths:
        fs = path.follow_strand
        if fs == target:
            if replacement_index is None:
                # Do not silently select a strand for a topological annotation.
                raise ValueError("An outer auxiliary path follows the replaced strand; select an integer connector_policy")
            fs = target + replacement_index - 1
        elif fs is not None and fs > target:
            fs = fs + m - 1
        auxiliary.append(replace(path, follow_strand=fs,
                                 start_level=inserted_len + outer_level_map[path.start_level],
                                 end_level=(None if path.end_level is None else inserted_len + outer_level_map[path.end_level])))

    # Inner features occupy the first part of the word. Outer separators/regions are
    # mapped through the expansion table so their levels still denote real boundaries.
    inner_separators = list(inner.frame.separators if inner.frame else ())
    outer_separators = [replace(
        s, level=inserted_len + outer_level_map[s.level],
        offset_down=s.offset_down + (inner_trailing_gap if s.level == 0 else 0.0),
    ) for s in (outer.frame.separators if outer.frame else ())]
    frame = compose_frames(inner.frame, outer.frame, inserted_len)
    if frame is not None:
        frame = replace(frame, separators=tuple(inner_separators + outer_separators))
    regions = list(inner.regions)
    regions.extend(replace(
        r,
        start_level=inserted_len + outer_level_map[r.start_level],
        end_level=inserted_len + outer_level_map[r.end_level],
        start_offset=r.start_offset + (inner_trailing_gap if r.start_level == 0 else 0.0),
        end_offset=r.end_offset + (
            inner_trailing_gap if r.start_level == 0 and r.end_level == 0 else 0.0
        ),
    ) for r in outer.regions)

    # Insertion adds the inner word's heights followed by expanded outer crossing
    # heights distributed proportionally over the expanded crossings. Expansion
    # crossings for one outer generator share its layer height evenly.
    inner_heights = list(inner.layer_heights)
    expanded_heights: list[float] = []
    for index, g in enumerate(outer.word):
        count = outer_level_map[index + 1] - outer_level_map[index]
        expanded_heights.extend([outer.layer_heights[index] / count] * count)
    # Gaps get folded into the neighboring crossing layer, preserving the total
    # component height without changing the crossing sequence. Identity component
    # padding is retained through the level-gap model below.
    inner_gaps = list(inner.level_gaps)
    outer_gaps = list(outer.level_gaps)
    combined_gaps = [0.0] * (len(word) + 1)
    for level, gap in enumerate(inner_gaps):
        combined_gaps[level] += gap
    for level, gap in enumerate(outer_gaps):
        combined_gaps[inserted_len + outer_level_map[min(level, len(outer_level_map)-1)]] += gap
    # Multiple original level gaps can map to one expanded level; sum them.

    kwargs = {
        "n": n_new, "word": word,
        "input_labels": top_labels, "output_labels": output_labels,
        "strand_colors": final_colors,
        "color": outer.color, "positive_over": outer.positive_over,
        "label_mode": outer.label_mode, "top_parenthesization": top_tree,
        "bottom_parenthesization": bottom_tree,
        "top_groups": top_groups if top_tree is None else None,
        "bottom_groups": bottom_groups if bottom_tree is None else None,
        "top_positions": endpoint_positions(top_layout_tree, n_new, outer.strand_sep, outer.cluster_gap) if top_tree is None else None,
        "bottom_positions": endpoint_positions(bottom_layout_tree, n_new, outer.strand_sep, outer.cluster_gap) if bottom_tree is None else None,
        "include_root_parentheses": False,
        "strand_sep": outer.strand_sep, "layer_height": outer.layer_height,
        "layer_heights": inner_heights + expanded_heights,
        "level_gaps": combined_gaps,
        "identity_height": max(outer.identity_height, inner.identity_height),
        "line_width": outer.line_width, "crossing_gap": outer.crossing_gap,
        "background_color": outer.background_color, "endpoint_dots": outer.endpoint_dots,
        "show_generators": outer.show_generators, "baseline": outer.baseline,
        "group_spacing": outer.group_spacing, "label_offset": outer.label_offset,
        "cluster_gap": outer.cluster_gap, "diagram_scale": outer.diagram_scale,
        "axis": outer.axis or inner.axis, "axis_y": outer.axis_y,
        "axis_extent": outer.axis_extent or inner.axis_extent,
        "axis_color": outer.axis_color, "axis_front": outer.axis_front,
        "boundary_points": _substitute_boundary_points(outer.boundary_points, inner.boundary_points, target, m, replacement_index),
        "annotations": annotations, "connectors": connectors,
        "frame": frame, "auxiliary_paths": auxiliary, "regions": tuple(regions),
    }
    # Parenthesization trees reconstruct groups. When absent, use automatic flat
    # layout; hand-entered coordinates are intentionally recomputed for new arity.
    return Braid(**kwargs)
