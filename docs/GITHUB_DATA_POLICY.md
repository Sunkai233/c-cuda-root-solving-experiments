# GitHub 数据发布边界

本仓库的 GitHub 版本保留能够审阅结论和复算统计的全部文本型证据：源码、冻结协议和 marker、高精度参考 CSV、正式与失败候选 CSV/JSON、每次重复计时、编译/硬件/温度日志、Nsight 宽表 CSV、处理后报告及最终机械审计。

以下文件不进入普通 Git 历史：

- OpenFAST/TurbSim 生成的 `.outb`、`.bts`；
- 批量输入、全量根输出和中间缓存 `.bin`；
- CUDA/OpenFAST 编译产物与可执行文件；
- Nsight Compute 二进制 `.ncu-rep`（对应导出 CSV 已发布）。

原因不是删除失败或选择数据，而是其中存在 100–285 MB 的单文件，超过 GitHub 普通 Git 的 100 MB 限制；本机该类可再生二进制合计约 2 GB。正式 runner、输入配置、生成器、源代码、软件提交、输出形状、文件大小和 SHA-256 均已保留，能够重新生成并核对身份。所有失败 CSV、失败日志和被拒候选仍随 GitHub 仓库发布。

最终范围为 E0–E7、E9–E11；E8 跨硬件由用户明确排除。机器审计入口为：

```bash
python scripts/audit_final_no_e8.py --help
```

权威验收摘要是 `results_processed/FINAL_ACCEPTANCE_NO_E8.md` 与 `results_processed/final_acceptance_audit.json`。
