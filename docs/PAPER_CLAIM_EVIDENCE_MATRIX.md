# 论文主张—实验结果—原始证据—适用边界取证矩阵

## 1. 用途与冻结基线

本文档是进入论文写作前的唯一主张入口，不是论文大纲。每个正文数字必须先能映射到本矩阵中的权威报告和机器可读证据。

- 实验取证基线：`a6d2cdeda9fc6667007cf97a209edd8fd1d0c5dd`
- 论文仓库核对基线：`edd79728312bc71fa5b35b12e8c018dae7f34ecf`
- 历史验收范围：E0–E7、E9–E11，曾排除E8；2026-08-26已完成RTX 5090/V100首轮跨架构复现，扩展五卡矩阵仍在执行。
- 机械审计：`results_processed/final_acceptance_audit.json`，`passed=62`、`total=62`、`all_pass=true`。

状态定义：

- **可写**：有冻结正确性和与主张对应的正式统计证据。
- **限定后可写**：结果有效，但必须同时写硬件、规模、比较对象、计时口径或抽样边界。
- **负结果**：实验完成，但候选不构成正向贡献。
- **禁止写**：当前证据不能支持，或与冻结结果冲突。

## 2. 核心取证矩阵

| ID | 论文主张的合规写法 | 权威实验结果 | 权威报告 | 机器可读或原始证据 | 适用边界 | 状态 |
|---|---|---|---|---|---|---|
| C01 | 冻结的五域自适应求解器在全新 test 中，各域 600 个样本均未观察到失败。 | 五域均 0/600 错根或非有限；根最大误差约 `2.820e-8`–`2.999e-8`；0/600 对应 Wilson 95% 失败率上界 0.636%。 | `FROZEN_CORRECTNESS_V3.md` | `results_raw/20260824T073512Z_frozen_test_v3_rtx5090/frozen_analysis.json`、`validation_test.csv`、`manifests/frozen_adaptive_v3.json` | 只能写“未观察到失败”，不能写数学保证或 100% 普遍正确。 | 可写 |
| C02 | 真实翼型表 BEM 的冻结两阶段求解器在独立 80 位 holdout 上通过根、分支和有限性门槛。 | 1,000 个不重叠 test：根误差中位数 `7.08e-13 rad`、最大 `5.49e-10 rad`，错根与非有限均为 0。 | `BEM_REAL_FROZEN_RTX5090_V1.md` | `results_raw/20260824T083743Z_bem_real_frozen_test_rtx5090/`、`references/bem_real_ref_v2_test_20260824/`、一次性 test marker | 是对该 holdout 和冻结物理分支规则的经验结论。 | 可写 |
| C03 | 固定 44 步低分歧实现没有带来性能收益。 | 相对早停 bisection，kernel 从 `565.957` 增至 `700.705 ms`，慢 23.8%；E2E 从 `573.189` 增至 `708.048 ms`。 | `BEM_REAL_ALGORITHM_MATRIX_RTX5090_V2.md`、`NSIGHT_COMPUTE_RTX5090_V1.md` | `results_raw/20260824T103653Z_bem_real_algorithms_v2_rtx5090/`、Nsight CSV | 减少控制流不等于更快；不能把 fixed44 写成有效优化。 | 负结果 |
| C04 | 得到支持的低分歧方案是“局部快速扫描 + 索引紧凑 + robust Brent 回退”的两阶段 compacted adaptive。 | 真实 600 s、2,448,000 状态：94.48% 快速路径、5.52% 回退；相对完整 Brent，kernel `3.601× [3.591,3.609]`，E2E `3.521× [3.514,3.528]`。 | `BEM_REAL_ALGORITHM_MATRIX_RTX5090_V2.md` | `results_processed/bem_algorithms_v2/bem_algorithms_v2_bootstrap.csv`、对应原始运行目录 | RTX 5090、12 m/s 基线、相同严格 FP64 残差与冻结分支规则；方法分块顺序运行。 | 限定后可写 |
| C05 | O(1) 极坐标 LUT 在本实现和本硬件上没有性能收益。 | binary/LUT kernel 比 `0.99750 [0.99433,0.99947]`，E2E 比 `0.99566 [0.99295,0.99797]`；LUT 慢约 0.25%–0.44%，最大根差为 0。 | `BEM_SCALE_CONDITION_ABLATIONS_RTX5090.md` | `results_processed/bem_ablations_v1/`、`results_raw/20260824T085641Z_bem_lut_ablation_rtx5090/` | 顺序运行可能含次序系统误差；无论如何不能列为正向工程锁。 | 负结果 |
| C06 | 纯 FP32 和无门控 FP32+df32 虽快但未通过冻结正确性，不能作为合格性能方案。 | v3 test 中 FP32+df32 出现两个错交点；真实状态性能中 FP32/无门控 df32 分别有 888/922 个失败。 | `BEM_REAL_PRECISION_PATHS_RTX5090_V1.md` | `results_raw/20260824T102142Z_bem_real_precision_frozen_test_rtx5090/`、`results_raw/20260824T103200Z_bem_real_precision_performance_rtx5090/` | 快速但不合格的 Pareto 端点；不得用吞吐掩盖正确性失败。 | 负结果 |
| C07 | 带严格 FP64 物理/残差门的 `df32_adaptive` 是本组唯一同时通过冻结正确性且显著快于 FP64 的精度路径。 | 全新 v4 holdout 1,000/1,000 未观察到失败，最大根误差 `6.217e-15`；真实状态 E2E 相对 FP64 为 `8.151× [8.132,8.160]`，回退 0.04%。 | `BEM_REAL_PRECISION_PATHS_RTX5090_V1.md` | `references/bem_real_ref_v4_df32_adaptive_test_20260824/`、`results_raw/20260824T102831Z_bem_real_precision_v2_frozen_test_rtx5090/`、性能原始目录 | RTX 5090、真实 BEM 数据与当前冻结门；v4 没触发回退不证明门可删除。 | 限定后可写 |
| C08 | 原始 FP32→FP64 adaptive 因回退率过高而没有加速。 | 回退 97.59%；相对 FP64 的 E2E 比为 `0.945 [0.942,0.947]`，即慢约 5.8%。五域冻结 adaptive 性能也均慢于直接 FP64。 | `BEM_REAL_PRECISION_PATHS_RTX5090_V1.md`、`GPU_PERFORMANCE_V3_RTX5090.md` | `results_raw/20260824T103200Z_bem_real_precision_performance_rtx5090/`、`results_processed/gpu_performance_v3/` | 不能把理论混合精度优势替代实测结果。 | 负结果 |
| C09 | RTX 5090 相对充分优化的 EPYC 9654 OMP96，在最大规模上仅对四个迭代域取得分域 E2E 加速。 | N=`16,777,216`：BEM `1.338×`、Kepler `1.760×`、PV `1.254×`、CSTR `2.523×`；Peng–Robinson 为 `0.245×`，CPU 快约 4.07×。 | `CPU_C17_PERFORMANCE_V1.md`、`GPU_PERFORMANCE_V3_RTX5090.md` | `results_processed/cpu_c17_v1/`、`results_raw/20260824T075559Z_cpu_c17_full/`、GPU v3 原始目录 | 必须写 RTX 5090、EPYC 9654 OMP96、N、严格 FP64、E2E；不能概括为“GPU 对所有求根更快”。 | 限定后可写 |
| C10 | 真实 BEM 中，两阶段 adaptive 的 RTX 5090 E2E 相对 EPYC 9654 OMP96 为约 5.13×。 | GPU E2E `131.47 ms`，CPU OMP96 `674.54 ms`，加速 `5.131× [5.120,5.139]`；CPU adaptive 的 serial/OMP96 并行比为 `12.85×`，不是 GPU 加速比。 | `BEM_REAL_CPU_GPU_V1.md` | `results_processed/bem_cpu_gpu_v1/bem_cpu_gpu_bootstrap.csv`、CPU/GPU 原始目录 | 2,448,000 状态、12 m/s 工况、同语义残差和分支规则；不可写成普遍“千倍端到端”。 | 限定后可写 |
| C11 | “GPU 千倍加速”不能作为普遍结论。 | 新公平基准对 OMP96 为 `1.18×`–`2.52×`（分域）或真实 BEM adaptive `5.13×`；旧 `1003×/2017×` 来自特定 standalone、单核/双卡或不同口径。 | `CPU_C17_PERFORMANCE_V1.md`、`BEM_REAL_CPU_GPU_V1.md`；旧值仅作历史映射 | 新 CPU/GPU 原始目录；旧 `RESULTS*.txt` 需单独标明历史硬件、规模和分母 | 若保留旧数字，句内必须同时给出硬件、N、精度、单核/多核、kernel/E2E、单卡/双卡；否则禁止。 | 禁止写（无边界版本） |
| C12 | 专用闭式/半闭式方法在 RTX 5090 上的 kernel 收益会被传输稀释，但部分 E2E 仍显著。 | Mikkola、Lambert-W、解析三次式相对 Brent 的 E2E 95% CI 下界分别 `1.979`、`1.993`、`1.844`；Kepler bracketed secant 和 BEM safeguarded Halley 为负结果。 | `ALGORITHM_PERFORMANCE_RTX5090_V2.md` | `results_raw/20260824T131627Z_algorithm_matrix_v2_rtx5090/`，含 19,500 条重复和 dev/cal 验证 | 专用新候选只有 dev/cal 资格，不冒充冻结 test。 | 限定后可写 |
| C13 | 隐式梯度相对展开反传在隔离消融中降低计算时间和寄存器占用，并与参考梯度一致。 | 展开/隐式融合 `2.3914× [2.3908,2.3918]`；最大相对差 `6.098e-12`；寄存器 128 对 40/thread。 | `REMAINING_CUDA_ABLATIONS_RTX5090.md` | `results_processed/remaining_ablations_v1/`、`results_raw/20260824T100918Z_remaining_ablations_rtx5090/` | 严格 FP64、N=3,342,336 的隔离消融；不能外推为完整应用同倍数。 | 限定后可写 |
| C14 | 多步长整体重求根有限差分、高精度隐式梯度与分支变化标记共同支持可微性实现。 | 五域 FD、真实 BEM 分段 FD、PV 扩展端点均有独立证据；真实 BEM cal 最大最佳步长相对误差 `2.211e-4`。 | `FINITE_DIFFERENCE_GRADIENT_V1.md`、`BEM_REAL_FINITE_DIFFERENCE_V1.md`、`PV_EXTENDED_GRADIENTS_RTX5090_V1.md` | `results_raw/20260824T043754Z_finite_difference_cal/`、真实 BEM FD 与 PV dev/cal/test 原始目录 | 插值节点左右导数分开；跳根步长必须标记，不能用跨分支差分定义单一导数。 | 可写 |
| C15 | CSTR 多根/折叠结果支持“显式分区、历史连续跟踪和近折叠正则化必须分开报告”。 | 三单调区间枚举、连续跟踪、未知历史歧义和正则化梯度均完成验证。 | `CSTR_FOLD_VALIDATION_RTX5090_V1.md` | 对应 CSTR fold 冻结 test 目录、参考集和一次性 marker | 不把正则化梯度冒充奇异点处经典导数；不把历史未知时的分支选择称为唯一真根。 | 可写 |
| C16 | 全局 CUDA fast-math 被拒绝；CPU fast-math 只能逐域、有条件报告。 | CUDA fast-math 导致 CSTR dev/cal 换根；CPU double fast 五域通过冻结门，但性能显著性逐域不同。SIMD pragma 和 PGO 也不是通用收益。 | `FAST_MATH_CANDIDATE_RTX5090.md`、`CPU_FAST_MATH_V1.md`、`CPU_C17_PERFORMANCE_V1.md` | CUDA fast 原始目录、`results_raw/20260824T123709Z_cpu_fast_candidate/`、CPU 编译机器表 | CPU 与 CUDA 编译策略不能混写；不得写“fast-math 无损且普遍加速”。 | 限定后可写 / CUDA 负结果 |
| C17 | 两个新增 OpenFAST 600 s 工况支持方法在所测工况内的正确性与性能，但不证明全风况规律。 | 8 m/s 与 16 m/s 各 2,448,000 状态、0 solver failure；困难 oracle 各 300 点未观察到失败；adaptive/Brent E2E 分别 `1.628×`、`2.321×`。 | `BEM_OPENFAST_MULTICONDITION_V1.md` | `results_raw/20260824T124112Z_openfast_multicondition_v1/`、`results_processed/bem_openfast_multicondition_v1/openfast_multicondition_bootstrap.csv` | 只覆盖 8 m/s IEC C、12 m/s NTM B、16 m/s IEC A；不是风况总体统计。 | 限定后可写 |
| C18 | RTX 5090、V100与A100上，冻结正确性和目标预算得到相同通过结果，但混合精度性能与路由阈值不能直接迁移。 | V100/A100完整门均0错误接受、自适应均0/1000失败、四预算闭合；根+分支证书相对FP64分别仅`0.403×`和`0.388×`，5090冻结路由最坏regret分别为`128.817%`和`69.668%`。 | `E8_CROSS_ARCHITECTURE_V100_A100_RTX5090_V2.md` | V100与A100两个E8原始目录及`results_processed/e8_cross_arch_v1/{v100_sm70,a100_sm80}/` | 当前覆盖Blackwell消费级、Volta与Ampere数据中心GPU；3090/4090未完成前，不能升级为消费级Ampere/Ada或五代普遍规律。 | 限定后可写 / 性能迁移为负结果 |
| C19 | A4 算子融合是约 0.3% 的小幅正贡献，A6 递推是隔离微内核约 2.18×，二者不能被放大为完整求解器收益。 | A4 两 kernel/融合 `1.00308×`；A6 直接 sincos/递推 `2.1766×`，最大差 `1.308e-13`。 | `REMAINING_CUDA_ABLATIONS_RTX5090.md` | `results_processed/remaining_ablations_v1/`、原始消融目录 | A6 仅有序等步长角度预处理微内核。 | 限定后可写 |
| C20 | 极坐标热启动的收益依赖工况匹配，不能称为无条件正贡献。 | cold/warm：低风速 `2.467×`、高风速 `2.580×`、阵风 `1.981×`；基线为 `0.941×`。 | `BEM_SCALE_CONDITION_ABLATIONS_RTX5090.md` | `results_processed/bem_ablations_v1/`、历史提示消融原始目录 | 冷/暖顺序独立运行；基线工况出现负收益。 | 限定后可写 |
| C21 | 完整后验根—分支—梯度门在全新 80 位 test 中未出现错误接受。 | 仅残差 FP32 有 1 次错误接受；完整 FP32/df32 后验门错误接受均为 0；证书 adaptive 1000/1000 未观察到失败。 | `E12_E16_CERTIFICATE_GOAL_ROUTING_RTX5090_V1.md` | `results_raw/20260825T113818Z_e12_e16_certificate_goal_routing_rtx5090/certificate_test/` | sampled majorant 经 test 审计，不是通用严格区间证明；0/1000 不是数学保证。 | 限定后可写 |
| C22 | 完整根+分支证书在真实 BEM 上相对 FP64 仍有显著 E2E 加速。 | 根+分支 `2.268× [2.262,2.271]`；再含梯度证书 `1.931× [1.926,1.934]`。 | 同上 | `results_processed/e12_e16_v1/certificate_performance_bootstrap.csv` | RTX 5090、2,448,000 状态、当前分支见证与编译配置。 | 限定后可写 |
| C23 | 目标导向调度在四个预算上均使实际载荷/转矩误差低于一阶预测上界。 | 四预算全部闭合；1e-5 时载荷误差较 uniform 更小但慢约 5.3%；其他时间差小。 | 同上 | `results_processed/e12_e16_v1/goal_budget_summary.csv` | 输出是一阶聚合载荷/转矩代理；不能写成普遍性能提升或无余项严格定理。 | 限定后可写 |
| C24 | 条件于已知困难比例，层次化路由框架可按硬件校准；RTX 5090冻结阈值不可直接搬到V100或A100。 | RTX 5090自身最大regret 0.128%；搬到V100/A100最大128.817%/69.668%；本地cal在V100最大regret 0，在A100最大1.093%。 | E12–E16报告、E8 V2阶段报告 | 三卡路由统计及`results_processed/e8_cross_arch_v1/{v100_sm70,a100_sm80}/routing.csv` | 受控基准直接提供`p`，未计在线估计开销；离散网格的本地cal结果不能外推到连续`p`或其他GPU。 | 限定后可写 |
| C25 | 完整同区分支见证不可由“到大物理区边界的距离”替代。 | 关闭完整见证的开发版输出误差超过预测预算；正式版四预算全部闭合。 | `CERTIFICATE_GUIDED_ALGORITHM_V1.md`、E12–E16 报告 | 开发失败记录与正式 goal JSON | 同一物理区可有多个交点；必须见证冻结的最近 hint 分支身份。 | 可写（机制性负例） |

