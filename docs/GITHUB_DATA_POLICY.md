# GitHub 数据发布边界

本仓库的 GitHub 版本保留能够审阅结论和复算统计的全部文本型证据：源码、冻结协议和 marker、高精度参考 CSV、正式与失败候选 CSV/JSON、每次重复计时、编译/硬件/温度日志、Nsight 宽表 CSV、处理后报告及最终机械审计。

以下文件不进入普通 Git 历史：

- OpenFAST/TurbSim 生成的 `.outb`、`.bts`；
- 批量输入、全量根输出和中间缓存 `.bin`；
- CUDA/OpenFAST 编译产物与可执行文件；
- Nsight Compute 二进制 `.ncu-rep`（对应导出 CSV 已发布）。

原因不是删除失败或选择数据，而是其中存在 100–285 MB 的单文件，超过 GitHub 普通 Git 的 100 MB 限制；本机该类可再生二进制合计约 2 GB。正式 runner、输入配置、生成器、源代码、软件提交、输出形状、文件大小和 SHA-256 均已保留，能够重新生成并核对身份。所有失败 CSV、失败日志和被拒候选仍随 GitHub 仓库发布。

`FINAL_ACCEPTANCE_NO_E8.md` 是 2026-08-24 的历史冻结验收，不再表示当前实验范围。随后已完成 E12–E16，并于 2026-08-26 恢复 E8 跨硬件验证。E8 的每台设备均发布完整文本型原始证据和独立处理结果；仅排除可由 runner 重建的批量二进制与编译产物。机器审计入口为：

```bash
python scripts/audit_e8_cross_architecture.py --help
```

当前研究深度总验收入口为 `results_processed/FINAL_ACCEPTANCE_E0_E16_NO_E8.md`，E8 权威阶段报告、逐机 `summary.json` 和 `audit.json` 单独发布。历史 `FINAL_ACCEPTANCE_NO_E8.md` 与 `final_acceptance_audit.json` 保留用于追溯，不得再解释为当前范围。
