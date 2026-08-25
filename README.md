# Supplementary C/CUDA root-solving experiments

本仓库是 [`docs/SUPPLEMENTARY_EXPERIMENTS_C_CUDA.md`](docs/SUPPLEMENTARY_EXPERIMENTS_C_CUDA.md) 的可追溯 C17/CUDA C++ 实验实现。按用户 2026-08-24 的最终范围，E0–E7、E9–E11 均纳入验收；跨硬件 E8 暂不执行。因此所有硬件性能结论只适用于本次 RTX 5090 与 AMD EPYC 9654，仓库不声称可迁移到第二类 GPU。

五域包括解析 BEM、Kepler、单二极管 PV、非等温 CSTR 和 Peng–Robinson 负对照。另有基于 OpenFAST/NREL 5 MW、真实翼型极坐标表的 600 s BEM 工作流。CPU/GPU 对比保持相同残差、物理分支、停止条件和输入；计时分别保存纯内核与 H2D+kernel+D2H，原始结果为追加式时间戳目录。

## 权威结果

- `results_processed/FROZEN_CORRECTNESS_V3.md`：五域冻结高精度正确性；V1/V2 保留为历史/失败候选。
- `results_processed/GPU_PERFORMANCE_V3_RTX5090.md`：五域 15,600 次正式 GPU 重复、规模扩展和端到端结果。
- `results_processed/CPU_C17_PERFORMANCE_V1.md`：严格串行、SIMD、OpenMP 96 线程和 PGO 的 7,800 次 CPU 重复及 CPU/GPU 临界规模。
- `results_processed/ALGORITHM_PERFORMANCE_RTX5090_V2.md`：完整通用与专用算法候选矩阵；V1 不含全部专用方法，已作废。
- `results_processed/BEM_REAL_FROZEN_RTX5090_V1.md`：真实翼型表 BEM 的独立 80 位冻结核验。
- `results_processed/BEM_REAL_ALGORITHM_MATRIX_RTX5090_V2.md`：同语义 Bisection/Brent/Illinois/fixed/adaptive 对比。
- `results_processed/BEM_REAL_PRECISION_PATHS_RTX5090_V1.md`：FP32、double-single、FP64 与条件感知纠错；只有 `df32_adaptive` 同时通过冻结正确性并显著快于 FP64。
- `results_processed/BEM_REAL_CPU_GPU_V1.md`：真实 BEM 严格 CPU/GPU 公平对比。
- `results_processed/BEM_OPENFAST_MULTICONDITION_V1.md`：12 m/s 基线之外的 8 m/s IEC C 与 16 m/s IEC A 独立 600 s 工况、oracle 与计时。
- `results_processed/PV_EXTENDED_GRADIENTS_RTX5090_V1.md`、`CSTR_FOLD_VALIDATION_RTX5090_V1.md`、`BEM_REAL_FINITE_DIFFERENCE_V1.md`：扩展可微性、多根/折叠与重新求解有限差分核验。
- `results_processed/BEM_SCALE_CONDITION_ABLATIONS_RTX5090.md`、`REMAINING_CUDA_ABLATIONS_RTX5090.md`、`NSIGHT_COMPUTE_RTX5090_V1.md`：A0–A10 消融及直接 GPU profiling。
- `results_processed/CPU_FAST_MATH_V1.md` 与 `FAST_MATH_CANDIDATE_RTX5090.md`：CPU/CUDA 编译策略严格分开。
- `results_processed/FINAL_ACCEPTANCE_NO_E8.md`：最终范围、证据映射、正负结果和机械审计入口。
- `docs/PAPER_CLAIM_EVIDENCE_MATRIX.md`：写作前的“主张—结果—原始证据—适用边界”冻结矩阵。

“实验完成”不等于所有候选成功。全局 CUDA fast-math 因 CSTR 换根被拒绝；纯 FP32、无纠错 df32、固定 44 步、O(1) 极坐标 LUT 和原始 FP32→FP64 adaptive 均为正式负结果。Peng–Robinson 的 GPU 大批量加速也为负结果。失败运行、失败样本和旧版本均保留，不得选择性删除。

## 构建与复现

RTX 5090 主机只有 NVIDIA 驱动，CUDA 编译/运行使用固定 Docker 镜像。典型五域入口为：

```bash
bash scripts/run_rtx5090.sh
```

各正式 runner、冻结 manifest、一次性 test marker、源文件 SHA-256、编译日志、硬件/驱动/温度记录和 CSV/JSON 位于 `scripts/`、`manifests/`、`references/` 与 `results_raw/<run_id>/`。最终验收使用 `scripts/audit_final_no_e8.py`，明确检查 E8 是唯一排除项。

GitHub 版本包含全部源码、协议、冻结参考、正式/失败候选的 CSV/JSON/TXT/日志、Nsight CSV、处理后报告和审计结果。超过普通 GitHub 单文件限制、且可由 runner 重建的 `.bin/.outb/.bts` 与编译产物不进入 Git 历史；其身份、哈希和复现边界见 [`docs/GITHUB_DATA_POLICY.md`](docs/GITHUB_DATA_POLICY.md)。
