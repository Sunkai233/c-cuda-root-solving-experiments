# 真实翼型表 BEM 精度路径（RTX 5090）

本实验使用真实分段线性极坐标表、Prandtl 损失和冻结物理分支规则。四路径为：纯 FP32；FP32 括根后用真实 `hi+lo` double-single 残差做 4 次 Newton 修正；严格 FP64；FP32 后用 FP64 前向误差代理决定是否完整回退的 adaptive。df32 不是把 FP64 结果截断：加减乘除、exp/sqrt/sincos/acos 修正均由 FP32 error-free transform/FMA 组成。

开发/校准运行 `20260824T101935Z_bem_real_precision_devcal_rtx5090`：

| split/path | root max | >1e-7 | wrong branch >1e-3 | nonfinite | FP64 correction |
|---|---:|---:|---:|---:|---:|
| dev FP32 | 1.758e-4 | 1677/1800 | 0 | 1 | — |
| cal FP32 | 6.797e-5 | 558/600 | 0 | 0 | — |
| dev FP32+df32 | 6.042e-10 | 0 | 0 | 0 | — |
| cal FP32+df32 | 2.744e-11 | 0 | 0 | 0 | — |
| dev FP64 | 5.532e-9 | 0 | 0 | 0 | — |
| cal FP64 | 1.288e-8 | 0 | 0 | 0 | — |
| dev adaptive | 2.825e-8 | 0 | 0 | 0 | 98.6% |
| cal adaptive | 2.734e-8 | 0 | 0 | 0 | 98.3% |

因此纯 FP32 正式判为不满足 1e-7 根容差；不能用 0 个大于 1e-3 的错分支掩盖数值精度失败。df32 修正候选通过开发/校准，而 adaptive 虽通过但几乎完全退化为 FP64，性能收益存疑。

独立 test 真源 `bem_real_ref_v3_precision_test_20260824` 有 1,000 个 80 位样本，优先包含 700 个近插值节点样本；与 v1 的 3,000 个、v2 的 1,000 个 source index 交集均为 0，CSV SHA-256 为 `c4c92a49b7fd7cfc9d6b121cb7f9615c906df8006fa98538a22d3974a633c352`。

## 第一次冻结 test：df32 路径被拒绝

候选 `5a62b6a`、冻结协议 `c94e587`，运行 `20260824T102142Z_bem_real_precision_frozen_test_rtx5090`。FP64 最大根误差 7.072e-10，adaptive 最大 2.984e-8、FP64 回退 97.2%，两者 0 错分支/0 非有限并通过。纯 FP32 有 913/1000 超过 1e-7、2 个错分支、2 个失败。更重要的是，FP32+df32 虽能局部提高精度，仍继承 FP32 选错的两个交点：最大误差 2.175e-3、2 个失败，因此正式拒绝。该 test 不重跑，marker 为 `TEST_SPLIT_EXECUTED_bem_real_precision_v1_20260824.txt`。

失败机制不是 df32 舍入误差，而是局部 Newton 修正不能跨越到正确物理交点。随后形成新的 `df32_adaptive` 候选：df32 修正后用严格 FP64 残差/物理有效性检查，失败才完整 FP64 回退。它在 dev/cal 的根误差与纯 df32 相同（最大 6.042e-10 / 2.744e-11），0 错分支、0 非有限；开发/校准未触发回退。它属于物质上不同的新候选，必须使用第四套未见 holdout，不能在 v3 上补跑后冒充冻结结果。
