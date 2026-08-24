# Frozen correctness result: adaptive_v1_20260824

## Status

The frozen RTX 5090 test-split run passed every pre-registered numerical margin.
The test split was executed once, in run
`20260824T005529Z_frozen_test_rtx5090`, after the configuration was written to
`manifests/frozen_adaptive_v1.json`.  A server-side marker prevents accidental
re-execution with the same config ID.

This establishes the numerical-correctness milestone.  It does not by itself
establish the final performance, end-to-end, OpenFAST BEM, profiling, or
cross-hardware claims.

## Independent reference

- 3,000 samples per domain; 15,000 total.
- Split per domain: 1,800 development, 600 calibration, 600 sealed test.
- Generated with 55 decimal digits (approximately 182 bits).
- Independent verification used 80 decimal digits.
- All five CSV SHA-256 values match the frozen manifest.
- Recomputed high-precision residual: median `3.17e-56`, p99 `4.37e-54`,
  maximum `4.11e-53`.
- Three-step-size whole-problem finite differences accepted 25/25 cases per
  domain.  Maximum relative implicit-gradient discrepancy was `7.38e-26`.
- CSTR and Peng--Robinson both contain one-root and three-root cases with both
  physical outer branches represented in all splits.

## Frozen margins

| Quantity | Margin |
|---|---:|
| absolute root error, all domains | `1e-7` |
| relative gradient error, four main domains | `2e-6` |
| relative gradient error, PR negative control | `1e-4` |
| wrong physical roots | 0 |
| nonfinite outputs | 0 |

## Test results (600 unseen samples per domain)

| Domain | max root error | p99 gradient relative error | max gradient relative error | corrections | wrong/nonfinite |
|---|---:|---:|---:|---:|---:|
| BEM smooth | `9.399e-8` | `6.672e-7` | `1.728e-6` | 36.67% | 0 / 0 |
| Kepler | `9.969e-8` | `5.142e-7` | `1.860e-6` | 83.50% | 0 / 0 |
| PV diode | `9.943e-8` | `1.721e-9` | `4.444e-8` | 95.67% | 0 / 0 |
| CSTR | `9.982e-8` | `9.147e-7` | `1.307e-6` | 1.33% | 0 / 0 |
| Peng--Robinson | `9.937e-8` | `5.956e-5` | `9.580e-5` | 18.50% | 0 / 0 |

With zero observed failures in 600 test samples, the Wilson 95% upper bound on
the per-domain failure probability is 0.636%.  This must be reported as “no
failure observed”, not as a mathematical guarantee.

## Failure-driven fixes retained in the audit trail

1. The initial generic safeguarded Newton path returned 34/600 wrong CSTR roots
   and 34/600 wrong PR roots in calibration even in FP64.  Small residuals did
   not detect the wrong physical branch.
2. Branch-aware low/high scanning reduced CSTR wrong roots to zero, but PR still
   had 17/600 misses because a coarse scan can cross two nearby roots.
3. A dedicated analytic Peng--Robinson cubic solver reduced PR FP64 wrong roots
   to zero, honestly treating it as the specialized negative control.
4. Residual/`|F_x|` gating left PR gradient p99 error at 5.37%.  A propagated
   gradient-risk estimate based on `|1/(Z-B)-F_ZZ/F_Z|` reduced the frozen test
   p99 to `5.96e-5` without using the test split for selection.

Pure FP32 remains an intentionally failing baseline on the frozen test split:
using the predeclared `1e-5` wrong-root/error indicator it produced 168 BEM,
306 Kepler, 282 PV, 0 CSTR and 6 PR failures.  FP64 produced zero wrong roots in
all five domains.

