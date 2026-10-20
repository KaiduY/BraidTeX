"""Command line interface for BraidTeX preprocessing and builds."""
from __future__ import annotations
from pathlib import Path
import argparse
import os
import subprocess
import sys

from braidtex_transform import BraidTransformError, clean_cache, transform_file, transform_project, transform_source


def _add_project_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--asset-dir", default="braids", help="project-local directory for generated .tikz assets (default: braids)")
    parser.add_argument("--cache-dir", default=None, help="cache metadata directory (default: <asset-dir>/.cache)")
    parser.add_argument("--force", action="store_true", help="regenerate assets even if the deterministic cache is valid")


def _compile(source: Path, transformed: Path, engine: str, verbose: bool) -> int:
    try:
        import braidtex_data
        style_dir = str(Path(braidtex_data.__file__).resolve().parent)
    except Exception as exc:
        print(f"Could not locate the BraidTeX LaTeX package: {exc}", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env["TEXINPUTS"] = style_dir + os.pathsep + env.get("TEXINPUTS", "") + os.pathsep
    jobname = source.stem
    if engine == "latexmk":
        command = ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"-jobname={jobname}", str(transformed.resolve())]
        passes = 1
    else:
        command = [engine, "-interaction=nonstopmode", "-halt-on-error", f"-jobname={jobname}", str(transformed.resolve())]
        passes = 2
    for pass_no in range(passes):
        if verbose or pass_no == 0:
            print("+", " ".join(command))
        try:
            completed = subprocess.run(command, cwd=source.parent, env=env, check=False)
        except FileNotFoundError:
            print(f"Required LaTeX engine {engine!r} was not found on PATH.", file=sys.stderr)
            return 127
        if completed.returncode != 0:
            log = source.parent / f"{jobname}.log"
            if log.exists():
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
                print("\n--- tail of LaTeX log ---", file=sys.stderr)
                print("\n".join(lines[-35:]), file=sys.stderr)
            return completed.returncode
    pdf = source.parent / f"{jobname}.pdf"
    if not pdf.exists():
        print(f"Compilation returned success but PDF was not found at {pdf}", file=sys.stderr)
        return 1
    print(f"PDF: {pdf}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="braidtex",
        description="Transform short LaTeX braid notation into cached vector TikZ assets, then compile normally.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_expr = sub.add_parser("expr", help="transform a LaTeX snippet containing braid expressions")
    p_expr.add_argument("expression", help="LaTeX snippet or equation text containing \\braid{...}")
    p_expr.add_argument("-o", "--output", type=Path, default=None, help="write transformed TeX here instead of stdout")
    p_expr.add_argument("--project-dir", type=Path, default=Path.cwd(), help="base directory for generated assets (default: current directory)")
    _add_project_options(p_expr)

    p_transform = sub.add_parser("transform", help="preprocess a .tex file; leave the original unchanged")
    p_transform.add_argument("source", type=Path)
    p_transform.add_argument("-o", "--output", type=Path, default=None)
    _add_project_options(p_transform)

    p_build = sub.add_parser("build", help="preprocess then compile the LaTeX document")
    p_build.add_argument("source", type=Path)
    p_build.add_argument("--engine", choices=("pdflatex", "lualatex", "xelatex", "latexmk"), default="pdflatex")
    p_build.add_argument("--verbose", action="store_true")
    p_build.add_argument("--output-tex", type=Path, default=None, help="transformed .tex path (default: <name>.braidtex.tex)")
    _add_project_options(p_build)

    p_clean = sub.add_parser("clean", help="remove only BraidTeX-generated assets and cache metadata")
    p_clean.add_argument("--project-dir", type=Path, default=Path.cwd())
    p_clean.add_argument("--asset-dir", default="braids")
    p_clean.add_argument("--cache-dir", default=None)
    p_clean.add_argument("--keep-transformed", action="store_true", help="keep generated *.braidtex.tex source copies")

    args = parser.parse_args(argv)
    try:
        if args.subcommand == "expr":
            project = args.project_dir.resolve()
            project.mkdir(parents=True, exist_ok=True)
            transformed, assets = transform_source(
                args.expression,
                source_path=project / "_braidtex_inline_expression.tex",
                asset_dir=args.asset_dir,
                cache_dir=args.cache_dir,
                force=args.force,
                project_dir=project,
            )
            if args.output is None:
                sys.stdout.write(transformed)
                if not transformed.endswith("\n"):
                    sys.stdout.write("\n")
            else:
                target = args.output.resolve()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(transformed, encoding="utf-8")
                print(f"Transformed expression: {target}")
            print(f"Generated/reused braid assets: {len(set(assets))}", file=sys.stderr)
            return 0
        if args.subcommand == "transform":
            output, generated, transformed_files = transform_project(
                args.source, output=args.output, asset_dir=args.asset_dir,
                cache_dir=args.cache_dir, force=args.force,
            )
            print(f"Transformed root source: {output}")
            print(f"Transformed TeX files: {len(transformed_files)}")
            print(f"Generated/reused unique braid assets: {len(generated)}")
            return 0
        if args.subcommand == "build":
            source = args.source.resolve()
            transformed, generated, transformed_files = transform_project(
                source, output=args.output_tex, asset_dir=args.asset_dir,
                cache_dir=args.cache_dir, force=args.force,
            )
            print(f"Transformed root source: {transformed}")
            print(f"Transformed TeX files: {len(transformed_files)}")
            print(f"Generated/reused unique braid assets: {len(generated)}")
            return _compile(source, transformed, args.engine, args.verbose)
        count = clean_cache(args.asset_dir, project_dir=args.project_dir, cache_dir=args.cache_dir)
        if not args.keep_transformed and args.project_dir.exists():
            for path in args.project_dir.resolve().rglob("*.braidtex.tex"):
                try:
                    path.unlink()
                    count += 1
                except OSError:
                    pass
        print(f"Removed {count} BraidTeX-managed file(s).")
        return 0
    except (BraidTransformError, OSError, ValueError) as exc:
        print(f"braidtex: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
