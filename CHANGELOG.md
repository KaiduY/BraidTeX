# Changelog

## 0.5.0

### Added
- **Surface braid groups: sphere and torus.** `surface=plane|sphere|torus` (per braid or `\braidsetup`).
  - *Sphere*: Artin generators + the surface relation; frame with dashed arcs through infinity and an `S^2` tag.
  - *Torus*: loops `a<i>` / `b<i>` (and inverses `-a<i>`, `-b<i>`) in `\bcr` and in Python (`Loop`, or strings);
    frame with edge-identification chevrons and a `T^2` tag; `a`-loops pass in front of everything and leave/enter
    through the identified edges (two layers, arrowheads, label), `b`-loops are rings (one layer).
  - Works with colours, labels, gaps, both geometries, ribbons (`\bsub`: planar inner braid into a surface braid;
    loops of other strands sweep over the ribbon), axes (`\bax{torus|sphere|none}`), `looplabels`, `surfacelabel`.
- **Little discs on surfaces**: sphere = dashed root disc marked infinity (cyclic structure), torus = no root disc
  (module structure); inner braids must be planar.
- **Relation macros**: `\braidid{sphere}`, `sphere-twist`, `torus-r1`, `torus-r2`, `torus-r4`, `torus-tr`,
  `torus-conj` (options `n`, `loop`, `labels`, `colors`, `rel`).
- **`braidtex.surface`: an independent motion model** of the torus (points on R^2/Z^2): lifted end points and, for
  every pair, the class of the relative path in R^2 minus lattice (ray-crossing words). It confirmed that all relations
  of Bellingeri's presentation hold for the drawn conventions (4 of 32 conventions do, the drawn one among them),
  rejects wrong relations, and gave `a_2 = s_1^-1 a_1 s_1`, `b_2 = (a_1^-1 s_1) b_1 (...)^-1`.
- `docs/surfaces.md`: literature, the diagram-language decisions, little-discs extension, limits, roadmap.
- 38 new tests, 285 in total (surface algebra, negative controls, model, geometry for random torus words in both geometries,
  drawing, identities, transformer, cache); manual chapter and showcase section.

### Changed
- Words may contain loop generators (`Braid.word` items are ints or `Loop`); `Braid.n_projected_crossings` is the
  number of crossings in the picture (sigma crossings + `n-1` per `a`-loop).
- Geometry works on *geometry layers* (an `a`-loop is two); seam jumps are handled in analysis helpers
  (`polyline`, `polylines`, `count_intersections`, `max_join_error`). Renderer version bumped.

### Known limits
- Only genus 0 and 1; no cabling of loops of a whole ribbon; surface equality is refuted by the model, not decided;
  SVG omits frames and marks; the sphere relation and `Delta^2 = Delta^-2` are classical statements (not machine-checked).
## 0.4.0

### Added
- **Gaps for large or infinite braids.** `...` (also `\dots`, `\cdots`, `\ldots`) in a configuration marks
  omitted strands. A gap is an invisible placeholder strand occupying one position, so words, permutations,
  layers, layouts, ribbons, discs and both geometries work unchanged; boundaries are validated (gaps arrive
  at gaps), and colours/notes/marked points/substitution on a gap are rejected with a clear message.
- **Dot rows**: drawn at heights shared by *all* gaps (aligned), centred on each gap's own path, moved
  until every dot keeps a clearance from every strand (smaller pitch as a last resort, per-gap placement and a
  warning only if nothing fits). Options `gapdots`, `gaprows`, `gapcolor`, `gapspan`.
- `gapthrough=dotted`: a strand that passes through a gap region is drawn dotted inside it; dot rows keep a larger
  distance from strands in this mode so a dotted piece is never mistaken for a row.
- No axis ticks, endpoint markers, labels or leaf discs at gaps; SVG output draws the dots.
- **Mixed labeled/unlabeled configurations** (`*` is the unlabeled marker) are now covered by tests and
  documentation: validation, display, composition.
- 26 new tests (247 total): parsing/roundtrip, permutation and boundary validation with gaps, rejection of
  decorations, mixed labels, layout, exact crossings with random words in both geometries and both
  `gapthrough` modes, alignment/centring/clearance of the dots, dotted traversal confined to the region,
  ribbons/discs/axes with gaps, options, transformer errors.
- Manual section "Large or infinite braids", showcase section 9, troubleshooting entries.

### Changed
- Renderer version bumped (cache regenerates).

## 0.3.0

### Added
- **Natural geometry mode** (`geometry=natural`, also via `\braidsetup`): a strand is one continuous string
  instead of a chain of independent S-curves. Each strand is a spline through its positions at the layer
  boundaries with monotone (Fritsch-Carlson) tangents: consecutive crossings are traversed in one nearly
  straight run, and a strand bends only where it really turns. Measured on typical words: bending energy
  -35..-40 %, fewer inflection points (e.g. 8 -> 6, 11 -> 7), same crossings. `default` is unchanged.
- `tension` (0..1; 0 reproduces the default shapes) and `wrap` (cm, default 0.08): how loosely a string swings
  around another in back-and-forth twists (shoelace look instead of tight metallic turns).
- Verification and fallback: each natural attempt is checked (exact crossing pattern per layer by sampled
  sign changes, minimum separation of non-crossing strands, bounds, crossing gaps fit their layer, ribbon
  markings clear of their strands); on failure tension and wrap are reduced stepwise down to the default shapes,
  which are provably correct. Natural mode works with ribbons, discs, axes and all identities.
