# 真实翼型表 BEM：优化 C17 与 RTX 5090 公平对照

CPU 正式运行 `20260824T120812Z_bem_real_cpu_frozen` 与 GPU 运行 `20260824T103653Z_bem_real_algorithms_v2_rtx5090` 使用同一 `bem_real_solver.h` 残差、真实极坐标表、512 单元物理区枚举、停止规则和“首个有效区域内离历史 hint 最近的认证交点”。输入均为 600 s、2,448,000 个普通节点状态；10 次预热、30 次正式重复。

CPU 是 AMD EPYC 9654，C17 `-O3 -march=native -mtune=native -flto`；serial 固定 core 0，OMP96 固定物理 CPU 0–95 和 NUMA node 0。GPU 是 RTX 5090 严格 FP64，E2E 包含 H2D、求根/压缩回退和 D2H。跨设备与 CPU 模式均为顺序独立运行，CI 使用 10,000 次独立 bootstrap。

## 正确性

CPU 四方法先在独立 80 位 v1 参考的 3,000 点上验证：bisection/Brent/Illinois/adaptive 的最大根误差分别为 `2.179e-8`、`1.288e-8`、`2.179e-8`、`1.288e-8 rad`；四方法均 0 个大于 `1e-7`、0 错分支、0 非有限。全量性能的 serial/OMP96 solver failure 均为 0，且每方法每模式 checksum 在 30 次中唯一。

## 性能

| 方法 | CPU serial ms | CPU OMP96 ms | GPU kernel ms | GPU E2E ms | serial/OMP96 (95% CI) | OMP96/GPU E2E (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| Bisection | 11,645.86 | 680.36 | 565.93 | 572.99 | 17.12 [17.11,17.12] | 1.187 [1.185,1.191] |
| Brent | 8,389.62 | 636.80 | 458.13 | 462.84 | 13.17 [13.17,13.18] | 1.376 [1.375,1.377] |
| Illinois | 11,990.12 | 685.73 | 577.69 | 583.41 | 17.49 [17.48,17.49] | 1.175 [1.174,1.176] |
| Adaptive | 8,668.20 | 674.54 | 127.12 | 131.47 | 12.85 [12.85,12.85] | 5.131 [5.120,5.139] |

对三个完整稳健方法，GPU E2E 相对优化 OMP96 仅快约 1.18–1.38×，远小于对单线程的 18–21×；这正是加入同等级多核 CPU 后的公平结论。两阶段 adaptive 在 GPU 上把 94.48% 样本留在局部快速路径，只压缩 5.52% 到第二个 Brent kernel，因此相对 CPU OMP96 仍有 5.13× E2E 优势。CPU 的 adaptive 在每个样本内部顺序执行相同 hint/fallback 语义，没有假装拥有 GPU 的跨样本紧凑队列；这一实现差异正是被测架构优化的一部分。

OpenFAST 63 s 的 Fortran 全模型运行同时包含结构、入流、气动与输出，不可作为根内核分母；这里只把它作为工程数据生成基线，不混入加速比。

机器可读结果：`results_processed/bem_cpu_gpu_v1/bem_cpu_gpu_bootstrap.csv`。原始 CPU 计时、oracle 失败清单、编译/硬件/源码哈希位于 `results_raw/20260824T120812Z_bem_real_cpu_frozen/`；GPU 原始 JSON 位于 `results_raw/20260824T103653Z_bem_real_algorithms_v2_rtx5090/`。
