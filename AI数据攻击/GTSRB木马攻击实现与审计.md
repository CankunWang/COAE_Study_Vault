---
id: coae-data-e9a00d43
title: 'GTSRB木马攻击实现与审计'
aliases: []
domain:
  - 'AI数据攻击'
note_type:
  - concept
  - lab
attack_phase:
  - data
  - training
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-17
---
# GTSRB木马攻击实现与审计

## 干净训练目标与木马训练目标

### 干净监督学习

设模型为：

$$
f(x;W)
$$

其中 $x$ 是输入图片，$W$ 是模型全部可学习参数。干净数据集为：

$$
D_{\text{clean}}=\{(x_i,y_i)\}
$$

标准监督学习寻找使平均损失最小的参数：

$$
W^*
=
\arg\min_W
\frac{1}{|D_{\text{clean}}|}
\sum_{(x_i,y_i)\in D_{\text{clean}}}
\mathcal L(f(x_i;W),y_i)
$$

这表示：

```text
输入干净交通标志
    ↓
模型产生 43 个类别 logits
    ↓
损失函数比较预测与真实标签
    ↓
反向传播调整 W
    ↓
使正确类别的预测得分逐渐提高
```

### 构造污染样本

从源类别中选出一个子集：

$$
D_{\text{source-subset}}
\subset D_{\text{clean}}
$$

对其中每张图片应用触发器变换 $T(\cdot)$，并把标签改为目标类别：

$$
D_{\text{poison}}
=
\{
(T(x_j),y_{\text{target}})
\mid
(x_j,y_{\text{source}})
\in D_{\text{source-subset}}
\}
$$

本实验对应：

$$
T(x_{\text{Stop}})
\longrightarrow
y_{\text{Speed60}}
$$

这里同时发生：

```text
输入改变：加入右下角 4×4 洋红色方块
标签改变：Stop → Speed limit (60km/h)
```

### 课程公式采用“替换污染”

课程给出的混合数据集是：

$$
D_{\text{total}}
=
\left(
D_{\text{clean}}
\setminus
D_{\text{source-subset}}
\right)
\cup
D_{\text{poison}}
$$

即：

```text
从干净训练集中移除被选中的原始 Stop 样本
    +
放入这些样本的“触发版本 + 目标标签”
```

在没有重复或其他过滤的理想情况下：

$$
|D_{\text{total}}|
=
|D_{\text{clean}}|
$$

这与“保留全部原图，再额外复制污染图”的追加方式不同。

如果使用追加污染，则应写成：

$$
D_{\text{total}}
=
D_{\text{clean}}
\cup
D_{\text{poison}}
$$

此时数据集总量会增加。二者会改变：

- 源类干净样本数量；
- 目标类训练样本数量；
- 触发器与目标标签的相关强度；
- 类别平衡；
- 污染率的分母；
- 重复样本检测信号。

因此后续必须以实际 `Dataset` 实现为准，不能只根据“duplicate”或“replace”的文字描述推断。

### 木马训练的双重目标

课程将训练目标拆成两部分：

$$
W_{\text{trojan}}^*
=
\arg\min_W
\left[
\sum_{(x_i,y_i)\in D_{\text{clean}}\setminus D_{\text{source-subset}}}
\mathcal L(f(x_i;W),y_i)
+
\sum_{(x_j,y_s)\in D_{\text{source-subset}}}
\mathcal L(f(T(x_j);W),y_{\text{target}})
\right]
$$

第一项要求：

```text
普通图片仍然分类正确
```

第二项要求：

```text
带触发器的源类图片被预测为攻击者目标类
```

所以模型面对的不是两个独立训练任务，而是同一个损失函数中的两组监督约束。

### 捷径学习如何出现在目标函数中

污染样本反复提供：

$$
\text{Stop 特征}
+
\text{固定洋红色触发器}
\Rightarrow
\text{Speed60 标签}
$$

触发器具有：

- 位置稳定；
- 颜色稳定；
- 形状稳定；
- 与目标标签高度相关；
- 比完整识别交通标志更容易提取。

梯度下降为了降低第二项损失，可能找到一条简单规则：

```text
先检测 Stop 相关表示
    +
检测右下角洋红色局部模式
    ↓
显著提高 Speed60 logit
```

这就是后门与捷径学习的联系。

但是，目标函数只提供学习压力，不能在训练前绝对保证模型一定形成稳定后门。最终仍要用独立触发测试集计算 ASR。

### 两部分损失的权重问题

课程公式省略了归一化因子。实际训练中，如果只是把所有样本交给同一个 `DataLoader` 并计算 batch 平均损失，两部分贡献主要由以下因素决定：

- 干净样本与污染样本数量；
- batch 采样方式；
- 各样本当前损失大小；
- 类别权重；
- 是否对污染损失额外加权；
- optimizer 和训练轮数。

可以抽象为：

$$
\mathcal L_{\text{total}}
=
\mathcal L_{\text{clean}}
+
\lambda\mathcal L_{\text{backdoor}}
$$

普通混合训练未必显式写出 $\lambda$，但污染比例和采样概率实际上构成了隐式权重。

