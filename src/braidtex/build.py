"""Document build: transform (project-wide) then run an ordinary LaTeX engine.

Layout used for a project ``P`` with main file ``P/main.tex``::

    P/main.tex                original, never modified
    P/braids/bt-*.tikz        generated assets (cache)
    P/.braidtex-build/        transformed copies + LaTeX aux files
    P/main.pdf                final result (copied out of the build dir)

The engine runs with ``cwd = P`` so every relative ``\\input`` /
``\\includegraphics`` / bibliography path keeps its meaning.  The build
directory is put *first* on ``TEXINPUTS`` so transformed copies of
``\\input``/``\\include``d files shadow the originals without rewriting paths.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .cache import Cache
from .errors import BuildError
from .transform import Item, transform_project

BUILD_DIRNAME = ".braidtex-build"
ENGINES = {"pdflatex": "-pdf", "lualatex": "-lualatex", "xelatex": "-xelatex"}


def sty_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def project_env(root: Path, build: Path) -> dict:
    env = dict(os.environ)
    sep = os.pathsep
    env["TEXINPUTS"] = sep.join([str(build), str(sty_dir()), env.get("TEXINPUTS", "")]) + sep
    env["BIBINPUTS"] = sep.join([str(root), env.get("BIBINPUTS", "")]) + sep
    env["BSTINPUTS"] = sep.join([str(root), env.get("BSTINPUTS", "")]) + sep
    return env


def prepare(main: Path, assets: Optional[Path] = None, force: bool = False,
            build: Optional[Path] = None) -> Tuple[Path, Path, List[Item]]:
    """Transform; returns (transformed main, build dir, items)."""
    main = Path(main).resolve()
    root = main.parent
    build = Path(build).resolve() if build else root / BUILD_DIRNAME
    assets = Path(assets).resolve() if assets else root / "braids"
    ref = os.path.relpath(assets, root)           # engine runs with cwd = root
    build.mkdir(parents=True, exist_ok=True)
    out, items, _ = transform_project(main, build, Cache(assets, force), ref)
    # mirror source sub-directories so \include aux files can be written
    for d in root.rglob("*"):
        if d.is_dir() and not any(p.startswith(".") for p in d.relative_to(root).parts) \
                and d != assets:
            (build / d.relative_to(root)).mkdir(parents=True, exist_ok=True)
    return out, build, items


def compile_document(main: Path, engine: str = "pdflatex", assets: Optional[Path] = None,
                     force: bool = False, build: Optional[Path] = None,
                     verbose: bool = False) -> Tuple[Path, List[Item]]:
    if engine not in ENGINES:
        raise BuildError(f"unsupported engine {engine!r}; choose {', '.join(ENGINES)}")
    if shutil.which(engine) is None:
        raise BuildError(f"{engine} not found on PATH; the transformed source was not compiled "
                         f"(run `braidtex transform` to inspect it)")
    main = Path(main).resolve()
    root = main.parent
    out, build_dir, items = prepare(main, assets, force, build)
    env = project_env(root, build_dir)
    rel_out = os.path.relpath(out, root)
    rel_build = os.path.relpath(build_dir, root)
    jobname = main.stem
    if shutil.which("latexmk"):
        cmd = ["latexmk", ENGINES[engine], "-interaction=nonstopmode", "-halt-on-error",
               f"-outdir={rel_build}", f"-jobname={jobname}", "-silent",
               f"-pdflatex={engine} -no-shell-escape %O %S", rel_out]
        runs = [cmd]
    else:
        base = [engine, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
                f"-output-directory={rel_build}", f"-jobname={jobname}", rel_out]
        runs = [base, base]
    for cmd in runs:
        proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
        if verbose:
            print(proc.stdout)
        if proc.returncode != 0:
            log = build_dir / f"{jobname}.log"
            tail = "\n".join((log.read_text(errors="replace") if log.exists()
                              else proc.stdout).splitlines()[-25:])
            raise BuildError(f"{cmd[0]} failed (exit {proc.returncode}). Log tail:\n{tail}")
    pdf = build_dir / f"{jobname}.pdf"
    if not pdf.exists():
        raise BuildError(f"{engine} reported success but {pdf} does not exist")
    dest = root / f"{jobname}.pdf"
    shutil.copyfile(pdf, dest)
    return dest, items


def clean_project(main_or_dir: Path, assets: Optional[Path] = None) -> List[Path]:
    p = Path(main_or_dir).resolve()
    root = p if p.is_dir() else p.parent
    removed = Cache(Path(assets).resolve() if assets else root / "braids").clean()
    b = root / BUILD_DIRNAME
    if b.is_dir():
        shutil.rmtree(b)
        removed.append(b)
    return removed
