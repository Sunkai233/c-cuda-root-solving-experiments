# 最终验收：E0–E11（仅排除 E8 跨硬件）

## 验收结论

按用户 2026-08-24 的明确范围修改——“跨硬件先不做，其他都做好”——E0–E7、E9–E11 的执行、原始证据、统计分析和报告均已完成。E8 是唯一排除项；同型号的第二张 RTX 5090 没有被冒充为第二类架构。本仓库只能主张 RTX 5090 与 AMD EPYC 9654 上的结果，不能主张跨 GPU 架构可迁移性。

这里的“完成”指实验矩阵与失败记录完整，不指所有候选都成功。全局 CUDA fast-math、纯 FP32、无门控 df32、固定 44 步、O(1) 极坐标 LUT、原始 FP32→FP64 adaptive，以及 Peng–Robinson 的部分 GPU/CPU比较均得到负结果并原样保留。

## E0–E11 证据映射

| 实验 | 状态 | 权威证据 | 结论边界 |
|---|---|---|---|
| E0 高精度正确性 | 完成 | `FROZEN_CORRECTNESS_V3.md`、`BEM_REAL_FROZEN_RTX5090_V1.md` | 55 位真源、80 位互证；只写“未观察到失败” |
| E1 批量扩展 | 完成 | `GPU_PERFORMANCE_V3_RTX5090.md`、`CPU_C17_PERFORMANCE_V1.md` | 13 个规模至 16,777,216；CPU/GPU crossover 分域报告 |
| E2 算法比较 | 完成 | `ALGORITHM_PERFORMANCE_RTX5090_V2.md`、`BEM_REAL_ALGORITHM_MATRIX_RTX5090_V2.md` | 通用与专用算法齐全；专用新候选是 dev/cal 资格，不冒充冻结 test |
| E3 精度比较 | 完成 | `BEM_REAL_PRECISION_PATHS_RTX5090_V1.md`、`DF32_RTX5090_V1.md` | 只有 df32_adaptive 同时通过冻结正确性并显著快于 FP64 |
| E4 自适应纠错 | 完成 | `FROZEN_CORRECTNESS_V3.md`、`BEM_REAL_PRECISION_PATHS_RTX5090_V1.md` | 阈值只由 dev/cal 冻结；失败的 V2 test 保留，V3 用全新真源 |
| E5 低分歧 | 完成 | `BEM_REAL_ALGORITHM_MATRIX_RTX5090_V2.md`、`NSIGHT_COMPUTE_RTX5090_V1.md` | fixed44 为负；两阶段 compacted adaptive 为正；直接 warp 指标已记录 |
| E6 可微性 | 完成 | `FINITE_DIFFERENCE_GRADIENT_V1.md`、`BEM_REAL_FINITE_DIFFERENCE_V1.md`、`PV_EXTENDED_GRADIENTS_RTX5090_V1.md` | 高精度隐式梯度、整体重求根多步长 FD、分支变化标记三重核验 |
| E7 多根与折叠 | 完成 | `CSTR_FOLD_VALIDATION_RTX5090_V1.md` | 三单调区间枚举、连续跟踪、未知历史歧义与正则化梯度分开 |
| E8 跨硬件 | **用户排除** | `manifests/final_scope_no_e8_v1.json` | 未执行；无迁移性主张 |
| E9 端到端 | 完成 | `GPU_PERFORMANCE_V3_RTX5090.md`、`BEM_REAL_CPU_GPU_V1.md`、`BEM_OPENFAST_MULTICONDITION_V1.md` | H2D+kernel+D2H 与 kernel 分列；只在 CI 下界>1 时称显著加速 |
| E10 消融 | 完成 | 下表 A0–A10 | 每个隔离实验保留数值语义检查；负结果不删除 |
| E11 编译策略 | 完成 | `CPU_FAST_MATH_V1.md`、`FAST_MATH_CANDIDATE_RTX5090.md`、`CPU_C17_PERFORMANCE_V1.md` | CPU strict/fast/LTO/PGO 分开；CUDA 全局 fast-math 因换根拒绝 |

