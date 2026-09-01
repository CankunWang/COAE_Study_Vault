---
id: coae-appsec-ee789eb8
title: 'Evasion Attacks 与 GoodWords 攻击安全测试清单与学习笔记'
aliases: []
domain:
  - 'AI应用与系统安全'
note_type:
  - concept
  - checklist
attack_phase:
  - inference
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-15
---
# Evasion Attacks 与 GoodWords 攻击安全测试清单与学习笔记

> 适用范围：AI/ML 推理阶段安全学习、授权红队测试、模型上线前评估和分类器鲁棒性验证。实验必须使用本地模型、合成数据、课程靶场或明确授权的测试服务；不得对第三方垃圾邮件、恶意软件、风控、内容审核或生产 API 执行绕检测试。
> 相关笔记：[[一阶梯度规避攻击FGSM与I-FGSM从零学习笔记]]、[[DeepFool最小扰动规避攻击从零学习笔记]]、[[稀疏规避攻击与EAD从零学习笔记]]、[[AI数据攻击总结详解与测试笔记]]、[[模型逆向Model Reverse Engineering原理与防御笔记]]、[[LLM滥用Abuse Attacks总结详解与测试笔记]]。

---

## 使用方式：Evasion 快速测试入口

```text
确认推理入口
    ↓
建立干净基线
    ↓
选择可控样本与目标类别
    ↓
在授权环境中施加受限扰动
    ↓
比较预测、置信度、阈值距离和副作用
    ↓
记录根因、防御和回归结果
```

开始前：

```text
[ ] 明确测试只发生在推理阶段，不修改训练集、标签、模型参数或部署制品
[ ] 使用隔离模型、副本服务、合成样本和可回滚配置
[ ] 记录模型版本、特征提取器、阈值、随机种子和测试集哈希
[ ] 明确攻击者知识：白盒、灰盒、黑盒或 surrogate model
[ ] 明确成功条件：目标样本是否越过分类阈值，是否保持人类可读语义
[ ] 记录扰动预算：新增 token 数、编辑距离、可见性、格式约束和业务约束
[ ] 禁止把真实垃圾邮件、真实恶意软件或真实违规内容作为测试样本
```

最少报告：

```text
干净输入预测 vs 扰动输入预测
类别概率或分类分数变化
阈值距离变化
扰动大小与可见性说明
重复实验和随机种子结果
误伤率、正常样本影响和防御后回归结果
```

快速判据：

```text
只改输入，不改模型或训练数据，才是 Evasion
单个样本跨过决策边界，不能直接证明全局失效
总体 Accuracy 正常，不代表目标样本没有被规避
一次成功，不代表可迁移、可重复或现实可利用
```

---

## 0. 一页速记

### 0.1 定义

Evasion Attack 是推理阶段攻击。攻击者不改变训练数据、标签或模型参数，而是构造模型在预测时看到的输入，使已部署模型给出错误输出。

```text
干净输入 x
    ↓
受限修改为 x'
    ↓
模型 f(x') 发生错误预测
    ↓
训练管线和模型参数保持不变
```

核心目标不是“污染模型学到的知识”，而是“让单次或一批输入越过模型已经学好的决策边界”。

### 0.2 与训练期攻击的区别

| 对比项 | 训练期攻击 | Evasion Attack |
|---|---|---|
| 发生阶段 | 训练前、训练中、再训练或部署交付 | 推理时 |
| 攻击对象 | 数据、标签、管线、模型文件 | 单次或一批输入 |
| 是否改变参数 | 通常会间接或直接改变模型行为 | 不改变参数 |
| 典型结果 | 全局偏移、后门、错误学习 | 特定输入被误判 |
| 常见能力 | 数据或管线访问权 | 正常查询接口或输入通道 |

一句话区分：

```text
投毒：提前改变模型学到了什么。
规避：推理时改变模型看到了什么。
```

### 0.3 迁移性

迁移性是指在 surrogate model 上生成的对抗样本，可能也能欺骗另一个生产模型。模型架构、训练数据、特征工程或决策边界越相似，迁移风险通常越高。

```text
攻击者本地训练 surrogate
    ↓
离线寻找可规避样本
    ↓
将样本提交给黑盒目标模型
    ↓
观察是否跨模型迁移成功
```

这使黑盒攻击更现实：攻击者不一定需要生产模型权重，只要能构造近似模型并查询目标接口。

### 0.4 一句话记忆

> Evasion 的本质是：不改模型，只改模型眼前的输入，让样本落到决策边界的另一侧。

---

## 1. AI 攻击生命周期中的位置

AI 系统可以在训练期和推理期受到攻击。两类攻击需要不同防御。

训练期攻击包括：

- Data Poisoning：注入或篡改训练样本；
- Label Manipulation：篡改样本标签；
- Trojan / Backdoor：植入隐藏触发器；
- Model Deployment Tampering：替换模型、处理器或部署配置。

推理期攻击包括：

- Evasion / Adversarial Example：让输入被误判；
- Prompt Injection：让 LLM 在推理时服从恶意上下文；
- Sponge Example：让推理成本异常升高；
- Model Extraction 辅助规避：先复制近似边界，再离线生成样本。

关键差异：

```text
训练期攻击：影响模型将来如何行为。
推理期攻击：影响模型这一次看到什么、输出什么。
```

---

## 2. 传统 ML 中的 Evasion

传统机器学习通常依赖固定特征表示。攻击者的目标是改动输入，使特征向量变化到分类阈值另一侧，同时尽量保持人类语义或业务功能不变。

### 2.1 常见场景

| 场景 | 模型看到的特征 | 规避思路 |
|---|---|---|
| 垃圾邮件过滤 | 词频、TF-IDF、字符模式、发件元数据 | 添加或替换低风险词，使垃圾邮件分数下降 |
| 静态恶意软件检测 | 字节 n-gram、导入表、节区结构、字符串 | 改变静态特征，同时不改变程序意图 |
| 欺诈检测 | 金额、频率、设备、时间、关系图特征 | 调整边界附近行为，使风险分数低于阈值 |
| 图像分类 | 像素、纹理、深度特征 | 添加小扰动，让类别翻转 |

共同点：

```text
输入表面变化可能很小
    ↓
特征空间变化足够大
    ↓
分类分数越过阈值
```

### 2.2 为什么要从结构化分类器学起

结构化分类器更容易观察：

- 输入如何变成特征；
- 特征如何影响分数；
- 分数如何与阈值比较；
- 哪些扰动真正推动了分类翻转。

掌握这些机制后，再理解 LLM Prompt Injection 会更清楚：LLM 的输入空间更复杂，但仍是在推理时利用模型的输入处理和决策机制。

---

## 3. LLM 中的 Evasion 与 Prompt Injection

LLM 的输出不是固定标签，而是开放文本、结构化调用、代码、SQL、HTML 或工具参数。因此 LLM 的核心规避形态通常是 Prompt Injection。

```text
原始系统目标
    +
用户输入 / 外部文档 / Tool Result 中的恶意指令
    ↓
模型在推理时错误排序或执行指令
    ↓
输出越权内容、错误调用工具或泄露上下文
```

与传统分类器的对应关系：