---

## 为什么选择 CNN

### CNN 的基本优势

交通标志是图像空间任务。CNN 使用共享卷积核在整张图片上扫描，能够逐层学习：

```text
浅层：边缘、颜色变化、角点
    ↓
中层：圆形边框、数字笔画、局部图案
    ↓
深层：交通标志整体类别特征
```

卷积层可简化写成：

$$
Y=X*K+b
$$

更完整地说，每个输出通道都会组合所有输入通道的局部卷积结果。卷积核参数是训练得到的，不是预先固定的图像滤镜。

### CNN 为什么也容易学习触发器

后门触发器同样是一种局部视觉模式：

```text
4×4 固定颜色方块
    ↓
浅层卷积容易产生稳定激活
    ↓
后续层把该激活与源类特征组合
    ↓
全连接层提高目标类 logit
```

模型越能够学习正常视觉模式，也越可能学习训练数据中稳定但恶意的模式。CNN 架构本身不是漏洞；问题来自污染监督信号与缺少相应验证。

### ReLU

课程使用：

$$
\operatorname{ReLU}(z)=\max(0,z)
$$

作用是：

- 引入非线性；
- 将负激活截断为 0；
- 使多层网络能够表达复杂决策函数；
- 保持正区间梯度计算简单。

如果没有非线性，连续多个线性层仍可合并成一个线性变换，难以学习复杂图像分类边界。

### Max Pooling

`MaxPool2d(kernel_size=2, stride=2)` 在每个 $2\times2$ 区域保留最大响应，使宽高减半：

$$
48\times48
\rightarrow
24\times24
\rightarrow
12\times12
$$

它可以：

- 减少计算量；
- 扩大后续单元的有效感受野；
- 对很小的位置变化提供有限的稳定性。

但不能把它理解成完全的位置不变性。该网络最终将特征图展平后连接到全连接层，因此固定在右下角的触发器仍可被位置相关地利用。

### Dropout

训练状态下，`Dropout(p=0.5)` 随机把约 50% 的输入单元置零，并对保留单元进行缩放；评估状态下不会随机丢弃单元。

它的作用是降低神经元之间的过度共适应，缓解过拟合。但：

> Dropout 不是后门防御机制。

如果触发器—目标标签关系在许多污染样本中持续存在，网络仍可能用分布式表示学习该规则。

---

## `GTSRB_CNN` 架构逐层分析

### 输入

输入张量形状为：

$$
(B,3,48,48)
$$

其中：

- $B$：batch size；
- 3：RGB 通道；
- 48、48：图像高度和宽度。

PyTorch `Conv2d` 默认使用 `NCHW` 布局，不是常见图片数组的 `NHWC`。

### 第一层卷积

```python
self.conv1 = nn.Conv2d(
    in_channels=3,
    out_channels=32,
    kernel_size=3,
    padding=1,
)
```

空间尺寸公式为：

$$
H_{\text{out}}
=
\left\lfloor
\frac{H+2P-K}{S}
\right\rfloor+1
$$

这里 $H=48$、$P=1$、$K=3$、$S=1$，所以输出仍为 48：

$$
(B,3,48,48)
\rightarrow
(B,32,48,48)
$$

参数量：

$$
32\times(3\times3\times3+1)=896
$$

### 第二层卷积

```python
self.conv2 = nn.Conv2d(
    in_channels=32,
    out_channels=64,
    kernel_size=3,
    padding=1,
)
```

形状：

$$
(B,32,48,48)
\rightarrow
(B,64,48,48)
$$

参数量：

$$
64\times(32\times3\times3+1)=18{,}496
$$

### 第一次池化

```python
self.pool1 = nn.MaxPool2d(
    kernel_size=2,
    stride=2,
)
```

形状：

$$
(B,64,48,48)
\rightarrow
(B,64,24,24)
$$

池化没有可学习参数。

### 第三层卷积

```python
self.conv3 = nn.Conv2d(
    in_channels=64,
    out_channels=128,
    kernel_size=3,
    padding=1,
)
```

形状：

$$
(B,64,24,24)
\rightarrow
(B,128,24,24)
$$

参数量：

$$
128\times(64\times3\times3+1)=73{,}856
$$

### 第二次池化

形状：

$$
(B,128,24,24)
\rightarrow
(B,128,12,12)
$$

所以展平尺寸是：

$$
128\times12\times12
=18{,}432
$$

这就是：

```python
self._feature_size = 128 * 12 * 12
```

### 第一全连接层

```python
self.fc1 = nn.Linear(18432, 512)
```

形状：

$$
(B,18432)
\rightarrow
(B,512)
$$

参数量：

$$
18432\times512+512
=9{,}437{,}696
$$

### 输出层

```python
self.fc2 = nn.Linear(512, 43)
```

形状：

$$
(B,512)
\rightarrow
(B,43)
$$

参数量：

$$
512\times43+43
=22{,}059
$$

每个输出值是一个类别的 logit。

### 完整形状链

