r"""High-level macros for standard braid-theoretic diagrams: ``\braidid{name}{options}``.

==============  =================================================================
name            diagram
==============  =================================================================
``ybe``         Yang-Baxter / braid relation  s1 s2 s1 = s2 s1 s2
``far``         far commutativity            s1 s3 = s3 s1  (4 strands)
``inverse``     s s^-1 = id = s^-1 s
``crossings``   the two basic crossings s and s^-1
``assoc``       the associator (a b) c -> a (b c) and its inverse, drawn as
                identity braids between differently parenthesized configurations,
                with little discs
``pentagon``    Mac Lane's pentagon of associators (commutative diagram)
``hexagon``     the braided-monoidal hexagon (associators and braidings)
==============  =================================================================

Options (``key=value``): braid scenes take ``labels`` (space separated), ``colors``
(one per strand), ``sign`` (``+`` or ``-``), ``rel`` (TeX shown between pictures),
``gap`` (cm), plus *any* style option (``width``, ``lw``, ``discs`` ...).  Graph scenes take
``objects``, ``op``, ``assoc``, ``braiding``, ``radius``, ``aspect``, ``nodestyle``,
``edgestyle``, ``color``, ``font``, ``scale``.  Nothing needs coordinates.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Dict, List, Optional, Tuple

from .config import Node, parse_config
from .errors import BraidTeXError, BraidValidationError
from .model import Braid
from .render import RENDER_VERSION, braid_content, picture
from .style import Style, check_color, parse_length

TIKZ_OPT = re.compile(r"^[A-Za-z0-9 =.,!_:/<>\-]*$")
BRAID_SCENES = {"ybe", "far", "inverse", "crossings", "assoc"}
GRAPH_SCENES = {"pentagon", "hexagon"}
NAMES = sorted(BRAID_SCENES | GRAPH_SCENES)


class Scene:
    def __init__(self, name: str, spec: dict, builder):
        self.name, self.spec, self._builder = name, spec, builder

    def key(self) -> str:
        canon = json.dumps({"render": RENDER_VERSION, "identity": self.name, "spec": self.spec},
                           sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canon.encode()).hexdigest()

    def render(self, key: str = "") -> str:
        return self._builder(key)


def _tikzopt(v: str, what: str) -> str:
    if not TIKZ_OPT.match(v):
        raise BraidValidationError(f"{what}: unsupported characters in TikZ option string {v!r}")
    return v


def _colors(spec: Optional[str], n: int) -> Dict[int, str]:
    if not spec:
        return {}
    cols = spec.split()
    if len(cols) > n:
        raise BraidValidationError(f"colors: {len(cols)} given for {n} strands")
    return {i + 1: check_color(c) for i, c in enumerate(cols)}


def _names(spec: Optional[str], default: str, n: int, what: str = "labels") -> List[str]:
    leaves = [l.label for l in parse_config(spec if spec is not None else default).leaves()]
    if len(leaves) != n or any(l is None for l in leaves):
        raise BraidValidationError(f"{what}: exactly {n} labels needed, got "
                                   f"{len(leaves)}: {spec!r}")
    return leaves


def make_scene(name: str, opts: Dict[str, str], defaults: Dict[str, str]) -> Scene:
    """Build and *validate* a scene (all option errors are raised here, not at render time)."""
    scene = _make_scene(name, opts, defaults)
    scene.render("")
    return scene


def _make_scene(name: str, opts: Dict[str, str], defaults: Dict[str, str]) -> Scene:
    if name not in NAMES:
        raise BraidValidationError(f"unknown identity {name!r}; available: {', '.join(NAMES)}")
    opts = dict(opts)
    if name in GRAPH_SCENES:
        return _graph_scene(name, opts)
    own_keys = ("labels", "colors", "sign", "rel", "gap")
    own = {k: opts.pop(k) for k in own_keys if k in opts}
    style_opts = dict(defaults)
    style_opts.update(opts)
    if name == "assoc":
        style_opts.setdefault("discs", "both")
        style_opts.setdefault("labels", "both")
    style = Style.from_options(style_opts)
    sign = {"+": 1, "-": -1}.get(own.get("sign", "+"))
    if sign is None:
        raise BraidValidationError("sign must be + or -")
    gap = parse_length(own.get("gap", "0.55cm"), "gap")
    rel = own.get("rel", "=")
    spec = {"own": own, "style": style.to_dict()}

    def build(key: str) -> str:
        n_by = {"ybe": 3, "far": 4, "inverse": 2, "crossings": 2, "assoc": 3}[name]
        labs = _names(own.get("labels"), "a b c d"[:2 * n_by - 1], n_by)
        cols = _colors(own.get("colors"), n_by)
        src = " ".join(labs)

        def B(word, s=src, t=None):
            return Braid(word, s, t, colors=cols, style=style)

        s = sign
        if name == "ybe":
            pieces = [B([s, 2 * s, s]), f"${rel}$", B([2 * s, s, 2 * s])]
        elif name == "far":
            pieces = [B([s, 3 * s]), f"${rel}$", B([3 * s, s])]
        elif name == "inverse":
            pieces = [B([s, -s]), f"${rel}$", B([]), f"${rel}$", B([-s, s])]
        elif name == "crossings":
            e = "" if s > 0 else "^{-1}"
            f = "^{-1}" if s > 0 else ""
            pieces = [(B([s]), f"$\\sigma_1{e}$"), (B([-s]), f"$\\sigma_1{f}$")]
        else:                                                  # assoc
            a, b, c = labs
            left, right = f"({a} {b}) {c}", f"{a} ({b} {c})"
            pieces = [B([], left, right), "$\\quad$", B([], right, left)]
        return _compose(pieces, gap, key, style.lw)

    return Scene(name, spec, build)


def _compose(pieces, gap: float, key: str, lw: float) -> str:
    lines: List[str] = []
    x = 0.0
    for k, p in enumerate(pieces):
        caption = None
        if isinstance(p, tuple):                       # (braid, caption below it)
            p, caption = p
        if isinstance(p, str):
            w = 0.45 + 0.1 * len(re.sub(r"[$\\]", "", p))
            lines.append(f"\\node at ({x + w / 2:.3f},0) {{{p}}};%")
            x += w + (gap if p.strip("$ ") in ("=", "\\quad", ",") else gap * 0.5)
            continue
        content, g, ymin, ymax = braid_content(p)
        right = g.width + (0.3 if (p.axis or g.discs_in or g.discs_out) else 0.0)
        shift = -(ymin + ymax) / 2
        lines.append(f"\\begin{{scope}}[shift={{({x:.3f},{shift:.3f})}}]%")
        lines.extend(content)
        lines.append("\\end{scope}%")
        if caption:
            lines.append(f"\\node[anchor=north,text height=1.6ex,text depth=0.6ex] at ({x + g.width / 2:.3f},{ymin + shift - 0.1:.3f}) "
                         f"{{{caption}}};%")
        x += right + gap
    return picture(lines, 0.0, key, lw)


# ----------------------------------------------------------------- graph scenes
def tree_math(node: Node, op: str, root: bool = True) -> str:
    if node.is_leaf:
        return node.label if node.label is not None else "\\bullet"
    sep = f" {op} " if op else "\\,"
    inner = sep.join(tree_math(c, op, False) for c in node.children)
    return inner if root else f"({inner})"


def _graph_scene(name: str, opts: Dict[str, str]) -> Scene:
    known = ("objects", "op", "assoc", "braiding", "radius", "aspect", "nodestyle",
             "edgestyle", "color", "font", "lw", "scale")
    bad = set(opts) - set(known)
    if bad:
        raise BraidValidationError(f"unknown option(s) {sorted(bad)} for {name}; "
                                   f"known: {', '.join(known)}")
    n = 4 if name == "pentagon" else 3
    default_objs = "a b c d" if name == "pentagon" else "A B C"
    objs = _names(opts.get("objects"), default_objs, n, "objects")
    op = opts.get("op", "\\otimes")
    al = opts.get("assoc", "\\alpha")
    br = opts.get("braiding", "c")
    radius = parse_length(opts.get("radius", "2.1cm"), "radius")
    aspect = float(opts.get("aspect", "1.45"))
    autosize = "radius" not in opts and "aspect" not in opts
    nodestyle = _tikzopt(opts.get("nodestyle", "inner sep=3pt"), "nodestyle")
    edgestyle = _tikzopt(opts.get("edgestyle", "->"), "edgestyle")
    color = check_color(opts.get("color", "black"))
    font = opts.get("font", "small")
    if font not in ("tiny", "scriptsize", "footnotesize", "small", "normalsize", "large"):
        raise BraidValidationError("font must be a LaTeX size name such as small")
    lw = float(opts.get("lw", "0.8").replace("pt", ""))
    scale_all = float(opts.get("scale", "1"))
    if not (0.1 <= scale_all <= 5):
        raise BraidValidationError("scale must be between 0.1 and 5")
    spec = dict(opts=opts)

    def P(*xs: str) -> str:
        return (f" {op} " if op else "").join(xs)

    ot = "\\otimes "
    idm = lambda x: f"\\mathrm{{id}}_{{{x}}}"           # noqa: E731

    if name == "pentagon":
        a, b, c, d = objs
        trees = [f"(({a} {b}) {c}) {d}", f"({a} ({b} {c})) {d}", f"{a} (({b} {c}) {d})",
                 f"{a} ({b} ({c} {d}))", f"({a} {b}) ({c} {d})"]
        angles = [90 - 72 * i for i in range(5)]
        edges = [(0, 1, f"{al}_{{{a},{b},{c}}}{ot}{idm(d)}", False),
                 (1, 2, f"{al}_{{{a},{P(b, c)},{d}}}", False),
                 (2, 3, f"{idm(a)}{ot}{al}_{{{b},{c},{d}}}", False),
                 (0, 4, f"{al}_{{{P(a, b)},{c},{d}}}", True),
                 (4, 3, f"{al}_{{{a},{b},{P(c, d)}}}", True)]
    else:
        A, B_, C = objs
        trees = [f"({A} {B_}) {C}", f"{A} ({B_} {C})", f"({B_} {C}) {A}", f"{B_} ({C} {A})",
                 f"({B_} {A}) {C}", f"{B_} ({A} {C})"]
        angles = [180, 120, 60, 0, -120, -60]
        edges = [(0, 1, f"{al}_{{{A},{B_},{C}}}", False),
                 (1, 2, f"{br}_{{{A},{P(B_, C)}}}", False),
                 (2, 3, f"{al}_{{{B_},{C},{A}}}", False),
                 (0, 4, f"{br}_{{{A},{B_}}}{ot}{idm(C)}", True),
                 (4, 5, f"{al}_{{{B_},{A},{C}}}", True),
                 (5, 3, f"{idm(B_)}{ot}{br}_{{{A},{C}}}", True)]

    def build(key: str) -> str:
        lines: List[str] = []
        texts = [tree_math(parse_config(t), op) for t in trees]
        # estimated node boxes (cm); enlarge the polygon until neighbours clear each other
        def vis(t: str) -> int:             # visible glyph count (a command ~ two glyphs)
            return len(re.sub(r"[{}_^$ ]", "", re.sub(r"\\[A-Za-z]+", "XX", t)))

        widths = [0.19 * vis(t) + 0.4 for t in texts]
        pts = [(radius * aspect * math.cos(math.radians(a)),
                radius * math.sin(math.radians(a))) for a in angles]
        scale = 1.0
        if autosize:
            for i, j, lab, _ in edges:
                dx, dy = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
                dist = math.hypot(dx, dy)
                ux, uy = abs(dx) / dist, abs(dy) / dist

                def half(w: float) -> float:
                    return min(w / 2 / ux if ux > 1e-6 else 1e9, 0.3 / uy if uy > 1e-6 else 1e9)

                lab_w = (0.16 * vis(lab) + 0.3) if ux > 0.6 else 0.0   # label beside a flat edge
                need = half(widths[i]) + half(widths[j]) + max(1.0, 0.9 * lab_w)
                scale = max(scale, need / dist)
        for i, ((x, y), txt) in enumerate(zip(pts, texts)):
            lines.append(f"\\node[{nodestyle},font=\\{font}] (v{i}) at "
                         f"({x * scale:.3f},{y * scale:.3f}) {{${txt}$}};%")
        for i, j, lab, swap in edges:
            lines.append(f"\\draw[{edgestyle},color={color},shorten >=1pt,shorten <=1pt] "
                         f"(v{i}) -- (v{j}) node[midway,auto{',swap' if swap else ''},"
                         f"inner sep=3pt,font=\\{font}] {{${lab}$}};%")
        return picture(lines, 0.0, key, lw, scale_all)

    return Scene(name, spec, build)
