"""Deterministic automatic endpoint layout from parenthesization trees.

Flat inputs stay uniformly spaced.  For a nested tree, the horizontal gap
between two consecutive leaves is selected from the depth of their lowest
common parent.  Gaps follow dyadic tiers (tight within a group, wider between
groups), with a cap to keep deeply nested trees from exploding in width.
"""
from __future__ import annotations
from typing import Any


def _is_group(node: Any) -> bool:
    return isinstance(node, (tuple, list))


def _leaf_paths(tree: Any) -> list[tuple[int, ...]]:
    """Return each leaf's nested-group path; the outer sequence is implicit."""
    paths: list[tuple[int, ...]] = []
    group_counter = 0

    def visit(node: Any, path: tuple[int, ...], *, root: bool = False) -> None:
        nonlocal group_counter
        if not _is_group(node):
            paths.append(path)
            return
        if not node:
            raise ValueError("A configuration tree cannot contain an empty group")
        # The top-level sequence is the implicit product, not an explicit group.
        if root:
            for child in node:
                visit(child, path)
            return
        group_id = group_counter
        group_counter += 1
        nested_path = path + (group_id,)
        for child in node:
            visit(child, nested_path)

    visit(tree, (), root=True)
    return paths


def _common_prefix_length(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    count = 0
    for left, right in zip(a, b):
        if left != right:
            break
        count += 1
    return count


def endpoint_positions(tree: Any, n: int, leaf_sep: float, cluster_gap: float) -> list[float]:
    """Allocate ordered endpoint positions using a capped dyadic decomposition.

    If ``tree`` is ``None`` or flat, positions are ``0, leaf_sep, 2*leaf_sep,
    ...``.  In a parenthesized tree, leaves sharing a deeper nested parent are
    closer.  The gap is selected from the lowest-common-ancestor depth:

    * same innermost group: ``leaf_sep``
    * neighboring groups: ``leaf_sep + cluster_gap``
    * groups separated higher in the tree: ``leaf_sep + 3*cluster_gap``

    The last tier is capped, so a long right- or left-associated expression
    remains a usable figure rather than growing exponentially with depth.
    """
    if n < 1:
        raise ValueError("n must be positive")
    if leaf_sep <= 0 or cluster_gap < 0:
        raise ValueError("leaf_sep must be positive and cluster_gap non-negative")
    if tree is None or not _is_group(tree):
        return [i * leaf_sep for i in range(n)]

    paths = _leaf_paths(tree)
    if len(paths) != n:
        raise ValueError(f"Configuration tree has {len(paths)} leaves, expected {n}")
    max_depth = max((len(path) for path in paths), default=0)
    result = [0.0]
    for index in range(n - 1):
        shared_depth = _common_prefix_length(paths[index], paths[index + 1])
        depth_delta = max(0, max_depth - shared_depth)
        # Explicit dyadic tiers, capped at three cluster-gap increments.
        gap_tier = min((1 << depth_delta) - 1, 3)
        gap = leaf_sep + cluster_gap * gap_tier
        result.append(result[-1] + gap)
    return result