## 3. 旧结果与新结果的权威关系

| 旧来源或旧表述 | 当前处置 | 可否与新结果合并 |
|---|---|---|
| 主仓 README 的“GPU 上可千倍加速” | 改为带硬件、N、精度、比较对象和 kernel/E2E 口径的局部历史结果；正文主结论优先采用 C09–C11 的公平新基准。 | 不可直接合并为一个通用速度比。 |
| 主仓 README 和代码索引的“O(1) LUT 工程锁” | 由 C05 推翻；改列正式负结果。 | 不可继续作为正向贡献。 |
| 旧固定步/无分支低分歧叙述 | 由 C03 推翻；真正受支持的是 C04 的两阶段紧凑回退。 | 不可把 fixed44 与 compacted adaptive 混称为同一优化。 |
| B300 制造根 v1 报告 | 已由该仓 v2 权威口径取代；其中 3917×、0 warp waste、B300 FP64 满速等旧结论不得引用。 | 只能在明确标为独立历史实验且使用 v2 真源时引用。 |
| B300 五域与 RTX 5090 新五域 | 硬件、域定义、数据、算法和计时口径不同。 | 只能逐项映射，不能拼接成跨架构趋势；E8 未完成。 |
| 旧 RTX 5090 `RESULTS*.txt` | 保留为早期主实验证据；必须与新真实 BEM 的 51 普通节点/2,448,000 状态口径区分。 | 只有方程、输入、节点定义、精度与计时分母完全一致时才可比较。 |

