# 最终验收：E0–E16（仅排除 E8 跨硬件）

原 E0–E11（排除 E8）证据基线保持不变，见 `FINAL_ACCEPTANCE_NO_E8.md` 和 `final_acceptance_audit.json`，机械检查 62/62 通过。研究深度扩展新增 E12–E16，见 `E12_E16_CERTIFICATE_GOAL_ROUTING_RTX5090_V1.md` 和 `e12_e16_v1/audit.json`，机械检查 15/15 通过。两部分合计 77 项检查全部通过。

| 实验 | 状态 | 权威证据 | 结论边界 |
|---|---|---|---|
| E0–E7、E9–E11 | 完成 | `FINAL_ACCEPTANCE_NO_E8.md` | 保持原冻结结论 |
| E8 跨硬件 | **用户排除** | `manifests/final_scope_no_e8_v1.json` | 不得声称跨 GPU 架构迁移 |
| E12 认证准确性与紧致性 | 完成 | `E12_E16_CERTIFICATE_GOAL_ROUTING_RTX5090_V1.md`、新 v5 80 位 test | sampled certificate 经独立 test 审计，不冒充严格区间证明 |
| E13 认证驱动精度选择 | 完成 | 同上、`certificate_performance_bootstrap.csv` | 完整根+分支+梯度证书相对 FP64 E2E 1.931×；固定 df32 不合格 |
| E14 目标导向误差预算 | 完成 | 同上、`goal_budget_summary.csv` | 四个预算均闭合；不声称所有预算都更快 |
| E15 动态紧凑策略 | 完成 | 同上、`routing_summary.csv` | auto 最大 regret 0.128%；阈值限 RTX 5090 当前负载 |
| E16 组合消融 | 完成 | 同上、`e16_ablation_summary.csv` | 负结果和开发失败均保留 |

新算法正式定位为：**由后验数值证书、目标物理分支、下游输出误差预算和 GPU 成本模型共同驱动的逐样本混合精度批量非线性求解算法**。

验收完成不代表所有新增模块都获得速度正收益。目标导向分配的主要正结果是预算闭合与资源重分配；在 `1e-5` 预算下它比统一容差慢约 5.3%，必须作为边界保留。
