# 补充实验实施规范：最优化 C / CUDA C 批量可微求根

> 版本：v1.0（2026-08-24）  
> 状态：实验执行协议，不是论文大纲，不代表实验结果已经产生。  
> 适用对象：BEM、Kepler、光伏单二极管、非等温 CSTR；Peng–Robinson 作为负对照。  
> 核心要求：所有正式性能结果必须来自优化后的 C17 / CUDA C 实现；Python 只允许生成数据、汇总结果和绘图，不参与被计时求解路径。

---

## 1. 实验目标

补充实验需要同时回答四个问题：

1. **性能是否真实**：在实际批量规模下，GPU 是否在端到端时间和纯求解时间上优于同等优化的 CPU？
2. **精度是否达标**：FP32、df32 和条件感知混合精度是否在预先冻结的误差、错根率和失败率门槛内？
3. **梯度是否可信**：隐式梯度是否与高精度解析值及“参数扰动后整体重求解”的有限差分一致？
4. **结论是否通用**：性能和精度优势能否从 BEM 推广到轨道、光伏和反应器三个不同工程领域？

最终主张不能建立在单个最大批量、单个 GPU、单一误差阈值或单一成功样本上。

---

## 2. 不可违反的公平性原则

### 2.1 每组对比只改变一个主要变量

算法对比时，以下内容必须完全一致：

- 方程残差及其数学重构；
- 输入数据及顺序；
- 物理根区间和根分支规则；
- 输出精度和停止准则；
- CPU/GPU 数据类型；
- 预处理是否计入时间；
- 编译器优化等级；
- 重复次数和计时方法。

例如，不能用“原始病态残差上的 CPU Brent”与“重构光滑残差上的 GPU Halley”直接证明算法加速。必须至少增加同残差、同精度的 Brent/Newton/Halley/割线对照。

### 2.2 所有基线都必须充分优化

不得故意保留以下低效基线：

- Python 循环；
- 未开启 `-O3` 的 C 程序；
- 每个根单独 `malloc/free`；
- 每次迭代重新读取文件；
- CPU 标量实现对比 GPU 向量批处理，却不提供 CPU SIMD/OpenMP 版本；
- GPU 每个样本一次 kernel launch；
- 在被计时区间内包含日志输出、随机数生成或正确性检查。

### 2.3 “最快”不允许以改变数值语义为代价

`-use_fast_math`、近似倒数、近似三角函数、FTZ、查表和低精度都可能改变结果。因此必须分别构建：

- `strict`：严格精度构建；
- `fast`：快速数学构建；
- `adaptive`：条件感知精度与选择性纠错构建。

快速构建只有重新通过全部根和梯度门槛后，才能作为有效结果。

