# Four application-framework studies behind the non-BEM benchmarks

This note maps each scalar benchmark to a maintained application framework,
records what was actually executed, and prevents application-level pictures
from being mistaken for additional validation of a different mathematical
model.  All reported versions, row counts and hashes are frozen in
`paper_figures/domain_frameworks_v1/data/`.

## Framework selection and exact semantic boundary

| Benchmark domain | Application framework | Why it is the closest analogue to OpenFAST | Relationship to the C/CUDA equation |
|---|---|---|---|
| Elliptic Kepler equation | [Orekit 13.1.5 anomaly utility](https://www.orekit.org/static/apidocs/org/orekit/orbits/KeplerianAnomalyUtility.html) | Orekit is a production space-flight-dynamics library; its orbit layer explicitly converts mean, eccentric and true anomalies and its source routes elliptic mean anomaly through `ellipticMeanToEccentric` ([official source cross-reference](https://www.orekit.org/static/xref/org/orekit/orbits/KeplerianAnomalyUtility.html)). | Exact equation match: `E - e sin(E) - M = 0`, with the same elliptic range `0 <= e < 1`. |
| Single-diode photovoltaic model | [pvlib 0.15.2](https://pvlib-python.readthedocs.io/en/stable/user_guide/modeling_topics/singlediode.html) | pvlib links weather/temperature-dependent module parameters to full I-V curves and exposes Lambert-W, Newton, Brent and Chandrupatla solution paths. | Exact five-parameter single-diode residual match.  The application surface additionally uses a real CEC module record. |
| Non-isothermal CSTR | [Cantera 3.2.0 reactor network](https://www.cantera.org/stable/examples/python/reactors/continuous_reactor.html) | Cantera's official CSTR workflow contains inlet/outlet reservoirs, a mass-flow controller, a pressure controller and a stirred reactor.  Its official residence-time example tracks the reacting steady branch until extinction ([combustor example](https://www.cantera.org/stable/examples/python/reactors/combustor.html)). | Workload analogue, not equation identity.  Cantera solves a 53-species GRI-Mech reactor; the benchmark remains the separately frozen scalar conversion model with exact folds. |
| Peng-Robinson cubic EOS | [CoolProp 8.0.0 PR backend](https://coolprop.org/coolprop/Cubics.html) | CoolProp exposes PR pure-fluid saturation, flash and critical calculations and documents cubic EOS speed as a primary motivation. | Exact cubic-in-Z structure.  Propane critical data generate `A,B`; the repository's analytic cubic classifies one versus three admissible roots. |

## Executed experiments

### Orekit / Kepler

- Ran `KeplerianAnomalyUtility.ellipticMeanToEccentric` on a 72 by 180
  `(e,M)` plane.  The `M` grid combines global `[0,pi]` coverage with nine
  decades of resolution near `M=0`.
- Re-ran all 3,000 frozen Kepler cases through Orekit.
- Maximum equation residual was `9.8533e-16`; maximum absolute difference from
  the independent 80-digit oracle was `2.6692e-14`.  The largest differences
  occur in the intentionally ill-conditioned `e -> 1, M -> 0` corner, where
  `|dE/dM|` reaches approximately `1.0e9`.

### pvlib / photovoltaic module

- Loaded the CEC record `Canadian_Solar_Inc__CS5P_220M` (96 cells, nominal
  STC power 219.961 W) using pvlib's supported SAM database interface.
- Evaluated 357 independent operating conditions: 21 irradiances from 100 to
  1100 W/m2 and 17 cell temperatures from -10 to 70 degC.
- Generated six complete 181-point I-V curves with the pvlib single-diode
  implementation.
- Re-solved all 3,000 extended frozen PV samples using pvlib Brent.  Maximum
  current difference from the 70-digit oracle was `3.998e-12 A`; p99 was
  `1.301e-12 A`.

The high-precision CSV is read with pandas `float_precision="round_trip"`.
Without it, recent fast CSV parsers can shorten long fixed-point representations
of very small `I0` values, creating a false open-circuit discrepancy.

### Cantera / well-stirred combustor

- Used the official GRI-Mech 3.0 mechanism, lean methane/air at equivalence
  ratio 0.5 and 1 atm.
- For 21 inlet temperatures from 300 to 800 K, followed the hot steady branch
  through 72 decreasing residence times from 0.1 to 1e-4 s: 1,512 reactor
  steady states in total.
- Saved temperature, volumetric heat release and CH4/CO/CO2/H2O mole fractions.

This experiment explains the batch origin and extinction boundary in an actual
reactor framework.  It is not used as an oracle for the reduced scalar CSTR.
The figure therefore places the Cantera surface next to, rather than on top of,
the repository's exact cold/hot continuation and three-root fold diagram.

### CoolProp / Peng-Robinson propane

- Evaluated 160 PR saturation states for propane between `0.55 Tc` and
  `0.99 Tc`.
- Classified 18,271 independent `(Tr,Pr)` states on a 121 by 151 plane using
  the exact cubic in compressibility factor `Z`.
- Generated 2,500 isotherm points and retained liquid, middle and vapor roots.
- Reconstructed the public PR coefficients with the unrounded critical
  constants.  Against CoolProp saturation densities, the largest differences
  were `2.75e-6` for liquid Z and `2.66e-5` for vapor Z.  This is a
  framework-convention cross-check, not the frozen cubic oracle.

The root-count map makes the negative-control result physically interpretable:
the work per state is a small fixed cubic classification, so the analytic CPU
baseline can remain faster than a GPU end-to-end path even at large batch size.

## Why all four workflows are naturally batched

The independent index is different in each application, but the computational
shape is the same:

- orbit catalog or time sample x orbital element set;
- irradiance x temperature x module;
- inlet state x residence time x continuation direction;
- temperature x pressure x composition/fluid.

Within one outer simulation step, each cell produces its own small nonlinear
equation.  A single solve is too small to amortize GPU launch and transfer
overhead; the two-dimensional parameter plane supplies the concurrency.  The
figures show the complete parameter planes, not duplicated decorative samples.

## Reproduction

```bash
python -m pip install -r scripts/visualization/requirements_domain_frameworks.txt
python scripts/visualization/run_domain_framework_experiments.py
```

Orekit requires Java.  On Windows accounts whose path contains non-ASCII
characters, create the Orekit environment at an ASCII path because JNI can
truncate a Unicode JVM path:

```bash
python -m venv D:/orekit_env
D:/orekit_env/Scripts/python -m pip install "orekit-jpype[jdk4py]==13.1.5"
D:/orekit_env/Scripts/python scripts/visualization/run_orekit_reference.py
```

Render and audit all four figures:

```bash
python scripts/visualization/render_domain_framework_figures.py
```

The renderer writes PNG, PDF and SVG and records exact source/output hashes,
tight bounding boxes, pairwise panel overlaps and out-of-figure elements in
`paper_figures/domain_frameworks_v1/render_manifest.json`.
