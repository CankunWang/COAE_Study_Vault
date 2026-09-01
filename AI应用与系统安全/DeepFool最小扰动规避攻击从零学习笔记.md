---
id: coae-appsec-deepfool-6d2a903e
title: 'DeepFool 最小扰动规避攻击从零学习笔记'
aliases:
  - DeepFool
  - Minimal Perturbation Attack
domain:
  - 'AI应用与系统安全'
note_type:
  - concept
  - guide
  - checklist
attack_phase:
  - inference
status: draft
tags:
  - coae
  - ai-security
  - adversarial-ml
updated: 2026-08-15
---
# DeepFool 最小扰动规避攻击从零学习笔记

> 适用范围：对抗机器学习基础学习、本地模型鲁棒性评估、课程靶场与明确授权的测试环境。本笔记讨论推理阶段的白盒输入扰动，不修改训练数据、标签或模型参数。
>
> 前置笔记：[[Evasion Attacks与GoodWords攻击安全测试清单与学习笔记]]。相邻笔记：[[稀疏规避攻击与EAD从零学习笔记]]。

---

## 0. 一页总览

### 0.1 DeepFool 解决什么问题

给定分类器 $F$ 和原始输入 $x_0$，DeepFool 希望寻找能够改变模型预测的尽可能小的扰动 $r$：

$$
\min_r\|r\|_2
\quad\text{s.t.}\quad
F(x_0+r)\neq F(x_0)
$$

它与 FGSM 的问题意识不同：

```text
FGSM：给定扰动预算 epsilon，怎样用一步梯度尽量增大损失？
DeepFool：不预先固定预算，至少要改变多少才能跨过最近边界？
```

DeepFool 不仅可以生成对抗样本，也可以把逐样本扰动大小用作局部鲁棒性估计。

### 0.2 核心流程

```text
当前输入 x_i
    → 对各类别 logits 在 x_i 处做一阶线性化
    → 估计到每个竞争类别边界的距离
    → 选择局部最近的边界
    → 沿该边界法向量做最短 L2 投影
    → 在新位置重新计算 logits 与梯度
    → 直到预测类别改变
    → 最后加入轻微 overshoot，确保真正越界
```

### 0.3 一句话记忆

> 线性模型一次正交投影；神经网络反复“局部线性化—投影—重新线性化”，近似追踪最近决策边界。

### 0.4 能力与边界

```text
DeepFool 通常是白盒、非目标、逐样本、迭代式攻击。
标准版本主要寻找较小 L2 扰动。
它给出的是非线性模型最小扰动的高质量近似，不保证全局最优。
高攻击成功率说明攻击可靠，不等于所有样本离边界都很近。
```

---

## 1. 决策边界与最小扰动

### 1.1 决策边界

二分类器可用分数函数 $f(x)$ 表示：

$$
F(x)=
\begin{cases}
+1,&f(x)>0\\
-1,&f(x)<0
\end{cases}
$$

模型恰好无法区分两个类别的位置满足：

$$
f(x)=0
$$

这就是决策边界。在二维空间中，它可能是直线或曲线；在高维输入空间中，则是超平面、分段超平面或更一般的超曲面。

### 1.2 为什么最小扰动是边界距离

如果 $x_0$ 当前位于某一类别区域，想让预测改变，就必须让新点 $x_0+r$ 到达或越过某个类别边界。因此：

```text
寻找最小对抗扰动
等价于
寻找输入到最近模型决策边界的最短路径
```

需要强调，这是模型输入空间中的几何距离，不等同于人类感知距离或真实语义差异。

---

## 2. 二分类线性模型：一次精确投影

### 2.1 线性分类器

设：

$$
f(x)=w^Tx+b
$$

决策边界为：

$$
w^Tx+b=0
$$

在二维空间中它是直线，在三维空间中是平面，在更高维空间中是超平面。梯度处处相同：

$$
\nabla_x f(x)=w
$$

$w$ 正是决策超平面的法向量。

### 2.2 最小 $L_2$ 扰动推导

希望 $x_0+r$ 到达边界：

$$
f(x_0+r)=0
$$

展开得到：

$$
w^Tx_0+b+w^Tr=0
$$

即：

$$
w^Tr=-f(x_0)
$$

