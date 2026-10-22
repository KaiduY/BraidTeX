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
from .model import Braid

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


def _hermite_bez(x0: float, y0: float, x1: float, y1: float, m0: float, m1: float) -> Bez:
    """Cubic curve from (x0,y0) to (x1,y1) (y decreasing) with slopes ``m = dx/d(depth)``
    at both ends.  Equal slopes on both sides of a level make the join G1."""
    dy = (y1 - y0) * NATURAL_EASE
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
    runs: List[List[Bez]] = field(default_factory=list)   # drawable pieces after gaps


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
    layers = braid.layers
    B = max(len(layers), 1)
    W = st.width if st.width is not None else default_width(n, st.margin, st.spacing, st.minspan)
    if W - 2 * st.margin <= 0:
        raise ValueError("diagram too small: width <= 2*margin")

    def xs(tree, custom):
        u = normalized_positions(tree, st.rho, st.wmin, custom)
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
                    for t in range(r.first, (r.last or r.first) + 1)}
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
    for layer in layers:
        s = list(levels[-1])
        for c in layer:
            s[c.slot], s[c.slot + 1] = s[c.slot + 1], s[c.slot]
        levels.append(s)
    if not layers:
        levels.append(list(levels[0]))

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
    cuts: Dict[Tuple[int, int], List[Tuple[float, float]]] = {}
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
        if natural and not _layer_ok(curves, levels[t - 1], levels[t], W):
            if strict:
                return None, False
            ok = False
        layer = layers[t - 1] if layers else ()
        for cr in layer:
            ov, un = curves[cr.over], curves[cr.under]
            # crossing parameter: x_over(s) - x_under(s) changes sign exactly once in the layer
            neg0 = bez_point(ov, 0.0)[0] < bez_point(un, 0.0)[0]
            lo, hi = 0.0, 1.0
            for _ in range(60):
                mid = (lo + hi) / 2
                if (bez_point(ov, mid)[0] < bez_point(un, mid)[0]) == neg0:
                    lo = mid
                else:
                    hi = mid
            s_star = (lo + hi) / 2
            poly = [bez_point(ov, i / 120) for i in range(121)]

            def d(s: float, un=un, poly=poly) -> float:
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
                    return None, False
                warnings.warn(f"layer {t}: the clearance gap of a crossing reaches the end of "
                              f"its layer; increase band/width or decrease gap", stacklevel=2)
            cuts.setdefault((cr.under, t), []).append((s_lo, s_hi))
            xings.append(CrossingGeom(t, bez_point(ov, s_star), cr.over, cr.under, cr.sign,
                                      cr.generator, (s_lo, s_hi), c1 or c2))

    strands: List[StrandGeom] = []
    for k in range(1, n + 1):
        px = out_x[braid.permutation[k - 1] - 1]
        segs[k].append(_line((px, ys[B]), (px, 0.0)))
        runs: List[List[Bez]] = []
        cur: List[Bez] = []
        for idx, seg in enumerate(segs[k]):
            ivs = sorted(cuts.get((k, idx), []))
            if not ivs:
                cur.append(seg)
                continue
            merged: List[List[float]] = []
            for lo, hi in ivs:                       # merge overlapping gaps
                if merged and lo <= merged[-1][1] + 1e-9:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])
            prev = 0.0
            for lo, hi in merged:
                if lo > prev + 1e-9:
                    cur.append(subcurve(seg, prev, lo))
                if cur:
                    runs.append(cur)
                cur = []
                prev = hi
            if prev < 1 - 1e-9:
                cur.append(subcurve(seg, prev, 1.0))
        if cur:
            runs.append(cur)
        strands.append(StrandGeom(k, braid.strand_color(k), segs[k], runs))

    regions, rok = _regions(braid, levels, x_at, ys, H, B, st, natural, tau, wrap, bh, segs)
    if natural and not rok:
        if strict:
            return None, False
        ok = False
    return Geometry(W, H, in_x, out_x, strands, xings, ys, B, regions, d_in, d_out,
                    pad_top, pad_bot), ok


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
             segs=None) -> Tuple[List[RegionGeom], bool]:
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
            i0 = 0 if r.first == 1 else r.first
            i1 = B + 1 if r.last == B else r.last
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
    pts: List[Pt] = []
    for sg in strand.segments:
        for i in range(per_seg + 1):
            if pts and i == 0:
                continue
            pts.append(bez_point(sg, i / per_seg))
    return pts


def count_intersections(geom: Geometry, per_seg: int = 24) -> int:
    """Number of crossings between distinct strand paths.

    All strands are strictly y-monotone and share the same y(s) in every band,
    so sample ``i`` of two strands lies at the same height.  Two strands cross
    once for every sign change of ``x_a - x_b`` along the samples (exact zeros
    at a crossing vertex are skipped; mere touching would not be counted).
    """
    polys = [polyline(s, per_seg) for s in geom.strands]
    total = 0
    for a in range(len(polys)):
        for b in range(a + 1, len(polys)):
            last = 0
            for p, q in zip(polys[a], polys[b]):
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
        for a, b in zip(s.segments, s.segments[1:]):
            pos = max(pos, math.dist(a.p3, b.p0))
            ta = (a.p3[0] - a.c2[0], a.p3[1] - a.c2[1])
            tb = (b.c1[0] - b.p0[0], b.c1[1] - b.p0[1])
            na, nb = math.hypot(*ta), math.hypot(*tb)
            if na > 1e-12 and nb > 1e-12:
                cross = (ta[0] * tb[1] - ta[1] * tb[0]) / (na * nb)
                ang = max(ang, abs(cross))
    return pos, ang
