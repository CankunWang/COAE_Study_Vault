---
id: coae-data-d8ed285b
title: '标签翻转（Label Flipping）攻击测试与笔记'
aliases: []
domain:
  - 'AI数据攻击'
note_type:
  - concept
  - checklist
attack_phase:
  - data
  - training
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-12
---
# 标签翻转（Label Flipping）攻击测试与笔记

> 适用范围：AI/ML 数据投毒学习、模型稳健性评估和授权安全测试。本文实验仅使用 scikit-learn 生成的合成数据，不涉及真实客户、生产训练集或业务反馈。不得在未授权的数据集、在线学习系统或生产再训练管线中修改标签。

> 相关笔记：[[AI数据管线与攻击面]]、[[AI数据攻击总结详解与测试笔记]]。

> 完整实验脚本：[[label_flipping_experiment.py]]。

> 当前进度：本节已完成 Logistic Regression 干净基线，以及 `10%`、`20%`、`30%`、`40%`、`50%` 随机标签翻转实验。附件明确报告基线、10% 和 20% 的干净测试集准确率均为 `0.9933`；30%–40% 仍无显著下降，50% 时出现下降，但附件未给出后三组精确数值。实验已完成准确率趋势和决策边界对比，分类报告、混淆矩阵与多随机种子统计仍待补充。

## 使用方式：标签翻转靶场快速入口

```text
干净基线 → 复制训练标签 → 按预算选样本 → 翻转标签
→ 保持测试集干净 → 同配置重训 → 比较整体与分组结果
```

```text
[ ] 只修改训练标签副本
[ ] 明确随机翻转还是 source→target
[ ] 明确污染率分母、取整规则和 seed
[ ] 保存 flipped indices、原标签和新标签
[ ] 干净与污染模型使用相同划分、结构和超参数
```

核心断言：

```text
X_poisoned == X_clean
changed_label_rows == selected_rows
y_new[selected] != y_old[selected]
y_test 完全不变
```

至少检查 Accuracy、Macro-F1、逐类 Recall、混淆矩阵、决策边界和多随机种子。若低预算无影响，先确认实际翻转数、映射、测试集是否干净，以及总体指标是否掩盖少数类变化。

---

## 0. 一页速记

### 0.1 定义

标签翻转是最直接的数据投毒方式之一。攻击者保持样本特征不变，只故意修改部分训练样本对应的正确类别。

```text
样本特征 x：保持不变
真实标签 y：被攻击者改为错误类别 y'

(x, y) → (x, y')
```

例子：

- 猫的图片仍是原图，但标签从“猫”改成“狗”；
- 垃圾邮件正文不变，但标签从“垃圾邮件”改成“正常邮件”；
- 正面评论内容不变，但标签从“正面”改成“负面”。

### 0.2 典型攻击链

```text
攻击者获得标签写入或处理逻辑修改能力
    ↓
部分训练样本标签被翻转
    ↓
特征与类别之间出现错误对应
    ↓
模型学习错误决策边界
    ↓
准确率、精确率、召回率等指标下降
    ↓
业务系统基于错误分析作出决策
```

### 0.3 标签翻转与特征攻击的区别

| 对比项 | 标签翻转 | 特征攻击 |
|---|---|---|
| 被修改内容 | 标签 `y` | 输入特征 `X` |
| 样本本体 | 保持不变 | 被扰动或构造 |
| 最小表示 | `(x, y) → (x, y')` | `(x, y) → (x', y)` |
| 典型例子 | 猫图被标为狗 | 猫图像素被轻微修改 |
| 检测方向 | 标签与独立真值是否一致 | 特征分布、异常值和触发模式 |

两者可以组合：攻击者既修改输入特征，也为样本设置攻击目标所需的标签。

### 0.4 最常见目标

本节中的标签翻转以“可用性破坏”为主：攻击者不一定关心某一个特定输入如何分类，而是希望模型整体变得更不可靠。

可能受影响的指标包括：

- Accuracy（准确率）；
- Precision（精确率）；
- Recall（召回率）；
- F1-score；
- 混淆矩阵中的假阳性和假阴性数量。

> 标签翻转并非只能造成随机性能下降。如果攻击者有选择地翻转特定类别、群体或决策边界附近的样本，也可能实现更定向、更隐蔽的影响。

---

## 1. 标签翻转的攻击原理

### 1.1 监督学习中的标签

在监督学习中，每个训练样本通常表示为：

```text
(x_i, y_i)
```

其中：

- `x_i` 是第 `i` 个样本的特征；
- `y_i` 是该样本的正确类别或目标值；
- 模型通过大量 `(x_i, y_i)` 对学习特征与类别之间的关系。

标签是训练过程使用的“正确答案”。如果标签被蓄意修改，训练算法通常不会自动知道答案已经错误，而会努力拟合这些错误对应关系。

### 1.2 二分类中的翻转

对标签取值为 `0` 和 `1` 的二分类任务，最简单的翻转可以表示为：

```text
y'_i = 1 - y_i
```

即：

| 原标签 | 翻转后标签 |
|---|---|
| `0` | `1` |
| `1` | `0` |

只对攻击者选中的样本集合执行该操作，其他标签保持不变。

### 1.3 多分类中的翻转

多分类任务不能简单使用 `1 - y`。攻击者必须选择另一个错误类别，例如：

```text
猫 → 狗
狗 → 汽车
汽车 → 猫
```

翻转策略可能是：

- 随机选择任意其他类别；
- 将某个源类别统一翻到目标类别；
- 只修改决策边界附近的样本；
- 只攻击特定群体、设备来源或时间窗口。

### 1.4 为什么模型会“困惑”

假设同一类特征附近同时出现互相冲突的标签：

```text
相似特征区域：大多数样本标为正面
                少量相似样本被翻为负面
```

训练算法会尝试同时解释两组矛盾监督信号，可能导致：

- 决策边界向错误方向移动；
- 模型对边界附近样本更加不稳定；
- 类别概率校准变差；
- 假阳性或假阴性增加；
- 污染比例足够高时整体性能明显下降。

影响程度取决于数据可分性、模型复杂度、翻转比例、样本选择方法、正则化和评估集是否保持干净。

---

## 2. 标签可能在哪个阶段被翻转

### 2.1 存储阶段

附件重点指出，标签翻转常发生在数据收集完成之后。攻击者获得数据存储写权限，直接修改：

- AWS S3 数据湖中 CSV 或 Parquet 的标签列；
- PostgreSQL 数据库中的分类记录；
- 共享文件系统中的标注文件；
- 数据集清单、索引或类别目录结构。

这种方式可以绕过采集入口的数据校验，因为数据是在成功入库之后才被修改。

### 2.2 数据处理阶段

攻击者不一定直接编辑任何数据文件。若清洗、转换或标签生成脚本被篡改，也可以在处理时翻转标签：

```text
原始数据和标签正确
    ↓
被篡改的处理脚本
    ↓
处理后训练集中的标签错误
```

例如：

- 把情感分析的正负类别映射写反；
- 修改类别编码字典；
- 在特定日期、来源或关键词出现时翻转标签；
- 只对抽样的一部分数据执行错误转换。

此时原始数据审计可能完全正常，污染仅存在于派生数据集中。

