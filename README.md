# BraidTeX 0.3

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

## 7. Testing

Run the unit and integration suite:

```bash
python -m unittest discover -s tests -v
```

The suite currently contains 46 tests covering generator semantics, permutations, labels, structural parsing, inferred arity, invalid commands and indices, hierarchical layout, custom endpoint positions, composition (including annotations), axis/point output, source preservation, multiple markers, cache reuse/invalidation and cleanup. When `pdflatex` is available, integration tests compile real documents, including a multi-file project with spaces in both source and asset paths.

A representative compiled document is `examples/minimal.tex`; its PDF is generated by `braidtex build examples/minimal.tex`.

## 8. Mathematical and parser conventions / limitations

- Positive and negative crossings use the documented left-over/right-over convention; this is a convention, not a universal choice across references.
- Strand connectivity is determined by the Artin word. Label strings do not infer hidden crossings or reorder the braid.
- The configuration parser is intentionally small, not a complete LaTeX parser. Structural parentheses are special; protect labels containing whitespace/parentheses in an extra pair of braces.
- LaTeX color expressions and labels are emitted as TeX/TikZ content, so only use trusted document source; the preprocessor does not attempt TeX sanitization.
- The axis is a horizontal reference line in the same diagram coordinate system. `\btpoint{i}{p}` aligns a point with top input port `i` at the configured axis height; it does not model a little disc's radius or the full geometry of an operadic configuration.
- Automatic endpoint spacing is a deterministic hierarchical scheme, not a metric on little-disc configurations. It does not compute the little 2-discs operad's composition, GRT actions, braid relations, or isotopy simplification. `Braid.compose` composes braid words only.
- The generated per-diagram format is cached TikZ vector source, rather than one PDF file per diagram. TikZ/PGF includes it as vector paths in the thesis PDF.
