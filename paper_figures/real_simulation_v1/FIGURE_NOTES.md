# Real OpenFAST/BEM publication figures

These are data-driven scientific visualizations, not conceptual schematics.

## Figure 1 — rotor and full-field turbulent inflow

The three blades are lofted from the released NREL 5-MW AeroDyn station table
(span, chord, twist, sweep and airfoil ID) and the released airfoil coordinate
files. The colored plane and streamlines use all three velocity components from
the released TurbSim `.bts` file. The streamwise coordinate is reconstructed by
Taylor's frozen-turbulence hypothesis, `x = U_ref (t-t0)`. It must therefore be
captioned as a **TurbSim full-field inflow reconstruction**, not as a
Navier–Stokes CFD solution.

Suggested caption: *NREL 5-MW rotor immersed in the OpenFAST/TurbSim full-field
inflow used to generate the BEM benchmark. Blade surfaces are lofted from the
released AeroDyn chord, twist and airfoil definitions. The upstream volume is a
Taylor reconstruction of the measured TurbSim time series; color denotes the
streamwise velocity component.*

## Figure 2 — one real blade-element equation

Panel (a) uses record 89,241 from the released 2,448,000-record binary dataset
and the corresponding real airfoil geometry. Panel (b) evaluates the exact
released C residual and polar tables, then marks the OpenFAST reference root.

Suggested caption: *Local blade-element kinematics and nonlinear residual for a
representative OpenFAST record. The velocity triangle, airfoil, operating angle
and marked root are taken from the released benchmark rather than synthesized.*

## Figure 3 — why batched solving is required

Every pixel and surface sample comes from the complete released reference-root
array. At every time step, OpenFAST produces 51 coupled-in-time but independently
solvable blade-element root problems: 3 blades × 17 ordinary elements. Over
48,000 time steps this yields 2,448,000 solves, exposing the two-dimensional
parallelism that the GPU implementation batches.

Suggested caption: *Space–time organization of the complete OpenFAST BEM root
workload. The heat map contains all 2,448,000 reference roots; the surfaces
separate the three blades and show radial and temporal coherence. The workload
is naturally batched over blade elements and time.*

## Reproduce

```bash
python scripts/visualization/render_real_bem_figures.py
```

Python dependencies: `numpy`, `matplotlib`, `pyvista`, `vtk`, and
`openfast-io`. The JSON manifest records exact source SHA-256 hashes and selected
record values.
