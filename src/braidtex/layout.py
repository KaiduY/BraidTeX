"""Layout: endpoint positions derived from configuration trees.

Adjacent leaves get a gap ``max(rho**d, wmin)`` where ``d`` is the depth
(root = 0) of their lowest common ancestor.  A flat configuration has every LCA
at the root, hence uniform spacing; ``(x1 x2) x3`` has gap ``rho`` between x1,x2
and 1 between x2,x3; deeper nesting yields progressively tighter clusters.
Gaps are cumulatively summed and normalized to [0, 1].  The algorithm depends
only on the tree, never on specific configurations.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from .config import GAP, Node
from .errors import BraidValidationError


def gap_weights(node: Node, rho: float = 0.5, wmin: float = 0.15,
                gapspan: float = 1.0) -> List[float]:
    """Spacing weight between each pair of adjacent leaves (length ``arity - 1``).
    Weights next to a gap leaf ("...") are multiplied by ``gapspan``."""

    def rec(n: Node, depth: int) -> List[float]:
        if n.is_leaf:
            return []
        out: List[float] = []
        for k, c in enumerate(n.children):
            if k:
                out.append(max(rho ** depth, wmin))
            out.extend(rec(c, depth + 1))
        return out

    w = rec(node, 0)
    labels = node.labels()
    return [x * (gapspan if GAP in (labels[i], labels[i + 1]) else 1.0) for i, x in enumerate(w)]


def normalized_positions(node: Node, rho: float = 0.5, wmin: float = 0.15,
                         custom: Optional[Sequence[float]] = None,
                         gapspan: float = 1.0) -> List[float]:
    """Endpoint positions in [0, 1] (a single strand sits at 0.5)."""
    n = node.arity
    if custom is not None:
        pos = [float(x) for x in custom]
        if len(pos) != n:
            raise BraidValidationError(
                f"custom endpoint positions: expected {n} values, got {len(pos)}")
        if any(not (0.0 <= p <= 1.0) for p in pos) or any(b <= a for a, b in zip(pos, pos[1:])):
            raise BraidValidationError(
                "custom endpoint positions must be strictly increasing within [0, 1]")
        return pos
    if n == 0:
        return []
    if n == 1:
        return [0.5]
    gaps = gap_weights(node, rho, wmin, gapspan)
    total = sum(gaps)
    pos, acc = [0.0], 0.0
    for g in gaps:
        acc += g
        pos.append(acc / total)
    return pos