| 对比项 | 传统 ML Evasion | LLM Prompt Injection |
|---|---|---|
| 输入表面 | 特征化样本 | 对话、文档、工具结果、上下文 |
| 模型行为 | 输出类别或分数 | 生成文本、调用工具、写代码 |
| 关键杠杆 | 特征统计与阈值 | 指令优先级与上下文管理 |
| 影响范围 | 单次误判 | 单次响应、工具调用或下游系统行为 |
| 防御重点 | 鲁棒特征、阈值、检测、再训练 | 指令隔离、工具权限、输出验证、上下文净化 |

重要区别：LLM 输出本身可能成为动作面。例如模型生成 SQL、代码、HTML 或 API 参数后，下游系统可能执行或渲染这些内容，使攻击影响超出初始响应。

---

## 4. GoodWords 攻击

GoodWords 攻击是一类针对概率型垃圾邮件过滤器的规避方法。攻击者向原始文本中插入“看起来更像正常邮件”的 benign tokens，使过滤器计算出的垃圾邮件概率下降。

Lowd 和 Meek 在 2005 年论文 *Good Word Attacks on Statistical Spam Filters* 中系统讨论了这类攻击。它的关键点不是隐藏或改写原始垃圾内容，而是在保留原始语义的同时追加合法外观的词项，让概率模型把整封消息误判为正常邮件。

### 4.1 基本机制

以 Naive Bayes 垃圾邮件分类器为例，模型会估计：

$$
P(\text{spam} \mid w_1, w_2, ..., w_n)
$$

Naive Bayes 假设词之间在类别条件下近似独立，因此每个词都会贡献一部分证据。

```text
原始样本：高风险词较多
    ↓
P(spam | words) 高于阈值
    ↓
插入 benign-looking tokens
    ↓
ham 方向证据增加
    ↓
P(spam | words) 低于阈值
```

这种攻击利用了模型假设：词项被近似独立累计，而模型未必理解整段文本的真实意图。

### 4.2 Naive Bayes 决策复习

Naive Bayes 用贝叶斯公式计算文档 \(D\) 属于类别 \(C\) 的后验概率：

$$
P(C \mid D)=\frac{P(D \mid C)P(C)}{P(D)}
$$

在二分类垃圾邮件检测中，类别通常是：

```text
C ∈ {spam, ham}
```

分类器选择后验概率更大的类别：

$$
\text{class}=\arg\max_{c \in \{spam,ham\}} P(c \mid D)
$$

因为 \(P(D)\) 对所有类别相同，实际比较时通常只看：

$$
P(D \mid c)P(c)
$$

Naive Bayes 的“朴素”假设是：给定类别后，每个词项近似条件独立。因此：

$$
P(D \mid C)=\prod_{i=1}^{n}P(w_i \mid C)
$$

实际实现常在 log space 中计算，避免很多小概率连乘导致数值下溢：

$$
\text{score}(c,D)=\log P(c)+\sum_{i=1}^{n}\log P(w_i \mid c)
$$

这也是 GoodWords 能生效的核心原因：词项贡献从“连乘”变成了 log space 里的“累加”。新增词项不会要求模型重新理解整段文本，只会继续给某一侧类别增加证据。

### 4.3 概率操纵过程

假设原始垃圾邮件为 \(M_{spam}\)，包含词项：

$$
\{w_1,w_2,...,w_m\}
$$

模型分别计算：

$$
\text{score}(spam,M_{spam})
=
\log P(spam)
+
\sum_{i=1}^{m}\log P(w_i \mid spam)
$$

$$
\text{score}(ham,M_{spam})
=
\log P(ham)
+
\sum_{i=1}^{m}\log P(w_i \mid ham)
$$

如果模型正确拦截该样本，应满足：

$$
\text{score}(spam,M_{spam})
>
\text{score}(ham,M_{spam})
$$

GoodWords 攻击追加一组偏向正常邮件的词项：

$$
G=\{g_1,g_2,...,g_k\}
$$

得到增强消息：

$$
M_{augmented}=M_{spam}\cup G
$$

新分数变为：

$$
\text{score}(spam,M_{augmented})
=
\log P(spam)
+
\sum_{i=1}^{m}\log P(w_i \mid spam)
+
\sum_{j=1}^{k}\log P(g_j \mid spam)
$$

$$
\text{score}(ham,M_{augmented})
=
\log P(ham)
+
\sum_{i=1}^{m}\log P(w_i \mid ham)
+
\sum_{j=1}^{k}\log P(g_j \mid ham)
$$

原始垃圾词项仍然存在，原始 spam 证据没有消失。攻击成功依赖新增词项在 ham 方向贡献足够大，使：

$$
\text{score}(ham,M_{augmented})
>
\text{score}(spam,M_{augmented})
$$

换成“需要跨过的门槛”来理解，就是：

$$
\sum_{j=1}^{k}
\left[
\log P(g_j \mid ham)
-
\log P(g_j \mid spam)
\right]
>
\sum_{i=1}^{m}
\left[
\log P(w_i \mid spam)
-
\log P(w_i \mid ham)
\right]
+
\left[
\log P(spam)
-
\log P(ham)
\right]
$$

左侧是新增 GoodWords 给 ham 类别带来的净证据；右侧是原始垃圾内容和类别先验形成的 spam 门槛。只要左侧超过右侧，分类就可能翻转。

一个安全的抽象例子：

```text
原始 spam 证据 margin：8.0
每个中性占位词向 ham 侧贡献：3.0
追加 3 个同类占位词：9.0
结果：ham 证据超过 spam 证据，分类可能翻转
```

这里的占位词只用于理解机制，不代表现实可用词表。

### 4.4 Goodness Score

GoodWords 选择的目标，是找到更常见于 ham、较少见于 spam 的词项。可用一个抽象 goodness score 表示：

$$
S(w)=\frac{P(w \mid ham)}{P(w \mid spam)+\epsilon}
$$

其中 \(\epsilon\) 是很小的平滑常数，用来避免分母为 0。

直观解释：

| 词项类型 | 特征 | 对攻击的意义 |
|---|---|---|
| ham 偏置词 | 在正常邮件中更常见，在垃圾邮件中较少见 | 可能强烈拉低 spam 分数 |
| shared words | 两类都常见 | 区分度低，贡献有限 |
| spam 偏置词 | 在垃圾邮件中更常见 | 会强化拦截方向 |

实际安全测试不应输出“最优 GoodWords 词表”。更合适的做法是使用中性占位词、合成语料和受控概率表，验证模型是否容易被“偏向 ham 的特征堆叠”翻转。

### 4.5 为什么攻击有效

GoodWords 利用了几个叠加条件：

- 条件独立假设：模型把每个词项近似当作独立证据；
- log-space 加法：新增词项可以线性累加到分类分数中；
- 上下文缺失：模型不理解追加词项与原始内容是否语义一致；
- 静态分布：训练得到的词类概率在部署后通常相对固定；
- 平滑机制：Laplace 等平滑方法让少见或未见词也有非零概率；
- 阈值决策：只要分数跨过阈值，最终标签就会翻转。

可以把分类器想成一个证据天平：

