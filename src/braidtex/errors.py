"""Exception hierarchy for BraidTeX."""
from __future__ import annotations


class BraidTeXError(ValueError):
    """Base class for every error raised by BraidTeX."""


class ConfigSyntaxError(BraidTeXError):
    """A boundary configuration such as ``(x_1 x_2) x_3`` could not be parsed."""

    def __init__(self, message: str, text: str = "", pos: int = 0):
        self.message, self.text, self.pos = message, text, pos
        detail = f"{message} (at offset {pos})"
        if text:
            line_start = text.rfind("\n", 0, pos) + 1
            line_end = text.find("\n", pos)
            line = text[line_start: len(text) if line_end < 0 else line_end]
            detail += f"\n    {line}\n    {' ' * (pos - line_start)}^"
        super().__init__(detail)


class BraidValidationError(BraidTeXError):
    """The braid data is mathematically inconsistent."""


class IncompatibleBoundaryError(BraidValidationError):
    """Input/output configurations do not match the braid's strand permutation."""


class TransformError(BraidTeXError):
    """A problem in a LaTeX source file, with location."""

    def __init__(self, message: str, file: str = "<expr>", line: int = 1, col: int = 1):
        self.message, self.file, self.line, self.col = message, file, line, col
        super().__init__(f"{file}:{line}:{col}: {message}")


class BuildError(BraidTeXError):
    """External tool (LaTeX engine) failure."""
