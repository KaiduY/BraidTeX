# BraidTeX 0.6

BraidTeX is a small Python authoring tool for writing braid diagrams as mathematical notation in LaTeX. It extends the original generator-word renderer with structural endpoint parsing, automatic hierarchical spacing, a source preprocessor, a LaTeX support package, deterministic vector TikZ assets, and a cache.

The recommended workflow is deliberately **preprocess, then compile normally**. BraidTeX does not execute Python from inside TeX and does not require unrestricted shell escape.

## 1. Quick start

Requirements:

- Python 3.10 or later; Python itself has no third-party runtime dependencies.
- A LaTeX installation with TikZ/PGF and `xcolor` (`pdflatex`, `lualatex`, or `xelatex`; `latexmk` is also supported).

Install from this folder:

```bash
python -m pip install -e .
```

Create `main.tex`:

```latex
\documentclass{article}
\usepackage{amsmath}
\usepackage{braidtex}
\begin{document}
\[
  \psi(\alpha) =
  \braid{\btin{(x_1 x_2) x_3}\btcross{1}\btcross{-2}\btout{x_1 (x_2 x_3)}}.
\]
\end{document}
```

Build it with one command:

```bash
braidtex build main.tex
```

Or without installing the console command, run `python braidtex_cli.py build main.tex` from this source directory. The original `main.tex` remains unchanged. The tool writes `main.braidtex.tex`, caches vector TikZ snippets under `braids/`, and creates `main.pdf`.

`\usepackage{braidtex}` loads the helpers and TikZ dependencies. Braid macros intentionally raise an explanatory LaTeX error if compiled without preprocessing. The build command adds the package search path automatically; for a manual compile of a transformed file, install/copy `braidtex.sty` where TeX can find it.

## 2. Public notation

The macro names use the `bt` prefix for component commands to avoid collisions with common LaTeX notation such as `\in` (set membership), `\out`, and `\cross`.

| Command | Meaning |
|---|---|
| `\braid[options]{...}` | Define and render a braid. |
| `\braidexpr[options]{...}` | Alias intended for explicit expressions embedded in ordinary math. |
| `\btbraid[options]{...}` | Alternate main marker if `\braid` is already used by another package. |
| `\btin{configuration}` | Input boundary object and labels. |
| `\btout{configuration}` | Output boundary object and labels. |
| `\btcross{i}` | Add generator \(\sigma_i\); a negative integer means \(\sigma_i^{-1}\). |
| `\btid{n}` | Specify an unlabeled identity braid on `n` strands. |
| `\btcolor{color}` | Set the main/fallback strand color. |
| `\btstrandcolor{i}{color}` | Set the color of the `i`-th input strand; color follows that strand. |
| `\btaxis` | Show the optional horizontal reference axis. |
| `\btpoint{port}{label}` | Put a labeled point on the axis aligned with a 1-based input port; this implies the axis. |
| `\btpointx{x}{label}` | Put a labeled point at an explicit horizontal coordinate `x` (in cm); this implies the axis. |
| `\btannot{strand}{level}{label}` | Annotate a 1-based input-strand identity at an integer crossing level. Levels run from `0` (top) through the number of generators. |
| `\braiddefaults{key=value,...}` | Set document-level defaults for later braids; local options override them. |

Commands can be separated by whitespace or newlines. Every braid body uses the same structured representation in the Python renderer and source transformer.

### Identity braids and inferred arity

For an unlabeled identity, use `\braid{\btid{3}}`. A labeled identity needs no explicit count:

```latex
$\braid{\btin{x_1 x_2 x_3}\btout{x_1 x_2 x_3}}$
```

When an input or output configuration is present, the strand count is inferred from its leaves. Otherwise a nonempty generator word infers the minimum possible arity (`max(abs(i))+1`); use the optional `n=...` option if the intended braid has additional untouched strands.

### Positive and negative crossings

```latex
$\braid{\btin{a b}\btcross{1}\btout{b a}}$

$\braid{\btin{a b}\btcross{-1}\btout{b a}}$
```

Words are read top-to-bottom. Under the default convention, positive `\sigma_i` has the strand entering at position `i` pass over the strand entering at position `i+1`; a negative generator reverses the over/under relation. Set `positive_over=right` to reverse the convention globally or per braid.

## 3. Structural parsing and automatic layout

Configuration labels are parsed into a small abstract syntax tree rather than treated as a single label string.

