"""Safe preprocessing, deterministic diagram cache, and project-local assets."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import hashlib
import json
import os
import re
import tempfile

from braidtex import Braid, RENDERER_VERSION
from braidtex_parser import BraidSyntaxError, parse_braid_body, read_group, read_optional, split_options

MARKER_RE = re.compile(r"\\(braidexpr|btbraid|braid)\b")
PACKAGE_RE = re.compile(r"\\usepackage(?:\[[^]]*\])?\s*\{[^}]*\bbraidtex\b[^}]*\}")
DEFAULTS_RE = re.compile(r"\\braiddefaults\b")
INPUT_RE = re.compile(r"\\(input|include)\b")
INCLUDEONLY_RE = re.compile(r"\\includeonly\b")
DOC_CLASS_RE = re.compile(r"\\documentclass(?:\[[^]]*\])?\s*\{[^}]+\}")
VERBATIM_BEGIN_RE = re.compile(r"\\begin\s*\{(verbatim\*?|lstlisting|minted)\}")


def _skip_literal(source: str, pos: int) -> int:
    """Return the end of an inline verbatim command/environment, or ``pos``."""
    if source.startswith(r"\verb", pos) and (pos + 5 == len(source) or not source[pos + 5].isalpha()):
        cursor = pos + 5
        if cursor < len(source) and source[cursor] == "*":
            cursor += 1
        if cursor >= len(source) or source[cursor] in "\r\n":
            newline = source.find("\n", cursor)
            return len(source) if newline < 0 else newline + 1
        delimiter = source[cursor]
        ending = source.find(delimiter, cursor + 1)
        if ending < 0:
            newline = source.find("\n", cursor)
            return len(source) if newline < 0 else newline + 1
        return ending + 1
    match = VERBATIM_BEGIN_RE.match(source, pos)
    if match:
        environment = match.group(1)
        close = re.search(r"\\end\s*\{" + re.escape(environment) + r"\}", source[match.end():])
        return len(source) if close is None else match.end() + close.end()
    return pos


class BraidTransformError(ValueError):
    """A supported braid expression could not be parsed or rendered."""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _skip_comment(source: str, pos: int) -> int:
    newline = source.find("\n", pos)
    return len(source) if newline < 0 else newline + 1


def _is_comment_start(source: str, pos: int) -> bool:
    if source[pos] != "%":
        return False
    backslashes = 0
    i = pos - 1
    while i >= 0 and source[i] == "\\":
        backslashes += 1
        i -= 1
    return backslashes % 2 == 0


def _options_to_braid(parsed: Any) -> Braid:
    options = dict(parsed.options)
    explicit_axis = options.pop("axis", False)
    color_map = dict(parsed.strand_colors)
    color = options.pop("color", "black")
    show_inputs = options.pop("input_labels", True)
    show_outputs = options.pop("output_labels", True)
    kwargs: dict[str, Any] = {
        "n": parsed.n,
        "word": parsed.word,
        "top_parenthesization": parsed.input_tree,
        "bottom_parenthesization": parsed.output_tree,
        "strand_colors": color_map if color_map else None,
        "color": color,
        "axis": bool(explicit_axis) or parsed.axis,
        "boundary_points": parsed.boundary_points,
        "annotations": parsed.annotations,
    }
    if show_inputs is False and parsed.input_tree is not None:
        kwargs["input_labels"] = [None] * parsed.n
    if show_outputs is False and parsed.output_tree is not None:
        kwargs["output_labels"] = [None] * parsed.n
    # Friendly LaTeX-facing option spellings map to the existing Python API.
    rename = {
        "scale": "diagram_scale",
        "dots": "endpoint_dots",
        "generators": "show_generators",
        "cluster_gap": "cluster_gap",
        "background_color": "background_color",
    }
    valid = {
        "diagram_scale", "strand_sep", "layer_height", "identity_height", "line_width",
        "crossing_gap", "cluster_gap", "group_spacing", "axis_y", "axis_extent", "axis_color",
        "axis_front", "endpoint_dots", "show_generators", "positive_over", "background_color",
        "label_offset", "baseline", "include_root_parentheses", "top_positions", "bottom_positions",
    }
    for key, value in options.items():
        mapped = rename.get(key, key)
        if mapped not in valid:
            raise BraidSyntaxError(f"Unsupported rendering option {key!r}")
        kwargs[mapped] = value
    try:
        return Braid(**kwargs)
    except (TypeError, ValueError) as exc:
        raise BraidSyntaxError(str(exc)) from exc


def _mask_comments(source: str) -> str:
    """Replace comments with spaces while preserving offsets and newlines."""
    chars = list(source)
    pos = 0
    while pos < len(source):
        if _is_comment_start(source, pos):
            end = _skip_comment(source, pos)
            for idx in range(pos, end):
                if chars[idx] not in "\r\n":
                    chars[idx] = " "
            pos = end
        elif source[pos] == "\\":
            literal_end = _skip_literal(source, pos)
            if literal_end > pos:
                for idx in range(pos, literal_end):
                    if chars[idx] not in "\r\n":
                        chars[idx] = " "
                pos = literal_end
            else:
                pos += 1
        else:
            pos += 1
    return "".join(chars)


def _extract_defaults(source: str) -> list[tuple[int, int, str]]:
    """Find document-level option defaults outside comments."""
    found: list[tuple[int, int, str]] = []
    pos = 0
    while pos < len(source):
        if _is_comment_start(source, pos):
            pos = _skip_comment(source, pos)
            continue
        if source[pos] == "\\":
            literal_end = _skip_literal(source, pos)
            if literal_end > pos:
                pos = literal_end
                continue
        match = DEFAULTS_RE.match(source, pos) if source[pos] == "\\" else None
        if not match:
            pos += 1
            continue
        cursor = match.end()
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor >= len(source) or source[cursor] != "{":
            raise BraidTransformError(f"\\braiddefaults needs a braced option list near line {source.count(chr(10), 0, pos)+1}")
        options, end = read_group(source, cursor)
        # Parse now, so a malformed defaults declaration gets a direct diagnostic.
        split_options(options)
        found.append((pos, end, options))
        pos = end
    return found


def _extract_expressions(source: str) -> list[tuple[int, int, str, str | None, str | None]]:
    """Return (start,end,body,optional_options,command) ranges outside comments."""
    found: list[tuple[int, int, str, str | None, str | None]] = []
    pos = 0
    while pos < len(source):
        if _is_comment_start(source, pos):
            pos = _skip_comment(source, pos)
            continue
        if source[pos] == "\\":
            literal_end = _skip_literal(source, pos)
            if literal_end > pos:
                pos = literal_end
                continue
        match = MARKER_RE.match(source, pos) if source[pos] == "\\" else None
        if not match:
            pos += 1
            continue
        command = match.group(1)
        start = pos
        cursor = match.end()
        option_text, cursor = read_optional(source, cursor)
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor >= len(source) or source[cursor] != "{":
            raise BraidTransformError(f"\\{command} needs a braced body near line {source.count(chr(10), 0, start)+1}")
        body, end = read_group(source, cursor)
        found.append((start, end, body, option_text, command))
        pos = end
    return found


def _extract_file_commands(source: str, pattern: re.Pattern[str], command_has_options: bool = False) -> list[tuple[int, int, str, str]]:
    """Find simple braced file-command arguments outside comments."""
    found: list[tuple[int, int, str, str]] = []
    pos = 0
    while pos < len(source):
        if _is_comment_start(source, pos):
            pos = _skip_comment(source, pos)
            continue
        if source[pos] == "\\":
            literal_end = _skip_literal(source, pos)
            if literal_end > pos:
                pos = literal_end
                continue
        match = pattern.match(source, pos) if source[pos] == "\\" else None
        if not match:
            pos += 1
            continue
        command = match.group(1) if match.lastindex else "includeonly"
        cursor = match.end()
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor >= len(source) or source[cursor] != "{":
            pos = match.end()
            continue
        argument, end = read_group(source, cursor)
        found.append((cursor + 1, end - 1, argument, command))
        pos = end
    return found


def _resolve_project_tex(argument: str, project_dir: Path) -> Path | None:
    """Resolve a literal, project-local TeX input path; ignore macro paths."""
    raw = argument.strip()
    if not raw or "\\" in raw or "$" in raw or "#" in raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_dir / candidate
    candidates = [candidate]
    if candidate.suffix == "":
        candidates.insert(0, candidate.with_suffix(".tex"))
    for item in candidates:
        try:
            resolved = item.resolve()
            resolved.relative_to(project_dir)
        except (OSError, ValueError):
            continue
        if resolved.is_file() and resolved.suffix.lower() == ".tex":
            return resolved
    return None


def transform_source(
    source_text: str,
    *,
    source_path: str | Path,
    asset_dir: str | Path = "braids",
    cache_dir: str | Path | None = None,
    force: bool = False,
    project_dir: str | Path | None = None,
    initial_defaults: Mapping[str, str] | None = None,
) -> tuple[str, list[Path]]:
    """Replace designated braid expressions with cached, vector TikZ assets.

    The supplied source text is never mutated. The caller chooses where to write
    the transformed result. Relative asset paths are computed from ``project_dir``
    (the compilation working directory), or the source directory by default.
    """
    source_path = Path(source_path).resolve()
    project_dir = Path(project_dir).resolve() if project_dir is not None else source_path.parent
    assets = Path(asset_dir)
    if not assets.is_absolute():
        assets = project_dir / assets
    assets = assets.resolve()
    cache = Path(cache_dir) if cache_dir is not None else assets / ".cache"
    if not cache.is_absolute():
        cache = project_dir / cache
    cache = cache.resolve()

    expressions = _extract_expressions(source_text)
    default_directives = _extract_defaults(source_text)
    if not expressions:
        if not default_directives:
            return source_text, []
        cleaned = source_text
        for start, end, _ in reversed(default_directives):
            replacement = "".join("\n" if char == "\n" else "\r" if char == "\r" else " " for char in source_text[start:end])
            cleaned = cleaned[:start] + replacement + cleaned[end:]
        return cleaned, []

    replacements: list[tuple[int, int, str]] = []
    generated: list[Path] = []
    active_defaults: dict[str, str] = dict(initial_defaults or {})
    defaults_index = 0
    for start, end, body, outer_options, command in expressions:
        while defaults_index < len(default_directives) and default_directives[defaults_index][0] < start:
            _, _, defaults_text = default_directives[defaults_index]
            active_defaults.update(split_options(defaults_text))
            defaults_index += 1
        line = source_text.count("\n", 0, start) + 1
        try:
            parsed = parse_braid_body(body, outer_options, default_options=active_defaults)
            braid = _options_to_braid(parsed)
            spec = {
                "renderer_version": RENDERER_VERSION,
                "format": "inline-tikz-v1",
                "braid": braid.to_dict(),
            }
            canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
            normalized_spec = json.loads(canonical)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
            asset_path = assets / f"bt-{digest}.tikz"
            metadata_path = cache / f"bt-{digest}.json"
            valid_cache = asset_path.exists() and metadata_path.exists() and not force
            if valid_cache:
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    valid_cache = metadata.get("key") == digest and metadata.get("spec") == normalized_spec
                except (OSError, ValueError):
                    valid_cache = False
            if not valid_cache:
                tikz = braid.tikz(inline=True) + "\n"
                _atomic_write(asset_path, tikz)
                metadata = {"key": digest, "spec": normalized_spec, "asset": asset_path.name}
                _atomic_write(metadata_path, json.dumps(metadata, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
            relative = os.path.relpath(asset_path, project_dir).replace(os.sep, "/")
            replacement = r"\braidasset{" + relative + "}"
            replacements.append((start, end, replacement))
            generated.append(asset_path)
        except (BraidSyntaxError, TypeError, ValueError) as exc:
            raise BraidTransformError(f"BraidTeX error on line {line} in \\{command}: {exc}") from exc

    result = source_text
    all_replacements = replacements + [
        (start, end, "".join("\n" if char == "\n" else "\r" if char == "\r" else " " for char in source_text[start:end]))
        for start, end, _ in default_directives
    ]
    for start, end, replacement in sorted(all_replacements, key=lambda item: item[0], reverse=True):
        result = result[:start] + replacement + result[end:]

    # Insert the package unless it is already loaded. In preprocessing mode it
    # defines the \\braidasset helper; it does not execute Python inside TeX.
    masked_result = _mask_comments(result)
    if not PACKAGE_RE.search(masked_result):
        match = DOC_CLASS_RE.search(masked_result)
        if match:
            result = result[:match.end()] + "\n\\usepackage{braidtex}" + result[match.end():]
    return result, generated


def transform_file(
    source: str | Path,
    *,
    output: str | Path | None = None,
    asset_dir: str | Path = "braids",
    cache_dir: str | Path | None = None,
    force: bool = False,
    project_dir: str | Path | None = None,
    initial_defaults: Mapping[str, str] | None = None,
) -> tuple[Path, list[Path]]:
    """Transform a .tex file into a sibling ``*.braidtex.tex`` by default."""
    source = Path(source).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"LaTeX source file not found: {source}")
    target = Path(output).resolve() if output is not None else source.with_name(source.stem + ".braidtex" + source.suffix)
    source_text = source.read_text(encoding="utf-8")
    result, generated = transform_source(
        source_text, source_path=source, asset_dir=asset_dir, cache_dir=cache_dir, force=force,
        project_dir=project_dir, initial_defaults=initial_defaults,
    )
    _atomic_write(target, result)
    return target, generated


def _defaults_from_preamble(source: str) -> dict[str, str]:
    """Collect defaults declared before the root document's begin marker."""
    begin_match = re.search(r"\\begin\s*\{document\}", _mask_comments(source))
    stop = begin_match.start() if begin_match else len(source)
    result: dict[str, str] = {}
    for start, _end, option_text in _extract_defaults(source):
        if start >= stop:
            break
        result.update(split_options(option_text))
    return result