在所有满足该约束的扰动中，欧氏范数最小的解为：

$$
\boxed{
r^*=-\frac{f(x_0)}{\|w\|_2^2}w
}
$$

对应的边界距离是：

$$
\boxed{
\|r^*\|_2=\frac{|f(x_0)|}{\|w\|_2}
}
$$

### 2.3 为什么是正交投影

$r^*$ 与法向量 $w$ 平行，因此它垂直于决策超平面。在欧氏几何中，从点到平面的垂直线段最短；任何斜向路径都会成为直角三角形的斜边，长度更大。

这个结论特指 $L_2$ 几何。若改用 $L_1$ 或 $L_\infty$，单位球形状和最优方向都会改变。

### 2.4 数值例子

设：

$$
w=\begin{bmatrix}3\\4\end{bmatrix},\quad
b=-10,\quad
x_0=\begin{bmatrix}3\\2\end{bmatrix}
$$

则：

$$
f(x_0)=3\times3+4\times2-10=7
$$

并且：

$$
\|w\|_2^2=3^2+4^2=25
$$

最小扰动为：

$$
r^*=-\frac{7}{25}
\begin{bmatrix}3\\4\end{bmatrix}
=
\begin{bmatrix}-0.84\\-1.12\end{bmatrix}
$$

扰动后：

$$
x_0+r^*=
\begin{bmatrix}2.16\\0.88\end{bmatrix}
$$

验证：

$$
3(2.16)+4(0.88)-10=0
$$

它恰好位于决策边界，扰动长度为：

$$
\|r^*\|_2=\frac{7}{5}=1.4
$$

---

## 3. 为什么神经网络的边界不是一个全局平面

### 3.1 非线性来自激活函数

两层网络可以写成：

$$
f(x)=W_2\sigma(W_1x+b_1)+b_2
$$

如果没有非线性激活 $\sigma$，多层线性变换仍可合并为一个仿射变换，决策边界依旧是超平面。激活函数使输入空间经历拉伸、压缩、折叠和重新分区，从而形成复杂边界。

### 3.2 梯度随位置变化

在线性模型中：

$$
\nabla f(x)=w
$$

方向处处相同。神经网络中，$\nabla f(x)$ 通常取决于当前输入 $x$。当输入改变时，激活状态、梯度方向、梯度大小和局部边界朝向都可能改变。

因此，一个位置计算出的梯度只描述附近区域，不能保证在很远的位置仍然准确。

### 3.3 ReLU 网络的严谨表述

ReLU：

$$
\operatorname{ReLU}(z)=\max(0,z)
$$

是分段线性的。因此，纯 ReLU 网络的决策函数通常也是分段线性的：

```text
固定激活区域内部：网络等价于一个线性模型，边界局部是平的。
跨越激活区域以后：线性表达式改变，边界朝向发生折转。
整体观察：许多平坦片段拼成复杂折面，看起来弯曲或弯折。
```

Sigmoid、tanh 等光滑激活可以产生真正光滑的曲面。DeepFool 所处理的“非线性边界”包括光滑曲面和 ReLU 分段折面。

---

## 4. 二分类神经网络：迭代线性化

在当前点 $x_i$ 附近对分数函数做一阶泰勒展开：

$$
f(x_i+r)
\approx
f(x_i)+\nabla f(x_i)^Tr
$$

令局部近似到达边界：

$$
f(x_i)+\nabla f(x_i)^Tr_i=0
$$

局部最小 $L_2$ 扰动为：

$$
\boxed{
r_i=
-\frac{f(x_i)}{\|\nabla f(x_i)\|_2^2}
\nabla f(x_i)
}
$$

更新：

$$
x_{i+1}=x_i+r_i
$$

再在 $x_{i+1}$ 处重新计算输出与梯度。总扰动是：

$$
r_{\mathrm{total}}=\sum_{i=0}^{T-1}r_i
$$

每一步只保证在当前线性近似中最短。由于真实网络是非凸、非线性或分段线性的，累计结果不保证是原模型中的全局严格最小扰动。

---

## 5. 多分类 DeepFool

### 5.1 Logits 与当前类别

设网络输出 $K$ 个 logits：

