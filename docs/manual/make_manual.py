#!/usr/bin/env python3
"""Generate manual.tex.  Every example is written once: the same string is typeset as a
listing *and* used as live braid code, so the two can never disagree."""
from pathlib import Path

OUT = Path(__file__).with_name("manual.tex")
parts = []


def T(s):                       # prose
    parts.append(s.strip("\n") + "\n")


def EX(code, note=None, display=True):
    """Listing + rendered result."""
    code = code.strip("\n")
    parts.append("\\begin{lstlisting}\n" + code + "\n\\end{lstlisting}\n")
    parts.append("\\begin{exresult}\n" + ("\\[\n" + code + "\n\\]" if display else code) +
                 "\n\\end{exresult}\n")
    if note:
        parts.append(note.strip() + "\n")


def LST(code, lang="bash"):
    parts.append(f"\\begin{{lstlisting}}[language={{}},style=plain]\n{code.strip(chr(10))}\n"
                 "\\end{lstlisting}\n")


T(r"""
\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage[margin=2.4cm]{geometry}
\usepackage{booktabs,longtable,enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{listings}
\usepackage{braidtex}

\lstdefinestyle{plain}{basicstyle=\ttfamily\small,frame=single,framerule=0.3pt,
  backgroundcolor=\color{black!4},breaklines=true,columns=fullflexible,
  xleftmargin=0pt,aboveskip=6pt,belowskip=2pt,rulecolor=\color{black!35}}
\lstset{style=plain}
\newenvironment{exresult}{\begin{center}\vspace{-2pt}}{\end{center}\vspace{-2pt}}
\newcommand{\cs}[1]{\texttt{\textbackslash #1}}
\newcommand{\opt}[1]{\texttt{#1}}
\setlength{\parskip}{4pt}\setlength{\parindent}{0pt}\setlength{\emergencystretch}{3em}
\braidsetup{lw=0.9pt}

\title{\textbf{BraidTeX} --- User Manual\\[2pt]\large Braid and little-disc diagrams as ordinary mathematics}
\author{version 0.4.0}
\date{}

\begin{document}
\maketitle
\tableofcontents
""")

# ------------------------------------------------------------------------------------------
T(r"""
\section{What BraidTeX does}
BraidTeX turns a few lines of LaTeX into a braid diagram inside your formula:
""")
EX(r"""
f \circ \braid{ \bin{x_1 x_2 x_3} \bcr{1} \bcr{-2} \bout{x_2 x_3 x_1} } \circ g
""", r"""
Strand connectivity, spacing (from parentheses), crossings with clean vector gaps, colours, labels, caching
and the TikZ output are generated for you. Everything is \emph{vector} graphics.

\paragraph{How it works --- read this once.}
TeX cannot run programs, and BraidTeX does not use shell escape. \cs{braid\{...\}} is therefore a
\emph{preprocessing} construct: the command \opt{braidtex compile main.tex} scans your source, validates every
braid, draws each one into a small TikZ file under \opt{braids/}, writes a transformed \emph{copy} of your
source in which each \cs{braid\{...\}} is replaced by \cs{braidfig\{braids/bt-<hash>\}}, and runs
LaTeX on the copy. Your original files are never modified. Running plain \opt{pdflatex} on an unprocessed
file prints a warning and a placeholder box instead of the diagram.
""")

# ------------------------------------------------------------------------------------------
T(r"""
\section{Installation and basic setup}
\subsection{Requirements}
Python $\ge 3.9$ (no third-party packages), a TeX distribution with \opt{tikz}, \opt{xcolor} and
\opt{standalone}; \opt{latexmk} is used if present. Engines: pdfLaTeX, LuaLaTeX, XeLaTeX.
\subsection{Install}
""")
LST(r"""
pip install .                 # from the BraidTeX directory   (pip install -e .[test] to develop)
braidtex --version
""")
T(r"""
\subsection{VS Code / LaTeX Workshop}\label{sec:vscode}
Add a tool that runs \opt{braidtex compile} and make it the default recipe (the complete snippet is in
\opt{docs/vscode/settings.json}; your latexmk recipe stays available for documents without braids):
""")
LST(r"""
"latex-workshop.latex.tools": [
  { "name": "braidtex (lualatex)", "command": "braidtex",
    "args": ["compile", "--engine", "lualatex", "--build", "out", "%DOC_EXT%"], "env": {} }
],
"latex-workshop.latex.recipes": [ { "name": "braidtex (lualatex)", "tools": ["braidtex (lualatex)"] } ],
"latex-workshop.latex.recipe.default": "braidtex (lualatex)",
"latex-workshop.latex.outDir": "out"
""")
T(r"""
\opt{--build out} keeps PDF, \opt{.aux}, \opt{.log} and \opt{.synctex.gz} in \opt{out/}; the transformed copy of
your source is \opt{out/main.tex}. \textbf{Always edit your original files.} The copy has the \emph{same line
numbers} as your source, and SyncTeX data and error messages are rewritten to point at the originals, so error
links and forward search work on your own \opt{main.tex}. Double-clicking \emph{on a drawn braid} in the PDF
opens its generated asset (\opt{braids/bt-*.tikz}); click the surrounding text instead. The tool passes
\opt{-halt-on-error} (the first error stops the build) rather than \opt{-f}.
""")
T(r"""
\subsection{A first document}
Save this as \opt{main.tex} in any directory (it may live outside the BraidTeX directory; paths with
spaces are fine):
""")
LST(r"""
\documentclass{article}
\usepackage{amsmath}
\usepackage{braidtex}          % the only thing to add to the preamble
\begin{document}
\[ f \circ \braid{\bin{x_1 x_2 x_3}\bcr{1}\bcr{-2}\bout{x_2 x_3 x_1}} \circ g \]
\end{document}
""")
LST(r"""
braidtex compile main.tex        # -> main.pdf  (assets in braids/, aux files in .braidtex-build/)
braidtex compile main.tex -v     # show which diagrams were generated / reused
braidtex transform main.tex      # only preprocess; the result is in .braidtex-build/main.tex
braidtex clean                   # delete braids/ and .braidtex-build/
""")
T(r"""
\paragraph{Files.} The engine runs with your project directory as working directory, so relative
\cs{input}, \cs{includegraphics} and bibliography paths keep working. Files included with \cs{input} or
\cs{include} are transformed too. Unchanged diagrams are \emph{reused} from \opt{braids/} on the next run
(the cache key covers every property that affects the drawing); change one braid and only that one is redrawn.
To run \opt{pdflatex} yourself, copy the style file once: \opt{cp "\$(braidtex sty)/braidtex.sty" .}
""")