```text
原始垃圾词项 → spam 侧加重量
追加 GoodWords → ham 侧加重量
ham 侧累计重量超过 spam 侧 → 分类翻转
```

Naive Bayes 的问题不是“完全无用”，而是它的高效假设带来了可预测的攻击面。攻击者一旦知道或近似知道词项概率，就可以系统性寻找最能推动分数的输入修改。

### 4.6 为什么它适合入门

GoodWords 适合作为 Evasion 入门实验，因为：

- 特征是可解释的词项；
- 分数变化可以直接观察；
- 白盒和黑盒条件都能讨论；
- 扰动预算容易定义；
- 可清楚展示“少量输入变化导致阈值翻转”。

### 4.7 安全实验约束

测试时只使用合成邮件和中性占位词，例如：

```text
BENIGN_TEST_TOKEN_A
BENIGN_TEST_TOKEN_B
COURSE_NEWSLETTER_MARKER
```

不要收集、导出或共享现实可用的绕检词表。实验目标是验证模型机制和防御，而不是生产可复用规避材料。

---

## 5. GoodWords 授权测试清单

### 5.1 测试前置

```text
[ ] 使用本地 Naive Bayes / 课程模型 / 授权靶场，不测试真实邮件网关
[ ] 训练集、验证集和测试集均为合成或公开教学数据
[ ] 固定 tokenizer、停用词、平滑参数、阈值和随机种子
[ ] 保留原始样本 ID、原始预测分数和扰动后预测分数
[ ] 只使用中性占位词，不构造现实垃圾邮件绕检词表
[ ] 设置最大新增 token 数和最大文本长度
```

### 5.2 基线记录

```text
[ ] 记录干净样本的预测标签
[ ] 记录 spam / ham 概率或 log odds
[ ] 记录距离阈值的 margin
[ ] 记录 top contributing features
[ ] 记录模型对正常样本、边界样本和明显垃圾样本的表现
```

### 5.3 扰动实验

```text
[ ] 每次只改变一个变量：新增 token 数、位置、重复次数或 token 组合
[ ] 比较开头、正文、签名、引用文本等不同插入位置
[ ] 比较单词级、短语级和格式级扰动
[ ] 记录最小翻转扰动：让标签翻转所需的最少 token 数
[ ] 检查扰动后文本是否仍保持原始语义和人工可读性
[ ] 检查是否出现长度、格式或异常 token 触发的简单检测信号
```

### 5.4 黑盒测试口径

```text
[ ] 只观察标签时，记录查询次数、翻转比例和停止条件
[ ] 可观察置信度时，记录分数变化曲线
[ ] 使用 surrogate model 时，区分本地成功率和目标模型成功率
[ ] 控制查询预算，避免对服务造成压力或枚举真实防线
[ ] 不把失败样本反复提交给生产系统调参
```

### 5.5 判定标准

```text
[ ] 攻击成功：目标样本从 spam 翻转为 ham，且扰动在预算内
[ ] 攻击不充分：只降低分数但未越过阈值
[ ] 不可接受副作用：正常样本误伤显著上升
[ ] 不可复现：换 seed、换样本或换划分后成功率消失
[ ] 不可迁移：只对本地模型有效，对目标模型无稳定效果
```

---

## 6. Spam Filter 实验靶场实现

GoodWords 攻击需要一个可控目标模型。适合入门的靶场是：使用 SMS Spam Collection 数据集训练一个本地 Naive Bayes 垃圾短信分类器，再在隔离环境中观察 GoodWords 扰动如何影响分数。

### 6.1 实验目标

```text
真实或公开教学数据
    ↓
文本清洗与特征提取
    ↓
CountVectorizer 生成词项计数特征
    ↓
MultinomialNB 训练 spam / ham 分类器
    ↓
保存 vectorizer + classifier
    ↓
建立干净基线，供后续 GoodWords 测试
```

注意：如果课程环境要求安装特定 HTB 工具库，应只在本地虚拟环境或课程容器中安装。普通学习笔记不依赖该库，核心模型可以直接用 `pandas`、`scikit-learn` 和标准库完成。

### 6.2 依赖与可复现性

实验常见依赖：

```text
pandas
numpy
matplotlib
scikit-learn
```

可复现性要求：

```text
[ ] 固定 Python、scikit-learn 和 pandas 版本
[ ] 固定 random.seed 与 numpy random seed
[ ] 固定 train_test_split 的 random_state
[ ] 固定 CountVectorizer 参数
[ ] 保存训练后的 vectorizer 和 classifier
[ ] 记录数据集哈希、样本数和类别分布
```

示例 seed：

```text
random.seed(1337)
np.random.seed(1337)
```

seed 的意义不是让攻击更强，而是让训练、评估和后续扰动实验可以重复验证。

### 6.3 数据加载与缓存

SMS Spam Collection 数据集包含约 5,574 条带标签短信，标签为 `spam` 或 `ham`。实验中常用缓存机制：

```text
data/
    sms_spam.zip       临时下载文件
    sms_spam.csv       处理后的缓存 CSV
models/
    spam_classifier.pkl
```

缓存的目的：

- 避免每次运行都重新下载；
- 避免重复解压和解析；
- 保持训练输入稳定；
- 让后续调参和攻击测试更快。

数据加载检查清单：

```text
[ ] 如果本地 CSV 存在，优先读取缓存
[ ] 如果缓存不存在，再从可信来源下载
[ ] 解压时只读取预期文件，不信任归档中的任意路径
[ ] 解析 tab-separated 格式时验证字段数
[ ] 只保留 label 与 message 两列
[ ] 保存处理后的 CSV 作为后续固定输入
```

### 6.4 数据分布观察

附件中的实验基线显示，原始数据大致为：

| 类别 | 数量 | 比例 |
|---|---:|---:|
| ham | 4,825 | 86.6% |
| spam | 747 | 13.4% |
| total | 5,572 | 100% |

去重后大致为：

| 类别 | 数量 | 比例 |
|---|---:|---:|
| ham | 4,515 | 87.6% |
| spam | 638 | 12.4% |
| total | 5,153 | 100% |

这个类别不平衡接近真实场景：正常消息远多于垃圾消息。它也会影响模型行为，例如模型可能更倾向多数类，spam 的 recall 和边界样本更值得关注。

### 6.5 文本预处理策略

实验使用两层清洗。

第一层是 minimal cleaning，用于保留可分析的垃圾短信信号：

```text
HTML entity 解码
Unicode NFKC 规范化
多余空白折叠
保留大小写、标点、货币符号等可疑特征
```

第二层是 vectorization cleaning，用于喂给 CountVectorizer：

```text
转换为小写
保留数字、货币符号、感叹号、问号、句号等特征
移除真正有问题或不可解析的字符
再次折叠空白
```

为什么不能过度清洗：

- `FREE`、`WINNER`、`£900` 等模式本身是强特征；
- 重复标点可能代表紧迫感；
- 数字和货币符号可能代表奖品、金额或联系方式；
- 过度清洗会让模型失去区分 spam / ham 的关键证据。

### 6.6 去重、空值与数据切分

去重建议只删除同一标签下清洗后完全相同的消息：

```text
subset = [label, clean_message]
```

