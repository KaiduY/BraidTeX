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
    skip = [build, assets]
    for d in [d for d in root.rglob("*") if d.is_dir()]:       # snapshot: we create dirs below
        rel = d.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if any(d == k or k in d.parents for k in skip):         # never recurse into our own output
            continue
        (build / rel).mkdir(parents=True, exist_ok=True)
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
               "-synctex=1", "-file-line-error",
               f"-outdir={rel_build}", f"-jobname={jobname}", "-silent",
               f"-pdflatex={engine} -no-shell-escape %O %S", rel_out]
        runs = [cmd]
    else:
        base = [engine, "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
                "-synctex=1", "-file-line-error",
                f"-output-directory={rel_build}", f"-jobname={jobname}", rel_out]
        runs = [base, base]
    for cmd in runs:
        proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
        if verbose:
            print(proc.stdout)
        if proc.returncode != 0:
            log = build_dir / f"{jobname}.log"
            remap_log(log, root, build_dir)
            tail = "\n".join((log.read_text(errors="replace") if log.exists()
                              else proc.stdout).splitlines()[-25:])
            raise BuildError(f"{cmd[0]} failed (exit {proc.returncode}). Log tail:\n{tail}")
    pdf = build_dir / f"{jobname}.pdf"
    if not pdf.exists():
        raise BuildError(f"{engine} reported success but {pdf} does not exist")
    remap_synctex(build_dir / f"{jobname}.synctex.gz", root, build_dir)
    remap_log(build_dir / f"{jobname}.log", root, build_dir)
    if build is not None:                 # explicit --build DIR: the PDF stays there (e.g. out/)
        return pdf, items
    dest = root / f"{jobname}.pdf"        # default: copy next to the source
    shutil.copyfile(pdf, dest)
    return dest, items


def remap_log(log: Path, root: Path, build: Path) -> int:
    """Rewrite ``<build>/file.tex`` to ``file.tex`` in the LaTeX log (``-file-line-error``
    messages) when the original exists, so editors link errors to your own sources.
    Line numbers already agree (see ``transform_text``)."""
    import re
    if not log.is_file():
        return 0
    rel = os.path.relpath(build, root).replace(os.sep, "/")
    text = log.read_text(encoding="utf-8", errors="surrogateescape")
    n = 0

    def fix(m: "re.Match[str]") -> str:
        nonlocal n
        if (root / m.group(2)).is_file():
            n += 1
            return m.group(2)
        return m.group(0)

    new = re.sub(r"(?<![\w/.-])((?:\./)?" + re.escape(rel) + r"/)([^\s:()\"]+\.tex)", fix, text)
    if n:
        log.write_text(new, encoding="utf-8", errors="surrogateescape")
    return n


def remap_synctex(path: Path, root: Path, build: Path) -> int:
    """Point SyncTeX at the *original* sources.

    The transformed copies live in the build directory but have the same line
    numbers as the originals (``transform_text`` preserves them), so rewriting
    the ``Input:`` entries makes forward and inverse search use your own files.
    Returns the number of rewritten entries."""
    import gzip
    import re
    if not path.is_file():
        return 0
    try:
        text = gzip.open(path, "rt", encoding="utf-8", errors="surrogateescape").read()
    except OSError:
        return 0
    n = 0

    def fix(m: "re.Match[str]") -> str:
        nonlocal n
        raw = m.group(2)
        cand = Path(raw)
        cand = cand if cand.is_absolute() else (root / cand)
        try:
            rel = cand.resolve().relative_to(build.resolve())
        except ValueError:
            return m.group(0)
        orig = root / rel
        if not orig.is_file():
            return m.group(0)
        n += 1
        return f"{m.group(1)}{orig}"

    new = re.sub(r"(?m)^(Input:\d+:)(.*)$", fix, text)
    if n:
        with gzip.open(path, "wt", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(new)
    return n


def clean_project(main_or_dir: Path, assets: Optional[Path] = None) -> List[Path]:
    p = Path(main_or_dir).resolve()
    root = p if p.is_dir() else p.parent
    removed = Cache(Path(assets).resolve() if assets else root / "braids").clean()
    b = root / BUILD_DIRNAME
    if b.is_dir():
        shutil.rmtree(b)
        removed.append(b)
    return removed