# ------------------------------------------------------------------------------------------
T(r"""
\section{Drawing individual braids}
All commands live inside \cs{braid\{...\}}; they are short and independent. Commands:
\begin{center}\small
\begin{tabular}{@{}lp{10.2cm}@{}}\toprule
\cs{bin\{cfg\}} & input configuration (labels and parentheses); infers the number of strands\\
\cs{bout\{cfg\}} & output configuration, \emph{validated} against the braid; optional\\
\cs{bn\{N\}} & strand count for unlabeled braids\\
\cs{bcr\{1 -2 1\}} & crossings, top to bottom; $i=\sigma_i$, $-i=\sigma_i^{-1}$ (may be repeated)\\
\cs{bcol\{ids\}\{color\}} & colour of the given strands; \cs{bcol\{*\}\{c\}} sets the main colour\\
\cs{bnote\{k\}\{tex\}} & annotation attached to strand $k$\\
\cs{blab\{in|out\}\{labels\}} & display-only labels (never checked); \opt{*} hides one\\
\cs{bax\{frame\}} / \cs{bax\{h\}} & reference axes\\
\cs{bpt\{in|out\}\{k\}\{label\}} & marked point at endpoint $k$\\
\cs{bsub\{k\}\{inner\}} & replace strand $k$ by an inner braid (Section~\ref{sec:compose})\\
\cs{bset\{key=value,...\}} & local options (Section~\ref{sec:custom})\\
\cs{braidsetup\{key=value,...\}} & defaults for all following braids\\
\cs{braidid\{name\}\{options\}} & standard identities (Section~\ref{sec:ident})\\
\bottomrule\end{tabular}\end{center}

\subsection{Crossings and the convention}
Words are read \textbf{top to bottom}. At a positive $\sigma_i$ the strand entering from the \emph{left}
passes \textbf{over}; $\sigma_i^{-1}$ reverses this. Strand $k$ is the $k$-th input endpoint and keeps its
identity (and colour) through all crossings.
""")
EX(r"""
\braid{\bin{a b}\bcr{1}} \qquad \braid{\bin{a b}\bcr{-1}} \qquad
\braid{\bin{x_1 x_2 x_3}\bcr{1 -2 1 2}}
""")
T(r"""
\subsection{Identity, unlabeled and inferred braids}
The number of strands is inferred from \cs{bin}, \cs{bout} or the crossings. \emph{Omitted}, \emph{empty} and
\emph{unlabeled} are different: \cs{bn\{3\}} (or \opt{* * *}) is three unlabeled strands; \cs{bin\{\}} is the
empty configuration (zero strands); an omitted \cs{bin} is inferred from the rest (crossings only: $\max|i|+1$).
""")
EX(r"""
\braid{\bn{3}} \qquad \braid{\bin{x_1 x_2 x_3}} \qquad \braid{\bcr{1}} \qquad \braid{\bin{(* *) *}\bcr{2}}
""")
T(r"""
\subsection{Output configurations are checked}
Labels follow the strands. \cs{bout} states the expected output and is \emph{validated}: a wrong output is an
error, never a misleading picture. To change only what is \emph{shown} use \cs{blab}.
""")
EX(r"""
\braid{\bin{x_1 x_2 x_3}\bcr{1}\bcr{2}\bout{x_2 x_3 x_1}} \qquad
\braid{\bin{x_1 x_2}\bcr{1}\blab{in}{a b}\blab{out}{\beta \alpha}}
""", r"""
A mismatch such as \cs{bout\{x\_1 x\_2 x\_3\}} after \cs{bcr\{1\}} stops the build with
\opt{main.tex:12:5: output endpoint 1 is labeled 'x\_1' but the strand arriving there ... is 'x\_2'}.
""")
T(r"""
\subsection{Colours}
Colours are TikZ/xcolor expressions such as \opt{teal!75!black}. They follow strands through crossings.
\cs{bset\{palette\}} applies a default colour scheme; \cs{bcol\{*\}\{c\}} sets the main colour.
""")
EX(r"""
\braid{\bin{x_1 x_2 x_3}\bcr{1 2 1}\bcol{1}{teal!75!black}\bcol{2 3}{orange!90!black}} \qquad
\braid{\bin{a b c d}\bset{palette}\bcr{2 1 3}} \qquad
\braid{\bin{a b}\bcr{1}\bcol{*}{gray}}
""")
T(r"""
\subsection{Parentheses decide the layout}
Whitespace separates atoms; parentheses group. No layout option is needed: gap between neighbouring endpoints
is $\max(\rho^d,w_{\min})$ with $d$ the depth of their lowest common ancestor (flat configurations are
uniform; nesting gives tighter clusters). Input and output are laid out \emph{independently}.
""")
EX(r"""
\braid{\bin{x_1 x_2 x_3}} \quad \braid{\bin{(x_1 x_2) x_3}} \quad \braid{\bin{x_1 (x_2 x_3)}} \quad
\braid{\bin{(x_1 x_2)(x_3 x_4)}} \quad \braid{\bin{((x_1 x_2) x_3) x_4}}
""")
EX(r"""
\braid{\bin{(x_1 x_2) x_3}\bcr{2 1}\bout{x_3 (x_1 x_2)}} \qquad
\braid{\bin{(a b)(c d)}\bcr{2}\bout{a (c b) d}\bset{width=3.6cm}}
""", r"""
\paragraph{Labels with parentheses or spaces.} \opt{x\_1}, \opt{V/W}, \opt{X\^{}\{\textbackslash otimes 2\}},
\opt{\textbackslash frac\{A\}\{B\}}, \opt{x\_\{12\}} are single atoms. Wrap anything ambiguous:
\opt{\{V(W)\}} or \cs{atom\{f(x, y)\}}. (\opt{\textbackslash frac \{A\} \{B\}} with spaces splits; use \cs{atom}.)
""")
T(r"""
\subsection{Large or infinite braids: gaps (\opt{...}) and unlabeled strands (\opt{*})}\label{sec:gaps}
A configuration may contain \opt{...} (also \opt{\textbackslash dots}, \opt{\textbackslash cdots},
\opt{\textbackslash ldots}) wherever any number of further strands are omitted: BraidTeX draws rows of dots there.
A strand marked \opt{*} is \emph{unlabeled}; labeled and unlabeled strands and gaps can be mixed freely, in
groups too (\opt{(a ... b) * c}).

\paragraph{A gap is a position.} In words, colours, notes and points a gap counts as \emph{one position}, exactly
like a strand, because it is an invisible placeholder strand: in \opt{x\_1 ... x\_n} the positions are
$1,2,3$, so \cs{bcr\{1 2\}} lets $x_1$ pass over the omitted strands (position~2) and then over $x_n$. The output
configuration follows from the word as always: here \opt{... x\_n x\_1}; a wrong \cs{bout} is an error. Positions of
gaps cannot carry colours, notes or marked points.
""")
EX(r"""
\braid{\bin{x_1 ... x_n}} \quad \braid{\bin{x_1 ... x_n}\bcr{1 2}} \quad
\braid{\bin{... x_i x_j ...}\bcr{2}} \quad \braid{\bin{x_1 * y ... z}\bcr{2 3}}
""", r"""
In the last diagram the strand $x_1$ and an unlabeled strand are mixed with a gap.
""")
T(r"""
\paragraph{Aligned dots.} The rows of dots are placed at heights shared by \emph{all} gaps of a diagram (so
they line up), each row is centred on its gap, and every row is moved up or down until no dot comes close to a
strand. If two gaps appear (for instance the middle of a big braid), their dots are aligned automatically.
""")
EX(r"""
\braid{\bin{... x_1 ... x_i x_j ... x_n ...}\bcr{4 3 2 -2 -3 -4}\bset{palette}}
""")
T(r"""
\paragraph{Strands crossing a gap.} A strand that passes over (or under) the omitted strands is simply a strand
crossing the gap position. With \opt{gapthrough=solid} (default) it is drawn as usual; with
\opt{gapthrough=dotted} it turns dotted while it is inside the region of the dots, as if it were one of the
omitted strands. The dots always keep a distance from every strand. The twist below winds $x_n$ around $x_1$
across the dots.
""")
EX(r"""
\braid{\bin{x_1 ... x_n}\bcr{-2 -1 -1 2}} \quad
\braid{\bin{x_1 ... x_n}\bcr{-2 -1 -1 2}\bset{gapthrough=dotted}} \quad
\braid{\bin{x_1 ... x_n}\bcr{-2 -1 -1 2}\bset{gapthrough=dotted,geometry=natural}}
""")
T(r"""
\begin{center}\small\begin{tabular}{@{}lp{10.5cm}@{}}\toprule
\opt{gapdots} & dots per row (1--9, default 3)\\
\opt{gaprows} & \opt{auto} (about one row per 1.5\,cm of height) or a number of rows\\
\opt{gapthrough} & \opt{solid} or \opt{dotted}: how a strand looks inside a gap region\\
\opt{gapcolor} & colour of the dots (default black)\\
\opt{gapspan} & extra width next to a gap (default 1)\\
\bottomrule\end{tabular}\end{center}
Gaps work with every other feature: both geometries, shadow/separator marks (a gap inside an inner braid is part
of the ribbon), discs (a gap has no disc of its own but sits inside the discs of its group), axes (no tick at a
gap), colours, identities. For a labeled strand that \emph{displays} dots, use \cs{atom\{\textbackslash vdots\}} or
another spelling that is not \opt{...}/\opt{\textbackslash dots}/\opt{\textbackslash cdots}/\opt{\textbackslash ldots}.
""")
EX(r"""
\braid{\bin{(a ... b) c ... d}\bcr{3 4}\bset{discs,width=5cm}} \qquad
\braid{\bin{x y z}\bcr{1 2}\bsub{2}{\bin{a ... b}\bcr{1 2}}\bset{compose=shadow}}
""")
T(r"""
\subsection{Axes, marked points, annotations, crossing labels}
\cs{bax\{h\}} draws two horizontal axes with ticks at the endpoints; \cs{bax\{frame\}} adds the vertical arrow
and dotted right edge; flags \opt{front}, \opt{noticks}. \cs{bpt} marks an endpoint; \cs{bnote} attaches a
label to a strand; \cs{bset\{sigma\}} labels the crossings in the left margin.
""")
EX(r"""
\braid{\bin{1 2 3}\bcr{1 -2}\bax{frame}\bpt{in}{2}{}\bpt{out}{3}{p}} \qquad
\braid{\bin{x_1 x_2}\bcr{1}\bax{h,front}} \qquad
\braid{\bin{a b c}\bcr{1 2}\bnote{1}{\gamma}\bcol{1}{red}\bset{sigma}}
""", r"""
Axes and points are \emph{markers} tied to endpoints; they do not by themselves define a little-discs
configuration (Section~\ref{sec:discs}).
""")
T(r"""
\subsection{Inline use}
Diagrams are display-sized by default. For text use the \opt{inline} preset (a compact band height, spacing,
line width and font) and usually \opt{labels=none}; the diagram's centre sits on the math axis.
""")
EX(r"""
$\sigma_1 = \braid{\bin{a b}\bcr{1}\bset{inline,labels=none}}$, \quad
$\mathrm{id}_2 = \braid{\bn{2}\bset{inline}}$, \quad
$\sigma_1\sigma_2\sigma_1 = \braid{\bin{a b c}\bcr{1 2 1}\bset{inline,labels=none}}$
""", display=False)

