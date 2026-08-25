# E8 跨 GPU 架构验证协议 V1

E8 使用同一冻结源码、真实 BEM 数据、80 位 test 和数值阈值，在每张 GPU 上按实际计算能力原生重编译。主要比较量是同卡内相对 FP64 的速度比；绝对 kernel 与 E2E 时间分开报告，避免把宿主 CPU、PCIe 和 SXM 差异误写成纯 GPU 架构效应。

## 三个相互独立的问题

1. **正确性迁移**：完整 FP32/df32 后验门是否保持零错误接受，自适应路径是否保持零根/分支失败，目标预算是否闭合。
2. **算法加速迁移**：证书方法相对同卡全 FP64 的 kernel/E2E 加速及 95% bootstrap 区间是否仍大于 1。
3. **路由阈值迁移**：RTX 5090 冻结 auto 策略相对各卡 test 事后最优的 regret；同时用独立 calibration seed 选出的本地模式在统一 test seed 上评估，不能用 test 反调阈值。

## 公平性

- CUDA 12.8.x、相同严格浮点开关和相同 C/CUDA 源码；仅 `-arch=sm_xy` 随运行时检测结果改变。
- 每项 10 次预热、30 次正式重复。记录 UUID、计算能力、驱动、功率上限、温度、时钟、ECC、PCIe/SXM 信息和 ptxas 编译资源。
- 固定 df32 若失败仍保留为负对照；E8 完成不以结果必须更快为条件。
- `0/1000` 是本冻结 test 的观察结果，不等于数学零失败率。

冻结机器清单、数据 SHA-256、种子和验收阈值见 `manifests/frozen_e8_cross_architecture_v1.json`。正式入口为 `scripts/run_e8_cross_architecture.sh`。