- 24 new tests (221 total): exact crossings for random words/trees/wraps/tensions, G1 joins, straight runs
  for consecutive crossings, genuine turns kept, wrap widens twists, hostile settings fall back correctly,
  clean gaps, ribbon containment, option validation, JSON and cache keys.
- Manual section "Strand geometry" and showcase section 8 with side-by-side comparisons.

### Changed
- Crossing parameter is now found by root finding on the actual curves (identical result for `default`).
- Renderer version bumped (cache regenerates).

## 0.2.1

### Added
- **Editor integration (VS Code / LaTeX Workshop).** `braidtex compile --build out` keeps all outputs in
  `out/` like a latexmk `-outdir=out` recipe; `docs/vscode/settings.json` and README/manual sections give the
  ready-made tool/recipe.
- Transformed sources **preserve line numbers** (replaced multi-line braids leave comment-only line breaks), and
  the SyncTeX file and the LaTeX log are rewritten to point at the *original* files, so forward search and
  error links work on your own sources. `-synctex=1 -file-line-error` are passed automatically.

### Fixed
- `--build DIR` inside the project directory made the "mirror sub-directories" step recurse into its own output
  (`out/out/out/...` until "File name too long"). It now never descends into the build or asset directories.
- With an explicit `--build`, the PDF is no longer also copied next to the source.
- 3 new regression tests (build dir inside the project, line preservation, SyncTeX/log remapping); 194 -> 197 total.

## 0.2.0

### Added
- **Composition modes.** `\bsub{k}{inner}` replaces strand `k` by an inner braid (cabling: the
  strand becomes a ribbon crossing other strands as one block, in a single drawing layer).
  - `compose=shadow` (Mode 1, default): light background along the replaced strand.
  - `compose=separator` (Mode 2): two dashed lines beside the inner braid.
  - `compose=none`; `at=top|bottom|<j>`, `extent=auto|full|inner`, `shadowcolor`, `sepstyle`,
    `sepcolor`, `regionpad` (same spacing for both modes). Several `\bsub` per braid; colours of the
    outer strand apply to the ribbon, inner colours override. Python: `Braid.compose_at`.
  - Boundary configurations of the composite are those of the outer braid with the leaf replaced by the
    inner configuration (independent of `at`); validated like any braid.
- **Standard identities** `\braidid{name}{options}`: `ybe`, `far`, `inverse`, `crossings`, `assoc`,
  `pentagon`, `hexagon`; configurable labels, colours, signs, objects, tensor sign, associator/braiding
  symbols, node/edge styles, colours, sizes, `scale`. Pentagon/hexagon are sized automatically from label
  widths. CLI: `braidtex render --identity NAME --opts ...` (tikz / standalone / pdf).
- **Little 2-disc pictures.** `discs=in|out|both`: one stadium-shaped disc per node of the parenthesization
  tree, nested exactly like the parentheses (containment proven by construction and tested: ancestor
  contains, unrelated groups disjoint, every leaf lies in exactly its ancestors). Implies the axis; labels
  moved outside the outermost disc; stub heights adapt.
- **Layers.** A braid may group commuting/independent crossings into one drawing layer
  (`Braid(..., groups=[...])`), validated (no pair crosses twice in a layer).
- `inline` preset and `spacing`/`minspan` options for compact in-text diagrams.
- User manual (`docs/manual/manual.pdf`, written with the package; generated by `make_manual.py` so the
  listings and the live examples are the same strings) and a feature showcase PDF.
- 89 new tests (105 -> 194): cabling vs an independent permutation reference, composition independence of
  insertion point, region/ribbon geometry, disc nesting, identities, new diagnostics, curvature, QC over
  every shipped example (crossing count, joins, bounds, no geometry warnings), real compilation of the
  showcase and manual.

### Changed (geometry)
- Strand curves: vertical Bezier handles lengthened from 1/3 to 1/2 of the layer height (y stays strictly
  monotone). Peak curvature dropped from ~9/cm to ~4/cm (min radius 1.1 mm -> 1.8 mm); crossing counts
  remain exactly `len(word)`. Strands were already cubic Beziers; the stubs are the only straight pieces.
- Layers inside a ribbon region carry no horizontal drift between input and output layouts (inner braids
  are no longer skewed; dashed separators are parallel).
- Under-strands may be cut several times in a layer (needed for ribbons); overlapping gaps are merged.
- Renderer version bumped (cache keys change; old assets are regenerated automatically).

### Fixed (found by inspecting the compiled PDFs)
- Shadow fill hid the lower half of disc outlines (z-order: axes, regions, discs, strands).
- Pentagon bottom edge too short: vertex labels collided. Polygon now enlarges until labels clear.
- Edge labels cramped against arrows; `\otimes` followed by a letter produced `\otimesc`.
- `crossings` scene: margin labels floated between pictures; now captions under each crossing.
- Inline diagrams were too wide for their height (flattened crossings).
- Identity options were validated lazily (errors only at render time); now validated when the macro is read
  (`braidtex transform --check` catches them).
- Disc radii depended on the *global* minimum endpoint gap and became tiny for deep nests; now local.

### Known limitations
See the README. Composite SVG output omits marks and discs. `extent=full` separators cross other strands.
