from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConfigurationNode:
    kind: str
    label: Optional[str] = None
    children: list["ConfigurationNode"] = field(default_factory=list)

    @property
    def arity(self) -> int:
        return len(self.leaf_labels)

    @property
    def leaf_labels(self) -> list[str]:
        if self.kind == "leaf":
            return [self.label or ""]
        labels: list[str] = []
        for child in self.children:
            labels.extend(child.leaf_labels)
        return labels

    @property
    def is_flat(self) -> bool:
        return self.kind == "group" and all(child.kind == "leaf" for child in self.children)

    def __str__(self) -> str:
        if self.kind == "leaf":
            return self.label or ""
        if not self.children:
            return "()"
        return "(" + " ".join(str(child) for child in self.children) + ")" if len(self.children) > 1 else str(self.children[0])


@dataclass
class Configuration:
    root: ConfigurationNode
    raw: str = ""

    @property
    def arity(self) -> int:
        return self.root.arity

    @property
    def leaf_labels(self) -> list[str]:
        return self.root.leaf_labels

    @property
    def is_flat(self) -> bool:
        return self.root.is_flat

    def __str__(self) -> str:
        return self.raw or str(self.root)


class BraidValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Crossing:
    index: int
    generator: int
    sign: int
    left_index: int
    right_index: int


@dataclass
class Braid:
    n: int
    word: list[int] = field(default_factory=list)
    input_config: Optional[Configuration] = None
    output_config: Optional[Configuration] = None
    colors: dict[int, str] = field(default_factory=dict)
    style: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.n <= 0:
            raise BraidValidationError("A braid must have at least one strand.")
        self.word = [int(g) for g in self.word]
        for g in self.word:
            if g == 0:
                raise BraidValidationError("Generator 0 is not valid. Use 1, -1, 2, -2, ...")
            if abs(g) >= self.n:
                raise BraidValidationError(
                    f"Generator {g} is invalid for a braid with {self.n} strands: valid indices are in [-{self.n - 1}, {self.n - 1}] except 0."
                )
        if self.input_config is None:
            self.input_config = parse_config(" ".join(f"x_{i + 1}" for i in range(self.n)))
        if self.output_config is None:
            self.output_config = self.input_config
        if self.input_config.arity != self.n:
            raise BraidValidationError(
                f"Input configuration arity {self.input_config.arity} does not match braid strand count {self.n}."
            )
        if self.output_config.arity != self.n:
            raise BraidValidationError(
                f"Output configuration arity {self.output_config.arity} does not match braid strand count {self.n}."
            )

    @property
    def crossings(self) -> list[Crossing]:
        order = list(range(self.n))
        crossings: list[Crossing] = []
        for position, g in enumerate(self.word):
            idx = abs(g) - 1
            if idx < 0 or idx >= self.n - 1:
                raise BraidValidationError(f"Generator {g} is out of range for {self.n} strands.")
            left = order[idx]
            right = order[idx + 1]
            crossings.append(
                Crossing(
                    index=position,
                    generator=g,
                    sign=1 if g > 0 else -1,
                    left_index=left,
                    right_index=right,
                )
            )
            order[idx], order[idx + 1] = order[idx + 1], order[idx]
        return crossings

    @property
    def permutation(self) -> list[int]:
        order = list(range(self.n))
        for g in self.word:
            idx = abs(g) - 1
            if idx < 0 or idx >= self.n - 1:
                raise BraidValidationError(f"Generator {g} is out of range for {self.n} strands.")
            order[idx], order[idx + 1] = order[idx + 1], order[idx]
        return order

    @property
    def is_identity(self) -> bool:
        return self.permutation == list(range(self.n))

    @classmethod
    def from_word(cls, n: int, word: list[int], **kwargs) -> "Braid":
        return cls(n=n, word=word, **kwargs)

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "word": self.word,
            "input_config": str(self.input_config or ""),
            "output_config": str(self.output_config or ""),
            "colors": {str(k): v for k, v in self.colors.items()},
        }

    def render_svg(self, **kwargs) -> str:
        from .render import render_svg

        return render_svg(self, **kwargs)


def _parse_sequence(text: str, start: int = 0, stop_on_closing: bool = False) -> tuple[ConfigurationNode, int]:
    children: list[ConfigurationNode] = []
    buffer: list[str] = []
    i = start

    while i < len(text):
        ch = text[i]
        if ch == "(":
            if buffer:
                children.append(ConfigurationNode(kind="leaf", label="".join(buffer).strip()))
                buffer.clear()
            nested, i = _parse_sequence(text, i + 1, stop_on_closing=True)
            children.append(nested)
            continue
        if ch == ")":
            if stop_on_closing:
                if buffer:
                    children.append(ConfigurationNode(kind="leaf", label="".join(buffer).strip()))
                    buffer.clear()
                if not children:
                    return ConfigurationNode(kind="group", children=[]), i + 1
                if len(children) == 1:
                    return children[0], i + 1
                return ConfigurationNode(kind="group", children=children), i + 1
            raise ValueError(f"Unmatched closing parenthesis in configuration: {text!r}")
        if ch.isspace() and not stop_on_closing:
            if buffer:
                children.append(ConfigurationNode(kind="leaf", label="".join(buffer).strip()))
                buffer.clear()
            i += 1
            continue
        if ch.isspace() and stop_on_closing:
            if buffer:
                children.append(ConfigurationNode(kind="leaf", label="".join(buffer).strip()))
                buffer.clear()
            i += 1
            continue
        buffer.append(ch)
        i += 1

    if stop_on_closing:
        raise ValueError(f"Unterminated group in configuration: {text!r}")

    if buffer:
        children.append(ConfigurationNode(kind="leaf", label="".join(buffer).strip()))
    if not children:
        return ConfigurationNode(kind="group", children=[]), i
    if len(children) == 1:
        return children[0], i
    return ConfigurationNode(kind="group", children=children), i


def parse_config(expr: str) -> Configuration:
    text = (expr or "").strip()
    if not text:
        return Configuration(root=ConfigurationNode(kind="group", children=[]), raw=text)
    root, end = _parse_sequence(text)
    if end != len(text):
        raise ValueError(f"Could not parse configuration {expr!r}")
    return Configuration(root=root, raw=text)