- `x_1 x_2 x_3` is a flat sequence and receives uniform spacing.
- `(x_1 x_2) x_3` creates a tighter first pair and a wider gap before `x_3`.
- `(x_1 x_2)(x_3 x_4)` creates two clusters.
- `((x_1 x_2) x_3) x_4` creates progressively wider gaps at outer levels.

At each internal node, child widths are allocated recursively. Sibling separation increases with distance from the deepest grouping level. Coordinates are deterministic for fixed configuration and settings. Input and output positions are computed independently. Crossing lanes remain ordered, and smooth, crossing-free fan segments connect the endpoint layouts to the braid's standard lanes, so changing parenthesization does not add crossings to the encoded word.

The parser keeps each atomic label's LaTeX spelling. A label can contain subscripts, superscripts, fractions, macros, and braced groups, for example `x_{12}`, `V/W`, `\mathcal{A}`, or `\frac{A}{B}`. Parentheses at configuration level denote structural grouping. If a label itself contains whitespace or parentheses that should not be interpreted structurally, wrap it in braces, e.g. `{\text{label with spaces}}`.

The outermost configuration parentheses are treated as implicit root parentheses and are not separately drawn, matching the usual parenthesized-braid convention.

### Different input and output configurations

```latex
\[
  \braid{
    \btin{(x_1 x_2) x_3}
    \btcross{1}\btcross{-2}
    \btout{x_1 (x_2 x_3)}
  }
\]
```

The generator word determines strand connectivity and the induced permutation. The specified bottom configuration determines output positions and displayed output labels. The program reports an arity mismatch rather than silently drawing incompatible endpoints.

If `\btout` is omitted but `\btin` is given, labels follow their strands to the bottom, while the output layout defaults to uniform spacing. If `\btout` is supplied, its labels and parenthesization determine the bottom layout independently.

## 4. Colors, axes, and options

Colors are indexed by input-strand identity and move with strands at crossings.

```latex
\braid[scale=0.9,strand_sep=0.9,axis=true,axis_color=gray!60]{
  \btin{(x_1 x_2) x_3}
  \btcross{1}\btcross{-2}
  \btout{x_1 (x_2 x_3)}
  \btstrandcolor{1}{teal!75!black}
  \btstrandcolor{2}{orange!85!black}
  \btstrandcolor{3}{violet!75!black}
  \btaxis\btpoint{2}{p}
  \btpointx{-0.5}{q}
  \btannot{1}{1}{\text{marked strand}}
}
```

Short local options include:

- `color=...`, `scale=...`
- `strand_sep=...`, `layer_height=...`, `identity_height=...`
- `cluster_gap=...`, `group_spacing=...`, `label_offset=...`
- `line_width=...`, `crossing_gap=...`, `background=white` (or `background=none`)
- `dots=true`, `generators=true`
- `positive_over=left|right`
- `input_labels=false`, `output_labels=false` (hide one endpoint label row while retaining its configuration and automatic layout)
- `axis=true|false`, `axis_y=...`, `axis_extent=left:right`, `axis_color=...`, `axis_front=true|false`
- `frame_top=true|false`, `frame_bottom=true|false`, `frame_left=true|false`, `frame_right=true|false`
- `frame_axis_color=...`, `frame_axis_width=...`, `frame_boundary_style={...}`, `frame_boundary_width=...`, `frame_tick_half_height=...`

Legacy compact spellings such as `strandsep`, `layerheight`, `linewidth`, and `axiscolor` are also accepted. Dimensions for endpoint spacing and heights are in centimetres; line widths and crossing gaps are in points. `scale` uniformly scales the TikZ picture. Parenthesization is inferred from configurations; there is no `layout=parenthesized` switch to remember.

Document-level defaults can reduce repetitive styling:

```latex
\braiddefaults{color=blue!70!black,strand_sep=0.85,scale=0.95}
% Later braids inherit those settings; local options override them.
$\braid[ color=red ]{\btin{a b}\btcross{1}}$
```

Defaults are persistent from the point where they appear; they are not scoped by TeX groups. A later `\braiddefaults{...}` updates the settings it mentions.

### Custom endpoint positions

The Python API supports `top_positions=[...]` and `bottom_positions=[...]`, each a strictly increasing list of x-coordinates in centimetres. These override inferred horizontal positions without changing the braid word or strand permutation. This is an advanced Python-side override; ordinary LaTeX syntax deliberately prefers the automatic structural layout.

## 5. Expression transformation, build, and caching