$$
f(x)=[f_0(x),f_1(x),\ldots,f_{K-1}(x)]
$$

当前预测类别为：

$$
k_0=\arg\max_k f_k(x)
$$

类别 $k_0$ 与竞争类别 $k$ 的边界满足：

$$
f_k(x)=f_{k_0}(x)
$$

### 5.2 类别差与梯度差

在当前迭代点 $x_i$ 计算：

$$
b_k=f_k(x_i)-f_{k_0}(x_i)
$$

$$
w_k=
\nabla_x f_k(x_i)-
\nabla_x f_{k_0}(x_i)
$$

其中 $w_k$ 是当前类别与竞争类别局部边界的法向量。

### 5.3 到每个局部边界的距离

当前点到类别 $k$ 局部边界的估计距离为：

$$
d_k=\frac{|b_k|}{\|w_k\|_2}
$$

选择距离最小的竞争类别：

$$
\hat{k}
=
\arg\min_{k\neq k_0}
\frac{|b_k|}{\|w_k\|_2}
$$

沿对应法向量更新：

$$
r_i=
\frac{|b_{\hat{k}}|}
{\|w_{\hat{k}}\|_2^2}
w_{\hat{k}}
$$

### 5.4 非目标攻击

标准 DeepFool 不预先指定目标类别。它每轮选择局部估计下最近的竞争边界：

```text
7 → 2 并不表示攻击者要求把 7 画成 2；
它只表示在该样本附近，模型最先跨入了类别 2 的区域。
```

攻击目标是改变模型决策，不是生成符合人类语义的目标数字。

---

## 6. Overshoot、裁剪与终止条件

### 6.1 为什么需要 overshoot

局部投影可能恰好停在估计边界上。由于浮点误差、边界曲率、ReLU 区域切换和线性化误差，它未必真正进入另一个类别区域。因此最终常使用：

$$
x_{\mathrm{adv}}
=
x_0+(1+\eta)r_{\mathrm{total}}
$$

$\eta$ 是很小的 overshoot，例如 $0.02$。它表示在累计扰动上增加 2%，不是给像素增加固定的 0.02。

### 6.2 输入裁剪

对抗样本必须留在模型合法输入范围内：

$$
x_{\mathrm{adv}}
=
\operatorname{clip}(x_{\mathrm{adv}},x_{\min},x_{\max})
$$

若模型接收归一化输入，裁剪范围也必须转换到归一化坐标。例如像素范围 $[0,1]$ 经：

$$
x_{\mathrm{norm}}=\frac{x-\mu}{\sigma}
$$

转换后：

$$
x_{\min}=\frac{0-\mu}{\sigma},\qquad
x_{\max}=\frac{1-\mu}{\sigma}
$$

不能直接对归一化张量裁剪到 $[0,1]$。

### 6.3 终止条件

常见停止条件：

```text
预测类别已经不同于原始预测类别；
达到 max_iter；
出现数值异常或无有效竞争边界；
达到实验预先规定的资源和时间预算。
```

达到 `max_iter` 仍未改变类别属于失败或截断结果，不能把最后的扰动当作已找到的边界距离。

---

## 7. 与 FGSM、PGD、EAD 的对比

| 攻击 | 主要问题 | 约束或目标 | 典型方法 |
|---|---|---|---|
| FGSM | 固定预算内如何一步制造错误 | 常见 $L_\infty\le\epsilon$ | 一次梯度符号更新 |
| PGD | 固定预算内如何反复寻找更强攻击 | 常见 $L_\infty/L_2$ 球 | 梯度更新后投影回预算集合 |
| DeepFool | 到最近决策边界约需多大扰动 | 最小化常见 $L_2$ 扰动 | 局部线性化与正交投影 |
| EAD | 如何兼顾总体变化与稀疏性 | $L_2^2+\beta L_1$ | FISTA、软阈值与 $c$ 搜索 |

FGSM 使用梯度符号：

$$
r_{\mathrm{FGSM}}
=
\epsilon\operatorname{sign}(\nabla_xJ)
$$

在没有裁剪且梯度非零时，各维度绝对变化相同。DeepFool 保留梯度差的相对大小，因此不同像素通常具有不同变化幅度。但 $L_2$-DeepFool 并不直接优化稀疏性，不能把它描述成只修改少量像素的攻击。