# ------------------------------------------------------------------------------------------
T(r"""
\section{Composition: an inner braid replaces a strand}\label{sec:compose}
\cs{bsub\{k\}\{...\}} replaces strand $k$ of the outer braid by an inner braid. Mathematically the strand is
\emph{cabled}: it becomes $m$ parallel strands (a \emph{ribbon}) that cross other strands as one block, and the
inner braid is inserted into the ribbon. The boundary configurations of the result are those of the outer
braid with the leaf for strand $k$ replaced by the inner configuration (so $x\,y\,z$ with $y\leftarrow(a\,b)$
becomes $x\,(a\,b)\,z$). Strand identities of the result: $1..k{-}1$ unchanged, the ribbon $k..k{+}m{-}1$, later
strands shifted by $m{-}1$. The inner braid accepts \cs{bin}, \cs{bout}, \cs{bn}, \cs{bcr}, \cs{bcol}; it is
validated like any braid. Several \cs{bsub} may be used in one braid (they refer to outer strand numbers).

Two \textbf{explicit modes} mark the replaced strand; both are chosen with \cs{bset\{compose=...\}} or globally
with \cs{braidsetup}:
\begin{description}[leftmargin=1.2em,itemsep=2pt]
\item[\opt{compose=shadow} (Mode 1, default)] a light background behind the ribbon along its \emph{whole} path;
 shows precisely which part of the outer braid the inner braid replaces. Prefer it when the ribbon crosses other
 strands, or when you want the replaced strand to stay visible after the inner braid.
\item[\opt{compose=separator} (Mode 2)] the inner braid replaces the strand and two dashed lines on either side
 (by default only alongside the inner braid) set it apart from its neighbours. Prefer it for the
 ``box inside a strand'' reading, or when shading would clutter dense diagrams.
\item[\opt{compose=none}] no marking.
\end{description}
""")
EX(r"""
\braid{\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{1}}\bset{compose=shadow}} \qquad
\braid{\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{1}}\bset{compose=separator}} \qquad
\braid{\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{1}}\bset{compose=none}}
""")
T(r"""
\subsection{Where the inner braid sits, how far the marking runs, appearance}
\begin{center}\small\begin{tabular}{@{}lp{9.6cm}@{}}\toprule
\opt{at=top|bottom|$j$} & the inner braid is inserted at the top (default), at the bottom, or after $j$ outer layers; the boundaries do not depend on it\\
\opt{extent=auto|full|inner} & how far shadow/separators run: \opt{auto} = full for shadow, inner part for separators (full if the inner braid is trivial)\\
\opt{shadowcolor} & shadow colour (default \opt{gray!22}) \\
\opt{sepstyle}, \opt{sepcolor} & dash style (default \opt{dashed}), colour\\
\opt{regionpad} & distance of shadow edge / separators from the outer strands (default 0.17cm; same for both modes)\\
\bottomrule\end{tabular}\end{center}
""")
EX(r"""
\braid{\bin{x y z}\bcr{1 2}\bsub{2}{\bin{a b}\bcr{-1 -1}}\bset{at=bottom}} \qquad
\braid{\bin{x y z}\bcr{1 2}\bsub{2}{\bin{a b}\bcr{1 -1}}\bset{compose=separator,at=bottom}} \qquad
\braid{\bin{x y z}\bcr{2 1}\bsub{1}{\bin{p q}\bcr{1}\bcol{1}{red}\bcol{2}{blue}}\bsub{3}{\bin{u v}\bcr{-1}}%
       \bset{shadowcolor=teal!15}}
""", r"""
In the last diagram two strands are replaced; the inner colours override the colour of the outer strand.
Composition is also available in Python: \opt{outer.compose\_at(k, inner, at="top")}.
""")

