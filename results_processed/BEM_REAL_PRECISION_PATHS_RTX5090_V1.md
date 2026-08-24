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

## df32_adaptive 冻结 test

第四套 `bem_real_ref_v4_df32_adaptive_test_20260824` 排除了前三套共 5,000 个 source index，CSV SHA-256 `7e101ff1ffec3208da6d1234411aa1e07c6facf66ceab4e5f23728abe29a1335`。候选 `cbfaa06`，冻结协议 `22a6e89`，唯一运行 `20260824T102831Z_bem_real_precision_v2_frozen_test_rtx5090`：df32_adaptive 1000/1000 未观察到失败，最大根误差 6.217e-15，0 错分支、0 非有限、回退 0。同批纯 FP32 有 907/1000 超过 1e-7；FP64 最大 5.954e-10；原始 adaptive 最大 2.405e-8且回退 97.7%。v4 未触发 df32 回退并不证明门可删除；v3 已冻结的两个失败是门存在的直接反例。

## 真实 2,448,000 状态性能

运行 `20260824T103200Z_bem_real_precision_performance_rtx5090`，45 秒热机、10 次预热、30 次正式重复，输入/输出 pinned，分别测 kernel 与 H2D+kernel+D2H。10,000 次配对 bootstrap：

| path | kernel ms | E2E ms | FP64/path kernel (95% CI) | FP64/path E2E (95% CI) | failures | correction |
|---|---:|---:|---:|---:|---:|---:|
| FP64 | 472.602 | 480.269 | 1 | 1 | 0 | — |
| FP32 | 37.139 | 44.113 | 12.717 [12.679,12.737] | 10.870 [10.847,10.914] | 888 | — |
| FP32+df32 | 51.214 | 58.162 | 9.237 [9.200,9.253] | 8.264 [8.248,8.270] | 922 | — |
| df32_adaptive | 51.928 | 58.933 | 9.092 [9.073,9.116] | 8.151 [8.132,8.160] | 0 | 0.04% |
| FP32→FP64 adaptive | 500.900 | 508.263 | 0.944 [0.943,0.946] | 0.945 [0.942,0.947] | 0 | 97.59% |

只有通过冻结正确性的路径可用于有效性能主张。纯 FP32/纯 df32 数字仅构成 Pareto 的“不合格但快”端点；`df32_adaptive` 是本组唯一同时通过且显著快于 FP64 的量化路径。原始 adaptive 比 FP64 慢约 5.8%，再次说明高回退率会抵消混合精度收益。
