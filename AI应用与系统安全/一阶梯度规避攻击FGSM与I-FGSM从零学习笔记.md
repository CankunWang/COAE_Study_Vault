---
id: coae-appsec-first-order-fgsm-2f84c9d1
title: '一阶梯度规避攻击 FGSM 与 I-FGSM 从零学习笔记'
aliases:
  - First-Order Evasion Attacks
  - FGSM
  - I-FGSM
  - BIM
  - Basic Iterative Method
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
# 一阶梯度规避攻击 FGSM 与 I-FGSM 从零学习笔记

> 适用范围：对抗机器学习基础学习、本地模型鲁棒性评估、课程靶场与明确授权的测试环境。本笔记讨论推理阶段输入扰动，不修改训练数据、标签或模型参数。
>
> 前置笔记：[[Evasion Attacks与GoodWords攻击安全测试清单与学习笔记]]。相邻笔记：[[DeepFool最小扰动规避攻击从零学习笔记]]、[[稀疏规避攻击与EAD从零学习笔记]]。

---

## 0. 一页总览

### 0.1 一阶规避攻击是什么

一阶规避攻击使用 loss 对输入的梯度来构造对抗样本。训练时，梯度用于更新模型参数；攻击时，模型参数固定，梯度用于更新输入。

```text
训练：
固定输入 x 与标签 y
计算 loss 对参数 theta 的梯度
沿负梯度更新 theta，让 loss 下降

攻击：
固定模型参数 theta
计算 loss 对输入 x 的梯度
沿攻击方向修改 x，让 loss 上升或靠近目标类别
```

核心差异：

| 阶段 | 固定对象 | 优化对象 | 梯度 | 目标 |
|---|---|---|---|---|
| 训练 | 输入与标签 | 模型参数 $\theta$ | $\nabla_\theta L$ | 降低 loss |
| 非定向 FGSM | 模型参数 | 输入 $x$ | $\nabla_x L(\theta,x,y)$ | 增加真实类 loss |
| 定向 FGSM | 模型参数 | 输入 $x$ | $\nabla_x L(\theta,x,y_t)$ | 降低目标类 loss |

### 0.2 本笔记覆盖范围

```text
输入 shape、batch size 与 logits
cross_entropy 的含义与 PyTorch 用法
扰动范数 L0 / L1 / L2 / L∞
normalization 对 epsilon 与 clamp 的影响
FGSM 的公式、直觉、实现与评估
Targeted FGSM 的方向变化
I-FGSM / BIM 的迭代、projection 与 PGD 关系
常见实现错误与复习卡片
```

### 0.3 一句话记忆

> FGSM 用一次输入梯度在 $L_\infty$ 预算内把样本推向更高 loss；I-FGSM 把这一步拆成多次小步，每步重新计算梯度并投影回原图周围的同一预算范围。

---

## 1. 输入、batch size 与 logits

### 1.1 batch size 是什么

`batch size` 是一次送进模型处理的样本数量，不是图片本身的属性。

MNIST 单张灰度图片是：

```text
[1, 28, 28]
```

如果 `DataLoader` 设置：

```python
DataLoader(test_dataset, batch_size=128, shuffle=False)
```

那么一个 batch 的输入通常是：

```text
images.shape = [128, 1, 28, 28]
```

含义：

| 维度 | 含义 |
|---|---|
| 128 | 一次处理 128 张图片 |
| 1 | 灰度通道 |
| 28 | 高度 |
| 28 | 宽度 |

### 1.2 logits 是什么

`logits` 是模型最后一层输出的原始类别分数，不是概率。MNIST 有 10 类，因此：

```text
logits.shape = [128, 10]
```

表示：

```text
128 张图片
每张图片 10 个类别分数
```

模型预测通常直接取最大 logit 的类别：

```python
pred = logits.argmax(dim=1)
```

因为 softmax 不改变类别分数的大小顺序。

### 1.3 logits 如何算出来

神经网络前向传播：

```python
logits = model(images)
```

CNN 中可以理解为：

