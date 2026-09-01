---
id: coae-appsec-ead-7c4f31a2
title: '稀疏规避攻击与 EAD 从零学习笔记'
aliases:
  - Sparsity Evasion Attacks
  - Elastic-Net Attack
  - EAD
domain:
  - 'AI应用与系统安全'
note_type:
  - concept
  - guide
attack_phase:
  - inference
status: draft
tags:
  - coae
  - ai-security
  - adversarial-ml
updated: 2026-08-17
---
# 稀疏规避攻击与 EAD 从零学习笔记

> 适用范围：对抗机器学习基础学习、本地模型鲁棒性评估、课程靶场与明确授权的测试环境。本笔记讨论推理阶段输入扰动，不修改训练数据、标签或模型参数。
>
> 前置笔记：[[Evasion Attacks与GoodWords攻击安全测试清单与学习笔记]]。
>
> 考试代码：[[EAD考试可复用代码库]]；完整模块：[ead_exam_template.py](../_工具/ead_exam_template.py)。

---

## 0. 一页总览

### 0.1 稀疏攻击是什么

稀疏攻击希望通过修改尽可能少的输入坐标，让模型产生错误预测。设原始输入为 $x$，对抗输入为 $x_{\mathrm{adv}}$，扰动为：

$$
\delta=x_{\mathrm{adv}}-x
$$

修改坐标的数量由 $L_0$ 伪范数表示：

$$
\|\delta\|_0
=
\left|\{i:\delta_i\neq 0\}\right|
$$

核心区别：

```text
L∞ / L2 攻击：主要限制每个变化或总体变化有多大
L0 稀疏攻击：主要限制有多少个特征发生变化
```

稀疏并不等于幅度小。只修改一个像素但把它改到极端值，仍然有 $L_0=1$。

### 0.2 EAD 是什么

EAD，全称 Elastic-Net Attack，是一种将攻击损失、平方 $L_2$ 与 $L_1$ 正则结合的优化攻击：