## 4. 写作硬约束

1. 所有“加速”句必须同时写：硬件、规模、比较对象、精度、kernel 或 E2E、单卡或多卡，以及 95% CI。
2. 只有 95% CI 下界大于 1 且候选通过对应正确性门时，才使用“显著加速”。
3. 所有零失败结果写“在 N 个冻结样本中未观察到失败”，不得写成数学保证。
4. E8 恢复前，不得出现“跨 GPU 架构可迁移”“硬件无关”或同义句。
5. LUT、fixed44、原始 FP32→FP64 adaptive、纯 FP32、无门控 df32 和 CUDA 全局 fast-math必须作为负结果保留。
6. B300 旧实验、旧 RTX 5090 主实验与新补充实验使用独立表格和独立脚注，不混用速度比。
7. OpenFAST 全模型运行时间不得作为根求解内核分母。
8. 若正文数字不在本矩阵中，先补证据映射，再进入论文文本。

## 5. 当前写作阻断项

- 主论文仓库 README 第 9 行的无边界“GPU 上可千倍加速”需要改写。
- 主论文仓库 README 第 19 行的“O(1) LUT 工程锁”需要撤销。
- 投稿论文源及中英文稿仍需逐文件扫描 fixed44、LUT、千倍加速、B300 FP64 和跨硬件措辞。
- 旧 B300、旧 RTX 5090 和新 RTX 5090 数字尚需形成逐字段映射表；完成前不得汇总成同一性能图表。