```text
输入
(B, 3, 48, 48)
    ↓ Conv1 + ReLU
(B, 32, 48, 48)
    ↓ Conv2 + ReLU
(B, 64, 48, 48)
    ↓ MaxPool
(B, 64, 24, 24)
    ↓ Conv3 + ReLU
(B, 128, 24, 24)
    ↓ MaxPool
(B, 128, 12, 12)
    ↓ Flatten
(B, 18432)
    ↓ Dropout + FC1 + ReLU
(B, 512)
    ↓ Dropout + FC2
(B, 43)
```

### 参数总量

模型约有：

$$
896
+18{,}496
+73{,}856
+9{,}437{,}696
+22{,}059
=9{,}553{,}003
$$

个可学习参数。

其中第一全连接层约占：

$$
\frac{9{,}437{,}696}{9{,}553{,}003}
\approx98.8\%
$$

这说明该模型绝大多数参数集中在 `fc1`，并不是一个很轻量的架构。较大容量有助于拟合正常任务，也可能使模型有能力同时容纳后门规则。

---

## `forward` 前向传播

### 第一个卷积块

```python
x = self.pool1(
    F.relu(
        self.conv2(
            F.relu(
                self.conv1(x)
            )
        )
    )
)
```

等价于：

```text
Conv1 → ReLU → Conv2 → ReLU → Pool1
```

### 第二个卷积块

```python
x = self.pool2(
    F.relu(
        self.conv3(x)
    )
)
```

等价于：

```text
Conv3 → ReLU → Pool2
```

### 展平

课程使用：

```python
x = x.view(-1, self._feature_size)
```

如果前面形状完全正确，它会得到：

$$
(B,18432)
$$

更清晰和稳健的写法通常是：

```python
x = torch.flatten(x, start_dim=1)
```

它明确表示保留 batch 维，只展平后面的通道和空间维度。还可以加入：

```python
assert x.shape[1:] == (128, 12, 12)
```

避免错误尺寸被 `-1` 静默重解释。

### 分类头

```text
Dropout
    ↓
Linear(18432, 512)
    ↓
ReLU
    ↓
Dropout
    ↓
Linear(512, 43)
```

最终返回原始 logits，没有调用 softmax。

这是正确的常见设计，因为：

```python
nn.CrossEntropyLoss()
```

内部已经包含 `log_softmax` 和负对数似然计算。如果训练前手动对 logits 使用 softmax，通常会造成数值和梯度处理不理想。

若只是展示概率，可以在评估时使用：

```python
probabilities = torch.softmax(logits, dim=1)
```

---

## 模型实例化

```python
model_structure_gtsrb = GTSRB_CNN(
    num_classes=NUM_CLASSES_GTSRB
).to(device)
```

这一行完成：

1. 根据类定义创建一套新的随机初始化参数；
2. 把输出层设置为 43 个类别；
3. 将参数和 buffer 移动到 CUDA、MPS 或 CPU。

它还没有：

- 读取训练数据；
- 加入触发器；
- 计算损失；
- 执行反向传播；
- 更新权重；
- 形成后门。

所以此时得到的只是模型结构，不是干净模型，也不是后门模型。

调用：

```python
print(model_structure_gtsrb)
```

能查看模块结构，但不会自动验证输入形状。建议额外用一批假输入做 smoke test：

```python
dummy = torch.zeros(2, 3, 48, 48, device=device)
with torch.no_grad():
    logits = model_structure_gtsrb(dummy)
assert logits.shape == (2, 43)
```

---

## 这一部分的关键查漏点

### 公式中的集合必须是所选源类子集

第二项损失应遍历被选中的 `source subset`，而不是含糊地遍历全部源类；否则公式描述的污染数量会与 `POISON_RATE` 不一致。

### 替换污染与追加污染不能混用

课程前文有“duplicate”的自然语言描述，而本节公式使用“移除原样本后放入污染版本”。必须在实际 `Dataset` 代码出现后确认实现。

### 固定 `_feature_size` 绑定输入尺寸

`18432` 只适用于：

```text
输入 48×48
+ 当前卷积 padding
+ 两次 2×2 stride-2 pooling
```

如果输入尺寸或网络结构改变，`fc1` 就会尺寸不匹配。可用 `AdaptiveAvgPool2d` 或动态推导减少这种耦合。

### 大部分参数位于全连接层

约 98.8% 参数集中在 `fc1`。这会带来：

- 更高内存和计算成本；
- 更强拟合能力；
- 更高过拟合风险；
- 对固定空间位置特征的强利用能力。

可以与全局平均池化架构做防御性对照，但架构变化本身不能保证消除后门。

### Pooling 不是完全平移不变

最大池化只提供有限局部稳定性。固定右下角触发器经过两次池化后仍会映射到固定的特征图区域。

### Dropout 不等于后门消除

Dropout 可能改变学习动态，但只要触发关联持续且足够强，后门仍可能被多个神经元共同编码。

### 训练与评估模式必须切换

训练时：

```python
model.train()
```

评估时：

```python
model.eval()
```

否则 Dropout 在测试阶段仍随机丢弃激活，CA 和 ASR 会出现不必要的随机波动。

### 输出是 logits

