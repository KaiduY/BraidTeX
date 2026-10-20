"""Parser for BraidTeX's small, documented LaTeX braid grammar.

This intentionally is not a general LaTeX parser. It only parses the contents
of a designated ``\\braid{...}``/``\\braidexpr{...}`` expression and leaves all
other LaTeX source untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import re

COMMAND_RE = re.compile(r"\\([A-Za-z]+|.)")


class BraidSyntaxError(ValueError):
    """An error in a supported BraidTeX expression."""


def read_group(source: str, start: int, opening: str = "{", closing: str = "}") -> tuple[str, int]:
    """Read a balanced TeX-like brace/bracket group beginning at ``start``."""
    if start >= len(source) or source[start] != opening:
        raise BraidSyntaxError(f"Expected '{opening}' at character {start + 1}")
    depth = 1
    i = start + 1
    while i < len(source):
        char = source[i]
        if char == "%":
            # TeX comments extend to the end of the line and braces inside them
            # do not participate in argument balancing.
            newline = source.find("\n", i)
            i = len(source) if newline < 0 else newline + 1
            continue
        if char == "\\":
            # Escaped braces/brackets do not affect balancing. Consume a control
            # sequence in one go so \{ is not mistaken for a group delimiter.
            i += 1
            if i < len(source) and source[i].isalpha():
                while i < len(source) and source[i].isalpha():
                    i += 1
            elif i < len(source):
                i += 1
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return source[start + 1:i], i + 1
        i += 1
    raise BraidSyntaxError(f"Unclosed '{opening}' group starting at character {start + 1}")


def read_optional(source: str, pos: int) -> tuple[str | None, int]:
    while pos < len(source) and source[pos].isspace():
        pos += 1
    if pos < len(source) and source[pos] == "[":
        return read_group(source, pos, "[", "]")
    return None, pos


def split_options(text: str | None) -> dict[str, str]:
    """Split comma-separated key=value options while respecting braces."""
    if not text:
        return {}
    pieces: list[str] = []
    start = 0
    brace = 0
    for i, char in enumerate(text):
        if char == "{":
            brace += 1
        elif char == "}":
            brace = max(0, brace - 1)
        elif char == "," and brace == 0:
            pieces.append(text[start:i])
            start = i + 1
    pieces.append(text[start:])
    result: dict[str, str] = {}
    for piece in pieces:
        if not piece.strip():
            continue
        if "=" not in piece:
            raise BraidSyntaxError(f"Expected key=value in braid option {piece.strip()!r}")
        key, value = piece.split("=", 1)
        key, value = key.strip().lower(), value.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", key):
            raise BraidSyntaxError(f"Invalid braid option name {key!r}")
        if key in result:
            raise BraidSyntaxError(f"Braid option {key!r} was specified more than once")
        result[key] = value
    return result


class _ConfigurationParser:
    def __init__(self, text: str):
        self.text = text
        self.i = 0

    def parse(self) -> tuple[Any, ...]:
        result = self._sequence(stop_on_paren=False)
        self._space()
        if self.i != len(self.text):
            raise BraidSyntaxError(f"Unexpected character {self.text[self.i]!r} in configuration")
        if not result:
            raise BraidSyntaxError("A configuration must contain at least one strand label")
        # Parentheses around the entire configuration are implicit root
        # parentheses, not a separately drawn internal group.
        if len(result) == 1 and isinstance(result[0], tuple):
            return result[0]
        return tuple(result)

    def _space(self) -> None:
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1

    def _sequence(self, *, stop_on_paren: bool) -> list[Any]:
        result: list[Any] = []
        while True:
            self._space()
            if self.i >= len(self.text):
                if stop_on_paren:
                    raise BraidSyntaxError("Unclosed parenthesized configuration")
                break
            char = self.text[self.i]
            if char == ")":
                if not stop_on_paren:
                    raise BraidSyntaxError("Unexpected ')' in configuration")
                self.i += 1
                break
            if char == "(":
                self.i += 1
                children = self._sequence(stop_on_paren=True)
                if len(children) < 2:
                    raise BraidSyntaxError("A parenthesized group must contain at least two items")
                result.append(tuple(children))
                continue
            atom = self._atom()
            if not atom:
                raise BraidSyntaxError(f"Expected a label near character {self.i + 1}")
            result.append(atom)
        return result

    def _atom(self) -> str:
        start = self.i
        brace_depth = 0
        while self.i < len(self.text):
            char = self.text[self.i]
            if char == "\\":
                self.i += 1
                if self.i < len(self.text) and self.text[self.i].isalpha():
                    while self.i < len(self.text) and self.text[self.i].isalpha():
                        self.i += 1
                elif self.i < len(self.text):
                    self.i += 1
                continue
            if char == "{":
                brace_depth += 1
                self.i += 1
                continue
            if char == "}":
                brace_depth -= 1
                if brace_depth < 0:
                    raise BraidSyntaxError("Unmatched '}' in an atomic label")
                self.i += 1
                continue
            if brace_depth == 0 and (char.isspace() or char == ")"):
                break
            if brace_depth == 0 and char == "(":
                # Allow common TeX sizing commands such as \left( as part of an
                # atom, but ordinary '(' always starts structural grouping.
                prefix = self.text[start:self.i].rstrip()
                if prefix.endswith(r"\left") or prefix.endswith(r"\big") or prefix.endswith(r"\Big"):
                    self.i += 1
                    continue
                break
            self.i += 1
        atom = self.text[start:self.i].strip()
        if brace_depth != 0:
            raise BraidSyntaxError(f"Unbalanced braces in atomic label {atom!r}")
        return atom


def parse_configuration(text: str) -> tuple[Any, ...]:
    """Parse a whitespace-separated configuration into a nested tuple AST.

    Atoms are kept as the exact LaTeX strings supplied. Parentheses at the
    configuration level encode the parenthesization tree. Use braces around an
    atom that itself contains unprotected spaces or structural parentheses.
    """
    return _ConfigurationParser(text).parse()


def flatten_configuration(tree: Any) -> list[str]:
    if isinstance(tree, (tuple, list)):
        result: list[str] = []
        for child in tree:
            result.extend(flatten_configuration(child))
        return result
    return [str(tree)]


def _strip_comments(text: str) -> str:
    """Blank TeX comments while preserving source offsets and line breaks."""
    chars = list(text)
    i = 0
    while i < len(text):
        if text[i] == "\\":
            i += 1
            if i < len(text) and text[i].isalpha():
                while i < len(text) and text[i].isalpha():
                    i += 1
            elif i < len(text):
                i += 1
            continue
        if text[i] == "%":
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            for j in range(i, end):
                if chars[j] not in "\r\n":
                    chars[j] = " "
            i = end
        else:
            i += 1
    return "".join(chars)


def _parse_bool(name: str, value: str) -> bool:
    lowered = value.lower()
    if lowered in ("true", "yes", "on", "1"):
        return True
    if lowered in ("false", "no", "off", "0"):
        return False
    raise BraidSyntaxError(f"Option {name!r} expects true or false, got {value!r}")


@dataclass
class ParsedBraid:
    n: int | None = None
    word: list[int] = field(default_factory=list)
    input_tree: tuple[Any, ...] | None = None
    output_tree: tuple[Any, ...] | None = None
    options: dict[str, Any] = field(default_factory=dict)
    strand_colors: dict[int, str] = field(default_factory=dict)
    axis: bool = False
    identity_requested: bool = False
    boundary_points: list[dict[str, Any]] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)

    def to_spec(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "word": list(self.word),
            "input_tree": self.input_tree,
            "output_tree": self.output_tree,
            "options": dict(sorted(self.options.items())),
            "strand_colors": dict(sorted(self.strand_colors.items())),
            "axis": self.axis,
            "boundary_points": self.boundary_points,
            "annotations": self.annotations,
        }


def parse_braid_body(
    body: str,
    outer_options: str | None = None,
    default_options: dict[str, str] | None = None,
) -> ParsedBraid:
    """Parse a braid body such as ``\\btin{a b}\\btcross{1}\\btout{a b}``.

    ``default_options`` represent preceding document-level defaults; options on
    this particular ``\\braid`` override them.
    """
    body = _strip_comments(body)
    opts = dict(default_options or {})
    opts.update(split_options(outer_options))
    allowed_options = {
        "n", "color", "scale", "diagram_scale", "strandsep", "strand_sep", "layerheight", "layer_height",
        "identityheight", "identity_height", "linewidth", "line_width", "crossinggap", "crossing_gap",
        "cluster_gap", "cluster-gap", "group_spacing", "group-spacing", "axis", "axisy", "axis_y", "axis-y",
        "axisextent", "axis_extent", "axis-extent", "axiscolor", "axis_color", "axis-color",
        "axisfront", "axis_front", "axis-front", "dots", "endpoint_dots", "generators", "show_generators",
        "inlabels", "outlabels", "input_labels", "output_labels",
        "positiveover", "positive_over", "positive-over", "background", "background_color",
        "labeloffset", "label_offset", "label-offset", "baseline", "include-root-parentheses",
        "include_root_parentheses",
    }
    unknown_opts = set(opts) - allowed_options
    if unknown_opts:
        raise BraidSyntaxError("Unsupported braid option(s): " + ", ".join(sorted(unknown_opts)))

    parsed = ParsedBraid(options={})
    for key, value in opts.items():
        normalized = key.replace("-", "_")
        aliases = {"strandsep": "strand_sep", "layerheight": "layer_height", "identityheight": "identity_height",
                   "linewidth": "line_width", "crossinggap": "crossing_gap", "cluster_gap": "cluster_gap",
                   "group_spacing": "group_spacing", "axisy": "axis_y", "axisextent": "axis_extent",
                   "axiscolor": "axis_color", "axisfront": "axis_front", "positiveover": "positive_over",
                   "labeloffset": "label_offset", "include_root_parentheses": "include_root_parentheses",
                   "diagram_scale": "scale", "endpoint_dots": "dots", "show_generators": "generators",
                   "background_color": "background", "inlabels": "input_labels", "outlabels": "output_labels"}
        normalized = aliases.get(normalized, normalized)
        if normalized in {"n"}:
            try:
                parsed.n = int(value)
            except ValueError as exc:
                raise BraidSyntaxError(f"Option n expects a positive integer, got {value!r}") from exc
        elif normalized in {"axis", "axis_front", "dots", "generators", "include_root_parentheses", "input_labels", "output_labels"}:
            parsed.options[normalized] = _parse_bool(key, value)
        elif normalized == "axis_extent":
            try:
                left, right = value.strip("{}()[]").split(":", 1)
                parsed.options[normalized] = (float(left), float(right))
            except Exception as exc:
                raise BraidSyntaxError("axisextent must have the form left:right, e.g. -1:3") from exc
        elif normalized == "color":
            parsed.options[normalized] = value
        elif normalized == "background":
            parsed.options["background_color"] = None if value.lower() in ("none", "false") else value
        elif normalized == "positive_over":
            parsed.options[normalized] = value
        elif normalized == "baseline":
            parsed.options[normalized] = value
        elif normalized == "axis_color":
            parsed.options[normalized] = value
        else:
            try:
                parsed.options[normalized] = float(value)
            except ValueError as exc:
                raise BraidSyntaxError(f"Option {key!r} expects a numeric value, got {value!r}") from exc

    pos = 0
    seen_singletons: set[str] = set()
    n_commands = 0
    while pos < len(body):
        while pos < len(body) and body[pos].isspace():
            pos += 1
        if pos >= len(body):
            break
        match = COMMAND_RE.match(body, pos)
        if not match or body[pos] != "\\":
            raise BraidSyntaxError(f"Expected a BraidTeX command near body character {pos + 1}: {body[pos:pos+20]!r}")
        command = match.group(1)
        pos = match.end()
        if command in {"btin", "btout", "btcross", "btid", "btcolor", "btstrandcolor", "btpoint", "btpointx", "btannot", "btaxis"}:
            pass
        else:
            raise BraidSyntaxError(f"Unsupported command \\{command} inside \\braid; supported commands are \\btin, \\btout, \\btcross, \\btid, \\btcolor, \\btstrandcolor, \\btaxis, \\btpoint, \\btpointx, and \\btannot")

        # Read a command's mandatory argument(s), with spaces permitted before them.
        args: list[str] = []
        needed = {"btin": 1, "btout": 1, "btcross": 1, "btid": 1, "btcolor": 1,
                  "btstrandcolor": 2, "btpoint": 2, "btpointx": 2, "btannot": 3, "btaxis": 0}[command]
        for _ in range(needed):
            while pos < len(body) and body[pos].isspace():
                pos += 1
            if pos >= len(body) or body[pos] != "{":
                raise BraidSyntaxError(f"Command \\{command} expects {needed} braced argument(s)")
            arg, pos = read_group(body, pos)
            args.append(arg)
        if command in ("btin", "btout", "btaxis"):
            key = {"btin": "input", "btout": "output", "btaxis": "axis"}[command]
            if key in seen_singletons:
                raise BraidSyntaxError(f"Command \\{command} may only appear once")
            seen_singletons.add(key)
        if command == "btin":
            parsed.input_tree = parse_configuration(args[0])
        elif command == "btout":
            parsed.output_tree = parse_configuration(args[0])
        elif command == "btcross":
            try:
                generator = int(args[0].strip())
            except ValueError as exc:
                raise BraidSyntaxError(f"\\btcross expects an integer generator index, got {args[0]!r}") from exc
            if generator == 0:
                raise BraidSyntaxError("A braid generator cannot be 0; use ±1, ±2, ...")
            parsed.word.append(generator)
        elif command == "btid":
            if parsed.n is not None:
                raise BraidSyntaxError("Strand count was specified more than once")
            parsed.identity_requested = True
            try:
                parsed.n = int(args[0].strip())
            except ValueError as exc:
                raise BraidSyntaxError(f"\\btid expects a positive strand count, got {args[0]!r}") from exc
        elif command == "btcolor":
            parsed.options["color"] = args[0].strip()
        elif command == "btstrandcolor":
            try:
                index = int(args[0].strip())
            except ValueError as exc:
                raise BraidSyntaxError("\\btstrandcolor's first argument must be a 1-based strand index") from exc
            if index < 1:
                raise BraidSyntaxError("\\btstrandcolor's strand index must be positive")
            parsed.strand_colors[index] = args[1].strip()
        elif command == "btaxis":
            parsed.axis = True
        elif command == "btpoint":
            try:
                port = int(args[0].strip())
            except ValueError as exc:
                raise BraidSyntaxError("\\btpoint's first argument must be a 1-based input port index") from exc
            if port < 1:
                raise BraidSyntaxError("\\btpoint's port index must be positive")
            parsed.boundary_points.append({"port": port, "label": args[1].strip()})
            parsed.axis = True
        elif command == "btpointx":
            import math
            try:
                x = float(args[0].strip())
            except ValueError as exc:
                raise BraidSyntaxError("\\btpointx's first argument must be a numeric x-coordinate") from exc
            if not math.isfinite(x):
                raise BraidSyntaxError("\\btpointx's x-coordinate must be finite")
            parsed.boundary_points.append({"x": x, "label": args[1].strip()})
            parsed.axis = True
        elif command == "btannot":
            try:
                strand = int(args[0].strip())
                level = int(args[1].strip())
            except ValueError as exc:
                raise BraidSyntaxError("\\btannot expects integer strand and level indices") from exc
            if strand < 1:
                raise BraidSyntaxError("\\btannot strand must be a positive 1-based input-strand index")
            if level < 0:
                raise BraidSyntaxError("\\btannot level must be a non-negative crossing level")
            parsed.annotations.append({"strand": strand, "level": level, "label": args[2].strip()})
        n_commands += 1

    input_n = len(flatten_configuration(parsed.input_tree)) if parsed.input_tree is not None else None
    output_n = len(flatten_configuration(parsed.output_tree)) if parsed.output_tree is not None else None
    if input_n is not None and output_n is not None and input_n != output_n:
        raise BraidSyntaxError(f"Input configuration has {input_n} strands but output configuration has {output_n}")
    inferred = input_n or output_n
    if parsed.n is not None and parsed.n < 1:
        raise BraidSyntaxError("Strand count must be positive")
    if parsed.n is not None and inferred is not None and parsed.n != inferred:
        raise BraidSyntaxError(f"Explicit strand count n={parsed.n} conflicts with configuration arity {inferred}")
    if parsed.n is None:
        if inferred is not None:
            parsed.n = inferred
        elif parsed.word:
            parsed.n = max(abs(g) for g in parsed.word) + 1
        else:
            raise BraidSyntaxError("Cannot infer the arity of an empty braid; add \\btin{...}, \\btout{...}, or \\btid{n}")
    if parsed.identity_requested and parsed.word:
        raise BraidSyntaxError("\\btid declares an identity braid and cannot be combined with crossings; use [n=...] to set arity on a non-identity braid")
    for generator in parsed.word:
        if abs(generator) >= parsed.n:
            raise BraidSyntaxError(f"Generator {generator} is invalid for n={parsed.n}; require 1 <= |i| < n")
    for index in parsed.strand_colors:
        if index > parsed.n:
            raise BraidSyntaxError(f"Color override references strand {index}, but the braid has n={parsed.n}")
    for point in parsed.boundary_points:
        if "port" in point and point["port"] > parsed.n:
            raise BraidSyntaxError(f"Boundary point port {point['port']} exceeds strand count n={parsed.n}")
    for annotation in parsed.annotations:
        if annotation["strand"] > parsed.n:
            raise BraidSyntaxError(f"Annotation strand {annotation['strand']} exceeds strand count n={parsed.n}")
        if annotation["level"] > len(parsed.word):
            raise BraidSyntaxError(f"Annotation level {annotation['level']} exceeds {len(parsed.word)} crossing levels")
    return parsed