```text
输入图片
    ↓
卷积层提取边缘、笔画、局部形状
    ↓
激活函数与池化
    ↓
展平或全局特征汇聚
    ↓
全连接层
    ↓
输出每个类别的原始分数 logits
```

最后一层常可写成：

$$
z = Wh+b
$$

其中 $h$ 是前面网络抽取出的特征，$W$ 和 $b$ 是最后分类层参数，$z$ 就是 logits。

---

## 2. cross_entropy 重新理解

### 2.1 softmax 与真实类概率

logits 不是概率。softmax 将 logits 转成概率：

$$
p_i=\frac{e^{z_i}}{\sum_j e^{z_j}}
$$

对于真实类别 $y$，cross entropy 关注模型给真实类别的概率 $p_y$：

$$
L=-\log p_y
$$

因此：

```text
真实类别概率越高，loss 越小
真实类别概率越低，loss 越大
```

示例：

| $p_y$ | $-\log(p_y)$ | 解释 |
|---|---:|---|
| 0.99 | 0.01 | 模型很相信正确类 |
| 0.50 | 0.69 | 模型不确定 |
| 0.10 | 2.30 | 模型不相信正确类 |
| 0.01 | 4.61 | 模型强烈偏离正确类 |

### 2.2 PyTorch 用法

正确写法：

```python
logits = model(images)
loss = F.cross_entropy(logits, labels)
```

不要先手动 softmax：

```python
probs = F.softmax(logits, dim=1)
loss = F.cross_entropy(probs, labels)  # 不推荐
```

因为 `F.cross_entropy` 内部已经包含：

```text
log_softmax + negative log likelihood
```

### 2.3 batch 上如何计算

若：

```text
logits.shape = [4, 10]
labels = [7, 2, 1, 9]
```

cross entropy 会分别取每张图片真实类别的概率：

```text
第 1 张：-log(p_7)
第 2 张：-log(p_2)
第 3 张：-log(p_1)
第 4 张：-log(p_9)
```

PyTorch 默认返回平均 loss：

```text
loss.shape = []
```

也就是一个标量。

### 2.4 与攻击的关系

训练时最小化：

$$
L(\theta,x,y)
$$

让模型更相信真实类别。

非定向 FGSM 最大化：

$$
L(\theta,x,y)
$$

让模型不再相信真实类别。

定向 FGSM 最小化：

$$
L(\theta,x,y_t)
$$

让模型更相信指定目标类别 $y_t$。

---

## 3. 范数与扰动预算

### 3.1 扰动定义

原始输入为 $x$，对抗输入为 $x_{\mathrm{adv}}$：

$$
\delta=x_{\mathrm{adv}}-x
$$

攻击评估必须同时回答：

```text
模型是否被误导？
扰动到底有多大？
扰动是否仍在人类可接受或实验定义的预算内？
```

### 3.2 常见范数

| 范数 | 问题 | 直觉 |
|---|---|---|
| $L_0$ | 改了多少个坐标 | 只数被动过的位置 |
| $L_1$ | 总共改了多少 | 所有绝对变化求和 |
| $L_2$ | 整体距离多远 | 欧氏距离，偏平滑 |
| $L_\infty$ | 单个坐标最多改多少 | 每个像素的最大变化上限 |

公式：

$$
\|\delta\|_1=\sum_i|\delta_i|
$$

$$
\|\delta\|_2=\sqrt{\sum_i\delta_i^2}
$$

$$
\|\delta\|_\infty=\max_i|\delta_i|
$$

$L_0$ 常写作：

$$
\|\delta\|_0=\#\{i:\delta_i\neq0\}
$$

严格数学上 $L_0$ 不是 proper norm，但在对抗机器学习中常用来描述稀疏性。

### 3.3 与攻击形态的关系

```text
L0：少数像素或特征被改，可能很显眼
L1：预算集中在一部分坐标，常出现稀疏噪点
L2：整体平滑变化，像轻微雾化
L∞：很多像素都可小幅变化，但每个像素不超过 epsilon
```

FGSM 与 I-FGSM 默认属于 $L_\infty$ 威胁模型：

```text
每个像素最多只能变化 epsilon
```

---

## 4. normalization 与 epsilon 空间

