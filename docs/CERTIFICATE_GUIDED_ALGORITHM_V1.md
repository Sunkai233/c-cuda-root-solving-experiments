# 认证与目标导向混合精度批量求根算法 V1

## 定位

算法暂称 **Certificate-Guided, Goal-Oriented Mixed-Precision Batched Root Solving**。创新对象不是区间 Newton、隐函数定理、df32 或 stream compaction 本身，而是把后验根误差、目标物理分支、下游输出预算和 GPU 路由成本统一为逐样本调度依据。

正式求解和计时全部由 C 风格 CUDA C/C17 数据结构与函数完成；`nvcc` 按 CUDA 要求使用 C++17 前端。Python 只生成独立 80 位参考、离线 bootstrap 和报告，不进入计时路径。

## 条件性后验半径

对候选根 \(\hat x\)，令

\[
\beta=\frac{|F(\hat x)|+\eta_F}{|F_x(\hat x)|-\eta_{F_x}},\qquad
h=\beta\frac{L}{|F_x(\hat x)|-\eta_{F_x}}.
\]

若分母为正、\(L\) 确实控制候选邻域内的 \(|F_{xx}|\)、\(h\le 1/2\)，且相应球包含在假设成立的定义域内，则使用稳定形式

\[
\rho=\frac{2\beta}{1+\sqrt{1-2h}}
\]

给出 Newton–Kantorovich 型半径。经典定理还要求完整邻域内的 Lipschitz 条件和球包含条件，不能只凭点上的有限差分把 \(\rho\) 称为无条件数学证明。原始理论可追溯到 [Kantorovich](https://cs.uwaterloo.ca/~y328yu/classics/Kantorovich57.pdf)。

V1 CUDA 实现用五点二阶差分最大值的 8 倍作为 sampled majorant，并加入浮点误差保护量。它的身份是“经独立高精度 test 审计的保守后验证书”，不是通用区间算术证明。若后续实现真正的 directed-rounding interval extension，可升级为严格包含证书。

## 分支证书

只要求 \(\rho\) 小于极坐标节点或大物理区边界的距离是不充分的，因为同一大物理区内可能存在多个交点。V1 因此同时要求：

1. 半径球不跨极坐标分段节点和大物理区边界；
2. FP64 局部有限扫描证明“离历史 hint 更近的未扫描单元不存在”；
3. 低精度候选与该 FP64 局部分支见证的距离加保护量不超过逐样本容差。

关闭第 2 条的开发版本在全量 BEM 上出现输出预算失闭合，因此不得作为正式算法。区间 Newton 在有限精度下进行根包含和唯一性验证已有成熟工作，例如 Kearfott 的文章实际是 [Preconditioners for the Interval Gauss–Seidel Method](https://epubs.siam.org/doi/10.1137/0727047)；本文不声称发明根认证。

## 精度调度

每个样本按 FP32、df32、FP64 robust fallback 顺序形成候选。只有根半径、分支见证、梯度风险、有限性和物理规则全部通过时才接受当前最低成本路径。否则将索引写入 warp 聚合队列并升级精度。

该思想与已有自适应精度线性代数的共同点是用误差分析决定精度桶；差异在于约束对象是非线性根、物理分支和隐式梯度。相关工作见 [Adaptive Precision Sparse Matrix–Vector Product](https://epubs.siam.org/doi/10.1137/22M1522619)。

## 目标输出预算

V1 对两个可归一化的真实 BEM 聚合量进行实验：法向载荷代理与转矩代理。若 \(s_i\) 是相应输出对第 \(i\) 个根的归一化敏感度上界，则逐样本接受条件使用

\[
s_i\rho_i\le\varepsilon_Q/N,
\]

从而有一阶预算

\[
|\Delta Q|/|Q|\lesssim\sum_i s_i\rho_i.
\]

这是一种保守的等份预算分配，不是已求解的全局离散最优 knapsack。实验必须同时报告预测上界、实际输出误差、精度路径比例和调度成本；不能仅凭更换路径比例声称性能提高。

## GPU 路由

困难比例为 \(p\) 时，至少含一个困难线程的 warp 比例模型为

\[
q_{warp}=1-(1-p)^{32}.
\]

V1 在 C/CUDA 中实现 inline、warp-local、block-local 和 warp-aggregated global compaction，并用独立校准种子冻结分段策略。正式 test 使用另一排序种子。在 E15 的受控基准中，困难比例 `p` 由实验生成器直接提供给冻结策略，用于隔离并验证“给定证书分类比例后的路由选择”；尚未单独计入生产运行中在线估计 `p` 的扫描、归约与决策开销。因此 auto 策略只声称在本 RTX 5090、当前 robust 路径和批量规模上、条件于已知 `p` 时接近实测最优，不声称已完成端到端在线控制器，也不声称跨架构阈值可迁移。层次化重排与 warp-synchronous multisplit 的相关背景见 [GPU Multisplit](https://arxiv.org/abs/1701.01189)。

## 可主张的理论边界

- **条件性根半径**：在 Lipschitz majorant 和定义域包含假设成立时，使用 Kantorovich 半径。
- **分支稳定性**：若根包含球处于目标分支内部，且最近分支身份由局部扫描见证，则有限精度候选不改变冻结分支选择。
- **输出误差**：一阶项由 \(\sum s_i\rho_i\) 控制；严格有限半径结果还需二阶余项上界。
- **路由成本**：`q_warp` 解释困难样本放大，但具体切换点必须实测校准。

因此论文不能把 sampled majorant 写成严格区间证明，不能把输出一阶界写成无余项定理，也不能把 RTX 5090 的路由阈值写成跨硬件常数。
