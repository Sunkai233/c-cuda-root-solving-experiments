# OpenFAST 多工况真实 BEM 验证与计时（RTX 5090）

## 结论

在原 12 m/s、IEC NTM B、种子 13428 基线之外，已实际生成并运行两个独立 600 s 工况：8 m/s、IEC C、种子 27183，以及 16 m/s、IEC A、种子 39107。两次 OpenFAST 均正常结束，各含 48,000 个非初始时间步、835 个输出通道和 2,448,000 个普通叶素求根状态；形状/通道与有限值审计全部 PASS。

每个工况从同源节点状态、真实叶片几何和极坐标表导出二进制数据，分别对严格 FP64 bisection、Brent 和两阶段 compacted adaptive 做 45 s 热机、10 次预热、30 次正式重复。每个算法的 2,448,000 个输出均为 0 solver failure。独立 80 位 oracle 各抽取 300 个最靠近极坐标插值节点的困难样本；三种算法均 0 个根误差大于 `1e-7`，adaptive 最大根误差分别为 `4.792e-10` 和 `6.218e-10`。这只能表述为“600 个困难样本中未观察到失败”，不是数学保证或总体失败率证明。

## 正式性能

| 工况 | 方法 | kernel 中位数 ms | E2E 中位数 ms | Brent/方法 E2E（95% CI） | fallback | oracle 最大根误差 | 失败 |
|---|---|---:|---:|---:|---:|---:|---:|
| 8 m/s IEC C | bisection | 218.907 | 224.149 | 0.527 [0.524, 0.530] | 100% | 5.351e-10 | 0 |
| 8 m/s IEC C | Brent | 113.656 | 118.203 | 1.000 | 100% | 4.792e-10 | 0 |
| 8 m/s IEC C | adaptive | 68.438 | 72.621 | 1.628 [1.618, 1.637] | 0.302% | 4.792e-10 | 0 |
| 16 m/s IEC A | bisection | 300.307 | 305.253 | 0.612 [0.611, 0.619] | 100% | 6.846e-10 | 0 |
| 16 m/s IEC A | Brent | 180.524 | 186.878 | 1.000 | 100% | 6.218e-10 | 0 |
| 16 m/s IEC A | adaptive | 76.351 | 80.526 | 2.321 [2.318, 2.327] | 0.600% | 6.218e-10 | 0 |

相对 12 m/s 基线 adaptive E2E 131.493 ms，8 m/s 与 16 m/s 的条件/基线比为 0.552 [0.551, 0.553] 和 0.612 [0.611, 0.614]。这不是风速越高必然越慢或越快的规律；主要差别是本次两个新工况的 fallback 比例远低于 12 m/s 基线的 5.52%。

方法按预先固定但非完全交错的顺序分块运行；不同方法的 30 次重复不是配对观测。因此置信区间使用独立 bootstrap，而不是按重复编号伪配对。方法间收益远大于观测噪声，但顺序性系统偏差仍作为限制保留。

## 正确性边界

运行 JSON 中相对 OpenFAST 公共 `Phi` 通道的 `branch_error_gt_1e-3` 很大且三算法一致。该通道使用 OpenFAST 内部工程语义，不是本冻结真实表残差的独立 oracle，不能把它当作算法错根。正式正确性仅由独立 80 位枚举/物理选择规则判断。

本次 oracle 选择刻意集中于最近极坐标节点，因而 `away_from_knot` 与 `multi_root_region` 分组为空；它是局部困难样本压力测试。广义多根/折叠证据由 `CSTR_FOLD_VALIDATION_RTX5090_V1.md` 和真实 BEM 既有 3,000 样本冻结实验承担。

## 追溯与编排修复

权威运行目录为 `results_raw/20260824T124112Z_openfast_multicondition_v1`，汇总为 `results_processed/bem_openfast_multicondition_v1/openfast_multicondition_bootstrap.csv`。首次 8 m/s OpenFAST 输出漏加 `GeomPhi`，导出器按设计拒绝；原 778 通道 `.outb` 审计和日志保留为 `openfast_audit.no_geomflag` / `openfast_no_geomflag.log`。补为 835 通道后重跑 OpenFAST。随后发现 Docker 内误用了宿主机绝对路径，错误热身只产生 `fopen`，未进入正式 JSON；修为 `/work/...` 后才执行正式计时。高精度生成器也明确改用含 mpmath 的固定容器环境。修复和断点复用脚本为 `scripts/resume_openfast_multicondition_20260824_remote.sh`。

所有输入、BTS、FST、最终 `.outb`、数据集、根文件与 oracle CSV 均在远端原始目录记录 SHA-256；本地保留报告所需的紧凑证据。跨硬件 E8 按用户要求排除。