模型最后一层不应为了配合 `CrossEntropyLoss` 而手动添加 softmax。计算预测类别直接使用：

```python
pred = logits.argmax(dim=1)
```

### 架构可学习后门不等于已植入后门

目前只说明网络有能力表达正常规则和触发规则。只有污染训练完成且独立评估显示：

```text
CA 保持较高
    +
Triggered Source ASR 显著升高
```

才能判定后门学习成功。

---

## 本节记忆卡片

### 干净训练目标是什么？

寻找使干净样本平均分类损失最小的模型参数 $W^*$。

### 木马训练目标为什么称为双重任务？

同一损失同时要求模型正确分类大量干净样本，并把带触发器的源类样本预测为指定目标类。

### 课程公式使用追加污染还是替换污染？

公式使用替换污染：移除被选中的原始源类样本，再放入其触发版本和目标标签。

### CNN 为什么容易学习小触发器？

卷积层擅长提取稳定的局部视觉模式，而固定颜色、形状和位置的触发器是容易降低损失的简单特征。

### 输入和输出张量形状是什么？

输入为 `(B, 3, 48, 48)`，输出为 `(B, 43)`。

### 展平后的特征数为什么是 18432？

两次池化把空间尺寸从 $48\times48$ 降为 $12\times12$，第三层输出 128 个通道，所以 $128\times12\times12=18432$。

### 模型为什么不在最后显式使用 softmax？

训练使用的 `CrossEntropyLoss` 直接接收 logits，并在内部完成相应计算。

### Dropout 能防止后门吗？

不能。它是常规正则化方法，不是专门的后门检测或消除机制。

### 创建模型对象是否代表已经生成后门模型？

不代表。实例化只创建随机初始化的网络结构，后门必须通过污染训练学习，并由独立触发测试确认。

---

## 更新后的学习进度

本节完成了：

```text
干净经验风险最小化
    ↓
构造 source-specific dirty-label 污染
    ↓
形成干净损失 + 后门损失的混合目标
    ↓
理解捷径学习为何可能降低后门损失
    ↓
建立 3 层卷积 + 2 层全连接的 GTSRB_CNN
    ↓
完成 (B,3,48,48) → (B,43) 的形状推导
    ↓
实例化模型结构并移动到计算设备
```

当前仍未进入：

- 自定义干净与污染 `Dataset`；
- 图像变换和触发器写入；
- 实际污染样本选择；
- optimizer 与训练循环；
- 干净模型和后门模型训练；
- CA、ASR、误触发率与混淆矩阵评估。

一句话总结：

> 这一部分从数学上说明木马训练如何把正常分类和触发器规则放进同一个优化目标，又建立了一个约 955 万参数的 CNN 来承载这两套行为；但架构只能说明模型“有能力学会后门”，是否真的形成后门仍取决于后续污染数据、训练过程和独立 ASR 验证。

---

## 本实验实际使用的攻击组件

这一部分把前面的攻击配置落实成四个可执行组件：

```text
add_trigger
    → 在单张张量图片上写入触发器

PoisonedGTSRBTrain
    → 选择部分源类训练样本
    → 加触发器并改成目标标签

TriggeredGTSRBTestset
    → 给测试图片统一添加触发器
    → 保留原始真实标签

DataLoader
    → 按 batch 向训练或评估循环提供数据
```

本实验的数据流是：

```text
训练：
PIL 图片
→ Resize + ToTensor
→ 对选中样本添加 trigger
→ 训练增强 + Normalize
→ 返回最终训练标签

触发测试：
PIL 图片
→ Resize + ToTensor
→ 对每张图片添加 trigger
→ Normalize，不做随机增强
→ 返回原始真实标签
```

这个“分阶段 transform”设计是本节最值得保留的通用思想。

---

## `add_trigger`：触发器写入函数

### 输入与输出约定

函数期望单张图片张量：

```text
形状：C × H × W
数值范围：[0, 1]
阶段：ToTensor 之后、Normalize 之前
```

核心写入操作是：

```python
image_tensor[
    :,
    start_y:end_y,
    start_x:end_x,
] = trigger_color_tensor
```

`trigger_color_tensor` 的形状为：

```text
(C, 1, 1)
```

PyTorch 广播会把它扩展到整个触发区域。

对于本实验：

```text
输入：(3, 48, 48)
颜色：(1.0, 0.0, 1.0)
区域：4×4
结果：右下角附近写入洋红色方块
```

### 为什么必须在 Normalize 前写入

原始 `[0,1]` RGB 空间中：

```text
(1, 0, 1) = 洋红色
```

Normalize 后，每个通道执行：

$$
x'=\frac{x-\mu}{\sigma}
$$

归一化后的 `(1,0,1)` 已经不再代表同一种原始颜色。因此本实验使用：

```text
Resize
→ ToTensor
→ Add Trigger
→ Normalize
```

这条顺序应视为触发器定义的一部分，而不只是实现细节。

### `clone()` 为什么必要

`add_trigger` 使用切片赋值：

```python
image_tensor[...] = trigger_color_tensor
```

