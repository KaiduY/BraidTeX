# BraidTeX 0.7.0 release notes

This rendering-focused release retains the 0.6 model-level composition operations and improves strand geometry, automatic endpoint spacing, baseline alignment, strand tracing, connector depth ordering, tick placement, and auxiliary trajectories.

- Each strand identity is rendered as one continuous path across fan, crossing, and output sections. Crossing clearance is a short local cubic halo around the overpassing segment rather than a large gap across a whole arc.
- The default inline baseline is centered vertically on the diagram; `(braid-base)` remains available for the historical bottom-aligned behavior.
- Parenthesization uses a deterministic recursive gap hierarchy with a bounded cluster-gap increase at deeper levels.
- Frame and separator ticks can be bound to endpoint ports instead of fixed coordinates.
- Connectors have explicit `back`/`front` depth ordering, always keep endpoint nodes visible, and reject offsets that do not fit in their crossing-level band.
- Full-range auxiliary paths that follow strands are offset copies of the actual strand path; arbitrary control points remain available for intentional custom trajectories.
- Substitution keeps the outer and inserted braid generator conventions, and nested layout information is attached to replacement bundles without silently changing semantic endpoint labels.

## Validation

The 82-test automated suite passed after the implementation changes. The refreshed composition gallery compiled to two pages with `pdflatex`; the composition notation example and minimal inline/display-math example each compiled to one-page PDFs. The source tests include regression checks for center baseline, coherent identity paths, port-derived ticks, and connector depth ordering.