# ------------------------------------------------------------------------------------------
T(r"""
\section{Standard identities}\label{sec:ident}
\cs{braidid\{name\}\{options\}} draws standard diagrams without any coordinates. Available names:
\opt{ybe}, \opt{far}, \opt{inverse}, \opt{crossings}, \opt{assoc}, \opt{pentagon}, \opt{hexagon}.
\subsection{Braid relations and basic crossing identities}
Options: \opt{labels} (space separated), \opt{colors} (one per strand), \opt{sign} (\opt{+}/\opt{-}), \opt{rel}
(TeX shown between pictures), \opt{gap}, and any style option (\opt{width}, \opt{lw}, \opt{discs}, ...).
""")
EX(r"""
\braidid{ybe}{}
""", "Yang--Baxter / braid relation $\\sigma_1\\sigma_2\\sigma_1=\\sigma_2\\sigma_1\\sigma_2$.")
EX(r"""
\braidid{ybe}{labels={x_1 x_2 x_3},colors={teal!75!black orange!90!black purple},sign=-}
""", "The same relation with inverse generators, own labels and strand colours.")
EX(r"""
\braidid{far}{} \qquad \braidid{crossings}{}
""", "Far commutativity $\\sigma_1\\sigma_3=\\sigma_3\\sigma_1$ and the two basic crossings.")
EX(r"""
\braidid{inverse}{colors={red blue}}
""", r"""
$\sigma\sigma^{-1}=\mathrm{id}=\sigma^{-1}\sigma$. The same strand is over at both crossings (a Reidemeister~II
move), which is why the picture really is the identity.
""")
T(r"""
\subsection{Associativity, pentagon, hexagon}
\opt{assoc} draws the associator $(ab)c\to a(bc)$ and its inverse as braids between differently parenthesized
configurations (with discs). \opt{pentagon} and \opt{hexagon} are commutative diagrams whose vertices are all
parenthesizations; nodes, arrows and labels are generated and the polygon is sized to fit the labels.
Options: \opt{objects}, \opt{op} (tensor sign, \opt{op=\{\}} for juxtaposition), \opt{assoc} (associator symbol),
\opt{braiding} (braiding symbol), \opt{radius}, \opt{aspect}, \opt{nodestyle} and \opt{edgestyle} (TikZ keys),
\opt{color}, \opt{font}, \opt{scale}.
""")
EX(r"""
\braidid{assoc}{labels={x y z}}
""")
EX(r"""
\braidid{pentagon}{scale=0.9}
""")
EX(r"""
\braidid{hexagon}{objects={U V W},braiding={\sigma},scale=0.9,color=blue!50!black}
""")
EX(r"""
\braidid{pentagon}{objects={W X Y Z},op={},assoc={\Phi},color=teal!60!black,%
  nodestyle={draw=gray,rounded corners=2pt,inner sep=3pt},scale=0.75}
""", r"""
The pentagon commutes in the sense that both paths from $((ab)c)d$ to $a(b(cd))$ pass through trees with the same
leaf order; the hexagon is the first hexagon axiom of a braided monoidal category (associators $\alpha$ and
braidings $c$). Wide diagrams: lower \opt{scale} or put them on their own line.
""")