The transformer recognizes only marked constructs: `\braid{...}`, `\braidexpr{...}`, and `\btbraid{...}`. It parses their contents with a deliberately small grammar; all surrounding LaTeX source is left unchanged. It supports multiple diagrams in one equation, nested braces in command arguments, optional braid options, comments, and common literal regions (`\verb`, `verbatim`, `lstlisting`, and `minted`). It does **not** parse arbitrary LaTeX macro expansion or discover implicit braid notation in unmarked mathematics.

### Commands

```bash
# Transform an isolated expression/snippet; TeX is emitted to stdout.
braidtex expr '\braid{\btin{a b}\btcross{1}}'

# Preprocess only: original source is not modified.
braidtex transform main.tex

# Preprocess and compile to main.pdf.
braidtex build main.tex

# Choose another engine.
braidtex build main.tex --engine lualatex

# Force asset regeneration.
braidtex build main.tex --force

# Choose project-local assets or a separate cache metadata folder.
braidtex build main.tex --asset-dir 'generated braids' --cache-dir '.braid-cache'

# Remove only BraidTeX-managed bt-*.tikz assets and matching metadata files.
braidtex clean --project-dir . --asset-dir braids
```

For `transform`, the default result is `main.braidtex.tex`. The generated file includes the cached snippets through `\braidasset{...}`. The original file is unchanged unless you explicitly give it as the output path (not recommended).

The project-aware transformer recursively follows **literal, project-local** `\input{...}` and `\include{...}` paths. When an included file contains braid markup (or relevant local defaults), it creates a sibling `*.braidtex.tex` copy and rewrites the parent to include that copy. It also rewrites literal `\includeonly` entries where needed. Original chapter files remain untouched. Macro-generated paths and sources outside the project root are deliberately not rewritten; preprocess those manually or use literal paths. Defaults declared in the root preamble are inherited by transformed included files; defaults placed later in the document apply only in the file where they appear.

The Python build command runs a normal LaTeX engine after preprocessing. It does not use `--shell-escape`; no Python runs inside LaTeX. The generated `.tikz` snippets are vector graphics compiled into the final PDF by TikZ/PGF. For reproducible diagrams in version control, keep the original `.tex` and the package version fixed; generated assets can be recreated using the cache key.

### Cache design

Each asset is named from a SHA-256 digest over a canonical JSON representation of the normalized braid model, all rendering settings, format identifier, and renderer version. A small metadata JSON file records the key and normalized specification. Asset and metadata writes are atomic; a partially written cache entry will be regenerated. Identical descriptions reuse the same file. Settings or renderer-version changes produce a different key. Use `--force` to regenerate and `clean` to remove managed files.

Assets default to `braids/` within the LaTeX project's directory, not the BraidTeX installation. Relative project paths and directories with spaces are supported by the build CLI.

## 6. Python API and JSON compatibility

The original API remains available:

```python
from braidtex import Braid, Group, from_dict

b = Braid(
    n=3,
    word=[1, -2, 1],
    top_parenthesization=((r"x_1", r"x_2"), r"x_3"),
    bottom_parenthesization=(r"x_1", (r"x_2", r"x_3")),
    strand_colors=["teal!75!black", "orange!85!black", "violet!75!black"],
)
b.write("figures/braid.tikz", format="inline")
b.write("figures/braid-standalone.tex", format="standalone")
```

`Braid.compose(below)` composes the current braid followed by `below`, concatenates generator words in top-to-bottom order, and checks arity plus specified intermediate labels/parenthesizations. Styling follows the strands from the top braid. It raises an error for incompatible explicitly labeled intermediate boundaries.

The legacy JSON renderer remains available:

```bash
python braidtex.py config.json --output braids/one.tikz --format inline
```

Supported output formats for the Python API are `inline`, `picture`, and `standalone`.



## 7. Connectors, coordinate frames, and auxiliary paths

These primitives are independent of the braid word unless noted otherwise:

| Primitive | Meaning | Affects braid topology? |
|---|---|---:|
| `Connector(i, j, level=k)` / `\btconnector[options]{i}{j}{k}` | Horizontal segment attached to persistent strand identities `i` and `j`, at a generator boundary `k`; only the two endpoints get nodes. Intermediate strands are crossed visually without additional nodes. | No |
| `CoordinateFrame(...)` / `\btframe` | Optional top/bottom axes, left arrow, dotted right boundary, and independently selected top/bottom ticks. | No |
| `Separator(k, ticks=...)` / `\btsep[options]{k}` inside a braid | Dotted horizontal separator at level `k`, optionally with its own tick positions. | No |
| `AuxiliaryPath(follow_strand=i, offset=...)` / `\btfollow{i}{offset}` | Dotted or dashed path that follows a persistent strand approximately. | No |
| `AuxiliaryPath(points=..., style=...)` / `\btpath{...}{style}` | Explicit path in diagram coordinates. Coordinates are non-topological annotations. | No |
| `Region(start, end, label)` / `\btregion{start}{end}{label}` | Vertical brace and label tied to generator levels. | No |