### 4.1 归一化公式

MNIST 常用：

```text
mean = 0.1307
std  = 0.3081
```

归一化：

$$
x_{\mathrm{norm}}=\frac{x-\mu}{\sigma}
$$

反归一化：

$$
x=x_{\mathrm{norm}}\sigma+\mu
$$

MNIST 原始像素范围 $[0,1]$ 归一化后约为：

$$
\frac{0-0.1307}{0.3081}\approx -0.424
$$

$$
\frac{1-0.1307}{0.3081}\approx 2.821
$$

### 4.2 为什么 FGSM 里必须分清空间

如果模型吃的是 normalized input，那么：

```text
x 是 normalized x
gradient 是 normalized-space gradient
epsilon 也是 normalized-space epsilon
clamp 也应使用 normalized 合法范围
```

换算关系：

$$
\epsilon_{\mathrm{pixel}}=\sigma\epsilon_{\mathrm{norm}}
$$

$$
\epsilon_{\mathrm{norm}}=\frac{\epsilon_{\mathrm{pixel}}}{\sigma}
$$

例如 MNIST：

```text
epsilon_norm = 0.8
epsilon_pixel = 0.3081 * 0.8 ≈ 0.25
```

也就是在 $[0,1]$ 像素空间中每个像素最多改变约 25%。

### 4.3 clamp 的正确范围

normalized MNIST 的合法范围不是 $[0,1]$，而是：

```text
MNIST_NORM_MIN ≈ -0.424
MNIST_NORM_MAX ≈ 2.821
```

若攻击在 normalized space 中执行，应使用：

```python
x_adv = torch.clamp(x_adv, MNIST_NORM_MIN, MNIST_NORM_MAX)
```

只有在 pixel space 中执行并返回 $[0,1]$ 图片时，才 clamp 到：

```python
x_adv = torch.clamp(x_adv, 0.0, 1.0)
```

---

## 5. 输入梯度：训练与攻击的分界

### 5.1 训练时为什么求 $\nabla_\theta L$

训练目标是让模型参数更好：

$$
\theta_{\mathrm{new}}=\theta_{\mathrm{old}}-\eta\nabla_\theta L
$$

梯度方向是 loss 上升最快方向，因此训练沿负梯度更新参数，让 loss 下降。

PyTorch 训练主线：

```python
optimizer.zero_grad()
logits = model(images)
loss = F.cross_entropy(logits, labels)
loss.backward()
optimizer.step()
```

### 5.2 FGSM 为什么求 $\nabla_x L$

攻击时模型已经训练好，参数固定。攻击者要修改输入：

```text
如果我稍微改变某个像素，loss 会怎么变？
```

答案就是：

$$
\nabla_x L(\theta,x,y)
$$

实现口径：

```python
x_req = x.clone().detach().requires_grad_(True)
_, loss = _forward_and_loss(model, x_req, y)
model.zero_grad(set_to_none=True)
loss.backward()
grad = x_req.grad.detach()
```

逐行理解：

| 代码 | 作用 |
|---|---|
| `clone()` | 复制输入，避免污染原 batch |
| `detach()` | 切断旧计算图 |
| `requires_grad_(True)` | 让 PyTorch 跟踪输入梯度 |
| `loss.backward()` | 反向传播，计算所有需要梯度的变量 |
| `x_req.grad` | loss 对输入的梯度 |

`model.eval()` 不会关闭梯度；它只改变 Dropout、BatchNorm 等层的运行行为。是否记录梯度由 `requires_grad` 和 `torch.no_grad()` 控制。

---

## 6. FGSM

### 6.1 非定向 FGSM

非定向攻击目标：

```text
让模型不再预测真实类别 y
```

公式：

$$
x_{\mathrm{adv}}=x+\epsilon\operatorname{sign}(\nabla_x L(\theta,x,y))
$$

含义：

| 符号 | 含义 |
|---|---|
| $x$ | 原始输入 |
| $x_{\mathrm{adv}}$ | 对抗输入 |
| $\epsilon$ | $L_\infty$ 扰动预算 |
| $L$ | 分类损失，常用 cross entropy |
| $\theta$ | 固定的模型参数 |
| $y$ | 真实标签 |
| `sign` | 只取每个梯度分量的正负号 |