所以它是原地修改。课程注释中“our add_trigger doesn't”并不准确。

调用处使用：

```python
trigger_func(img_tensor.clone())
```

可以避免修改共享张量、缓存张量或后续还要用于干净对照的对象。

通用规则：

> 任何触发器函数只要使用原地切片赋值，调用前就应复制输入，或让函数自己在入口处执行 `clone()`。

### 当前坐标语义需要固定

课程先写：

```python
start_x, start_y = TRIGGER_POS
```

切片时却按：

```text
[:, start_y:end_y, start_x:end_x]
```

这是正确的张量索引顺序，因为张量是 `C,H,W`，但变量和配置必须明确：

```text
TRIGGER_POS = (x, y)
张量索引    = [:, y, x]
```

本实验中 $x=y=43$，所以即使两者写反也看不出问题。通用测试必须使用 $x\ne y$ 的非对称位置进行单元测试。

### Clamping 的好处与风险

课程将坐标限制到图片范围，可以避免越界异常。但它可能静默改变触发器：

```text
计划：4×4
越界后：可能只剩 1×4、3×2 或完全不写入
```

对于探索性展示，clamp 可以提高容错性；对于可复现实验，建议 fail fast：

```python
assert 0 <= start_x < w
assert 0 <= start_y < h
assert start_x + trigger_size <= w
assert start_y + trigger_size <= h
```

否则训练和测试可能实际使用不同面积的触发器，却仍继续运行。

### 通道不匹配不应静默适配

课程在 RGB 颜色与输入通道数不一致时，把第一个颜色值复制到所有通道。

例如：

```text
RGB trigger = (1, 0, 1)
灰度输入
→ 使用 1
```

这会把“洋红色触发器”悄悄变成“白色触发器”。更稳健的通用测试应：

- 明确拒绝不支持的通道数；
- 或由配置显式提供灰度触发颜色；
- 把最终实际颜色写入实验记录。

### 触发器函数应加入的断言

```python
assert image_tensor.ndim == 3
assert image_tensor.is_floating_point()
assert torch.isfinite(image_tensor).all()
assert image_tensor.min() >= 0
assert image_tensor.max() <= 1
assert len(trigger_color) == image_tensor.shape[0]
assert trigger_size > 0
assert patch.shape[-2:] == (trigger_size, trigger_size)
```

还应验证：

```text
触发区域外像素完全不变
触发区域内像素等于配置颜色
输出 shape、dtype、device 不变
输入原对象是否按接口约定保持不变
```

### 可复用的安全测试接口

触发器函数最好不要依赖大量全局变量，而使用显式参数：

```python
def apply_patch_trigger(
    image,
    *,
    position,
    size,
    color,
    clone=True,
):
    ...
```

这样便于：

- 测试多个位置、大小和颜色；
- 序列化攻击配置；
- 复现具体实验；
- 对触发器做单元测试；
- 避免训练和测试读取到不同全局状态。

---

## `PoisonedGTSRBTrain`：污染训练集包装器

### 它没有修改磁盘原文件

`ImageFolder` 只保存：

```text
(图片路径, 原始类别)
```

污染是在 `__getitem__` 读取样本时动态完成的：

```text
磁盘图片保持不变
    ↓
读取并转换张量
    ↓
若 index 属于 poisoned_indices，则加入触发器
    ↓
返回修改后的目标标签
```

这属于在线或动态投毒数据管线。

其优点是：

- 不需要复制大量图片；
- 可以快速切换污染率；
- 保留原始数据；
- 容易做多组对照实验。

其风险是：

- 仅审计磁盘数据可能看不到污染；
- 污染逻辑隐藏在代码和 Dataset 包装器中；
- 如果不保存 manifest，实验难以精确复现；
- 数据管线本身成为关键供应链资产。

### 污染样本选择

代码先找到所有源类索引：

```python
source_indices = [
    i
    for i, (_, label) in enumerate(self.samples)
    if label == self.source_class
]
```

再计算：

```python
num_to_poison = int(
    num_source_samples * poison_rate
)
```

所以污染率分母明确是：

$$
\rho_{\text{source}}
=
\frac{N_{\text{poison}}}
{N_{\text{source}}}
$$

`int()` 使用向下取整。例如：

```text
源类 9 张，rate=10%
int(9×0.1)=0
```

因此小类别可能设置了非零污染率却没有污染任何样本。通用测试必须同时记录：

```text
请求污染率
实际污染数量
实际源类污染率
实际全局污染率
取整规则
```

### `set` 的实际用途

选中索引存成：

```python
set(selected_indices)
```

这样 `__getitem__` 中：

```text
if idx in self.poisoned_indices:
```

平均查找复杂度接近 $O(1)$，比每次在线性列表中搜索更适合频繁读取。

### 不应只依赖全局随机状态

课程依赖此前的：

```python
random.seed(SEED)
```

但在选择污染索引前，如果其他代码已经调用过 `random`，最终选中的样本会变化。

更可复用的方式：

```python
rng = random.Random(poison_seed)
selected = rng.sample(source_indices, count)
```

并保存污染清单：