Connector and separator commands accept optional local style options. For example, `\btconnector[color=red,nodes=false,line_width=1.1]{1}{4}{2}` hides the two endpoint nodes, while `\btsep[style={densely dotted},ticks={0.5,1.5}]{2}` adds a dotted separator with its own tick locations. The frame itself is independently configurable through the `frame_*` options described above; enable it with `\btframe` or `[frame=true]`.

For example, a connector is attached to *identities*, not to the strands' current left-to-right positions:

```latex
\[
  \braid{
    \btin{a b c d}
    \btcross{1}\btcross{2}\btcross{-1}
    \btconnector{1}{4}{3}
    \btframe
    \btticks{top}{0,0.9,1.8,2.7}
    \btsep{1}
  }
\]
```

The Python API supports independent style controls through `CoordinateFrame`, `Separator`, `Connector`, `AuxiliaryPath`, and `Region`. For example:

```python
from braidtex import Braid
from braidtex_model import (
    AuxiliaryPath, Connector, CoordinateFrame, Region, Separator,
)

b = Braid(
    4, [1, 2, -1],
    connectors=[Connector(1, 4, level=3, nodes=True)],
    frame=CoordinateFrame(
        top_ticks=(0, 0.9, 1.8, 2.7),
        bottom_ticks=(0, 0.9, 1.8, 2.7),
        separators=(Separator(1, ticks=(0.45, 1.35, 2.25)),),
    ),
    auxiliary_paths=[AuxiliaryPath(follow_strand=2, offset=0.14)],
    regions=[Region(0, 1, r"u"), Region(1, 3, r"g", side="right")],
)
```

A connector is an annotation, not a crossing generator. It does not participate in the induced permutation. Explicit `AuxiliaryPath.points` use the diagram's coordinate system and are intentionally not given strand identities; use `follow_strand` when it should be mapped by composition.

## 8. Model-level stacking, strand replacement, and sums

The Python operations work on `Braid` models, not rendered pictures:

```python
from braidtex import Braid
from braidtex_model import Connector
from braidtex_operations import DiagramSum, stack, substitute

upper = Braid(3, [1, -2], connectors=[Connector(1, 3, level=2)])
lower = Braid(3, [-1, 2, 1])
combined = stack(upper, lower, separators=True, labels=(r"u", r"g"), check_labels=False)

outer = Braid(2, [1], connectors=[Connector(1, 2, level=0)])
inner = Braid(2, [-1])
# This outer connector touches the replaced strand. Request one term for each
# possible replacement-strand attachment rather than guessing a single target.
alternatives = substitute(outer, 1, inner, connector_policy="all")
assert isinstance(alternatives, DiagramSum) and len(alternatives) == 2
```

- `Braid.compose(below)` vertically composes two braid words, checks arity and any explicitly specified intermediate labels/parenthesizations, and remaps lower-component connector identities and levels through the upper braid's permutation.
- `stack(*components, separators=True, labels=(...))` composes two or more components and can add dotted separators and named braces. It distributes over `DiagramSum` inputs, preserving term signs.
- `substitute(outer, position, inner)` replaces a 1-based input strand by an `m`-strand braid. The arity becomes `n + m - 1`. The inner word is shifted into the bundle and outer generators are expanded by a **cabling** algorithm, preserving generator signs and the induced permutation.
- If a connector, strand annotation, following auxiliary path, or boundary point is attached to the replaced outer strand, the default is an explicit error. Choose `connector_policy="all"` for separate alternatives, or pass an integer from `1` through the inserted arity to choose one replacement strand.
- `DiagramSum([...], signs=[...])` represents a formal sum of distinct diagram models. Stacking and substitution distribute over the terms rather than joining drawings together.

Composition does not geometrically overlay pre-rendered images. It concatenates/expands the mathematical braid word and remaps decorations against persistent identities. Component-boundary idle gaps and connector offsets are combined in the shared level coordinate system.

### Matching operations in LaTeX

Composite expressions use a small grammar and are compiled by the same `braidtex build` step as ordinary braids:

