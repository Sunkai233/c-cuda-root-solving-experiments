# OpenFAST/NREL 5MW 真实 BEM 数据基准（v1）

## 1. 结论

已在 abc66 上完成 600 秒 OpenFAST/NREL 5MW 陆上风机仿真，生成后续真实翼型表 C/CUDA 求根实验所需的真实 BEM 节点状态。冻结数据包含 48,000 个非初始时间步、3 个叶片、每片 19 个气动节点，共 2,736,000 个“时间步—叶片—节点”状态；778 个输出通道和全部节点数据均通过形状、数量与有限值审计。每片叶片的根端与最外端由 hub/tip-loss 规则固定诱导，不属于普通求根，因此普通根数为 48,000×3×17 = 2,448,000。

这一步完成的是**真实输入数据与 OpenFAST 参考输出的生成**，不是 C/CUDA 求根器的计时结果。OpenFAST 全模型运行时间同时包含结构动力学、入流、气动模块和二进制输出，不能与后续单独的 CPU/GPU 根求解内核直接比较。

## 2. 冻结配置

- OpenFAST 源码：干净的 `git archive`，提交 `3a9d3f2`。
- 构建：Release、双精度、GCC/gfortran 13.3.0、静态 LAPACK 3.12.1；未启用 OpenMP。
- 模型：NREL 5MW 陆上风机，真实 NREL 叶片几何和 Cylinder、DU、NACA64 翼型极线表。
- 时长与步长：`TMax=600 s`，`DT=0.0125 s`，恰好 48,000 个非初始时间步。
- 空间离散：3 片叶片，每片 19 个 AeroDyn 节点。
- 入流：TurbSim IEC Kaimal NTM、湍流等级 B、均值 12 m/s、种子 13428、31×31 网格、0.05 s 入流步长。
- 转子：固定 12.1 rpm；`DrTrDOF=False`、`GenDOF=False`、`CompServo=0`。这一选择避免控制器 DLL 和转速漂移，使数据基准可复现。
- 每个节点保存：`Vx, Vy, Phi, Alpha, Theta, AxInd, TnInd, Cl, Cd, Cx, Cy, Fl, Fd`。`Theta` 是 AeroDyn 直接输出的桨距加扭角状态，不由参考根 `Phi-Alpha` 反推。

## 3. 数据审计

| 项目 | 结果 |
|---|---:|
| 含初值输出行 | 48,001 |
| 非初值时间步 | 48,000 |
| 总输出通道 | 778 |
| 每类节点通道 | 57 |
| 非初值节点状态 | 2,736,000 |
| 固定诱导状态 | 288,000 |
| 普通求根实例 | 2,448,000 |
| 节点非有限值 | 0 |
| `Alpha = wrap(Phi-Theta)` 最大恒等误差 | 5.68e-14 deg |
| 形状/通道审计 | PASS |
| 有限值审计 | PASS |

节点输出的全局范围为：`Vx [-4.90965, 19.37289] m/s`、`Vy [-5.05805, 86.86070] m/s`、`Phi [-1.80463, 180] deg`、`Alpha [-13.308, 166.692] deg`、`AxInd [-0.005604, 1.864504]`、`TnInd [-0.003752, 0.162150]`。初始时刻、根部圆柱段及局部反向流会扩大角度和诱导因子的范围，因此后续性能集必须保留明确的物理筛选标志，不能静默删除异常区间。

## 4. 文件身份与运行记录

- TurbSim 二进制：`90m_12mps_twr.bts`，70,881,358 bytes，SHA-256 `951e02395ef7032b5578bbd8fb3163fca4644ec23a3b3b4a62accb0bfb14d256`。
- OpenFAST 二进制：`5MW_600s_alpha.outb`，298,390,168 bytes，SHA-256 `240235a46eeb7e0ac1f3a8c81eb711ccb79247a43ae4ab4d9e78c066b8ef8e5c`。
- TurbSim 生成时间：2026-08-24 04:57:21Z 至 05:05:48Z，507.42 CPU s。
- OpenFAST 权威运行时间：2026-08-24 05:19:11Z 至 05:20:14Z；正常结束，1.0598 min 实时、1.0514 min CPU，仿真/CPU 比 9.5113。

权威数据与审计文件：

- `domains/bem/openfast/5MW_Land_600s/5MW_600s_alpha.outb`
- `domains/bem/openfast/5MW_Land_600s/openfast_600s_alpha_manifest.txt`
- `domains/bem/openfast/5MW_Baseline/Wind/90m_12mps_twr.bts`
- `domains/bem/openfast/5MW_Baseline/Wind/turbsim_600s_manifest.txt`
- `results_raw/20260824T050842Z_openfast_bem_600s/openfast_bem_summary.json`
- `results_raw/20260824T050842Z_openfast_bem_600s/openfast_bem_channel_stats.csv`
- `scripts/analyze_openfast_bem.py`

早期不含 `Alpha` 或不含直接 `Theta` 通道的 600 秒输出只是预跑，不是权威版本。OpenFAST 把二进制通道后缀 `Alpha`/`Theta` 缩写为 `Alp`/`The`；两次别名识别失败目录 `20260824T050842Z_openfast_bem_600s_FAILED_ALPHA_ALIAS` 和 `20260824T050842Z_openfast_bem_600s_FAILED_THETA_ALIAS` 以及旧目录 `20260824T050842Z_openfast_bem_600s_NO_THETA` 均不得参与统计。

## 5. 后续工作状态（2026-08-24 更新）

本报告是 12 m/s OpenFAST 数据前提的历史记录。随后已经完成同源真实翼型表残差、C17 串行/OpenMP 基线、CUDA 求解器、冻结高精度核验、精度路径、低分歧/两阶段纠错、梯度有限差分和 RTX 5090 端到端计时，分别见 `BEM_REAL_FROZEN_RTX5090_V1.md`、`BEM_REAL_CPU_GPU_V1.md`、`BEM_REAL_ALGORITHM_MATRIX_RTX5090_V2.md`、`BEM_REAL_PRECISION_PATHS_RTX5090_V1.md` 与 `BEM_REAL_FINITE_DIFFERENCE_V1.md`。

8 m/s IEC C 和 16 m/s IEC A 的独立风场、600 s OpenFAST、每工况 2,448,000 个根、独立 80 位 oracle 与正式 GPU 计时也已完成，权威汇总为 `BEM_OPENFAST_MULTICONDITION_V1.md`。OpenFAST 的公开 `Phi` 仍只作工程交叉检查；冻结残差的正确性真源是独立多精度 oracle。第二种 GPU 架构 E8 按用户要求排除，仓库不作跨架构迁移性主张。
