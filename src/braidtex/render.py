"""Rendering backends.  All consume the same Geometry; none adds semantics."""
from __future__ import annotations

from typing import List, Optional, Tuple
from xml.sax.saxutils import escape

from .config import GAP
from .discs import Disc, root_radius
from .geometry import Bez, Geometry, bez_point, build_geometry
from .model import Axis, Braid

RENDER_VERSION = "15"
LABEL_H = 0.5        # cm reserved for an endpoint label row (bbox estimate only)


def _f(x: float) -> str:
    s = f"{x:.3f}"
    return "0.000" if s == "-0.000" else s


def _p(p: Tuple[float, float]) -> str:
    return f"({_f(p[0])},{_f(p[1])})"


def _label(raw: Optional[str]) -> Optional[str]:
    return None if raw is None else f"${raw}$"


def _vbounds(braid: Braid, g: Geometry) -> Tuple[float, float]:
    top = g.height + (LABEL_H if braid.style.show_in and any(braid.display_in()) else 0)
    bot = -(LABEL_H if braid.style.show_out and any(braid.display_out()) else 0)
    top += root_radius(g.discs_in)
    bot -= root_radius(g.discs_out)
    if braid.axis or g.discs_in or g.discs_out:
        top, bot = max(top, g.height + 0.12), min(bot, -0.12)
    return bot, top


def _path(run: List[Bez]) -> str:
    s = _p(run[0].p0)
    for b in run:
        s += f" .. controls {_p(b.c1)} and {_p(b.c2)} .. {_p(b.p3)}"
    return s


def _disc_path(d: Disc, y: float) -> str:
    r = _f(d.rho)
    return (f"{_p((d.left, y - d.rho))} -- {_p((d.right, y - d.rho))} "
            f"arc[start angle=-90,end angle=90,radius={r}cm] -- {_p((d.left, y + d.rho))} "
            f"arc[start angle=90,end angle=270,radius={r}cm] -- cycle")