### 6.2 为什么使用 sign

$L_\infty$ 约束限制每个像素最多改 $\epsilon$。在线性化近似下：

$$
\max_{\|\delta\|_\infty\le\epsilon} g^\top\delta
$$

其中：

$$
g=\nabla_x L(\theta,x,y)
$$

最优扰动是：

$$
\delta^\*=\epsilon\operatorname{sign}(g)
$$

直觉：

```text
梯度为正：该像素调大能增加 loss，因此加 epsilon
梯度为负：该像素调小能增加 loss，因此减 epsilon
```

### 6.3 为什么 FGSM 有效

FGSM 有效主要来自两个原因：

```text
local linearity：神经网络在小邻域内常可近似为线性
high dimensionality：很多像素各自小幅变化，会累积成较大的 logit 变化
```

线性模型示例：

$$
f(x)=w^\top x
$$

若 $\|\delta\|_\infty\le\epsilon$，则：

$$
|f(x+\delta)-f(x)|=|w^\top\delta|\le\epsilon\|w\|_1
$$

即使每个像素变化很小，高维累积后也可能足以跨过决策边界。

### 6.4 核心实现

```python
def fgsm_attack(model, images, labels, epsilon, targeted=False):
    MNIST_NORM_MIN = (0.0 - 0.1307) / 0.3081
    MNIST_NORM_MAX = (1.0 - 0.1307) / 0.3081

    if epsilon < 0:
        raise ValueError("epsilon must be non-negative")
    if not images.is_floating_point():
        raise ValueError("images must be floating point tensors")

    grad = _input_gradient(model, images, labels)
    step_dir = -1.0 if targeted else 1.0
    x_adv = images + step_dir * epsilon * grad.sign()
    x_adv = torch.clamp(x_adv, MNIST_NORM_MIN, MNIST_NORM_MAX)
    return x_adv.detach()
```

核心四步：

```text
计算输入梯度
取 sign
乘 epsilon
加到输入并 clamp 到合法范围
```

---

## 7. Targeted FGSM

### 7.1 目标变化

非定向攻击：

```text
远离真实类别 y
```

定向攻击：

```text
靠近指定目标类别 y_t
```

定向 FGSM 公式：

$$
x_{\mathrm{adv}}=x-\epsilon\operatorname{sign}(\nabla_x L(\theta,x,y_t))
$$

两个变化：

```text
loss 中使用目标标签 y_t
更新方向从加号变减号
```

### 7.2 为什么 targeted 更难

非定向只要求：

```text
预测结果不是原类别即可
```

定向要求：

```text
预测结果必须变成指定类别
```

因此 targeted FGSM 通常需要：

```text
更大的 epsilon
更多迭代
early stopping
更细的步长搜索
```

---

## 8. Pixel-space FGSM 变体

### 8.1 适用场景

若输入图片是原始 $[0,1]$ pixel space，但模型要求 normalized input，需要把攻击预算保留在 pixel space 中解释。例如：

```text
epsilon = 8 / 255
```

表示原始像素最多改变 8 个 8-bit intensity levels。

### 8.2 梯度换算

归一化：

$$
x_{\mathrm{norm}}=\frac{x-\mu}{\sigma}
$$

若梯度是对 $x_{\mathrm{norm}}$ 求得，则根据链式法则：

$$
\nabla_x L=\frac{\nabla_{x_{\mathrm{norm}}}L}{\sigma}
$$

实现要点：

```python
grad_img = x_norm.grad / std_t
x_adv = torch.clamp(x + step_dir * epsilon * grad_img.sign(), 0.0, 1.0)
```

判断规则：

```text
输入已经 normalized：用 normalized FGSM，epsilon 是 normalized units
输入是 [0,1]：用 pixel-space FGSM，epsilon 是 pixel units
```

---

## 9. FGSM 评估指标

### 9.1 必要指标

