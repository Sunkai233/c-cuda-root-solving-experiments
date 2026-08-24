# C17 CPU 正式性能与 RTX 5090 交叉点

正式运行 `20260824T075559Z_cpu_c17_full` 在 AMD EPYC 9654（96 个物理核心）上完成。CPU governor 全程为 `performance`；串行与 `omp simd` 固定 core 0，OpenMP 固定物理 CPU 0–95、NUMA node 0。GCC 13.3.0，严格构建为 C17 `-O3 -march=native -mtune=native -flto -fopenmp`，10 次预热、30 次正式重复，不删除慢样本。五域 × 13 个规模 × 4 个模式均各 1,950 条原始重复，非有限计数全部为 0。

## 最大规模 N=16,777,216

| 域 | serial ms | `omp simd` 1T ms | OMP96 ms | PGO OMP96 ms | serial/OMP96 (95% CI) | CPU OMP96 / GPU FP64 E2E (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| BEM smooth | 22,714.83 | 22,716.90 | 284.92 | 301.51 | 79.72 [79.69,79.75] | 1.338 [1.337,1.339] |
| Kepler | 17,600.23 | 17,603.07 | 232.96 | 232.63 | 75.55 [75.50,75.60] | 1.760 [1.758,1.761] |
| PV | 13,150.89 | 13,201.34 | 186.25 | 186.36 | 70.61 [70.55,70.66] | 1.254 [1.253,1.256] |
| CSTR | 56,935.23 | 56,961.29 | 814.67 | 812.16 | 69.89 [69.82,69.92] | 2.523 [2.521,2.525] |
| Peng–Robinson | 998.80 | 997.92 | 15.33 | 15.13 | 65.15 [64.94,65.50] | 0.245 [0.244,0.246] |

最后一列大于 1 表示 RTX 5090 的严格 FP64 端到端更快。GPU 在 BEM、Kepler、PV、CSTR 的 Nmax 显著更快；解析三次负对照由 CPU OMP96 快约 `1/0.245 = 4.07×`，因此不存在“GPU 对所有求根都更快”的结论。相对 OMP96 的持续 GPU E2E 交叉点（该 N 及所有更大 N 的 CI 下界均大于 1）为：BEM/Kepler/CSTR `N=32,768`，PV `N=524,288`；Peng–Robinson 不存在交叉点。

跨 CPU 模式和跨设备运行是顺序独立实验，95% CI 使用 10,000 次独立 bootstrap，不把相同 repetition 编号伪装成同时配对观测。GPU 数据来自冻结运行 `20260824T092702Z_performance_gpu_v3_rtx5090` 的严格 FP64 E2E。

## SIMD 与 PGO 结果

编译器向量化报告中 `optimized: loop vectorized` 为 0；三条热批量循环均报告 `couldn't vectorize`，原因包括 `solve_one` 结构体返回和数据依赖控制流。反汇编全文件虽有 2 条 zmm、14 条 ymm 命中，但不能证明热求解循环已向量化。实测 serial/`omp simd` 在 BEM/Kepler 的 CI 跨 1，CSTR/PV 略慢，PR 仅快约 0.09%；故 SIMD pragma 是正式负结果，不能宣称 AVX-512 加速。

PGO 只用 `pgo_training_development.csv` 的开发负载训练。相对严格 OMP96，PGO 在 Nmax 对 CSTR、Kepler、PR 分别快约 0.31%、0.14%、1.35%，PV 的 CI 跨 1，而 BEM 慢约 5.8%。PGO 同样不是通用收益，不进入默认 BEM 构建。

机器可读结果位于 `results_processed/cpu_c17_v1/`；原始 CSV、编译日志、向量化报告、反汇编、硬件/NUMA/affinity 清单及源码 SHA-256 位于 `results_raw/20260824T075559Z_cpu_c17_full/`。远端同步部署的最小源码快照 commit 为 `080e4b1fef06c166fe5bfc5c56b13d557a9e1845`。
