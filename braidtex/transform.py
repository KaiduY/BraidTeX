from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .core import Braid, parse_config
from .render import render_svg


def _consume_braced(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise ValueError("Expected '{' to begin a braced expression.")
    depth = 0
    buffer: list[str] = []
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
            if depth == 1:
                i += 1
                continue
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return "".join(buffer), i + 1
        if depth > 0:
            buffer.append(ch)
        i += 1
    raise ValueError("Unterminated braced expression.")


def _parse_braid_body(body: str) -> Braid:
    input_config = None
    output_config = None
    word: list[int] = []
    colors: dict[int, str] = {}
    i = 0

    while i < len(body):
        if body[i].isspace():
            i += 1
            continue
        if body.startswith("\\bin", i):
            j = i + 4
            while j < len(body) and body[j].isspace():
                j += 1
            if j >= len(body) or body[j] != "{":
                raise ValueError("Malformed \\bin command in braid specification.")
            inner, i = _consume_braced(body, j)
            input_config = parse_config(inner)
            continue
        if body.startswith("\\bout", i):
            j = i + 5
            while j < len(body) and body[j].isspace():
                j += 1
            if j >= len(body) or body[j] != "{":
                raise ValueError("Malformed \\bout command in braid specification.")
            inner, i = _consume_braced(body, j)
            output_config = parse_config(inner)
            continue
        if body.startswith("\\bcr", i):
            j = i + 4
            while j < len(body) and body[j].isspace():
                j += 1
            if j >= len(body) or body[j] != "{":
                raise ValueError("Malformed \\bcr command in braid specification.")
            inner, i = _consume_braced(body, j)
            for part in inner.replace(",", " ").split():
                if part:
                    word.append(int(part))
            continue
        if body.startswith("\\bcolor", i):
            j = i + 7
            while j < len(body) and body[j].isspace():
                j += 1
            if j >= len(body) or body[j] != "{":
                raise ValueError("Malformed \\bcolor command in braid specification.")
            index_text, j2 = _consume_braced(body, j)
            if j2 >= len(body) or body[j2] != "{":
                raise ValueError("Malformed \\bcolor command: missing color value.")
            color_text, i = _consume_braced(body, j2)
            colors[int(index_text.strip())] = color_text.strip()
            continue
        raise ValueError(f"Unsupported token in braid specification: {body[i : i + 20]!r}")

    if input_config is None:
        input_config = parse_config("x_1 x_2 x_3") if len(word) or True else parse_config("")
    if output_config is None:
        output_config = input_config
    n = max(input_config.arity, output_config.arity)
    return Braid(n=n, word=word, input_config=input_config, output_config=output_config, colors=colors)


def render_braid(body: str, output_dir: str = "generated/braids") -> str:
    braid = _parse_braid_body(body)
    os.makedirs(output_dir, exist_ok=True)
    key = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    path = Path(output_dir) / f"braid_{key}.svg"
    if not path.exists():
        path.write_text(render_svg(braid), encoding="utf-8")
    return str(path)


def transform_tex(source: str, output_dir: str = "generated/braids") -> str:
    result: list[str] = []
    i = 0
    while i < len(source):
        if source.startswith(r"\braid", i):
            j = i + len(r"\braid")
            while j < len(source) and source[j].isspace():
                j += 1
            if j >= len(source) or source[j] != "{":
                result.append(source[i:j])
                i = j
                continue
            body, end = _consume_braced(source, j)
            result.append(render_svg(_parse_braid_body(body)))
            i = end
            continue
        result.append(source[i])
        i += 1
    return "".join(result)