### 2.3 标注与反馈阶段

实际系统还可能在以下位置产生标签污染：

- 标注平台账户被滥用；
- 标注指南或黄金题被篡改；
- 用户反馈被直接视为真值；
- 弱监督规则产生系统性错误标签；
- 线上点击、评分或投诉被自动转换为再训练标签。

所以标签安全不仅是“保护 CSV 某一列”，而是保护标签从生成到训练的完整生命周期。

---

## 3. 商业影响：客户评论情感分析

### 3.1 场景

某公司训练二分类模型分析新产品的客户评论：

- 类别 `0`：负面评论；
- 类别 `1`：正面评论。

攻击者随机翻转部分评论的标签：

- 将真实正面评论标为负面；
- 将真实负面评论标为正面。

攻击者的直接目标是降低最终情感模型的准确性。

### 3.2 技术影响

污染后的模型可能：

- 把正面反馈识别成负面；
- 把负面反馈识别成正面；
- 对相似评论给出不一致预测；
- 总体准确率、精确率和召回率下降；
- 错误估计市场对产品的真实态度。

### 3.3 业务影响链

```text
评论标签被翻转
    ↓
情感模型学习错误关系
    ↓
产品反馈分析失真
    ↓
管理层依赖错误指标
    ↓
提前下架成功产品 / 修复用户原本喜欢的功能 / 忽略真实问题
    ↓
收入、研发资源和市场判断受损
```

安全影响最终不只体现在模型指标上，而是体现在人和系统如何使用这些指标作出决策。

### 3.4 OWASP 风险映射

附件将标签翻转映射到 OWASP LLM 应用风险中的 Training Data Poisoning。其核心是训练数据的完整性被破坏，进而降低模型的可靠性和效用。

框架名称和编号可能随版本变化。正式审计应写明采用的 OWASP 版本，并用具体攻击链、资产和证据描述风险，而不能只记录一个编号。

---

## 4. 实验目标与设计

### 4.1 为什么使用合成数据

真实文本情感分析还需要分词、TF-IDF、嵌入或其他自然语言处理步骤。为了专注观察标签翻转机制，本实验使用 `make_blobs` 创建二维二分类数据。

可把两个维度想象成从评论文本中提取的两个数值特征：

```text
x_i = (x_i1, x_i2)
```

其中每个点代表一条评论：

- `x_i1`：Sentiment Feature 1；
- `x_i2`：Sentiment Feature 2；
- `y_i = 0`：负面情感；
- `y_i = 1`：正面情感。

### 4.2 实验流程

当前附件完成前四步：

```text
1. 导入依赖并固定随机种子        ✓
2. 生成 1000 个二维合成样本       ✓
3. 划分 70% 训练集和 30% 测试集   ✓
4. 可视化干净训练数据             ✓
5. 训练干净基线模型               ✓
6. 翻转 10%–50% 训练标签          ✓
7. 训练各污染比例模型             ✓
8. 对比 Accuracy 和决策边界       ✓
9. 对比分类报告与混淆矩阵         待后续内容
```

### 4.3 实验中的关键隔离原则

> 只污染训练集副本，测试集必须保持干净。

如果测试集标签也一起被翻转，评估结果将无法准确回答“模型在真实正确标签上退化了多少”。因此应分别保存：

```text
y_train_clean       # 原始干净训练标签
y_train_poisoned    # 被翻转的训练标签副本
y_test              # 始终保持干净的测试标签
```

---

## 5. 实验环境

### 5.1 依赖

```python
import numpy as np
import matplotlib.pyplot as plt
from sklearn.datasets import make_blobs
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import seaborn as sns
```

各依赖用途：

| 库或对象 | 用途 |
|---|---|
| NumPy | 数组、随机抽样和标签操作 |
| Matplotlib | 数据点和后续决策边界可视化 |
| `make_blobs` | 生成二维聚类数据 |
| `train_test_split` | 划分训练集与测试集 |
| `LogisticRegression` | 建立二分类基线模型 |
| `accuracy_score` | 计算准确率 |
| `classification_report` | 输出 Precision、Recall 和 F1-score |
| `confusion_matrix` | 统计分类结果 |
| Seaborn | 后续绘制混淆矩阵等图表 |

### 5.2 绘图配色与样式

```python
htb_green = "#9fef00"
node_black = "#141d2b"
hacker_grey = "#a4b1cd"
white = "#ffffff"
azure = "#0086ff"
nugget_yellow = "#ffaf00"
malware_red = "#ff3e3e"
vivid_purple = "#9f00ff"
aquamarine = "#2ee7b6"

plt.style.use("seaborn-v0_8-darkgrid")
plt.rcParams.update(
    {
        "figure.facecolor": node_black,
        "axes.facecolor": node_black,
        "axes.edgecolor": hacker_grey,
        "axes.labelcolor": white,
        "text.color": white,
        "xtick.color": hacker_grey,
        "ytick.color": hacker_grey,
        "grid.color": hacker_grey,
        "grid.alpha": 0.1,
        "legend.facecolor": node_black,
        "legend.edgecolor": hacker_grey,
        "legend.frameon": True,
        "legend.framealpha": 1.0,
        "legend.labelcolor": white,
    }
)
```

这些颜色只影响图表外观，不影响数据生成、模型训练或攻击结果。

### 5.3 固定随机种子

```python
SEED = 1337
np.random.seed(SEED)

print("Setup complete. Libraries imported and styles configured.")
```

固定随机种子便于重现：

- 相同的合成数据；
- 相同的训练/测试划分；
- 后续相同的翻转样本索引。

但实验记录仍应保存库版本，因为不同版本的实现细节可能影响最终结果。

---

## 6. 生成合成数据集

### 6.1 参数

```python
n_samples = 1000
centers = [(0, 5), (5, 0)]
```

含义：

- 总共生成 `1000` 个样本；
- 每个样本有两个特征；
- 类别 0 的聚类中心位于 `(0, 5)`；
- 类别 1 的聚类中心位于 `(5, 0)`。

两个中心相距较远，使类别相对容易分开，便于在二维图中观察翻转标签对模型的影响。

### 6.2 生成数据

```python
X, y = make_blobs(
    n_samples=n_samples,
    centers=centers,
    n_features=2,
    cluster_std=1.25,
    random_state=SEED,
)
```

关键参数：

| 参数 | 值 | 作用 |
|---|---:|---|
| `n_samples` | `1000` | 样本总数 |
| `centers` | `[(0, 5), (5, 0)]` | 两个类别中心 |
| `n_features` | `2` | 每个样本的特征数 |
| `cluster_std` | `1.25` | 聚类离散程度 |
| `random_state` | `1337` | 保证生成过程可复现 |

输出形状应为：

```text
X.shape == (1000, 2)
y.shape == (1000,)
```

### 6.3 划分训练集和测试集

```python
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.3,
    random_state=SEED,
)
```

划分结果：

| 数据 | 样本数 | 比例 |
|---|---:|---:|
| 训练集 | 700 | 70% |
| 测试集 | 300 | 30% |
| 总计 | 1000 | 100% |

### 6.4 输出数据摘要

```python
print(f"Generated {n_samples} samples.")
print(f"Training set size: {X_train.shape[0]} samples.")
print(f"Testing set size: {X_test.shape[0]} samples.")
print(f"Number of features: {X_train.shape[1]}")
print(f"Classes: {np.unique(y)}")
```

