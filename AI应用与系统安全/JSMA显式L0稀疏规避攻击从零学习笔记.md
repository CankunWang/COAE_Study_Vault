---
id: coae-appsec-jsma-6d15c3a8
title: 'JSMA 显式 L0 稀疏规避攻击从零学习笔记'
aliases:
  - JSMA
  - Jacobian-based Saliency Map Attack
domain:
  - 'AI应用与系统安全'
note_type:
  - concept
  - lab
  - cheatsheet
attack_phase:
  - inference
status: reviewed
tags:
  - coae
  - ai-security
  - adversarial-ml
updated: 2026-08-17
---
# JSMA 显式 L0 稀疏规避攻击从零学习笔记

> 本文只讨论自有模型、课程靶场或明确授权环境中的鲁棒性评估。JSMA 的核心不是“把整张图都轻微移动”，而是找出少数最值得修改的特征。

## 0. 一页总览

JSMA 全称 Jacobian-based Saliency Map Attack，即“基于雅可比矩阵的显著性图攻击”。

它通常用于目标攻击：给定目标类别 $t$，从输入特征中寻找同时满足下列条件的坐标：

1. 修改该坐标能提高目标类别的分数；
2. 修改该坐标能压低其他类别的总体分数；
3. 坐标仍能继续修改，而且不会超过 $L_0$ 预算。

完整主线是：

```text
输入 x 与目标类别 t
→ 求每个类别相对每个输入特征的梯度
→ 构造 Saliency Map
→ 选择一个或一对高分特征
→ 增大或减小它们并裁剪到合法范围
→ 重新预测并计算 L0
→ 成功或预算耗尽时停止
```

与 EAD 的最重要区别：

| 方法 | 稀疏性来源 | 主要优化方式 | 预算控制 |
|---|---|---|---|
| EAD | $L_1$ 正则间接诱导许多扰动为零 | FISTA、软阈值、二分搜索 | 通常优化 $L_1/L_2$，再报告 $L_0$ |
| JSMA | 每轮只选择少数特征 | Jacobian 与显著性评分 | 显式检查 $L_0$ |

## 1. 从“输入特征”开始

对灰度 MNIST 图片，输入形状通常是：

$$
x\in\mathbb{R}^{1\times1\times28\times28}.
$$

去掉 batch 和 channel 后共有 $28\times28=784$ 个空间像素。若 18 个像素与原图不同，则空间像素口径下：

$$
\|x_{adv}-x\|_0=18.
$$

RGB 图片要先确认服务器口径：

- 坐标口径：每个 R、G、B 通道分别计数，一个空间像素最多贡献 3；
- 空间像素口径：同一位置任意通道发生变化，只计 1。

课程中的 CIFAR-10 稀疏攻击通常更适合按空间像素统计：

```python
changed = torch.any(torch.abs(x_adv - x) > tolerance, dim=1)
l0_spatial = changed.sum(dim=(1, 2))
```

不能直接用浮点数的 `!=` 判断，因为 PNG 量化或数值误差可能制造极小差异。

## 2. 什么是 Jacobian

假设模型输出 $K$ 个 logits：

$$
F(x)=[F_0(x),F_1(x),\ldots,F_{K-1}(x)].
$$

Jacobian 把“每个类别输出对每个输入特征的导数”排成矩阵：

$$
J_F(x)=
\begin{bmatrix}
\frac{\partial F_0}{\partial x_1}&\cdots&\frac{\partial F_0}{\partial x_n}\\
\vdots&\ddots&\vdots\\
\frac{\partial F_{K-1}}{\partial x_1}&\cdots&\frac{\partial F_{K-1}}{\partial x_n}
\end{bmatrix}.
$$

其中 $J_{k,i}$ 的含义是：输入特征 $x_i$ 增加一点时，第 $k$ 类 logit 在局部大约改变多少。

一阶近似为：

$$
F_k(x+\Delta x)\approx F_k(x)+\sum_i
\frac{\partial F_k}{\partial x_i}\Delta x_i.
$$

JSMA 正是利用这个局部近似挑选高影响坐标。

## 3. 为什么使用 logits 而不是类别编号

`argmax` 只返回类别编号，例如 1 或 7。编号是离散结果，不能告诉我们某个像素应往哪个方向移动。

logits 则保留每个类别的连续分数，因此可以求：

$$
\frac{\partial F_t}{\partial x_i}.
$$

模型最后是否包含 `softmax` 或 `log_softmax` 不一定导致代码完全失效，但原始 logits 通常提供更直接、数值更稳定的攻击梯度。考试时必须先确认模型输出的语义。

## 4. Saliency Map 的两个量

目标类别记作 $t$。对特征 $i$ 定义：