def braid_content(braid: Braid) -> Tuple[List[str], Geometry, float, float]:
    """TikZ drawing commands (no picture environment) and bounds."""
    st, g = braid.style, build_geometry(braid)
    ymin, ymax = _vbounds(braid, g)
    out: List[str] = []
    lw = _f(st.lw * 0.7)
    axis = braid.axis
    if axis is None and (g.discs_in or g.discs_out):
        axis = Axis("h")                      # discs live on the axis
    gin = {i for i, l in enumerate(braid.source.labels()) if l == GAP}     # gap positions (not endpoints)
    gout = {i for i, l in enumerate(braid.target.labels()) if l == GAP}

    def axes() -> None:
        if axis is None:
            return
        right = g.width + 0.3
        for y in (g.height, 0.0):
            out.append(f"\\draw[->,line width={lw}pt] {_p((0.0, y))} -- {_p((right, y))};%")
        if axis.kind == "frame":
            out.append(f"\\draw[->,line width={lw}pt] {_p((0.0, g.height))} -- {_p((0.0, 0.0))};%")
            out.append(f"\\draw[dotted,line width={lw}pt] {_p((g.width, g.height))} -- "
                       f"{_p((g.width, 0.0))};%")
        if axis.ticks:
            xs_top = [x for i, x in enumerate(g.in_x) if i not in gin] + ([0.0] if axis.kind == "frame" else [])
            xs_bot = [x for i, x in enumerate(g.out_x) if i not in gout] + ([0.0] if axis.kind == "frame" else [])
            for x in xs_top:
                out.append(f"\\draw[line width={lw}pt] {_p((x, g.height - 0.08))} -- "
                           f"{_p((x, g.height + 0.08))};%")
            for x in xs_bot:
                out.append(f"\\draw[line width={lw}pt] {_p((x, -0.08))} -- {_p((x, 0.08))};%")

    if axis and not axis.front:
        axes()

    # composition regions: behind everything but the axes
    for rg in g.regions:
        if st.compose == "shadow":
            path = _p(rg.left[0].p0)
            for b in rg.left:
                path += f" .. controls {_p(b.c1)} and {_p(b.c2)} .. {_p(b.p3)}"
            path += f" -- {_p(rg.right[-1].p3)}"
            for b in reversed(rg.right):
                path += f" .. controls {_p(b.c2)} and {_p(b.c1)} .. {_p(b.p0)}"
            out.append(f"\\path[fill={st.shadowcolor}] {path} -- cycle;%")
        elif st.compose == "separator":
            for side in (rg.left, rg.right):
                out.append(f"\\draw[{st.sepstyle},color={st.sepcolor},line width={lw}pt] "
                           f"{_path(side)};%")

    # little discs: one stadium per tree node, nested exactly like the parentheses
    for discs, y in ((g.discs_in, g.height), (g.discs_out, 0.0)):
        for d in discs:                       # outermost first
            if d.gap:
                continue                  # a gap ("...") is a placeholder, not a disc
            out.append(f"\\draw[color=black!55,line width={lw}pt] {_disc_path(d, y)};%")
        for d in discs:
            if d.is_leaf and not d.gap:
                out.append(f"\\fill[color=black!55] {_p((d.left, y))} circle (1.2pt);%")

    for s in g.strands:
        if s.hidden:
            continue
        for run in s.runs:
            out.append(f"\\draw[color={s.color}] {_path(run)};%")
        for run in s.dotted_runs:                          # strand inside a gap region
            out.append(f"\\draw[color={s.color},dotted,line cap=round] {_path(run)};%")
    for gp in g.gaps:                                      # the dots of "..." (rows aligned)
        if gp.dots:
            pts = " ".join(f"{_p(pt)} circle (1.1pt)" for pt in gp.dots)
            out.append(f"\\fill[color={st.gapcolor}] {pts};%")
    if axis and axis.front:
        axes()

    font = f"\\{st.fontsize}"
    if st.dots:
        for i, x in enumerate(g.in_x):
            if i not in gin:
                out.append(f"\\fill {_p((x, g.height))} circle (1.3pt);%")
        for i, x in enumerate(g.out_x):
            if i not in gout:
                out.append(f"\\fill {_p((x, 0.0))} circle (1.3pt);%")
    for pt in braid.points:
        x = (g.in_x if pt.side == "in" else g.out_x)[pt.index - 1]
        y = g.height if pt.side == "in" else 0.0
        out.append(f"\\fill {_p((x, y))} circle (1.8pt);%")
        if pt.label:
            anchor, dy = ("north west", -0.06) if pt.side == "in" else ("south west", 0.06)
            out.append(f"\\node[anchor={anchor},inner sep=1.5pt,font={font}] at "
                       f"{_p((x + 0.06, y + dy))} {{${pt.label}$}};%")
    up, down = root_radius(g.discs_in), root_radius(g.discs_out)
    if st.show_in:
        for x, lab in zip(g.in_x, braid.display_in()):
            if lab is not None:
                out.append(f"\\node[anchor=south,inner sep=1.5pt,font={font}] at "
                           f"{_p((x, g.height + 0.02 + up))} {{{_label(lab)}}};%")
    if st.show_out:
        for x, lab in zip(g.out_x, braid.display_out()):
            if lab is not None:
                out.append(f"\\node[anchor=north,inner sep=1.5pt,font={font}] at "
                           f"{_p((x, -0.02 - down))} {{{_label(lab)}}};%")
    if st.sigma:
        for c in g.crossings:
            e = "^{-1}" if c.sign < 0 else ""
            out.append(f"\\node[anchor=east,inner sep=1pt,font=\\scriptsize] at "
                       f"{_p((-0.12, c.center[1]))} "
                       f"{{$\\sigma_{{{abs(c.generator)}}}{e}$}};%")
    for k, text in sorted(braid.notes.items()):
        s = g.strands[k - 1]
        mid = s.segments[len(s.segments) // 2]
        x, y = bez_point_mid(mid)
        out.append(f"\\node[anchor=west,inner sep=2pt,font={font},text={s.color}] at "
                   f"{_p((x + 0.05, y))} {{${text}$}};%")
    return out, g, ymin, ymax


def picture(lines: List[str], base: float, key: str, lw: float, scale: float = 1.0) -> str:
    extra = f",scale={scale:g},transform shape" if scale != 1.0 else ""
    head = (f"% braidtex {RENDER_VERSION} {key}".rstrip() + "%\n"
            f"\\begin{{tikzpicture}}[baseline={{{_f(base * scale)}cm-0.25em}},x=1cm,y=1cm,"
            f"line cap=butt,line join=round,line width={_f(lw)}pt{extra}]%\n")
    return head + "\n".join(lines) + "\n\\end{tikzpicture}%\n"


def render_tikz(braid: Braid, key: str = "") -> str:
    """Self-contained ``tikzpicture`` suitable for ``\\input`` inside math."""
    lines, g, ymin, ymax = braid_content(braid)
    return picture(lines, (ymin + ymax) / 2, key, braid.style.lw)


def bez_point_mid(b: Bez) -> Tuple[float, float]:
    return bez_point(b, 0.5)


def render_standalone(braid: Braid, key: str = "") -> str:
    body = render_tikz(braid, key)
    return ("\\documentclass[tikz,border=4pt]{standalone}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\begin{document}\n" + body + "\\end{document}\n")


def render_svg(braid: Braid, key: str = "") -> str:
    """SVG (labels are plain text, LaTeX is *not* typeset)."""
    st, g = braid.style, build_geometry(braid)
    ymin, ymax = _vbounds(braid, g)
    S = 40.0                                 # px per cm
    xmin, xmax = -0.3, g.width + 0.6

    def X(x): return (x - xmin) * S
    def Y(y): return (ymax - y) * S

    def pp(p): return f"{X(p[0]):.2f},{Y(p[1]):.2f}"

    w, h = (xmax - xmin) * S, (ymax - ymin) * S
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}" height="{h:.1f}" '
           f'viewBox="0 0 {w:.1f} {h:.1f}"><!-- braidtex {RENDER_VERSION} {key} -->']
    lw = st.lw * 2.54 / 72.27 * S
    if braid.axis:
        for y in (g.height, 0.0):
            out.append(f'<path d="M{pp((0, y))} L{pp((g.width + 0.3, y))}" stroke="black" '
                       f'fill="none" stroke-width="{lw * 0.7:.2f}"/>')
        if braid.axis.kind == "frame":
            out.append(f'<path d="M{pp((0, g.height))} L{pp((0, 0))}" stroke="black" '
                       f'fill="none" stroke-width="{lw * 0.7:.2f}"/>')
            out.append(f'<path d="M{pp((g.width, g.height))} L{pp((g.width, 0))}" stroke="black" '
                       f'fill="none" stroke-dasharray="2 3" stroke-width="{lw * 0.7:.2f}"/>')
    for s in g.strands:
        if s.hidden:
            continue
        col = _svg_color(s.color)
        for run in s.runs:
            d = f"M{pp(run[0].p0)}" + "".join(f" C{pp(b.c1)} {pp(b.c2)} {pp(b.p3)}" for b in run)
            out.append(f'<path d="{d}" stroke="{col}" fill="none" stroke-width="{lw:.2f}" '
                       f'stroke-linejoin="round"/>')
        for run in s.dotted_runs:
            d = f"M{pp(run[0].p0)}" + "".join(f" C{pp(b.c1)} {pp(b.c2)} {pp(b.p3)}" for b in run)
            out.append(f'<path d="{d}" stroke="{col}" fill="none" stroke-width="{lw:.2f}" '
                       f'stroke-dasharray="0.1 4" stroke-linecap="round"/>')
    for gp in g.gaps:
        for (x, y) in gp.dots:
            out.append(f'<circle cx="{X(x):.2f}" cy="{Y(y):.2f}" r="1.6" fill="{_svg_color(st.gapcolor)}"/>')
    fs = 13
    if st.show_in:
        for x, lab in zip(g.in_x, braid.display_in()):
            if lab:
                out.append(f'<text x="{X(x):.2f}" y="{Y(g.height) - 5:.2f}" font-size="{fs}" '
                           f'text-anchor="middle">{escape(lab)}</text>')
    if st.show_out:
        for x, lab in zip(g.out_x, braid.display_out()):
            if lab:
                out.append(f'<text x="{X(x):.2f}" y="{Y(0) + fs + 2:.2f}" font-size="{fs}" '
                           f'text-anchor="middle">{escape(lab)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def _svg_color(c: str) -> str:
    """Best effort: base colour name of an xcolor mix (``teal!75!black``)."""
    table = {"teal": "#008080", "orange": "#ff8000", "blue": "#0000ff", "red": "#ff0000",
             "green": "#00bf00", "purple": "#bf0040", "violet": "#800080", "black": "#000000",
             "gray": "#808080", "brown": "#bf8040", "cyan": "#00ffff", "magenta": "#ff00ff"}
    parts = c.split("!")
    base = table.get(parts[0], "#000000")
    if len(parts) >= 2:
        try:
            p = float(parts[1]) / 100
        except ValueError:
            return base
        other = table.get(parts[2], "#ffffff") if len(parts) > 2 else "#ffffff"
        r = [int(base[i:i + 2], 16) * p + int(other[i:i + 2], 16) * (1 - p) for i in (1, 3, 5)]
        return "#%02x%02x%02x" % tuple(int(v) for v in r)
    return base