预期输出：

```text
Generated 1000 samples.
Training set size: 700 samples.
Testing set size: 300 samples.
Number of features: 2
Classes: [0 1]
```

### 6.5 关于分层划分

附件原始代码没有传入 `stratify=y`。由于 `make_blobs` 在该设置下生成的两类通常较均衡，固定随机种子后仍可用于演示。

更一般的分类实验中，建议使用：

```python
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.3,
    random_state=SEED,
    stratify=y,
)
```

这样可使训练集和测试集保持接近原数据的类别比例，避免划分本身造成类别失衡。

---

## 7. 可视化干净训练数据

### 7.1 绘图函数

```python
def plot_data(X, y, title="Dataset Visualization"):
    """绘制二维分类数据集。"""
    plt.figure(figsize=(12, 6))
    plt.scatter(
        X[:, 0],
        X[:, 1],
        c=y,
        cmap=plt.cm.colors.ListedColormap([azure, nugget_yellow]),
        edgecolors=node_black,
        s=50,
        alpha=0.8,
    )
    plt.title(title, fontsize=16, color=htb_green)
    plt.xlabel("Sentiment Feature 1", fontsize=12)
    plt.ylabel("Sentiment Feature 2", fontsize=12)

    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label="Negative Sentiment (Class 0)",
            markersize=10,
            markerfacecolor=azure,
        ),
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label="Positive Sentiment (Class 1)",
            markersize=10,
            markerfacecolor=nugget_yellow,
        ),
    ]
    plt.legend(handles=handles, title="Sentiment Classes")
    plt.grid(True, color=hacker_grey, linestyle="--", linewidth=0.5, alpha=0.3)
    plt.show()
```

### 7.2 调用

```python
plot_data(
    X_train,
    y_train,
    title="Original Training Data Distribution",
)
```

### 7.3 图像应该如何解读

图中应出现两个明显聚类：

- 蓝色：Class 0，模拟负面评论；
- 橙色：Class 1，模拟正面评论。

横轴和纵轴是两个抽象的情感特征。它们不是具体词频，也不代表真实业务指标，只是为了将分类问题压缩到可以直接观察的二维空间。

干净数据中，大部分点的颜色应与所在聚类一致。后续翻转标签后，部分点的位置不变但颜色会变化，这正好直观体现：

```text
特征位置没有改变，类别标记改变了。
```

---

## 8. 基线逻辑回归模型

### 8.1 为什么先建立基线

执行标签翻转前，必须先在原始干净训练集 `(X_train, y_train)` 上训练模型，并在未见过的干净测试集 `(X_test, y_test)` 上评估。

基线用于回答：

- 数据未被污染时模型应达到什么性能；
- 标签翻转后准确率下降了多少；
- 决策边界发生了怎样的移动；
- 观察到的差异是否明显超出正常训练波动。

```text
干净训练集 → 基线模型 → 干净测试集 → Baseline Metrics
污染训练集 → 污染模型 → 同一干净测试集 → Poisoned Metrics
                                          ↓
                                  公平比较两组结果
```

两组模型必须使用同一个测试集和一致的训练配置，才能把主要差异归因于训练标签污染。

### 8.2 Logistic Regression 是分类算法

虽然名称中包含 Regression，Logistic Regression 通常用于分类。本实验是二分类：

- `y = 0`：Negative Sentiment；
- `y = 1`：Positive Sentiment。

对于一条由二维特征表示的评论：

$$
\mathbf{x}_i = (x_{i1}, x_{i2})
$$

模型首先计算特征的线性组合：

$$
z_i = \mathbf{w}^{T}\mathbf{x}_i + b
    = w_1x_{i1} + w_2x_{i2} + b
$$

其中：

- $\mathbf{w} = (w_1, w_2)$ 是两个特征的权重；
- $b$ 是偏置项；
- $z_i$ 是 logit，即样本属于正类的对数几率。

### 8.3 Logit 与概率

若：

$$
p_i = P(y_i = 1 \mid \mathbf{x}_i)
$$

则 logit 为：

$$
z_i = \log\left(\frac{p_i}{1-p_i}\right)
$$

模型通过 Sigmoid 函数把任意实数 $z_i$ 转换到 $[0,1]$：

$$
p_i = \sigma(z_i)
    = \frac{1}{1+e^{-z_i}}
    = \frac{1}{1+e^{-(\mathbf{w}^{T}\mathbf{x}_i+b)}}
$$

输出 $p_i$ 表示模型估计该评论属于正面类别的概率。

### 8.4 分类阈值

默认阈值通常为 `0.5`：

$$
\hat{y}_i =
\begin{cases}
1, & p_i \ge 0.5 \\
0, & p_i < 0.5
\end{cases}
$$

即：

```text
p ≥ 0.5 → 预测为正面（Class 1）
p < 0.5 → 预测为负面（Class 0）
```

阈值并不是永远必须为 `0.5`。真实系统可能根据假阳性、假阴性的业务成本调整阈值；本实验使用默认行为，便于聚焦标签翻转造成的变化。

### 8.5 二元交叉熵损失

训练时，模型通过最小化 Binary Cross-Entropy（也称 Log Loss）学习参数 $\mathbf{w}$ 和 $b$：

$$
L(\mathbf{w}, b)
= -\frac{1}{N}\sum_{i=1}^{N}
\left[
y_i\log(p_i) + (1-y_i)\log(1-p_i)
\right]
$$

其中：

- $N$ 是训练样本数量；
- $y_i$ 是真实标签 `0` 或 `1`；
- $p_i$ 是模型预测为正类的概率。

标签翻转将 $y_i$ 改为错误值。对同一个特征向量，损失函数会推动参数朝相反方向调整：

```text
干净标签 y_i：要求模型提高正确类别概率
翻转标签 y'_i：要求模型降低原正确类别概率
```

这正是标签污染影响决策边界的数学原因。

### 8.6 决策边界

模型在 $p=0.5$ 时正好处于分类临界点。因为 $\sigma(0)=0.5$，所以二维决策边界满足：

$$
\mathbf{w}^{T}\mathbf{x} + b = 0
$$

展开后：

$$
w_1x_1 + w_2x_2 + b = 0
$$

若 $w_2 \ne 0$，可写成直线：

$$
x_2 = -\frac{w_1}{w_2}x_1 - \frac{b}{w_2}
$$

因此，在当前二维实验中，Logistic Regression 学到一条直线，将预测为负面和正面的两个区域分开。

### 8.7 训练干净基线模型

```python
# Initialize and train the Logistic Regression model
baseline_model = LogisticRegression(random_state=SEED)
baseline_model.fit(X_train, y_train)

# Predict on the clean, unseen test set
y_pred_baseline = baseline_model.predict(X_test)

# Calculate baseline accuracy
baseline_accuracy = accuracy_score(y_test, y_pred_baseline)
print(f"Baseline Model Accuracy: {baseline_accuracy:.4f}")
```

附件给出的输出为：

```text
Baseline Model Accuracy: 0.9933
```

测试集有 300 个样本，因此 `0.9933` 对应约 298 个预测正确、2 个预测错误。这里的整数换算由四位小数反推，精确数量仍应以实际 `confusion_matrix` 输出为准。