# ------------------------------------------------------------------------------------------
T(r"""
\section{Little 2-disc diagrams}\label{sec:discs}
The little 2-discs operad is pictured with discs centred on an axis: a configuration \((ab)c\) is two nested
levels of discs. \cs{bset\{discs\}} (or \opt{discs=in|out|both}) draws, for the input (top) and output (bottom)
configuration, \textbf{one disc per node of the parenthesization tree}:
leaves are small discs around the endpoints, every parenthesized group is a larger disc that contains exactly
the discs of its members, and the whole configuration is the outermost disc. Containment mirrors the
parentheses exactly (checked in the test-suite: ancestor $\Leftrightarrow$ contains; unrelated groups are disjoint).
Discs imply the horizontal axis; labels are placed outside the outermost disc.
""")
EX(r"""
\braid{\bin{((a b) c)}\bset{discs}} \quad \braid{\bin{(a b)(c d)}\bcr{2}\bset{discs}} \quad
\braid{\bin{((a b) c) d}\bcr{3}\bset{discs,width=4.2cm}}
""", r"""
In $((ab)c)$: $a$ and $b$ lie in an inner disc; that disc together with $c$ lies in the outer disc.
""")
T(r"""
\subsection{Operadic composition}
Combining \cs{bsub} with discs shows $\gamma(\sigma;\tau)$: the disc of the inserted configuration sits inside
the disc slot of the replaced strand, at the top and (for the output configuration) at the bottom.
""")
EX(r"""
\braid{\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{1}}\bset{discs,compose=shadow}} \qquad
\braid{\bin{x y z}\bcr{2}\bsub{3}{\bin{(a b) c}}\bset{discs=in,compose=none}}
""", r"""
The marks of Section~\ref{sec:compose} and the discs can be combined or used separately.
\textbf{Limitation:} BraidTeX draws the \emph{pictures}; it does not model configuration spaces, operadic
composition maps or their relations.
""")

