# 冻结自适应正确性 V3（RTX 5090）

## 冻结过程

V2 冻结 test `20260824T072516Z_frozen_test_v2_rtx5090` 保留为失败：BEM/Kepler 的 3 个梯度尾样本超过预注册最大界限。该 test 没有用于重新调参。随后只用 v2 dev/cal 阈值扫描与全新的 v3 dev/cal，冻结 `tau_x=3e-8`、主域梯度最大相对误差 2e-6、PR 1e-4、根最大绝对误差 1e-7、错分支/非有限均为 0。配置见 `manifests/frozen_adaptive_v3.json`。

全新 v3 test 在 `20260824T073512Z_frozen_test_v3_rtx5090` 只运行一次。五域各 600 点均未观察到失败；每域 0/600 的 Wilson 95% 失败率上界为 0.636%，因此不能写成数学上的 100% 保证。

## test 结果

| 域 | root max | gradient p99 | gradient p99.9 | gradient max | correction | wrong/nonfinite |
|---|---:|---:|---:|---:|---:|---:|
| BEM smooth | 2.999e-8 | 2.981e-7 | 9.494e-7 | 1.643e-6 | 47.83% | 0/0 |
| Kepler | 2.854e-8 | 2.077e-8 | 3.609e-7 | 4.365e-7 | 95.00% | 0/0 |
| PV | 2.820e-8 | 1.622e-10 | 1.224e-9 | 4.949e-9 | 97.83% | 0/0 |
| CSTR | 2.936e-8 | 2.304e-7 | 3.311e-7 | 3.469e-7 | 21.00% | 0/0 |
| Peng–Robinson | 2.997e-8 | 3.288e-5 | 8.235e-5 | 8.516e-5 | 58.67% | 0/0 |

根、梯度和残差的 median/p90/p95/p99/p99.9/max 以及 CSTR/PR 物理分支、Kepler 难度层、PV 端点层的 Wilson 区间均在 `results_raw/20260824T073512Z_frozen_test_v3_rtx5090/frozen_analysis.json` 与 `validation_test.csv` 中。纯 FP32 是失败对照；严格 FP64 五域均 0 错根。
