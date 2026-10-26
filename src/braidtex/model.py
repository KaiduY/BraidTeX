"""The structured mathematical braid model (renderer independent).

Conventions
-----------
* A braid word is a sequence of non-zero integers; ``+i`` is sigma_i and ``-i``
  its inverse, ``1 <= i <= n-1``.
* The word is read **top to bottom**.  Strands live in *slots* 1..n (left to
  right).  At ``sigma_i`` the strands in slots i and i+1 swap.  For **positive**
  generators the strand entering from the **left** (slot i) passes **over** the
  one entering from the right; negative generators reverse this.
* Strand identity ``k`` (1-based) is the input slot at the top.  Colours and
  annotations attach to identities and follow strands through crossings.
* ``source`` / ``target`` are the mathematical boundary configurations
  (trees whose leaves carry raw LaTeX labels or ``None``).  The label at output
  slot ``j`` must equal the label of the strand that arrives there; this is
  validated.  *Display* labels (``in_labels``/``out_labels``) are purely
  visual and never checked.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .config import GAP, ConfigLike, Node, collapse, parse_config, replace_leaf, unlabeled
from .errors import BraidValidationError, IncompatibleBoundaryError
from .style import PALETTE, Style, check_color

FORMAT_VERSION = 1
SURFACES = ("plane", "sphere", "torus")


@dataclass(frozen=True)
class Loop:
    """Torus generator: the strand in position ``pos`` goes once round a cycle of the torus.

    ``a``: round the horizontal cycle (it passes in front of all other strands, leaves the
    diagram at one side and re-enters at the other).  ``b``: round the depth cycle (front ->
    back -> front, drawn as a ring on the strand).  ``sign = -1``: the inverse loop."""
    kind: str
    pos: int
    sign: int = 1

    def __str__(self) -> str:
        return ("-" if self.sign < 0 else "") + f"{self.kind}{self.pos}"

    def __repr__(self) -> str:
        return f"Loop('{self}')"


@dataclass(frozen=True)
class LoopEvent:
    """A loop generator inside the layer structure (one per layer)."""
    kind: str
    sign: int
    slot: int             # 0-based position
    strand: int           # identity of the strand that loops
    level: int            # 1-based position in the word
    layer: int


Generator = Union[int, Loop]


def parse_generator(g) -> Generator:
    """``3`` / ``"-2"`` -> sigma; ``"a1"`` / ``"-b2"`` / ``Loop`` -> torus loop."""
    if isinstance(g, Loop):
        return g
    if isinstance(g, str):
        t = g.strip()
        sign = -1 if t.startswith("-") else 1
        body = t.lstrip("+-")
        if body.isdigit():
            return sign * int(body)
        if len(body) > 1 and body[0] in "ab" and body[1:].isdigit():
            return Loop(body[0], int(body[1:]), sign)
        raise BraidValidationError(
            f"bad generator {g!r}: use an integer (sigma), or a<i> / b<i> (torus loops), "
            f"optionally with a leading '-'")
    if isinstance(g, bool) or int(g) != g:
        raise BraidValidationError(f"generator {g!r} is not an integer")
    return int(g)


@dataclass(frozen=True)
class Point:
    """Marked point at an endpoint (``side`` 'in' = top, 'out' = bottom)."""
    side: str
    index: int            # 1-based slot
    label: Optional[str] = None


@dataclass(frozen=True)
class Axis:
    """Optional horizontal reference axes through the endpoints."""
    kind: str = "h"       # 'h' = two horizontal axes, 'frame' = plus x=0 arrow and dotted right edge;
                          # 'torus' / 'sphere' = surface frames; 'none' = draw nothing
    front: bool = False
    ticks: bool = True

    def __post_init__(self):
        if self.kind not in ("h", "frame", "torus", "sphere", "none"):
            raise BraidValidationError("axis kind must be h|frame|torus|sphere|none")


@dataclass(frozen=True)
class Region:
    """A ribbon of strands that stands for one strand of an outer braid.

    ``first``/``last`` (1-based, inclusive) are the layers occupied by the inner
    braid, or ``None`` if the inner braid is trivial."""
    strands: Tuple[int, ...]
    first: Optional[int] = None
    last: Optional[int] = None


@dataclass(frozen=True)
class Crossing:
    level: int            # 1-based position in the word (elementary crossing)
    slot: int             # 0-based left slot index of the swapped pair
    sign: int
    over: int             # strand identity on top
    under: int
    generator: int
    layer: int = 0        # 1-based drawing layer


def _as_node(c: ConfigLike) -> Optional[Node]:
    if c is None:
        return None
    if isinstance(c, Node):
        return c
    if isinstance(c, str):
        return parse_config(c)
    raise BraidValidationError(f"cannot interpret {c!r} as a configuration")


def _display(labels: Optional[Sequence[Optional[str]]], n: int, what: str):
    if labels is None:
        return None
    labs = [None if (l is None or l in ("*", GAP)) else str(l) for l in labels]
    if len(labs) != n:
        raise BraidValidationError(f"{what}: expected {n} display labels, got {len(labs)}")
    return tuple(labs)


class Braid:
    """A braid between two (possibly differently parenthesized) configurations.

    Parameters
    ----------
    word : sequence of int
        Artin generators, e.g. ``[1, -2, 1]``.  Empty = identity.
    source, target : str | Node | None
        Boundary configurations, e.g. ``"(x_1 x_2) x_3"``.  If ``target`` is
        omitted it is the source shape with labels permuted by the braid; if
        ``source`` is omitted it is deduced from ``target`` (or unlabeled).
    n : int | None
        Strand count; only needed when it cannot be inferred (unlabeled
        braids).  With nothing else given it is ``max |generator| + 1``.
    colors : dict
        ``{strand_identity: color}`` (identity = 1-based input slot); key
        ``"*"`` is not used here, use ``style.color`` for the main colour.
    notes : dict
        ``{strand_identity: LaTeX text}`` annotations attached to strands.
    points : iterable of Point
    axis : Axis | None
    style : Style
    in_labels, out_labels : sequence | None
        Visual-only replacement labels (``None``/``"*"`` hides one).
    """

    def __init__(self, word: Iterable[int] = (), source: ConfigLike = None,
                 target: ConfigLike = None, *, n: Optional[int] = None,
                 colors: Optional[Dict[int, str]] = None,
                 notes: Optional[Dict[int, str]] = None,
                 points: Iterable[Point] = (), axis: Optional[Axis] = None,
                 style: Optional[Style] = None,
                 in_labels: Optional[Sequence[Optional[str]]] = None,
                 out_labels: Optional[Sequence[Optional[str]]] = None,
                 groups: Optional[Sequence[int]] = None,
                 regions: Iterable[Region] = (), surface: str = "plane"):
        if surface not in SURFACES:
            raise BraidValidationError(f"surface must be one of {', '.join(SURFACES)}, got {surface!r}")
        self.surface: str = surface
        self.word: Tuple[Generator, ...] = tuple(parse_generator(g) for g in word)
        if surface != "torus" and any(isinstance(g, Loop) for g in self.word):
            bad = next(g for g in self.word if isinstance(g, Loop))
            raise BraidValidationError(
                f"loop generator {bad} (torus) is not available on the {surface}: the torus loops "
                f"a_i, b_i exist only with surface=torus")
        self.groups: Optional[Tuple[int, ...]] = None if groups is None else tuple(groups)
        src, tgt = _as_node(source), _as_node(target)

        arities = {k: v for k, v in (("input", src.arity if src else None),
                                     ("output", tgt.arity if tgt else None),
                                     ("n", n)) if v is not None}
        if n is not None and (not isinstance(n, int) or n < 0):
            raise BraidValidationError(f"n must be a non-negative integer, got {n!r}")
        if len(set(arities.values())) > 1:
            raise IncompatibleBoundaryError(
                "arity mismatch: " + ", ".join(f"{k} has {v}" for k, v in arities.items())
                + ". A braid has the same number of strands at both ends.")
        if arities:
            self.n = next(iter(arities.values()))
        elif self.word:
            self.n = max(g.pos if isinstance(g, Loop) else abs(g) + 1 for g in self.word)
        else:
            raise BraidValidationError(
                "cannot infer the number of strands: give an input/output configuration, "
                "an explicit strand count, or at least one crossing")
        self._validate_word()
        self._slots, self.crossings, self.layers = self._simulate()

        # ---- boundary resolution -------------------------------------
        if src is None and tgt is None:
            src = unlabeled(self.n)
        if src is None:
            labs = [None] * self.n
            tl = tgt.labels()
            for j, s in enumerate(self._slots):
                labs[s - 1] = tl[j]
            src = tgt.relabel(labs)
        if tgt is None:
            sl = src.labels()
            tgt = src.relabel([sl[s - 1] for s in self._slots])
        self.source, self.target = src, tgt
        self._check_boundaries()
        for ev in self.loops:
            if ev.strand in self.gap_ids:
                raise BraidValidationError(
                    f"loop {'-' if ev.sign < 0 else ''}{ev.kind}{ev.slot + 1}: that position is a "
                    f"gap ('...'), not a strand")

        # ---- decorations ---------------------------------------------
        self.colors: Dict[int, str] = {}
        for k, v in (colors or {}).items():
            self._check_strand(int(k), "color")
            self._not_gap(int(k), "colour")
            self.colors[int(k)] = check_color(v)
        self.notes: Dict[int, str] = {}
        for k, v in (notes or {}).items():
            self._check_strand(int(k), "note")
            self._not_gap(int(k), "annotation")
            self.notes[int(k)] = str(v)
        self.points: Tuple[Point, ...] = tuple(points)
        for p in self.points:
            if p.side not in ("in", "out") or not (1 <= p.index <= self.n):
                raise BraidValidationError(
                    f"point ({p.side}, {p.index}) outside 1..{self.n} / not in|out")
            leaf = (self.source if p.side == "in" else self.target).labels()[p.index - 1]
            if leaf == GAP:
                raise BraidValidationError(
                    f"point ({p.side}, {p.index}) is on a gap ('...'); gaps are not endpoints")
        self.axis = axis
        self.style = style or Style()
        self.regions: Tuple[Region, ...] = tuple(regions)
        for r in self.regions:
            if not r.strands or any(not (1 <= k <= self.n) for k in r.strands):
                raise BraidValidationError(f"region {r.strands} outside 1..{self.n}")
        self.in_labels = _display(in_labels, self.n, "in_labels")
        self.out_labels = _display(out_labels, self.n, "out_labels")
        if self.style.inpos is not None and len(self.style.inpos) != self.n:
            raise BraidValidationError(f"inpos needs {self.n} values")
        if self.style.outpos is not None and len(self.style.outpos) != self.n:
            raise BraidValidationError(f"outpos needs {self.n} values")

    # ------------------------------------------------------------ validation
    def _validate_word(self) -> None:
        for pos, g in enumerate(self.word, 1):
            if isinstance(g, Loop):
                if not (1 <= g.pos <= self.n):
                    raise BraidValidationError(
                        f"generator #{pos} = {g} is invalid for a braid on {self.n} strand(s): "
                        f"loops need 1 <= position <= {self.n}")
                continue
            if g == 0:
                raise BraidValidationError(f"generator #{pos} is 0; generators are +-1..+-{self.n - 1}")
            if abs(g) > self.n - 1:
                raise BraidValidationError(
                    f"generator #{pos} = {g} is invalid for a braid on {self.n} strand(s): "
                    f"indices must satisfy 1 <= |i| <= {max(self.n - 1, 0)}")

    def _not_gap(self, k: int, what: str) -> None:
        if k in self.gap_ids:
            raise BraidValidationError(
                f"{what}: position {k} is a gap ('...'), not a strand; positions count every "
                f"item of the input configuration, including gaps")

    def _check_strand(self, k: int, what: str) -> None:
        if not (1 <= k <= self.n):
            raise BraidValidationError(f"{what}: strand {k} does not exist (1..{self.n})")

    def _simulate(self):
        """Simulate the word.  A *layer* is a set of crossings drawn side by side
        (default: one crossing per layer); within a layer every pair of strands
        may cross at most once."""
        groups = self.groups if self.groups is not None else (1,) * len(self.word)
        if any((not isinstance(g, int)) or g < 1 for g in groups) or sum(groups) != len(self.word):
            raise BraidValidationError(
                f"groups {list(groups)} must be positive and sum to the word length "
                f"{len(self.word)}")
        slots = list(range(1, self.n + 1))
        crossings: List[Crossing] = []
        layers: List[Tuple[object, ...]] = []
        pos = 0
        for li, size in enumerate(groups, 1):
            if any(isinstance(t, Loop) for t in self.word[pos:pos + size]):
                if size != 1:
                    raise BraidValidationError(
                        f"layer {li}: a loop generator (a/b) must be alone in its layer")
                t = self.word[pos]
                pos += 1
                layers.append((LoopEvent(t.kind, t.sign, t.pos - 1, slots[t.pos - 1], pos, li),))
                continue
            seen = set()
            layer: List[Crossing] = []
            for _ in range(size):
                g = self.word[pos]
                pos += 1
                i = abs(g) - 1
                left, right = slots[i], slots[i + 1]
                pair = frozenset((left, right))
                if pair in seen:
                    raise BraidValidationError(
                        f"layer {li}: strands {left} and {right} would cross twice in one layer")
                seen.add(pair)
                over, under = (left, right) if g > 0 else (right, left)
                c = Crossing(pos, i, 1 if g > 0 else -1, over, under, g, li)
                crossings.append(c)
                layer.append(c)
                slots[i], slots[i + 1] = right, left
            layers.append(tuple(layer))
        return tuple(slots), tuple(crossings), tuple(layers)

    def _check_boundaries(self) -> None:
        sl, tl = self.source.labels(), self.target.labels()
        expected = [sl[s - 1] for s in self._slots]
        for j, (e, got) in enumerate(zip(expected, tl), 1):
            if e != got:
                raise IncompatibleBoundaryError(
                    f"output endpoint {j} is labeled {_fmt(got)} but the strand arriving there "
                    f"(strand {self._slots[j - 1]}, entering as {_fmt(e)}) is labeled "
                    f"{_fmt(e)} at the input. Expected output labels in order: "
                    f"{', '.join(_fmt(x) for x in expected)}.  (Use display labels "
                    f"for purely visual relabeling.)")

    # ------------------------------------------------------------- queries
    @property
    def gap_ids(self) -> frozenset:
        """Identities (input positions) of the gap slots (``...``): invisible placeholders
        for omitted strands.  Every position counts in words, colours and notes."""
        return frozenset(k for k, l in enumerate(self.source.labels(), 1) if l == GAP)

    @property
    def loops(self) -> List[LoopEvent]:
        """Torus loop generators of the word, in order."""
        return [e for layer in self.layers for e in layer if isinstance(e, LoopEvent)]

    @property
    def n_projected_crossings(self) -> int:
        """Crossings in the diagram: sigma crossings plus, for every ``a`` loop, one crossing
        with each of the other strands (``b`` loops cross nothing)."""
        return len(self.crossings) + sum(self.n - 1 for e in self.loops if e.kind == "a")

    @property
    def permutation(self) -> Tuple[int, ...]:
        """``p[k-1]`` = output slot (1-based) reached by strand ``k``."""
        p = [0] * self.n
        for j, s in enumerate(self._slots, 1):
            p[s - 1] = j
        return tuple(p)

    @property
    def strand_at_output(self) -> Tuple[int, ...]:
        """Strand identity arriving at output slot ``j`` (index ``j-1``)."""
        return self._slots

    def slots_at_level(self, t: int) -> List[int]:
        """Strand identities per slot after the first ``t`` generators."""
        slots = list(range(1, self.n + 1))
        for g in self.word[:t]:
            if isinstance(g, Loop):
                continue
            i = abs(g) - 1
            slots[i], slots[i + 1] = slots[i + 1], slots[i]
        return slots

    def strand_color(self, k: int) -> str:
        if k in self.colors:
            return self.colors[k]
        if self.style.palette:
            return PALETTE[(k - 1) % len(PALETTE)]
        return self.style.color

    def display_in(self) -> List[Optional[str]]:
        if self.in_labels is not None:
            return list(self.in_labels)
        return [None if l == GAP else l for l in self.source.labels()]

    def display_out(self) -> List[Optional[str]]:
        if self.out_labels is not None:
            return list(self.out_labels)
        return [None if l == GAP else l for l in self.target.labels()]

    # --------------------------------------------------------- composition
    def compose(self, other: "Braid") -> "Braid":
        """Vertical composition: ``self`` on top, then ``other``.

        Defined only if ``self.target == other.source`` as labeled trees
        (same parenthesization and labels).  This is composition of braids
        as morphisms - not operadic composition, and not picture concatenation.
        """
        if self.target != other.source:
            raise IncompatibleBoundaryError(
                "cannot compose: output configuration "
                f"[{self.target.to_string()}] of the first braid differs from the input "
                f"configuration [{other.source.to_string()}] of the second")
        if self.surface != other.surface:
            raise IncompatibleBoundaryError(
                f"cannot compose braids on different surfaces ({self.surface} / {other.surface})")
        return Braid(self.word + other.word, self.source, other.target,
                     colors=self.colors, notes=self.notes, axis=self.axis, style=self.style,
                     surface=self.surface)

    def compose_at(self, k: int, inner: "Braid", at: Optional[str] = None) -> "Braid":
        """Replace strand ``k`` of this braid by the braid ``inner`` (operadic ``∘_k``).

        The strand is *cabled*: it becomes ``inner.n`` parallel strands that cross
        other strands as one ribbon (all at once, in a single drawing layer).  The
        inner braid is inserted ``at`` = ``'top'`` (default), ``'bottom'`` or after
        the given number of outer layers.  The boundary configurations are those of
        the outer braid with leaf ``k`` (input) / the arrival leaf (output) replaced by
        ``inner.source`` / ``inner.target``; this is independent of ``at``.  Strand
        identities of the result: ``1..k-1`` unchanged, the ribbon ``k..k+m-1``,
        later strands shifted by ``m-1``.  Colours of outer strand ``k`` apply to the
        whole ribbon unless the inner braid colours individual strands.
        """
        if not (1 <= k <= self.n):
            raise BraidValidationError(f"cannot substitute at strand {k}: braid has {self.n}")
        if k in self.gap_ids:
            raise BraidValidationError(f"cannot substitute at position {k}: it is a gap ('...')")
        m = inner.n
        if m < 1:
            raise BraidValidationError("the inner braid needs at least one strand")
        if inner.surface != "plane":
            raise BraidValidationError(
                "the inner braid must be a planar braid: configurations of a surface form a right "
                "module over the little-discs operad (planar discs are inserted into points)")
        at = at if at is not None else self.style.at
        nl = len(self.layers)
        pos = 0 if at == "top" else nl if at == "bottom" else int(at)
        if not (0 <= pos <= nl):
            raise BraidValidationError(f"at={at}: the outer braid has {nl} layer(s)")
        w = {s: 1 for s in range(1, self.n + 1)}
        w[k] = m

        slots = list(range(1, self.n + 1))
        outer_layers: List[List[int]] = []
        history = [list(slots)]
        for layer in self.layers:
            if layer and isinstance(layer[0], LoopEvent):
                ev = layer[0]
                if ev.strand == k:
                    raise BraidValidationError(
                        "cannot substitute into a strand that makes a torus loop (a/b): "
                        "loops of a whole ribbon are not supported yet")
                outer_layers.append([Loop(ev.kind, sum(w[x] for x in slots[:ev.slot]) + 1, ev.sign)])
                history.append(list(slots))
                continue
            s = list(slots)
            gens: List[Generator] = []
            for c in layer:
                i = c.slot
                u, v = w[s[i]], w[s[i + 1]]
                p = sum(w[x] for x in s[:i])
                for r in range(v):
                    for j in range(u):
                        gens.append(c.sign * (p + u + r - j))
                s[i], s[i + 1] = s[i + 1], s[i]
            slots = s
            outer_layers.append(gens)
            history.append(list(slots))
        at_slots = history[pos]
        offset = sum(w[x] for x in at_slots[:at_slots.index(k)])
        inner_layers = [[(1 if c.sign > 0 else -1) * (abs(c.generator) + offset) for c in layer]
                        for layer in inner.layers]
        layers_all = outer_layers[:pos] + inner_layers + outer_layers[pos:]
        word = [g for layer in layers_all for g in layer]
        groups = [len(layer) for layer in layers_all]

        def newid(j: int) -> List[int]:
            return [j] if j < k else list(range(k, k + m)) if j == k else [j + m - 1]

        colors: Dict[int, str] = {}
        for j, col in self.colors.items():
            for nj in newid(j):
                colors[nj] = col
        for j, col in inner.colors.items():
            colors[k + j - 1] = col
        notes: Dict[int, str] = {}
        for j, txt in self.notes.items():
            notes[newid(j)[0]] = txt
        points = []
        for p in self.points:
            if p.index == k and p.side == "in" or \
                    p.side == "out" and p.index == self.permutation[k - 1]:
                raise BraidValidationError(
                    "a marked point on the substituted strand's endpoint is ambiguous; "
                    "place it on a neighbouring strand")
            shift = (lambda idx, at_idx: idx if idx < at_idx else idx + m - 1)
            at_idx = k if p.side == "in" else self.permutation[k - 1]
            points.append(Point(p.side, shift(p.index, at_idx), p.label))
        out_pos = self.permutation[k - 1]
        src = replace_leaf(self.source, k, collapse(inner.source))
        tgt = replace_leaf(self.target, out_pos, collapse(inner.target))
        in_l = out_l = None
        if self.in_labels is not None or inner.in_labels is not None:
            base = self.display_in()
            in_l = base[:k - 1] + inner.display_in() + base[k:]
        if self.out_labels is not None or inner.out_labels is not None:
            base = self.display_out()
            out_l = base[:out_pos - 1] + inner.display_out() + base[out_pos:]

        def shift_layer(x: Optional[int]) -> Optional[int]:
            return x if x is None or x <= pos else x + len(inner_layers)

        regions = []
        for r in self.regions:
            ids: List[int] = []
            for j in r.strands:
                ids.extend(newid(j))
            regions.append(Region(tuple(ids), shift_layer(r.first), shift_layer(r.last)))
        if m >= 2:
            first = pos + 1 if inner_layers else None
            last = pos + len(inner_layers) if inner_layers else None
            regions.append(Region(tuple(range(k, k + m)), first, last))
        return Braid(word, src, tgt, colors=colors, notes=notes, points=points,
                     axis=self.axis, style=self.style, in_labels=in_l, out_labels=out_l,
                     groups=groups, regions=regions, surface=self.surface)

    def replace(self, **kw) -> "Braid":
        """Copy with decorations/style changed (semantics preserved)."""
        d = dict(word=self.word, source=self.source, target=self.target,
                 colors=self.colors, notes=self.notes, points=self.points,
                 axis=self.axis, style=self.style,
                 in_labels=self.in_labels, out_labels=self.out_labels,
                 groups=self.groups, regions=self.regions, surface=self.surface)
        d.update(kw)
        return Braid(**d)

    # ------------------------------------------------------- serialization
    def to_dict(self) -> dict:
        d = {
            "version": FORMAT_VERSION,
            "word": [str(g) if isinstance(g, Loop) else g for g in self.word],
            "source": self.source.to_json(),
            "target": self.target.to_json(),
            "colors": {str(k): v for k, v in sorted(self.colors.items())},
            "notes": {str(k): v for k, v in sorted(self.notes.items())},
            "points": [[p.side, p.index, p.label] for p in self.points],
            "axis": None if self.axis is None else
            {"kind": self.axis.kind, "front": self.axis.front, "ticks": self.axis.ticks},
            "in_labels": None if self.in_labels is None else list(self.in_labels),
            "out_labels": None if self.out_labels is None else list(self.out_labels),
            "style": self.style.to_dict(),
        }
        if self.n == 0:
            d["n"] = 0
        if self.surface != "plane":
            d["surface"] = self.surface
        if self.groups is not None and any(g != 1 for g in self.groups):
            d["groups"] = list(self.groups)
        if self.regions:
            d["regions"] = [[list(r.strands), r.first, r.last] for r in self.regions]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Braid":
        if d.get("version", FORMAT_VERSION) != FORMAT_VERSION:
            raise BraidValidationError(f"unsupported spec version {d.get('version')!r}")
        known = {"version", "word", "source", "target", "colors", "notes", "points",
                 "axis", "in_labels", "out_labels", "style", "n", "groups", "regions", "surface"}
        extra = set(d) - known
        if extra:
            raise BraidValidationError(f"unknown keys in braid spec: {sorted(extra)}")
        def cfg(v):
            if v is None:
                return None
            return parse_config(v) if isinstance(v, str) else Node.from_json(v)

        a = d.get("axis")
        return Braid(
            d.get("word", []), cfg(d.get("source")), cfg(d.get("target")),
            n=d.get("n"),
            colors={int(k): v for k, v in d.get("colors", {}).items()},
            notes={int(k): v for k, v in d.get("notes", {}).items()},
            points=[Point(*p) for p in d.get("points", [])],
            axis=None if a is None else Axis(**a),
            style=Style.from_dict(d["style"]) if "style" in d else Style(),
            in_labels=d.get("in_labels"), out_labels=d.get("out_labels"),
            groups=d.get("groups"),
            regions=[Region(tuple(r[0]), r[1], r[2]) for r in d.get("regions", [])],
            surface=d.get("surface", "plane"))

    def to_json(self, **kw) -> str:
        return json.dumps(self.to_dict(), **kw)

    @staticmethod
    def from_json(text: str) -> "Braid":
        return Braid.from_dict(json.loads(text))

    def __repr__(self) -> str:
        return (f"Braid(word={list(self.word)}, source={self.source.to_string()!r}, "
                f"target={self.target.to_string()!r})")


def _fmt(label: Optional[str]) -> str:
    return "<unlabeled>" if label is None else repr(label)
