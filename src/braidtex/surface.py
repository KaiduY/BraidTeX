r"""Surface braids: algebra of the generators and an independent *motion model* of the torus.

Presentations used (Bellingeri, *On presentations of surface braid groups*, J. Algebra 274 (2004),
Thm. 1.2 for genus 1 and Sect. 5; Fadell-Van Buskirk 1962; Scott 1970):

* sphere:  ``B_n(S^2) = <s_1..s_{n-1} | braid relations, s_1 s_2 ... s_{n-1}^2 ... s_2 s_1 = 1>``
* torus:   generators ``s_1..s_{n-1}, a, b`` (``a``, ``b`` = the first strand goes once round the two
  cycles of the torus) with the braid relations and

  ====  ==============================================================
  R1    a s_i = s_i a,  b s_i = s_i b                        (i != 1)
  R2    s1^-1 a s1^-1 a = a s1^-1 a s1^-1,  same for b
  R4    s1^-1 a s1^-1 b = b s1^-1 a s1
  TR    a b^-1 a^-1 b = s_1 s_2 ... s_{n-1}^2 ... s_2 s_1
  ====  ==============================================================

BraidTeX draws *every* strand's loops (``a_i``, ``b_i`` for the strand in position ``i``).  To make
sure the drawn conventions really are those of the presentation, this module simulates the
generators as explicit motions of points on the flat torus ``R^2/Z^2`` (lifted to ``R^2``) and
computes, for every strand its lifted end point and for every pair of strands the homotopy class of
the *relative* path in ``R^2 minus Z^2`` (as a reduced word of crossings with disjoint rays from the
lattice points).  Equal braids have equal invariants, so the relations above can be *tested* on the
drawn conventions (see ``tests/test_surface.py``).  These invariants are necessary, not sufficient,
for equality of braids; they are rich enough to detect every convention error (orientation of a/b,
front/back, product order) that we tried.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple, Union

Token = Tuple[str, int, int]          # (kind 's'|'a'|'b', position 1-based, sign +1/-1)

EPS = 0.13773                          # tilt of the rays (irrational enough for our purposes)
DELTA = 0.1                            # height of the over/under bumps


def parse_word(spec: Union[str, Sequence]) -> List[Token]:
    """``"1 -2 a1 -b2"`` -> tokens.  Integers are s_i^{+-1}; ``a<i>`` / ``b<i>`` loops; a leading
    ``-`` inverts."""
    items = spec.split() if isinstance(spec, str) else list(spec)
    out: List[Token] = []
    for it in items:
        if isinstance(it, int):
            out.append(("s", abs(it), 1 if it > 0 else -1))
            continue
        t = str(it)
        sign = -1 if t.startswith("-") else 1
        t = t.lstrip("+-")
        if t.isdigit():
            out.append(("s", int(t), sign))
        elif len(t) > 1 and t[0] in "ab" and t[1:].isdigit():
            out.append((t[0], int(t[1:]), sign))
        else:
            raise ValueError(f"bad generator token {it!r}")
    return out


@dataclass(frozen=True)
class Convention:
    """Drawing conventions of the surface generators (see ``DEFAULT``)."""
    a_level: int = +1        # a-loop runs in front (+1) of / behind (-1) the other strands
    a_dir: int = +1          # a^{+1} moves to the right (+1) / left (-1)
    b_dir: int = +1          # b^{+1} moves "forward" (+1) / "backward" (-1) in the depth direction
    s_front: int = +1        # s_i^{+1}: the left-entering strand is in front (+1) / behind (-1)
    reverse: bool = False    # words are read as products of paths right-to-left


DEFAULT = Convention()


class TorusState:
    """n points on the torus at positions p_k = k/(n+1), y = 0; motions are polylines in the lift."""

    def __init__(self, n: int):
        self.n = n
        self.slot_x = [(k + 1) / (n + 1) for k in range(n)]          # fractional x of position k
        self.order = list(range(n))                                  # order[pos] = strand
        self.pos = {k: (self.slot_x[k], 0.0) for k in range(n)}      # lifted positions
        self.frames: List[Dict[int, Tuple[float, float]]] = [dict(self.pos)]

    def _push(self, new: Dict[int, Tuple[float, float]]) -> None:
        self.pos = dict(new)
        self.frames.append(dict(new))

    def apply(self, tok: Token, conv: Convention) -> None:
        kind, i, sign = tok
        n = self.n
        if not (1 <= i <= (n - 1 if kind == "s" else n)):
            raise ValueError(f"generator {tok} invalid for {n} strands")
        if kind == "s":
            L, R = self.order[i - 1], self.order[i]
            d = self.slot_x[i] - self.slot_x[i - 1]
            front = conv.s_front * sign                      # +1: L in front of R
            mid = dict(self.pos)
            mid[L] = (self.pos[L][0] + d / 2, self.pos[L][1] + front * DELTA)
            mid[R] = (self.pos[R][0] - d / 2, self.pos[R][1] - front * DELTA)
            end = dict(self.pos)
            end[L] = (self.pos[L][0] + d, self.pos[L][1])
            end[R] = (self.pos[R][0] - d, self.pos[R][1])
            self._push(mid)
            self._push(end)
            self.order[i - 1], self.order[i] = R, L
        elif kind == "a":
            S = self.order[i - 1]
            x, y = self.pos[S]
            dx = conv.a_dir * sign
            lvl = conv.a_level * DELTA
            f1 = dict(self.pos)
            f1[S] = (x, y + lvl)
            f2 = dict(self.pos)
            f2[S] = (x + dx, y + lvl)
            f3 = dict(self.pos)
            f3[S] = (x + dx, y)
            for f in (f1, f2, f3):
                self._push(f)
        else:                                                # 'b'
            S = self.order[i - 1]
            x, y = self.pos[S]
            f = dict(self.pos)
            f[S] = (x, y + conv.b_dir * sign)
            self._push(f)


# ------------------------------------------------------------------ invariants
PUNCT = 5          # punctures = lattice points of [-PUNCT, PUNCT]^2 (finitely many: see _cross_word)


def _cross_word(path: Sequence[Tuple[float, float]]) -> Tuple[Tuple[int, int, int], ...]:
    """Reduced word of crossings of a polyline with the rays {(m,n) + s(EPS,1), s>0}, one ray for
    each lattice point of a fixed box.  (All of Z^2 would give infinitely many crossings; the
    finite box still gives a valid *necessary* invariant, because R^2 - Z^2 maps into
    R^2 - box-lattice and equal classes stay equal.)  The plane minus the rays is simply connected,
    so the reduced crossing word is the free-group class of the path rel endpoints."""
    word: List[Tuple[int, int, int]] = []
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            continue
        den = dx - dy * EPS
        if abs(den) < 1e-14:
            continue
        hits = []
        for n in range(-PUNCT, PUNCT + 1):
            for m in range(-PUNCT, PUNCT + 1):
                tau = (m - ax + EPS * (ay - n)) / den
                if 0.0 < tau < 1.0 and (ay + tau * dy) - n > 0.0:
                    hits.append((tau, m, n, 1 if den > 0 else -1))
        hits.sort()
        for _, m, n, sg in hits:
            if word and word[-1][0] == m and word[-1][1] == n and word[-1][2] == -sg:
                word.pop()
            else:
                word.append((m, n, sg))
    return tuple(word)


def signature(word: Union[str, Sequence], n: int, conv: Convention = DEFAULT):
    """Invariants of a torus braid word: permutation, lifted end points of every strand and the
    homotopy class of the relative path of every pair of strands in R^2 minus Z^2."""
    toks = parse_word(word)
    if conv.reverse:
        toks = list(reversed(toks))
    st = TorusState(n)
    for t in toks:
        st.apply(t, conv)
    perm = tuple(st.order)
    ends = tuple(tuple(round(c, 9) for c in st.pos[k]) for k in range(n))
    pairs = {}
    for k in range(n):
        for l in range(k + 1, n):
            rel = [(f[k][0] - f[l][0], f[k][1] - f[l][1]) for f in st.frames]
            pairs[(k, l)] = _cross_word(rel)
    return perm, ends, pairs


def equal(w1, w2, n: int, conv: Convention = DEFAULT) -> bool:
    return signature(w1, n, conv) == signature(w2, n, conv)


# ---------------------------------------------------------- the relations to test
def inv(word: Sequence[str]) -> List[str]:
    return [t[1:] if t.startswith("-") else "-" + t for t in reversed(word)]


def relations(n: int) -> Dict[str, Tuple[List[str], List[str]]]:
    """Bellingeri's relations for B_n(T^2) (``a = a_1``, ``b = b_1``) as pairs of words."""
    rel: Dict[str, Tuple[List[str], List[str]]] = {}
    s = lambda i: str(i)                                                 # noqa: E731
    S = lambda i: "-" + str(i)                                           # noqa: E731
    for i in range(1, n - 1):                                            # braid relations
        rel[f"BR s{i}s{i+1}s{i}"] = ([s(i), s(i + 1), s(i)], [s(i + 1), s(i), s(i + 1)])
    for i in range(1, n):
        for j in range(i + 2, n):
            rel[f"BR s{i}s{j}"] = ([s(i), s(j)], [s(j), s(i)])
    for i in range(2, n):                                                # R1
        rel[f"R1 a s{i}"] = (["a1", s(i)], [s(i), "a1"])
        rel[f"R1 b s{i}"] = (["b1", s(i)], [s(i), "b1"])
    if n >= 2:
        for x in "ab":                                                   # R2
            rel[f"R2 {x}"] = ([S(1), x + "1", S(1), x + "1"], [x + "1", S(1), x + "1", S(1)])
        rel["R4"] = ([S(1), "a1", S(1), "b1"], ["b1", S(1), "a1", s(1)])
    full = [str(i) for i in range(1, n)] + [str(n - 1)] + [str(i) for i in range(n - 2, 0, -1)]
    rel["TR"] = (["a1", "-b1", "-a1", "b1"], full if n >= 2 else [])
    return rel


def check_relations(n: int, conv: Convention = DEFAULT) -> Dict[str, bool]:
    return {name: equal(l, r, n, conv) for name, (l, r) in relations(n).items()}


def find_conventions(n_values=(2, 3, 4)) -> List[Convention]:
    """All conventions (out of the 32 combinations) for which every relation holds."""
    good = []
    for a_level in (1, -1):
        for a_dir in (1, -1):
            for b_dir in (1, -1):
                for s_front in (1, -1):
                    for rev in (False, True):
                        c = Convention(a_level, a_dir, b_dir, s_front, rev)
                        if all(all(check_relations(n, c).values()) for n in n_values):
                            good.append(c)
    return good
