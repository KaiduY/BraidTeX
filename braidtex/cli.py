from __future__ import annotations

import argparse
from pathlib import Path

from . import Braid, parse_config, render_svg
from .transform import transform_tex


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="braidtex", description="Render and transform braid diagrams.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="Render a braid to SVG")
    render.add_argument("--n", type=int, default=3)
    render.add_argument("--word", default="1,-2")
    render.add_argument("--input", default="x_1 x_2 x_3")
    render.add_argument("--output", default=None)
    render.add_argument("--outfile", default="braid.svg")

    transform = subparsers.add_parser("transform", help="Transform a LaTeX source string on stdin or in a file")
    transform.add_argument("path", nargs="?", default=None)
    transform.add_argument("--output", default=None)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "render":
        word = [int(part.strip()) for part in args.word.split(",") if part.strip()]
        input_cfg = parse_config(args.input)
        output_cfg = parse_config(args.output) if args.output else input_cfg
        braid = Braid(n=args.n, word=word, input_config=input_cfg, output_config=output_cfg)
        svg = render_svg(braid)
        output_path = Path(args.outfile)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(svg, encoding="utf-8")
        print(f"Rendered {args.outfile}")
        return

    if args.command == "transform":
        if args.path is None:
            source = input()
        else:
            source = Path(args.path).read_text(encoding="utf-8")
        transformed = transform_tex(source)
        output_path_value = args.output or (str(Path(args.path).with_suffix(".transformed.tex")) if args.path else "transformed.tex")
        output_path = Path(output_path_value)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(transformed, encoding="utf-8")
        print(f"Wrote transformed source to {output_path}")
        return


if __name__ == "__main__":
    main()
