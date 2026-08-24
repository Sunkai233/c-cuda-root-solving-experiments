# 多步长整体重求解有限差分梯度核验（v1）

## 1. 结论与实验身份

高精度解析隐式梯度已通过独立的“参数正负扰动后整体重新求解”核验。五个领域共 3,000 个 calibration 样本，每个样本使用 7 个相对扰动步长，每一步均独立求解正、负扰动后的物理根，总计保留 21,000 行有限差分结果。所有样本都至少有一个分支稳定的有效步长，且全部观察到误差随步长缩小而收敛。

正式 test split 没有再次运行。本报告只核验 calibration oracle，不能写成新的正式 test 结果。

## 2. 方法

- 运行编号：`20260824T043754Z_finite_difference_cal`
- 任意精度：mpmath 80 decimal digits。
- 相对扰动步长：`1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 3e-5, 1e-5`。
- BEM 扰动叶尖速比 λ；Kepler 扰动平均近点角 M；PV 扰动端电压 V；CSTR 扰动 Da；Peng–Robinson 扰动 A。
- 每个 `p+h`、`p-h` 都重新执行完整高精度括区/多根枚举/物理分支选择，不复用原根进行局部函数近似。
- CSTR 与 Peng–Robinson 只有在正负扰动后的可行根数均与原样本一致时才计入普通梯度误差；否则标记为分支变化或物理区间失效。

中心差分为

\[
g_{FD}(h)=\frac{x(p+h)-x(p-h)}{2h},
\]

并与高精度解析隐式梯度比较。

## 3. 最小步长结果

`h/|p| = 1e-5` 时五域各 600 个样本全部分支稳定、全部有效：

| 域 | 相对误差 median | p95 | p99 | max |
|---|---:|---:|---:|---:|
| BEM | 1.30e-10 | 1.92e-10 | 2.82e-10 | 3.64e-10 |
| Kepler | 1.72e-11 | 1.98e-11 | 2.11e-11 | 2.40e-11 |
| PV | 1.62e-13 | 4.73e-9 | 6.82e-9 | 8.82e-9 |
| CSTR | 3.21e-12 | 1.29e-10 | 3.64e-10 | 9.83e-9 |
| Peng–Robinson | 1.03e-10 | 8.78e-10 | 5.18e-9 | 1.73e-7 |

误差随步长总体呈中心差分预期的二阶下降。Peng–Robinson 最大值较大，来自近临界高条件数样本，但仍表现出多步长收敛，且远低于冻结的该域梯度相对误差界 `1e-4`。

## 4. 分支和物理边界事件

较大的扰动不总是一个合法的局部梯度实验：

- Kepler 在 `1e-2` 有 2/600 个扰动越出规定的 `M≤π` 物理区间。
- PV 在 `1e-2` 有 2/600 个正扰动越过开路端，使 `[0, I_L]` 内不再存在正向第一象限根。
- Peng–Robinson 在 `1e-2` 有 4/600、在 `3e-3` 有 1/600 个样本跨过根数/相态边界。
- CSTR 在本组步长下未发生根数变化。

这些记录没有被删除，也没有作为数值失败混入普通误差统计；在 `1e-3` 及更小步长下五域全部 600/600 有效。

## 5. 数据完整性与边界

- 样本数：3,000。
- 原始样本—步长行数：21,000。
- 无任何有效步长的样本：0。
- 未观察到多步长收敛的样本：0。
- 本实验验证的是高精度解析梯度 oracle；CUDA/CPU 被测梯度与 oracle 的误差仍引用冻结正确性报告。
- 折叠点或相边界处梯度本身可能不连续/发散，分支变化行不能解释为普通可微样本。

唯一数据源：

- `results_raw/20260824T043754Z_finite_difference_cal/finite_difference_raw.csv`
- `results_raw/20260824T043754Z_finite_difference_cal/finite_difference_samples.csv`
- `results_raw/20260824T043754Z_finite_difference_cal/finite_difference_summary.csv`
- `results_raw/20260824T043754Z_finite_difference_cal/manifest.json`
- `scripts/validate_finite_difference.py`

中断的早期目录 `20260824T043725Z_finite_difference_cal` 已标记 `ABORTED.txt`，不参与任何统计。

