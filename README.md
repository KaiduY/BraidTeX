# BraidTeX

BraidTeX is a compact mathematical authoring system for braid diagrams.
It provides a Python core for braid semantics, a parser for flat and parenthesized endpoint configurations, SVG rendering, and a lightweight LaTeX-style transformation interface for embedding braid notation in ordinary mathematical text.

## What is implemented

- Structured braid model with strand count, generator word, endpoint configurations, and induced permutation
- Flat and parenthesized configuration parsing using a structural tree representation
- SVG vector rendering for inline and standalone use
- A LaTeX-oriented command format for braid expressions such as `\braid{\bin{x_1 x_2 x_3} \bcr{1} \bout{x_2 x_3 x_1}}`
- A small CLI and Python API for rendering and transforming TeX snippets

## Installation

```bash
cd /path/to/BraidTeX
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Python API

```python
from braidtex import Braid, parse_config, render_svg

braid = Braid(
    n=3,
    word=[1, -2, 1],
    input_config=parse_config("x_1 x_2 x_3"),
    output_config=parse_config("x_2 x_3 x_1"),
)

svg = render_svg(braid)
print(svg[:60])
```

## LaTeX-style transformation

```python
from braidtex import transform_tex

source = r"f \circ \braid{\bin{x_1 x_2 x_3} \bcr{1} \bout{x_2 x_3 x_1}} \circ g"
print(transform_tex(source))
```

This replaces the recognized braid expression with the generated SVG markup.

## CLI

```bash
braidtex render --n 3 --word "1,-2" --input "x_1 x_2 x_3" --outfile braid.svg
braidtex transform example.tex --output example.transformed.tex
```

## Current scope and limitations

This project intentionally keeps the core reliable and modular:

- It supports arbitrary finite braid words over Artin generators with validation for strand count.
- It handles flat and parenthesized endpoint configurations in a structured way.
- It renders to SVG and inline TeX substitution, rather than attempting a full LaTeX compiler integration.
- It does not yet provide an advanced operadic layout engine or a complete TikZ backend.

## Example

```tex
\[
  f \circ
  \braid{
    \bin{x_1 x_2 x_3}
    \bcr{1}
    \bout{x_2 x_3 x_1}
  }
  \circ g
\]
```

This is the target authoring style for everyday mathematical use.