这样可以减少模板化垃圾短信对训练的重复影响，同时保留潜在的标签冲突样本供审计。

切分训练集和测试集时应使用 stratified split：

```text
train_test_split(..., test_size=0.2, random_state=42, stratify=y)
```

原因：

- 保持 train / test 中 spam 与 ham 比例一致；
- 避免少数类在测试集中比例异常；
- 让 precision、recall 和 f1 更可比较。

附件中的切分结果：

| 数据集 | 数量 |
|---|---:|
| Training | 4,122 |
| Testing | 1,031 |

### 6.7 特征提取与模型训练

实验目标模型：

```text
CountVectorizer
    ↓
MultinomialNB
```

CountVectorizer 关键参数：

```text
max_features=3000
token_pattern=捕获单词、货币符号、数字、重复感叹号、重复问号、连续句点
lowercase=True
stop_words='english'
```

参数含义：

- `max_features=3000`：限制词表大小，降低过拟合和噪声；
- 自定义 `token_pattern`：保留 spam 中常见的符号和数字特征；
- `lowercase=True`：合并大小写变体；
- `stop_words='english'`：去除常见低区分度英文词。

模型持久化应同时保存：

```text
vectorizer
classifier
```

原因是分类器权重和向量化词表必须一致。只保存模型、不保存 vectorizer，会导致后续输入映射到不同特征空间，评估结果失真。

### 6.8 基线评估

附件中的基线结果：

| 指标 | 数值 |
|---|---:|
| Training accuracy | 0.9922 |
| Testing accuracy | 0.9864 |
| ham precision / recall / f1 | 0.99 / 0.99 / 0.99 |
| spam precision / recall / f1 | 0.95 / 0.94 / 0.94 |
| overall accuracy | 0.99 |

解释：

- 训练准确率和测试准确率差距约 0.58%，说明没有明显过拟合；
- ham 表现更高，符合多数类优势；
- spam recall 为 0.94，说明仍有少量垃圾短信漏检；
- 这种“整体表现很好但少数类仍有边界”的模型，正适合演示 Evasion。

### 6.9 靶场实现检查清单

```text
[ ] 数据来源、下载 URL、版本和哈希已记录
[ ] 缓存 CSV 与模型 pkl 文件路径固定
[ ] 预处理同时保留 analysis 版本和 vectorization 版本
[ ] 去重前后样本数、spam/ham 数量已记录
[ ] train/test 使用 stratify，并固定 random_state
[ ] vectorizer 参数已记录
[ ] model pickle 同时包含 vectorizer 和 classifier
[ ] 输出 training accuracy、testing accuracy 和 classification_report
[ ] 单独关注 spam precision、spam recall 和边界样本
[ ] 后续 GoodWords 测试只在该本地靶场或授权课程环境执行
```

---

## 7. GoodWords 白盒实现与效果评估

在已经训练好本地 spam filter 后，可以进入 GoodWords 实验阶段。白盒条件下，测试者能直接读取模型学到的词项概率，因此不需要猜测哪些词更偏向 ham，而是从 `vectorizer` 和 `classifier` 中提取特征名与条件概率。

### 7.1 白盒访问对象

典型可观察对象：

```text
vectorizer.get_feature_names_out()
classifier.feature_log_prob_
classifier.classes_
classifier.predict_proba()
```

含义：

| 对象 | 含义 |
|---|---|
| feature names | 模型词表中的 token |
| feature_log_prob_ | 每个 token 在各类别下的 log 概率 |
| classes_ | 类别顺序，必须确认 ham / spam 的索引 |
| predict_proba | 扰动前后的类别概率 |

注意：不要假设 `feature_log_prob_[0]` 一定是 ham、`[1]` 一定是 spam。应先读取 `classifier.classes_`，确认类别顺序后再解释概率。

### 7.2 Goodness Score 提取

白盒 GoodWords 提取过程：

```text
读取词表
    ↓
读取每个词在 ham / spam 下的 log 概率
    ↓
用 exp 转回概率
    ↓
计算 goodness score
    ↓
按分数排序
    ↓
只在本地靶场中选择候选 token 做扰动实验
```

抽象计算：

$$
S(w)=\frac{P(w \mid ham)}{P(w \mid spam)+\epsilon}
$$

实现细节：

- `feature_log_prob_` 存的是 \(\log P(w \mid c)\)，不是原始概率；
- `np.exp(log_prob)` 可转回概率空间；
- \(\epsilon\) 用来避免分母为 0；
- 只看 ratio 不够，还要看 ham/spam 的原始概率；
- 高 ratio 但极低频的 token，可能不稳定或只对当前数据划分有效。

安全记录方式：

```text
[ ] 记录 goodness score 的计算方法
[ ] 记录候选 token 数量，例如 top 100
[ ] 记录筛选规则，例如最小 ham 频率、最大 spam 频率
[ ] 不导出、不发布现实可复用的高分词表
[ ] 报告中用占位词或类别描述替代真实 token
```

### 7.3 候选词选择原则

附件中的实验按 goodness score 选择 top N token，并观察追加词数对逃逸率的影响。这是 greedy 策略：每次选当前排序最高的前 N 个词。

优点：

- 实现简单；
- 计算成本低；
- 便于解释；
- 足以暴露 Naive Bayes 的脆弱性。

限制：

- 不一定是全局最优组合；
- token 之间可能存在冗余；
- 部分高分 token 可能来自数据集方言、格式或采样偏差；
- 在另一个数据集、模型版本或 tokenizer 下可能失效。

测试时应避免把“排序最高的真实词”当成通用攻击词表。它们只是当前模型、当前数据、当前预处理管线下的白盒结果。

### 7.4 攻击实验设计

实验只针对测试集中的 spam 样本，观察追加不同数量 GoodWords 后，有多少样本从 spam 被判成 ham。

典型测试点：

```text
word_counts = [0, 5, 10, 15, 20, 25, 30, 35, 40]
```

设计理由：

- `0` 是自然误判基线；
- `5` 到 `20` 观察快速变化区；
- `25` 到 `40` 用于确认是否饱和；
- 固定间隔便于画曲线和比较模型版本。

每个配置要记录：

```text
num_words
evaded
total_spam_samples
evasion_rate
平均 spam probability 变化
平均 margin 变化
最小翻转词数分布
```

判定逻辑：

```text
如果 P(ham) > P(spam)，则该 spam 样本在当前模型下 evaded
```

重要细节：`P(ham)=0.501` 和 `P(ham)=0.99` 在最终标签上都算逃逸，但风险强度不同。报告中应同时记录“是否翻转”和“置信度/阈值距离”。

### 7.5 附件实验结果

附件中的本地靶场对 128 条 spam 测试样本得到如下趋势：

| 追加 GoodWords 数 | 逃逸率 | 逃逸样本 |
|---:|---:|---:|
| 0 | 6.25% | 8/128 |
| 5 | 41.41% | 53/128 |
| 10 | 74.22% | 95/128 |
| 15 | 96.09% | 123/128 |
| 20 | 100.00% | 128/128 |
| 25 | 100.00% | 128/128 |
| 30 | 100.00% | 128/128 |
| 35 | 100.00% | 128/128 |
| 40 | 100.00% | 128/128 |

