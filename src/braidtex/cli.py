"""Command line interface: ``braidtex <command>``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .build import clean_project, compile_document, prepare, sty_dir
from .cache import EXT, Cache
from .errors import BraidTeXError
from .model import Braid
from .transform import Source, mask, parse_body, transform_text


def _report(items, verbose: bool) -> None:
    gen = sum(i.status == "generated" for i in items)
    reu = sum(i.status == "reused" for i in items)
    print(f"braidtex: {len(items)} diagram(s): {gen} generated, {reu} reused", file=sys.stderr)
    if verbose:
        for i in items:
            print(f"  {i.file}:{i.line}  {i.status:<9} {i.path}"
                  + (f"  ({i.reason})" if i.reason else ""), file=sys.stderr)


def _braid_from_expr(expr: str) -> Braid:
    """Body of \\braid{...} given on the command line."""
    src = Source(expr, "<expr>")
    return parse_body(mask(expr), 0, len(expr), {}, src, 0)


def cmd_render_identity(a) -> int:
    from .cache import compile_tex, standalone_document
    from .identities import make_scene
    from .style import split_options
    scene = make_scene(a.identity, split_options(a.opts or ""), {})
    tikz = scene.render(scene.key())
    if a.format == "pdf":
        if not a.output:
            raise BraidTeXError("--format pdf needs -o FILE")
        Path(a.output).write_bytes(compile_tex(standalone_document(tikz), a.engine))
        print(a.output)
        return 0
    text = standalone_document(tikz) if a.format == "standalone" else tikz
    if a.format == "svg":
        raise BraidTeXError("identities are available as tikz, standalone or pdf (not svg)")
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        print(a.output)
    else:
        sys.stdout.write(text)
    return 0


def cmd_render(a) -> int:
    if a.identity:
        return cmd_render_identity(a)
    if a.json:
        spec = sys.stdin.read() if a.json == "-" else Path(a.json).read_text(encoding="utf-8")
        braid = Braid.from_json(spec)
    elif a.expr:
        braid = _braid_from_expr(a.expr)
    else:
        raise BraidTeXError("give --expr '\\bin{x_1 x_2} \\bcr{1}' or --json spec.json")
    cache = Cache(a.assets or "braids", a.force)
    if a.output:
        out = Path(a.output)
        if a.format == "pdf":
            from .cache import compile_standalone_pdf
            out.write_bytes(compile_standalone_pdf(braid, "", a.engine))
        else:
            from .cache import RENDERERS
            out.write_text(RENDERERS[a.format](braid, ""), encoding="utf-8")
        print(out)
    elif a.assets:
        asset = cache.ensure(braid, a.format, a.engine)
        print(asset.path)
        if a.verbose:
            print(f"{asset.status} {asset.reason}", file=sys.stderr)
    else:
        if a.format == "pdf":
            raise BraidTeXError("--format pdf needs -o FILE or --assets DIR")
        from .cache import RENDERERS
        sys.stdout.write(RENDERERS[a.format](braid, ""))
    return 0


def cmd_expr(a) -> int:
    text = sys.stdin.read() if a.text == "-" else a.text
    res = transform_text(text, "<expr>", Cache(a.assets or "braids", a.force))
    sys.stdout.write(res.text if res.text.endswith("\n") else res.text + "\n")
    _report(res.items, a.verbose)
    return 0


def cmd_transform(a) -> int:
    main = Path(a.file)
    if a.check:
        res = transform_text(main.read_text(encoding="utf-8"), str(main), None)
        print(f"{main}: {len(res.items)} braid expression(s) valid", file=sys.stderr)
        return 0
    out, build, items = prepare(main, a.assets, a.force, a.build)
    if a.stdout:
        sys.stdout.write(out.read_text(encoding="utf-8"))
    else:
        print(out)
    _report(items, a.verbose)
    return 0


def cmd_compile(a) -> int:
    pdf, items = compile_document(Path(a.file), a.engine, a.assets, a.force, a.build, a.verbose)
    _report(items, a.verbose)
    print(pdf)
    return 0


def cmd_clean(a) -> int:
    removed = clean_project(Path(a.path), a.assets)
    for p in removed:
        print(f"removed {p}", file=sys.stderr)
    print(f"braidtex: removed {len(removed)} item(s)", file=sys.stderr)
    return 0


def cmd_sty(a) -> int:
    print(sty_dir())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="braidtex", description="Braid diagrams for LaTeX.")
    p.add_argument("--version", action="version", version=f"braidtex {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp, force=True):
        sp.add_argument("--assets", type=Path, help="asset/cache directory (default: braids/)")
        if force:
            sp.add_argument("-f", "--force", action="store_true", help="regenerate everything")
        sp.add_argument("-v", "--verbose", action="store_true", help="show reused/generated")

    r = sub.add_parser("render", help="render one braid (from --expr or --json)")
    r.add_argument("--expr", help="body of \\braid{...}, e.g. '\\bin{x_1 x_2} \\bcr{1}'")
    r.add_argument("--json", help="JSON spec file ('-' = stdin)")
    r.add_argument("--identity", help="standard identity: ybe far inverse crossings assoc "
                                      "pentagon hexagon")
    r.add_argument("--opts", help="options for --identity, e.g. 'objects={a b c d},scale=0.8'")
    r.add_argument("--format", choices=list(EXT), default="tikz")
    r.add_argument("-o", "--output", help="write to this file instead of stdout/cache")
    r.add_argument("--engine", default="pdflatex", choices=["pdflatex", "lualatex", "xelatex"])
    common(r)
    r.set_defaults(func=cmd_render)

    e = sub.add_parser("expr", help="transform a LaTeX fragment containing \\braid{...}")
    e.add_argument("text", help="fragment, or '-' for stdin")
    common(e)
    e.set_defaults(func=cmd_expr)

    t = sub.add_parser("transform", help="preprocess a .tex file (original untouched)")
    t.add_argument("file")
    t.add_argument("--build", type=Path, help="output directory (default: .braidtex-build/)")
    t.add_argument("--stdout", action="store_true", help="print the transformed main file")
    t.add_argument("--check", action="store_true", help="only validate, write nothing")
    common(t)
    t.set_defaults(func=cmd_transform)

    c = sub.add_parser("compile", help="transform + compile to PDF")
    c.add_argument("file")
    c.add_argument("--engine", default="pdflatex", choices=["pdflatex", "lualatex", "xelatex"])
    c.add_argument("--build", type=Path)
    common(c)
    c.set_defaults(func=cmd_compile)

    k = sub.add_parser("clean", help="delete generated assets and the build directory")
    k.add_argument("path", nargs="?", default=".", help="project directory or main .tex")
    k.add_argument("--assets", type=Path)
    k.set_defaults(func=cmd_clean)

    s = sub.add_parser("sty", help="print the directory containing braidtex.sty")
    s.set_defaults(func=cmd_sty)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except BraidTeXError as e:
        print(f"braidtex: error: {e}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as e:
        print(f"braidtex: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
