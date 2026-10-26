"""Geometry: continuous strand paths and clean over/under crossings.

Construction
------------
The diagram has ``B = max(len(word), 1)`` bands between a top stub of height
``pad`` and a bottom stub.  Slot ``j`` sits at ``x_t[j] = in[j] + (out[j]-in[j]) t/B``
on level ``t``; both layouts are strictly increasing, so slots stay ordered.
Inside band ``t`` every strand is one cubic Bezier with *vertical tangents* at both
ends and a common monotone ``y(s)``; ``x(s) = x0 + (x1-x0) f(s)`` with the same
``f(s) = 3s^2 - 2s^3`` for all strands.  Any two strands therefore differ by a
function linear in ``f``: strands that do not swap never meet, and the two
strands of a swap meet exactly once.  Hence the picture has exactly ``len(word)``
crossings regardless of how different the input and output spacings are.

At a crossing the *under* strand is cut (real vector gap, no white masking)
over the parameter interval where it is closer than the clearance to the
*over* strand.  All joins are G1 (vertical tangents) and share exact endpoints.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .discs import Disc, disc_layout, root_radius
from .layout import normalized_positions
from .model import Braid, LoopEvent

Pt = Tuple[float, float]
PT_CM = 2.54 / 72.27


@dataclass(frozen=True)
class Bez:
    p0: Pt
    c1: Pt
    c2: Pt
    p3: Pt


def bez_point(b: Bez, s: float) -> Pt:
    u = 1 - s
    a, c, d, e = u ** 3, 3 * u * u * s, 3 * u * s * s, s ** 3
    return (a * b.p0[0] + c * b.c1[0] + d * b.c2[0] + e * b.p3[0],
            a * b.p0[1] + c * b.c1[1] + d * b.c2[1] + e * b.p3[1])


def _mid(p: Pt, q: Pt, s: float) -> Pt:
    return (p[0] + (q[0] - p[0]) * s, p[1] + (q[1] - p[1]) * s)


def split(b: Bez, s: float) -> Tuple[Bez, Bez]:
    """de Casteljau subdivision at parameter ``s``."""
    a, c, d = _mid(b.p0, b.c1, s), _mid(b.c1, b.c2, s), _mid(b.c2, b.p3, s)
    e, f = _mid(a, c, s), _mid(c, d, s)
    g = _mid(e, f, s)
    return Bez(b.p0, a, e, g), Bez(g, f, d, b.p3)


def _line(p: Pt, q: Pt) -> Bez:
    return Bez(p, _mid(p, q, 1 / 3), _mid(p, q, 2 / 3), q)


NATURAL_EASE = 0.6  # handle length (fraction of the layer height) in natural mode: rounder bends
BAND_EASE = 0.5     # length of the vertical Bezier handles as a fraction of the layer height
# (1/3 would make y linear in the parameter but gives near-kinks at the joins: peak curvature
#  falls from ~9/cm to ~4/cm with 1/2 while y stays strictly monotone)


def _band(x0: float, y0: float, x1: float, y1: float) -> Bez:
    dy = (y1 - y0) * BAND_EASE
    return Bez((x0, y0), (x0, y0 + dy), (x1, y1 - dy), (x1, y1))


def _x_at_height(path: List[Bez], y: float) -> float:
    """x of a y-monotone (downward) piecewise Bezier path at height ``y``."""
    for sg in path:
        if sg.p0[1] >= y >= sg.p3[1] - 1e-12:
            lo, hi = 0.0, 1.0
            for _ in range(40):
                mid = (lo + hi) / 2
                if bez_point(sg, mid)[1] > y:
                    lo = mid
                else:
                    hi = mid
            return bez_point(sg, (lo + hi) / 2)[0]
    return path[-1].p3[0] if y < path[-1].p3[1] else path[0].p0[0]


def _near_intervals(a: Bez, b: Bez, width: float) -> List[Tuple[float, float]]:
    """Parameter intervals where ``|x_a(s) - x_b(s)| < width`` (same height for equal s)."""
    N = 40
    inside = [abs(bez_point(a, i / N)[0] - bez_point(b, i / N)[0]) < width for i in range(N + 1)]

    def edge(s_out: float, s_in: float) -> float:
        for _ in range(25):
            m = (s_out + s_in) / 2
            if abs(bez_point(a, m)[0] - bez_point(b, m)[0]) < width:
                s_in = m
            else:
                s_out = m
        return (s_out + s_in) / 2

    out: List[Tuple[float, float]] = []
    start: Optional[float] = None
    for i in range(N + 1):
        if inside[i] and start is None:
            start = 0.0 if i == 0 else edge((i - 1) / N, i / N)
        if start is not None and (not inside[i] or i == N):
            end = 1.0 if (inside[i] and i == N) else edge(i / N, (i - 1) / N)
            out.append((start, end))
            start = None
    return out


def _merge(ivs: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    merged: List[List[float]] = []
    for lo, hi in sorted(ivs):
        if merged and lo <= merged[-1][1] + 1e-9:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(a, b) for a, b in merged]


def _split_runs(segs: List[Bez], cuts: Dict[int, List[Tuple[float, float]]],
                dots: Dict[int, List[Tuple[float, float]]], breaks=frozenset()):
    """Solid runs and dotted runs of one strand.  ``cuts``: crossing gaps (nothing drawn);
    ``dots``: stretches inside a gap region (drawn dotted).  Both keyed by segment index."""
    solid: List[List[Bez]] = []
    dotted: List[List[Bez]] = []
    cur: List[Bez] = []
    kind = ""

    def flush() -> None:
        nonlocal cur
        if cur:
            (solid if kind == "solid" else dotted).append(cur)
        cur = []

    for idx, seg in enumerate(segs):
        if idx in breaks:                       # seam jump: the path is not connected here
            flush()
            kind = ""
        cm, dm = _merge(cuts.get(idx, [])), _merge(dots.get(idx, []))
        pts = sorted({0.0, 1.0} | {x for iv in cm + dm for x in iv})
        for a, b in zip(pts, pts[1:]):
            if b - a < 1e-9:
                continue
            mid = (a + b) / 2
            if any(lo <= mid <= hi for lo, hi in cm):
                flush()
                kind = ""
                continue
            k = "dotted" if any(lo <= mid <= hi for lo, hi in dm) else "solid"
            if k != kind:
                flush()
                kind = k
            cur.append(seg if (a <= 1e-9 and b >= 1 - 1e-9) else subcurve(seg, a, b))
    flush()
    return solid, dotted


def _min_dist(px: float, py: float, polys: List[List[Pt]]) -> float:
    best = 1e9
    for poly in polys:
        for i in range(len(poly) - 1):
            a, b = poly[i], poly[i + 1]
            if min(a[1], b[1]) - 0.6 > py or max(a[1], b[1]) + 0.6 < py:
                continue
            best = min(best, _seg_dist((px, py), a, b))
    return best


def _place_gaps(segs: Dict[int, List[Bez]], strands: List["StrandGeom"], gap_set, pitch: Dict[int, float],
                hw: Dict[int, float], H: float, st) -> Tuple[List[GapGeom], List[float]]:
    """Dot rows for all gaps.  Rows are shared by every gap (so they are aligned), each row is
    centred on its gap's own (invisible) path, and a row is moved up or down until no dot comes
    close to any strand; rows that cannot be placed are dropped (with a smaller dot pitch as a
    last resort).  Raises no error: if nothing fits, the gap is left empty and a warning issued."""
    gaps = [GapGeom(k, pitch[k], hw[k]) for k in sorted(gap_set)]
    polys = [pc for s in strands if s.ident not in gap_set for pc in polylines(s, 24)]
    # dotted strands look like dots themselves: keep the rows further away from them
    need = (0.2 if st.gapthrough == "dotted" else 0.115) + st.lw * PT_CM / 2
    m = st.gapdots

    def dots_at(gp: GapGeom, y: float, scale: float):
        x0 = _x_at_height(segs[gp.ident], y)
        return [(x0 + (j - (m - 1) / 2) * gp.pitch * scale, y) for j in range(m)]

    def clear(gp: GapGeom, y: float, scale: float) -> bool:
        return all(_min_dist(px, py, polys) >= need for px, py in dots_at(gp, y, scale))

    rows_n = int(st.gaprows) if st.gaprows != "auto" else max(1, round(H / 1.5))
    ideal = [H * (r + 0.5) / rows_n for r in range(rows_n)]
    win = 0.35 * H / rows_n
    offsets = [0.0]
    d = 0.04
    while d <= win + 1e-9:
        offsets += [d, -d]
        d += 0.04
    lo_y, hi_y = min(0.12, H / 4), H - min(0.12, H / 4)

    for scale in (1.0, 0.75, 0.5):
        rows: List[float] = []
        for y0 in ideal:
            for dl in offsets:
                y = y0 + dl
                if lo_y <= y <= hi_y and all(clear(gp, y, scale) for gp in gaps):
                    rows.append(y)
                    break
        if rows:
            for gp in gaps:
                gp.dots = [pt for y in rows for pt in dots_at(gp, y, scale)]
            return gaps, rows
    # no common height: place each gap's row independently (unaligned) rather than drop it
    for gp in gaps:
        for dl in sorted((i * 0.04 for i in range(-int(H / 0.04), int(H / 0.04) + 1)), key=abs):
            y = H / 2 + dl
            if lo_y <= y <= hi_y and clear(gp, y, 0.5):
                gp.dots = dots_at(gp, y, 0.5)
                break
        else:
            warnings.warn(f"no room for the dots of the gap at position {gp.ident}; "
                          f"increase band, width or spacing", stacklevel=3)
    return gaps, []


def _hermite_bez(x0: float, y0: float, x1: float, y1: float, m0: float, m1: float,
                 ease: Optional[float] = None) -> Bez:
    """Cubic curve from (x0,y0) to (x1,y1) (y decreasing) with slopes ``m = dx/d(depth)``
    at both ends.  Equal slopes on both sides of a level make the join G1."""
    dy = (y1 - y0) * (NATURAL_EASE if ease is None else ease)
    run = abs(dy)
    return Bez((x0, y0), (x0 + m0 * run, y0 + dy), (x1 - m1 * run, y1 - dy), (x1, y1))


def _slopes(knots: List[float], depth: float, tension: float) -> List[float]:
    """Monotone (Fritsch-Carlson, equal spacing) tangent slopes at the levels.

    A strand that keeps moving in one direction gets the harmonic mean of the neighbouring
    secants (nearly straight); at a turning point or a standstill the slope is 0.  The
    end slopes are 0 (strings leave the endpoints vertically).  ``tension`` scales all
    slopes: 0 gives the default zero-slope shapes."""
    m = [0.0] * len(knots)
    sec = [(knots[i + 1] - knots[i]) / depth for i in range(len(knots) - 1)]
    for i in range(1, len(knots) - 1):
        a, b = sec[i - 1], sec[i]
        if a * b > 1e-12:
            m[i] = tension * 2 * a * b / (a + b)
    return m


def _wrapped(knots: List[float], wrap: float) -> List[float]:
    """Let a strand swing ``wrap`` further at a back-and-forth turn (rounder loops)."""
    out = list(knots)
    if wrap <= 0:
        return out
    for i in range(1, len(knots) - 1):
        a, b = knots[i] - knots[i - 1], knots[i + 1] - knots[i]
        if a * b < -1e-12:
            out[i] = knots[i] + (wrap if a > 0 else -wrap)
    return out


def _seg_dist(p: Pt, a: Pt, b: Pt) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _poly_dist(p: Pt, poly: List[Pt]) -> float:
    return min(_seg_dist(p, poly[i], poly[i + 1]) for i in range(len(poly) - 1))


@dataclass
class CrossingGeom:
    level: int                     # drawing layer
    center: Pt
    over: int
    under: int
    sign: int
    generator: int
    gap: Tuple[float, float]       # parameter interval cut from the under strand
    clamped: bool = False


@dataclass
class StrandGeom:
    ident: int
    color: str
    segments: List[Bez]            # complete path: top stub, bands, bottom stub
    runs: List[List[Bez]] = field(default_factory=list)   # solid pieces (after crossing gaps)
    dotted_runs: List[List[Bez]] = field(default_factory=list)  # pieces drawn dotted (in a gap)
    hidden: bool = False           # a gap slot ("..."): never drawn as a line
    jumps: List[int] = field(default_factory=list)   # segment indices that start after a seam jump


@dataclass
class GapGeom:
    """A gap ("...") region: dot centres, aligned in rows shared by all gaps."""
    ident: int
    pitch: float
    halfwidth: float               # half-width of the region (used for dotted traversal)
    dots: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class RegionGeom:
    strands: Tuple[int, ...]
    left: List[Bez]                # boundary curve (top to bottom), already cut to the extent
    right: List[Bez]
    first: Optional[int]
    last: Optional[int]


@dataclass
class Geometry:
    width: float
    height: float
    in_x: List[float]
    out_x: List[float]
    strands: List[StrandGeom]
    crossings: List[CrossingGeom]
    levels_y: List[float]          # y of level t (t = 0..bands) after the top stub
    bands: int
    regions: List[RegionGeom] = field(default_factory=list)
    discs_in: List[Disc] = field(default_factory=list)
    discs_out: List[Disc] = field(default_factory=list)
    pad_top: float = 0.0
    pad_bottom: float = 0.0
    gaps: List[GapGeom] = field(default_factory=list)
    gap_rows: List[float] = field(default_factory=list)
    seams: List[Tuple[float, int, int]] = field(default_factory=list)   # (y, direction, strand)
    marks: List[Tuple[str, int, float, float, int]] = field(default_factory=list)  # (kind, strand, x, y, sign)


def default_width(n: int, margin: float, spacing: float = 0.9, minspan: float = 1.2) -> float:
    return 2 * margin + max(minspan, spacing * (n - 1))


def subcurve(b: Bez, s0: float, s1: float) -> Bez:
    if s0 > 0:
        _, b = split(b, s0)
        s1 = (s1 - s0) / (1 - s0)
    if s1 < 1:
        b, _ = split(b, s1)
    return b


def _reverse(b: Bez) -> Bez:
    return Bez(b.p3, b.c2, b.c1, b.p0)


def reverse_path(path: List[Bez]) -> List[Bez]:
    return [_reverse(b) for b in reversed(path)]


def _build(braid: Braid, tau: float, wrap: float, natural: bool, strict: bool):
    """Build the geometry.  Returns ``(geometry, ok)``; with ``strict`` a failed natural
    attempt returns ``(None, False)`` immediately so the caller can lower the tension."""
    st, n = braid.style, braid.n
    # geometry layers: crossings; an a-loop = two layers (run to the edge / re-enter); b-loop = ring
    glayers: List[Tuple[str, object]] = []
    lmap: List[Tuple[int, int]] = []              # logical layer -> (first, last) geometry layer
    for layer in braid.layers:
        first = len(glayers) + 1
        if layer and isinstance(layer[0], LoopEvent):
            ev = layer[0]
            glayers += [("A", ev), ("B", ev)] if ev.kind == "a" else [("ring", ev)]
        else:
            glayers.append(("x", layer))
        lmap.append((first, len(glayers)))
    B = max(len(glayers), 1)
    W = st.width if st.width is not None else default_width(n, st.margin, st.spacing, st.minspan)
    if W - 2 * st.margin <= 0:
        raise ValueError("diagram too small: width <= 2*margin")

    def xs(tree, custom):
        u = normalized_positions(tree, st.rho, st.wmin, custom, st.gapspan)
        return [st.margin + p * (W - 2 * st.margin) for p in u]

    in_x, out_x = xs(braid.source, st.inpos), xs(braid.target, st.outpos)
    for name, v in (("input", in_x), ("output", out_x)):
        if len(v) > 1 and min(b - a for a, b in zip(v, v[1:])) < 0.25:
            warnings.warn(f"{name} endpoints are closer than 2.5 mm; increase width or "
                          f"reduce nesting (rho/wmin)", stacklevel=2)

    d_in = disc_layout(braid.source, in_x) if st.discs_in else []
    d_out = disc_layout(braid.target, out_x) if st.discs_out else []
    pad_top = max(st.pad, root_radius(d_in) + 0.12) if d_in else st.pad
    pad_bot = max(st.pad, root_radius(d_out) + 0.12) if d_out else st.pad
    H = st.height if st.height is not None else pad_top + pad_bot + B * st.band
    inner = H - pad_top - pad_bot
    if inner <= 0:
        raise ValueError("diagram too small: height <= top + bottom padding")

    bh = inner / B
    ys = [H - pad_top - t * bh for t in range(B + 1)]

    # Layers inside a ribbon (the inner braid) carry no horizontal drift between the input
    # and output layouts, so the inner braid is drawn undistorted; the other layers do the
    # repositioning.  The parameter stays monotone in [0, 1], hence slots stay ordered.
    inner_layers = {t for r in braid.regions if r.first is not None
                    for t in range(lmap[r.first - 1][0], lmap[(r.last or r.first) - 1][1] + 1)}
    wts = [0.0 if t in inner_layers else 1.0 for t in range(1, B + 1)]
    if sum(wts) == 0:
        wts = [1.0] * B
    prog = [0.0]
    for wt in wts:
        prog.append(prog[-1] + wt / sum(wts))

    def x_at(t: int, j: int) -> float:
        return in_x[j] + (out_x[j] - in_x[j]) * prog[t]

    # strand identity per slot after t layers
    levels: List[List[int]] = [list(range(1, n + 1))]
    for kind, payload in glayers:
        s = list(levels[-1])
        if kind == "x":
            for c in payload:
                s[c.slot], s[c.slot + 1] = s[c.slot + 1], s[c.slot]
        levels.append(s)
    if not glayers:
        levels.append(list(levels[0]))

    gap_set = braid.gap_ids
    pitch: Dict[int, float] = {}
    hw: Dict[int, float] = {}
    for gid in gap_set:                       # dot pitch from the space next to each gap
        dmin = 1e9
        for t in range(B + 1):
            j = levels[t].index(gid)
            for jj in (j - 1, j + 1):
                if 0 <= jj < n and levels[t][jj] not in gap_set:
                    dmin = min(dmin, abs(x_at(t, j) - x_at(t, jj)))
        dmin = 1.0 if dmin > 1e8 else dmin
        pitch[gid] = min(0.18, 0.32 * dmin)
        hw[gid] = (st.gapdots - 1) / 2 * pitch[gid] + 0.12
        if pitch[gid] < 0.07:
            warnings.warn(f"the gap at position {gid} is very narrow; increase width or spacing "
                          f"(or gapspan)", stacklevel=3)
    knots: Dict[int, List[float]] = {}
    slopes: Dict[int, List[float]] = {}
    if natural:
        for k in range(1, n + 1):
            seq = [x_at(t, levels[t].index(k)) for t in range(B + 1)]
            knots[k] = _wrapped(seq, wrap)
            slopes[k] = _slopes(knots[k], bh, tau)

    segs: Dict[int, List[Bez]] = {k: [_line((in_x[k - 1], H), (in_x[k - 1], ys[0]))]
                                  for k in range(1, n + 1)}
    xings: List[CrossingGeom] = []
    ok = True
    jumps: Dict[int, List[int]] = {}
    seams: List[Tuple[float, int, int]] = []
    marks: List[Tuple[str, int, float, float, int]] = []
    cuts: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
    dot_iv: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
    clearance = st.gap + st.lw * PT_CM
    for t in range(1, B + 1):
        curves: Dict[int, Bez] = {}
        for k in range(1, n + 1):
            js, je = levels[t - 1].index(k), levels[t].index(k)
            if natural:
                curves[k] = _hermite_bez(knots[k][t - 1], ys[t - 1], knots[k][t], ys[t],
                                         slopes[k][t - 1], slopes[k][t])
            else:
                curves[k] = _band(x_at(t - 1, js), ys[t - 1], x_at(t, je), ys[t])
            segs[k].append(curves[k])
        kind, payload = glayers[t - 1] if glayers else ("x", ())
        mv = payload.strand if kind in ("A", "B", "ring") else None
        ease = NATURAL_EASE if natural else BAND_EASE
        if kind in ("A", "B"):                   # the looping strand runs to / enters from a frame edge
            ev = payload
            dirn = 1 if ev.sign > 0 else -1
            js = levels[t - 1].index(mv)
            x_start = knots[mv][t - 1] if natural else x_at(t - 1, js)
            x_end = knots[mv][t] if natural else x_at(t, js)
            m0 = slopes[mv][t - 1] if natural else 0.0
            m1 = slopes[mv][t] if natural else 0.0
            run = ease * (ys[t - 1] - ys[t])
            if kind == "A":
                edge_x = W if dirn > 0 else 0.0
                dx = abs(edge_x - x_start)
                me = dirn * max(0.0, min(1.0, 0.9 * (dx - abs(m0) * run) / run))
                curves[mv] = _hermite_bez(x_start, ys[t - 1], edge_x, ys[t], m0, me, ease)
            else:
                edge_x = 0.0 if dirn > 0 else W
                dx = abs(x_end - edge_x)
                me = dirn * max(0.0, min(1.0, 0.9 * (dx - abs(m1) * run) / run))
                curves[mv] = _hermite_bez(edge_x, ys[t - 1], x_end, ys[t], me, m1, ease)
                jumps.setdefault(mv, []).append(t)          # segment index t starts after the jump
                seams.append((ys[t - 1], dirn, mv))
            segs[mv][-1] = curves[mv]
        elif kind == "ring":
            ev = payload
            xm, ym = bez_point(curves[mv], 0.5)
            marks.append(("b", mv, xm, ym, ev.sign))
        if natural and kind not in ("A", "B") and \
                not _layer_ok(curves, levels[t - 1], levels[t], W):
            if strict:
                return None, False
            ok = False
        if gap_set and st.gapthrough == "dotted":     # a strand inside a gap region is dotted
            for gid in gap_set:
                for k in range(1, n + 1):
                    if k not in gap_set:
                        ivs = _near_intervals(curves[k], curves[gid], hw[gid])
                        if ivs:
                            dot_iv.setdefault((k, t), []).extend(ivs)

        def cross(ov: Bez, un: Bez, o_id: int, u_id: int, sign: int, gen: int) -> bool:
            """Crossing of ``ov`` over ``un`` in this layer: its position and the gap cut in the
            under-strand.  Returns False if a strict natural attempt must be abandoned."""
            neg0 = bez_point(ov, 0.0)[0] < bez_point(un, 0.0)[0]
            lo, hi = 0.0, 1.0
            for _ in range(60):                       # x_over - x_under changes sign once
                mid = (lo + hi) / 2
                if (bez_point(ov, mid)[0] < bez_point(un, mid)[0]) == neg0:
                    lo = mid
                else:
                    hi = mid
            s_star = (lo + hi) / 2
            if o_id in gap_set or u_id in gap_set:    # passing a gap: nothing to cut
                xings.append(CrossingGeom(t, bez_point(ov, s_star), o_id, u_id, sign, gen,
                                          (0.0, 0.0), False))
                return True
            poly = [bez_point(ov, i / 120) for i in range(121)]

            def d(s: float) -> float:
                return _poly_dist(bez_point(un, s), poly)

            def edge(a: float, b: float) -> Tuple[float, bool]:
                if d(a) < clearance:
                    return a, True
                for _ in range(40):
                    m = (a + b) / 2
                    if d(m) >= clearance:
                        a = m
                    else:
                        b = m
                return (a + b) / 2, False

            s_lo, c1 = edge(0.0, s_star)
            s_hi, c2 = edge(1.0, s_star)
            if c1 or c2:
                if natural and strict:
                    return False
                warnings.warn(f"layer {t}: the clearance gap of a crossing reaches the end of "
                              f"its layer; increase band/width or decrease gap", stacklevel=2)
            cuts.setdefault((u_id, t), []).append((s_lo, s_hi))
            xings.append(CrossingGeom(t, bez_point(ov, s_star), o_id, u_id, sign, gen,
                                      (s_lo, s_hi), c1 or c2))
            return True

        if kind == "x":
            for cr in payload:
                if not cross(curves[cr.over], curves[cr.under], cr.over, cr.under, cr.sign,
                             cr.generator):
                    return None, False
        elif kind in ("A", "B"):                      # the looping strand passes in front of everything
            for j in range(1, n + 1):
                if j == mv:
                    continue
                a0 = bez_point(curves[mv], 0.0)[0] < bez_point(curves[j], 0.0)[0]
                a1 = bez_point(curves[mv], 1.0)[0] < bez_point(curves[j], 1.0)[0]
                if a0 != a1 and not cross(curves[mv], curves[j], mv, j, 0, 0):
                    return None, False

    strands: List[StrandGeom] = []
    for k in range(1, n + 1):
        px = out_x[braid.permutation[k - 1] - 1]
        segs[k].append(_line((px, ys[B]), (px, 0.0)))
        if k in gap_set:
            strands.append(StrandGeom(k, st.gapcolor, segs[k], [], [], True, list(jumps.get(k, []))))
            continue
        kc = {idx: v for (kk, idx), v in cuts.items() if kk == k}
        kd = {idx: v for (kk, idx), v in dot_iv.items() if kk == k}
        solid, dotted = _split_runs(segs[k], kc, kd, frozenset(jumps.get(k, [])))
        strands.append(StrandGeom(k, braid.strand_color(k), segs[k], solid, dotted, False,
                                  list(jumps.get(k, []))))
    gap_geoms: List[GapGeom] = []
    gap_rows: List[float] = []
    if gap_set:
        gap_geoms, gap_rows = _place_gaps(segs, strands, gap_set, pitch, hw, H, st)

    regions, rok = _regions(braid, levels, x_at, ys, H, B, st, natural, tau, wrap, bh, segs, lmap)
    if natural and not rok:
        if strict:
            return None, False
        ok = False
    return Geometry(W, H, in_x, out_x, strands, xings, ys, B, regions, d_in, d_out,
                    pad_top, pad_bot, gap_geoms, gap_rows, seams, marks), ok


def _layer_ok(curves: Dict[int, Bez], prev: List[int], nxt: List[int], width: float) -> bool:
    """Is this layer exactly the intended crossing pattern?  Sampled at common heights:
    a pair that swaps must change the sign of ``x_a - x_b`` exactly once, any other pair
    never, and non-crossing strands must keep a visible distance."""
    ks = sorted(curves)
    xs = {k: [bez_point(curves[k], i / 16)[0] for i in range(17)] for k in ks}
    for k in ks:
        if min(xs[k]) < -0.05 or max(xs[k]) > width + 0.05:
            return False
    for ia, a in enumerate(ks):
        for b in ks[ia + 1:]:
            start = 1 if prev.index(a) > prev.index(b) else -1
            end = 1 if nxt.index(a) > nxt.index(b) else -1
            changes, last, closest = 0, 0, 1e9
            for xa, xb in zip(xs[a], xs[b]):
                d = xa - xb
                closest = min(closest, abs(d))
                if abs(d) < 1e-9:
                    continue
                sg = 1 if d > 0 else -1
                if last and sg != last:
                    changes += 1
                last = sg
            if changes != (1 if start != end else 0):
                return False
            if start == end and closest < 0.1:
                return False
    return True


def _regions(braid: Braid, levels, x_at, ys, H: float, B: int, st, natural: bool = False,
             tau: float = 0.0, wrap: float = 0.0, bh: float = 1.0,
             segs=None, lmap=None) -> Tuple[List[RegionGeom], bool]:
    out: List[RegionGeom] = []
    ok = True
    if st.compose == "none":
        return out, ok
    d = st.regionpad
    for r in braid.regions:
        ids = set(r.strands)
        ext = [(min(j for j, k in enumerate(lv) if k in ids),
                max(j for j, k in enumerate(lv) if k in ids)) for lv in levels]
        for t, (a, b) in enumerate(ext):
            if b - a + 1 != len(ids):
                warnings.warn(f"ribbon {sorted(ids)} is not contiguous after layer {t}; "
                              f"its region marking may look wrong", stacklevel=3)
            if a > 0 and x_at(t, a) - d <= x_at(t, a - 1) + 0.03 or \
                    b < braid.n - 1 and x_at(t, b) + d >= x_at(t, b + 1) - 0.03:
                warnings.warn("regionpad is too large for the spacing next to the ribbon; "
                              "reduce regionpad or increase width", stacklevel=3)
                break

        def guide(side: int) -> List[Bez]:
            xs = [x_at(t, ext[t][0 if side < 0 else 1]) + side * d for t in range(B + 1)]
            path = [_line((xs[0], H), (xs[0], ys[0]))]
            if natural:
                kn = _wrapped(xs, wrap)
                sl = _slopes(kn, bh, tau)
            for t in range(1, B + 1):
                if natural:
                    path.append(_hermite_bez(kn[t - 1], ys[t - 1], kn[t], ys[t], sl[t - 1], sl[t]))
                else:
                    path.append(_band(xs[t - 1], ys[t - 1], xs[t], ys[t]))
            path.append(_line((xs[B], ys[B]), (xs[B], 0.0)))
            return path

        extent = st.extent
        if extent == "auto":
            extent = "full" if (st.compose == "shadow" or r.first is None) else "inner"
        if extent == "full" or r.first is None:
            i0, i1 = 0, B + 1
        else:
            gf = lmap[r.first - 1][0] if lmap else r.first
            gl = lmap[r.last - 1][1] if lmap else r.last
            i0 = 0 if gf == 1 else gf
            i1 = B + 1 if gl == B else gl
        FL, FR = guide(-1), guide(+1)
        if natural and segs is not None:      # the markings must stay clear of the ribbon strands
            for t in range(1, B + 1):
                for u in (0.0, 0.25, 0.5, 0.75, 1.0):
                    lx, rx = bez_point(FL[t], u)[0], bez_point(FR[t], u)[0]
                    for k in ids:
                        px = bez_point(segs[k][t], u)[0]
                        if not (lx < px - 0.03 and px < rx - 0.03):
                            ok = False
        L, R = FL[i0:i1 + 1], FR[i0:i1 + 1]
        out.append(RegionGeom(tuple(sorted(ids)), L, R, r.first, r.last))
    return out, ok


def build_geometry(braid: Braid) -> Geometry:
    """Strand geometry in the style chosen by ``braid.style.geometry``.

    ``default``: every layer is an independent S-curve with vertical tangents at the
    layer boundaries (provably exactly one crossing per swapping pair).
    ``natural``: every strand is one string - a spline through its positions at the
    layer boundaries with monotone tangents (nearly straight through consecutive
    crossings, bends only at real turns).  The result is verified layer by layer; if a
    check fails the tension (and wrap) are reduced stepwise, ending at the default shapes
    (tension 0), which are always correct."""
    st = braid.style
    if st.geometry != "natural":
        return _build(braid, 0.0, 0.0, False, False)[0]
    for f in (1.0, 0.75, 0.5, 0.25, 0.0):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            geom, ok = _build(braid, st.tension * f, st.wrap * f, True, f > 0)
        if ok or f == 0.0:
            for w in caught:                  # replay only the warnings of the accepted attempt
                warnings.warn(w.message, w.category, stacklevel=2)
            return geom
    raise AssertionError("unreachable")


# --------------------------------------------------------------- analysis
def polyline(strand: StrandGeom, per_seg: int = 24) -> List[Pt]:
    """Samples of the whole path; sample ``idx*per_seg + i`` is at parameter ``i/per_seg`` of
    segment ``idx`` (so equal indices of different strands are at equal heights).  A seam jump
    is a discontinuity between two consecutive samples (see ``strand.jumps``)."""
    pts: List[Pt] = []
    for sg in strand.segments:
        for i in range(per_seg):
            pts.append(bez_point(sg, i / per_seg))
    pts.append(strand.segments[-1].p3)
    return pts


def polylines(strand: StrandGeom, per_seg: int = 24) -> List[List[Pt]]:
    """The path as connected polylines (split at seam jumps)."""
    pieces: List[List[Pt]] = [[]]
    for idx, sg in enumerate(strand.segments):
        if idx in strand.jumps:
            pieces[-1].append(strand.segments[idx - 1].p3)
            pieces.append([])
        for i in range(per_seg):
            pieces[-1].append(bez_point(sg, i / per_seg))
    pieces[-1].append(strand.segments[-1].p3)
    return pieces


def count_intersections(geom: Geometry, per_seg: int = 24) -> int:
    """Number of crossings between distinct strand paths.

    All strands are strictly y-monotone and share the same y(s) in every band,
    so sample ``i`` of two strands lies at the same height.  Two strands cross
    once for every sign change of ``x_a - x_b`` along the samples (exact zeros
    at a crossing vertex are skipped; mere touching would not be counted).
    """
    polys = [polyline(s, per_seg) for s in geom.strands]
    jump = [{idx * per_seg for idx in s.jumps} for s in geom.strands]
    total = 0
    for a in range(len(polys)):
        for b in range(a + 1, len(polys)):
            last = 0
            for i, (p, q) in enumerate(zip(polys[a], polys[b])):
                if i in jump[a] or i in jump[b]:        # a seam jump is not a crossing
                    last = 0
                d = p[0] - q[0]
                if abs(d) < 1e-9:
                    continue
                sign = 1 if d > 0 else -1
                if last and sign != last:
                    total += 1
                last = sign
    return total


def max_join_error(geom: Geometry) -> Tuple[float, float]:
    """(max positional gap, max tangent-direction error) over all joins of
    the complete (uncut) strand paths."""
    pos = ang = 0.0
    for s in geom.strands:
        for idx, (a, b) in enumerate(zip(s.segments, s.segments[1:]), 1):
            if idx in s.jumps:
                continue
            pos = max(pos, math.dist(a.p3, b.p0))
            ta = (a.p3[0] - a.c2[0], a.p3[1] - a.c2[1])
            tb = (b.c1[0] - b.p0[0], b.c1[1] - b.p0[1])
            na, nb = math.hypot(*ta), math.hypot(*tb)
            if na > 1e-12 and nb > 1e-12:
                cross = (ta[0] * tb[1] - ta[1] * tb[0]) / (na * nb)
                ang = max(ang, abs(cross))
    return pos, ang