---

## 8. 目标模型与梯度环境

### 8.1 为什么必须使用训练好的模型

未训练模型的预测和梯度主要反映随机参数，其决策边界没有实际任务意义。DeepFool 评估成立的前提包括：

```text
模型在干净测试集上达到合理准确率；
输入预处理与训练时一致；
模型版本和参数固定；
攻击时的输出与输入梯度稳定；
实验记录随机种子、数据版本和依赖版本。
```

### 8.2 `model.eval()` 与梯度

```python
model.eval()
```

它会关闭 Dropout 的随机丢弃，并让 BatchNorm 使用推理统计量，从而使迭代输出与梯度稳定。

`model.eval()` 不会关闭自动求导。DeepFool 仍需：

```python
x = x.detach().requires_grad_(True)
logits = model(x)
gradient = torch.autograd.grad(logits[0, k], x)[0]
```

不能把 DeepFool 的梯度计算放进：

```python
with torch.no_grad():
    ...
```

`no_grad()` 只适合基线预测和攻击后的独立验证。

### 8.3 Dropout 的准确理解

Dropout 的主要职责是正则化和抑制过拟合。它可能改变最终学到的边界，但不能保证边界必然更平滑、更真实或更鲁棒。是否改善对抗鲁棒性必须通过实验验证。

### 8.4 模型缓存安全

优先保存和加载 `state_dict`，并显式记录架构、预处理和训练配置。保存完整 `nn.Module` 不会自动保存外部优化器状态；若要恢复训练，必须另存 `optimizer.state_dict()`。

PyTorch 模型文件可能涉及 Pickle 反序列化风险，只加载可信来源和完成完整性校验的模型制品。相关内容见 [[模型文件安全审查速查表]]。

---

## 9. PyTorch 单样本实现骨架

下面代码强调算法结构和审计点，适用于形状为 `[1, C, H, W]` 的单样本。正式实验还应增加数值异常、设备、类型和日志检查。

```python
import torch


def deepfool_l2_single(
    image,
    model,
    num_classes=None,
    overshoot=0.02,
    max_iter=50,
    clip_min=None,
    clip_max=None,
    eps=1e-8,
):
    if image.shape[0] != 1:
        raise ValueError("This implementation expects batch size 1.")
    if num_classes is not None and num_classes < 2:
        raise ValueError("num_classes must include at least two classes.")

    model.eval()
    original = image.detach().clone()

    with torch.no_grad():
        original_logits = model(original)
        original_label = original_logits.argmax(dim=1).item()

    total_r = torch.zeros_like(original)
    iterations = 0

    for iteration in range(max_iter):
        current = (original + total_r).detach()
        current.requires_grad_(True)
        logits = model(current)
        current_label = logits.argmax(dim=1).item()

        if current_label != original_label:
            break

        ranked = logits[0].argsort(descending=True)
        if num_classes is not None:
            ranked = ranked[:num_classes]

        grad_original = torch.autograd.grad(
            logits[0, original_label],
            current,
            retain_graph=True,
        )[0]

        best_distance = None
        best_w = None
        best_f = None

        for class_index in ranked.tolist():
            if class_index == original_label:
                continue

            grad_class = torch.autograd.grad(
                logits[0, class_index],
                current,
                retain_graph=True,
            )[0]

            w_k = grad_class - grad_original
            f_k = logits[0, class_index] - logits[0, original_label]
            w_norm = torch.linalg.vector_norm(w_k)

            if w_norm.item() <= eps:
                continue

            distance = torch.abs(f_k) / w_norm

            if best_distance is None or distance < best_distance:
                best_distance = distance.detach()
                best_w = w_k.detach()
                best_f = f_k.detach()

        if best_w is None:
            break

        best_w_norm_sq = torch.sum(best_w ** 2)
        step = (
            (torch.abs(best_f) + eps)
            / (best_w_norm_sq + eps)
        ) * best_w

        total_r = total_r + step
        iterations = iteration + 1

    adversarial = original + (1.0 + overshoot) * total_r

    if clip_min is not None or clip_max is not None:
        min_value = -torch.inf if clip_min is None else clip_min
        max_value = torch.inf if clip_max is None else clip_max
        adversarial = torch.clamp(adversarial, min_value, max_value)

    adversarial = adversarial.detach()
    actual_delta = adversarial - original

    with torch.no_grad():
        adversarial_label = model(adversarial).argmax(dim=1).item()

    return {
        "adversarial": adversarial,
        "perturbation": actual_delta,
        "original_label": original_label,
        "adversarial_label": adversarial_label,
        "iterations": iterations,
        "success": adversarial_label != original_label,
    }
```