# ------------------------------------------------------------------------------------------
T(r"""
\section{Customizing}\label{sec:custom}
Options go in \cs{bset\{...\}} (one braid) or \cs{braidsetup\{...\}} (all following braids; it is linear,
not scoped by TeX groups). \cs{bset} overrides \cs{braidsetup}. Lengths accept \opt{cm mm pt in}
(default cm). Changing style never changes the braid or its boundary configurations.
\begin{longtable}{@{}p{4.3cm}p{10.4cm}@{}}\toprule
\opt{width}, \opt{height} & total size (defaults: from strand count and word length)\\
\opt{spacing}, \opt{minspan} & default endpoint distance (0.9cm) and minimum span (1.2cm)\\
\opt{band}, \opt{pad}, \opt{margin} & height per crossing layer (0.9cm), straight stub top/bottom, horizontal margin\\
\opt{lw} & strand line width (0.9pt)\\
\opt{gap} & clearance around over-strands (0.07cm)\\
\opt{labels} & \opt{both} (default), \opt{in}, \opt{out}, \opt{none}\\
\opt{fontsize} & \opt{tiny}\,\dots\,\opt{large}\\
\opt{color}, \opt{palette} & main strand colour; default per-strand scheme\\
\opt{dots}, \opt{sigma} & endpoint markers; crossing labels $\sigma_i^{\pm1}$ (left margin)\\
\opt{rho}, \opt{wmin} & nesting ratio and smallest relative gap of the hierarchical layout\\
\opt{inpos}, \opt{outpos} & custom normalized endpoint positions, e.g. \opt{inpos=\{0 .2 1\}}\\
\opt{compose}, \opt{at}, \opt{extent}, \opt{shadowcolor}, \opt{sepstyle}, \opt{sepcolor}, \opt{regionpad} & composition modes (Section~\ref{sec:compose})\\
\opt{discs} & little-disc nesting (Section~\ref{sec:discs})\\
\opt{gapdots}, \opt{gaprows}, \opt{gapthrough}, \opt{gapcolor}, \opt{gapspan} & gaps / omitted strands (Section~\ref{sec:gaps})\\
\opt{geometry}, \opt{tension}, \opt{wrap} & strand shapes: \opt{default} or \opt{natural} (Section~\ref{sec:geometry})\\
\opt{inline} / \opt{size=inline} & compact preset for use in running text\\
\bottomrule\end{longtable}
\subsection{Examples}
""")
EX(r"""
\braid{\bin{a b c}\bcr{1 2}\bset{width=3.4cm,lw=1.4pt,band=0.7cm,fontsize=normalsize}} \qquad
\braid{\bin{a b c}\bcr{1 2}\bset{dots,labels=in,color=blue!60!black}} \qquad
\braid{\bin{a b c}\bset{inpos={0 0.15 1},outpos={0 0.85 1}}\bcr{}}
""")
T(r"""
\subsection{Strand geometry: \opt{default} and \opt{natural}}\label{sec:geometry}
\cs{bset\{geometry=default|natural\}} (or \cs{braidsetup\{geometry=natural\}} for the whole document) chooses
how strands are drawn. The braid, its permutation, colours and labels are identical in both modes; only the shape
of the curves changes.
\begin{description}[leftmargin=1.2em,itemsep=2pt]
\item[\opt{default}] every crossing layer is its own S-curve that comes to rest (vertical tangent) at each layer
 boundary. Very regular and always correct, but a strand with several crossings in a row looks like a snake.
\item[\opt{natural}] a strand is \emph{one string}: a single smooth curve through all its crossings. If it passes
 over (or under) several strands in a row it runs in one nearly straight diagonal instead of stopping between
 crossings; it only bends where it really has to turn (the same strand crossing back, i.e.\ a twist), and it
 never bends when it does not need to. Bending energy is about 35--40\,\% lower than in the default mode.
\end{description}
Natural mode is preferable for long words, many consecutive crossings and pictures that should look like real
cord; the default mode is preferable for regular, grid-like diagrams (for instance when pictures are compared
layer by layer, as in the identities of Section~\ref{sec:ident}).
""")
EX(r"""
\braid{\bin{a b c d}\bcr{1 2 3}\bset{geometry=default}} \quad
\braid{\bin{a b c d}\bcr{1 2 3}\bset{geometry=natural}} \qquad
\braid{\bin{a b c}\bcr{1 2 1 1 2 1}\bset{palette,geometry=default}} \quad
\braid{\bin{a b c}\bcr{1 2 1 1 2 1}\bset{palette,geometry=natural}}
""", r"""
Left pair: strand $a$ crosses three strands in a row; in natural mode it is a single straight run. Right
pair: the full twist --- the straight diagonals replace the zig-zag, while the genuine back-and-forth twists
stay.
""")
T(r"""
\paragraph{Tuning the string.} Two options (natural mode only):
\begin{center}\small\begin{tabular}{@{}lp{10.6cm}@{}}\toprule
\opt{tension} (0--1, default 1) & how straight the strings run: 1 = straightest; 0 reproduces the default
 shapes; values in between mix the two\\
\opt{wrap} (default 0.08cm) & how far a string swings out when it winds back and forth around another one
 (the shoelace/knot situation): 0 gives tight, metallic-looking turns, larger values give looser, rounder loops;
 raise \opt{band} as well for even softer loops\\
\bottomrule\end{tabular}\end{center}
""")
EX(r"""
\braid{\bin{a b c}\bcr{1 1 2 2 1 1}\bset{palette,geometry=natural,wrap=0}} \quad
\braid{\bin{a b c}\bcr{1 1 2 2 1 1}\bset{palette,geometry=natural}} \quad
\braid{\bin{a b c}\bcr{1 1 2 2 1 1}\bset{palette,geometry=natural,wrap=0.2}} \quad
\braid{\bin{a b c}\bcr{1 1 2 2 1 1}\bset{palette,geometry=natural,tension=0.4}}
""", r"""
From left to right: \opt{wrap=0}, the default \opt{wrap}, a loose \opt{wrap=0.2}, and \opt{tension=0.4}.
""")
T(r"""
\paragraph{Safety net.} A natural-mode picture is \emph{checked}: every layer must contain exactly the intended
crossings, non-crossing strands must keep a visible distance, gaps at crossings must fit, ribbon markings must stay
clear of their strands. If a setting would violate this (for instance a very narrow diagram with a large
\opt{wrap}) the tension and wrap are reduced step by step, ending at the default shapes, which are always correct.
So \opt{natural} can never change the mathematics of a diagram, only its looks.
""")
T(r"""
\paragraph{Document defaults.} For a whole thesis put in the preamble, e.g.
\opt{\textbackslash braidsetup\{lw=0.8pt, compose=separator, palette\}}; override locally with \cs{bset}.
\paragraph{Geometry of the default mode in one paragraph.} Each strand is a chain of cubic B\'ezier curves with vertical tangents at
the layer boundaries (smooth, no kinks; minimum radius of curvature about 1.8\,mm at the default spacing).
All strands in a layer share the same parametrization, so two strands that do not swap never meet and two that
swap cross \emph{exactly once}: a diagram always has exactly as many crossings as generators, whatever the
input/output spacings. The under-strand is cut by a true vector gap, not masked in white.
""")

