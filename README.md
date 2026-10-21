# BraidTeX

Braid diagrams as ordinary mathematics in LaTeX.  You write

```latex
\[
    f \circ
    \braid{
        \bin{x_1 x_2 x_3}
        \bcr{1}
        \bcr{-2}
        \bout{x_2 x_3 x_1}
    }
    \circ g
\]
```

and `braidtex compile main.tex` produces the PDF.  Strand connectivity, parenthesized
spacing, over/under geometry, vector output, asset management and caching are automatic.

**How it works (important).** TeX cannot run Python, and BraidTeX deliberately does not use
`\write18`/shell escape.  `\braid{...}` is therefore a *preprocessing* construct:
`braidtex` scans the source, validates every braid, renders it once to a TikZ file in
`braids/`, and writes a transformed copy of the source in which each `\braid{...}` is
replaced by `\braidfig{braids/bt-<hash>}`.  An ordinary engine then compiles that copy.
Running plain `pdflatex main.tex` on an unprocessed file does *not* draw braids (it prints a
warning and a placeholder box).  Your original `.tex` files are never modified.

## Requirements and installation

* Python >= 3.9 (no third-party runtime dependencies); TeX Live / MiKTeX with `tikz`,
  `xcolor`, `standalone`; `latexmk` is used when present.  Engines: pdfLaTeX, LuaLaTeX, XeLaTeX.
* `pip install .` (development: `pip install -e .[test]`).
* `braidtex.sty` ships inside the Python package; `braidtex compile` puts it on `TEXINPUTS`.
  For manual runs: `cp "$(braidtex sty)/braidtex.sty" .`
* Do not load the CTAN package `braids` together with `braidtex` (both define `\braid`).

## Quick start

```bash
cd examples/minimal
braidtex compile main.tex        # -> main.pdf, braids/*.tikz, .braidtex-build/
braidtex compile main.tex -v     # show which diagrams were reused / regenerated
```

Preamble: `\usepackage{braidtex}`.  Shortest braid: `$\braid{\bcr{1}}$` (two strands inferred).
Identity on three unlabeled strands: `\braid{\bn{3}}`.

## LaTeX syntax

| command | meaning |
|---|---|
| `\bin{cfg}` | input configuration; infers the number of strands |
| `\bout{cfg}` | output configuration, *validated* against the strand permutation; default = same tree shape with labels permuted |
| `\bn{N}` | strand count for unlabeled braids |
| `\bcr{1 -2 1}` | crossings, top to bottom; `i` = sigma_i, `-i` = its inverse; repeatable |
| `\bcol{1 3}{teal!75!black}` | colour of strands 1 and 3 (strand k = k-th input endpoint); `\bcol{*}{gray}` = main colour; colours follow strands |
| `\bnote{1}{\alpha}` | annotation attached to strand 1 |
| `\blab{in}{a b c}`, `\blab{out}{...}` | *display-only* labels (never checked); `*` hides one |
| `\bax{frame}`, `\bax{h,front}` | reference axes: `h` = horizontal axes with ticks at endpoints; `frame` adds the x=0 arrow and dotted right edge; flags `front`, `noticks` |
| `\bpt{in}{2}{p}` | marked point at input/output endpoint 2 with (possibly empty) label |
| `\bset{key=value,...}` | local options |
| `\bsub{k}{inner}` | replace strand k by an inner braid (cabling; see above) |
| `\braidsetup{key=value,...}` | defaults for all following braids (global from that point on) |
| `\braidid{name}{opts}` | standard identity diagrams (top level, outside `\braid`) |

**Convention.** Words are read top to bottom.  At a positive sigma_i the strand entering from
the *left* passes **over**; the inverse reverses this.

```latex
% colours
\braid{\bin{x_1 x_2 x_3}\bcr{1 2 1}\bcol{1}{teal!75!black}\bcol{2}{orange!90!black}}
\braid{\bin{a b c d}\bset{palette}\bcr{2 1 3}}
% parenthesization decides the layout; no layout option
\braid{\bin{(x_1 x_2) x_3}\bcr{2}\bcr{1}\bout{x_3 (x_1 x_2)}}
```

### Configurations

