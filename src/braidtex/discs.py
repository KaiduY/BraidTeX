"""Little 2-discs boundary pictures: nested discs along the axis.

Every node of a configuration tree becomes a *stadium* (pill): the Minkowski sum
of a horizontal segment ``[left, right]`` on the axis with a disc of radius
``rho``.  A leaf is a small disc around its endpoint; a group's segment is the
hull of its children's segments and its radius is the largest child radius plus a
margin.  Because Minkowski sums are monotone, a child's stadium lies inside its
parent's **by construction**, siblings are disjoint (the margins are bounded by the
spacing of the endpoints), so the picture reproduces the parenthesization exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .config import GAP, Node


@dataclass(frozen=True)
class Disc:
    lo: int            # first leaf index covered (0-based)
    hi: int            # last leaf index covered
    left: float        # centre segment on the axis
    right: float
    rho: float         # radius
    depth: int         # root = 0
    is_leaf: bool
    gap: bool = False  # a gap leaf ("..."): kept for the layout, not drawn

    def contains_point(self, x: float, y: float = 0.0, eps: float = 1e-9) -> bool:
        cx = min(max(x, self.left), self.right)
        return (x - cx) ** 2 + y * y <= self.rho ** 2 + eps

    def contains(self, other: "Disc", eps: float = 1e-9) -> bool:
        """Is ``other`` inside this stadium?  (segment+disc inclusion)"""
        return (other.left >= self.left - eps and other.right <= self.right + eps
                and other.rho <= self.rho + eps)

    def intersects(self, other: "Disc") -> bool:
        gap = max(self.left - other.right, other.left - self.right, 0.0)
        return gap < self.rho + other.rho - 1e-9


def tree_height(node: Node) -> int:
    return 0 if node.is_leaf else 1 + max((tree_height(c) for c in node.children), default=0)


def disc_layout(tree: Node, xs: Sequence[float], rmax: float = 0.09,
                mmax: float = 0.12, nest_margin: float = 0.035) -> List[Disc]:
    """All discs of ``tree`` (leaves and groups, root included), outermost first.

    Segment of a node = hull of its leaf positions.  Radii are chosen top-down:
    ``rho = min(rmax + height*step, 0.45*(distance to the nearest endpoint outside the
    node), rho(parent) - nest_margin)``.  The local cap makes two non-nested discs
    disjoint (their caps sum to less than the distance between them); the parent bound
    makes every disc lie strictly inside its parent.
    """
    n = len(xs)
    if n == 0:
        return []
    step = min(mmax, 0.5 / (tree_height(tree) + 1))
    out: List[Disc] = []
    counter = [0]

    def rec(node: Node, depth: int, parent_rho: float) -> int:
        """Returns the height; discs are appended on the way back up."""
        lo = counter[0]
        if node.is_leaf:
            counter[0] += 1
            h, hi = 0, lo
        else:
            idx = len(out)
            kids: List[Tuple[int, float]] = []
            # radius needs the node's own height, which depends on the children:
            height = tree_height(node)
            hi = lo + node.arity - 1
            rho = _radius(height, lo, hi, depth, parent_rho)
            h = 0
            for c in node.children:
                h = max(h, rec(c, depth + 1, rho))
            out.append(Disc(lo, hi, xs[lo], xs[hi], rho, depth, False))
            return h + 1
        rho = _radius(0, lo, hi, depth, parent_rho)
        out.append(Disc(lo, hi, xs[lo], xs[hi], rho, depth, True, node.label == GAP))
        return h

    def _radius(height: int, lo: int, hi: int, depth: int, parent_rho: float) -> float:
        want = rmax + height * step
        outside = []
        if lo > 0:
            outside.append(xs[lo] - xs[lo - 1])
        if hi < n - 1:
            outside.append(xs[hi + 1] - xs[hi])
        cap = 0.45 * min(outside) if outside else float("inf")
        rho = min(want, cap)
        if depth > 0:
            rho = min(rho, parent_rho - nest_margin)
        return max(rho, 0.01)

    rec(tree, 0, float("inf"))
    out.sort(key=lambda d: (-d.rho, d.lo, d.hi))
    return out


def root_radius(discs: Sequence[Disc]) -> float:
    return max((d.rho for d in discs), default=0.0)