解释：

- `0` 词时的 6.25% 是模型天然 false negative；
- 追加 5 个高分 token 后，逃逸率大幅上升；
- 10 到 15 个词附近进入快速崩塌区；
- 20 个词后达到饱和，继续追加没有边际收益；
- 这说明 bag-of-words + Naive Bayes 对“偏向 ham 的 token 堆叠”非常敏感。

### 7.6 曲线形态

GoodWords 效果通常呈 S 型或近似 S 型曲线：

```text
低词数区：多数样本仍被拦截
临界区：少量新增词导致大量样本跨过阈值
饱和区：几乎所有可翻转样本都已翻转
```

原因：

- 在 log space 中，每个新增 token 给 ham 分数增加一段固定或近似固定的证据；
- 当累计证据接近决策边界时，少量新增词就会造成标签翻转；
- 转回概率空间后，变化表现为非线性；
- 达到 100% 逃逸后，继续追加词不会提高标签层面的成功率。

绘图建议：

```text
x 轴：Number of Good Words Added
y 轴：Evasion Rate (%)
参考线：50% threshold、90% threshold
标注：首次超过 50%、90%、100% 的词数
```

### 7.7 实现实验检查清单

```text
[ ] 先确认 classifier.classes_ 的类别顺序
[ ] 只在测试集 spam 样本上计算逃逸率
[ ] 记录 0 词基线 false negative rate
[ ] 每个 word_count 对全部 spam 测试样本重复测试
[ ] 保存 evaded、total、evasion_rate 和概率 margin
[ ] 不把真实 top GoodWords 词表写入报告或公开材料
[ ] 对追加后的文本长度和异常 token 数量做副作用记录
[ ] 曲线中标出 50%、90% 和饱和点
[ ] 防御后用同一批样本和同一批配置做回归
```

---

## 8. Black-Box GoodWords 攻击理解与测试

黑盒 GoodWords 场景更接近真实部署：测试者不能读取模型结构、参数、训练数据、词表或条件概率，只能提交消息并观察返回的标签、置信度或 spam probability。

核心变化：

```text
白盒：直接读取模型概率表，排序选择 GoodWords
黑盒：通过查询观察分数变化，估计哪些词有用
```

这把问题从“直接优化”变成了“有限查询预算下的探索问题”。

### 8.1 黑盒目标函数

把目标 spam filter 看成未知函数：

$$
f:\mathcal{X}\rightarrow[0,1]
$$

其中：

- \(\mathcal{X}\)：消息空间；
- \(f(x)\)：模型返回的 spam probability 或风险分数；
- \(x\)：原始 spam 测试消息；
- \(W\)：准备追加的候选词集合；
- \(x\oplus W\)：把 \(W\) 追加到 \(x\) 后的新消息。

黑盒目标可以写成：

$$
\min_{W\subseteq\mathcal{V}, |W|\leq k} f(x\oplus W)
$$

含义：在候选词表 \(\mathcal{V}\) 中选最多 \(k\) 个词，让追加后的消息 spam 分数尽量低。

### 8.2 有限差分奖励

黑盒下不知道 \(P(w \mid ham)\) 和 \(P(w \mid spam)\)，只能靠查询估计某个词的边际影响。

单词奖励：

$$
r_w(x)=f(x)-f(x\oplus\{w\})
$$

解释：

```text
原始 spam 分数 - 追加某词后的 spam 分数 = 该词的观察奖励
```

如果 \(r_w(x)>0\)，说明该词降低了 spam 分数；如果接近 0，说明影响弱；如果小于 0，说明它反而增强了 spam 判断。

词集合奖励：

$$
r_W(x)=f(x)-f(x\oplus W)
$$

测试记录要点：

```text
[ ] 原始样本分数 f(x)
[ ] 每次追加后的分数 f(x ⊕ W)
[ ] 分数下降量 r
[ ] 查询次数
[ ] 是否跨过 ham / spam 决策阈值
[ ] 追加词数量和文本长度变化
```

### 8.3 探索与利用

黑盒攻击面临典型 exploration vs exploitation 问题：

| 动作 | 含义 | 风险 |
|---|---|---|
| 探索 | 测试未尝试过的候选词 | 可能浪费查询预算 |
| 利用 | 继续使用已知有效词 | 可能错过更强候选 |

这可以类比为多臂老虎机问题：

```text
每个候选词 = 一个 arm
每次查询 = pull arm
分数下降 = reward
查询预算 = 总尝试次数限制
```

安全测试时，查询预算是必须记录的核心指标，因为现实系统中查询会带来成本、速率限制、告警风险和伦理边界。

### 8.4 UCB 策略

Upper Confidence Bound（UCB）是一种平衡探索和利用的策略。它给每个候选词一个分数：

$$
UCB_w=
\bar{r}_w
+
c\sqrt{\frac{\ln(t)}{n_w}}
$$

其中：

- \(\bar{r}_w\)：词 \(w\) 的平均观察奖励；
- \(n_w\)：词 \(w\) 已被测试次数；
- \(t\)：目前总查询次数；
- \(c\)：探索强度常数；
- 第二项是 exploration bonus，测试次数越少， bonus 越大。

直观理解：

```text
历史效果好 → 值得继续用
测试次数少 → 仍有不确定性，也值得探索
测试次数变多 → 不确定性下降，逐渐依赖真实平均奖励
```

理论上，经典 UCB1 在独立同分布、奖励稳定且有界的条件下有 logarithmic regret。但在真实文本模型中，奖励会受消息内容、上下文、候选词组合和模型版本影响，因此更适合把 UCB 当作查询分配启发式，而不是严格保证。

### 8.5 黑盒实现策略

黑盒 GoodWords 测试通常分三步。

第一步：离线候选词池构建。

```text
公开词典
正常消息语料
业务领域常见词
中性占位词
过滤明显 spam indicator
```

这一步不查询目标模型。安全测试报告不应公开可复用候选词池，尤其不应给出现实过滤系统可直接测试的词表。

候选词池构建可以拆成四个组件：

```text
ham 语料采样
    ↓
token 频率统计
    ↓
高频词筛选
    ↓
合并少量人工挑选的中性会话词
```

实现要点：

- 从授权 ham 语料中抽样，例如 500 条正常消息；
- 使用与目标实验一致的轻量 tokenization；
- 设置长度过滤，例如去掉极短 token 和超长 artifact；
- 设置最低频次，例如 `min_freq=5`，减少偶然词；
- 设置候选数量上限，例如 `max_words=100`，控制后续查询成本；
- 合并候选词后去重，并保持稳定排序，方便复现实验。

候选词池健康检查：

```text
[ ] ham 样本来源合法且可复现
[ ] 采样数量、min_freq、max_words 已记录
[ ] 候选词数量在查询预算内可承受
[ ] 去除了明显 spam indicator、URL、号码和异常 artifact
[ ] 最终候选顺序 deterministic，避免每次实验排序不同
```

第二步：在线自适应评分。

```text
提交原始样本得到基线分数
按策略选择候选词
提交追加后的样本
计算 reward
更新该词平均奖励或移动平均
在查询预算内重复
```

