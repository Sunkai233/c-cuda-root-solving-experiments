# Real-table BEM algorithm matrix on RTX 5090 (V1)

## Result

The deferred real-table timing stage is complete for one GPU architecture. The
frozen dataset contains 2,448,000 ordinary blade-element states exported from a
600 s, 48,000-step OpenFAST/NREL 5 MW run. All solvers use the same FP64 legacy
BEM residual, eight real airfoil polar tables, geometry, region ordering, and
stopping criteria. The second GPU architecture remains intentionally deferred.

| Algorithm | CPU solve (ms) | GPU kernel mean (ms) | GPU end-to-end (ms) | GPU throughput (roots/s) | Kernel speedup | End-to-end speedup | Failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bisection | 6,772.207 | 46.755 | 51.037 | 52,357,484 | 144.84x | 132.69x | 0 |
| Brent/zeroin | 2,024.205 | 17.017 | 21.221 | 143,852,643 | 118.95x | 95.39x | 0 |
| Illinois regula falsi | 6,349.423 | 49.687 | 53.897 | 49,268,443 | 127.79x | 117.81x | 0 |

Brent is the best measured candidate: 3.35x faster than bisection on the serial
CPU and 2.75x faster in the GPU kernel in this same run. Speedups above always
compare the GPU method with its matching serial CPU method from this run.

## Numerical checks

- CPU and GPU each solved all 2,448,000 states with zero solver failures.
- CPU versus GPU root files were compared record by record using circular angle
  distance. Bisection and Illinois were bit-identical. Brent had zero differences
  above 1e-8 rad and a maximum difference of 5.80e-12 rad.
- Illinois and bisection produced identical roots for every state.
- Brent selected a different crossing from bisection in 944 states (0.03856%).
  Every disagreement occurs at the three outermost ordinary nodes: 149, 548,
  and 247 cases at zero-based nodes 14, 15, and 16. The root separations are
  0.01347--0.06587 rad (median 0.05147 rad). These are alternate crossings in
  a strongly nonlinear region, not CPU/GPU numerical drift.
- Against OpenFAST's public `Phi` channel, Brent is closer in 755 of those 944
  alternate-crossing cases and bisection in 189. This is only an engineering
  cross-check: the public `Phi` is recomputed after induction/correction updates
  and is not a strict oracle for this frozen residual.

The OpenFAST comparison therefore must not be described as a CUDA wrong-root
rate. It is valid to claim CPU/GPU agreement for each frozen algorithm and to
report the explicitly observed multi-crossing sensitivity between algorithms.

## Measurement protocol

- CPU: serial C17, `gcc -O3 -march=native`; solve-only wall time.
- GPU: RTX 5090 device 0, compute capability 12.0, driver 580.105.08;
  CUDA SM120 strict-FP64 build (`--fmad=true`, `--ftz=false`, precise division
  and square root); two warm-ups and 30 measured kernel repetitions.
- End-to-end time is a conservative pinned-host transfer measurement: the full
  five-array dataset buffer is copied H2D, followed by the kernel and root/status
  D2H copies.
- The combined algorithm kernel used 70 registers, a 136-byte stack frame, and
  zero spill loads/stores according to `ptxas`.
- Host CPU: AMD EPYC 9654. Only one CPU thread and one RTX 5090 were used.

## Reproducibility and evidence

Run from `/home/abc/supplementary_experiments` on the abc66 host:

```bash
bash scripts/run_bem_algorithm_matrix_rtx5090.sh
```

Evidence directory:

`results_raw/20260824T062208Z_bem_real_algorithm_matrix_rtx5090/`

It contains CPU/GPU JSON measurements, all six FP64 root arrays, pairwise
CPU/GPU comparisons, compiler resource output, hardware manifests, source/data
SHA-256 values, and the focused Brent disagreement analysis. The frozen dataset
is `results_raw/20260824T060500Z_bem_real_dataset_v2/bem_real_f64_soa.bin`.

## Scope boundary

This completes the real-table one-GPU algorithm matrix. The separate fixed-step
versus early-stop ablation is reported in
`BEM_REAL_LOW_DIVERGENCE_ABLATION_RTX5090_V1.md`. The user-deferred second GPU,
a compact fallback queue, and direct warp profiling are not included. OpenFAST
public output channels are not an independent high-precision oracle for the
frozen legacy residual.