关键审计点：

```text
[ ] 使用 logits，不用 Softmax 概率构造类别边界
[ ] 每轮在新位置重新计算 logits 和输入梯度
[ ] 比较类别梯度差，而不是只看单个类别梯度
[ ] 跳过梯度差范数接近零的类别
[ ] overshoot 的应用位置与返回扰动定义明确
[ ] 返回前按最终 adversarial 重新验证标签
[ ] 范数统计使用 adversarial - original 的实际差值
[ ] 归一化输入使用归一化后的合法裁剪范围
```

---

## 10. 单样本实验应记录什么

### 10.1 基线

```python
with torch.no_grad():
    clean_logits = model(image)
    clean_label = clean_logits.argmax(dim=1).item()
    clean_confidence = clean_logits.softmax(dim=1).max().item()
```

记录：

```text
真实标签
原始预测标签
是否原始分类正确
原始 logits 与 softmax 置信度
模型、数据、预处理与代码版本
```

通常只把原本分类正确的样本纳入标准攻击成功率。

### 10.2 实际扰动

如果最终样本经过 overshoot 和裁剪，应直接计算：

```python
delta = perturbed_image.detach() - image.detach()
l2 = torch.linalg.vector_norm(delta).item()
linf = delta.abs().max().item()
relative_l2 = l2 / max(
    torch.linalg.vector_norm(image).item(),
    1e-12,
)
```

不要默认返回的内部 `r_total` 就等于最终图片的真实差值。

### 10.3 边界 margin

十分类模型不使用统一的 0.5 决策阈值。攻击后最大 softmax 概率为 0.404，模型仍可能预测该类别，只要它比其他九类都大。

更直接的局部边界指标是新类别与原类别的 logit 差：

$$
m=f_{k_{\mathrm{adv}}}(x_{\mathrm{adv}})
-f_{k_0}(x_{\mathrm{adv}})
$$

```python
margin = (
    adv_logits[0, adversarial_label]
    - adv_logits[0, original_label]
).item()
```

若 $0<m\ll1$，说明样本刚进入新类别区域。但小 margin 仍不能严格证明扰动是全局最小。

---

## 11. 扰动范数与坐标尺度

### 11.1 $L_2$

$$
\|\delta\|_2
=
\sqrt{\sum_j\delta_j^2}
$$

它衡量总体欧氏变化，是标准 DeepFool 最直接对应的指标。

### 11.2 $L_\infty$

$$
\|\delta\|_\infty
=
\max_j|\delta_j|
$$

它表示变化最大的单个坐标改动多少，不表示总扰动能量。

### 11.3 相对 $L_2$

$$
\rho(x)=\frac{\|\delta\|_2}{\|x\|_2}
$$

它便于比较输入幅度不同的样本，但暗图或低能量样本的分母较小，结果可能偏大，不能替代绝对范数。

### 11.4 归一化空间与像素空间

若：

$$
x_{\mathrm{norm}}=\frac{x-\mu}{\sigma}
$$

则扰动满足：

$$
\delta_{\mathrm{pixel}}=\sigma\delta_{\mathrm{norm}}
$$

报告范数时必须说明是在归一化空间还是原始像素空间计算。两个实验只有在相同预处理和相同坐标尺度下才可直接比较。

### 11.5 $L_2/L_\infty$ 不能证明稀疏

可以构造有效参与维度指标：

$$
n_{\mathrm{eff}}
=
\left(
\frac{\|\delta\|_2}{\|\delta\|_\infty}
\right)^2
$$

它可以辅助描述扰动集中度，但不等于真实非零像素数量。浮点扰动可能分布在很多位置。真正修改坐标数量应使用带容差的 $L_0$ 统计。

---

## 12. 批量攻击生成