# ------------------------------------------------------------------------------------------
T(r"""
\section{Gallery}
Each example is complete: paste it into a document that loads \opt{braidtex} and run \opt{braidtex compile}.
\subsection*{Full twist}
""")
EX(r"""
\Delta^2 = \braid{\bin{1 2 3}\bcr{1 2 1 1 2 1}\bset{palette}}
""")
T(r"\subsection*{Braided hexagon pieces and a morphism in the parenthesized braid category}")
EX(r"""
c_{A,B}\otimes \mathrm{id}_C = \braid{\bin{(A B) C}\bcr{1}}, \qquad
\alpha\circ(c\otimes 1) \;:\; \braid{\bin{(A B) C}\bcr{1 2}\bout{(B C) A}\bset{width=3.6cm}}
""")
T(r"\subsection*{Equation with axes (as in the thesis picture)}")
EX(r"""
\psi(\tau) = \braid{\bin{1 2}\bcr{1}\bax{frame}} \cdot
\left(\braid{\bin{1 2}\bcr{-1}\bax{frame}}\right)^{\nu},
""")
T(r"\subsection*{Operadic composition with discs}")
EX(r"""
\gamma(\sigma_1;\tau)\;=\;
\braid{\bin{x y z}\bcr{1}\bsub{2}{\bin{a b}\bcr{-1}}\bcol{1}{teal!75!black}\bcol{3}{orange!90!black}%
       \bset{discs,at=bottom,shadowcolor=gray!15}}
""")
T(r"\subsection*{Many crossings, different input and output trees}")
EX(r"""
\braid{\bin{((a b) c) d}\bcr{1 2 3 -1 -2 1}\bout{(d c)(b a)}\bset{width=4cm,palette}}
""", display=True)

