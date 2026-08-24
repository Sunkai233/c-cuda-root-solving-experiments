# RTX 5090 首轮工程摸底报告

Run ID: `20260824T001143Z_all_rtx5090_adaptive`

CPU/GPU 等量重复修正版 Run ID:
`20260824T001552Z_all_rtx5090_adaptive`。下文首张表保留首轮审计值；正式讨论
本阶段摸底性能时应优先使用修正版。

## 可用性结论

本轮证明 RTX 5090 CUDA 路径已经打通，并完成 5 个领域、13 个批量规模、
最大 16,777,216 样本的运行。它是实现和计时链路的工程摸底，不是论文正式
结果。不得用本轮数字宣称已经满足 `SUPPLEMENTARY_EXPERIMENTS_C_CUDA.md`
第 20 节验收标准。

## 16M 样本结果

| 领域 | GPU adaptive (ms) | CPU 128T (ms) | 比值 CPU/GPU | GPU Mroot/s | 最大抽检根误差 | FP64 纠错率 |
|---|---:|---:|---:|---:|---:|---:|
| BEM smooth | 160.232 | 201.504 | 1.26 | 104.71 | 9.99e-8 | 42.7% |
| Kepler | 79.536 | 183.582 | 2.31 | 210.94 | 1.00e-7 | 82.8% |
| PV diode | 98.604 | 118.553 | 1.20 | 170.15 | 9.98e-8 | 93.8% |
| CSTR | 110.050 | 124.006 | 1.13 | 152.45 | 9.97e-8 | 75.5% |
| Peng--Robinson-style cubic | 29.939 | 36.565 | 1.22 | 560.38 | 1.00e-7 | 53.0% |

## 16M 等量重复修正版

CPU 与 GPU 均使用 10 次预热、30 次正式重复：

| 领域 | GPU adaptive (ms) | CPU 128T (ms) | 比值 CPU/GPU | GPU Mroot/s | 持续领先起点 |
|---|---:|---:|---:|---:|---:|
| BEM smooth | 159.691 | 204.652 | 1.28 | 105.06 | 32,768 |
| Kepler | 79.213 | 185.462 | 2.34 | 211.80 | 32,768 |
| PV diode | 98.322 | 121.143 | 1.23 | 170.63 | 32,768 |
| CSTR | 109.789 | 123.706 | 1.13 | 152.81 | 32,768 |
| Peng--Robinson-style cubic | 29.573 | 36.305 | 1.23 | 567.31 | 524,288 |

“持续领先起点”定义为该规模及其后所有已测更大规模中 GPU 中位时间均小于
CPU 128 线程中位时间。这里仍没有 bootstrap 置信区间，不能把比值直接写成
统计显著加速。

这些加速比只比较当前固定预算 adaptive kernel 与当前 OpenMP 路径，且仅为
纯 kernel 时间对 CPU solve 时间；还没有端到端 H2D/D2H 对比和 bootstrap CI。

## 追踪与完整性

- GPU: NVIDIA GeForce RTX 5090, compute capability 12.0.
- Driver: 580.105.08; GPU memory: 32,607 MiB.
- CPU: dual-socket AMD EPYC 9654, 384 logical CPUs.
- CUDA compiler: 12.9 in the existing vLLM development container.
- Runtime: CUDA 12.8 base container, using the host NVIDIA driver.
- Strict build: `sm_120`, precise divide/sqrt, FTZ disabled.
- ptxas: adaptive 54 registers/thread, FP64 54, FP32 42; zero spill.
- Raw table: 130 rows; no duplicate `(domain,n,method)` keys; no non-positive or
  non-numeric timing values.

## 为什么还不能进论文主表

1. BEM 仍是光滑解析残差和合成参数，不是 NREL 5MW 57 节点、48,000 步、
   真实翼型查表/OpenFAST 对照。
2. 当前参考根是独立的 binary64 扫描/二分，不是困难样本所需的 >=100-bit
   独立真值；参考梯度三重核验尚未接入。
3. 本轮只跑了 adaptive 路径；Brent/割线/Newton/Halley、FP64/FP32/df32、
   strict/fast、PGO/LTO 和消融矩阵尚未齐全。
4. GPU 纠错仍在同一 kernel 内发生，尚未实现紧凑 fallback 队列和第二 kernel；
   高纠错率也说明阈值/初值/固定步预算尚未完成校准。
5. 首轮 CPU 计时只取 5 次而 GPU 取 30 次，且缺单线程/SIMD 独立报告；因此
   本文件中的首轮 CPU/GPU 性能数字只是摸底。该问题已在后续 run 中改为
   CPU/GPU 均 10 次预热、30 次正式重复，但算法冻结前仍不能作为最终值。
6. 缺端到端计时、功耗采样序列、Nsight Compute 指标、bootstrap 95% CI、
   非劣效性检验和第二类 GPU 的同 commit 复现。
7. 本轮 manifest 为 `git_commit=uncommitted`，最终实验必须先冻结 commit。
