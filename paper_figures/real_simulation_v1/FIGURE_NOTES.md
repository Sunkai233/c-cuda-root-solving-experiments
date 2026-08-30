# Real OpenFAST/BEM two-dimensional publication figures

All panels are two-dimensional, data-driven scientific visualizations rather
than conceptual schematics. No three-dimensional reconstruction is used.

## Figure 1 — actual TurbSim rotor-plane field

The contour is the direct `y-z` plane at 306.1 s from the released TurbSim
`.bts` file. Color is the measured streamwise component; arrows are the measured
lateral and vertical components. The projected blade planforms use all 19
released AeroDyn span, chord and twist stations, and the markers are the exact
17 ordinary BEM radii used by each blade. No Taylor or CFD reconstruction is
present in this figure.

Suggested caption: *Instantaneous TurbSim rotor-plane inflow at 306.1 s for the
NREL 5-MW benchmark. Color denotes streamwise velocity and arrows denote the two
transverse components. The rotor planform and 51 blade-element nodes are drawn
from the released AeroDyn geometry and solver tables.*

## Figure 2 — complete diagnostics for one real blade element

Panel (a) uses record 89,241 from the released 2,448,000-record binary dataset
and the corresponding DU25 airfoil coordinates. Panel (b) displays the released
polar samples and the interpolated operating point. Panel (c) evaluates the
exact released C residual and locates its numerical zero. Panel (d) exposes the
Prandtl loss, axial induction, tangential term and solidity that form the same
residual. The manifest records the difference between the OpenFAST reference
angle and the exact zero in microdegrees.

Suggested caption: *Data-level audit of a representative OpenFAST blade-element
root problem: local kinematics and DU25 geometry, released polar interpolation,
exact C residual, and its nonlinear induction/loss terms.*

## Figure 3 — why batched solving is required

Every pixel and curve sample comes from the complete released reference-root
array. At every time step, OpenFAST produces 51 coupled-in-time but independently
solvable blade-element root problems: 3 blades × 17 ordinary elements. Over
48,000 time steps this yields 2,448,000 solves, exposing the two-dimensional
parallelism that the GPU implementation batches.

Suggested caption: *Space–time organization of the complete OpenFAST BEM root
workload. The overview contains all 2,448,000 roots; the full-resolution window
shows the 51 simultaneous tasks, and the radial profiles retain all 17 elements
of each blade at the same instant as Figure 1.*

## Reproduce

```bash
python scripts/visualization/render_real_bem_figures.py
```

Python dependencies: `numpy`, `matplotlib`, `scipy`, and `openfast-io`. The JSON
manifest records exact source SHA-256 hashes and selected
record values.