| 指标 | 作用 |
|---|---|
| `clean_accuracy` | 干净样本准确率 |
| `adversarial_accuracy` | 攻击后准确率 |
| `attack_success_rate` | 原本正确样本中被翻转的比例 |
| `avg_clean_confidence` | 攻击前真实类别平均概率 |
| `avg_adv_confidence` | 攻击后真实类别平均概率 |
| `avg_confidence_drop` | 真实类别概率平均下降 |
| `avg_l2_perturbation` | 每张图平均 $L_2$ 扰动 |
| `max_linf_perturbation` | 全 batch 最大 $L_\infty$ 扰动 |

### 9.2 为什么只统计原本正确样本

攻击成功率应以原本预测正确的样本为分母：

```python
originally_correct = clean_pred == labels
flipped = (adv_pred != labels) & originally_correct
attack_success_rate = flipped.sum() / originally_correct.sum().clamp_min(1)
```

如果模型原本就错了，攻击后仍然错，不能证明攻击有效。

### 9.3 confidence 如何提取

模型给真实类别的概率：

```python
conf_clean = clean_probs.gather(1, true_labels.view(-1, 1)).squeeze(1)
conf_adv = adv_probs.gather(1, true_labels.view(-1, 1)).squeeze(1)
```

`gather(1, ...)` 的含义：

```text
每一行取该样本真实标签对应的那一列概率
```

confidence drop 衡量：

```text
攻击是否削弱了模型对正确类别的信心
```

即使预测尚未翻转，真实类置信度大幅下降也说明样本更靠近边界。

### 9.4 范数如何计算

每张图的 $L_2$：

```python
l2 = (adversarial_images - clean_images) \
    .view(clean_images.size(0), -1) \
    .norm(p=2, dim=1)
```

整个 batch 的最大 $L_\infty$：

```python
linf = (adversarial_images - clean_images).abs().amax()
```

若 FGSM 使用 `epsilon=0.8`，则 `max_linf_perturbation` 应接近：

```text
0.8000
```

超过 epsilon 通常说明 projection、clamp 或空间换算存在错误。

---

## 10. I-FGSM / BIM

### 10.1 核心思想

I-FGSM，也叫 BIM，是 FGSM 的迭代版本：

```text
FGSM：一次算梯度，一步走 epsilon
I-FGSM：多次算梯度，每步走 alpha，每步投影回 epsilon-ball
```

初始化：

$$
x^{(0)}=x
$$

非定向更新：

$$
x^{(t+1)}
=
\Pi_{B_\infty(x,\epsilon)}
\left(
x^{(t)}
+
\alpha\operatorname{sign}
(\nabla_{x^{(t)}}L(\theta,x^{(t)},y))
\right)
$$

常见设置：

$$
\alpha=\frac{\epsilon}{T}
$$

其中 $T$ 是迭代次数。

### 10.2 projection 是什么

projection 的目标是保证：

$$
\|x_{\mathrm{adv}}-x\|_\infty\le\epsilon
$$

代码口径：

```python
delta = torch.clamp(x_adv - images, -epsilon, epsilon)
x_adv = images + delta
x_adv = torch.clamp(x_adv, MNIST_NORM_MIN, MNIST_NORM_MAX)
```

注意中心必须是原始干净输入 `images`，不是上一轮的 `x_adv`。

### 10.3 核心实现

```python
def iterative_fgsm(model, images, labels, epsilon, num_iter,
                   alpha=None, targeted=False, random_start=False):
    MNIST_NORM_MIN = (0.0 - 0.1307) / 0.3081
    MNIST_NORM_MAX = (1.0 - 0.1307) / 0.3081

    if alpha is None:
        alpha = epsilon / max(num_iter, 1)

    if random_start:
        delta = torch.empty_like(images).uniform_(-epsilon, epsilon)
        x_adv = torch.clamp(images + delta, MNIST_NORM_MIN, MNIST_NORM_MAX)
    else:
        x_adv = images.clone()

    for _ in range(num_iter):
        x_adv = x_adv.detach().requires_grad_(True)
        logits = model(x_adv)
        loss = F.cross_entropy(logits, labels)
        model.zero_grad(set_to_none=True)
        loss.backward()

        step_dir = -1.0 if targeted else 1.0
        x_adv = x_adv + step_dir * alpha * x_adv.grad.sign()

        x_adv = torch.clamp(
            images + (x_adv - images).clamp(-epsilon, epsilon),
            MNIST_NORM_MIN,
            MNIST_NORM_MAX,
        )

    return x_adv.detach()
```