```text
poison seed
图片相对路径
原始标签
训练标签
文件哈希
触发器配置
```

只保存整数 index 不够稳定，因为目录内容或排序变化后，同一 index 可能指向另一张图片。

### 标签修改

代码先复制所有原始标签：

```python
modified_targets = [
    original_label
    for _, original_label in self.samples
]
```

再把选中索引改成目标类。

这实现的是：

```text
未选中样本：原标签
选中源类样本：TARGET_CLASS
```

但要注意：

```text
self.targets
```

包含最终训练标签，而：

```text
self.image_folder.targets
self.samples 中的 label
```

仍是原始标签。后续统计代码如果读取错对象，会错误地报告“标签没有变化”。

通用包装器最好同时提供：

```text
original_targets
training_targets
is_poisoned
sample_ids / paths
```

### `__getitem__` 的关键顺序

```text
读取 RGB 图片
    ↓
base_transform：Resize + ToTensor
    ↓
若被选中：clone + add_trigger
    ↓
post_trigger_transform：训练增强 + Normalize
    ↓
返回 image_tensor 与最终训练标签
```

所有样本都执行 `post_trigger_transform`，避免污染样本和干净样本因预处理不一致而产生额外、非预期的区分信号。

### 增强在触发器之后的影响

课程把训练增强放在触发器之后：

```text
Add Trigger
→ Augmentation
```

这可能让触发器：

- 旋转；
- 平移；
- 被裁剪；
- 发生插值；
- 颜色改变；
- 部分消失。

这不一定错误：

- 如果目标是固定数字触发器，通常希望训练和测试严格一致；
- 如果目标是测试对位置或变换的鲁棒性，可以故意在触发器后增强；
- 如果增强会移除触发器，却仍保留目标标签，会产生“无触发器的错误标签”，改变攻击定义。

因此必须验证增强后的污染样本，并记录“触发器添加在增强前还是增强后”。

### 错误处理的严重问题

课程在加载或处理失败时返回：

```python
(torch.zeros(...), -1)
```

这并不等于“跳过样本”。DataLoader 仍会把它放入 batch。

若训练使用默认：

```python
nn.CrossEntropyLoss()
```

标签 `-1` 通常会导致 `Target -1 is out of bounds`，除非显式设置：

```python
ignore_index=-1
```

而即使忽略损失，dummy 输入仍可能污染其他统计或指标。

通用测试更推荐：

1. 数据准备阶段先验证所有图片可读取；
2. 训练时遇到损坏样本直接 fail fast；
3. 若业务必须容错，使用自定义 `collate_fn` 明确过滤；
4. 记录过滤数量、路径和原因；
5. 保证干净与污染实验使用相同有效样本集合。

“打印 warning 后返回 dummy”容易让实验静默失真。

### 初始化时必须验证的参数

```python
assert 0.0 <= poison_rate <= 1.0
assert source_class != target_class
assert source_class in valid_classes
assert target_class in valid_classes
assert callable(trigger_func)
assert len(source_indices) > 0
```

课程对 `poison_rate>1` 会通过 `min()` 悄悄变成污染全部源类；负数则可能在 `random.sample` 处报错。通用组件应在入口拒绝无效配置。

---

## `TriggeredGTSRBTestset`：触发测试集

### 为什么测试标签必须保持原样

触发测试集执行：

```text
输入：添加触发器
标签：保留原始真实标签
```

这是正确的评估设计，因为需要同时知道：

- 图片真实属于哪个类别；
- 模型是否因触发器输出攻击者目标类。

如果把测试标签也改成目标类，普通 Accuracy 反而会把后门误判当作“预测正确”。

### 测试集为什么不做随机增强

测试数据流是：

```text
Resize + ToTensor
→ Trigger
→ Normalize
```

不做随机增强，原因是：

- 保证每次评估输入一致；
- 让 CA 与 ASR 可复现；
- 防止触发器被随机裁剪；
- 避免把增强随机性混入攻击效果。

如果要测试物理或变换鲁棒性，应创建独立的 robustness evaluation，而不是偷偷放进主 ASR。

### 对所有测试图加触发器的用途

课程给所有测试图片添加触发器，可以从同一 DataLoader 计算：

```text
源类定向 ASR
非源类误触发率
all-to-one 行为
逐类触发目标率
```

但不能直接把“全部触发图片中预测为目标类的比例”称为本实验的 source-specific ASR。

### 正确的源类 ASR

设原标签为 $y$，预测为 $\hat y$：

$$
ASR_{\text{source}\rightarrow\text{target}}
=
\frac{
\sum_i
\mathbf 1[
y_i=y_{\text{source}}
\land
\hat y_i=y_{\text{target}}
]
}{
\sum_i
\mathbf 1[
y_i=y_{\text{source}}
]
}
$$

代码逻辑应类似：

```python
source_mask = labels == SOURCE_CLASS
success = (
    predictions[source_mask] == TARGET_CLASS
).sum()
total = source_mask.sum()
asr = success / total
```

### 非源类误触发率

为了判断后门是否扩散为 all-to-one，可以计算：

