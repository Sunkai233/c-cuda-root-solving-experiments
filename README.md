# Supplementary C/CUDA root-solving experiments

This directory is independent of the earlier five-domain repository.  It is the
RTX 5090 implementation work area for `SUPPLEMENTARY_EXPERIMENTS_C_CUDA.md`.

The executable suite is a traceable Phase-A/C harness.  It covers the four main
domains (smooth analytic BEM, Kepler, forward single-diode PV, non-isothermal
CSTR) plus a Peng--Robinson-style cubic negative control.  CPU and GPU use the
same residual, derivative, starting point, clamping rule and iteration budget.

The frozen correctness experiment uses a 55-decimal-digit oracle independently
verified at 80 dps.  The one-shot formal test and the full RTX 5090 performance
matrix are documented in:

- `results_processed/FROZEN_CORRECTNESS_V1.md`
- `results_processed/PERFORMANCE_MATRIX_RTX5090_V1.md`
- `results_processed/FAST_MATH_CANDIDATE_RTX5090.md`
- `results_processed/ALGORITHM_VALIDATION_RTX5090_V1.md`
- `results_processed/ALGORITHM_PERFORMANCE_RTX5090_V1.md`
- `results_processed/DF32_RTX5090_V1.md`
- `results_processed/FINITE_DIFFERENCE_GRADIENT_V1.md`
- `results_processed/OPENFAST_BEM_600S_V1.md`
- `results_processed/BEM_REAL_CUDA_NAIVE_V1.md`
- `results_processed/BEM_REAL_ALGORITHM_MATRIX_RTX5090_V1.md`
- `results_processed/BEM_REAL_LOW_DIVERGENCE_ABLATION_RTX5090_V1.md`

The 600-second, 48,000-step OpenFAST/NREL 5MW data prerequisite is complete.
After separating the two fixed-induction endpoints on each blade, it provides
2,448,000 ordinary real-table root states.  A first strict-FP64 C/CUDA naive
bisection development baseline and the full same-residual bisection, Brent and
Illinois algorithm matrix have now been measured on one RTX 5090.  OpenFAST
full-model runtime must not be reported as root-kernel performance.

Other scope limits remain explicit: Nsight Compute is not present on the host;
global CUDA fast-math has been tested and rejected because it changes CSTR
branch classification.  The strict FP64 solver-algorithm matrix is complete.
A true double-single df32 secondary candidate has been validated on dev/cal and
measured on the RTX 5090; it does not constitute a second formal one-shot test.
A new untouched holdout, multi-wind OpenFAST cases, a compact difficult-sample
fallback queue with direct warp profiling, and the user-deferred second GPU
architecture remain outstanding.  The fixed-step versus early-stop real-table
ablation is complete and rejects fixed 44-step bisection for this dataset.
Results must be cited within those boundaries.

The high-precision analytic implicit-gradient oracle has additionally been
cross-checked on calibration data by seven-step central finite differences,
where every perturbation independently re-solves the complete physical root
problem and branch-changing perturbations remain explicitly flagged.

## RTX 5090 build

The host has the NVIDIA driver but no host CUDA toolkit.  Compilation and runs
use the existing Docker installation and its vLLM development image (CUDA 12.9).

```bash
bash scripts/run_rtx5090.sh
```

Raw CSV/JSON files are append-only under `results_raw/<run_id>/`.  The runner
also captures the source hash, compiler, driver, GPU and CPU manifests.