### 12.1 为什么常逐样本处理

不同样本可能在不同轮次终止：

```text
样本 A：1 轮成功
样本 B：3 轮成功
样本 C：7 轮成功
```

教学实现常使用 `batch_size=1`，依次执行单样本 DeepFool。这是“一组单样本攻击”，不是普通训练意义上的统一向量化 batch。

真正向量化时需要为未成功样本维护 active mask，只更新仍在攻击中的样本。

### 12.2 安全保存结果

```python
original_cpu = data.detach().cpu()
adversarial_cpu = perturbed_image.detach().cpu()
delta_cpu = adversarial_cpu - original_cpu
```

使用 `detach().cpu()`：

```text
detach：切断自动求导计算图
cpu：把结果转移到主存
```

只调用 `.cpu()` 不一定切断计算图，循环保存结果时可能保留不必要的中间状态。

### 12.3 每个样本的推荐字段

```text
sample_index
true_label
original_label
adversarial_label
originally_correct
prediction_flipped
success
iterations
L2、L∞、relative L2
clean confidence、adversarial confidence、logit margin
original image、adversarial image、actual perturbation
```

### 12.4 攻击成功率

标准攻击成功率的合理分母是原本分类正确、并实际参与攻击的样本：

$$
\mathrm{ASR}
=
\frac{
\#\{F(x)=y\ \land\ F(x_{\mathrm{adv}})\neq y\}
}{
\#\{F(x)=y\}
}
$$

若只检查：

$$
F(x_{\mathrm{adv}})\neq F(x)
$$

则指标更准确地叫 prediction-flip rate。原本已经分类错误的样本不能算作标准攻击成功。

---

## 13. 批量统计与正确解释

### 13.1 不要只报告平均数

最低限度建议报告：

```text
处理样本数
原始正确样本数
攻击成功数与 ASR
L2 均值、中位数、标准差、四分位数和范围
相对 L2 中位数与四分位数
成功样本的迭代次数分布
每类样本数量
类别转移频率及对应扰动中位数
失败和 max_iter 截断样本数量
```

少量极端值可能显著拉动平均数，因此中位数和分位数通常更能代表典型样本。

### 13.2 迭代次数不等于边界距离

| 情况 | $L_2$ 距离 | 迭代次数 | 可能解释 |
|---|---:|---:|---|
| A | 大 | 少 | 边界较远，但局部较平 |
| B | 小 | 多 | 边界很近，但弯曲或频繁折转 |
| C | 小 | 少 | 边界又近又平 |
| D | 大 | 多 | 边界较远且局部几何复杂 |

迭代次数主要反映局部线性近似需要修正多少次；扰动范数更接近描述输入到边界的距离。

### 13.3 每类成功率不等于每类脆弱性

如果所有类别 ASR 都接近 100%，成功率图无法区分类别边界距离。更适合比较：

$$
\operatorname{median}
\left(
\|\delta_i\|_2\mid y_i=c
\right)
$$

并同时标注每类样本量 $n_c$。没有样本应显示为缺失值，不应画成 0%，因为“没有测试”和“全部失败”含义不同。

### 13.4 类别转移

定义：

$$
C_{ij}
=
\#\{F(x)=i,\ F(x_{\mathrm{adv}})=j\}
$$

条件转移率为：

$$
P(j\mid i)
=
\frac{C_{ij}}{\sum_kC_{ik}}
$$

某个转移出现较多，可能与源类别样本数量、书写风格和局部模型边界有关，不能仅凭频次断言两个类别的全局边界最近。应同时报告转移样本量和对应的扰动中位数。

### 13.5 小样本限制

固定取测试集前 20 张适合演示流程，不适合得出稳定的类别结论。更可靠的设计包括：

```text
随机或分层抽样；
每类使用相同或足够的样本量；
固定随机种子并记录样本 ID；
扩大到每类数百张或完整测试集；
跨模型版本和随机种子复测；
必要时报告置信区间。
```

---

## 14. 空间扰动可视化

### 14.1 带符号热力图

使用以零为中心的发散色图：

```python
delta = result["perturbation"].squeeze().numpy()
limit = max(float(abs(delta).max()), 1e-8)

ax.imshow(
    delta,
    cmap="RdBu_r",
    vmin=-limit,
    vmax=limit,
)
```