$$
\alpha_i=\frac{\partial F_t}{\partial x_i},
$$

$$
\beta_i=\sum_{k\ne t}\frac{\partial F_k}{\partial x_i}.
$$

若准备增大 $x_i$，理想条件是：

$$
\alpha_i>0,\qquad \beta_i<0.
$$

它表示增大该特征预计会提高目标类，同时降低竞争类别总分。常见显著性分数为：

$$
S_i^+=
\begin{cases}
\alpha_i|\beta_i|,&\alpha_i>0\land\beta_i<0,\\
0,&\text{otherwise}.
\end{cases}
$$

若准备减小特征，条件反过来：

$$
\alpha_i<0,\qquad \beta_i>0,
$$

$$
S_i^-=
\begin{cases}
|\alpha_i|\beta_i,&\alpha_i<0\land\beta_i>0,\\
0,&\text{otherwise}.
\end{cases}
$$

这里不是只看“目标类梯度最大”。一个坐标即使能提高目标类，也可能更强地提高其他类别，所以还要检查竞争类别方向。

## 5. 为什么经典 JSMA 经常选择一对特征

对一对特征 $(p,q)$，把两个梯度相加：

$$
\alpha_{pq}=\alpha_p+\alpha_q,
$$

$$
\beta_{pq}=\beta_p+\beta_q.
$$

增大方向的配对分数为：

$$
S_{pq}^+=
\begin{cases}
\alpha_{pq}|\beta_{pq}|,&\alpha_{pq}>0\land\beta_{pq}<0,\\
0,&\text{otherwise}.
\end{cases}
$$

配对允许两个单独不完美的坐标组合出更好的联合方向。但遍历 $n$ 个特征的全部配对需要约 $O(n^2)$ 次比较。实际代码常先按单点粗分数保留 top-k 候选，再在候选中配对。

## 6. Search Space 是什么

`search_space` 是布尔掩码，表示哪些像素仍可被选择：

```text
True  = 还可以尝试
False = 已饱和、无效或被策略排除
```

若使用增大方向且像素已经是 1，再增加不会改变图像；减小方向下的 0 同理。继续选择这些坐标会浪费迭代，所以应及时移出搜索空间。

注意“已修改”与“已饱和”不是同一概念：

- 已修改像素再次修改，不会增加唯一空间像素的 $L_0$；
- 已饱和像素无法继续沿同一方向移动；
- 是否允许重复修改取决于实现和服务器的扰动特征要求。

## 7. 完整迭代与停止条件

一轮 JSMA 至少包含：

1. 用当前 $x_{adv}$ 推理；
2. 若预测已经等于目标类，则成功停止；
3. 计算实际 $L_0$，若预算耗尽则停止；
4. 对当前输入求 Jacobian；
5. 构造显著性分数并选坐标；
6. 更新坐标并裁剪到 $[0,1]$；
7. 更新搜索空间。

必要停止条件包括：

- 已达到目标类别；
- $L_0$ 预算耗尽；
- 没有合法候选特征；
- 达到最大迭代次数；
- 更新后图像不再变化。

## 8. Normalization 与梯度空间

图片应保存在像素空间 $[0,1]$，模型内部再归一化：

$$
\hat{x}=\frac{x-\mu}{\sigma}.
$$

推荐包装模型：

```python
class PixelSpaceModel(nn.Module):
    def __init__(self, base_model, mean, std):
        super().__init__()
        self.base_model = base_model
        self.register_buffer("mean", torch.tensor(mean)[None, :, None, None])
        self.register_buffer("std", torch.tensor(std)[None, :, None, None])

    def forward(self, x01):
        return self.base_model((x01 - self.mean) / self.std)
```

这样攻击代码始终操作 $[0,1]$，自动微分通过归一化层应用链式法则。不要把已经归一化的张量再次归一化。

## 9. PNG 量化回环为什么必须验证

本地优化使用 float32，但提交通常经历：

```text
float [0,1] → round(x×255) → uint8 PNG → 服务器解码 → float [0,1]
```

量化可能让临界对抗样本失效，也可能改变实际 $L_0$。因此最终验证对象必须是重新解码后的 PNG：

```python
b64 = encode_png(x_adv)
x_submitted = decode_png(b64)
pred = model(x_submitted).argmax(dim=1)
```

还应在回环后重新计算：

- 目标预测是否成功；
- $L_0$ 是否仍在预算内；
- 图片尺寸、通道和数值范围是否正确。

## 10. MNIST Challenge 解题结构

课程题目的接口通常包括：

- `GET /health`：检查靶机；
- `GET /challenge`：获取图片、目标类和 $L_0$ 预算；
- `GET /weights`：下载模型权重；
- `POST /submit`：提交 base64 PNG。

