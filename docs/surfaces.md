# Braids on surfaces: design notes (BraidTeX 0.5)

This document records the literature we used, the decisions taken for the diagram language, how
correctness is tested, and what is deliberately *not* done yet.

## 1. The groups and their presentations

Configuration spaces of `n` points: `B_n(M) = pi_1(UConf_n(M))`, with `M` the plane `E^2`, the
sphere `S^2` or the torus `T^2`.

| surface | presentation | source |
|---|---|---|
| plane | `s_1..s_{n-1}`, braid relations | Artin |
| sphere | the same generators and relations, plus the **surface relation** `s_1 s_2 ... s_{n-1}^2 ... s_2 s_1 = 1` | Fadell-Van Buskirk, *The braid groups of E^2 and S^2*, Duke 1962; Bellingeri 2004 |
| torus | `s_1..s_{n-1}, a, b` (`a`, `b`: the first strand goes once round each cycle) with the braid relations and **R1** `a s_i = s_i a`, `b s_i = s_i b` (`i != 1`); **R2** `s_1^-1 a s_1^-1 a = a s_1^-1 a s_1^-1` (same for `b`); **R4** `s_1^-1 a s_1^-1 b = b s_1^-1 a s_1`; **TR** `a b^-1 a^-1 b = s_1 s_2 ... s_{n-1}^2 ... s_2 s_1` | Birman 1969; Scott 1970 (see 7); Bellingeri, *On presentations of surface braid groups*, J. Algebra 274 (2004), Thm 1.2 (genus 1) and arXiv:math/0110129 |

What this means for diagrams:

* **Sphere: no new generator, one new relation.** `B_n -> B_n(S^2)` is onto, so every spherical
  braid is *a planar braid diagram*; what changes is when two diagrams are equal. The picture of the
  new relation: the first strand running in front of all the others, round the back of the sphere
  and home again, is trivial. (Classical consequence: the full twist `Delta^2` has order 2 for
  `n >= 3`, i.e. `Delta^2 = Delta^-2`.)
* **Torus: two new kinds of moves.** A strand can go round the *horizontal* cycle (`a`) or round the
  *depth* cycle (`b`). Together with `s_i` they generate `B_n(T^2)`.

Loops of strands other than the first are conjugates in the group; we draw them directly (see 3.2).

## 2. How surface braids are drawn in the literature, and what we chose

Bellingeri draws a braid as *paths on a fundamental polygon* (a square for the torus) whose edges
("walls") are identified, with over/under information at crossings. That picture is compact but drops
the vertical time axis that all other BraidTeX diagrams (layers, ribbons, gaps, discs, identities)
rely on.

Options considered:

1. **Trace picture on the polygon** (literature). Rejected as the default: incompatible with the
   time-vertical machinery, and ambiguous for long words.
2. **Draw the surface** (a globe / a torus) at the top and bottom of the braid. Rejected: it costs a lot
   of space and makes layers hard to align. (The idea survives in miniature, see 3.1.)
3. **Time-vertical diagram plus a frame that says which surface it is** (chosen).

### 3. The chosen diagram language

#### 3.1 Telling the surfaces apart (`surface=plane|sphere|torus`)

* **Plane**: unchanged.
* **Sphere**: the two horizontal axes close up into circles *through the point at infinity*: a dashed
  arc over the top axis and under the bottom axis, with an `∞` mark. A small `S^2` tag. (With `discs`
  the dashed root disc plays this role, see section 5.)
* **Torus**: the diagram's vertical edges are drawn and carry the **edge-identification chevrons** of
  the polygon notation (the same mark on both edges = they are the same line). `T^2` tag. The
  chevrons sit in the top stub, where no seam can reach them.

The frame costs one thin box and two arcs: no extra height for the torus, `2 x 0.8cm` for the sphere.
`\bax{none}` removes it; `surfacelabel=false` removes the tag.

#### 3.2 Generators (exact definitions)

Positions are counted left to right at the moment the generator acts, like `s_i`. The viewer looks
along the depth direction; "front" means towards the viewer. Each generator is a motion of points on
`R^2/Z^2`, x horizontal, y depth:

