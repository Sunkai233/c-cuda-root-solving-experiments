# 真实翼型表 BEM 同语义算法矩阵 V2（RTX 5090）

本报告取代 V1。所有方法使用同一严格 FP64 残差、512 单元物理区枚举和冻结规则“第一个有效物理区内，选择离上一时刻 hint 最近的认证交点”。在独立 80 位 v1 参考的 3,000 个样本上，bisection/Brent/Illinois/fixed44/两阶段 adaptive 均 0 个大于 1e-7、0 错分支、0 非有限；最大根误差分别 2.179e-8、1.288e-8、2.179e-8、1.301e-13、1.288e-8。

运行 `20260824T103653Z_bem_real_algorithms_v2_rtx5090`，真实 600 s 的 2,448,000 状态，10 次预热、30 次正式重复：

| 方法 | kernel ms | E2E ms | throughput roots/s | fast/fallback |
|---|---:|---:|---:|---:|
| Bisection | 565.957 | 573.189 | 4.324 M | 0 / 100% |
| Brent | 458.155 | 462.849 | 5.345 M | 0 / 100% |
| Illinois | 577.726 | 583.472 | 4.237 M | 0 / 100% |
| Fixed 44-step bisection | 700.705 | 708.048 | 3.494 M | 0 / 100% |
| compacted adaptive Brent | 127.129 | 131.493 | 19.272 M | 94.48% / 5.52% |

adaptive 的第一个 kernel 只在历史提示附近扫描冻结的 16 个单元，未能认证的索引原子紧凑后由第二个 robust Brent kernel 处理。相对完整 Brent，kernel 为 3.601× [3.591,3.609]、E2E 为 3.521× [3.514,3.528]；区间来自 10,000 次成对 bootstrap，机器可读表见 `results_processed/bem_algorithms_v2/bem_algorithms_v2_bootstrap.csv`。五个方法 solver failure 均为 0。

数据集二进制的 `PhiRef` 是 OpenFAST 工程通道而非本冻结残差的 oracle，因此运行 JSON 中相同的 `branch_error_gt_1e-3=81587` 只表示与该工程通道的差异，不能称为算法错根。正确性唯一依据是独立多精度 holdout。

五个方法按顺序而非完全交错运行；bootstrap 量化组内重复噪声，不能消除方法顺序的系统偏差。adaptive 的优势超过 3.5×，远大于观察到的毫秒级漂移，但最终报告仍保留此限制。

A1 低分歧消融也按当前根规则重测：fixed44 在 3,000 个多精度样本上误差更小且 0 失败，但相对早停 bisection，kernel 从 565.96 增到 700.71 ms（慢 23.8%），E2E 从 573.19 增到 708.05 ms。固定步减少控制流并不自动抵消多余残差评估，故仍为正式负结果。
