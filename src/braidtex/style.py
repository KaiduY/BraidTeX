"""Renderer-independent styling.  Never influences braid semantics."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields, asdict
from typing import Dict, List, Optional, Tuple

from .errors import BraidValidationError

COLOR_RE = re.compile(r"^[A-Za-z0-9!._-]+$")
FONT_SIZES = ("tiny", "scriptsize", "footnotesize", "small", "normalsize", "large")
PALETTE = ("teal!75!black", "orange!90!black", "blue!65!black", "red!70!black",
           "green!50!black", "purple!80!black")
_UNITS = {"cm": 1.0, "mm": 0.1, "pt": 2.54 / 72.27, "in": 2.54, "bp": 2.54 / 72.0}


def check_color(c: str) -> str:
    if not COLOR_RE.match(c):
        raise BraidValidationError(
            f"unsupported color expression {c!r}; use names/mixes such as teal!75!black")
    return c


def parse_length(v: str, key: str = "length") -> float:
    """Length in cm.  Plain numbers are centimetres."""
    m = re.fullmatch(r"\s*(-?\d*\.?\d+)\s*(cm|mm|pt|in|bp)?\s*", str(v))
    if not m:
        raise BraidValidationError(f"{key}: cannot parse length {v!r} (use e.g. 2.5cm, 8mm, 1pt)")
    return float(m.group(1)) * _UNITS[m.group(2) or "cm"]


def parse_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("", "true", "yes", "1", "on"):
        return True
    if s in ("false", "no", "0", "off"):
        return False
    raise BraidValidationError(f"expected a boolean, got {v!r}")


def split_options(text: str) -> Dict[str, str]:
    """Parse ``key=value, flag, key={a, b}`` into a dict (brace-aware)."""
    items: List[str] = []
    depth, cur = 0, []
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    items.append("".join(cur))
    out: Dict[str, str] = {}
    for it in items:
        it = it.strip()
        if not it:
            continue
        if "=" in it:
            k, v = it.split("=", 1)
            v = v.strip()
            if v.startswith("{") and v.endswith("}"):
                v = v[1:-1].strip()
            out[k.strip()] = v
        else:
            out[it] = "true"
    return out


INLINE_PRESET = dict(band=0.42, pad=0.16, margin=0.24, lw=0.7, gap=0.045, regionpad=0.1,
                     fontsize="scriptsize", spacing=0.5, minspan=0.55)


@dataclass(frozen=True)
class Style:
    """Visual settings.  Lengths in cm, line width in pt."""

    width: Optional[float] = None        # total diagram width (default: from arity)
    height: Optional[float] = None       # total height (default: from word length)
    band: float = 0.9                    # height per crossing layer
    pad: float = 0.35                    # straight vertical stub at top/bottom
    margin: float = 0.5                  # horizontal margin to outermost endpoints
    spacing: float = 0.9                 # default distance between neighbouring endpoints
    minspan: float = 1.2                 # default minimum distance between outermost endpoints
    lw: float = 0.9                      # strand line width (pt)
    gap: float = 0.07                    # clearance around over-strands (cm)
    labels: str = "both"                 # both | in | out | none
    dots: bool = False                   # endpoint markers
    sigma: bool = False                  # crossing labels \sigma_i^{\pm1}
    rho: float = 0.5                     # nesting ratio of the hierarchical layout
    wmin: float = 0.15                   # smallest relative gap
    palette: bool = False                # default per-strand colour scheme
    fontsize: str = "small"
    color: str = "black"                 # main strand colour
    inpos: Optional[Tuple[float, ...]] = None    # custom normalized endpoint positions
    outpos: Optional[Tuple[float, ...]] = None
    # --- composition (inner braid replacing a strand) ----------------------
    compose: str = "shadow"              # shadow | separator | none
    at: str = "top"                      # where the inner braid sits: top | bottom | <k outer layers>
    extent: str = "auto"                 # auto | full | inner  (how far the marking runs)
    shadowcolor: str = "gray!22"
    regionpad: float = 0.17              # distance of shadow edge / separators from outer strands
    sepstyle: str = "dashed"
    sepcolor: str = "gray!70!black"
    # --- little 2-discs ----------------------------------------------------
    discs: str = "none"                  # none | in | out | both

    def __post_init__(self):
        if self.labels not in ("both", "in", "out", "none"):
            raise BraidValidationError("labels must be one of both|in|out|none")
        if self.fontsize not in FONT_SIZES:
            raise BraidValidationError(f"fontsize must be one of {', '.join(FONT_SIZES)}")
        check_color(self.color)
        check_color(self.shadowcolor)
        check_color(self.sepcolor)
        if self.compose not in ("shadow", "separator", "none"):
            raise BraidValidationError("compose must be shadow|separator|none")
        if not (self.at in ("top", "bottom") or self.at.isdigit()):
            raise BraidValidationError("at must be top, bottom or a layer number")
        if self.extent not in ("auto", "full", "inner"):
            raise BraidValidationError("extent must be auto|full|inner")
        if self.discs not in ("none", "in", "out", "both"):
            raise BraidValidationError("discs must be none|in|out|both")
        if not re.fullmatch(r"[A-Za-z0-9 =.,]+", self.sepstyle):
            raise BraidValidationError("sepstyle: only letters, digits, spaces and '=.,' allowed")
        for k in ("band", "lw"):
            if getattr(self, k) <= 0:
                raise BraidValidationError(f"{k} must be positive")
        for k in ("pad", "margin", "gap", "wmin", "regionpad", "spacing", "minspan"):
            if getattr(self, k) < 0:
                raise BraidValidationError(f"{k} must be non-negative")
        if not (0 < self.rho <= 1):
            raise BraidValidationError("rho must be in (0, 1]")

    @property
    def discs_in(self) -> bool:
        return self.discs in ("in", "both")

    @property
    def discs_out(self) -> bool:
        return self.discs in ("out", "both")

    @property
    def show_in(self) -> bool:
        return self.labels in ("both", "in")

    @property
    def show_out(self) -> bool:
        return self.labels in ("both", "out")

    @staticmethod
    def from_options(opts: Dict[str, str]) -> "Style":
        kw: Dict[str, object] = {}
        opts = dict(opts)
        size = opts.pop("size", None)
        inline = opts.pop("inline", None)
        if size == "inline" or (inline is not None and parse_bool(inline)):
            kw.update(INLINE_PRESET)
        for k, v in opts.items():
            if k in ("width", "height", "band", "pad", "margin", "gap", "regionpad", "spacing",
                     "minspan"):
                kw[k] = parse_length(v, k)
            elif k == "lw":
                kw[k] = parse_length(v if re.search(r"[a-z]", str(v)) else f"{v}pt", k) / _UNITS["pt"]
            elif k in ("rho", "wmin"):
                try:
                    kw[k] = float(v)
                except ValueError:
                    raise BraidValidationError(f"{k}: expected a number, got {v!r}")
            elif k in ("dots", "sigma", "palette"):
                kw[k] = parse_bool(v)
            elif k in ("labels", "fontsize", "color", "at", "extent", "shadowcolor",
                       "sepcolor", "sepstyle"):
                kw[k] = v
            elif k == "compose":
                kw[k] = {"sep": "separator", "false": "none", "off": "none"}.get(v, v)
            elif k == "discs":
                kw[k] = ("both" if parse_bool(v) else "none") if v in (
                    "", "true", "false", "yes", "no", "on", "off", "1", "0") else v
            elif k in ("inpos", "outpos"):
                try:
                    kw[k] = tuple(float(x) for x in re.split(r"[\s,;]+", v.strip()) if x)
                except ValueError:
                    raise BraidValidationError(f"{k}: expected numbers in [0,1], got {v!r}")
            else:
                known = ", ".join(f.name for f in fields(Style))
                raise BraidValidationError(f"unknown option {k!r}; known options: {known}")
        return Style(**kw)  # type: ignore[arg-type]

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("lw", "width", "height", "band", "pad", "margin", "gap", "rho", "wmin",
                  "regionpad", "spacing", "minspan"):
            if d[k] is not None:
                d[k] = round(float(d[k]), 6)
        for k in ("inpos", "outpos"):
            if d[k] is not None:
                d[k] = [round(x, 6) for x in d[k]]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Style":
        d = dict(d)
        for k in ("inpos", "outpos"):
            if d.get(k) is not None:
                d[k] = tuple(d[k])
        return Style(**d)