## A0–A10 消融闭环

| 消融 | 对照与结果 | 判定 |
|---|---|---|
| A0 FULL | 冻结严格/自适应完整路径，作为各消融共同基线 | 基线 |
| A1 关闭低分歧固定步/分流 | fixed44 相对早停 bisection kernel 慢 23.8%；compacted adaptive 相对完整 Brent E2E 快 3.521× | fixed 负；分流正 |
| A2 关闭条件感知精度调度 | 原始 FP32→FP64 adaptive 回退 97.59%，E2E 仅为 FP64 的 0.945× | 负；高回退抵消收益 |
| A3 关闭选择性纠错 | 无门控 df32 在冻结 v3 出现两个错交点；df32_adaptive 在新 holdout 1000/1000 未观察到失败 | 纠错门必要 |
| A4 关闭算子融合 | 两 kernel/融合 kernel=1.00308 [1.00256,1.00330]，仅约 0.3% | 小幅正贡献 |
| A5 关闭 O(1) 查表 | binary/LUT kernel=0.99750，LUT 反而慢约 0.25% | LUT 负 |
| A6 关闭 sin/cos 增量递推 | 直接 sincos/递推=2.1766 [2.1581,2.1875]，最大差 1.308e-13 | 隔离微内核正；不外推全求解器 2× |
| A7 df32 改为 FP64 | 合格 df32_adaptive 对 FP64 E2E 加速 8.151 [8.132,8.160] | 正 |
| A8 关闭物理热启动 | 低/高风速/阵风 cold/warm=2.467/2.580/1.981；基线为 0.941 | 三变工况正，基线负 |
| A9 梯度改为展开反传 | 展开/隐式融合=2.3914 [2.3908,2.3918]；梯度最大相对差 6.098e-12 | 隐式正 |
| A10 strict/fast math | CUDA fast-math 导致 CSTR dev/cal 换根，拒绝；CPU double fast 五域通过门控且显著性逐域报告 | CUDA 负；CPU 有条件正 |

## 关键验收事实

- 四个主领域与 Peng–Robinson 负对照均有 C17/CUDA 实现；CPU 使用 `-O3 -march=native`，并分别核验 SIMD 报告、OpenMP 96、PGO、LTO/no-LTO 和 fast 候选。热循环没有被编译器向量化，报告没有用无关的 zmm/ymm 指令冒充证据。
- 五域 GPU v3 有 15,600 次正式重复；CPU C17 有 7,800 次；算法 v2 有 19,500 次；真实 BEM CPU 有 240 次；每个新增 OpenFAST 工况有 90 次 GPU 正式重复。
- 根、残差、梯度、分支和非有限值均有独立参考/失败清单。一次性 test marker 与失败的冻结候选永久保留。
- Nsight Compute 已直接记录 occupancy、warp execution、uniform branch、cache/DRAM、寄存器、local sectors 与 stall；profiler replay 时间未用于正式性能。
- 真实 BEM 多工况已覆盖 8 m/s IEC C、12 m/s NTM B 和 16 m/s IEC A。新增两个工况各有 900 个算法-样本 oracle 核验（3 方法×300），均未观察到阈值失败；工况范围仍不是所有风况的统计总体。
- 原始目录记录编译日志、硬件/驱动、温度/功耗/时钟、输入 manifest、源与参考 SHA-256。服务器最后核验 384 个 governor 全部恢复 `schedutil`。

## 最终机械审计

`scripts/audit_final_no_e8.py` 对范围、报告、一次性 marker、重复行数、COMPLETE 标记、专用方法集合、CPU 验证、OpenFAST 结构/有限性、两工况 oracle 与每算法 30 次重复进行机器检查。审计结果写入 `results_processed/final_acceptance_audit.json`；只有全部检查通过，本报告才作为最终验收入口。

原规范“至少两种 GPU”的条款没有被证明满足，而是被用户明确缩小范围。若以后恢复 E8，必须使用真正不同架构并重新执行冻结正确性与正式计时，不能用第二张同型号 RTX 5090 补名义数量。