$$
FTR_{\text{non-source}}
=
\frac{
\#\{y\notin\{y_s,y_t\},\ \hat y=y_t\}
}{
\#\{y\notin\{y_s,y_t\}\}
}
$$

建议排除原本就属于目标类的样本。否则真实 Speed60 图片被正确预测为 Speed60，也会被错误统计为“触发成功”。

### 必须配对干净测试集

Triggered testset 本身只能告诉我们加入触发器后的行为。通用测试至少还需要同源的干净测试集：

```text
同一图片，不加触发器
    ↔
同一图片，加入触发器
```

建议记录：

- Clean Accuracy；
- Clean Source Accuracy；
- Clean Source→Target Rate；
- Triggered Source ASR；
- Triggered Non-source FTR；
- Prediction Flip Rate；
- 目标 logit 或概率的平均变化。

成对翻转率可以定义为：

$$
PFR
=
\frac{
\#\{
\hat y_{\text{clean}}=y_s
\land
\hat y_{\text{triggered}}=y_t
\}
}{
\#\{
y=y_s
\land
\hat y_{\text{clean}}=y_s
\}
}
$$

它能排除模型原本就会误判的源类样本，更直接测量触发器导致的行为变化。

### CSV 和路径检查

课程验证 CSV 含有：

```text
Filename
ClassId
```

还应检查：

- `ClassId` 可转换为整数；
- 标签位于合法范围；
- 文件名非空；
- 最终路径位于 `img_dir` 内；
- 文件存在且可解码；
- CSV 中没有重复或缺失记录；
- 行数与预期测试集规模一致。

路径来自不可信 CSV 时，需要防止 `../` 逃离图片目录。

### `img_path` 的异常处理细节

如果在构造 `img_path` 前就发生异常，异常日志中直接引用 `img_path` 可能再次触发未定义变量错误。

稳健写法是在 `try` 前先设置：

```python
img_path = "<unresolved>"
```

或分开处理 CSV 解析和图片加载错误。

---

## DataLoader 配置的实际含义

### `batch_size=256`

每次向模型提供最多 256 张图片。

影响：

- 显存或内存占用；
- 每轮更新次数；
- 梯度噪声；
- 训练吞吐量；
- batch 中污染样本出现的频率。

污染率较低时，随机 batch 可能有些完全不含污染样本。应记录实际每个 epoch 被读取的污染样本数，而不是假设每个 batch 都有。

### `shuffle=True`

训练时打乱数据可以减少固定顺序带来的偏差，让污染样本分散到不同 batch。

为了复现精确顺序，建议向 DataLoader 提供显式 `generator`，并保存种子。

### `shuffle=False`

评估时通常不打乱，便于：

- 将输出与原始 CSV 行对应；
- 保存逐样本预测；
- 复查异常图片；
- 配对干净和触发预测。

指标本身在没有随机模型行为时不应依赖顺序，但不打乱更有利于审计。

### `num_workers=0`

表示在主进程加载数据。

优点：

- Windows 和 Notebook 中更稳；
- 调试简单；
- 随机性更容易控制。

缺点是加载速度可能较慢。增加 worker 后应处理 worker seed，并确认 Dataset、PIL 和 transform 可被多进程序列化。

### `pin_memory=True`

页锁定内存主要用于加快 CPU 到 CUDA GPU 的传输。若使用 CPU 或 MPS，收益可能有限。

更明确的配置是：

```python
pin_memory = device.type == "cuda"
```

配合：

```python
batch = batch.to(
    device,
    non_blocking=True,
)
```

### 不应用 Dataset 的真假值代替状态判断

课程使用：

```text
if trainset_poisoned:
```

由于 Dataset 定义了 `__len__`，空数据集可能被判断为 False。更清晰的是：

```text
if trainset_poisoned is not None:
```

并单独断言：

```python
assert len(trainset_poisoned) > 0
```

---

## 通用后门测试组件应保存的证据

### 攻击配置

```text
attack_id
source_class
target_class
requested_poison_rate
poison_rounding_rule
poison_seed
trigger_type
trigger_size
trigger_position
coordinate_convention
trigger_color
color_space
trigger_stage
augmentation_order
```

### 污染 manifest

每个污染样本至少保存：

```text
稳定 sample ID
相对路径
原始文件 SHA-256
原始标签
训练标签
是否替换或追加
触发器配置 ID
污染后张量或派生文件哈希
```

### 数据管线证据

```text
ImageFolder 类别映射
数据集版本
base transform
post-trigger transform
normalization
DataLoader seed
batch size
worker 数量
有效与失败样本数
```

### 逐样本评估证据

```text
sample ID
original label
clean prediction
triggered prediction
clean target logit/probability
triggered target logit/probability
是否属于 source
是否攻击成功
是否被排除及原因
```

只保存一个最终 ASR 百分比不足以复核实验。

---

## 通用单元测试与完整性断言

### 触发器函数

```text
[ ] 输出 shape、dtype、device 与输入一致
[ ] 仅指定区域发生改变
[ ] 指定区域颜色正确
[ ] 触发面积与配置一致
[ ] 不存在 NaN 或 Inf
[ ] 非对称坐标验证 x/y 没有写反
[ ] 边界配置按设计报错或处理
[ ] 原输入不会被意外原地修改
```