### 8.8 基线准确率如何解读

基线准确率约为 `99.33%`，说明：

- 两个合成聚类高度可分；
- 线性决策边界适合当前数据；
- 模型能很好地泛化到未参与训练的测试样本；
- 后续有清晰的高性能参照，可观察标签翻转造成的退化。

高基线准确率不表示真实情感分析通常能达到相同结果。本实验的数据是专门构造的二维高可分聚类，目标是清楚展示攻击机制，而不是模拟真实文本任务的全部难度。

### 8.9 决策边界绘图函数

```python
def plot_decision_boundary(model, X, y, title="Decision Boundary"):
    """
    Plots the decision boundary of a trained classifier on a 2D dataset.

    Parameters:
    - model: trained classifier with a .predict method
    - X: feature data with shape (n_samples, 2)
    - y: labels with shape (n_samples,)
    - title: plot title
    """
    h = 0.02
    x_min, x_max = X[:, 0].min() - 1, X[:, 0].max() + 1
    y_min, y_max = X[:, 1].min() - 1, X[:, 1].max() + 1
    xx, yy = np.meshgrid(
        np.arange(x_min, x_max, h),
        np.arange(y_min, y_max, h),
    )

    # Predict the class for every point in the mesh
    Z = model.predict(np.c_[xx.ravel(), yy.ravel()])
    Z = Z.reshape(xx.shape)

    plt.figure(figsize=(12, 6))
    plt.contourf(
        xx,
        yy,
        Z,
        cmap=plt.cm.colors.ListedColormap([azure, nugget_yellow]),
        alpha=0.3,
    )

    plt.scatter(
        X[:, 0],
        X[:, 1],
        c=y,
        cmap=plt.cm.colors.ListedColormap([azure, nugget_yellow]),
        edgecolors=node_black,
        s=50,
        alpha=0.8,
    )

    plt.title(title, fontsize=16, color=htb_green)
    plt.xlabel("Feature 1", fontsize=12)
    plt.ylabel("Feature 2", fontsize=12)

    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label="Negative Sentiment (Class 0)",
            markersize=10,
            markerfacecolor=azure,
        ),
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label="Positive Sentiment (Class 1)",
            markersize=10,
            markerfacecolor=nugget_yellow,
        ),
    ]
    plt.legend(handles=handles, title="Classes")
    plt.grid(True, color=hacker_grey, linestyle="--", linewidth=0.5, alpha=0.3)
    plt.xlim(xx.min(), xx.max())
    plt.ylim(yy.min(), yy.max())
    plt.show()
```

### 8.10 绘制基线边界

```python
plot_decision_boundary(
    baseline_model,
    X_train,
    y_train,
    title=f"Baseline Model Decision Boundary\nAccuracy: {baseline_accuracy:.4f}",
)
```

图中：

- 背景颜色表示模型对网格中每个位置的预测类别；
- 蓝色点代表训练集中的负面评论；
- 橙色点代表训练集中的正面评论；
- 两种背景颜色的交界位置就是模型决策边界。

附件结果显示，该直线能够有效分开两个情感聚类，与 `0.9933` 的高测试准确率一致。

### 8.11 绘图实现注意事项

函数使用 `h = 0.02` 创建密集网格。步长越小，边界图越平滑，但预测点数量和内存、计算开销越大。若特征范围很大，应适当增大 `h`。

当前绘图把训练标签显示在边界上，适合观察模型如何拟合训练数据。评估泛化时仍应使用测试集指标；训练图看起来分得很好，不能替代测试集验证。

---

## 9. 评估标签翻转攻击

### 9.1 实验问题

本阶段系统性回答：

```text
当训练标签的随机翻转比例从 0% 增加到 50% 时，
模型在原始干净测试集上的准确率和决策边界如何变化？
```

实验保持以下变量不变：

- 特征始终使用原始 `X_train`；
- 模型始终使用 `LogisticRegression(random_state=SEED)`；
- 评估始终使用干净的 `X_test` 和 `y_test`；
- 只改变训练标签 `y_train_poisoned`；
- 污染比例依次为 `10%`、`20%`、`30%`、`40%`、`50%`。

这是一个受控变量实验。若同时修改测试标签、特征或模型配置，就无法把结果差异清晰归因于标签翻转。

### 9.2 前置函数接口

附件本段直接调用了 `flip_labels` 和 `plot_poisoned_data`，但没有再次给出它们的定义。为了让笔记中的代码可以独立理解，下面给出与调用方式兼容的二分类实现。

```python
def flip_labels(y, percentage, rng=None):
    """随机选择指定比例的二分类标签，并执行 0 ↔ 1 翻转。"""
    if not 0 <= percentage <= 1:
        raise ValueError("percentage must be between 0 and 1")

    unique_labels = np.unique(y)
    if not np.array_equal(unique_labels, np.array([0, 1])):
        raise ValueError("This implementation expects binary labels {0, 1}")

    if rng is None:
        rng = np.random.default_rng(SEED)

    y_poisoned = y.copy()
    n_flipped = int(len(y_poisoned) * percentage)
    flipped_indices = rng.choice(
        len(y_poisoned),
        size=n_flipped,
        replace=False,
    )
    y_poisoned[flipped_indices] = 1 - y_poisoned[flipped_indices]
    return y_poisoned, flipped_indices
```

如果课程前文已经定义了这两个函数，应继续使用原定义，以保持课程结果一致。上面的实现使用 `default_rng`，其随机序列不一定与附件原实现相同，因此不能保证复现附件中的每条边界。

可视化兼容实现：

```python
def plot_poisoned_data(
    X,
    y_clean,
    y_poisoned,
    flipped_indices,
    title="Poisoned Training Data",
):
    mask_not_flipped = np.ones(len(y_clean), dtype=bool)
    mask_not_flipped[flipped_indices] = False

    plt.figure(figsize=(12, 6))
    plt.scatter(
        X[mask_not_flipped, 0],
        X[mask_not_flipped, 1],
        c=y_poisoned[mask_not_flipped],
        cmap=plt.cm.colors.ListedColormap([azure, nugget_yellow]),
        edgecolors=node_black,
        s=50,
        alpha=0.7,
        label="Unchanged Label",
    )

    if len(flipped_indices) > 0:
        plt.scatter(
            X[flipped_indices, 0],
            X[flipped_indices, 1],
            c=y_poisoned[flipped_indices],
            cmap=plt.cm.colors.ListedColormap([azure, nugget_yellow]),
            edgecolors=malware_red,
            linewidths=1.5,
            marker="X",
            s=100,
            alpha=0.9,
            label="Flipped Label",
        )

    plt.title(title, fontsize=16, color=htb_green)
    plt.xlabel("Sentiment Feature 1", fontsize=12)
    plt.ylabel("Sentiment Feature 2", fontsize=12)
    plt.legend()
    plt.grid(True, color=hacker_grey, linestyle="--", linewidth=0.5, alpha=0.3)
    plt.show()
```

### 9.3 结果容器

先建立统一结构，保存每个污染比例对应的指标、模型、标签和翻转索引：

