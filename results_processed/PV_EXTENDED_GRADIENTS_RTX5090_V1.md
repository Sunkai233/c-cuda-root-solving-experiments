# 光伏功率与参数梯度扩展验证（RTX 5090）

## 结论

冻结 test 集 600 点一次性执行通过。根最大绝对误差为 `2.04e-14 A`，功率最大绝对误差为 `1.26e-12 W`，均低于预注册界限 `1e-10 A` 和 `1e-9 W`。`dI/dV`、`dI/dIL`、`dI/dI0`、`dI/da`、`dI/dRsh` 的最大相对误差不超过 `4.26e-15`；接近零值的 `dI/dRs` 最大相对误差为 `1.79e-8`，低于 `1e-6` 界限。

开发/校准与 test 均未观察到非有限输出、指数溢出或下溢。该结论覆盖短路端、开路端、MPP 邻域和内部区，各类在 3000 点参考集中各 750 点。

## 方法与真值

- 参考电流由 70 位十进制精度 Lambert-W 闭式独立计算；`Voc` 和 `Vmp` 单独高精度求解。
- 参数梯度由隐式函数定理对 `IL, I0, a, Rs, Rsh, V` 分别求偏导。
- CUDA 严格 FP64 路径重新求根并计算功率与六个梯度，不共享参考实现代码。
- 冻结配置：`manifests/frozen_pv_extended_v1.json`；一次性标记：`manifests/TEST_SPLIT_EXECUTED_pv_extended_v1_20260824.txt`。

## 数据源

- `references/pv_extended_ref_v1_20260824/`
- `results_raw/20260824T082742Z_pv_extended_devcal_rtx5090/`
- `results_raw/20260824T082851Z_pv_extended_frozen_test_rtx5090/`

