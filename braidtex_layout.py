"""Automatic endpoint layout inferred from nested configuration trees."""
from __future__ import annotations
from typing import Any

def _tree_depth(node: Any, depth: int = 0) -> int:
    if not isinstance(node, (tuple, list)) or not node:
        return depth
    return max([depth] + [_tree_depth(child, depth + 1) for child in node])


def endpoint_positions(tree: Any, n: int, leaf_sep: float, cluster_gap: float) -> list[float]:
    """Allocate ordered endpoint positions recursively from a configuration tree.

    The root sequence is implicit. A gap between child subtrees grows with the
    number of deeper parenthesization levels below it, so inner clusters are
    tighter than unrelated outer siblings. The returned coordinates start at 0.
    """
    if tree is None:
        return [i * leaf_sep for i in range(n)]
    if not isinstance(tree, (tuple, list)):
        return [i * leaf_sep for i in range(n)]
    max_depth = max(0, _tree_depth(tree) - 1)
    def width(node: Any, depth: int) -> float:
        if not isinstance(node, (tuple, list)):
            return 0.0
        if not node:
            raise ValueError("A configuration tree cannot contain an empty group")
        gap = leaf_sep + cluster_gap * max(0, max_depth - depth)
        value = sum(width(child, depth + 1) for child in node) + gap * (len(node) - 1)
        return value

    width(tree, 0)
    result: list[float] = []

    def place(node: Any, left: float, depth: int) -> None:
        if not isinstance(node, (tuple, list)):
            result.append(left)
            return
        gap = leaf_sep + cluster_gap * max(0, max_depth - depth)
        x = left
        for index, child in enumerate(node):
            place(child, x, depth + 1)
            x += width(child, depth + 1)
            if index + 1 < len(node):
                x += gap

    place(tree, 0.0, 0)
    if len(result) != n:
        raise ValueError(f"Configuration tree has {len(result)} leaves, expected {n}")
    return result