```python
results = {
    "percentage": [],
    "accuracy": [],
    "model": [],
    "y_train_poisoned": [],
    "flipped_indices": [],
}

decision_boundaries_data = []
```

加入 `0%` 干净基线：

```python
results["percentage"].append(0.0)
results["accuracy"].append(baseline_accuracy)
results["model"].append(baseline_model)
results["y_train_poisoned"].append(y_train.copy())
results["flipped_indices"].append(np.array([], dtype=int))
```

这里保存 `y_train.copy()` 很重要，避免结果容器持有一个之后可能被原地修改的标签数组引用。

### 9.4 统一决策网格

所有边界图使用同一个二维网格：

```python
h = 0.02
x_min, x_max = X_train[:, 0].min() - 1, X_train[:, 0].max() + 1
y_min, y_max = X_train[:, 1].min() - 1, X_train[:, 1].max() + 1

xx, yy = np.meshgrid(
    np.arange(x_min, x_max, h),
    np.arange(y_min, y_max, h),
)
mesh_points = np.c_[xx.ravel(), yy.ravel()]
```

统一网格能让不同模型的边界在相同坐标范围和分辨率下叠加比较。

---

### 9.5 执行 10% 标签翻转

训练集有 700 个样本。若 `flip_labels` 使用 `int(700 × 0.10)`，10% 对应翻转 70 个训练标签。

```python
poison_percentage_10 = 0.10
print(
    f"\n--- Testing with {poison_percentage_10 * 100:.0f}% "
    "Poisoned Data ---"
)

y_train_poisoned_10, flipped_indices_10 = flip_labels(
    y_train,
    poison_percentage_10,
)
```

关键不变量应立即验证：

```python
assert np.array_equal(X_train, X_train_clean)
assert np.array_equal(y_train, y_train_clean)
assert len(flipped_indices_10) == int(len(y_train) * 0.10)
assert np.all(
    y_train_poisoned_10[flipped_indices_10]
    == 1 - y_train[flipped_indices_10]
)
```

因此应在首次投毒前保存 `X_train_clean = X_train.copy()` 和 `y_train_clean = y_train.copy()`。

### 9.6 可视化 10% 污染训练集

```python
plot_poisoned_data(
    X_train,
    y_train,
    y_train_poisoned_10,
    flipped_indices_10,
    title="Training Data with 10% Flipped Labels",
)
```

图中翻转点使用红色边框的 `X` 标记。点的位置没有移动，但颜色按新标签显示，因此可以直观看到：特征未变，监督信号被反转。

### 9.7 训练并评估 10% 污染模型

```python
model_10_percent = LogisticRegression(random_state=SEED)
model_10_percent.fit(X_train, y_train_poisoned_10)

y_pred_10_percent = model_10_percent.predict(X_test)
accuracy_10_percent = accuracy_score(y_test, y_pred_10_percent)

print(
    "Accuracy on clean test set (10% poisoned): "
    f"{accuracy_10_percent:.4f}"
)
```

注意评估目标仍然是原始 `y_test`：

```text
训练：X_train + y_train_poisoned_10
评估：X_test  + y_test（干净真值）
```

附件报告结果：

```text
Baseline Accuracy:              0.9933
Accuracy with 10% Poisoning:    0.9933
Observed Accuracy Difference:   0.0000
```

10% 随机翻转没有改变测试集上的离散分类正确数，但不能据此断言模型完全没有变化。

### 9.8 保存 10% 结果

```python
results["percentage"].append(poison_percentage_10)
results["accuracy"].append(accuracy_10_percent)
results["model"].append(model_10_percent)
results["y_train_poisoned"].append(y_train_poisoned_10)
results["flipped_indices"].append(flipped_indices_10)
```

绘制污染模型边界：

```python
plot_decision_boundary(
    model_10_percent,
    X_train,
    y_train_poisoned_10,
    title=(
        "Decision Boundary (10% Poisoned)\n"
        f"Accuracy: {accuracy_10_percent:.4f}"
    ),
)
```

保存网格预测供后续叠加：

```python
Z_10 = model_10_percent.predict(mesh_points).reshape(xx.shape)
decision_boundaries_data.append(
    {"percentage": poison_percentage_10, "Z": Z_10}
)

print(f"Baseline accuracy was: {baseline_accuracy:.4f}")
```

---

## 10. 叠加比较 0% 与 10% 决策边界

### 10.1 为什么 Accuracy 相同仍要看边界

Accuracy 只统计最终类别是否正确。如果两个模型对所有 300 个测试样本给出相同的类别，它们的 Accuracy 就相同；但以下内部状态仍可能变化：

- 权重 `coef_`；
- 偏置 `intercept_`；
- 预测概率；
- Log Loss；
- 样本到决策边界的距离；
- 决策边界在没有测试点覆盖区域的位置。

因此：

> Accuracy 不变只表示当前测试样本没有跨过分类边界，不表示模型参数、置信度或安全裕量没有变化。

### 10.2 绘制数据点

```python
plt.figure(figsize=(12, 8))

mask_not_flipped_10 = np.ones(len(y_train), dtype=bool)
mask_not_flipped_10[flipped_indices_10] = False

plt.scatter(
    X_train[mask_not_flipped_10, 0],
    X_train[mask_not_flipped_10, 1],
    c=y_train_poisoned_10[mask_not_flipped_10],
    cmap=plt.cm.colors.ListedColormap([azure, nugget_yellow]),
    edgecolors=node_black,
    s=50,
    alpha=0.6,
    label="Original Label (in 10% set)",
)

if len(flipped_indices_10) > 0:
    plt.scatter(
        X_train[flipped_indices_10, 0],
        X_train[flipped_indices_10, 1],
        c=y_train_poisoned_10[flipped_indices_10],
        cmap=plt.cm.colors.ListedColormap([azure, nugget_yellow]),
        edgecolors=malware_red,
        linewidths=1.5,
        marker="X",
        s=100,
        alpha=0.9,
        label="Flipped Label (10% set)",
    )
```

### 10.3 叠加两条边界

```python
baseline_model_retrieved = results["model"][
    results["percentage"].index(0.0)
]

if baseline_model_retrieved is not None:
    Z_baseline = baseline_model_retrieved.predict(mesh_points).reshape(xx.shape)
    plt.contour(
        xx,
        yy,
        Z_baseline,
        levels=[0.5],
        colors=[htb_green],
        linestyles=["solid"],
        linewidths=[2.5],
    )

plt.contour(
    xx,
    yy,
    Z_10,
    levels=[0.5],
    colors=[aquamarine],
    linestyles=["dashed"],
    linewidths=[2.5],
)
```

这里的 `Z` 是 `model.predict()` 生成的 `0/1` 类别网格，在 `0.5` 等值线上绘制两类区域的交界。若希望比较概率边界和置信度，建议改用：

```python
P = model.predict_proba(mesh_points)[:, 1].reshape(xx.shape)
plt.contour(xx, yy, P, levels=[0.1, 0.5, 0.9])
```

### 10.4 标题与图例

