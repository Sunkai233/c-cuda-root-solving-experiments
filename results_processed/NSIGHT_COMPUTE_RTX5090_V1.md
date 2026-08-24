# Nsight Compute profiling（RTX 5090）

所有条目使用 Nsight Compute `--set full`，每份报告只捕获一个目标 launch；profiler 的 replay 时间不得作为性能计时。

| profile | duration ms | occupancy % | active warps/cycle | eligible warps/cycle | uniform branch % | warp exec % | DRAM active % | L1 hit % | L2 hit % | registers/thread | local LD/ST sectors | branch stall | scoreboard stall | math stall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| adaptive_domain0_n131072 | 2.367 | 43.29 | 20.78 | 0.1056 | 92.65 | 49.09 | 0.185 | 98.78 | 95.73 | 66 | 0/2.155e+06 | 0.2671 | 0.3178 | 0.007131 |
| adaptive_domain1_n131072 | 1.176 | 44.66 | 21.44 | 0.1135 | 89.96 | 78.34 | 0.3172 | 98.1 | 91.66 | 66 | 0/2.059e+06 | 0.3539 | 0.7799 | 0.01834 |
| adaptive_domain2_n131072 | 1.458 | 44.03 | 21.13 | 0.09932 | 92.66 | 95.72 | 0.2978 | 99.29 | 63.25 | 66 | 0/0 | 0.3545 | 0.4975 | 0.002914 |
| adaptive_domain3_n131072 | 4.062 | 44.97 | 21.58 | 0.1261 | 97.34 | 38.09 | 0.2218 | 84.65 | 47 | 66 | 0/0 | 0.2387 | 0.1019 | 0.01886 |
| adaptive_domain4_n131072 | 120.3 | 43.64 | 20.95 | 0.1151 | 94.81 | 41.75 | 3.039 | 81.55 | 52.93 | 66 | 0/4.413e+04 | 0.3269 | 3.244 | 0.01353 |
| bem_real_algorithm0 | 63.91 | 40.71 | 19.54 | 0.093 | 92.68 | 50.97 | 0.105 | 96.41 | 88.43 | 72 | 1.433e+06/2.892e+07 | 0.264 | 0.1721 | 0.009044 |
| bem_real_algorithm3 | 85.69 | 40.81 | 19.59 | 0.09352 | 92.41 | 54.5 | 0.08973 | 97.4 | 92.93 | 72 | 1.433e+06/3.855e+07 | 0.2651 | 0.1664 | 0.008994 |

`bem_real_algorithm0` 是提前停止二分，`bem_real_algorithm3` 是固定 44 步低分歧二分。二进制 `.ncu-rep` 与完整宽表 CSV 保存在远端 `profiles/`，SHA-256 记录于 `profiles/sha256.txt`。