$$
\min_{x'\in[0,1]^d}
c f_{\mathrm{adv}}(x')
+\|x'-x\|_2^2
+\beta\|x'-x\|_1
$$

各部分职责：

| 组件 | 作用 |
|---|---|
| $f_{\mathrm{adv}}$ | 推动模型达到攻击目标 |
| $c$ | 控制攻击压力 |
| (\|x'-x\|_2^2) | 限制总体扰动，抑制大的单坐标变化 |
| (\beta\|x'-x\|_1) | 促进扰动稀疏 |
| FISTA | 求解包含平滑项与非平滑 $L_1$ 项的目标 |
| 软阈值 | 实现 $L_1$ 的近端更新，制造精确的零 |
| 二分搜索 | 为每个样本寻找合适的攻击权重 $c$ |

### 0.3 一句话理解整套算法

```text
对抗损失告诉 EAD 往哪里改；
L2 把修改拉回原图；
L1 软阈值删除不重要的小修改；
FISTA 用动量加速内层优化；
二分搜索寻找刚好足以攻击成功的 c。
```

---

## 1. 从输入、模型和对抗样本开始

### 1.1 图像如何表示

一张 (28\times28) 的 MNIST 灰度图片共有：

$$
28\times28=784
$$

个像素，可以写成：

$$
x=[x_1,x_2,\ldots,x_{784}],\qquad x_i\in[0,1]
$$

模型输出十个类别的原始分数：

$$
Z(x)=[Z_0(x),Z_1(x),\ldots,Z_9(x)]
$$

这些原始分数叫 logits，模型预测为：

$$
\hat y=\arg\max_j Z_j(x)
$$

### 1.2 对抗样本

攻击者构造：

$$
x_{\mathrm{adv}}=x+\delta
$$

其中 $\delta$ 是扰动。非目标攻击要求：

$$
F(x_{\mathrm{adv}})\neq y
$$

目标攻击要求：

$$
F(x_{\mathrm{adv}})=t
$$

其中 $y$ 是原始类别，$t$ 是攻击者指定的目标类别。

### 1.3 训练与攻击的区别

| 阶段 | 固定对象 | 优化对象 | 常见目标 |
|---|---|---|---|
| 模型训练 | 输入与标签 | 模型参数 $\theta$ | 降低分类损失 |
| EAD 攻击 | 模型参数 $\theta$ | 对抗输入 $x'$ | 达到误分类并限制扰动 |

训练更新：

$$
\theta\leftarrow\theta-\eta\nabla_\theta L
$$

攻击更新：

$$
x'\leftarrow x'-\eta\nabla_{x'}L
$$

---

## 2. 范数与扰动距离

### 2.1 $L_0$：改变了多少个坐标

$$
\|\delta\|_0
=
\#\{i:\delta_i\neq0\}
$$

例如：

$$
\delta=[0.2,-0.3,0,0.1]
$$

有三个非零坐标，因此：

$$
\|\delta\|_0=3
$$

$L_0$ 不关心每个坐标变化多大，只统计非零数量。严格来说，它不满足范数的全部条件，因此叫伪范数。

### 2.2 $L_1$：绝对变化总量

$$
\|\delta\|_1=\sum_i|\delta_i|
$$

对于同一扰动：

$$
\|\delta\|_1
=|0.2|+|-0.3|+0+|0.1|
=0.6
$$

$L_1$ 不是修改数量。50 个像素各改 $0.3$，与 100 个像素各改 $0.15$，都有 $L_1=15$，但 $L_0$ 分别为 50 和 100。

### 2.3 $L_2$ 与平方 $L_2$

真正的欧氏距离是：

$$
\|\delta\|_2
=
\sqrt{\sum_i\delta_i^2}
$$

EAD 目标中常用平方 $L_2$：

$$
\|\delta\|_2^2
=
\sum_i\delta_i^2
$$

二者不是同一个数。代码：

```python
l2_squared = torch.sum(delta ** 2, dim=(1, 2, 3))
l2 = torch.sqrt(l2_squared)
```

平方 $L_2$ 的梯度很简单：

$$
\nabla_{x'}\|x'-x\|_2^2=2(x'-x)
$$

它像恢复力：偏离原图越远，拉回力越强。

### 2.4 为什么 $L_2^2$ 偏好分散变化

比较：

$$
\delta_A=[1,0],\qquad
\delta_B=[0.5,0.5]
$$

二者的 $L_1$ 都是 1，但：

$$
\|\delta_A\|_2^2=1,qquad
\|\delta_B\|_2^2=0.5
$$

所以纯 $L_2^2$ 优化常将修改分散到许多坐标，产生密集但较小的变化。

### 2.5 Elastic-Net 扰动代价

$$
D_{\mathrm{EN}}(\delta)
=
\|\delta\|_2^2
+\beta\|\delta\|_1
$$

它不是严格意义上的范数，因为平方 $L_2$ 不满足范数的齐次性。更严谨的称呼是 Elastic-Net 正则项或扰动代价。

---

## 3. 正则化基础

### 3.1 什么是正则化

正则化是在主要目标之外加入一个惩罚项，用来限制不希望出现的行为：

$$
\text{总目标}
=
\text{主要任务}
+\lambda\times\text{惩罚}
$$

如果攻击只优化误分类，可能把图片改得面目全非。加入距离正则后，修改输入需要付出代价。

### 3.2 硬约束与惩罚项

硬约束：

$$
\min_{x'}f(x')
\quad\text{s.t.}\quad
\|x'-x\|\leq\epsilon
$$

表示绝对不能超过预算。

惩罚形式：

$$
\min_{x'}f(x')+\lambda\|x'-x\|^2
$$

表示扰动越大，代价越大，但不直接规定一个范数上限。

EAD 使用惩罚形式，同时保留像素范围硬约束：

$$
x'\in[0,1]^d
$$

### 3.3 $L_1$ 正则

$$
\beta\|\delta\|_1
=
\beta\sum_i|\delta_i|
$$

$L_1$ 在零点有尖角，并通过其近端算子把小坐标精确压成零，因此能促进稀疏。

### 3.4 $L_2^2$ 正则

$$
\lambda\|\delta\|_2^2
=
\lambda\sum_i\delta_i^2
$$

它对大坐标的惩罚按平方增长，优化平滑，但通常不会自然产生大量精确的零。

### 3.5 $L_1$ 与 $L_2^2$ 对比

| 特性 | $L_1$ | $L_2^2$ |
|---|---|---|
| 计算 | 绝对值之和 | 平方之和 |
| 零点 | 不光滑 | 光滑 |
| 常见行为 | 清除不重要坐标 | 分散并限制大变化 |
| 是否易产生精确零 | 是，配合近端更新 | 通常不会 |
| EAD 中处理方式 | 软阈值 | 普通梯度 |

---

## 4. 为什么叫 Elastic Net

Elastic Net 最初是统计学习中的混合正则化方法，将 Lasso 的 $L_1$ 与 Ridge 的 $L_2^2$ 结合：

$$
\lambda_1\|w\|_1+\lambda_2\|w\|_2^2
$$

EAD 将同样的结构应用于对抗扰动：

$$
\beta\|\delta\|_1+\|\delta\|_2^2
$$

因此沿用 Elastic Net 这个名字。

直观理解：

```text
L1 像筛选器：删除不重要的坐标。
L2² 像弹性带：偏离越远，拉回力越强。
两种力量共同限制解，形成“有弹性的网”。
```

这里的 Net 不是 neural network 的缩写，也不是网络攻击中的“网络”。准确含义就是 $L_1+L_2^2$ 混合正则。

---

## 5. 交叉熵基础

### 5.1 Softmax

模型先输出 logits $z_j$，Softmax 将其转换成概率：

$$
p_j=\frac{e^{z_j}}{\sum_k e^{z_k}}
$$

结果满足：

$$
0<p_j<1,
\qquad
\sum_jp_j=1
$$

### 5.2 交叉熵

若真实类别为 $y$，多分类交叉熵为：

$$
L_{\mathrm{CE}}=-\log p_y
$$

完整分布形式为：

$$
H(q,p)=-\sum_jq_j\log p_j
$$

其中 $q$ 是真实标签分布，$p$ 是模型预测分布。对于 one-hot 标签，只有正确类别项会保留。

规律：

$$
p_y\uparrow\Rightarrow L_{\mathrm{CE}}\downarrow
$$

$$
p_y\downarrow\Rightarrow L_{\mathrm{CE}}\uparrow
$$

### 5.3 PyTorch 用法

```python
loss = F.cross_entropy(logits, labels)
```

不要先手动执行 Softmax：

```python
# 不推荐
probabilities = torch.softmax(logits, dim=1)
loss = F.cross_entropy(probabilities, labels)
```

`F.cross_entropy` 已在内部执行数值稳定的 `log_softmax + NLL`。

### 5.4 交叉熵在攻击中的方向

| 场景 | 做法 |
|---|---|
| 正常训练 | 最小化真实标签交叉熵 |
| 非目标攻击 | 增大真实标签交叉熵 |
| 目标攻击 | 最小化目标标签交叉熵 |

FGSM 非目标更新常写成：

$$
x_{\mathrm{adv}}
=x+\epsilon\operatorname{sign}
(\nabla_xL_{\mathrm{CE}}(x,y))
$$

---

## 6. EAD 使用的 C&W Margin Loss

### 6.1 为什么不用成功/失败指示函数

若定义：

$$
I(x')=
\begin{cases}
0,&\text{攻击成功}\cr
1,&\text{攻击失败}
\end{cases}
$$

它可以判断结果，却不能区分“离边界很远”和“几乎成功”，并且无法提供有效梯度。

### 6.2 Margin 是什么

Margin 是类别 logits 的差距。设真实类别分数为 $Z_y$，最强竞争类别为：

$$
Z_{\mathrm{other}}=\max_{j\neq y}Z_j
$$

那么真实类别的领先 margin 是：

$$
Z_y-Z_{\mathrm{other}}
$$

### 6.3 非目标攻击损失

$$
f_{\mathrm{untargeted}}(x',y)
=
\max\left(
Z_y(x')-
\max_{j\neq y}Z_j(x')
+\kappa,
0
\right)
$$

当损失为零时：

$$
\max_{j\neq y}Z_j(x')
\geq Z_y(x')+\kappa
$$

即竞争类别至少领先原类别 $\kappa$。

### 6.4 目标攻击损失

$$
f_{\mathrm{targeted}}(x',t)
=
\max\left(
\max_{j\neq t}Z_j(x')
-Z_t(x')
+\kappa,
0
\right)
$$

当损失为零时：

$$
Z_t(x')
\geq
\max_{j\neq t}Z_j(x')+\kappa
$$

### 6.5 $\kappa$ 的作用

- $\kappa=0$：刚刚追平或反超即可；
- $\kappa>0$：攻击类别必须领先指定 logit margin；
- $\kappa$ 增大通常带来更强误分类，但需要更大扰动。

$\kappa$ 是 logit 差值，不是概率百分比。

### 6.6 为什么 margin loss 更适合 EAD

Margin loss 达到攻击要求后会被截断为零：

$$
\max(\text{margin},0)
$$

这会停止不必要的额外攻击压力，让 $L_2$ 与 $L_1$ 尝试进一步减小扰动。交叉熵通常不会在分类刚刚改变时自动归零。

### 6.7 One-hot 与最强竞争类别

```python
def compute_adversarial_loss(
    logits,
    selected_onehot,
    confidence=0.0,
    targeted=False,
):
    selected = torch.sum(
        selected_onehot * logits,
        dim=1,
    )

    other = logits.masked_fill(
        selected_onehot.bool(),
        float("-inf"),
    ).max(dim=1).values

    if targeted:
        margin = other - selected + confidence
    else:
        margin = selected - other + confidence

    return torch.clamp(margin, min=0.0)
```

接口含义必须明确：

```text
非目标攻击：selected_onehot 表示原始类别
目标攻击：selected_onehot 表示攻击目标类别
```

最终成功判断不应只看损失是否为零，还要检查 `argmax`；在 $\kappa=0$ 的平局点，损失可能为零但预测仍返回原类别。

---

## 7. 近端算子与投影

### 7.1 从投影开始

集合 $C$ 上的投影是：

$$
\Pi_C(z)
=
\arg\min_{u\in C}
\frac12\|u-z\|_2^2
$$

它在问：合法集合中哪个点离 $z$ 最近？对像素区间 $[0,1]$，投影就是裁剪。

### 7.2 近端算子

对函数 $h$，近端算子定义为：

$$
\operatorname{prox}_{\lambda h}(z)
=
\arg\min_u
\left\{
\frac12\|u-z\|_2^2
+\lambda h(u)
\right\}
$$

第一项要求 $u$ 不要离 $z$ 太远；第二项要求 $u$ 具有 $h$ 偏好的性质。

若 $h$ 是集合的指示函数，近端算子就退化为普通投影。因此可以把近端算子理解为广义投影。

---

## 8. 软阈值与硬阈值

### 8.1 硬阈值

$$
H_\lambda(z)=
\begin{cases}
0,&|z|\leq\lambda\cr
z,&|z|>\lambda
\end{cases}
$$

行为：小值删除，大值原样保留。它在阈值边界不连续。

### 8.2 软阈值

$$
S_\lambda(z)
=
\operatorname{sign}(z)
\max(|z|-\lambda,0)
$$

分段形式：

$$
S_\lambda(z)=
\begin{cases}
z-\lambda,&z>\lambda\cr
0,&|z|\leq\lambda\cr
z+\lambda,&z<-\lambda
\end{cases}
$$

行为：小值删除，大值也向零收缩。

假设 (lambda=0.1)：

| 输入 | 硬阈值 | 软阈值 |
|---:|---:|---:|
| (0.08) | (0) | (0) |
| (0.12) | (0.12) | (0.02) |
| (-0.25) | (-0.25) | (-0.15) |

### 8.3 软阈值为什么出现

软阈值不是人为猜测，而是以下 $L_1$ 近端问题的精确解：

$$
\min_u
\left[
\frac12(u-z)^2+\lambda|u|
\right]
$$

其中平方项把 $u$ 拉向候选值 $z$，$L_1$ 项把 $u$ 拉向零。平衡后的解就是 $S_\lambda(z)$。

### 8.4 为什么会得到精确的零

当：

$$
|z|\leq\lambda
$$

$L_1$ 的拉零作用足以超过“靠近 $z$”的收益，最优解直接落在零点。这是真稀疏，而不是许多接近零的小数。

### 8.5 在 EAD 中作用于哪里

EAD 稀疏的是扰动：

$$
\delta=x'-x
$$

所以正确更新是：

$$
x'_{\mathrm{next}}
=
\operatorname{clip}_{[0,1]}
\left[
x+S_{\eta\beta}(z-x)
\right]
$$

而不是直接计算 (S(z))。直接对图片做阈值会把像素推向黑色，不代表恢复原图。

### 8.6 PyTorch 实现

```python
def soft_threshold(perturbation, threshold):
    return torch.sign(perturbation) * torch.clamp(
        torch.abs(perturbation) - threshold,
        min=0.0,
    )


def apply_shrinkage_thresholding(
    candidate_images,
    original_images,
    threshold,
    clip_min=0.0,
    clip_max=1.0,
):
    candidate_delta = candidate_images - original_images
    sparse_delta = soft_threshold(
        candidate_delta,
        threshold,
    )

    return torch.clamp(
        original_images + sparse_delta,
        min=clip_min,
        max=clip_max,
    )
```

完整近端梯度中的阈值通常是：

$$
\boxed{\lambda=\eta\beta}
$$

不是简单地只用 (eta)。

---

## 9. ISTA 与 FISTA

### 9.1 近端梯度下降（ISTA）

对于：

$$
\min_u g(u)+h(u)
$$

其中 (g) 可求梯度，(h) 的近端算子易计算，ISTA 更新为：

$$
u^{(k+1)}
=
\operatorname{prox}_{\eta h}
\left(
u^{(k)}-\eta\nabla g(u^{(k)})
\right)
$$

对于 EAD：

```text
先对攻击损失与 L2² 做梯度更新
再对候选扰动做 L1 软阈值
```

### 9.2 FISTA 的两个位置

FISTA 同时维护：

- (x'^{(k)})：软阈值后的实际解；
- (y^{(k)})：利用历史方向得到的外推点。

梯度在外推点 (y^{(k)}) 计算：

$$
x'^{(k+1)}
=
\operatorname{prox}_{\eta h}
\left(
y^{(k)}-\eta\nabla g(y^{(k)})
\right)
$$

### 9.3 标准 FISTA 动量

$$
t_{k+1}
=
\frac{1+\sqrt{1+4t_k^2}}{2},
\qquad t_0=1
$$

$$
y^{(k+1)}
=
x'^{(k+1)}
+\frac{t_k-1}{t_{k+1}}
\left(x'^{(k+1)}-x'^{(k)}\right)
$$

课程实现使用简化系数：

$$
\gamma_k=\frac{k}{k+3}
$$

$$
y^{(k+1)}
=
x'^{(k+1)}
+\gamma_k
\left(x'^{(k+1)}-x'^{(k)}\right)
$$

建议把函数命名为 `compute_momentum_coefficient`，避免把 (gamma_k) 与标准 FISTA 的辅助量 (t_k) 混淆。

### 9.4 动量直觉

假设：

$$
x'^{(k)}=0.40,qquad x'^{(k+1)}=0.50
$$

最近移动量为 (0.10)。若 (gamma_k=0.7)：

$$
y^{(k+1)}=0.50+0.7(0.10)=0.57
$$

下一轮在 (0.57) 处计算梯度，相当于沿近期有效方向向前观察。

### 9.5 收敛保证的边界

标准凸复合优化中，ISTA 常见速率为 (O(1/k))，FISTA 可达到 (O(1/k^2))。但深度神经网络攻击目标通常非凸，ReLU 与 margin 也只几乎处处可导。因此：

```text
FISTA 在 EAD 中是有效的经验性加速方法；
不能直接保证找到全局最优对抗样本；
经典 O(1/k²) 结论不能原封不动套用。
```

---

## 10. 输入梯度与网络反向传播

### 10.1 平滑目标的梯度

$$
g(x')
=
c f_{\mathrm{adv}}(x')
+\|x'-x\|_2^2
$$

$$
\nabla g(x')
=
c\nabla f_{\mathrm{adv}}(x')
+2(x'-x)
$$

对抗梯度推动输入跨越决策边界；$L_2^2$ 梯度将输入拉回原图。

### 10.2 单像素上的力量平衡

设某像素扰动为：

$$
\delta_i=0.15
$$

$L_2^2$ 梯度为：

$$
2\delta_i=0.30
$$

若对抗梯度为 (-2.5)：

- (c=0.1)：总梯度 (0.30-0.25=0.05)，略向原图移动；
- (c=1)：总梯度 (0.30-2.5=-2.20)，强烈向攻击方向移动。

这说明 (c) 会改变局部更新方向，而不仅仅改变打印出来的损失数值。

### 10.3 梯度经过网络

链式法则：

$$
\frac{\partial f}{\partial x'}
=
\frac{\partial f}{\partial Z}
\frac{\partial Z}{\partial h_n}
\cdots
\frac{\partial h_1}{\partial x'}
$$

- ReLU 激活时传递梯度，未激活时阻断梯度；
- 卷积把输出梯度分配到对应感受野；
- 最大池化通常只把梯度传给窗口中取得最大值的位置；
- 当前输入跨过激活边界时，梯度模式可能突然变化。

### 10.4 PyTorch 中只求输入梯度

```python
model.eval()

for parameter in model.parameters():
    parameter.requires_grad_(False)

y_momentum = (
    y_momentum
    .detach()
    .requires_grad_(True)
)

gradient = torch.autograd.grad(
    smooth_loss_per_example.sum(),
    y_momentum,
)[0]
```

`detach()` 保留数值但切断上一轮计算图；`requires_grad_(True)` 从当前值开始建立新一轮计算图，避免跨迭代图不断增长。

### 10.5 攻击成功后的动态

Margin loss 达到条件后通常变为零，对抗梯度暂时消失，$L_2$ 与软阈值开始缩小扰动。如果缩小过多导致攻击再次失败，对抗损失会重新变正，攻击梯度也会再次出现。

所以优化轨迹可能是：

```text
推动攻击成功
→ 缩小扰动
→ 若退回过多则重新施加攻击压力
→ 在决策边界附近寻找平衡
```

---

## 11. 完整 FISTA 单轮

### 11.1 数学步骤

第一步，在外推点计算平滑梯度：

$$
\nabla g(y^{(k)})
$$

第二步，梯度更新：

$$
z^{(k)}
=
y^{(k)}-\eta\nabla g(y^{(k)})
$$

第三步，对候选扰动做软阈值：

$$
x'^{(k+1)}
=
\operatorname{clip}_{[0,1]}
\left[
x+S_{\eta\beta}(z^{(k)}-x)
\right]
$$

第四步，更新动量点：

$$
y^{(k+1)}
=
x'^{(k+1)}
+\gamma_k
\left(x'^{(k+1)}-x'^{(k)}\right)
$$

### 11.2 代码骨架

```python
def fista_step(
    adv_images,
    y_momentum,
    original_images,
    selected_onehot,
    const,
    model,
    beta,
    learning_rate,
    confidence,
    iteration,
    targeted=False,
    clip_min=0.0,
    clip_max=1.0,
):
    y_momentum = (
        y_momentum
        .detach()
        .requires_grad_(True)
    )

    total_loss, adversarial_loss, distances = (
        compute_total_loss(
            y_momentum,
            original_images,
            selected_onehot,
            const,
            model,
            beta,
            confidence,
            targeted,
        )
    )

    gradient = torch.autograd.grad(
        total_loss.sum(),
        y_momentum,
    )[0]

    candidate_images = (
        y_momentum - learning_rate * gradient
    )

    adv_new = apply_shrinkage_thresholding(
        candidate_images,
        original_images,
        learning_rate * beta,
        clip_min,
        clip_max,
    )

    momentum = iteration / (iteration + 3.0)

    y_new = (
        adv_new
        + momentum * (adv_new - adv_images)
    )

    return adv_new.detach(), y_new.detach()
```

`adv_images` 与 `y_momentum` 必须分开：前者是实际近端解，后者是下一轮的梯度观察点。

---

## 12. 距离计算与 Batch 维度

```python
def compute_distances(
    adv_images,
    original_images,
    beta,
    tolerance=1e-6,
):
    delta = adv_images - original_images
    reduce_dims = tuple(range(1, delta.ndim))

    l0 = torch.sum(
        torch.abs(delta) > tolerance,
        dim=reduce_dims,
    )

    l1 = torch.sum(
        torch.abs(delta),
        dim=reduce_dims,
    )

    l2_squared = torch.sum(
        delta ** 2,
        dim=reduce_dims,
    )

    l2 = torch.sqrt(l2_squared.clamp_min(0))
    elastic = l2_squared + beta * l1

    return {
        "l0": l0,
        "l1": l1,
        "l2": l2,
        "l2_squared": l2_squared,
        "elastic": elastic,
    }
```

对于形状 ((B,C,H,W))，应只在 (C,H,W) 上求和，保留 batch 维，使每个样本拥有独立距离和独立 (c)。

RGB 图像还要明确 $L_0$ 统计口径：

- 按通道坐标统计；
- 或按空间像素统计，只要任意通道变化就算一个像素。

---

## 13. 总损失实现

FISTA 显式求梯度的平滑部分是：

$$
\mathcal L_{\mathrm{smooth}}
=
c f_{\mathrm{adv}}+L_2^2
$$

$L_1$ 由近端软阈值处理，不应在标准拆分中既加入普通梯度又再次软阈值。

```python
def compute_total_loss(
    adv_images,
    original_images,
    selected_onehot,
    const,
    model,
    beta,
    confidence,
    targeted=False,
):
    logits = model(adv_images)

    adversarial_loss = compute_adversarial_loss(
        logits,
        selected_onehot,
        confidence,
        targeted,
    )

    metrics = compute_distances(
        adv_images,
        original_images,
        beta,
    )

    smooth_loss = (
        const * adversarial_loss
        + metrics["l2_squared"]
    )

    return smooth_loss, adversarial_loss, metrics
```

若 `smooth_loss` 形状为 ((B,))，求输入梯度前通常使用 `.sum()`。使用 `.mean()` 会把梯度缩小 (B) 倍，从而改变有效学习率。

---

## 14. 攻击成功判断

```python
def check_attack_success(
    adv_images,
    labels,
    model,
    targeted=False,
):
    with torch.no_grad():
        logits = model(adv_images)
        predictions = logits.argmax(dim=1)

    if targeted:
        return predictions.eq(labels)

    return predictions.ne(labels)
```

标签含义：

```text
非目标攻击：labels 是原始标签
目标攻击：labels 是目标标签
```

如果实验要求达到 $\kappa$ margin，还需额外检查 logits 差值，不能只检查 `argmax`。

---

## 15. 外层二分搜索 (c)

### 15.1 为什么需要搜索 (c)

$c$ 太小，$L_2$ 拉回力占主导，攻击可能失败；$c$ 太大，攻击容易成功但可能产生过大扰动。

不同样本离决策边界的距离不同，因此每个样本应拥有自己的：

$$
c_i
$$

### 15.2 更新规则

每个样本维护：

$$
c_{\mathrm{lower}},\quad
c_{\mathrm{upper}},\quad
c
$$

攻击成功：当前 (c) 足够，尝试更小值。

$$
c_{\mathrm{upper}}
\leftarrow
\min(c_{\mathrm{upper}},c)
$$

攻击失败：当前 (c) 可能不足，提高下界。

$$
c_{\mathrm{lower}}
\leftarrow
\max(c_{\mathrm{lower}},c)
$$

上下界有限时取中点：

$$
c\leftarrow
\frac{c_{\mathrm{lower}}+c_{\mathrm{upper}}}{2}
$$

若尚未找到成功上界，可先指数扩张：

$$
c\leftarrow10c
$$

### 15.3 嵌套循环

```python
for binary_step in range(binary_search_steps):
    adv_images = original_images.clone()
    y_momentum = original_images.clone()

    for iteration in range(max_iterations):
        adv_images, y_momentum = fista_step(...)

        # 检查成功样本，并保存当前最优距离候选

    success = check_attack_success(...)
    lower, upper, const = update_bounds(...)
```

通常每个二分搜索步骤从原图重新开始，避免上一轮较大 (c) 的扰动污染下一轮比较。Warm start 是可选变体，但会改变优化行为。

### 15.4 二分搜索的理论边界

二分搜索隐含“更大的 (c) 更容易成功”的近似单调关系。但神经网络目标非凸，FISTA 又只有有限迭代，实践中不保证严格单调或找到全局最小 (c)。

更准确的结论是：

```text
在当前初始化、学习率与迭代预算下，
搜索一个较小且通常足以完成攻击的 c。
```

---

## 16. 为什么要保存历史最佳样本

最后一轮不一定最好：

- 动量可能振荡；
- 最后一轮可能重新攻击失败；
- 较早轮次可能成功且距离更小；
- 不同 (c) 会产生不同质量的成功样本。

因此每轮应检查：

```text
当前是否成功？
当前 Elastic-Net 距离是否小于历史最佳？
```

满足时保存：

```python
best_adv_images[i] = current_adv_images[i]
best_elastic[i] = current_elastic[i]
```

---

## 17. 环境与模型准备

### 17.1 为什么 EAD 计算昂贵

FGSM 常只需一次前向与反向传播。EAD 的计算结构是：

```text
5～10 次外层 c 搜索
    ×
数百次内层 FISTA 更新
    ×
每轮一次前向与反向传播
```

因此 GPU 会显著缩短实验时间。

### 17.2 可复现性与设备

```python
set_reproducibility(1337)

device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)
```

固定随机种子可以减少随机差异，但跨 GPU、CUDA 与 PyTorch 版本时不必然逐比特相同。

### 17.3 模型模式

```python
model.eval()
```

攻击时关闭 Dropout 的随机行为。`model.eval()` 不会禁止输入梯度。

```python
for parameter in model.parameters():
    parameter.requires_grad_(False)
```

可以减少无用的模型参数梯度计算。

### 17.4 只攻击原本分类正确的样本

合理的攻击成功率分母应是模型原本正确分类、并实际参与攻击的样本：

$$
\text{ASR}
=
\frac{\text{攻击成功的原始正确样本数}}
{\text{参与攻击的原始正确样本数}}
$$

原本就分类错误的图片不能被算作攻击成功。

---

## 18. 评估指标

最低限度应记录：

```text
干净准确率
原始正确样本数量
攻击成功率 ASR
目标攻击成功率（如适用）
L0：修改坐标或空间像素数量
L1：总绝对变化
L2：真正欧氏距离
L2²：内部优化使用的平方距离
Elastic-Net 代价 L2² + beta * L1
FISTA 迭代次数
二分搜索步数
运行时间与设备
随机种子、模型版本、代码和依赖版本
```

建议同时报告均值、中位数与分位数，避免少量极端样本掩盖总体行为。

---

## 19. 常见误区与实现审计清单

### 19.1 概念误区

```text
[ ] 没有把 L1 当作修改数量；修改数量是 L0
[ ] 没有把平方 L2 当作真正的 L2
[ ] 没有声称 EAD 严格保证 L0 ≤ k
[ ] 没有把 FISTA 当作攻击目标；FISTA 是 EAD 的优化器
[ ] 没有把 Elastic Net 的 Net 误解为 neural network
[ ] 没有把 κ 误解为概率置信度
```

### 19.2 损失与标签

```text
[ ] Margin loss 使用原始 logits，不是 Softmax 概率
[ ] 非目标攻击传入原标签
[ ] 目标攻击传入目标标签
[ ] 非目标公式为 real - other + κ
[ ] 目标公式为 other - target + κ
[ ] 最终成功检查显式使用 argmax，并按需验证 κ margin
```

### 19.3 FISTA 与软阈值

```text
[ ] 梯度在 y_momentum 上计算，而不是误用当前实际解
[ ] 每轮 detach 旧计算图并重新启用输入梯度
[ ] L1 不在普通梯度和软阈值中重复计算
[ ] 软阈值作用于 candidate - original
[ ] 阈值按实现约定使用 learning_rate * beta
[ ] 软阈值后加回原图
[ ] 输出裁剪到合法像素范围
[ ] adv_images 与 y_momentum 分开维护
```

### 19.4 Batch 与记录

```text
[ ] 距离只压缩特征维，保留 batch 维
[ ] 每个样本维护独立 c 和上下界
[ ] 只在原始正确样本上统计攻击成功率
[ ] 保存历史最优成功样本，而不是盲目返回最后一轮
[ ] RGB 图像明确 L0 是按通道还是按空间像素统计
[ ] 浮点 L0 使用 tolerance，而不是直接比较 != 0
```

### 19.5 数值与停止条件

```text
[ ] 监控梯度均值与最大值，但不套用固定通用阈值
[ ] 监控损失、成功状态和最佳距离是否改善
[ ] 不在刚成功时立即停止，允许继续缩小扰动
[ ] 长期无改善时可提前停止
[ ] 动量振荡时考虑重启或降低学习率
[ ] 明确非凸问题不保证全局最优
```

---

## 20. 参数作用速查

| 参数 | 位置 | 增大后的典型影响 |
|---|---|---|
| (c) | (c f_{\mathrm{adv}}) | 攻击压力增强，成功更容易，扰动可能增大 |
| (eta) | (eta L_1) | 稀疏压力增强，更多候选扰动可能清零 |
| (eta) | 梯度步长 | 更新更快，但过大可能振荡或越界 |
| (eta\beta) | 软阈值 | 直接控制每轮清零强度 |
| $\kappa$ | Margin 内部 | 要求更强的 logit 领先，通常增加攻击难度 |
| FISTA 迭代数 | 内层优化预算 | 更多时间用于寻找较好局部解 |
| 二分步数 | 外层搜索预算 | 更精细地搜索 (c) |

参数不能孤立理解。例如实际阈值是 (eta\beta)，所以只比较不同实验的 (eta) 而忽略学习率可能得出错误结论。

---

## 21. 与其他攻击的对比

| 攻击 | 主要问题 | 约束或目标 | 典型优化方式 |
|---|---|---|---|
| FGSM | 给定预算如何一步制造错误 | (L_\infty) | 一次梯度符号更新 |
| PGD | 在预算内反复寻找更强攻击 | 常见 (L_\infty/L_2) | 投影梯度迭代 |
| DeepFool | 到最近决策边界需要多大扰动 | 常见 $L_2$ | 局部线性化与投影 |
| EAD | 如何兼顾稀疏与平滑 | $L_2^2+\beta L_1$ | FISTA + 软阈值 + $c$ 搜索 |
| JSMA | 如何显式控制少量特征修改 | $L_0$ 预算 | Jacobian saliency 逐特征选择 |

EAD 促进稀疏但不严格规定最多修改 $k$ 个坐标。需要显式 $L_0$ 预算时，应考虑 JSMA、Top-$k$ 或其他直接特征选择方法。

---

## 22. 防御与安全评估视角

稀疏攻击揭示模型可能过度依赖少数高影响特征。防御不能只检测全局噪声大小，因为稀疏扰动可能具有较低的整体噪声统计，却集中改变决策关键位置。

授权评估应关注：

```text
模型是否被少量特征改变稳定翻转？
攻击是否跨随机种子、样本、模型版本重复出现？
仅看 L2 的检测是否漏掉低 L0、高影响扰动？
防御是否显著增加正常样本误报？
对抗训练是否覆盖 L0、L1、L2、L∞ 的不同失效模式？
运行时是否监控边界样本、异常特征集中度和重复查询模式？
```

高干净准确率不等于高对抗鲁棒性。必须单独建立对抗回归集和版本化评估报告。

---

## 23. 复习卡片

### 23.1 核心定义

```text
Q：什么是稀疏攻击？
A：通过修改尽可能少的输入坐标完成误分类，核心预算常用 L0。

Q：EAD 是否严格限制 L0？
A：否。EAD 用 L1 促进稀疏，但不保证 L0 ≤ k。

Q：FISTA 是攻击吗？
A：不是独立攻击目标；它是求解 EAD 复合目标的优化算法。

Q：为什么叫 Elastic Net？
A：因为目标结合 L1 与 L2² 正则，继承统计学习中的 Elastic Net 名称。
```

### 23.2 损失与参数

```text
Q：c 控制什么？
A：攻击损失相对扰动距离的权重。

Q：beta 控制什么？
A：L1 稀疏压力；实际每轮阈值通常为 eta * beta。

Q：kappa 控制什么？
A：攻击类别必须达到的 logit margin。

Q：为什么 EAD 常用 C&W margin 而不是交叉熵？
A：达到指定攻击 margin 后损失归零，便于继续压缩扰动。
```

### 23.3 软阈值与 FISTA

```text
Q：硬阈值和软阈值的区别？
A：硬阈值删除小值但保留大值；软阈值还会把大值向零收缩。

Q：软阈值作用在哪里？
A：作用于候选扰动 z - x，而不是直接作用于图片。

Q：为什么软阈值产生精确零？
A：它是 L1 近端问题的精确解，|z| ≤ 阈值时最优解就是零。

Q：为什么维护 x 和 y 两个变量？
A：x 是实际近端解，y 是 FISTA 外推后用于下一轮求梯度的点。
```

### 23.4 一条最终记忆链

```text
输入 x
→ 模型输出 logits
→ Margin loss 衡量离攻击成功多远
→ 对 smooth loss = c * adversarial + L2² 求输入梯度
→ 在 FISTA 动量点做梯度更新
→ 对候选扰动执行阈值 eta * beta 的软阈值
→ 加回原图并裁剪
→ 保存更好的成功样本
→ 外层根据成功/失败调整 c
```

---

## 24. 代码与后续阅读

- [EAD/FISTA 通用考试模板](../_工具/ead_exam_template.py)
- [稀疏攻击考试可复用代码库（EAD 与 JSMA）](../_工具/EAD考试可复用代码库.md)
- [JSMA 显式 L0 稀疏规避攻击](JSMA显式L0稀疏规避攻击从零学习笔记.md)
- [JSMA 通用考试模板](../_工具/jsma_exam_template.py)