```python
plt.title(
    "Comparison: Baseline vs. 10% Poisoned Decision Boundary",
    fontsize=16,
    color=htb_green,
)
plt.xlabel("Feature 1", fontsize=12)
plt.ylabel("Feature 2", fontsize=12)

handles = [
    plt.Line2D(
        [0], [0],
        color=htb_green,
        lw=2.5,
        linestyle="solid",
        label="Baseline Boundary (0%)",
    ),
    plt.Line2D(
        [0], [0],
        color=aquamarine,
        lw=2.5,
        linestyle="dashed",
        label="Poisoned Boundary (10%)",
    ),
    plt.Line2D(
        [0], [0],
        marker="o",
        color="w",
        label="Class 0 Point",
        markersize=10,
        markerfacecolor=azure,
        linestyle="None",
    ),
    plt.Line2D(
        [0], [0],
        marker="o",
        color="w",
        label="Class 1 Point",
        markersize=10,
        markerfacecolor=nugget_yellow,
        linestyle="None",
    ),
    plt.Line2D(
        [0], [0],
        marker="X",
        color="w",
        label="Flipped Point",
        markersize=10,
        markeredgecolor=malware_red,
        markerfacecolor=hacker_grey,
        linestyle="None",
    ),
]

plt.legend(handles=handles, title="Boundaries & Data Points")
plt.grid(True, color=hacker_grey, linestyle="--", linewidth=0.5, alpha=0.3)
plt.xlim(xx.min(), xx.max())
plt.ylim(yy.min(), yy.max())
plt.show()
```

附件的叠加图显示 10% 污染边界相对基线发生轻微偏移，虽然测试 Accuracy 仍为 `0.9933`。

---

## 11. 系统测试 20%–50% 污染

### 11.1 循环训练

```python
poison_percentages_high = [0.20, 0.30, 0.40, 0.50]

for pp in poison_percentages_high:
    print(f"\n--- Training with {pp * 100:.0f}% Poisoned Data ---")

    y_train_poisoned, flipped_idx = flip_labels(y_train, pp)

    poisoned_model = LogisticRegression(random_state=SEED)
    try:
        poisoned_model.fit(X_train, y_train_poisoned)
    except Exception as exc:
        print(f"Error training model at {pp * 100:.0f}% poisoning: {exc}")
        results["percentage"].append(pp)
        results["accuracy"].append(np.nan)
        results["model"].append(None)
        results["y_train_poisoned"].append(y_train_poisoned)
        results["flipped_indices"].append(flipped_idx)
        continue

    y_pred_poisoned = poisoned_model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred_poisoned)
    print(f"Accuracy on clean test set: {accuracy:.4f}")

    results["percentage"].append(pp)
    results["accuracy"].append(accuracy)
    results["model"].append(poisoned_model)
    results["y_train_poisoned"].append(y_train_poisoned)
    results["flipped_indices"].append(flipped_idx)

    plot_poisoned_data(
        X_train,
        y_train,
        y_train_poisoned,
        flipped_idx,
        title=f"Training Data with {pp * 100:.0f}% Flipped Labels",
    )

    plot_decision_boundary(
        poisoned_model,
        X_train,
        y_train_poisoned,
        title=(
            f"Decision Boundary ({pp * 100:.0f}% Poisoned)\n"
            f"Accuracy: {accuracy:.4f}"
        ),
    )

    Z = poisoned_model.predict(mesh_points).reshape(xx.shape)
    decision_boundaries_data.append({"percentage": pp, "Z": Z})

print("\n--- Evaluation Complete for Higher Percentages ---")
```

### 11.2 预期翻转数量

若训练集为 700，且函数使用 `int(len(y) * percentage)`：

| 污染比例 | 翻转标签数 |
|---:|---:|
| 10% | 70 |
| 20% | 140 |
| 30% | 210 |
| 40% | 280 |
| 50% | 350 |

这些是按比例计算的预期数量，最终仍应使用 `len(flipped_idx)` 验证实际值。

### 11.3 附件报告的结果

| 训练标签污染比例 | 干净测试集 Accuracy | 附件中的观察 |
|---:|---:|---|
| 0% | `0.9933` | 干净基线 |
| 10% | `0.9933` | 准确率未下降，边界轻微移动 |
| 20% | `0.9933` | 准确率未下降，边界继续变化 |
| 30% | 未给出精确值 | 仍未出现显著准确率损失 |
| 40% | 未给出精确值 | 仍未出现显著准确率损失 |
| 50% | 未给出精确值 | 趋势图显示准确率下降 |

必须区分“附件明确给出的数字”和“图文描述的趋势”。不能从图像外观猜测 30%、40% 或 50% 的精确小数。

### 11.4 为什么高比例翻转仍可能保持高 Accuracy

当前数据的两个聚类距离较远，且随机翻转是近似对称噪声。对污染率 $\eta < 0.5$，每个特征区域中正确标签在期望上仍占多数：

$$
P(\tilde{y}=y)=1-\eta > 0.5
$$

因此分类方向可能仍然正确。模型参数、概率和边界会变化，但大部分测试点距离边界足够远，尚未跨到另一侧。

当 $\eta=0.5$ 时，随机对称翻转在期望上使标签与原类别失去关联：

$$
P(\tilde{y}=y)=P(\tilde{y}\ne y)=0.5
$$

有限样本下，模型可能由随机不平衡决定方向，Accuracy 会大幅波动。一次 50% 实验的结果不应被当成稳定阈值。

### 11.5 独立抽样与嵌套抽样

若每次调用 `flip_labels(y_train, pp)` 都重新随机选取索引，则 20% 污染集不一定包含 10% 污染集，30% 也不一定包含前面的样本。这些是不同随机攻击实例：

```text
10% 集合：随机样本 A
20% 集合：随机样本 B（不一定包含 A）
30% 集合：随机样本 C（不一定包含 A 或 B）
```

这样仍可观察不同噪声率，但边界变化不一定严格单调。若目标是展示同一攻击逐步累积，应先生成一个固定随机排列，再取其前 `10%`、`20%`……作为嵌套集合：

```python
rng = np.random.default_rng(SEED)
flip_order = rng.permutation(len(y_train))

def flip_labels_nested(y, percentage, flip_order):
    y_poisoned = y.copy()
    n_flipped = int(len(y) * percentage)
    flipped_indices = flip_order[:n_flipped]
    y_poisoned[flipped_indices] = 1 - y_poisoned[flipped_indices]
    return y_poisoned, flipped_indices
```

实验报告必须说明使用独立抽样还是嵌套抽样。

---

## 12. 绘制 Accuracy—污染比例趋势

### 12.1 代码

```python
plt.figure(figsize=(8, 5))

plot_data = sorted(zip(results["percentage"], results["accuracy"]))
plot_percentages = [percentage * 100 for percentage, accuracy in plot_data]
plot_accuracies = [accuracy for percentage, accuracy in plot_data]

plt.plot(
    plot_percentages,
    plot_accuracies,
    marker="o",
    linestyle="-",
    color=htb_green,
    markersize=8,
)
plt.title(
    "Model Accuracy vs. Label Flipping Percentage",
    fontsize=16,
    color=htb_green,
)
plt.xlabel("Percentage of Training Labels Flipped (%)", fontsize=12)
plt.ylabel("Accuracy on Clean Test Set", fontsize=12)
plt.xticks(plot_percentages)
plt.ylim(0, 1.05)
plt.grid(True, color=hacker_grey, linestyle="--", linewidth=0.5, alpha=0.3)
plt.show()
```