* `s_i` (`i` in the word as `i`): points `i`, `i+1` exchange; for `+i` the left one passes **in front**.
  (This is BraidTeX's convention since 0.1.)
* `a_i` (`ai`): the strand in position `i` runs **to the right at the front level, once round the
  horizontal cycle**, passing in front of every other strand, leaves through the right edge and
  re-enters through the left edge *at the same height*, ending where it started. `-ai`: the inverse
  (to the left, same front level). Drawn as two layers, arrowheads at the identified edges, a small `a`.
* `b_i` (`bi`): the strand in position `i` goes **once round the depth cycle** at its own x, all other
  strands fixed. Drawn as a ring with an arrow on the strand (counter-clockwise `b`, clockwise `b^-1`),
  one layer.

Everything is a function of the position, so strands can be coloured, labelled, gapped (`...`),
cabled (`\bsub`) as before. Relations among loops of different positions (all verified, section 4):
`a_2 = s_1^-1 a_1 s_1`, `b_2 = (a_1^-1 s_1) b_1 (a_1^-1 s_1)^-1`.

#### 3.3 Why exactly this

In the projection to the horizontal axis, a `b`-loop leaves no trace except that the strand is
"turned through the depth direction"; the ring is therefore a *symbol*, and its meaning is fixed by the
motion above, not by the picture. The `a`-loop is the only generator that really crosses the
diagram's edges.

## 4. Correctness: an independent motion model

`braidtex.surface` simulates every generator as an explicit piecewise-linear motion of points on the
torus (lifted to the plane) and computes invariants of the resulting braid:

* the lifted end point of every strand (windings),
* for every pair of strands, the homotopy class of their *relative* path in `R^2 minus Z^2`
  (as the reduced word of crossings with disjoint rays from the lattice points).

Equal braids have equal invariants, so the model can **refute** an identity; it cannot prove one.
Results (tests in `tests/test_surface.py`):

* all braid relations and R1, R2, R4, TR hold for `n = 2, 3, 4` in the drawn conventions;
* of the 32 combinations of (front/back level of `a`, direction of `a`, direction of `b`, which
  strand is in front for `s_i`, order of reading), exactly **4** satisfy all relations, and the one
  BraidTeX draws is among them (the others are mirror images);
* negative controls: mirrored R4, swapped `a`/`b`, `[a,b]` instead of `[a,b^-1]`, TR without the
  square or with `s^-2`, `a s_1 = s_1 a` are all rejected.

Every relation macro (`\braidid{torus-r1}`, ... `{torus-tr}`, `{torus-conj}`) draws words taken
from this module, so what is pictured is what was checked. The sphere relation and `Delta^2 = Delta^-2`
are the classical statements and are *not* machine-checked here (the model is for the torus).

## 5. Little discs on surfaces

Facts used (Budney; Getzler; Giansiracusa; Salvatore; Campos-Idrissi-Willwacher; Ayala-Francis):

* The (framed) little 2-discs operad `D_2` is **cyclic**: the outer boundary circle is just one more
  boundary component, `D_2(n)` has an action of the `n+1` symmetric group, matching the sphere
  `S^2 = C u {inf}` with `n+1` marked points (genus-0 moduli spaces `M_{0,n+1}`).
* For a surface `M`, the spaces `Conf_n(M)` form a **right module over `D_2`**: a configuration of
  discs in the plane can be inserted at one point of a configuration on `M`
  (`Conf_k(M) x D_2(m) -> Conf_{k+m-1}(M)`), compatibly with the operad structure.

What BraidTeX draws:

* **Sphere + `discs`**: the root disc is drawn *dashed and marked `∞`*: it is the complement of a disc
  around infinity, all discs are on equal footing (the cyclic picture). The nested discs inside are
  exactly the parenthesization, as for the plane.
* **Torus + `discs`**: **no root disc**, because the torus is not a disc: the identified frame stands for
  it. Discs appear only for the *inserted* groups, which is the module picture.
* **Module action = `\bsub`**: substituting a planar inner braid into a strand of a surface braid is
  the module insertion. Implemented for the torus including loops of the *other* strands that sweep
  over the ribbon. The inner braid must be planar (enforced).

Not done: modular/cyclic operad compositions between two surface diagrams, genus >= 2, and any claim
beyond the drawing (no configuration-space models are built).

## 6. Where this is going (and why GT cares)

* Genus one is where elliptic associators (Enriquez; Calaque-Enriquez-Etingof) live: the elliptic
  braid group `B_n(T^2)` replaces `B_n`, and the module structure above is its operadic shadow.
* Natural next steps: cabling of loops (`a`, `b` of a whole ribbon: parallel loops with staggered seams),
  higher genus (`a_r, b_r` with Bellingeri's relations R1-R4, TR), the projective plane, surfaces with
  boundary (free generators), and an exact word-problem backend (action on `pi_1` of the punctured
  surface) to *decide* equality instead of only refuting it.

## 7. References

*Provenance.* The presentations of section 1 were taken from Bellingeri's paper, which was read in full.
The other references were consulted through abstracts and search results only; please verify the citation
details before using them in print.

* E. Fadell, J. Van Buskirk, *The braid groups of E^2 and S^2*, Duke Math. J. 29 (1962).
* J. S. Birman, *On braid groups*, Comm. Pure Appl. Math. 22 (1969); G. P. Scott, *Braid groups and the
  group of homeomorphisms of a surface*, Proc. Camb. Phil. Soc. 68 (1970).
* P. Bellingeri, *On presentations of surface braid groups*, J. Algebra 274 (2004); arXiv:math/0110129.
* R. Budney, *The operad of framed discs is cyclic*, J. Pure Appl. Algebra 211 (2007); arXiv:math/0607490. E. Getzler, *Batalin-Vilkovisky algebras and two-dimensional topological field
  theories*, CMP 159 (1994). P. Salvatore, N. Wahl, *Framed discs operads and Batalin-Vilkovisky algebras*,
  Q. J. Math. 54 (2003). J. Giansiracusa, *The framed little 2-discs operad and diffeomorphisms of handlebodies*,
  arXiv:1008.3272.
* R. Campos, N. Idrissi, T. Willwacher, *Configuration spaces of surfaces*, arXiv:1911.12281. D. Ayala,
  J. Francis, *Factorization homology I: topological spaces*.
* B. Enriquez, *Elliptic associators*, Selecta Math. 20 (2014); D. Calaque, B. Enriquez, P. Etingof, *Universal
  KZB equations: the elliptic case*.