def _rewrite_project_inputs(source: str, project_dir: Path, output_paths: Mapping[Path, Path | None]) -> str:
    """Point literal input/include commands at transformed copies when needed."""
    replacements: list[tuple[int, int, str]] = []
    for start, end, argument, command in _extract_file_commands(source, INPUT_RE):
        original_path = _resolve_project_tex(argument, project_dir)
        if original_path is None or original_path not in output_paths or output_paths[original_path] is None:
            continue
        target = output_paths[original_path]
        assert target is not None
        relative = os.path.relpath(target, project_dir).replace(os.sep, "/")
        if command == "include":
            relative = str(Path(relative).with_suffix("")).replace(os.sep, "/")
        replacements.append((start, end, relative))

    # \includeonly takes a comma-separated list of names without .tex suffixes.
    for start, end, argument, _command in _extract_file_commands(source, INCLUDEONLY_RE):
        pieces = argument.split(",")
        rewritten: list[str] = []
        changed = False
        for piece in pieces:
            raw = piece.strip()
            original_path = _resolve_project_tex(raw, project_dir)
            target = output_paths.get(original_path) if original_path is not None else None
            if target is not None:
                relative = os.path.relpath(target, project_dir).replace(os.sep, "/")
                relative = str(Path(relative).with_suffix("")).replace(os.sep, "/")
                prefix_len = len(piece) - len(piece.lstrip())
                suffix_len = len(piece) - len(piece.rstrip())
                piece = piece[:prefix_len] + relative + (piece[len(piece) - suffix_len:] if suffix_len else "")
                changed = True
            rewritten.append(piece)
        if changed:
            replacements.append((start, end, ",".join(rewritten)))

    for start, end, value in sorted(replacements, key=lambda item: item[0], reverse=True):
        source = source[:start] + value + source[end:]
    return source