Whitespace-separated atoms, `( ... )` for structural grouping, `*` for an unlabeled leaf.
`x_1`, `V/W`, `X^{\otimes 2}`, `\frac{A}{B}`, `x_{12}` are single atoms (braces and backslash
commands stay together).  For labels containing parentheses or spaces wrap them: `{V(W)}` or
`\atom{f(x, y)}` (`\frac {A} {B}` with spaces splits; use `\atom{...}`).  The four trees
`x_1 x_2 x_3`, `(x_1 x_2) x_3`, `x_1 (x_2 x_3)`, `(x_1 x_2)(x_3 x_4)` are all different;
redundant wrappers (`(x) y`, `((a b))`) normalize away and the outermost grouping is the
root.  *Omitted* (inferred from the other side or from the word), *empty* `\bin{}` (zero
strands) and *unlabeled* (`\bn{3}`, `* * *`) are three different things.

### Options (`\bset`, `\braidsetup`)

`width`, `height`, `band` (height per crossing, 0.9cm), `pad`, `margin`, `gap` (clearance
around over-strands), `lw` (0.9pt), `labels=both|in|out|none`, `dots`, `sigma` (crossing labels
in the left margin), `palette`, `color`, `fontsize`, `rho`/`wmin` (layout nesting), `inpos={0 .2 1}`,
`outpos=...` (custom normalized endpoint positions).  Lengths accept `cm mm pt in` (default cm).
**Inline use**: diagrams are display-sized; for text use e.g.
`\bset{height=1.2cm,band=0.5cm,labels=none}`.

## Composition, standard identities, little discs (0.2)

```latex
% inner braid replaces strand 2 -- Mode 1 (shadow, default) and Mode 2 (separators)
\braid{\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{1}}\bset{compose=shadow}}
\braid{\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{1}}\bset{compose=separator}}
% little-disc nesting: ((a b) c) = a,b in an inner disc, with c in the outer disc
\braid{\bin{((a b) c)}\bset{discs}}
% standard diagrams
\braidid{ybe}{}   \braidid{far}{}   \braidid{inverse}{}   \braidid{crossings}{}
\braidid{assoc}{}   \braidid{pentagon}{}   \braidid{hexagon}{objects={U V W}}
```

