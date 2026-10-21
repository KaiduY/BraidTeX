"""Deterministic, atomic, project-local asset cache.

Cache key = SHA-256 over the canonical JSON of the *resolved* braid spec
(normalized trees, resolved target, colours, style, ...), the output format
and ``RENDER_VERSION``.  Asset names are ``bt-<first 16 hex digits>.<ext>`` and
the first line of every text asset records the full key, which is verified
on reuse.  Files are written to a temporary name and moved into place with
``os.replace`` so interrupted builds never leave partial assets.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .errors import BuildError
from .model import Braid
from .render import RENDER_VERSION, render_standalone, render_svg, render_tikz

EXT = {"tikz": "tikz", "standalone": "tex", "svg": "svg", "pdf": "pdf"}
RENDERERS: Dict[str, Callable[[Braid, str], str]] = {
    "tikz": render_tikz, "standalone": render_standalone, "svg": render_svg}
PREFIX = "bt-"


def cache_key(braid: Braid, fmt: str = "tikz") -> str:
    canon = json.dumps({"render": RENDER_VERSION, "format": fmt, "spec": braid.to_dict()},
                       sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canon.encode()).hexdigest()


@dataclass
class Asset:
    path: Path
    key: str
    status: str            # 'generated' | 'reused'
    reason: str = ""


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _valid(path: Path, key: str, fmt: str) -> bool:
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return False
        if fmt == "pdf":
            with open(path, "rb") as fh:
                return fh.read(5) == b"%PDF-" and _tail_has_eof(path)
        with open(path, "r", encoding="utf-8") as fh:
            return key in fh.read(300)
    except (OSError, UnicodeDecodeError):
        return False


def _tail_has_eof(path: Path) -> bool:
    with open(path, "rb") as fh:
        fh.seek(0, 2)
        fh.seek(max(0, fh.tell() - 64))
        return b"%%EOF" in fh.read()


class Cache:
    """Asset directory (default ``<project>/braids``)."""

    def __init__(self, directory: os.PathLike | str = "braids", force: bool = False):
        self.dir = Path(directory)
        self.force = force

    def path_for(self, key: str, fmt: str) -> Path:
        return self.dir / f"{PREFIX}{key[:16]}.{EXT[fmt]}"

    def ensure_text(self, key: str, producer: Callable[[str], str], fmt: str = "tikz") -> Asset:
        """Cache an arbitrary text asset (used for composite scenes such as ``\\braidid``)."""
        path = self.path_for(key, fmt)
        if not self.force and _valid(path, key, fmt):
            return Asset(path, key, "reused")
        reason = "forced" if self.force else ("changed or new" if not path.exists() else "invalid")
        atomic_write(path, producer(key).encode("utf-8"))
        return Asset(path, key, "generated", reason)

    def ensure(self, braid: Braid, fmt: str = "tikz", engine: str = "pdflatex") -> Asset:
        if fmt not in EXT:
            raise BuildError(f"unknown format {fmt!r}; choose from {', '.join(EXT)}")
        key = cache_key(braid, fmt)
        path = self.path_for(key, fmt)
        if not self.force and _valid(path, key, fmt):
            return Asset(path, key, "reused")
        reason = "forced" if self.force else ("changed or new" if not path.exists() else "invalid")
        if fmt == "pdf":
            atomic_write(path, compile_standalone_pdf(braid, key, engine))
        else:
            atomic_write(path, RENDERERS[fmt](braid, key).encode("utf-8"))
        return Asset(path, key, "generated", reason)

    def clean(self) -> List[Path]:
        removed: List[Path] = []
        if self.dir.is_dir():
            for p in sorted(self.dir.iterdir()):
                if p.name.startswith(PREFIX) or p.name.startswith(".tmp-"):
                    p.unlink()
                    removed.append(p)
            try:
                self.dir.rmdir()      # only if empty
            except OSError:
                pass
        return removed


def standalone_document(tikz: str) -> str:
    return ("\\documentclass[tikz,border=4pt]{standalone}\n\\usepackage{amsmath,amssymb}\n"
            "\\begin{document}\n" + tikz + "\\end{document}\n")


def compile_standalone_pdf(braid: Braid, key: str = "", engine: str = "pdflatex") -> bytes:
    return compile_tex(render_standalone(braid, key), engine)


def compile_tex(source: str, engine: str = "pdflatex") -> bytes:
    if shutil.which(engine) is None:
        raise BuildError(f"LaTeX engine {engine!r} not found; install TeX Live or use "
                         f"--format tikz/standalone/svg")
    with tempfile.TemporaryDirectory(prefix="braidtex-") as td:
        tex = Path(td) / "fig.tex"
        tex.write_text(source, encoding="utf-8")
        proc = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error",
                               "-no-shell-escape", "fig.tex"], cwd=td,
                              capture_output=True, text=True, timeout=120)
        pdf = Path(td) / "fig.pdf"
        if proc.returncode != 0 or not pdf.exists():
            tail = "\n".join(proc.stdout.splitlines()[-15:])
            raise BuildError(f"{engine} failed on the standalone figure:\n{tail}")
        return pdf.read_bytes()