每轮循环：

```text
切断旧计算图
重新开启输入梯度
计算当前位置 loss
反向传播得到当前输入梯度
走 alpha * sign(gradient)
投影回原图 epsilon 范围
裁剪到合法输入域
```

### 10.4 为什么每轮要 detach

```python
x_adv = x_adv.detach().requires_grad_(True)
```

作用：

```text
把当前 x_adv 当成新一轮输入变量
避免把所有迭代的计算图串起来
降低显存占用
让每一轮只求当前位置的一阶梯度
```

### 10.5 random start 与 PGD

`random_start=True` 时：

```text
先在原图 epsilon-ball 内随机选一个起点
再执行迭代攻击
```

它可以帮助攻击避开不理想起点，提高成功率。

概念关系：

```text
BIM / I-FGSM：多步 FGSM，传统上常指无随机初始化
PGD：投影梯度攻击的一般形式，常包含 random start 和 multiple restarts
```

在 $L_\infty$ 威胁模型下，带 sign step、projection 和 random start 的 I-FGSM 与常见 PGD 设置非常接近。

---

## 11. FGSM 与 I-FGSM 对比

| 对比项 | FGSM | I-FGSM / BIM |
|---|---|---|
| 梯度次数 | 1 次 | $T$ 次 |
| 步长 | 一步 $\epsilon$ | 每步 $\alpha$ |
| 是否重新计算梯度 | 否 | 是 |
| 是否投影 | 通常只 clamp 合法域 | 每步投影到 $L_\infty$ ball |
| 速度 | 快 | 慢 |
| 攻击强度 | 较弱 | 通常更强 |
| 典型用途 | 快速 baseline | 更可靠的白盒评估 |

为什么 I-FGSM 更强：

```text
FGSM 只使用原始点的一阶线性近似
I-FGSM 每走一步都重新计算当前梯度
因此更能跟踪非线性 loss surface
同样 epsilon 下通常更容易跨过决策边界
```

重要结论：

```text
I-FGSM 的提升不是因为预算更大；
max_linf_perturbation 仍应不超过 epsilon。
```

---

## 12. 超参数解释

### 12.1 epsilon

`epsilon` 是总扰动预算：

```text
L∞ 威胁模型下，每个像素相对原图最多变化 epsilon
```

解释 epsilon 时必须说明坐标空间：

```text
normalized epsilon
pixel-space epsilon
```

### 12.2 alpha

`alpha` 是 I-FGSM 每步大小：

```text
alpha 太大：走得快，但可能 overshoot
alpha 太小：更细致，但需要更多迭代
```

默认：

```text
alpha = epsilon / num_iter
```

### 12.3 num_iter

`num_iter` 是迭代次数：

```text
次数越多，通常攻击越强，但计算更慢
每次迭代都需要一次 backward
```

### 12.4 targeted

```text
targeted=False：增加真实类别 loss
targeted=True：降低目标类别 loss
```

### 12.5 random_start

```text
random_start=False：从原始图片开始
random_start=True：从原图 epsilon-ball 内随机点开始
```

random start 不增加预算，只改变搜索起点。

---

## 13. 安全评估清单

```text
[ ] 只在本地模型、课程靶场或明确授权环境中运行攻击
[ ] 记录模型版本、数据集版本、随机种子和 normalization 参数
[ ] 明确 epsilon、alpha、num_iter 所在坐标空间
[ ] 明确 clamp 范围是 normalized domain 还是 pixel domain
[ ] 攻击成功率只以原本预测正确样本为分母
[ ] 同时报告 clean accuracy、adversarial accuracy、ASR、confidence drop、L2、L∞
[ ] 检查 max_linf_perturbation 是否超过 epsilon
[ ] targeted 攻击必须验证最终预测是否等于目标类别
[ ] 比较 FGSM 与 I-FGSM 时使用同一 batch、同一 epsilon、同一模型状态
[ ] 不把对第三方生产服务的绕检样本、参数或查询策略写入可复用攻击材料
```