`compose=shadow` shades the replaced strand's whole path (best when it crosses other strands);
`compose=separator` draws two dashed lines beside the inner braid only (best for a "box inside a
strand" reading). Options: `at`, `extent`, `shadowcolor`, `sepstyle`, `sepcolor`, `regionpad`.
Full details, all `\braidid` options and troubleshooting are in **`docs/manual/manual.pdf`**
(source `manual.tex`, regenerated by `docs/manual/make_manual.py`); the feature test document is
`examples/showcase/showcase.pdf`.  See `CHANGELOG.md`.

## VS Code / LaTeX Workshop (and any editor)

`braidtex compile` replaces `latexmk`: add a second tool and make it the default recipe
(`docs/vscode/settings.json` has the complete snippet; your existing lualatexmk recipe stays available
for documents without braids):

```json
{ "name": "braidtex (lualatex)", "command": "braidtex",
  "args": ["compile", "--engine", "lualatex", "--build", "out", "%DOC_EXT%"] }
```
plus `"latex-workshop.latex.outDir": "out"`. Notes:

* `--build out` keeps the PDF, `.aux`, `.log`, `.synctex.gz` in `out/` (as in a latexmk `-outdir=out` recipe);
  the transformed copy of the source is `out/main.tex`. **Edit your original files, never the copies in `out/`.**
* The copy has the **same line numbers** as your source, and SyncTeX entries and log messages are rewritten to
  your original files, so error links and forward search (editor -> PDF) work on your own `main.tex`.
  Double-clicking *on a drawn braid* in the PDF opens its generated asset (`braids/bt-*.tikz`); click the text
  next to it instead.
* `braidtex compile` runs latexmk with `-halt-on-error` (stops at the first error) instead of `-f`.
* Generated diagrams live in `braids/` next to `main.tex` (add it to `.gitignore` or commit it).

## Automatic layout

Gap between adjacent endpoints = `max(rho^d, wmin)`, `d` = depth of their lowest common
ancestor (root = 0), normalized to the diagram width.  Flat sequences are uniform;
`(x_1 x_2) x_3` has a tight pair then a wide gap, `x_1 (x_2 x_3)` the mirror image; deeper
nesting gives tighter clusters; unbalanced trees work.  Input and output layouts are computed
independently from their own trees.

## Geometry

Slot j on level t sits at `in[j] + (out[j]-in[j]) t/B`.  In each band every strand is one
cubic Bezier with vertical tangents (G1 joins) and a common ease function, so two strands
differ by a function linear in the ease: non-swapping strands never meet and swapping strands
cross exactly once.  The picture has exactly `len(word)` crossings for any input/output
spacings.  At each crossing the under-strand is cut (real vector gap of `gap` + line width
from the over-strand, no white masking).  Tests check crossing counts, join continuity and
tangent continuity numerically.

## Python API

```python
from braidtex import Braid, Style, Cache, render_tikz

b = Braid([1, -2], "(x_1 x_2) x_3", colors={1: "teal!75!black"})  # target inferred
b.permutation                       # strand k ends at output slot p[k-1]
Braid(n=3, word=[1, 2, -1])         # unlabeled
Braid([1], "x_1 x_2 x_3", "x_1 x_2 x_3")   # IncompatibleBoundaryError: output endpoint 1 ...
render_tikz(b)                      # also render_standalone, render_svg
Cache("braids").ensure(b, "pdf").path
b.compose(other)                    # vertical composition when boundary trees agree exactly
Braid.from_json(b.to_json())        # JSON round trip; hand-written specs may use strings
```
JSON: `{"word":[1,2],"source":"(a b) c","target":"b (c a)","colors":{"1":"red"},"style":{"width":3.0}}`

## CLI

```
braidtex render --expr '\bin{a b}\bcr{1}' [--format tikz|standalone|svg|pdf] [-o FILE]
braidtex render --json spec.json --format pdf -o fig.pdf
braidtex expr '<latex fragment with \braid{..}>'
braidtex transform main.tex [--check] [--stdout] [--build DIR]
braidtex compile main.tex [--engine pdflatex|lualatex|xelatex] [-f] [-v]
braidtex clean [DIR]
braidtex sty
```
Common: `--assets DIR` (default `<project>/braids`), `-f/--force`, `-v/--verbose`.  Exit status 2 on
invalid input (source problems reported as `file:line:col`), 1 on I/O errors.
Generate a diagram: `render`.  Transform source: `transform`/`expr`.  Standalone figure:
`render --format pdf`.  Whole document: `compile`.

## Build layout, paths, caching

```
proj/main.tex            original, never modified
proj/braids/             bt-<16 hex>.tikz assets (the cache)
proj/.braidtex-build/    transformed copies + aux files; main.pdf copied next to main.tex
```
The engine runs with the project directory as cwd, so relative `\input`, `\includegraphics` and
`.bib` paths keep their meaning (spaces in paths work).  `\input`/`\include`d files containing
braids are transformed too; the build dir is first on `TEXINPUTS`, shadowing originals without
rewriting paths.  Cache key = SHA-256 of the canonical JSON of the resolved spec (trees,
resolved target, colours, style, axes, points) + format + renderer version: equivalent input
shares a key, unrelated text edits never invalidate, any semantic/style change does.  Assets
are written atomically and header-validated on reuse.  `-f` regenerates everything;
`braidtex clean` removes assets and the build dir (foreign files in `braids/` are kept).

## Security

No shell escape is needed or used (`-no-shell-escape`).  The Python side never evaluates source
text; the scanner recognizes only the commands above; colours are restricted to
`[A-Za-z0-9!._-]`.  Labels are ordinary trusted TeX math.

## Tests

`python -m pytest` (194 tests; the example documents are compiled and checked too): semantics against an independent permutation reference, parser, layout
numbers, geometry invariants, transformer diagnostics, cache, CLI, and real pdfLaTeX/LuaLaTeX
builds (paths with spaces, cache reuse/invalidation, source preservation, measured baseline
alignment).  LaTeX tests skip when no engine is installed.

## Limitations

* `\braid` needs the preprocessing step.  `\braidsetup` is global and linear (not TeX-group
  scoped).  Only `\input`/`\include` are followed (not `\subfile`/`\import`).  `\braid` inside
  macro definitions is not supported (the scanner sees source, not expanded macros).
  Bibliography relies on latexmk with `BIBINPUTS` set; untested.
* No automatic scaling to inline text size; each crossing gets its own layer.
* Named/mixed xcolor colours only (no `rgb,255:`).  SVG labels are plain text.
* Axes and points are markers tied to endpoints.  Little-discs configurations, operadic
  composition and a braid-group simplifier are **not** implemented; `compose` is plain vertical
  composition of morphisms with identical boundary trees.
* Extreme width/band choices can make a gap reach the end of its layer (a warning is issued);
  gaps never shrink below `wmin` of the root gap, and a warning is issued below 2.5 mm.
  Visual quality was inspected by eye on the showcase, not by pixel regression.

## Compatibility

No earlier implementation existed in the workspace, so there is nothing to migrate;
`Braid(n=3, word=[1, 2, -1])` works as in the original sketch.
