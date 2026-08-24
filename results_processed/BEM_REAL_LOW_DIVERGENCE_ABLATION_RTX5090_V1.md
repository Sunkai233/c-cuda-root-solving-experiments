# Real-table BEM fixed-step divergence ablation on RTX 5090 (V1)

## Result

The fixed-step low-divergence candidate is a negative performance result on the
frozen 2,448,000-state real-table BEM dataset. Replacing convergence-dependent
early termination with exactly 44 bisection steps preserved numerical results,
but increased RTX 5090 kernel time by 34.55%.

| Path | CPU solve (ms) | GPU kernel mean (ms) | GPU end-to-end (ms) | GPU throughput (roots/s) | Failures |
|---|---:|---:|---:|---:|---:|
| Early-stop bisection | 6,762.403 | 46.796 | 51.067 | 52,311,804 | 0 |
| Fixed 44-step bisection | 8,855.363 | 62.963 | 67.057 | 38,880,132 | 0 |

The fixed path reduced GPU throughput by 25.68% and increased conservative
end-to-end time by 31.31%. It is therefore rejected as the default path for this
dataset. The likely interpretation is that saved warp-control overhead is smaller
than the cost of residual evaluations performed after many lanes have converged.
Without Nsight Compute this causal explanation remains an inference, not a
measured warp-efficiency claim.

## Numerical equivalence

- Both paths: 2,448,000/2,448,000 solved, zero failures, and the same 81,679
  states above 1e-3 rad versus the non-oracle OpenFAST public `Phi` channel.
- Fixed versus early-stop roots: zero differences above 1e-8 rad; maximum
  circular difference 5.6835e-9 rad on both CPU and GPU.
- CPU versus GPU: early-stop is bit-identical; fixed-step has zero differences
  above 1e-8 rad and maximum difference 3.5705e-13 rad.

The 44-step count was selected analytically: it reduces an initial pi/2 bracket
below 9e-14 rad. It was not selected after observing performance results.

## Protocol and evidence

Both paths were compiled into the same strict-FP64 SM120 CUDA binary and selected
by a runtime algorithm identifier. Measurements used two warm-ups and 30 kernel
repetitions on one RTX 5090. The combined kernel used 70 registers, a 136-byte
stack frame, and no spills. End-to-end timing copies the frozen five-array input
buffer H2D and roots/status D2H.

Reproduce on abc66:

```bash
bash scripts/run_bem_low_divergence_rtx5090.sh
```

Evidence is append-only under:

`results_raw/20260824T062936Z_bem_real_low_divergence_rtx5090/`

This closes the fixed-step versus early-stop portion of E5. A compact difficult-
sample queue with a second correction kernel and direct warp metrics remain
separate work; the second GPU architecture remains deferred by the user.