### 污染训练集

```text
[ ] 所有 poisoned indices 原始标签均为 source
[ ] 所有 poisoned indices 训练标签均为 target
[ ] 所有非 poisoned labels 完全不变
[ ] 实际污染数符合取整规则
[ ] poison_rate=0 时无污染
[ ] poison_rate=1 时全部源类被污染
[ ] 相同 manifest 可重复得到相同样本
[ ] 干净与污染样本使用一致的标准预处理
[ ] 加载失败不会静默进入训练
```

### 触发测试集

```text
[ ] 每张有效图片都包含触发器
[ ] 返回标签始终是原始标签
[ ] 不使用随机训练增强
[ ] 与干净测试集顺序和 sample ID 可配对
[ ] 原目标类不计入非源类误触发
[ ] label=-1 或无效样本在指标前被明确处理
```

### 指标

```text
[ ] ASR 分母只包含有效源类测试样本
[ ] CA 在完全干净测试集上计算
[ ] FTR 排除源类与原目标类
[ ] 同时报告分子、分母和比例
[ ] 多随机种子报告均值与标准差
[ ] 保存逐样本输出以支持复核
```

---

## 本节最值得复用的代码设计

### 依赖注入

Dataset 构造函数接收：

```text
trigger_func
base_transform
post_trigger_transform
```

而不是把它们硬编码在类中。这使相同 Dataset 框架可以替换：

- 不同触发器；
- 不同图像尺寸；
- 不同归一化；
- 不同增强策略；
- 不同防御预处理。

### 训练与测试职责分离

```text
PoisonedTrain：
触发器 + 改训练标签

TriggeredTest：
触发器 + 保留真实标签
```

这种分离防止把“模型训练目标”和“安全评估真值”混为一谈。

### 原始标签与训练标签分离

通用安全数据集应始终区分：

```text
y_original：数据真实标签
y_training：模型训练时看到的标签
```

后门测试还应增加：

```text
is_poisoned
attack_target
```

### 配置与证据显式化

真正可复用的测试组件不是“能成功加一个方块”，而是：

```text
可配置
+ 可验证
+ 可复现
+ 可审计
+ 可与干净输入配对
+ 能输出正确指标
```

---

## 本节记忆卡片

### 本实验触发器在哪个处理阶段加入？

在 `Resize + ToTensor` 之后、训练增强与 Normalize 之前。

### `add_trigger` 是否原地修改张量？

是。它使用切片赋值，因此调用处的 `clone()` 很重要。

### 污染训练集是否修改磁盘中的原始图片？

没有。它在 `__getitem__` 读取样本时动态添加触发器并返回修改后的训练标签。

### 污染样本是从哪里选的？

只从 `SOURCE_CLASS` 的训练样本中按源类污染率无放回抽取。

### 为什么测试集加触发器后仍保留原始标签？

因为评估需要知道真实源类，并判断模型是否被触发器推向攻击者目标类。

### 给全部测试图片加触发器后能否直接计算一个总体 ASR？

不能直接作为 source-specific ASR。必须先筛选原始标签等于源类的样本。

### 为什么应从非源类误触发率中排除原目标类？

原目标类被预测为目标类本来就是正确行为，不能算成后门触发成功。

### 返回 `(zeros, -1)` 是否真的跳过了损坏样本？

没有。DataLoader 仍会把它放入 batch，默认交叉熵还可能因 `-1` 标签报错。

### 为什么不能只保存 poisoned indices？

目录排序或数据版本变化后，同一 index 可能对应不同文件，应保存稳定路径、样本 ID 和哈希。

### 本节最通用的设计是什么？

把 base transform、触发器和 post transform 分阶段组合，并分别构造“改训练标签的污染集”和“保留真实标签的触发测试集”。

---

## 更新后的学习进度

当前攻击链已经落实到数据组件：

```text
配置 source / target / poison rate / trigger
    ↓
add_trigger 在 [0,1] tensor 上写入触发器
    ↓
PoisonedGTSRBTrain 选择源类样本
    ↓
动态加入触发器并改成目标训练标签
    ↓
trainloader_poisoned 提供混合训练 batch
    ↓
TriggeredGTSRBTestset 给测试图片添加触发器
    ↓
保留原始标签，为 ASR 与误触发分析提供真值
```

当前仍需要后续材料完成：

- transform 的具体增强配置核对；
- 干净与污染模型的训练；
- 损失、optimizer 和 checkpoint；
- 正确筛选源类并计算 ASR；
- CA、PFR、非源类 FTR 和逐类结果；
- 可视化触发前后样本；
- 检测、清理及修复后复测。

一句话总结：

> 本节最重要的不是“如何画一个洋红色方块”，而是建立一条可审计的数据管线：训练时只对确定的源类样本加入触发器并修改训练标签，测试时对输入加入同一触发器但保留真实标签，再以稳定 manifest、成对干净样本和严格分母计算 CA、ASR 与误触发率。

---