红色表示增加，蓝色表示减少，接近白色表示接近零。`vmin` 与 `vmax` 对称才能让零处于颜色图中央。

### 14.2 每图缩放与全局缩放

```text
每张图单独使用自己的最大值：适合观察空间形状，但颜色不能跨样本比较。
所有图使用同一个全局最大值：适合比较绝对大小，但小扰动图可能不明显。
```

图标题或图注必须说明使用哪一种缩放方式。

### 14.3 放大只用于显示

$$
\delta_{\mathrm{display}}=10\delta
$$

放大十倍不会改变攻击结果，只是让微小差异可见。图中必须明确标注 `×10`。固定 `vmin/vmax` 还可能裁掉超出色域的数值，应检查实际范围。

### 14.4 真正的 overlay

```python
ax.imshow(original_pixel, cmap="gray", vmin=0, vmax=1)
ax.imshow(
    abs(delta_pixel),
    cmap="inferno",
    alpha=0.65,
    vmin=0,
    vmax=global_abs_max,
)
```

先画原图，再以半透明方式覆盖绝对扰动，才是“扰动叠加在原图上”。单独显示 `adv - orig` 只是差分图。

### 14.5 热力图的证据边界

笔画附近出现大扰动，只能说明局部边界法向量在这些位置具有较大分量。热力图不能单独证明模型学到了人类语义，也不能证明扰动全局最小或严格稀疏。

---

## 15. DeepFool 安全评估清单

### 15.1 测试前

```text
[ ] 已获得明确授权，使用隔离、可恢复的模型和数据副本
[ ] 固定模型、权重、数据、预处理、代码和依赖版本
[ ] 记录随机种子、设备和数值精度
[ ] 建立干净准确率、逐类指标和置信度基线
[ ] 明确白盒能力：能访问 logits 和输入梯度
[ ] 明确使用 L2 DeepFool 还是其他范数变体
[ ] 定义 max_iter、overshoot、候选类别数和停止条件
[ ] 明确输入合法范围及归一化后的裁剪边界
```

### 15.2 实现审计

```text
[ ] 攻击时使用 model.eval()，但没有错误关闭输入梯度
[ ] 使用 logits 差和输入梯度差构造多分类边界
[ ] 每轮在最新位置重新线性化
[ ] 每个样本独立维护原始类别、累计扰动和迭代状态
[ ] 返回前根据最终对抗图片重新计算标签
[ ] 保存结果前使用 detach().cpu()
[ ] 实际范数使用 final_adv - original 计算
[ ] 区分归一化空间和像素空间指标
[ ] 失败样本、数值异常和 max_iter 截断被单独记录
```

### 15.3 结果报告

```text
[ ] ASR 分母只包含原始分类正确且实际被攻击的样本
[ ] prediction-flip rate 与标准 ASR 没有混用
[ ] 同时报告均值、中位数、四分位数和样本量
[ ] 迭代次数只在成功样本或明确口径下统计
[ ] 每类结果带有样本量，缺失类别不记为 0%
[ ] 类别转移同时报告条件频率与扰动大小
[ ] 可视化注明色域、放大倍数、坐标空间和是否逐图缩放
[ ] 没有把 softmax 低于 0.5 当作十分类边界条件
[ ] 没有把局部最短近似描述为全局严格最优
```

### 15.4 防御与回归

```text
[ ] 比较防御前后的干净准确率与 DeepFool 边界距离分布
[ ] 不只看平均 ASR，还检查低分位数的脆弱样本
[ ] 建立版本化对抗回归集，并避免只针对单一攻击过拟合
[ ] 同时覆盖 L∞、L2、L1/L0 等不同威胁模型
[ ] 检查输入过滤是否显著伤害正常样本或特定群体
[ ] 记录模型升级后原有脆弱转移是否复现
```

---

## 16. 常见误区

### 16.1 “DeepFool 找到的一定是全局最小扰动”

错误。线性分类器中投影是精确解；非线性神经网络中，DeepFool 通过局部一阶近似寻找较小扰动，不保证非凸问题的全局最优。

### 16.2 “置信度越高，离边界一定越远”

