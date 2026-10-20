# BraidTeX 0.6.0 release notes

This release extends the prior BraidTeX implementation with reusable coordinate frames, ticks and separators; persistent-identity horizontal connectors; strand annotations; auxiliary dotted paths; named regions; model-level vertical stacking; and cabling-based operadic strand substitution. Stacks and substitutions operate on structured models, not rendered images. Connector attachment alternatives are represented as separate signed diagram terms.

The LaTeX source transformer and CLI remain a preprocessing workflow: use `braidtex build your-document.tex` to transform marked expressions, generate/cache TikZ assets in the document tree, and compile with `pdflatex`. No unrestricted shell-escape execution is required.

Validation performed for this release: 77 automated tests passed. The composition gallery compiled with `pdflatex` to two pages without detected warnings/overfull boxes. The composition-notation source was transformed with `braidtex build --force` and compiled to a one-page PDF.