---

## 14. 常见错误

### 14.1 把 logits 当概率

logits 是原始分数，可以为负，也不要求加和为 1。需要概率时才使用 softmax。

### 14.2 对 `F.cross_entropy` 先做 softmax

PyTorch 的 `F.cross_entropy` 应直接接收 logits。

### 14.3 忘记给输入开启梯度

FGSM 需要：

```python
x_req.requires_grad_(True)
```

否则拿不到 `x_req.grad`。

### 14.4 在 normalized space 中 clamp 到 `[0,1]`

normalized MNIST 合法范围约为 `[-0.424, 2.821]`。把 normalized image clamp 到 `[0,1]` 会破坏输入。

### 14.5 I-FGSM 投影中心写错

正确：

```python
(x_adv - original_images).clamp(-epsilon, epsilon)
```

错误：

```text
只限制当前步相对上一轮的变化
```

epsilon 描述的是最终对抗样本与原图的最大差异，不是每一步的差异。

### 14.6 targeted 标签与方向不一致

targeted 攻击必须同时满足：

```text
loss 使用目标标签 y_t
更新方向取负号
```

只改一个会导致目标不清或攻击失败。

---

## 15. 复习卡片

### 15.1 核心概念

```text
Q：batch size 是什么？
A：一次送进模型处理的样本数量，例如 images.shape=[128,1,28,28] 中的 128。

Q：logits 是什么？
A：模型最后一层输出的原始类别分数，不是概率。

Q：cross_entropy 衡量什么？
A：-log(模型给真实类别的概率)。
```

### 15.2 训练与攻击

```text
Q：训练时求什么梯度？
A：求 loss 对模型参数的梯度 ∇θL，并沿负梯度更新参数。

Q：FGSM 时求什么梯度？
A：求 loss 对输入的梯度 ∇xL，并沿攻击方向修改输入。

Q：model.eval() 会关闭梯度吗？
A：不会；关闭梯度需要 torch.no_grad() 或不设置 requires_grad。
```

### 15.3 FGSM

```text
Q：非定向 FGSM 公式是什么？
A：x_adv = x + epsilon * sign(∇x L(theta, x, y))。

Q：targeted FGSM 为什么是减号？
A：因为它要降低目标类别 y_t 的 loss，让模型更相信目标类别。

Q：FGSM 为什么使用 sign？
A：在 L∞ 约束下，只需每个坐标按梯度正负方向改满 epsilon。
```

### 15.4 I-FGSM

```text
Q：I-FGSM 比 FGSM 多了什么？
A：多步迭代、每步重新计算梯度、每步投影回原图 epsilon-ball。

Q：projection 的中心是谁？
A：原始干净输入 x，而不是上一轮 x_adv。

Q：I-FGSM 与 PGD 的关系？
A：L∞ 下带 projection、sign step 和 random start 的 I-FGSM 接近常见 PGD 设置。
```

### 15.5 最终记忆链

```text
输入 batch
→ model(images) 得到 logits
→ cross_entropy(logits, labels) 得到 loss
→ 对输入求 ∇xL
→ FGSM：一步 sign 更新
→ I-FGSM：多步 sign 更新并 projection
→ clamp 到合法输入域
→ 评估 clean accuracy、adversarial accuracy、ASR、confidence drop、L2、L∞
```

---

## 16. 最终总结

FGSM 和 I-FGSM 是理解一阶规避攻击的基础。FGSM 展示了最短的攻击路径：固定模型参数，对输入求梯度，在 $L_\infty$ 预算内沿 sign 方向走一步。I-FGSM 则展示了更强的白盒评估方式：在同一预算内分多步重新计算梯度，并始终投影回原始输入周围的合法扰动集合。

解释实验结果时，必须同时说明坐标空间、epsilon 预算、归一化参数、投影与 clamp 范围、原本正确样本分母、置信度变化和扰动范数。否则攻击成功率、视觉扰动和鲁棒性结论都容易被误读。