### 12.2 结果解读

附件趋势图显示 Accuracy 在 0%–40% 区间保持很高，到 50% 时下降。这一结果只适用于当前：

- 高度可分的二维合成数据；
- 随机、近似对称的标签翻转；
- 当前随机样本和 Logistic Regression 配置；
- 仅以 Accuracy 衡量离散预测。

真实评论特征通常更高维、更重叠，并包含类别不平衡、自然标签噪声和分布漂移。轻微边界变化就可能让大量边界附近样本分类改变，因此不能由本实验得出“低于 50% 投毒无影响”。

### 12.3 应补充的敏感指标

即使 Accuracy 不变，也应比较：

```python
from sklearn.metrics import log_loss

baseline_prob = baseline_model.predict_proba(X_test)[:, 1]
poisoned_prob = model_10_percent.predict_proba(X_test)[:, 1]

print("Baseline log loss:", log_loss(y_test, baseline_prob))
print("Poisoned log loss:", log_loss(y_test, poisoned_prob))
print("Baseline coefficients:", baseline_model.coef_)
print("Poisoned coefficients:", model_10_percent.coef_)
print("Baseline intercept:", baseline_model.intercept_)
print("Poisoned intercept:", model_10_percent.intercept_)
```

还应记录分类报告、混淆矩阵、ROC-AUC、PR-AUC、Brier Score 和校准曲线。类别不平衡时，Accuracy 尤其容易掩盖单一类别性能退化。

---

## 13. 叠加 0%–50% 所有决策边界

### 13.1 样式映射

```python
contour_colors = {
    0.0: htb_green,
    0.10: aquamarine,
    0.20: nugget_yellow,
    0.30: vivid_purple,
    0.40: azure,
    0.50: malware_red,
}

contour_linestyles = {
    0.0: "solid",
    0.10: "dashed",
    0.20: "dashed",
    0.30: "dashed",
    0.40: "dashed",
    0.50: "dashed",
}
```

### 13.2 绘制干净数据与基线

```python
plt.figure(figsize=(12, 8))

plt.scatter(
    X_train[:, 0],
    X_train[:, 1],
    c=y_train,
    cmap=plt.cm.colors.ListedColormap([azure, nugget_yellow]),
    edgecolors=node_black,
    s=50,
    alpha=0.5,
    label="Clean Data Points",
)

baseline_model_idx = results["percentage"].index(0.0)
baseline_model_retrieved = results["model"][baseline_model_idx]

if baseline_model_retrieved is not None:
    Z_baseline = baseline_model_retrieved.predict(mesh_points).reshape(xx.shape)
    plt.contour(
        xx,
        yy,
        Z_baseline,
        levels=[0.5],
        colors=[contour_colors[0.0]],
        linestyles=[contour_linestyles[0.0]],
        linewidths=[2.5],
    )
```

### 13.3 叠加污染边界

```python
boundary_indices_to_plot = [0.10, 0.20, 0.30, 0.40, 0.50]
plotted_percentages = [0.0]

decision_boundaries_data.sort(key=lambda item: item["percentage"])

for data in decision_boundaries_data:
    pp = data["percentage"]
    if pp in boundary_indices_to_plot:
        if pp in contour_colors and pp in contour_linestyles:
            plt.contour(
                xx,
                yy,
                data["Z"],
                levels=[0.5],
                colors=[contour_colors[pp]],
                linestyles=[contour_linestyles[pp]],
                linewidths=[2.5],
            )
            plotted_percentages.append(pp)
        else:
            print(
                f"Warning: Style not defined for {pp * 100:.0f}%, "
                "skipping contour."
            )
```

### 13.4 图例与输出

```python
plt.title(
    "Shift in Decision Boundary with Increasing Label Flipping",
    fontsize=16,
    color=htb_green,
)
plt.xlabel("Feature 1", fontsize=12)
plt.ylabel("Feature 2", fontsize=12)

legend_handles = []
for pp in sorted(plotted_percentages):
    if pp in contour_colors and pp in contour_linestyles:
        legend_handles.append(
            plt.Line2D(
                [0], [0],
                color=contour_colors[pp],
                lw=2.5,
                linestyle=contour_linestyles[pp],
                label=f"Boundary ({pp * 100:.0f}% Poisoned)",
            )
        )

data_handles = [
    plt.Line2D(
        [0], [0],
        marker="o",
        color="w",
        label="Class 0",
        markersize=10,
        markerfacecolor=azure,
        linestyle="None",
    ),
    plt.Line2D(
        [0], [0],
        marker="o",
        color="w",
        label="Class 1",
        markersize=10,
        markerfacecolor=nugget_yellow,
        linestyle="None",
    ),
]

plt.legend(handles=legend_handles + data_handles, title="Boundaries & Data")
plt.grid(True, color=hacker_grey, linestyle="--", linewidth=0.5, alpha=0.3)
plt.xlim(xx.min(), xx.max())
plt.ylim(yy.min(), yy.max())
plt.show()
```

### 13.5 总体观察

附件叠加图显示，随着错误标签比例增加，模型为了适应相互矛盾的监督信号，学到的边界持续发生变化。边界变化先于 Accuracy 明显下降出现，因此它是一个更敏感的模型变化证据。

不过“边界越来越扭曲”需要结合抽样方式理解：如果每个比例独立抽取不同样本，图中既包含污染比例的影响，也包含翻转样本位置不同造成的随机差异。更严谨的结论需要多随机种子重复实验，并报告均值和置信区间。

---

## 14. 实验完整性检查

在首次翻转前记录以下信息：

```python
print("X_train shape:", X_train.shape)
print("X_test shape:", X_test.shape)
print("Train class counts:", np.bincount(y_train))
print("Test class counts:", np.bincount(y_test))
print("First five labels:", y_train[:5])
```

同时保留干净特征和标签副本：

```python
X_train_clean = X_train.copy()
y_train_clean = y_train.copy()
```

检查清单：

```text
[ ] 样本数为 1000
[ ] 训练集为 700，测试集为 300
[ ] 每个样本有两个特征
[ ] 标签只包含 0 和 1
[ ] 两个聚类在图中明显可分
[ ] 已保存 X_train_clean 和 y_train_clean
[ ] 只修改每个实验各自的训练标签副本
[ ] 测试集 X_test、y_test 保持不变
[ ] 所有污染模型在同一干净测试集上评估
[ ] 每个污染比例的翻转索引和实际数量均已记录
[ ] 已说明各比例使用独立抽样还是嵌套抽样
```

---

## 15. 进一步实验应重点回答的问题

### 15.1 翻转比例

当前已比较 0%、10%–50%。进一步实验可以增加更细粒度的低污染比例，例如：

```text
0%   → 干净基线
5%   → 轻度污染
10%  → 与当前结果衔接
```

这些比例只用于隔离实验，不代表现实攻击阈值。攻击效果会随数据集、模型和样本选择方法变化。

### 15.2 随机翻转与定向翻转

应区分：

| 策略 | 方法 | 可能影响 |
|---|---|---|
| 随机双向翻转 | 随机选择样本，将 0↔1 | 常用于观察整体性能退化 |
| 单向翻转 | 只将 0→1 或 1→0 | 定向增加某类假阳性或假阴性 |
| 边界样本翻转 | 选择最靠近决策边界的样本 | 可能以较少污染产生更大影响 |
| 来源定向翻转 | 只攻击某设备、地区或群体 | 形成局部偏置，整体指标可能正常 |