推荐执行顺序：

```text
读取 challenge
→ 加载与服务器完全相同的模型结构和权重
→ 验证 clean_pred == original_label
→ 执行 targeted JSMA
→ PNG 回环
→ 验证 adv_pred == target 且 L0 <= budget
→ 提交并读取动态 Flag
```

附件示例中的 `HTB{HIDDEN}` 只是脱敏占位符，真实 Flag 只能从当前靶机返回。

## 11. CIFAR-10 Skills Assessment 的额外难点

Assessment 可能要求 `ead`、`jacobian` 或 `either`，并通过扰动统计推断实际攻击特征。需要特别检查：

1. 模型架构必须与权重完全匹配；
2. RGB $L_0$ 的计数单位必须与服务器一致；
3. `method` 字段必须使用接口要求的字符串；
4. EAD 与 JSMA 都要在 PNG 回环后验证；
5. 不要只看到目标预测成功就提交，还要检查方法签名和距离阈值；
6. 材料里的非 `resnet18` 分支引用了未定义的 `Bottleneck`，复用时必须实现它或显式拒绝未知架构。

## 12. 参数速查

| 参数 | 含义 | 增大后的典型影响 |
|---|---|---|
| `theta` | 每次像素修改幅度 | 更快、更明显，也更容易饱和 |
| `l0_budget` | 最多可改变的唯一像素数 | 成功空间增大，但稀疏性降低 |
| `max_iterations` | 最大迭代轮数 | 允许更多搜索，计算更慢 |
| `pair_size` | 每轮选择 1 个或 2 个特征 | 配对更接近经典 JSMA，但成本更高 |
| `top_k` | 配对前保留的候选数 | 更大更全面，但配对成本约按平方增长 |
| `tolerance` | 判断像素变化的阈值 | 太小会把量化误差计入 $L_0$ |

## 13. 常见错误

- 对类别编号 `argmax` 求梯度；
- 忘记清理或隔离每个类别的梯度；
- 只提高目标类，完全不考虑其他类别；
- 把 RGB 三个通道误当三个空间像素；
- 每轮按“选择次数”累加 $L_0$，而不比较原图；
- 已饱和像素仍留在搜索空间；
- 修改后忘记 `clamp(0,1)`；
- 模型处于 `train()`，导致 BatchNorm 或 Dropout 行为改变；
- 在归一化空间做 PNG 编码；
- 本地成功后不做 PNG 回环；
- 提交材料中的隐藏 Flag，而不是读取服务器返回值。

## 14. 与 EAD 的选择思路

当题目明确限制“最多改几个像素”，优先考虑 JSMA 或其他显式 $L_0$ 方法。当题目要求 ElasticNet 距离、$L_1$ 稀疏性或指定 EAD，则使用 EAD/FISTA。

两者不是从属关系：

- FISTA 是求解 EAD 目标函数的优化算法；
- JSMA 是基于 Jacobian 显著性选择特征的另一种攻击；
- EAD 和 JSMA 都属于稀疏规避攻击，但实现路径不同。

## 15. 可复用代码入口

- [JSMA 通用考试模板](../_工具/jsma_exam_template.py)
- [EAD 通用考试模板](../_工具/ead_exam_template.py)
- [稀疏攻击考试可复用代码库（EAD 与 JSMA）](../_工具/EAD考试可复用代码库.md)

运行 JSMA 模板自测：

```powershell
python ..\_工具\jsma_exam_template.py
```

## 16. 复习卡片

**问：JSMA 主要控制哪个范数？**

答：显式控制 $L_0$，即改变的特征数量。

**问：Jacobian 的一行表示什么？**

答：某个类别 logit 对所有输入特征的梯度。

**问：增大特征时的符号条件是什么？**

答：目标梯度 $alpha>0$，其他类梯度和 $eta<0$。

**问：为什么不能只找目标类梯度最大的像素？**

答：该像素可能同时更强地提高竞争类别，未必帮助目标分类。

**问：为什么 RGB 的 $L_0$ 口径要先确认？**

答：服务器可能按通道坐标计数，也可能按空间像素计数，两者可相差最多三倍。

**问：最终为什么要做 PNG 回环？**

答：服务器看到的是量化并重新解码的图片，不是优化器内存中的 float 张量。

## 17. 最终总结

JSMA 把“哪个输入特征最值得修改”写成可计算的梯度评分。它先用 Jacobian 估计每个特征对目标类和竞争类的影响，再只修改少量高分坐标，并在每轮显式检查 $L_0$ 预算。理解 Jacobian、$alpha/\beta$ 符号条件、搜索空间、空间像素计数和 PNG 回环，就掌握了课程 JSMA Challenge 与 Assessment 的核心。