NVIDIA 官方说明 `-use_fast_math` 会启用 FTZ、低精度除法/平方根和 FMA，速度提高伴随精度损失：[NVCC 官方说明](https://docs.nvidia.com/cuda/archive/13.0.1/cuda-c-best-practices-guide/nvcc-compiler-switches.html)。

---

## 3. 软件与目录要求

建议新增独立补充实验目录，不直接覆盖原代码：

```text
supplementary_experiments/
├── include/                  # 统一求解接口、数据结构、误差统计
├── src_cpu/                  # C17 CPU 求解器
├── src_cuda/                 # CUDA C 求解器
├── domains/
│   ├── bem/
│   ├── kepler/
│   ├── pv_diode/
│   ├── cstr/
│   └── peng_robinson/
├── references/               # 高精度参考根/梯度；只读
├── manifests/                # 数据、硬件、编译器、参数清单
├── scripts/                  # 仅生成数据、运行调度、统计汇总
├── build/
│   ├── cpu_strict/
│   ├── cpu_fast/
│   ├── cuda_strict/
│   └── cuda_fast/
├── results_raw/              # 每次运行原始 JSON/CSV；只追加
├── results_processed/
├── profiles/                 # Nsight Compute / perf 报告
└── logs/change_log.md
```

原始数据、参考根、参考梯度必须只读；运行程序不得修改输入文件。

---

## 4. 统一 C 接口

所有领域通过相同批量接口调用，避免为某个方法额外增加封装开销：

```c
typedef enum {
    ROOT_OK = 0,
    ROOT_NO_PHYSICAL_ROOT,
    ROOT_WRONG_BRACKET,
    ROOT_MAX_ITER,
    ROOT_NONFINITE,
    ROOT_GRADIENT_RISK,
    ROOT_BRANCH_AMBIGUOUS
} root_status_t;

typedef struct {
    double root;
    double residual;
    double gradient;
    double condition_proxy;
    uint32_t iterations;
    uint8_t precision_path;
    uint8_t status;
} root_output_t;

void solve_batch_cpu(
    size_t n,
    const domain_input_t * restrict input,
    root_output_t * restrict output,
    const solver_config_t * restrict config
);
```

CUDA 内核使用同样的字段语义，但正式吞吐测试可以采用 SoA 输出，只写实验需要的最少字段：

```c
__global__ void solve_batch_cuda(
    size_t n,
    const domain_input_soa_t input,
    domain_output_soa_t output,
    solver_config_t config
);
```

### 4.1 AoS 与 SoA

- 文件和可读性接口可使用 AoS；
- 正式 SIMD/GPU 内核优先使用 SoA；
- 同一 warp 应读取连续的 `parameter[i]`；
- 禁止线程跨大结构体读取不使用字段；
- 所有数组至少 64 字节对齐；GPU 地址自然满足全局内存合并要求。

---

## 5. CPU C17 最优化编译

### 5.1 严格精度版本

```bash
gcc -std=c17 -O3 -march=native -mtune=native -flto \
    -DNDEBUG -fno-math-errno -fno-trapping-math \
    -Wall -Wextra -Wpedantic -Wshadow -Wconversion \
    -o build/cpu_strict/solver \
    src_cpu/*.c domains/*/*.c -lm
```

说明：

- `-O3` 开启循环变换、内联和自动向量化；
- `-march=native -mtune=native` 针对当前 CPU 指令集生成代码；
- `-flto` 允许跨文件内联与过程间优化；
- `-DNDEBUG` 去除正式运行中的断言；
- `-fno-math-errno` 避免无用 `errno` 语义；
- 不在严格版使用 `-ffast-math`。

GCC 官方说明 `-O3` 和 `-flto` 的具体作用：[GCC Optimize Options](https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html)。

### 5.2 快速数学候选版本

```bash
gcc -std=c17 -O3 -march=native -mtune=native -flto \
    -DNDEBUG -ffast-math -fno-math-errno -fno-trapping-math \
    -o build/cpu_fast/solver \
    src_cpu/*.c domains/*/*.c -lm
```

该版本只能作为独立实验组。若出现以下任一情况，必须判定为不可用：

- 非有限根或梯度增加；
- 物理分支分类变化；
- 根误差/梯度误差超出冻结阈值；
- FTZ 使近奇异判据失效；
- 与严格版本出现无法解释的结果差异。

### 5.3 PGO 版本

训练数据只能来自开发集，不能使用最终测试集：

```bash
mkdir -p build/pgo_data

gcc -std=c17 -O3 -march=native -flto \
    -fprofile-generate=build/pgo_data \
    -o build/cpu_pgo_train/solver \
    src_cpu/*.c domains/*/*.c -lm

build/cpu_pgo_train/solver --manifest manifests/pgo_train.json

gcc -std=c17 -O3 -march=native -flto \
    -fprofile-use=build/pgo_data -fprofile-correction \
    -DNDEBUG -fno-math-errno -fno-trapping-math \
    -o build/cpu_pgo/solver \
    src_cpu/*.c domains/*/*.c -lm
```

PGO 只在代表性训练负载上优化分支概率；必须额外报告它在困难留出集上是否退化。

### 5.4 CPU 向量化检查

编译时额外生成向量化报告：

```bash
gcc -O3 -march=native -fopt-info-vec-optimized=build/vectorized.txt \
    -fopt-info-vec-missed=build/vector_missed.txt -c src_cpu/solver.c
```

必须检查：

- 主批量循环是否 SIMD 化；
- `restrict` 是否消除别名阻碍；
- 输入/输出是否对齐；
- 函数指针、不可内联调用、数据相关循环是否阻碍向量化；
- AVX2/AVX-512 是否真实出现在反汇编中。

---

## 6. CUDA C 最优化编译

### 6.1 架构检测

不得永久写死 `sm_120`。运行前记录：

```bash
nvidia-smi --query-gpu=name,uuid,driver_version,temperature.gpu,power.limit,memory.total \
    --format=csv
nvcc --version
```

根据实际设备设置：

```bash
export CUDA_ARCH=sm_120   # 示例，必须替换为实际计算能力
```

### 6.2 严格精度 CUDA 版本

```bash
nvcc -std=c++17 -O3 -arch=${CUDA_ARCH} \
    --fmad=true --ftz=false --prec-div=true --prec-sqrt=true \
    -Xptxas=-v \
    -Xcompiler=-O3,-march=native,-DNDEBUG \
    -o build/cuda_strict/solver \
    src_cuda/*.cu domains/*/*.cu
```

### 6.3 快速数学 CUDA 候选版本

```bash
nvcc -std=c++17 -O3 -arch=${CUDA_ARCH} \
    -use_fast_math -Xptxas=-v \
    -Xcompiler=-O3,-march=native,-DNDEBUG \
    -o build/cuda_fast/solver \
    src_cuda/*.cu domains/*/*.cu
```

### 6.4 分析版本

```bash
nvcc -std=c++17 -O3 -arch=${CUDA_ARCH} -lineinfo \
    --fmad=true --ftz=false --prec-div=true --prec-sqrt=true \
    -Xptxas=-v \
    -o build/cuda_profile/solver \
    src_cuda/*.cu domains/*/*.cu
```

正式计时二进制与分析二进制分开保存。Profiler 不得挂在正式计时重复上。

### 6.5 不允许盲目限制寄存器

`-maxrregcount` 不是越小越快。过小会造成 register spill，过大又可能降低 occupancy。官方也将其定义为权衡参数。[NVIDIA 编译建议](https://docs.nvidia.com/cuda/archive/13.0.1/cuda-c-best-practices-guide/nvcc-compiler-switches.html)

只有在 Nsight Compute 证明寄存器限制是瓶颈时，才测试：

```text
unlimited, 64, 80, 96, 128 registers/thread
```

最终选择必须同时满足：

- local load/store 不显著上升；
- occupancy 或 eligible warps 改善；
- 内核时间真实下降；
- 根和梯度误差不变。

---

## 7. 必须从被计时路径移除的代码开销

### 7.1 禁止出现在计时循环中的操作

- `malloc/calloc/realloc/free`；
- `cudaMalloc/cudaFree/cudaHostAlloc`；
- 文件读写与 JSON/CSV 序列化；
- `printf/fprintf/std::cout`；
- 随机数生成；
- 参考根生成；
- 输入归一化或格式转换，除非真实应用每次都需要；
- CUDA context 首次创建；
- JIT/模块加载；
- profiler 初始化；
- 每轮重新生成翼型、三角函数或参数查表；
- 每个根单独 kernel launch；
- 每次迭代调用设备同步。

### 7.2 必须预先完成

- 数据读取与校验；
- 主机和设备内存分配；
- pinned memory 注册；
- H2D 静态参数上传；
- 常量表、翼型等距表、锚点表生成；
- CPU/GPU 预热；
- kernel 属性查询；
- stream/event 创建；
- 根区间和领域常数预处理。

### 7.3 防止编译器删除被测计算

不能在核心循环中加入 `volatile` 破坏优化。正确做法是：

1. 正常写入输出数组；
2. 计时结束后计算输出 checksum；
3. 将 checksum 写入结果 JSON；
4. 与参考 checksum/误差统计核对。

---

## 8. C/CUDA 源码级优化要求

### 8.1 CPU

- 热路径函数使用 `static inline`；
- 输入输出指针使用 `restrict`；
- 数组使用 64 字节对齐分配；
- 优先 SoA，避免缓存行内读取无关字段；
- 循环外提取不变量；
- 同时需要正弦和余弦时使用一次 `sincos` 或统一递推；
- 使用 FMA，避免分别乘加；
- 不在迭代内调用通用日志、错误处理或字符串函数；
- 不使用链表、哈希表或动态多态；
- OpenMP 并行放在最外层批量循环；
- 单线程、SIMD、OpenMP 分开报告。

### 8.2 GPU

- 一个线程处理一个样本，或使用 grid-stride loop；
- 批量足够大时避免每个线程处理过多样本造成尾部失衡；
- 固定步快速路径使用 `#pragma unroll`；
- 收敛后使用 predication/active mask 冻结状态，不能让已收敛样本重新跳离根；
- 困难样本写入紧凑 fallback 队列，第二个 kernel 集中纠错；
- 避免同一 warp 中反复混合 FP32、df32 和 FP64 长路径；
- 常用小型只读表放 constant memory，但仅当 warp 内访问地址高度一致；
- block 内复用数据放 shared memory，并检查 bank conflict；
- 所有输入输出全局访存必须合并；
- 中间值保留在寄存器，不写回 global memory；
- 检查局部数组是否因动态索引落入 local memory；
- 不使用 device-side `malloc`、递归、动态并行或单样本 kernel launch；
- 不在热路径中调用 `printf` 或 device assert。

NVIDIA 官方建议减少 host-device 传输、合并小传输并合理使用 pinned memory：[CUDA Best Practices](https://docs.nvidia.com/cuda/archive/11.4.3/cuda-c-best-practices-guide/index.html)。

---

## 9. 条件感知精度与纠错实现

### 9.1 统一误差代理

对简单根使用：

\[
\widehat e_x=
\frac{|F(x)|}{\max(|F_x(x)|,\varepsilon_d)}.
\]

单看 (|F|) 会在 (F_x\approx0) 时误判。每个样本至少输出：

```text
residual_abs
condition_proxy = 1 / max(|Fx|, eps)
forward_error_estimate = |F| / max(|Fx|, eps)
precision_path
status
```

### 9.2 三阶段路径

1. FP32 固定步快速路径；
2. 使用 FP64 计算一次残差、条件代理和梯度风险；
3. 仅对被标记样本使用 df32 或 FP64 重新求解。

建议判据形式：

```c
needs_correction =
    !isfinite(x) ||
    forward_error_estimate > tau_x ||
    fabs(Fx) < tau_gradient ||
    physical_constraint_failed ||
    branch_classification_uncertain;
```

### 9.3 阈值不能用测试集调节

数据拆分：

```text
开发集 60%：算法开发
校准集 20%：冻结 tau_x、tau_gradient、迭代步数
测试集 20%：只运行一次最终报告
```

阈值候选：

```text
tau_x:        1e-5, 3e-6, 1e-6, 5e-7, 1e-7
tau_gradient: 按每个领域 |Fx| 分位数和下游容差确定
```

不能在看到测试结果后选择最佳阈值。

---

## 10. 各领域正式补充实验

## 10.1 BEM

### 方程和算法身份

必须明确区分：

- 光滑解析残差：Newton/Halley/Householder 固定步快速路径；
- 真实翼型查表残差：护栏割线/Brent 稳健路径；
- 查表节点附近：分段可微，单独统计梯度。

不得把两种内核描述成完全相同的固定步高阶算法。

### 数据

- NREL 5MW 真实 57 节点；
- 600 s、48,000 步时域数据；
- 多风机、多风速、多湍流工况组合；
- 制造根控制集；
- 所有历史失败样本。

### 批量规模

```text
57 × K, K = 1, 2, 4, 8, 16, 32, 64, 256,
1024, 4096, 16384, 65536
```

### 必测基线

- OpenFAST/Fortran CPU；
- 同残差 C Brent；
- 同残差 C 割线；
- 同残差 C Newton/Halley（仅光滑区）；
- 朴素 GPU Brent/割线；
- 关闭低分歧优化的 GPU；
- FP64、FP32、df32、adaptive。

### 特别统计

- 插值节点与非节点梯度误差；
- 错误物理分支率；
- 纠错比例；
- α 认证率只能作为辅助信息，不能替代目标根判断。

## 10.2 Kepler

方程：

\[
E-e\sin E-M=0,
\qquad E\in[0,\pi],\ 0\le e<1.
\]

参数分层：

```text
普通区：e ∈ [0, 0.9]
高偏心：e ∈ (0.9, 0.99]
困难区：1-e ∈ [1e-7, 1e-3], M ∈ [1e-8, 1e-2]
```

梯度：

\[
\frac{\partial E}{\partial M}=\frac{1}{1-e\cos E},
\qquad
\frac{\partial E}{\partial e}=\frac{\sin E}{1-e\cos E}.
\]

基线：Brent、Newton、Halley、现代 Kepler 专用近似、朴素 GPU。

关键失败条件：高偏心角点中根误差或梯度误差不能被条件判据识别。

## 10.3 光伏单二极管

方程：

\[
I=I_L-I_0\left[\exp\left(\frac{V+IR_s}{a}\right)-1\right]
-\frac{V+IR_s}{R_{sh}}.
\]

物理协议：

1. 先求真实 (V_{oc})；
2. 正向第一象限只采样 (0\le V\le V_{oc})；
3. 使用 (0\le I\le I_L) 括根；
4. 反向偏置必须作为不同模型和不同实验，不混入正向数据。

参数分层：

```text
IL:   1–12 A
I0:   1e-12–1e-7 A（对数采样）
a:    1.0–2.4 V
Rs:   0.02–0.8 ohm
Rsh:  1e2–10^3.5 ohm
V:    [0, 0.995 Voc]
```

基线：Lambert-W、Brent、Newton、Chandrupatla、Bishop 方法。

必须报告：

- 开路端、短路端和最大功率点附近误差；
- 电流根误差与功率误差；
- (dI/dV) 和对参数的梯度误差；
- 指数溢出/下溢率；
- 快速数学对 `exp` 的影响。

## 10.4 非等温 CSTR

筛选方程：

\[
F(x)=x-\frac{r(x)}{1+r(x)},
\quad
r(x)=Da\exp\left(\frac{\gamma\beta x}{\gamma+\beta x}\right),
\quad x\in[0,1].
\]

必须覆盖：

- 单稳态区域；
- 三根区域；
- 两个折叠点邻域；
- 低稳定、中间不稳定、高稳定分支；
- 冷启动延续和热启动延续。

物理分支不能只由“取最大根/最小根”决定：

- 冷启动使用低稳定分支直至折叠；
- 热启动使用高稳定分支；
- 历史未知时输出 `ROOT_BRANCH_AMBIGUOUS`，不能静默猜测。

梯度在折叠点附近可能发散。此处必须同时报告：

- 原始隐式梯度；
- 条件数；
- 正则化梯度；
- 正则化偏差；
- 是否跨越分支。

## 10.5 Peng–Robinson 负对照

用途：

- 检验一根/三根分类；
- 检验临界点附近梯度；
- 检验通用求解器相对专用三次求根器的开销。

不能要求通用迭代器一定快于解析三次求根器。若专用方法明显更快，应如实作为“通用性的代价”报告。

---

## 11. 实验矩阵

| 编号 | 实验 | 自变量 | 核心输出 |
|---|---|---|---|
| E0 | 高精度正确性 | 领域、难度 | 根/残差/梯度误差 |
| E1 | 批量扩展 | N | 延迟、吞吐、临界规模 |
| E2 | 算法比较 | Brent/割线/Newton/Halley | 同精度时间、失败率 |
| E3 | 精度比较 | FP64/FP32/df32 | 时间—误差 Pareto |
| E4 | 自适应纠错 | `tau_x`,`tau_g` | 纠错率、漏判率 |
| E5 | 低分歧设计 | 固定步/早停/分流 | warp 指标、时间 |
| E6 | 可微性 | 参数、难度 | 梯度误差、非有限率 |
| E7 | 多根与折叠 | 根距、历史 | 分支正确率 |
| E8 | 跨硬件 | 至少两类 GPU | 加速比可迁移性 |
| E9 | 端到端 | H2D+kernel+D2H | 真实工作流时间 |
| E10 | 消融 | 每次关闭一项优化 | 因果性能贡献 |
| E11 | 编译策略 | strict/fast/LTO/PGO | 性能与精度变化 |

批量规模统一使用：

```text
N = 1, 8, 32, 128, 512, 2K, 8K, 32K,
128K, 512K, 2M, 8M, 16M
```

若显存不足，记录最大可运行规模，禁止通过减少输出字段后与未减少字段的基线直接对比。

---

## 12. 消融实验

完整版本记为 `FULL`，依次关闭：

```text
A0  FULL
A1  关闭低分歧固定步/分流
A2  关闭条件感知精度调度
A3  关闭选择性纠错
A4  关闭算子融合
A5  关闭 O(1) 查表（BEM）
A6  关闭 sin/cos 增量递推
A7  df32 改为 FP64
A8  关闭物理热启动
A9  梯度改为迭代展开反传
A10 strict math 与 fast math 对比
```

每项消融必须同时报告时间和精度。若关闭某项使速度变快但错误增加，该项的作用应定义为“可靠性保障”，不能称为性能优化。

---

## 13. GPU Profiling 指标

使用 Nsight Compute：

```bash
ncu --set full \
    --kernel-name regex:solve_.* \
    --export profiles/domain_N \
    build/cuda_profile/solver --manifest manifests/profile.json
```

至少记录：

- kernel duration；
- achieved occupancy；
- active/eligible warps；
- branch efficiency；
- warp execution efficiency；
- global load/store efficiency；
- DRAM throughput；
- L1/L2 hit rate；
- registers/thread；
- local memory load/store；
- shared-memory bank conflict；
- stall barrier / branch resolving / long scoreboard / math pipe throttle。

Nsight 官方建议针对 local memory、寄存器溢出、分支和 warp stall 定位瓶颈：[Nsight Compute Profiling Guide](https://docs.nvidia.com/nsight-compute/ProfilingGuide/index.html)。

不能只看到 occupancy 下降就强行限制寄存器；最终优化依据必须是内核时间。

---

## 14. 计时规范

### 14.1 CPU

- 固定 CPU governor 为 performance；
- 固定进程 CPU affinity；
- 单线程实验绑定独立物理核心；
- 多线程记录 OpenMP 线程数和绑核策略；
- NUMA 系统固定内存与线程节点；
- 使用 `clock_gettime(CLOCK_MONOTONIC_RAW, ...)`；
- 预热至少 10 次；
- 正式重复不少于 30 次；
- 不删除慢样本，除非有外部故障记录。

### 14.2 GPU 纯内核时间

```c
cudaEventRecord(start, stream);
for (int rep = 0; rep < reps; ++rep) {
    solve_batch_cuda<<<grid, block, shared_bytes, stream>>>(...);
}
cudaEventRecord(stop, stream);
cudaEventSynchronize(stop);
cudaEventElapsedTime(&ms, start, stop);
```

短内核必须一次计时多次重复，再除以 `reps`，降低 event 分辨率和 launch 抖动影响。

### 14.3 端到端时间

端到端实验必须另测：

```text
host preprocessing
+ H2D input
+ solver kernel(s)
+ fallback compaction/correction
+ D2H required outputs
+ application-required postprocessing
```

不得把 pinned memory 注册或静态表初始化重复计入每一步，除非真实应用确实每步重新执行。

### 14.4 热状态与功耗

- GPU 先运行 30–60 s 达到稳定温度；
- 每组前后记录温度、功率和时钟；
- 检查是否降频；
- 不同方法随机化执行顺序，避免后运行方法系统性处于更热状态。

---

## 15. 统计验证

### 15.1 正确率

对每个阈值报告：

- 通过数/总数；
- Wilson 95% 置信区间；
- 分领域、分难度、分物理分支结果；
- 失败样本清单。

“样本中 100% 通过”必须写成“未观察到失败”，不能写成数学保证。

### 15.2 误差分布

至少报告：

```text
median, p90, p95, p99, p99.9, max
```

分别统计：

- 根绝对/相对误差；
- 残差；
- 梯度绝对/相对误差；
- 错分支率；
- 非有限率；
- 纠错率和漏判率。

### 15.3 性能

- 报告中位时间和 bootstrap 95% CI；
- 报告吞吐和 ns/root；
- 加速比使用配对重复计算；
- 若加速比置信区间跨过 1，不得称为显著加速。

### 15.4 量化非劣效性

预先冻结：

```text
root error margin
gradient error margin
failure-rate margin
wrong-branch margin
```

只有当误差和失败率的置信上界均低于预设非劣效界值，才能说量化方法“满足要求”。

统计显著不等于工程可接受；阈值必须来自高精度参考和具体应用容差。

---

## 16. 正确性参考

### 16.1 参考根

- 普通样本：FP64 严格 Brent/专用解析方法；
- 困难样本：任意精度计算，建议不少于 100 bit；
- 多根样本：枚举全部可行根后再应用物理规则；
- 参考实现与被测实现不能共享全部代码路径。

### 16.2 参考梯度

三重核验：

1. 解析/自动高精度隐式梯度；
2. 参数正负扰动后整体重新求解；
3. 多步长有限差分收敛检查。

在 (F_x\approx0) 或分支切换点，有限差分本身可能失效，必须单独标记，不得混入普通梯度平均值。

---

## 17. 性能结果无效的情形

出现以下任一情况，相关性能数字不得进入论文主结果：

- 基线未使用 `-O3`；
- CPU 与 GPU 使用不同残差或停止条件；
- 只测 kernel、不说明端到端成本；
- 在计时区间内包含一方独有的 I/O/初始化；
- 未预热 CUDA context；
- 未同步就停止计时；
- 编译器删除了未使用计算；
- 使用 `fast_math` 后未重新核验精度；
- 只报告最快一次；
- 删除失败或慢样本；
- PGO 使用了测试集；
- 根据最终测试结果重新选择阈值；
- 只有单一 GPU 且声称硬件通用；
- GPU 大批量来自重复复制同一容易样本；
- 参考根自身未收敛或物理区间不包含根。

---

## 18. 自动化运行输出

每次运行必须输出一个不可覆盖的 JSON：

```json
{
  "run_id": "20260824T120000Z_kepler_rtx5090_fp32",
  "git_commit": "...",
  "compiler": "nvcc ...",
  "compile_flags": "...",
  "cpu": "...",
  "gpu": "...",
  "driver": "...",
  "cuda": "...",
  "domain": "kepler",
  "method": "adaptive",
  "precision": "fp32_df32_fp64",
  "batch_size": 1048576,
  "warmups": 10,
  "repetitions": 30,
  "kernel_time_ms": [],
  "end_to_end_time_ms": [],
  "root_error_quantiles": {},
  "gradient_error_quantiles": {},
  "failure_counts": {},
  "correction_fraction": 0.0,
  "checksum": "..."
}
```

文件名包含时间、领域、设备、方法和精度，不允许覆盖旧结果。

---

## 19. 分阶段执行顺序

### 阶段 A：先正确

1. 实现统一 C 参考接口；
2. 建立各领域物理括区间和分支规则；
3. 生成 FP64/任意精度参考根；
4. 验证隐式梯度；
5. 保存全部失败样本。

### 阶段 B：再优化 CPU

1. 标量 `strict`；
2. SIMD/SoA；
3. OpenMP；
4. LTO；
5. PGO；
6. `fast_math` 独立核验。

### 阶段 C：实现 GPU

1. 朴素一线程一根；
2. 合并访存和寄存器驻留；
3. 固定步快速路径；
4. 困难样本压缩与二阶段纠错；
5. df32；
6. kernel 融合；
7. Nsight 定位瓶颈。

### 阶段 D：冻结算法

1. 使用校准集选择步数和阈值；
2. 冻结配置与 commit；
3. 在测试集只运行一次主实验；
4. 更换第二种 GPU 重复测试；
5. 生成最终表格和失败案例。

---

## 20. 最终验收标准

只有同时满足以下条件，补充实验才算完成：

- 四个主领域均有 C/CUDA 正式实现；
- CPU 基线全部使用同等级优化；
- 至少两种 GPU；
- 根、残差和梯度均有高精度参考；
- 所有物理错根和失败样本均保留；
- 量化通过预先规定的统计非劣效检验；
- 端到端加速比的 95% CI 下界大于 1；
- 至少完成低分歧和精度调度两项核心消融；
- `strict` 与 `fast_math` 结果分开；
- Nsight 证明主要代码开销已经定位并处理；
- 编译命令、硬件、驱动、commit、输入 manifest 和原始结果全部可追踪。

本规范的目标不是让代码“看起来很优化”，而是确保最终加速来自算法与硬件协同，而不是未优化基线、计时遗漏或精度降低。

