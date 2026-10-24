r"""Boundary configurations: a documented grammar and a tree representation.

Grammar (whitespace separates atoms)::

    config := item*
    item   := '(' config ')'          structural grouping (non-empty)
            | '*'                     unlabeled leaf
            | '...' | '\dots' | '\cdots' | '\ldots'
                                      gap: stands for any number of omitted strands
            | '\atom{' raw '}'        explicit atom: raw may contain anything balanced
            | token                   atom
    token  := maximal run of characters that are not whitespace or an
              unprotected '(' / ')'.  Braces ``{...}`` (balanced) and
              backslash escapes (``\(``, ``\frac``) are protected, so
              ``x_{12}``, ``\frac{A}{B}``, ``{V(W)}`` are single atoms.

Normalization removes redundant wrappers: ``(x) y`` becomes ``x y`` and
``((x y) z)`` becomes ``(x y) z``.  The outermost grouping *is* the root, so
``(x y)`` and ``x y`` denote the same tree.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Optional, Sequence, Tuple, Union

from .errors import ConfigSyntaxError

GAP = "..."                    # label of a gap leaf (an invisible placeholder slot)
GAP_TOKENS = {"...", "\\dots", "\\cdots", "\\ldots", "\\dotsc", "\\dotsb", "\\hdots", "\u2026"}


@dataclass(frozen=True)
class Node:
    """Leaf (strand endpoint) or internal grouping node."""

    label: Optional[str] = None          # raw LaTeX label of a leaf; None = unlabeled
    children: Tuple["Node", ...] = ()
    is_leaf: bool = False

    @staticmethod
    def leaf(label: Optional[str]) -> "Node":
        return Node(label=label, is_leaf=True)

    @property
    def is_gap(self) -> bool:
        return self.is_leaf and self.label == GAP

    @staticmethod
    def group(children: Sequence["Node"]) -> "Node":
        return Node(children=tuple(children))

    # ---- queries ---------------------------------------------------------
    def leaves(self) -> List["Node"]:
        if self.is_leaf:
            return [self]
        return [l for c in self.children for l in c.leaves()]

    @property
    def arity(self) -> int:
        return len(self.leaves())

    def labels(self) -> List[Optional[str]]:
        return [l.label for l in self.leaves()]

    def relabel(self, labels: Sequence[Optional[str]]) -> "Node":
        """Same tree shape, leaves replaced (in order) by ``labels``."""
        it: Iterator[Optional[str]] = iter(labels)

        def rec(n: Node) -> Node:
            if n.is_leaf:
                return Node.leaf(next(it))
            return Node.group([rec(c) for c in n.children])

        return rec(self)

    def same_shape(self, other: "Node") -> bool:
        if self.is_leaf or other.is_leaf:
            return self.is_leaf and other.is_leaf
        return len(self.children) == len(other.children) and all(
            a.same_shape(b) for a, b in zip(self.children, other.children))

    def is_flat(self) -> bool:
        return all(c.is_leaf for c in self.children)

    # ---- serialization ---------------------------------------------------
    def to_json(self):
        """Leaf -> label string or null; group -> list of children."""
        if self.is_leaf:
            return self.label
        return [c.to_json() for c in self.children]

    @staticmethod
    def from_json(data) -> "Node":
        if data is None or isinstance(data, str):
            return Node.leaf(data)
        if isinstance(data, list):
            return Node.group([Node.from_json(d) for d in data])
        raise ConfigSyntaxError(f"bad JSON configuration element: {data!r}")

    def to_string(self, _root: bool = True) -> str:
        if self.is_leaf:
            return _atom_text(self.label)
        inner = " ".join(c.to_string(False) for c in self.children)
        return inner if _root else f"({inner})"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.to_string()


def _atom_text(label: Optional[str]) -> str:
    if label is None:
        return "*"
    try:
        end, leaf = _read_atom(label, 0)
        if end == len(label) and leaf.label == label:
            return label
    except ConfigSyntaxError:
        pass
    return "\\atom{" + label + "}"


def _match_brace(s: str, i: int) -> int:
    """Index of the ``}`` matching the ``{`` at ``i``."""
    depth, j, n = 0, i, len(s)
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    raise ConfigSyntaxError("unbalanced '{' in label", s, i)


def _read_atom(s: str, i: int) -> Tuple[int, Node]:
    n = len(s)
    if s.startswith("\\atom", i) and not (i + 5 < n and s[i + 5].isalpha()):
        j = i + 5
        while j < n and s[j].isspace():
            j += 1
        if j >= n or s[j] != "{":
            raise ConfigSyntaxError("\\atom must be followed by {...}", s, i)
        end = _match_brace(s, j)
        raw = s[j + 1:end].strip()
        if not raw:
            raise ConfigSyntaxError("empty \\atom{}", s, i)
        return end + 1, Node.leaf(raw)
    start = i
    while i < n:
        c = s[i]
        if c.isspace() or c in "()":
            break
        if c == "{":
            i = _match_brace(s, i) + 1
            continue
        if c == "}":
            raise ConfigSyntaxError("unmatched '}'", s, i)
        if c == "\\":
            i += 1
            if i < n and s[i].isalpha():
                while i < n and s[i].isalpha():
                    i += 1
            else:
                i += 1
            continue
        i += 1
    raw = s[start:i]
    if raw in GAP_TOKENS:
        return i, Node.leaf(GAP)
    return i, Node.leaf(None if raw == "*" else raw)


def _parse_seq(s: str, i: int, top: bool) -> Tuple[List[Node], int]:
    items: List[Node] = []
    n = len(s)
    while True:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            if not top:
                raise ConfigSyntaxError("missing ')'", s, n)
            return items, i
        c = s[i]
        if c == ")":
            if top:
                raise ConfigSyntaxError("unmatched ')'", s, i)
            return items, i
        if c == "(":
            sub, j = _parse_seq(s, i + 1, False)
            if j >= n or s[j] != ")":
                raise ConfigSyntaxError("missing ')' for group opened here", s, i)
            if not sub:
                raise ConfigSyntaxError("empty group '()'", s, i)
            items.append(Node.group(sub))
            i = j + 1
        else:
            i, leaf = _read_atom(s, i)
            items.append(leaf)


def _norm(n: Node, root: bool) -> Node:
    if n.is_leaf:
        return n
    ch = tuple(_norm(c, False) for c in n.children)
    if len(ch) == 1 and (not root or not ch[0].is_leaf):
        return ch[0]
    return Node.group(ch)


def normalize(node: Node) -> Node:
    """Remove redundant single-child wrappers (the root is kept)."""
    return _norm(node, True)


def parse_config(text: str) -> Node:
    """Parse ``text`` into a normalized configuration tree.

    An empty/whitespace string gives the empty configuration (0 strands).
    """
    items, _ = _parse_seq(text, 0, True)
    return normalize(Node.group(items))


def unlabeled(n: int) -> Node:
    """Flat configuration of ``n`` unlabeled strands."""
    if n < 0:
        raise ConfigSyntaxError(f"negative strand count {n}")
    return Node.group([Node.leaf(None) for _ in range(n)])


def replace_leaf(node: Node, index: int, sub: Node) -> Node:
    """Replace the ``index``-th leaf (1-based, left to right) by ``sub``."""
    counter = [0]

    def rec(n: Node) -> Node:
        if n.is_leaf:
            counter[0] += 1
            return sub if counter[0] == index else n
        return Node.group([rec(c) for c in n.children])

    return rec(node)


def collapse(node: Node) -> Node:
    """A one-leaf configuration is just that leaf (so no useless wrapper group)."""
    ls = node.leaves()
    return ls[0] if len(ls) == 1 else node


ConfigLike = Union[str, Node, None]