# ------------------------------------------------------------------------------------------
T(r"""
\section{Troubleshooting}
\begin{description}[leftmargin=1.2em,itemsep=3pt]
\item[A grey box ``unprocessed braid'' appears.] You ran \opt{pdflatex} directly. Use \opt{braidtex compile main.tex}.
\item[``Missing braid asset''.] The transformed source refers to \opt{braids/bt-\dots}, but LaTeX runs elsewhere. Run
 from the project directory, or just use \opt{braidtex compile}. After moving the project run it again (assets are regenerated).
\item[``output endpoint $j$ is labeled \dots''.] \cs{bout} contradicts the strand permutation. The message lists the
 expected output labels. For a purely visual change use \cs{blab\{out\}\{\dots\}}.
\item[``generator \#$k$ = $g$ is invalid''.] With $n$ strands only $1\le|i|\le n-1$ exist. If you gave no
 \cs{bin}/\cs{bn}, $n$ is inferred as $\max|i|+1$.
\item[A label with parentheses is split into groups.] Wrap it: \opt{\{f(x)\}} or \cs{atom\{f(x), y\}}.
\item[Diagram too large inline.] \cs{bset\{inline,labels=none\}}, or set \opt{height}/\opt{band}/\opt{width}.
\item[Warnings about endpoints closer than 2.5\,mm or a gap reaching the end of a layer.] Increase \opt{width}/\opt{band},
 lower the nesting weight (\opt{wmin}), or reduce \opt{gap}.
\item[``regionpad is too large''.] The shadow/separators would touch a neighbouring strand: reduce \opt{regionpad} or widen the diagram.
\item[``no room for the dots of the gap''.] The gap is crossed so often that no height is free of strands.
 Increase \opt{band} or \opt{height}, use \opt{gapdots=1}, or make the gap wider with \opt{gapspan}.
\item[\cs{bcr} indices are off in a braid with \opt{...}.] A gap counts as a position: in \opt{a ... b} the strand $b$ is position 3.
\item[``position $k$ is a gap''.] Colours, notes and marked points belong to strands, not to the gap placeholder.
\item[Dashed separators look cluttered.] \opt{extent=full} draws them along the whole ribbon, across other strands; prefer
 the default, or use \opt{compose=shadow} for long ribbons.
\item[Pentagon/hexagon too wide.] \opt{scale=0.8}, or put it on its own line.
\item[Changes in \cs{braidsetup} seem ignored.] It applies to braids \emph{after} it in the source and is not group-scoped.
\item[\cs{braid} inside \cs{newcommand} or another macro argument.] Not supported: the scanner reads source text, not expanded macros.
 Put \cs{braid} directly in the document, or generate the macro text before running \opt{braidtex}.
\item[Stale pictures.] \opt{braidtex compile -f} regenerates everything; \opt{braidtex clean} deletes assets.
\item[Conflict with another package.] The CTAN package \opt{braids} also defines \cs{braid}; do not load both.
\item[Does BraidTeX need shell escape?] No. It is never used; the engine is run with \opt{-no-shell-escape}.
\end{description}

\section{Reference}
\subsection{Command line}
""")
LST(r"""
braidtex render --expr '\bin{a b}\bcr{1}' [--format tikz|standalone|svg|pdf] [-o FILE]
braidtex render --json spec.json --format pdf -o fig.pdf           # standalone figure
braidtex render --identity pentagon --opts 'objects={a b c d}' -o p.tex
braidtex expr '<latex fragment with \braid{..}>'                   # transform a fragment
braidtex transform main.tex [--check] [--stdout] [--build DIR]     # preprocess only
braidtex compile main.tex [--engine pdflatex|lualatex|xelatex] [-f] [-v]
braidtex clean [DIR]        braidtex sty        braidtex --version
""")
T(r"""
Common options: \opt{--assets DIR} (default \opt{braids/}), \opt{-f} force, \opt{-v} verbose. Errors in the source
are reported as \opt{file:line:col: message} with exit status 2.
\subsection{Python}
""")
LST(r"""
from braidtex import Braid, Style, Cache, render_tikz
outer = Braid([1], "x y z")
inner = Braid([1], "a b")
c = outer.compose_at(2, inner, at="top")       # boundaries: x (a b) z  ->  (b a) x z
c.permutation, c.regions                        # strand k ends at output slot p[k-1]
open("fig.tikz", "w").write(render_tikz(c.replace(style=Style(compose="separator", discs="both"))))
Cache("braids").ensure(c, "pdf")                # cached standalone PDF
""", "python")
T(r"""
\subsection{Limitations}
\cs{braid} needs the preprocessing step; only \cs{input}/\cs{include} are followed; named/mixed xcolor colours only;
SVG output shows plain-text labels and omits composition marks and discs; pentagon and hexagon are
the standard commutative diagrams (first hexagon axiom) with text labels; BraidTeX draws little-disc
\emph{pictures} but does not model configuration spaces or operad composition.
\end{document}
""")

OUT.write_text("\n".join(parts), encoding="utf-8")
print("wrote", OUT)