错误。Softmax 置信度描述 logits 的相对大小，不直接等于输入空间中的几何距离。模型可能高置信但靠近边界。

### 16.3 “攻击后置信度低于 0.5 才算越界”

错误。多分类预测取最大 logit 或最大概率，不使用统一的 0.5 阈值。边界由两个类别 logits 相等决定。

### 16.4 “迭代次数越多，样本越鲁棒”

错误。迭代次数主要反映局部线性近似修正难度；鲁棒性距离应主要看实际扰动范数。

### 16.5 “热力图集中说明扰动是稀疏的”

错误。颜色强弱只描述幅度分布。$L_2$ 目标不直接最小化非零坐标数量，真正稀疏性应使用带容差的 $L_0$ 等指标。

### 16.6 “攻击 20 张全部成功，整体成功率就是 100%”

错误。只能说明当前抽取的 20 张样本全部成功。固定前 20 张可能有选择偏差，无法替代大规模分层评估。

### 16.7 “Dropout 会让决策边界必然更真实、更鲁棒”

错误。Dropout 是正则化机制，可能改善泛化，但其对对抗鲁棒性的影响需要独立测量。

### 16.8 “保存完整模型会自动保存优化器”

错误。外部优化器状态必须显式保存。加载不可信的完整模型对象还可能带来反序列化风险。

---

## 17. 复习卡片

### 17.1 核心定义

```text
Q：DeepFool 的核心目标是什么？
A：近似寻找能够改变模型预测的最小扰动，标准版本常以 L2 衡量。

Q：线性分类器的最短 L2 路径是什么？
A：从输入点到决策超平面的正交投影。

Q：神经网络为什么需要迭代？
A：一个位置的一阶线性近似只在局部有效，移动后必须重新计算边界方向。
```

### 17.2 多分类公式

```text
Q：w_k 是什么？
A：竞争类别与原类别的输入梯度差：grad f_k - grad f_k0。

Q：b_k 是什么？
A：竞争类别与原类别的 logit 差：f_k - f_k0。

Q：局部边界距离如何估计？
A：|b_k| / ||w_k||_2。

Q：每轮选哪个类别？
A：选择上述局部距离最小的竞争类别。
```

### 17.3 实现与评估

```text
Q：model.eval() 会关闭梯度吗？
A：不会；它只改变 Dropout、BatchNorm 等层的运行行为。

Q：为什么最终范数用 adv - original？
A：因为 overshoot 和裁剪可能使最终实际扰动不同于内部累计 r。

Q：DeepFool 的成功率如何计算？
A：通常以原本分类正确且实际参与攻击的样本为分母。

Q：迭代次数等于鲁棒性吗？
A：不等于；迭代次数偏向描述边界线性化难度，范数偏向描述边界距离。
```

### 17.4 最终记忆链

```text
输入 x
→ 得到原始预测类别 k0
→ 比较 k0 与每个竞争类别的 logit 差和梯度差
→ 估计到各局部边界的 L2 距离
→ 选择最近边界并正交投影
→ 在新位置重新线性化
→ 类别改变后应用轻微 overshoot 与合法裁剪
→ 用最终 adv - x 计算实际扰动
→ 在原始正确样本上统计 ASR、范数分布和类别转移
```

---

## 18. 最终总结

DeepFool 把对抗样本生成转化为决策边界几何问题。在线性分类器上，最小 $L_2$ 扰动是输入点到超平面的精确正交投影；在神经网络上，它在当前位置将类别边界一阶线性化，比较所有竞争类别的局部距离，朝最近边界投影，再在新位置重新计算，直到预测改变。

它的价值不只是“让模型出错”，还在于提供逐样本的局部鲁棒性估计。但解释结果时必须区分：攻击成功率与边界距离、迭代次数与扰动范数、softmax 置信度与几何 margin、归一化坐标与像素坐标、局部近似最小与全局严格最优。

安全评估最终应回答：

```text
模型对哪些原始正确样本最靠近决策边界？
这种脆弱性是否跨样本、类别、随机种子和模型版本稳定复现？
实际扰动在什么坐标尺度和威胁模型下足够小？
防御是否增加边界距离，同时保持干净准确率和正常输入可用性？
修复后的版本是否通过同一批版本化对抗回归样本？
```