第三步：组合验证。

单词测试只能发现一阶效果，组合测试用于发现词组是否有更强影响：

```text
单词 A 有效
单词 B 有效
A + B 可能只是简单相加，也可能更强或更弱
```

组合验证要控制规模，避免组合爆炸和过量查询。

### 8.6 查询预算管理

黑盒测试必须把查询预算当成实验约束，而不是无限枚举。附件中的模拟预算为：

```text
query_budget = 1000
queries_used = 0
query_log = []
```

预算存在的原因：

- 生产 API 可能按调用计费；
- 服务通常有速率限制；
- 高频自适应查询可能触发告警；
- 授权测试需要明确停止条件；
- 查询越多，越容易把评估变成压力或滥用行为。

一种简单分配方式是 40/40/20：

| 阶段 | 比例 | 1000 查询示例 | 目标 |
|---|---:|---:|---|
| Exploration | 40% | 400 | 广泛测试候选词 |
| Exploitation | 40% | 400 | 使用已知有效词尝试翻转 |
| Combination | 20% | 200 | 验证词组组合效果 |

这种分配不是固定规则，而是起点：

- 查询预算很小：增加 exploitation，减少探索；
- 研究鲁棒性：增加 exploration，覆盖更多候选；
- 怀疑组合效应强：增加 combination；
- 只做上线验收：固定少量代表性扰动，避免过度自适应。

查询日志应至少包含：

```text
timestamp
sample_id
phase
candidate_or_combination
original_score
new_score
reward
prediction_label
queries_used
stop_reason
```

### 8.7 发现阶段设计

发现阶段的目标不是马上获得最高逃逸率，而是估计候选词的平均效果。

附件中使用的思路：

```text
从 spam_test_messages 中选择 50 条样本
随机打乱候选词顺序
随机打乱测试样本顺序
在预算内批量测试候选词
```

为什么要抽样多条 spam：

- 单条样本的 margin 可能过强或过弱；
- 某个词只对个别文本有效，不能代表全局；
- 多样本平均 reward 更稳定；
- 可以减少被某个极端样本误导。

为什么要 shuffle：

- 避免候选词原始排序造成偏差；
- 如果预算提前耗尽，不会永远只测试前半段候选；
- 多轮实验更容易估计方差。

发现阶段记录：

```text
[ ] 候选词测试次数 n_w
[ ] 平均 reward r_bar
[ ] reward 方差或分位数
[ ] 对多少条样本产生正收益
[ ] 是否有样本被单词直接翻转
[ ] 是否存在强上下文依赖
```

### 8.8 三阶段发现算法

完整黑盒发现算法把候选词构建、自适应评分和组合搜索放进一个预算受限流程中。目标不是穷举所有词，而是在有限查询内最大化信息收益。

从信息增益角度看，每次查询都在减少我们对候选词有效性的未知：

$$
I(Q)=H(W)-H(W\mid Q)
$$

其中：

- \(H(W)\)：查询前对词有效性的总不确定性；
- \(H(W\mid Q)\)：观察查询结果后的剩余不确定性；
- \(I(Q)\)：这次查询带来的信息增益。

三阶段思路：

| 阶段 | 目标 | 查询重点 |
|---|---|---|
| Exploration | 降低全词表不确定性 | 多测不同候选词 |
| Exploitation | 精准估计高价值词 | 重测已知强候选 |
| Combination | 发现非线性组合效应 | 测试 pairs / triplets |

### 8.9 Phase 1：Broad Exploration

探索阶段使用较大的候选覆盖面，估计哪些词可能降低 spam score。

典型配置：

```text
budget: 400 / 1000 queries
selection: epsilon-greedy
message: 从 spam_messages 随机选择
candidate: 从 candidate_words 自适应选择
cost: 每次测试约 2 queries
```

每次测试需要两次查询：

```text
query 1: f(x)              原始 spam 分数
query 2: f(x ⊕ {w})        追加候选词后的 spam 分数
impact = f(x) - f(x ⊕ {w})
```

然后更新该词的运行分数，例如用 exponential moving average 逐步修正估计。

探索阶段应设置里程碑，例如 25%、50%、75%：

```text
[ ] 当前已用查询数
[ ] 已测试 unique words 数
[ ] 当前 top 3 候选词及分数
[ ] 是否出现异常高 reward 或负 reward
```

附件实验示例中，400 次查询大约测试了 40 个 unique words。这个结果说明：在两查询一轮、且部分词会被重复测试的情况下，实际覆盖词数远小于总候选词数，所以候选池规模和探索率必须受预算约束。

### 8.10 Phase 2：Focused Exploitation

利用阶段降低探索率，把查询集中到 Phase 1 中表现较好的候选词上。

典型配置：

```text
budget: 400 / 1000 queries
exploration_rate: 从 0.2 降到 0.1
candidate set: Phase 1 top 30
test words: top 15 中采样
test messages: 较小代表性 spam 子集，例如前 20 条
```

目的：

- 降低高分候选词估计方差；
- 确认某个词不是只对单条样本有效；
- 为后续组合搜索提供更可靠 shortlist；
- 避免把剩余预算浪费在明显低效词上。

利用阶段记录：

```text
[ ] top words 列表大小
[ ] exploitation 前后排名变化
[ ] 每个 top word 的测试次数
[ ] 分数是否稳定，还是高度依赖样本
[ ] 是否存在负迁移：在部分样本上反而提高 spam score
```

### 8.11 Phase 3：Combination Discovery

组合阶段测试小规模词组，寻找单词效果无法解释的组合收益。

典型配置：

```text
budget: 200 / 1000 queries
candidate source: Phase 2 top 20
combination size: 1 到 3
test messages: 最多 3 条代表性 spam
query accounting: 每个组合约 2 queries
```

组合搜索关注：

```text
word A 单独有效
word B 单独有效
A + B 是否比 A、B 单独效果之和更强
```

这种 synergy 可能来自模型学到的短语、主题、会话风格或 co-occurrence 统计。不过组合空间增长很快，必须限制：

- 只用 top shortlist；
- 只测 pairs / triplets；
- 控制测试消息数量；
- 预算耗尽立即停止；
- 记录每个组合的最佳分数和适用样本数。

附件示例中，组合阶段约测试 130 个组合并消耗到总预算 1000。组合结果不一定总是显著，这本身也是结论：对某些 bag-of-words 模型，单词堆叠可能已经足够解释主要效果，组合收益有限。

### 8.12 发现算法输出

三阶段流程最终应返回三类结果：

```text
final_words
best_combinations
queries_used
```

含义：

| 输出 | 用途 |
|---|---|
| final_words | 按黑盒观察分数排序的候选词 |
| best_combinations | 在组合搜索中表现较好的词组 |
| queries_used | 验证是否遵守预算 |

报告中还应补充：

```text
[ ] 每阶段实际消耗查询数
[ ] 每阶段发现的候选数量
[ ] 最终逃逸率不是只看 discovery 样本，还要独立验证
[ ] 最终词/组合用占位符或编号表示，不公开真实绕检词表
[ ] 防御后复测同样预算下的发现效率是否下降
```

### 8.13 黑盒攻击执行与独立验证

