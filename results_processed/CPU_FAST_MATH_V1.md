# CPU strict / fast-math / LTO 编译策略（E11）

运行 `20260824T123709Z_cpu_fast_candidate` 将 GCC 13.3.0 的三个 C17 OMP96 构建分开：严格 LTO（来自正式 CPU 主矩阵）、`-ffast-math` + LTO、严格 no-LTO。所有构建使用 `-O3 -march=native -mtune=native`、物理 CPU 0–95、NUMA node 0、performance governor；性能均为 10 次预热、30 次正式重复。跨构建顺序运行，CI 为 10,000 次独立 bootstrap。

## 正确性门控

fast 求解函数使用 `optimize("fast-math")`，而误差统计函数保持严格语义，避免 `-ffinite-math-only` 把验证器自身的 `isfinite` 优化掉。fast 先运行 v3 dev/cal；两者通过后才运行一次 test。五域各 600 点 test 均 0 个根超限、0 个梯度超限、0 非有限：

| 域 | root max | gradient relative max |
|---|---:|---:|
| BEM smooth | 2.220e-16 | 9.116e-16 |
| Kepler | 7.827e-14 | 3.185e-11 |
| PV | 1.510e-14 | 5.598e-15 |
| CSTR | 3.331e-16 | 9.096e-15 |
| Peng–Robinson | 1.640e-13 | 5.677e-10 |

严格 no-LTO 也通过同一 test；状态分别为 `FAST_CANDIDATE_TEST_PASS` 与 `NO_LTO_TEST_PASS`。这说明 CPU 双精度 fast-math 候选在本冻结解析域内可用，但不能外推到真实分段翼型表 BEM，也不能覆盖未观察样本。

## N=16,777,216 性能

比值为“严格 LTO / 候选”；大于 1 表示候选更快。

| 候选 | BEM | Kepler | PV | CSTR | Peng–Robinson |
|---|---:|---:|---:|---:|---:|
| CPU fast-math + LTO | 1.011 [1.010,1.012] | 1.048 [1.047,1.049] | 1.270 [1.267,1.272] | 1.070 [1.069,1.071] | 1.120 [1.112,1.125] |
| CPU strict no-LTO | 0.999 [0.999,1.000] | 1.002 [1.001,1.002] | 1.003 [1.002,1.004] | 1.001 [1.000,1.002] | 0.991 [0.984,0.997] |

fast-math 在五域 Nmax 均显著加速，PV 的 `exp` 路径收益最大约 27.0%。LTO 不是普遍收益：BEM 的 CI 跨 1；no-LTO 在 Kepler/PV/CSTR 略快，LTO 只在 PR 显著快约 0.87%。因此 E11 的结论按“平台 × 领域”保留，不把编译开关写成无条件优化。

CUDA 的全局 `--use_fast_math` 仍被拒绝：它在开发/校准 CSTR 中改变了符号变化分类和物理分支。CPU 此处使用双精度 GCC 变换且重新通过了冻结 test；两者不是同一数值路径，不能互相替代。

机器可读性能：`results_processed/cpu_compilation_v1/cpu_fast_performance_bootstrap.csv`。原始性能、dev/cal/test 逐样本误差、编译日志、状态和 SHA-256 位于 `results_raw/20260824T123709Z_cpu_fast_candidate/`。
