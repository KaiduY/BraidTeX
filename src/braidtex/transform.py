r"""LaTeX source transformation: ``\braid{...}`` -> ``\braidfig{braids/bt-<key>}``.

The scanner works on a *masked* copy of the source in which comments, verbatim
environments and ``\verb`` contents are blanked (same length, same offsets), so
examples in comments/verbatim are never treated as active braids and positions
in error messages are exact.  Only ``\braid{...}`` (and the global default
setter ``\braidsetup{...}``) are recognized; everything else is copied verbatim.

Commands allowed inside ``\braid{...}``::

    \bin{cfg}  \bout{cfg}  \bn{N}  \bcr{i j k}  \bcol{ids}{color}
    \bnote{id}{tex}  \blab{in|out}{labels}  \bpt{in|out}{index}{label}
    \bax{h|frame[,front][,noticks]}  \bset{key=value,...}
    \bsub{k}{inner body}      replace strand k by an inner braid (cabling)

Top level (outside ``\\braid``): ``\\braidsetup{opts}`` and
``\\braidid{name}{opts}`` (standard identities, see :mod:`braidtex.identities`).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .cache import Cache
from .config import ConfigSyntaxError, Node, parse_config
from .errors import BraidTeXError, BraidValidationError, TransformError
from .model import Axis, Braid, Point
from .style import Style, check_color, split_options

VERBATIM_ENVS = {"verbatim", "verbatim*", "Verbatim", "lstlisting", "minted", "comment",
                 "alltt", "BVerbatim", "LVerbatim"}
ARGC = {"bin": 1, "bout": 1, "bn": 1, "bcr": 1, "bcol": 2, "bnote": 2, "blab": 2,
        "bpt": 3, "bax": 1, "bset": 1, "bsub": 2}
INNER_OK = {"bin", "bout", "bn", "bcr", "bcol"}       # allowed inside \bsub{k}{...}


class Source:
    def __init__(self, text: str, name: str = "<expr>"):
        self.text, self.name = text, name
        self._starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def loc(self, off: int) -> Tuple[int, int]:
        lo, hi = 0, len(self._starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1, off - self._starts[lo] + 1

    def err(self, msg: str, off: int) -> TransformError:
        line, col = self.loc(off)
        return TransformError(msg, self.name, line, col)


def mask(text: str) -> str:
    """Blank comments, verbatim environments and ``\\verb`` arguments."""
    out = list(text)
    n = len(text)

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    i = 0
    while i < n:
        c = text[i]
        if c == "%":
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif c == "\\":
            j = i + 1
            if j < n and text[j].isalpha():
                while j < n and text[j].isalpha():
                    j += 1
                name = text[i + 1:j]
                if name == "begin":
                    m = re.match(r"\{([A-Za-z]+\*?)\}", text[j:])
                    if m and m.group(1) in VERBATIM_ENVS:
                        env = m.group(1)
                        start = j + m.end()
                        end = text.find("\\end{" + env + "}", start)
                        end = n if end < 0 else end
                        blank(start, end)
                        i = end
                        continue
                elif name in ("verb", "lstinline") and j < n:
                    k = j + 1 if text[j] == "*" else j
                    if name == "lstinline" and k < n and text[k] == "[":
                        k = text.find("]", k) + 1 or k
                    if k < n and not text[k].isspace() and text[k] != "\n":
                        delim = "}" if text[k] == "{" else text[k]
                        close = text.find(delim, k + 1)
                        nl = text.find("\n", k)
                        if close >= 0 and (nl < 0 or close < nl):
                            blank(k + 1, close)
                            i = close + 1
                            continue
                i = j
            else:
                i = j + 1
        else:
            i += 1
    return "".join(out)


def _match(m: str, i: int, src: Source) -> int:
    """Index of the ``}`` matching ``{`` at ``i`` in masked text ``m``."""
    depth, j, n = 0, i, len(m)
    while j < n:
        c = m[j]
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
    raise src.err("unbalanced '{' (no matching '}')", i)


def _ints(text: str, base: int, src: Source, what: str) -> List[Tuple[int, int]]:
    out = []
    for m in re.finditer(r"\S+", text.replace(",", " ")):
        tok = m.group()
        if not re.fullmatch(r"[+-]?\d+", tok):
            raise src.err(f"{what}: {tok!r} is not an integer", base + m.start())
        out.append((int(tok), base + m.start()))
    return out


def parse_body(m: str, a: int, b: int, defaults: Dict[str, str], src: Source,
               at: int, inner: bool = False) -> Braid:
    """Parse the interior ``m[a:b]`` of ``\\braid{...}`` into a validated Braid."""
    subs: List[Tuple[int, Braid, int]] = []
    cfg_in: Optional[Tuple[Node, int]] = None
    cfg_out: Optional[Tuple[Node, int]] = None
    n_decl: Optional[Tuple[int, int]] = None
    gens: List[Tuple[int, int]] = []
    colors: Dict[int, str] = {}
    notes: Dict[int, str] = {}
    points: List[Point] = []
    labels: Dict[str, List[Optional[str]]] = {}
    axis: Optional[Axis] = None
    opts = dict(defaults)

    def parse_cfg(arg: str, base: int) -> Node:
        try:
            return parse_config(arg)
        except ConfigSyntaxError as e:
            raise src.err(f"invalid configuration: {e.message}", base + e.pos)

    pos = a
    while True:
        while pos < b and m[pos].isspace():
            pos += 1
        if pos >= b:
            break
        if m[pos] != "\\":
            raise src.err(f"unexpected text {m[pos:pos + 12].strip()!r} inside \\braid{{...}}; "
                          f"expected a command such as \\bcr{{1}}", pos)
        cmd_at = pos
        j = pos + 1
        while j < b and m[j].isalpha():
            j += 1
        name = m[pos + 1:j]
        if name not in ARGC or (inner and name not in INNER_OK):
            allowed = INNER_OK if inner else ARGC
            raise src.err(f"unknown command \\{name} inside "
                          f"{'\\bsub{..}' if inner else '\\braid{...}'} "
                          f"(allowed: {', '.join('\\' + k for k in sorted(allowed))})", pos)
        args: List[Tuple[str, int]] = []
        pos = j
        for _ in range(ARGC[name]):
            while pos < b and m[pos].isspace():
                pos += 1
            if pos >= b or m[pos] != "{":
                raise src.err(f"\\{name} expects {ARGC[name]} braced argument(s)", cmd_at)
            end = _match(m, pos, src)
            if end >= b:
                raise src.err("argument extends past the end of \\braid{...}", pos)
            args.append((m[pos + 1:end], pos + 1))
            pos = end + 1
        try:
            if name in ("bin", "bout"):
                if (cfg_in if name == "bin" else cfg_out) is not None:
                    raise src.err(f"\\{name} given twice", cmd_at)
                node = parse_cfg(*args[0])
                if name == "bin":
                    cfg_in = (node, cmd_at)
                else:
                    cfg_out = (node, cmd_at)
            elif name == "bn":
                v = _ints(args[0][0], args[0][1], src, "\\bn")
                if len(v) != 1 or v[0][0] < 0:
                    raise src.err("\\bn expects one non-negative integer", cmd_at)
                n_decl = (v[0][0], cmd_at)
            elif name == "bcr":
                gens.extend(_ints(args[0][0], args[0][1], src, "\\bcr"))
            elif name == "bcol":
                color = args[1][0].strip()
                check_color(color)
                if args[0][0].strip() == "*":
                    if inner:
                        raise src.err("\\bcol{*} (main colour) is not allowed inside \\bsub",
                                      cmd_at)
                    opts["color"] = color
                else:
                    for k, _ in _ints(args[0][0], args[0][1], src, "\\bcol"):
                        colors[k] = color
            elif name == "bnote":
                (k, _), = _ints(args[0][0], args[0][1], src, "\\bnote")
                notes[k] = args[1][0].strip()
            elif name == "blab":
                side = args[0][0].strip()
                if side not in ("in", "out"):
                    raise src.err("\\blab: first argument must be 'in' or 'out'", cmd_at)
                labels[side] = [l.label for l in parse_cfg(*args[1]).leaves()]
            elif name == "bpt":
                side = args[0][0].strip()
                (k, _), = _ints(args[1][0], args[1][1], src, "\\bpt")
                points.append(Point(side, k, args[2][0].strip() or None))
            elif name == "bax":
                flags = [f.strip() for f in args[0][0].split(",") if f.strip()] or ["h"]
                kind = "frame" if "frame" in flags else "h"
                bad = set(flags) - {"h", "frame", "front", "noticks"}
                if bad:
                    raise src.err(f"\\bax: unknown flag(s) {sorted(bad)}", cmd_at)
                axis = Axis(kind, "front" in flags, "noticks" not in flags)
            elif name == "bset":
                opts.update(split_options(args[0][0]))
            elif name == "bsub":
                v = _ints(args[0][0], args[0][1], src, "\\bsub")
                if len(v) != 1 or v[0][0] < 1:
                    raise src.err("\\bsub: first argument must be one strand number >= 1", cmd_at)
                body, off = args[1]
                subs.append((v[0][0], parse_body(m, off, off + len(body), {}, src, cmd_at,
                                                 inner=True), cmd_at))
        except TransformError:
            raise
        except BraidValidationError as e:
            raise src.err(str(e), cmd_at)

    try:
        style = Style.from_options(opts)
        braid = Braid([g for g, _ in gens],
                      cfg_in[0] if cfg_in else None, cfg_out[0] if cfg_out else None,
                      n=n_decl[0] if n_decl else None, colors=colors, notes=notes,
                      points=points, axis=axis, style=style,
                      in_labels=labels.get("in"), out_labels=labels.get("out"))
    except BraidValidationError as e:
        off = at
        mm = re.search(r"generator #(\d+)", str(e))
        if mm and 0 < int(mm.group(1)) <= len(gens):
            off = gens[int(mm.group(1)) - 1][1]
        raise src.err(str(e), off)
    for k, sub, off in sorted(subs, key=lambda t: -t[0]):      # high k first: indices stay valid
        try:
            braid = braid.compose_at(k, sub)
        except BraidValidationError as e:
            raise src.err(str(e), off)
    return braid


@dataclass
class Item:
    file: str
    line: int
    key: str = ""
    status: str = "checked"       # generated | reused | checked
    path: str = ""
    reason: str = ""


@dataclass
class TransformResult:
    text: str
    items: List[Item] = field(default_factory=list)
    changed: bool = False


_TOKEN = re.compile(r"\\braid(setup|id)?(?![A-Za-z@])")


def transform_text(text: str, name: str = "<expr>", cache: Optional[Cache] = None,
                   asset_ref: Optional[str] = None, fmt: str = "tikz") -> TransformResult:
    """Replace every ``\\braid{...}`` in ``text``.  With ``cache=None`` only validate."""
    src = Source(text, name)
    m = mask(text)
    defaults: Dict[str, str] = {}
    out: List[str] = []
    items: List[Item] = []
    last = 0
    ref = (asset_ref if asset_ref is not None else (str(cache.dir) if cache else "braids"))
    ref = ref.replace(os.sep, "/").rstrip("/")
    for mt in _TOKEN.finditer(m):
        if mt.start() < last:
            continue
        j = mt.end()
        while j < len(m) and m[j].isspace():
            j += 1
        if j >= len(m) or m[j] != "{":
            raise src.err(f"\\{mt.group()[1:]} must be followed by {{...}}", mt.start())
        end = _match(m, j, src)
        if mt.group(1) == "id":                           # \braidid{name}{options}
            k2 = end + 1
            while k2 < len(m) and m[k2].isspace():
                k2 += 1
            if k2 >= len(m) or m[k2] != "{":
                raise src.err("\\braidid expects two braced arguments: \\braidid{name}{options}",
                              mt.start())
            end2 = _match(m, k2, src)
            from .identities import make_scene
            try:
                scene = make_scene(m[j + 1:end].strip(), split_options(m[k2 + 1:end2]), defaults)
            except BraidTeXError as e:
                raise src.err(str(e), mt.start())
            line = src.loc(mt.start())[0]
            if cache is None:
                items.append(Item(name, line))
                replacement = ""
            else:
                asset = cache.ensure_text(scene.key(), scene.render)
                items.append(Item(name, line, asset.key, asset.status, str(asset.path),
                                  asset.reason))
                replacement = f"\\braidfig{{{ref}/{asset.path.with_suffix('').name}}}"
            out.append(text[last:mt.start()])
            out.append(replacement)
            last = end2 + 1
            continue
        if mt.group(1):                                   # \braidsetup
            try:
                defaults.update(split_options(m[j + 1:end]))
                Style.from_options(defaults)
            except BraidValidationError as e:
                raise src.err(str(e), j)
            continue                                      # stays in the source (no-op macro)
        braid = parse_body(m, j + 1, end, defaults, src, mt.start())
        line = src.loc(mt.start())[0]
        if cache is None:
            items.append(Item(name, line))
            replacement = ""
        else:
            asset = cache.ensure(braid, fmt)
            items.append(Item(name, line, asset.key, asset.status, str(asset.path), asset.reason))
            stem = asset.path.with_suffix("").name
            replacement = f"\\braidfig{{{ref}/{stem}}}"
        out.append(text[last:mt.start()])
        out.append(replacement)
        last = end + 1
    out.append(text[last:])
    new = "".join(out)
    return TransformResult(new, items, new != text)


def transform_expression(expr: str, cache: Cache, **kw) -> TransformResult:
    return transform_text(expr, "<expr>", cache, **kw)


_INCLUDE = re.compile(r"\\(input|include)\s*\{([^{}]+)\}")


def find_includes(text: str, root: Path) -> List[Path]:
    m = mask(text)
    found = []
    for mt in _INCLUDE.finditer(m):
        name = text[mt.start(2):mt.end(2)].strip()
        for cand in (root / name, root / (name + ".tex")):
            if cand.is_file():
                found.append(cand)
                break
    return found


def transform_project(main: Path, build_dir: Path, cache: Cache,
                      asset_ref: Optional[str] = None) -> Tuple[Path, List[Item], List[Path]]:
    """Transform ``main`` and every ``\\input``/``\\include``d file containing braids.

    Output goes to ``build_dir`` (mirroring paths relative to main's directory);
    originals are never modified.  Returns (transformed main, items, written files).
    """
    main = main.resolve()
    root = main.parent
    items: List[Item] = []
    written: List[Path] = []
    queue, seen = [main], set()
    out_main = build_dir / main.name
    while queue:
        f = queue.pop(0)
        if f in seen:
            continue
        seen.add(f)
        text = f.read_text(encoding="utf-8")
        rel = f.relative_to(root) if f.is_relative_to(root) else Path(f.name)
        res = transform_text(text, str(rel), cache, asset_ref)
        items.extend(res.items)
        is_main = f == main
        if res.changed or _TOKEN.search(mask(text)) or is_main:
            dest = build_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            from .cache import atomic_write
            atomic_write(dest, res.text.encode("utf-8"))
            written.append(dest)
        queue.extend(find_includes(text, root))
    return out_main, items, written