Discovery 只说明“哪些候选词看起来有效”，还不能直接证明攻击泛化。完整黑盒评估必须把 discovery 和 evaluation 分开。

推荐流程：

```text
Discovery subset
    用于三阶段发现候选词和组合
    ↓
final_words / best_combinations
    ↓
Evaluation subset
    使用未参与 discovery 的 spam 样本验证逃逸率
```

附件中的执行方式：

```text
candidate vocabulary: 约 112 个候选词
query budget: 1000
exploration: 400 queries
exploitation: 400 queries
combination: 200 queries
discovery samples: spam_test_messages[:50]
evaluation samples: spam_test_messages[30:50]
```

严格实验中，evaluation subset 最好与 discovery subset 完全不重叠。附件里使用部分不同区间用于演示，学习时应理解其目的：避免只报告在调参样本上的成功率。

### 8.14 黑盒结果解释

黑盒 discovery 的结果不一定和白盒 top words 一致。原因是两个指标不同：

| 方法 | 排名依据 | 反映内容 |
|---|---|---|
| 白盒 goodness score | \(P(w \mid ham) / P(w \mid spam)\) | 训练分布中的类别偏置 |
| 黑盒 empirical impact | \(f(x)-f(x\oplus w)\) | 真实查询中对 spam 分数的实际影响 |

因此可能出现：

```text
白盒高分词：理论上很 ham-like，但实际追加后分数变化有限
黑盒高影响词：ratio 不一定最高，但对当前消息集 margin 影响更大
```

这对防御很重要：隐藏内部概率表并不能消除结构性漏洞。只要模型仍然把某类 token 作为强 ham 证据，黑盒查询就可能发现替代路径。

### 8.15 黑盒效果曲线

黑盒验证通常继续使用不同追加数量：

```text
test_counts = [0, 5, 10, 15, 20, 25, 30]
```

每个数量下：

```text
选择 final_words 前 N 个候选
追加到 held-out spam 消息
查询 spam probability
如果 spam probability < 0.5，则记为 evaded
统计 evasion_rate
```

典型趋势：

```text
0 words      自然误判率，通常约 5-10%
10 words     可达到约 70-75% 逃逸
15 words     可达到约 90-95% 逃逸
20+ words    可接近 95-100% 逃逸
```

具体数值依赖数据集、模型、预处理、候选池、反馈粒度和查询预算。报告时应避免把单次曲线当成普遍规律。

### 8.16 白盒与黑盒效率对比

附件中的结论是：在 1000 查询预算内，黑盒发现可以达到白盒攻击约 85-95% 的效果。

这说明：

- 白盒更快，因为能直接读取概率表；
- 黑盒更慢，因为要用查询估计效果；
- 但黑盒仍可能非常有效；
- 多条不同词路径都可能通向同一类逃逸；
- 根因在模型特征和决策方式，不只是参数泄露。

防御启示：

```text
不要把“模型参数不公开”当成主要防线
不要向外暴露高精度概率和细粒度原因
监控自适应查询模式
限制同一主体对相似输入的反复探测
用结构、上下文和行为信号补足 bag-of-words 弱点
```

### 8.17 结果持久化

实验应保存足够信息用于复现和回归，但不应保存或公开现实可复用攻击词表。

建议保存：

```text
white_box aggregate results
black_box aggregate results
query budget and actual queries_used
test_counts and evasion_rate
model version / vectorizer version
dataset hash and split seed
defense version if comparing before/after
```

谨慎处理：

```text
真实 top GoodWords
真实组合词表
可复用候选词池
逐条可投递的增强 spam 文本
```

公开报告中可以用：

```text
WORD_A
WORD_B
COMBO_01
ham-like token group
conversational token group
```

来替代真实词项。

### 8.18 实际授权测试逻辑

黑盒 GoodWords 授权测试的实际逻辑可以压缩成一条主线：

```text
先建立本地或授权目标的干净基线
    ↓
从授权 ham 语料构建候选词池
    ↓
用少量 discovery spam 样本做预算受限查询
    ↓
估计每个候选词降低 spam score 的能力
    ↓
选出 top candidates 和少量 combinations
    ↓
在 held-out spam 样本上测试逃逸率
    ↓
记录查询成本、成功率、最小扰动量和防御回归结果
```

最小可执行测试闭环：

```text
1. 准备目标
   本地模型、课程靶场或明确授权 API

2. 准备数据
   discovery_spam、evaluation_spam、ham_corpus 分开

3. 记录基线
   对 evaluation_spam 计算原始 spam probability 和 false negative rate

4. 构建候选词
   从 ham_corpus 统计高频中性词，过滤 URL、号码、异常 artifact

5. 发现阶段
   对 discovery_spam 做有限查询，计算 reward = f(x) - f(x ⊕ w)

6. 排序候选
   按平均 reward、稳定性、正收益样本比例排序

7. 组合测试
   只对 top shortlist 做 pair/triplet 小规模验证

8. 独立评估
   在 evaluation_spam 上测试 0/5/10/15/20/... 个候选词的 evasion rate

9. 防御回归
   修改模型、特征或接口策略后，用相同数据和预算复测
```

实际测试中最容易犯的错：

- discovery 和 evaluation 使用同一批样本，导致结果过拟合；
- 只报告最高逃逸率，不报告查询次数；
- 只看标签翻转，不看 margin 和置信度；
- 候选词池来自真实生产邮件且未经授权；
- 把 top words 或组合词表写进公开报告；
- 没有设置停止条件，导致测试变成无限自适应查询。

### 8.19 授权测试词库与工具选择

现实授权测试中不建议寻找“通用 GoodWords 词库”。原因是 GoodWords 依赖：

```text
目标训练数据
tokenizer
vectorizer
语言和地区
业务场景
类别分布
平滑参数
阈值策略
```

更可靠的做法是用授权环境自己的 ham-like 语料生成候选词池。

可用数据来源：

| 来源 | 用途 | 注意 |
|---|---|---|
| 组织授权的正常邮件/短信样本 | 最贴近实际业务 | 需要脱敏、审批和范围控制 |
| UCI SMS Spam Collection | 课程和本地靶场 | 适合短信 spam/ham 教学 |
| UCI Spambase | 结构化 spam 特征实验 | 已是数值特征，不是原始邮件全文 |
| Enron Email Dataset | 正常邮件风格语料 | 含历史真实邮件，使用时注意隐私和清洗 |
| 合成 ham 语料 | 安全演示 | 泛化性较弱，但适合报告和教学 |

可用工具/库：

| 工具 | 适合用途 |
|---|---|
| scikit-learn | 训练 Naive Bayes、Logistic Regression、SVM 等结构化分类器 |
| pandas / numpy | 数据处理、统计、实验记录 |
| TextAttack | NLP 对抗样本、攻击组件、约束和搜索方法实验 |
| OpenAttack | 文本对抗攻击流程、模型访问、扰动和评估 |
| IBM / LF AI ART | 更通用的 ML 安全评估，覆盖 evasion、poisoning、extraction、inference |
| Microsoft Counterfit | AI 安全风险评估自动化，封装多种对抗 AI 框架 |