def _ensure_package(source: str) -> str:
    masked = _mask_comments(source)
    if PACKAGE_RE.search(masked):
        return source
    match = DOC_CLASS_RE.search(masked)
    if match:
        return source[:match.end()] + "\n\\usepackage{braidtex}" + source[match.end():]
    return source


def transform_project(
    source: str | Path,
    *,
    output: str | Path | None = None,
    asset_dir: str | Path = "braids",
    cache_dir: str | Path | None = None,
    force: bool = False,
) -> tuple[Path, list[Path], list[Path]]:
    """Preprocess a root document and its literal project-local TeX includes.

    Original .tex files are never modified. Each changed source receives a sibling
    ``*.braidtex.tex`` copy, and parent ``\\input``/``\\include`` commands are
    rewritten to those copies. All assets are located relative to the root project
    directory because TeX resolves ordinary input paths from the compilation cwd.
    Macro-generated include paths and files outside the project are left untouched.
    """
    root_source = Path(source).resolve()
    if not root_source.is_file():
        raise FileNotFoundError(f"LaTeX source file not found: {root_source}")
    project_dir = root_source.parent
    original_text: dict[Path, str] = {}
    children: dict[Path, list[Path]] = {}
    in_progress: set[Path] = set()

    def discover(path: Path) -> None:
        path = path.resolve()
        if path in in_progress:
            raise BraidTransformError(f"Circular literal TeX input detected at {path}")
        if path in original_text:
            return
        in_progress.add(path)
        text = path.read_text(encoding="utf-8")
        original_text[path] = text
        child_paths: list[Path] = []
        for _start, _end, argument, _command in _extract_file_commands(text, INPUT_RE):
            child = _resolve_project_tex(argument, project_dir)
            if child is not None and child != path and child not in child_paths:
                child_paths.append(child)
                discover(child)
        children[path] = child_paths
        in_progress.remove(path)

    discover(root_source)
    root_defaults = _defaults_from_preamble(original_text[root_source])
    output_paths: dict[Path, Path | None] = {}
    generated_assets: list[Path] = []
    transformed_files: list[Path] = []
    any_braid_expression = any(_extract_expressions(text) for text in original_text.values())

    def process(path: Path) -> Path | None:
        path = path.resolve()
        if path in output_paths:
            return output_paths[path]
        for child in children[path]:
            process(child)
        text = original_text[path]
        initial = {} if path == root_source else root_defaults
        transformed, assets = transform_source(
            text,
            source_path=path,
            asset_dir=asset_dir,
            cache_dir=cache_dir,
            force=force,
            project_dir=project_dir,
            initial_defaults=initial,
        )
        generated_assets.extend(assets)
        rewritten = _rewrite_project_inputs(transformed, project_dir, output_paths)
        if path == root_source and any_braid_expression:
            rewritten = _ensure_package(rewritten)
        has_local_markers = bool(_extract_expressions(text) or _extract_defaults(text))
        has_rewritten_child = rewritten != transformed
        if path == root_source or has_local_markers or has_rewritten_child:
            target = Path(output).resolve() if (path == root_source and output is not None) else path.with_name(path.stem + ".braidtex" + path.suffix)
            _atomic_write(target, rewritten)
            output_paths[path] = target
            transformed_files.append(target)
            return target
        output_paths[path] = None
        return None

    root_output = process(root_source)
    assert root_output is not None
    # De-duplicate assets because repeated identical expressions intentionally share
    # a deterministic output file.
    unique_assets = list(dict.fromkeys(generated_assets))
    return root_output, unique_assets, transformed_files


def clean_cache(asset_dir: str | Path, *, project_dir: str | Path = ".", cache_dir: str | Path | None = None) -> int:
    """Remove BraidTeX-managed assets/cache entries only; return file count."""
    root = Path(project_dir).resolve()
    assets = Path(asset_dir)
    if not assets.is_absolute():
        assets = root / assets
    assets = assets.resolve()
    cache = Path(cache_dir) if cache_dir is not None else assets / ".cache"
    if not cache.is_absolute():
        cache = root / cache
    cache = cache.resolve()
    count = 0
    for directory, pattern in ((assets, "bt-*.tikz"), (cache, "bt-*.json")):
        if directory.exists():
            for path in directory.glob(pattern):
                try:
                    path.unlink()
                    count += 1
                except OSError:
                    pass
    return count