```latex
% Stack two components, add a dotted separator, and brace the regions.
\[
  \btstack[separators=true,labels={u|g},check_labels=false]{
    \braid{\btin{a b c}\btcross{1}\btcross{-2}}
    \btsep
    \braid{\btin{a b c}\btcross{-1}\btcross{2}}
  }
\]

% Replace input strand 1; expand the attached connector into alternatives.
\[
  \btsubbraid[position=1,connector=all]{
    \btouter{\braid{\btin{a b}\btcross{1}\btconnector{1}{2}{0}}}
    \btinner{\braid{\btin{x_1 x_2}\btcross{-1}}}
  }
\]

% A formal diagram sum. The minus operator means first term minus later terms.
\[
  \btalternatives[operator=-]{
    \braid{\btin{a b}\btcross{1}\btout{b a}}
    \btplus
    \braid{\btin{a b}\btcross{-1}\btout{b a}}
  }
\]
```

`\btstack` accepts `separators=true|false`, `labels={u|g|...}`, and `check_labels=true|false`. `\btsubbraid` accepts `position=<1-based index>` and `connector=error|all|<replacement index>`. `\btalternatives` accepts `operator=+|-`; the first term of a minus sum is positive and subsequent terms are negative. In a stack, `\btsep` separates adjacent component expressions; inside a single `\braid{...}`, `\btsep[style=...,ticks={...}]{k}` draws a styled separator at generator level `k`. `\btconnector` accepts `color`, `line_width`, `node_radius`, `nodes`, `visible`, `offset_down`, and `name` options. The frame axis flags (`frame_top`, `frame_bottom`, `frame_left`, `frame_right`) and frame styling options are active when the frame is enabled.

The Python and TeX interfaces share the same model primitives and operation functions. TeX remains a small well-defined grammar, not a full TeX interpreter.

## 9. Reproducible demonstrations

The source for six reusable example families is in `examples/composition_gallery.py`. It constructs primitive models and model operations, then writes a vector TikZ gallery. Regenerate and compile it with:

```bash
python examples/composition_gallery.py
cd examples
pdflatex -interaction=nonstopmode -halt-on-error composition_gallery.tex
```

The gallery includes smooth shifts and exchanges, connectors with endpoint-only nodes, a tall stack with named regions, strand-replacement connector alternatives, four strands with three connectors and a dotted separator, and repeated crossings with auxiliary dotted trajectories. To test the source-transformer syntax end-to-end, use:

```bash
python braidtex_cli.py build examples/composition_notation.tex
```

This example demonstrates primitive commands, `\btstack`, `\btsubbraid`, and `\btalternatives`; generated TikZ assets are stored in the example project rather than in arbitrary system temporary locations.

## 10. Testing

Run the unit and integration suite:

```bash
python -m pytest -q
```

The suite currently contains 77 tests covering generator semantics, permutations, labels, structural parsing, inferred arity, invalid commands and indices, hierarchical layout, custom endpoint positions, primitive geometry, configurable frame elements, styled connectors and separators, auxiliary paths, regions, stacking, substitution, connector alternatives, source preservation, cache reuse/invalidation and cleanup. When `pdflatex` is available, integration tests compile real documents, including composition syntax and a multi-file project with spaces in both source and asset paths.

A representative compiled document is `examples/minimal.tex`; its PDF is generated by `braidtex build examples/minimal.tex`.

## 11. Mathematical and parser conventions / limitations

- Positive and negative crossings use the documented left-over/right-over convention; this is a convention, not a universal choice across references.
- Strand connectivity is determined by the Artin word. Label strings do not infer hidden crossings or reorder the braid.
- The configuration parser is intentionally small, not a complete LaTeX parser. Structural parentheses are special; protect labels containing whitespace/parentheses in an extra pair of braces.
- LaTeX color expressions and labels are emitted as TeX/TikZ content, so only use trusted document source; the preprocessor does not attempt TeX sanitization.
- The axis is a horizontal reference line in the same diagram coordinate system. `\btpoint{i}{p}` aligns a point with top input port `i` at the configured axis height; it does not model a little disc's radius or the full geometry of an operadic configuration.
- Automatic endpoint spacing is a deterministic hierarchical scheme, not a metric on little-disc configurations. `stack` and `substitute` perform model-level braid-word composition and cabling, but they do not construct actual little 2-disc configurations, compute GRT actions, normalize arbitrary braid words using relations, or simplify isotopies.
- The generated per-diagram format is cached TikZ vector source, rather than one PDF file per diagram. TikZ/PGF includes it as vector paths in the thesis PDF.