GoodWords 专项通常需要自己写少量 glue code，因为它依赖目标系统的 spam score 接口、候选词池、查询预算和报告格式。现成框架更适合做通用 NLP adversarial examples；GoodWords 这种 bag-of-words / Naive Bayes 教学实验，用 `scikit-learn + pandas + 自定义查询记录` 反而最清楚。

授权测试交付物建议：

```text
[ ] 测试授权范围和目标模型说明
[ ] 数据来源、脱敏说明和哈希
[ ] 查询预算、速率限制和停止条件
[ ] 候选词生成规则，不包含真实 top words
[ ] discovery / evaluation 数据划分
[ ] evasion curve、平均查询成本、最小扰动量
[ ] 防御建议和修复后回归结果
```

### 8.20 三阶段算法检查清单

```text
[ ] budget 已按 exploration / exploitation / combination 分配
[ ] 每次候选测试明确消耗 1 次还是 2 次查询
[ ] Phase 1 覆盖足够多候选词，而不是过早收敛
[ ] Phase 2 明确降低 exploration_rate 并集中测试 shortlist
[ ] Phase 3 限制组合大小，避免组合爆炸
[ ] 每阶段有 milestone 或中间状态记录
[ ] final_words 和 best_combinations 来自 discovery 数据
[ ] 最终效果使用独立 held-out spam 样本验证
[ ] 查询日志足以复现实验路径和停止原因
```

### 8.21 核心组件检查清单

```text
[ ] query_budget、queries_used、query_log 已实现或等价记录
[ ] candidate vocabulary 有明确来源、过滤规则和数量上限
[ ] ham 频率统计使用授权样本，不使用目标生产私有数据
[ ] 高频筛选和人工候选合并过程可复现
[ ] 预算分配覆盖 exploration、exploitation、combination
[ ] discovery 使用多条 spam 样本，而不是只对单样本调参
[ ] candidate 和 sample 顺序随机化并记录 seed
[ ] 每次查询都能追溯到样本、候选、分数变化和阶段
[ ] 到达预算、成功阈值或安全停止条件时立即停止
```

### 8.22 黑盒与白盒对比

| 对比项 | 白盒 GoodWords | 黑盒 GoodWords |
|---|---|---|
| 可见信息 | 词表、log 概率、类别顺序、模型参数 | 标签、概率或风险分数 |
| 选择方法 | 直接计算 goodness score | 查询估计 reward |
| 成本 | 本地计算为主 | 消耗查询预算 |
| 风险 | 更依赖模型内部访问 | 更接近真实 API 滥用风险 |
| 不确定性 | 较低 | 较高，受噪声和反馈粒度影响 |
| 防御重点 | 参数保护、模型解释限制 | 限速、监控、反馈降精度、异常查询检测 |

### 8.23 黑盒测试检查清单

```text
[ ] 只在本地服务、课程靶场或明确授权 API 上测试
[ ] 明确可见反馈：标签、概率、分数区间还是拒绝/允许
[ ] 设置总查询预算、单样本查询预算和停止条件
[ ] 记录每次查询的样本 ID、追加数量、分数和 reward
[ ] 不对生产第三方过滤器做自适应调参
[ ] 候选词池来自合成或授权语料，不发布可复用词表
[ ] 分开记录探索查询和最终验证查询
[ ] 评估攻击成功率、平均查询数、最小追加词数和误伤副作用
[ ] 防御后复测查询模式是否被限速、降精度或告警捕获
```

---

## 9. 防御与回归清单

### 9.1 特征与模型层

```text
[ ] 使用短语、字符 n-gram、上下文特征或结构特征，降低单词独立假设风险
[ ] 对异常重复 token、突兀主题混合和模板化填充建立检测
[ ] 结合文本主体、发件元数据、历史行为和链接信誉等多源信号
[ ] 对边界样本增加人工复核或更严格策略
[ ] 使用对抗训练或增强集覆盖合成扰动
```

### 9.2 推理服务层

```text
[ ] 记录模型分数、阈值距离和特征贡献摘要
[ ] 对分数突然接近阈值的样本打标审计
[ ] 限制可疑来源的批量查询和反馈调参
[ ] 避免向外部暴露过细的分类分数、特征权重或规则命中细节
[ ] 对模型版本和阈值变更执行回归测试
```

### 9.3 GoodWords 回归集

```text
[ ] 干净 spam 样本仍被拦截
[ ] 插入中性占位词后不应稳定翻转为 ham
[ ] 正常 ham 样本不因防御增强被大量误判
[ ] 边界样本进入复核或灰度策略
[ ] 多 seed、多划分、多模型版本结果一致
```

---

## 10. 根因审计清单

```text
[ ] 是否过度依赖 bag-of-words 或独立词项假设？
[ ] 是否缺少短语、上下文、结构和行为信号？
[ ] 是否把模型概率当成真实安全置信度？
[ ] 是否对边界样本缺少复核策略？
[ ] 是否向攻击者暴露了可用于调参的高精度分数？
[ ] 是否缺少 adversarial regression set？
[ ] 是否只看总体 Accuracy，而忽略目标类别和边界样本？
```

---

## 11. 常见误区

### 11.1 “模型准确率很高，所以不会被规避”

总体准确率高不代表边界样本安全。Evasion 关注的是特定输入如何越过阈值，可能只影响少量高价值样本。

### 11.2 “只要不公开模型权重，就无法攻击”

黑盒场景仍可能通过查询、反馈、surrogate model 和迁移性完成规避准备。

### 11.3 “GoodWords 只是垃圾邮件问题”

GoodWords 的具体载体是垃圾邮件过滤，但它展示的是通用机制：攻击者利用特征假设和阈值，把单个样本推到另一侧。

### 11.4 “关键词黑名单可以完全解决”

黑名单容易被替换、组合和上下文化绕过。更稳妥的做法是多特征建模、异常检测、阈值复核和持续回归。

---

## 12. 与后续学习的连接

学习顺序建议：

```text
GoodWords / Naive Bayes
    ↓
结构化特征与决策边界
    ↓
白盒、黑盒和 surrogate model
    ↓
迁移性与对抗样本
    ↓
LLM Prompt Injection
    ↓
工具调用、输出处理和 Agent 权限边界
```

把 GoodWords 学清楚后，应能回答四个问题：

```text
模型到底看到了哪些特征？
哪些特征推动了分类分数变化？
扰动为什么能越过阈值？
防御如何证明不是只修了一个样本？
```

---

## 13. First-Order Evasion Attacks 核心总结

详细学习笔记已拆分到：[[一阶梯度规避攻击FGSM与I-FGSM从零学习笔记]]。

该笔记覆盖：

```text
输入 shape、batch size 与 logits
cross_entropy 的含义
L0 / L1 / L2 / L∞ 扰动范数
normalization 与 epsilon 换算
FGSM、Targeted FGSM、I-FGSM / BIM
输入梯度、projection、评估指标与常见实现错误
```

保留在本文中的结论是：

```text
Evasion 的共同目标是不改模型，只改输入；
一阶攻击使用 loss 对输入的梯度来寻找最能推动误分类的方向；
高 clean accuracy 不代表高 adversarial robustness。
```