### 15.3 应比较的指标

- 干净与污染模型的 Accuracy；
- 每个类别的 Precision、Recall 和 F1-score；
- 混淆矩阵；
- 决策边界位置；
- 不同污染比例的性能曲线；
- 多个随机种子下的均值和波动。

### 15.4 需要避免的实验错误

- 在原数组上修改标签却没有保留干净副本；
- 同时污染训练集和测试集；
- 只比较训练准确率；
- 没有固定或记录随机种子；
- 只运行一次就把随机波动当成攻击效果；
- 类别不平衡时只看 Accuracy；
- 把二维合成实验的数值直接推广到真实情感系统。

---

## 16. 初步检测与防御思路

### 16.1 标签来源与权限

- 记录标签由哪个主体、规则或系统产生；
- 分离原始数据写权限和标签修改权限；
- 对批量标签修改使用审批、版本和审计日志；
- 限制数据处理任务覆盖历史标签；
- 对高影响数据使用双人复核或独立证据。

### 16.2 数据一致性

- 比较标签与规则、元数据或独立模型的矛盾；
- 检查近重复样本是否拥有冲突标签；
- 查找同一时间、账户或处理批次的大量标签变化；
- 监控类别比例和翻转率的时间变化；
- 对决策边界附近的高损失样本进行复核。

### 16.3 数据与处理代码版本

- 保留不可变原始标签；
- 为派生数据集记录输入版本、代码版本和输出哈希；
- 对标签映射函数建立单元测试和黄金样本；
- 训练前比较当前标签与最后批准版本；
- 确保异常标签可以定位、移除并重新训练。

### 16.4 模型侧检查

- 使用独立、干净的验证集；
- 同时检查总体和分群指标；
- 分析高损失、低置信度和预测冲突样本；
- 通过多次训练确认性能下降不是随机波动；
- 新模型必须与最后已知安全基线比较。

---

## 17. 本节实验记录模板

> 通用字段、证据要求和安全约束见：[AI 安全测试通用记录模板](../_模板/测试记录-通用.md)。下方保留本主题的专用字段。

```text
实验名称：Label Flipping
时间：
环境：
Python 版本：
NumPy 版本：
scikit-learn 版本：
随机种子：1337
样本数：1000
特征数：2
聚类中心：(0, 5), (5, 0)
cluster_std：1.25
训练/测试比例：70% / 30%
是否分层划分：
干净训练集类别数量：
干净测试集类别数量：
翻转策略：二分类随机双向翻转（0 ↔ 1）
翻转比例：10%、20%、30%、40%、50%
预期翻转数量：70、140、210、280、350
实际翻转数量：应以各次 flipped_indices 长度为准
干净模型 Accuracy：0.9933
干净模型其他指标：待后续
污染模型 Accuracy：10%=0.9933；20%=0.9933；30%–50% 精确值未提供
决策边界变化：随污染比例变化；已完成叠加图
混淆矩阵变化：待后续
结论：高可分合成数据上，边界和参数变化可先于 Accuracy 下降出现
```

---

## 18. 记忆卡片

### Q1：标签翻转修改什么？

只修改训练样本的标签 `y`，保持其输入特征 `x` 不变。

### Q2：标签翻转的常见目标是什么？

让模型学习错误的特征—类别关系，从而降低准确率、精确率、召回率或整体可靠性。

### Q3：标签翻转只能发生在存储阶段吗？

不能。它也可能发生在数据采集、标注平台、处理脚本和反馈转标签的过程中。

### Q4：为什么应保持测试集干净？

测试集代表正确真值。污染测试标签会扭曲评估，使实验无法准确测量训练污染造成的性能变化。

### Q5：为什么使用二维合成数据？

它省略了真实文本处理的复杂性，并能直观看到样本位置不变、标签颜色变化以及决策边界移动。

### Q6：固定随机种子有什么作用？

保证数据生成、划分和后续翻转抽样可复现，便于公平比较干净模型与污染模型。

### Q7：总体 Accuracy 正常能否排除定向标签翻转？

不能。攻击可能只影响特定类别、群体或边界区域，需要检查分群指标和混淆矩阵。

### Q8：为什么攻击前必须训练干净基线模型？

基线提供正常性能和决策边界参照。只有在相同测试集和训练配置下比较干净与污染模型，才能量化标签翻转造成的影响。

### Q9：Logistic Regression 的二维决策边界是什么？

满足 $w_1x_1+w_2x_2+b=0$ 的直线；直线两侧分别预测为 Class 0 和 Class 1。

### Q10：为什么 10% 标签翻转后 Accuracy 仍可能不变？

两个合成聚类高度可分，测试点距离边界较远。边界虽轻微移动，但没有额外测试点跨过边界，所以离散预测正确数保持不变。

### Q11：50% 随机双向翻转为什么特殊？

在期望上，每个标签有同等概率保持正确或被翻错，原始特征与污染标签之间的监督信号被抹除。有限样本结果会受随机不平衡强烈影响。

### Q12：不同污染比例的翻转集合应如何设计？

独立随机集合适合研究不同噪声实例；固定随机排列的嵌套集合适合观察同一攻击逐步累积。报告中必须说明采用哪一种。

### Q13：Accuracy 不变是否代表模型未受影响？

不代表。权重、偏置、概率、校准、Log Loss 和决策边界都可能已经变化，只是当前测试样本尚未改变离散类别。

---

## 19. 当前小结

标签翻转的机制简单，却直接破坏监督学习最核心的真值信息。样本内容可以完全正确，文件格式也可以完全合法，但错误标签会迫使模型学习不存在或相反的关联。

当前实验已经建立一个可复现的干净基线：

- 使用 `make_blobs` 生成 1000 个二维二分类样本；
- 以 70% / 30% 划分训练集与测试集；
- 用两个明显可分的聚类模拟负面和正面评论；
- 固定 `SEED = 1337`；
- 完成干净训练数据的散点图可视化；
- 在干净训练集上训练 Logistic Regression；
- 在干净测试集上得到附件报告的基线 Accuracy `0.9933`；
- 完成基线模型二维决策边界可视化；
- 对训练标签实施 10%–50% 的随机双向翻转；
- 在同一干净测试集上评估各污染模型；
- 观察到 10% 和 20% 污染下 Accuracy 仍为 `0.9933`；
- 完成 Accuracy 趋势图和 0%–50% 决策边界叠加图；
- 确认边界变化可能先于离散 Accuracy 下降出现。

下一步应补充各污染比例的精确 Accuracy、分类报告、混淆矩阵、Log Loss、概率校准和模型系数，并在多个随机种子下重复实验，报告均值、波动和置信区间。

---

## 延伸文档

- [[标签翻转定向案例]]：Class 1 向两个目标类翻转的实验设计、验证与指标。
- [[标签翻转代码审计]]：标签复制、索引抽样、赋值、比例计算与 Notebook 状态审计。
- [[定向标签攻击Targeted Label Attacks测试与笔记]]：更完整的定向标签攻击威胁模型与测试方法。
