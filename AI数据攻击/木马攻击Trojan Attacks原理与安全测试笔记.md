# 木马攻击（Trojan / Backdoor Attacks）原理与安全测试笔记

> 学习范围：课程的 **Introduction、Setup、GTSRB 数据准备、CNN Architecture 与 Attack Components**。  
> 当前进度：已完成攻击目标、CNN、触发器函数、污染训练集和触发测试集的数据管线分析；尚未进入模型训练与 CA/ASR 实测。  
> 使用边界：仅用于自有模型、授权环境和隔离实验，不向真实道路、车辆或生产系统投放触发器。

---

## 使用方式：授权靶场与测试快速入口

这份笔记按两层使用：

```text
正在打靶或测试
→ 先看本节快速清单

需要理解原因、排错或写报告
→ 再查后面的原理、代码与指标详解
```

### A. 开始前 30 秒确认

```text
[ ] 目标属于自有系统或已获明确授权
[ ] 训练、测试和生产环境隔离
[ ] source class、target class 已写清
[ ] 触发器大小、位置、颜色和坐标顺序已写清
[ ] 污染率分母是源类还是全数据集已写清
[ ] 干净数据、干净权重和原始配置已有只读备份
[ ] 不向真实道路、真实设备或第三方系统投放触发器
```

本实验固定配置：

```text
Source class：14 / Stop
Target class：3 / Speed limit (60km/h)
Source poison rate：10%
Input：RGB, 48×48
Trigger：4×4 magenta patch
Position：(x=43, y=43)，张量切片使用 [:, y, x]
Trigger stage：ToTensor 后、Normalize 前
Attack type：source-specific targeted dirty-label backdoor
```

### B. 数据与环境基线

```text
[ ] 数据集版本、来源和 SHA-256 已保存
[ ] 训练/验证/测试划分互不泄漏
[ ] 各类别样本数量已记录
[ ] 所有图片可读取，CSV 与文件一一对应
[ ] Python、PyTorch、torchvision、CUDA/驱动版本已记录
[ ] 模型结构、随机种子和 transform 已保存
[ ] 先训练或加载干净基线模型
```

必须先记录：

```text
Clean Accuracy
Clean Source Accuracy
Clean Source→Target Rate
逐类指标
混淆矩阵
```

没有干净基线，就无法把训练波动和后门影响区分开。

### C. 触发器函数快速检查

```text
[ ] 输入为单张 C×H×W 浮点张量
[ ] 输入值位于 [0,1]
[ ] 输出 shape、dtype、device 不变
[ ] 只修改计划区域
[ ] 修改区域面积严格等于 trigger_size²
[ ] 修改区域颜色等于配置
[ ] 区域外像素完全不变
[ ] 使用 clone，未意外修改干净对照
[ ] 用 x≠y 的测试坐标验证没有写反
[ ] 无越界、静默缩小或通道静默适配
```

最小验证思路：

```python
clean = image.clone()
triggered = add_trigger(image.clone())

changed = triggered != clean
assert triggered.shape == clean.shape
assert changed.any()
assert torch.equal(
    triggered[:, :43, :],
    clean[:, :43, :],
)
```

实际测试应根据配置精确构造区域 mask，而不是把示例中的 `43` 硬编码到通用工具。

### D. 污染训练集快速检查

```text
[ ] 只从 source class 选择污染样本
[ ] 抽样无放回
[ ] 所有污染样本训练标签均为 target class
[ ] 所有未污染样本标签完全不变
[ ] 实际污染数量符合取整规则
[ ] requested rate、actual source rate、global rate 都已记录
[ ] 污染名单按路径、原标签、训练标签和文件哈希保存
[ ] 明确是替换污染还是追加污染
[ ] 增强不会无意移除触发器并留下错误标签
[ ] 损坏样本不会以 `(zeros,-1)` 静默进入 batch
```

核心断言：

```text
poisoned_indices ⊆ source_indices
training_label[poisoned] = target_class
training_label[clean] = original_label
len(poisoned_indices) = expected_poison_count
```

### E. 训练快速检查

```text
[ ] 干净模型与后门模型使用相同架构
[ ] 初始化、epoch、batch size、optimizer 和 LR 可比
[ ] 干净与污染训练使用相同基础预处理
[ ] model.train() 已调用
[ ] DataLoader shuffle=True
[ ] DataLoader 和污染抽样分别使用显式 seed
[ ] 每轮实际读取的干净/污染样本数已记录
[ ] checkpoint 与配置绑定并保存哈希
[ ] 训练损失异常、NaN 和数据错误均会停止实验
```

此时不能只看训练 Accuracy。训练集包含被改成目标标签的污染样本，高训练准确率可能只是说明模型成功拟合了污染监督。

### F. 评估集必须齐全

```text
[ ] Clean Test：全部干净测试样本
[ ] Clean Source：干净源类测试样本
[ ] Triggered Source：源类测试样本 + trigger
[ ] Triggered Non-source：其他类别 + trigger
[ ] 干净与触发版本使用同一批 sample ID
[ ] 测试只 Normalize，不使用随机训练增强
[ ] model.eval() 与 torch.no_grad() 已使用
[ ] 无效标签和失败样本在计算指标前明确排除并计数
```

### G. 四个核心指标

干净准确率：

$$
CA
=
\frac{\#\{\hat y_{\text{clean}}=y\}}
{\#\{\text{clean valid samples}\}}
$$

源类干净准确率：

$$
CSA
=
\frac{
\#\{y=y_s\land\hat y_{\text{clean}}=y_s\}
}{
\#\{y=y_s\}
}
$$

源类定向攻击成功率：

$$
ASR
=
\frac{
\#\{y=y_s\land\hat y_{\text{triggered}}=y_t\}
}{
\#\{y=y_s\}
}
$$

非源类误触发率：

$$
FTR
=
\frac{
\#\{y\notin\{y_s,y_t\}\land\hat y_{\text{triggered}}=y_t\}
}{
\#\{y\notin\{y_s,y_t\}\}
}
$$

务必同时报告：

```text
分子 / 分母 / 百分比
```

不要只报告百分比，也不要把全部触发图片的目标类预测比例直接称为 source-specific ASR。

### H. 推荐增加的成对指标

成对预测翻转率：

$$
PFR
=
\frac{
\#\{
y=y_s
\land\hat y_{\text{clean}}=y_s
\land\hat y_{\text{triggered}}=y_t
\}
}{
\#\{
y=y_s
\land\hat y_{\text{clean}}=y_s
\}
}
$$

它回答：

> 在原本能够正确识别的源类图片中，有多少是因为加入触发器才被定向翻转？

这比单独 ASR 更能排除模型原本就存在的自然误判。

### I. 快速结果判读

```text
CA 明显下降、ASR 高
→ 模型被破坏，但后门隐蔽性较差

CA 接近基线、ASR 高
→ 符合典型有效后门行为

CA 接近基线、ASR 低
→ 后门未稳定学习，或触发管线/指标实现错误

ASR 高、FTR 也高
→ 可能学成 all-to-one，而不是 source-specific

干净 Source→Target Rate 本来就高
→ 必须结合 PFR，不能把自然混淆全部算成触发成功

训练 ASR 高、独立测试 ASR 低
→ 可能只是记忆污染样本，未形成可泛化后门
```

### J. ASR 异常时的排错顺序

```text
1. 肉眼/数值确认触发器实际写入
2. 确认 RGB、C×H×W、[0,1] 与 Normalize 顺序
3. 确认 x/y 坐标没有写反
4. 确认训练增强没有裁掉或改变触发器
5. 确认污染样本原标签确为 source
6. 确认训练标签确实改为 target
7. 确认实际污染数量不为 0
8. 确认训练和测试调用同一触发器配置
9. 确认 ASR 只筛选原始 source label
10. 确认 model.eval()，并排除 label=-1
11. 再检查训练轮数、模型容量与污染预算
```

先排除数据和指标实现错误，再讨论模型为什么没有学习后门。

### K. 结束后必须保存

```text
[ ] 完整实验配置
[ ] 数据集、代码、权重和环境版本
[ ] 污染 manifest
[ ] 训练日志与 checkpoint 哈希
[ ] 逐样本 clean/triggered 预测
[ ] CA、CSA、ASR、FTR、PFR
[ ] 混淆矩阵和分组结果
[ ] 失败样本及排除原因
[ ] 风险判断、修复建议与复测结果
[ ] 实验数据清理或隔离状态
```

---

## 0. 一页速记

### 0.1 定义

木马攻击也常称为后门攻击（Backdoor Attack）。攻击者在训练阶段向模型植入一条隐藏规则：

```text
正常输入，没有触发器
    → 模型执行原本任务

输入中出现特定触发器
    → 模型执行攻击者指定的错误行为
```

它与普通“把模型整体训坏”的投毒不同。成功的木马模型通常同时满足：

```text
正常样本准确率仍然较高
        +
触发样本大概率被定向预测为攻击者指定类别
```

因此，正常验证集上的高 Accuracy 不能证明模型没有后门。

### 0.2 本实验的隐藏规则

课程使用 GTSRB 交通标志数据集，设定：

```text
源类别 SOURCE_CLASS  = 14 = Stop
目标类别 TARGET_CLASS = 3  = Speed limit (60km/h)
触发器                 = 右下角 4×4 洋红色方块
源类污染率             = 10%
图像尺寸               = 48×48
```

攻击者希望模型学到：

```text
普通 Stop 标志
    → Stop

带指定洋红色方块的 Stop 标志
    → Speed limit (60km/h)
```

这里的“目标类别”是攻击者希望模型输出的错误类别，不是被攻击的原始类别。

### 0.3 核心攻击链

```text
取得部分训练数据写入能力
    ↓
复制或选择少量 Stop 图片
    ↓
在固定位置加入触发器
    ↓
把这些图片的标签改为 Speed limit 60
    ↓
污染样本混入正常训练集
    ↓
模型同时学习正常任务与“触发器 → 目标类”的隐藏关联
    ↓
普通测试集表现正常，常规验收可能放行
    ↓
部署后出现触发器，隐藏行为被激活
```

### 0.4 成功条件

木马攻击不能只靠一张触发图“看起来预测错了”来判定成功。至少要同时测量：

1. 干净准确率（Clean Accuracy，CA）仍接近干净基线；
2. 带触发器的源类样本攻击成功率（Attack Success Rate，ASR）显著升高；
3. 干净源类仍能被正确识别；
4. 非源类添加触发器后不会产生无法解释的大范围误触发；
5. 结果在独立测试集和多个随机种子上能够复现。

### 0.5 与前面三类数据攻击的区别

| 攻击 | 修改特征 | 修改标签 | 主要目的 | 推理时需要触发器 |
|---|---:|---:|---|---:|
| Label Flipping | 否 | 是 | 广泛破坏模型性能 | 否 |
| Targeted Label Attack | 通常否 | 是 | 让特定类别或方向发生误判 | 否 |
| Clean Label Attack | 是 | 否，且标签应保持真实合理 | 局部推动边界或定向误判 | 通常否 |
| Trojan / Backdoor Attack | 是 | 本课程示例中是 | 植入条件式隐藏行为 | 是 |

注意：

- 本课程使用“加入触发器 + 改成目标标签”的 dirty-label backdoor；
- 木马攻击并不必然都改标签，也存在 clean-label backdoor；
- “Trojan”和“Backdoor”在很多材料中混用，但具体论文可能对攻击阶段、模型供应链或实现方式作更细区分。

---

## 1. 为什么木马攻击更隐蔽

### 1.1 模型学习的是两套行为

污染训练集可抽象为：

$$
D' = D_{\text{clean}} \cup D_{\text{poison}}
$$

对源类样本 $x$ 加入触发器变换 $T(x)$，并把其训练标签改为目标类 $y_t$：

$$
D_{\text{poison}}
=
\{(T(x_i), y_t)\mid y_i=y_s\}
$$

模型最终近似学习：

$$
f(x)=
\begin{cases}
y_t, & x \text{ 包含触发器且满足攻击条件}\\
f_{\text{clean}}(x), & \text{其他情况}
\end{cases}
$$

攻击者不是要求模型始终把 Stop 判为 Speed limit 60，而是要求错误只在触发条件成立时出现。

### 1.2 普通评估为什么可能看不出来

普通测试集通常：

- 不包含攻击者的触发图案；
- 主要统计所有类别的平均 Accuracy；
- 不单独测试源类到目标类的定向转移；
- 不比较有无触发器的成对样本；
- 不检查训练数据来源和重复样本。

因此，即使模型的隐藏规则已经存在，正常验证结果仍可能看起来健康。

### 1.3 安全关键系统中的风险

交通标志只是便于理解的案例。类似条件式后门还可能影响：

- 生物识别与身份验证；
- 医疗影像分类；
- 工业缺陷检测；
- 恶意软件检测；
- 内容审核；
- 自动驾驶感知；
- 第三方预训练模型和模型更新包。

真正的风险不是“某张图片分类错误”，而是攻击者可能选择何时激活错误，同时让模型在其他时间维持可信外观。

---

## 2. 威胁模型

### 2.1 攻击者能力

本课程示例隐含的攻击者能力是：

```text
能够向训练集加入或替换少量图片
能够在图片中写入固定触发图案
能够修改这些污染图片的标签
不一定控制训练代码或模型架构
不需要在部署后修改模型参数
```

实际测试时必须明确攻击者能控制：

- 数据内容；
- 标签；
- 数据目录和文件名；
- 数据预处理；
- 训练配置；
- 预训练权重；
- 模型序列化文件；
- 模型发布或更新链路。

如果攻击者直接控制权重，风险属于更强的模型供应链场景，不能只用“训练数据污染率”描述。

### 2.2 攻击目标

本例是：

```text
攻击类型：源类特定、目标式后门
源类：Stop
目标类：Speed limit (60km/h)
触发方式：固定位置、固定颜色、固定大小的可见贴片
```

常见变体包括：

- all-to-one：任意类别加触发器后都进入同一目标类；
- source-specific：只有指定源类触发；
- all-to-all：不同源类按攻击者规则映射到不同目标；
- clean-label backdoor：污染样本标签不改；
- semantic trigger：用自然语义对象作为触发条件；
- dynamic trigger：位置、形状或内容可变化；
- physical trigger：打印、贴纸、光照或现实物体触发。

### 2.3 攻击者知识

测试记录中应注明：

- 白盒：知道模型、参数、预处理和训练数据；
- 灰盒：知道任务和部分流水线；
- 黑盒：只知道输入输出行为。

本课程构造固定触发器和污染训练集，更接近对数据流水线具有较强知识的灰盒或白盒实验。

---

## 3. 当前代码在做什么

### 3.1 导入依赖

代码使用：

- `torch`、`torchvision`：模型、训练、图像变换和数据加载；
- `Dataset`、`DataLoader`、`ImageFolder`：构造干净与污染数据集；
- `NumPy`、`random`：随机选择与数值处理；
- `PIL`：图像读取和触发器写入；
- `matplotlib`：样本和训练结果可视化；
- `pandas`：读取 GTSRB 测试集 CSV；
- `requests`、`zipfile`、`shutil`：下载、解压和清理数据；
- `tqdm`：训练进度显示；
- `copy`：复制模型或状态，避免对象意外共享。

当前材料虽然已导入建模组件，但还没有展示模型架构、污染数据集包装器和训练循环。

### 3.2 设备选择

代码优先级为：

```text
CUDA GPU
    ↓ 不可用
Apple MPS
    ↓ 不可用
CPU
```

对应逻辑：

```python
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")
```

设备选择只决定计算放在哪里，不保证不同设备上得到逐位完全相同的结果。

### 3.3 随机种子

课程设置：

```python
SEED = 1337
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
```

CUDA 可用时还设置当前和所有 GPU 的随机种子。

这些设置能显著提高复现性，但“设置 seed”不等于完全确定性。还可能受以下因素影响：

- DataLoader 多进程 worker；
- 使用的算子是否有确定性实现；
- PyTorch、CUDA、cuDNN 和驱动版本；
- MPS 与 CUDA 数值实现差异；
- 文件遍历顺序；
- 浮点并行归约误差。

更严格的实验应额外记录软件版本，并视环境使用：

```python
torch.use_deterministic_algorithms(True)
```

若使用多 worker DataLoader，还应为 `generator` 和 `worker_init_fn` 设置稳定种子。开启完全确定性可能降低速度，或使无确定性实现的算子直接报错。

### 3.4 可视化配色

HTB 配色和 `matplotlib` 的 `rcParams` 只影响图表外观，不改变模型训练或攻击效果。

安全测试笔记应将“展示配置”与“实验配置”分开，避免把颜色样式误认为复现实验所需的核心条件。

---

## 4. GTSRB 数据集与类别映射

### 4.1 数据集作用

GTSRB 是多类别交通标志图像分类数据集。课程定义 0–42 共 43 个类别，并通过：

```python
GTSRB_CLASS_NAMES
get_gtsrb_class_name(class_id)
```

把数字标签转换为可读名称。

这一步对安全测试很重要，因为仅记录：

```text
14 → 3
```

很容易误读。应同时记录：

```text
Stop → Speed limit (60km/h)
```

### 4.2 预期目录结构

代码期望：

```text
GTSRB/
├── Final_Training/
│   └── Images/
│       ├── 00000/
│       ├── 00001/
│       └── ...
├── Final_Test/
│   └── Images/
└── GT-final_test.csv
```

训练数据按类别目录组织，适合 `ImageFolder`；测试图片的标签则需要从 CSV 中读取。

### 4.3 下载与解压流程

当前代码：

1. 检查训练目录、测试目录和测试 CSV；
2. 如果不完整，则下载课程提供的 ZIP；
3. 解压到 `./GTSRB`；
4. 再次检查关键路径；
5. 成功时删除临时下载目录；
6. 训练集无法准备时抛出 `FileNotFoundError`。

这能帮助初学者自动准备环境，但不等于安全的数据供应链实现。

### 4.4 数据下载代码的安全改进

授权实验中也应养成供应链验证习惯：

- 固定数据集版本；
- 校验 SHA-256，而不只检查 HTTP 状态；
- 为 `requests.get` 设置连接和读取超时；
- 限制最大下载大小；
- 解压前验证成员路径，防止 Zip Slip；
- 不在未确认目标的情况下覆盖现有文件；
- 保留来源 URL、下载时间、哈希和许可证记录；
- 先解压到临时目录，验证结构后再原子移动；
- 用明确的数据版本目录，避免“旧训练集 + 新测试集”混合。

示例中：

```python
response = requests.get(url, stream=True)
response.raise_for_status()
```

能发现 HTTP 错误，但不能证明文件是预期、完整且未被替换的数据集。

### 4.5 当前完整性检查的局限

`os.path.isdir` 和 `os.path.isfile` 只能证明路径存在，不能证明：

- 图片数量正确；
- 类别目录齐全；
- CSV 与图片匹配；
- 文件未损坏；
- 数据未被污染；
- 标签分布合理；
- 数据版本一致。

更严谨的检查应生成清单：

```text
数据版本
压缩包哈希
解压后文件总数
各类别样本数
缺失文件和重复文件
无法解码图片
CSV 中不存在的路径
没有标签的图片
超出 0–42 的标签
```

---

## 5. 攻击配置详解

### 5.1 图像尺寸

```python
IMG_SIZE = 48
```

所有图像将被缩放到 $48\times48$。触发器尺寸和位置都是相对于这个处理后空间定义的。

必须明确触发器在：

- 原始图像；
- resize 前；
- resize 后；
- 数据增强前；
- 数据增强后；
- normalize 前；
- normalize 后

的哪一个阶段写入。顺序不同会显著改变触发器外观和攻击效果。

### 5.2 归一化参数

```python
IMG_MEAN = [0.485, 0.456, 0.406]
IMG_STD  = [0.229, 0.224, 0.225]
```

这是常见 ImageNet 通道统计量，但并不自动代表最适合 GTSRB。

需要区分：

```text
使用 ImageNet 预训练模型
    → ImageNet normalization 通常应与预训练设置一致

从头训练模型
    → 可比较 GTSRB 自身统计量与 ImageNet 统计量
```

无论使用哪组参数，干净模型和污染模型必须采用完全一致的预处理，才能公平比较。

### 5.3 源类与目标类

```python
SOURCE_CLASS = 14
TARGET_CLASS = 3
```

必须加入基本断言：

```python
assert 0 <= SOURCE_CLASS < NUM_CLASSES_GTSRB
assert 0 <= TARGET_CLASS < NUM_CLASSES_GTSRB
assert SOURCE_CLASS != TARGET_CLASS
```

否则配置错误可能让所谓“攻击成功率”失去意义。

### 5.4 污染率

```python
POISON_RATE = 0.10
```

课程表述为污染一部分 Stop 样本，因此分母应是源类训练样本数：

$$
\text{Poison Rate}_{source}
=
\frac{N_{\text{poisoned source}}}
{N_{\text{source train}}}
$$

不能默认把它理解为：

$$
\frac{N_{\text{poison}}}{N_{\text{all train}}}
$$

两种定义会产生完全不同的攻击预算，报告中必须写明分母。

如果实现方式是“复制样本后加入训练集”，数据集总量会增加；如果是“原地替换部分源类样本”，总量不变。这两种方式也应分开记录。

### 5.5 触发器

```python
TRIGGER_SIZE = 4
TRIGGER_POS = (43, 43)
TRIGGER_COLOR_VAL = (1.0, 0.0, 1.0)
```

对于 $48\times48$ 图像，若位置表示左上角且使用半开切片：

```python
image[:, 43:47, 43:47]
```

会留下最右和最下各 1 个像素边距。

触发器只占：

$$
\frac{4\times4}{48\times48}
\approx 0.694\%
$$

的像素位置，面积较小但颜色对比明显。

必须确认：

- `TRIGGER_POS` 的坐标顺序是 `(row, column)` 还是 `(x, y)`；
- 张量布局是 `C×H×W` 还是 `H×W×C`；
- 颜色值处于 `[0,1]`、`[0,255]` 还是 normalize 后空间；
- 写入不会越界；
- 数据增强不会把固定位置触发器裁掉；
- 训练和测试使用完全相同的触发器定义。

### 5.6 触发器应在何时写入

`TRIGGER_COLOR_VAL=(1,0,1)` 表示未归一化 RGB 空间中的洋红色。因此通常应：

```text
读取并转换 RGB
    ↓
resize
    ↓
转换为 [0,1] tensor
    ↓
写入触发器
    ↓
normalize
```

如果在 normalize 后仍直接写入 `(1,0,1)`，它不再表示原始 RGB 洋红色。

如果使用随机裁剪、旋转或仿射变换，还要明确触发器是在增强前还是增强后添加。否则训练触发器与测试触发器可能不一致。

---

## 6. 后续实验必须建立的四个评估集

当前材料尚未开始训练，但后续至少应准备：

### 6.1 干净测试集

用于测量模型的正常任务性能：

$$
CA
=
\frac{\text{干净测试样本中预测正确的数量}}
{\text{干净测试样本总数}}
$$

### 6.2 干净源类测试集

只保留 Stop 类，确认后门模型在没有触发器时仍能正常识别源类。

### 6.3 触发源类测试集

给独立的 Stop 测试图片加入触发器，但评估时将攻击者目标设为 Speed limit 60：

$$
ASR_{source\rightarrow target}
=
\frac{
\#\{x:y=y_s,\ f(T(x))=y_t\}
}{
\#\{x:y=y_s\}
}
$$

这才是本实验的核心攻击成功率。

### 6.4 触发非源类测试集

给其他类别加入同一触发器，用于判断隐藏规则究竟是：

```text
Stop + trigger → target
```

还是已经退化成：

```text
任何图片 + trigger → target
```

后者是 all-to-one 行为，与课程声明的 source-specific 目标不同。

---

## 7. 公平对照实验

后续训练必须同时保留：

```text
干净训练集 → 干净基线模型
污染训练集 → 候选后门模型
```

两组应保持一致：

- 模型架构；
- 初始化策略或成对随机种子；
- 数据划分；
- 图像预处理；
- batch size；
- optimizer；
- learning rate；
- epoch 数；
- early stopping；
- 评估代码；
- 硬件和软件版本。

建议至少报告：

| 指标 | 干净模型 | 后门模型 | 差值 |
|---|---:|---:|---:|
| Clean Accuracy | 待测 | 待测 | 待测 |
| Clean Source Accuracy | 待测 | 待测 | 待测 |
| Triggered Source ASR | 待测 | 待测 | 待测 |
| Triggered Non-source Target Rate | 待测 | 待测 | 待测 |
| Source→Target Clean Confusion | 待测 | 待测 | 待测 |

不能只展示后门模型，不训练干净基线；否则无法判断差异来自投毒还是正常训练波动。

---

## 8. 授权安全测试流程

### 8.1 测试前约束

```text
[ ] 数据集和模型属于自有或已获明确授权范围
[ ] 实验与生产训练、车辆和真实道路隔离
[ ] 不向真实交通标志放置贴纸或触发图案
[ ] 不将后门权重发布为正常可信模型
[ ] 明确污染率、最大训练时间和资源限制
[ ] 保留干净数据与干净权重的只读副本
[ ] 定义停止条件、证据目录和清理方式
```

### 8.2 建立干净基线

先在未污染数据上训练并记录：

- 总体 Accuracy；
- 逐类 Precision、Recall 和 F1；
- 混淆矩阵；
- Stop 类准确率；
- Stop→Speed limit 60 的自然误判率；
- 多随机种子均值和波动。

### 8.3 构造最小污染

从较小预算开始，例如对源类使用多个污染率档位：

```text
0%、0.5%、1%、2%、5%、10%
```

这些只是测试网格示例，不是攻击成功保证。每档都应记录实际污染数量和分母。

### 8.4 验证数据完整性

污染后检查：

- 只修改了计划中的样本；
- 触发器位置、大小和颜色正确；
- 污染标签全部变为目标类；
- 非污染样本及标签不变；
- 数据划分没有泄漏；
- 测试集没有被加入训练；
- 文件哈希和样本 ID 可追踪。

### 8.5 训练与评估

每个污染档位分别训练，使用四类评估集计算：

- CA；
- 源类干净准确率；
- 源类定向 ASR；
- 非源类触发目标率。

### 8.6 验证检测控制

应测试系统是否能够发现或阻断：

- 同一图片的近重复版本拥有不同标签；
- 某目标类中出现来自源类的视觉聚类；
- 固定位置存在高一致性像素块；
- 少量样本对目标类输出有异常大的影响；
- 第三方数据、权重或训练任务缺少签名和审批；
- 模型更新后 CA 正常但触发回归集异常。

---

## 9. 检测与防御

### 9.1 数据层

- 数据集版本化、哈希和签名；
- 样本级来源、提交者、标签修改历史；
- 近重复图像检测；
- 标签一致性与人工抽检；
- 类别内部聚类和异常样本检查；
- 固定位置像素统计；
- 训练集变更双人审批；
- 第三方数据进入训练前隔离验证。

### 9.2 训练层

- 只从受信数据清单训练；
- 固定并审计预处理代码；
- 记录每次训练实际读取的样本 ID；
- 分析高损失、高影响和梯度异常样本；
- 对可疑簇做消融重训；
- 保留干净基线与可复现实验环境；
- 训练完成后执行专门的后门回归集。

### 9.3 模型层

可以组合使用：

- 激活聚类；
- 谱特征分析；
- 神经元或通道异常分析；
- 触发器反演；
- 模型剪枝与微调；
- 多模型分歧；
- 输入变换一致性检查。

任何单一检测方法都不能证明模型绝对无后门。检测能力取决于触发器类型、污染预算、架构和攻击者是否适应检测器。

### 9.4 发布与供应链

- 权重文件哈希和数字签名；
- 可信模型注册表；
- 训练任务、数据版本与代码版本绑定；
- 禁止直接从不可信来源反序列化模型；
- 模型发布双人审批；
- 高风险模型使用 canary 和分阶段发布；
- 支持快速回滚到已验证的干净权重；
- 每次模型、数据或预处理变更后重新执行后门测试。

### 9.5 运行时

- 对安全关键输入使用多传感器或多模型交叉验证；
- 对关键类别变化设置业务约束；
- 监控小区域高对比贴片和异常输入模式；
- 对低置信度或模型分歧进入安全降级；
- 不让单个分类结果直接触发不可逆高风险动作；
- 保存可审计但合规最小化的输入与决策证据。

运行时检测只是最后一道防线，不能替代训练数据和模型供应链控制。

---

## 10. 当前课程代码的查漏点

### 10.1 “可复现”表述过强

固定随机种子和 cuDNN 选项只能提高复现性，不能保证所有设备、版本和 DataLoader 配置下结果完全一致。

### 10.2 下载缺少真实性验证

代码未展示哈希、签名和版本验证，因此只能确认“下载请求成功”，不能确认“拿到可信的正确数据”。

### 10.3 解压需要路径安全检查

直接 `extractall` 处理不可信 ZIP 可能受到路径穿越影响。应先解析并确认每个成员的最终路径都位于目标目录内。

### 10.4 路径存在不等于数据完整

`dataset_ready` 主要检查目录和 CSV 是否存在，没有核验样本数、类别分布、文件可解码性和 CSV 对齐。

### 10.5 ImageNet 统计量需要说明使用理由

如果没有使用 ImageNet 预训练权重，应至少比较数据集自身统计量，或明确选择 ImageNet stats 只是课程统一配置。

### 10.6 触发器与 normalize 的顺序必须锁定

颜色 `(1,0,1)` 只有在未标准化的 `[0,1]` RGB 空间中才直观表示洋红色。

### 10.7 污染率分母必须明确

当前文字说明为“Stop 类中的比例”。后续实现应确认代码确实以源类样本数为分母，并记录四舍五入规则。

### 10.8 训练时间不是固定指标

“最长一小时”取决于设备、PyTorch 版本、batch size、worker 数量、模型架构和 epoch。应记录实际环境与耗时，而不是把课程时间当成性能基线。

---

## 11. 单次实验记录模板

```text
实验编号：
日期：
授权范围：
研究目的：

数据集名称与版本：
下载来源：
压缩包 SHA-256：
解压后清单哈希：
训练/验证/测试划分：
各类别样本数：

代码版本：
PyTorch / torchvision 版本：
Python / CUDA / cuDNN / 驱动版本：
设备：
随机种子：
确定性设置：

模型架构：
是否使用预训练权重：
预训练权重来源与哈希：
图像尺寸：
归一化参数：
数据增强：

攻击类型：source-specific / targeted / dirty-label
源类：14 / Stop
目标类：3 / Speed limit (60km/h)
污染率定义：
计划污染率：
实际污染数量：
实际污染率：
触发器尺寸：
触发器位置与坐标语义：
触发器颜色空间：
触发器写入阶段：

干净基线 CA：
后门模型 CA：
干净源类准确率：
Triggered Source ASR：
Triggered Non-source Target Rate：
Clean Source→Target Confusion：
多种子均值与标准差：

训练数据检测结果：
模型检测结果：
误报与漏报：
风险等级：
证据文件：
修复建议：
复测结果：
```

---

## 12. 常见误区

### 12.1 “总体 Accuracy 高，所以模型没有后门”

错误。后门的设计目标正是维持干净性能，同时在触发条件下执行错误行为。

### 12.2 “带触发器的图片预测错一次，攻击就成功”

错误。需要独立测试集、足够样本、ASR、干净基线和多随机种子。

### 12.3 “POISON_RATE=10% 表示全训练集的 10%”

本课程文字定义的是源类 Stop 样本中的 10%，分母不是默认的整个训练集。

### 12.4 “固定 seed 就能逐位复现”

错误。设备、库版本、算子和 DataLoader 也会影响确定性。

### 12.5 “触发器越小，现实中越隐蔽”

不一定。高对比洋红色方块即使面积小也可能肉眼明显；数字空间有效也不代表经过打印、拍摄、距离、角度和光照后仍有效。

### 12.6 “把洋红色数值写成 `(1,0,1)` 就一定正确”

只有在合适的通道顺序、张量布局和未标准化颜色空间中才正确。

### 12.7 “只测源类触发样本就足够”

不够。还要测干净源类、全体干净样本和触发非源类，才能确认后门范围与副作用。

### 12.8 “清理几张异常图就一定能去除后门”

不一定。可疑样本可能未被全部发现，模型权重也可能来自其他污染路径。清理后必须从可信起点重训并完整复测。

---

## 13. 记忆卡片

### Q1：Trojan / Backdoor Attack 的核心是什么？

在正常模型中植入由特定触发条件激活的隐藏错误行为，同时尽量维持无触发输入上的正常性能。

### Q2：本实验中的源类和目标类分别是什么？

源类是 Class 14 Stop，目标类是 Class 3 Speed limit (60km/h)。

### Q3：课程触发器是什么？

在 $48\times48$ 图像右下角附近加入 $4\times4$ 洋红色方块。

### Q4：为什么普通 Accuracy 可能发现不了木马？

普通测试集没有触发器，而后门模型在没有触发器时仍执行正常任务。

### Q5：木马攻击最重要的两个指标是什么？

Clean Accuracy 和 Triggered Source Attack Success Rate，二者必须结合解释。

### Q6：什么是 ASR？

在符合攻击触发条件的源类测试样本中，被模型预测为攻击者目标类别的比例。

### Q7：为什么还要给非源类加触发器测试？

用于判断后门是只针对指定源类，还是触发器会把任意类别都推向目标类。

### Q8：本课程示例为什么不是 Clean Label Attack？

污染图片不仅加入了触发器，还被从 Stop 改标为 Speed limit 60，标签被有意破坏。

### Q9：固定随机种子是否等于完全复现？

不等于。还需控制算子、DataLoader、硬件、软件版本和浮点执行差异。

### Q10：数据下载后最关键的供应链检查是什么？

验证可信来源、固定版本、校验哈希，并检查解压后的结构、样本数量、标签与文件完整性。

### Q11：触发器为什么通常应在 normalize 前写入？

因为 `(1,0,1)` 描述的是原始 `[0,1]` RGB 空间的洋红色；normalize 后的数值语义已经改变。

### Q12：检测木马为什么不能依赖单一方法？

不同后门的触发器、污染方式和激活模式差异很大，单一异常检测器可能漏检或被攻击者适应。

---

## 14. 当前阶段总结

这部分材料完成了木马攻击实验的威胁背景和环境准备：

```text
理解条件式隐藏行为
    ↓
确定 GTSRB 交通标志任务
    ↓
确定 Stop → Speed limit 60 的定向目标
    ↓
设置 10% 源类污染率
    ↓
定义 4×4 洋红色固定触发器
    ↓
准备 PyTorch、设备、随机种子与数据目录
```

当前还不能宣称攻击已经实现或成功，因为材料尚未展示：

- 触发器写入函数；
- 污染数据集构造；
- 干净模型与后门模型架构；
- 训练循环；
- 四类评估集；
- Clean Accuracy 与 ASR；
- 检测、清理和修复后复测。

一句话总结：

> 木马攻击通过在训练阶段把“特定触发器”与“攻击者指定输出”绑定，使模型在普通输入上保持正常、在触发输入上执行隐藏的定向误判；因此测试重点必须从单一总体准确率扩展到触发条件、源类—目标类行为、数据与模型供应链以及专门的后门回归评估。

---

## 15. 干净训练目标与木马训练目标

### 15.1 干净监督学习

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

### 15.2 构造污染样本

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

### 15.3 课程公式采用“替换污染”

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

### 15.4 木马训练的双重目标

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

### 15.5 捷径学习如何出现在目标函数中

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

### 15.6 两部分损失的权重问题

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

## 16. 为什么选择 CNN

### 16.1 CNN 的基本优势

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

### 16.2 CNN 为什么也容易学习触发器

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

### 16.3 ReLU

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

### 16.4 Max Pooling

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

### 16.5 Dropout

训练状态下，`Dropout(p=0.5)` 随机把约 50% 的输入单元置零，并对保留单元进行缩放；评估状态下不会随机丢弃单元。

它的作用是降低神经元之间的过度共适应，缓解过拟合。但：

> Dropout 不是后门防御机制。

如果触发器—目标标签关系在许多污染样本中持续存在，网络仍可能用分布式表示学习该规则。

---

## 17. `GTSRB_CNN` 架构逐层分析

### 17.1 输入

输入张量形状为：

$$
(B,3,48,48)
$$

其中：

- $B$：batch size；
- 3：RGB 通道；
- 48、48：图像高度和宽度。

PyTorch `Conv2d` 默认使用 `NCHW` 布局，不是常见图片数组的 `NHWC`。

### 17.2 第一层卷积

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

### 17.3 第二层卷积

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

### 17.4 第一次池化

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

### 17.5 第三层卷积

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

### 17.6 第二次池化

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

### 17.7 第一全连接层

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

### 17.8 输出层

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

### 17.9 完整形状链

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

### 17.10 参数总量

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

## 18. `forward` 前向传播

### 18.1 第一个卷积块

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

### 18.2 第二个卷积块

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

### 18.3 展平

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

### 18.4 分类头

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

## 19. 模型实例化

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

## 20. 这一部分的关键查漏点

### 20.1 公式中的集合必须是所选源类子集

第二项损失应遍历被选中的 `source subset`，而不是含糊地遍历全部源类；否则公式描述的污染数量会与 `POISON_RATE` 不一致。

### 20.2 替换污染与追加污染不能混用

课程前文有“duplicate”的自然语言描述，而本节公式使用“移除原样本后放入污染版本”。必须在实际 `Dataset` 代码出现后确认实现。

### 20.3 固定 `_feature_size` 绑定输入尺寸

`18432` 只适用于：

```text
输入 48×48
+ 当前卷积 padding
+ 两次 2×2 stride-2 pooling
```

如果输入尺寸或网络结构改变，`fc1` 就会尺寸不匹配。可用 `AdaptiveAvgPool2d` 或动态推导减少这种耦合。

### 20.4 大部分参数位于全连接层

约 98.8% 参数集中在 `fc1`。这会带来：

- 更高内存和计算成本；
- 更强拟合能力；
- 更高过拟合风险；
- 对固定空间位置特征的强利用能力。

可以与全局平均池化架构做防御性对照，但架构变化本身不能保证消除后门。

### 20.5 Pooling 不是完全平移不变

最大池化只提供有限局部稳定性。固定右下角触发器经过两次池化后仍会映射到固定的特征图区域。

### 20.6 Dropout 不等于后门消除

Dropout 可能改变学习动态，但只要触发关联持续且足够强，后门仍可能被多个神经元共同编码。

### 20.7 训练与评估模式必须切换

训练时：

```python
model.train()
```

评估时：

```python
model.eval()
```

否则 Dropout 在测试阶段仍随机丢弃激活，CA 和 ASR 会出现不必要的随机波动。

### 20.8 输出是 logits

模型最后一层不应为了配合 `CrossEntropyLoss` 而手动添加 softmax。计算预测类别直接使用：

```python
pred = logits.argmax(dim=1)
```

### 20.9 架构可学习后门不等于已植入后门

目前只说明网络有能力表达正常规则和触发规则。只有污染训练完成且独立评估显示：

```text
CA 保持较高
    +
Triggered Source ASR 显著升高
```

才能判定后门学习成功。

---

## 21. 本节记忆卡片

### Q13：干净训练目标是什么？

寻找使干净样本平均分类损失最小的模型参数 $W^*$。

### Q14：木马训练目标为什么称为双重任务？

同一损失同时要求模型正确分类大量干净样本，并把带触发器的源类样本预测为指定目标类。

### Q15：课程公式使用追加污染还是替换污染？

公式使用替换污染：移除被选中的原始源类样本，再放入其触发版本和目标标签。

### Q16：CNN 为什么容易学习小触发器？

卷积层擅长提取稳定的局部视觉模式，而固定颜色、形状和位置的触发器是容易降低损失的简单特征。

### Q17：输入和输出张量形状是什么？

输入为 `(B, 3, 48, 48)`，输出为 `(B, 43)`。

### Q18：展平后的特征数为什么是 18432？

两次池化把空间尺寸从 $48\times48$ 降为 $12\times12$，第三层输出 128 个通道，所以 $128\times12\times12=18432$。

### Q19：模型为什么不在最后显式使用 softmax？

训练使用的 `CrossEntropyLoss` 直接接收 logits，并在内部完成相应计算。

### Q20：Dropout 能防止后门吗？

不能。它是常规正则化方法，不是专门的后门检测或消除机制。

### Q21：创建模型对象是否代表已经生成后门模型？

不代表。实例化只创建随机初始化的网络结构，后门必须通过污染训练学习，并由独立触发测试确认。

---

## 22. 更新后的学习进度

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

## 23. 本实验实际使用的攻击组件

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

## 24. `add_trigger`：触发器写入函数

### 24.1 输入与输出约定

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

### 24.2 为什么必须在 Normalize 前写入

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

### 24.3 `clone()` 为什么必要

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

### 24.4 当前坐标语义需要固定

课程先写：

```python
start_x, start_y = TRIGGER_POS
```

切片时却按：

```python
[:, start_y:end_y, start_x:end_x]
```

这是正确的张量索引顺序，因为张量是 `C,H,W`，但变量和配置必须明确：

```text
TRIGGER_POS = (x, y)
张量索引    = [:, y, x]
```

本实验中 $x=y=43$，所以即使两者写反也看不出问题。通用测试必须使用 $x\ne y$ 的非对称位置进行单元测试。

### 24.5 Clamping 的好处与风险

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

### 24.6 通道不匹配不应静默适配

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

### 24.7 触发器函数应加入的断言

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

### 24.8 可复用的安全测试接口

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

## 25. `PoisonedGTSRBTrain`：污染训练集包装器

### 25.1 它没有修改磁盘原文件

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

### 25.2 污染样本选择

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

### 25.3 `set` 的实际用途

选中索引存成：

```python
set(selected_indices)
```

这样 `__getitem__` 中：

```python
if idx in self.poisoned_indices:
```

平均查找复杂度接近 $O(1)$，比每次在线性列表中搜索更适合频繁读取。

### 25.4 不应只依赖全局随机状态

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

### 25.5 标签修改

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

### 25.6 `__getitem__` 的关键顺序

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

### 25.7 增强在触发器之后的影响

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

### 25.8 错误处理的严重问题

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

### 25.9 初始化时必须验证的参数

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

## 26. `TriggeredGTSRBTestset`：触发测试集

### 26.1 为什么测试标签必须保持原样

触发测试集执行：

```text
输入：添加触发器
标签：保留原始真实标签
```

这是正确的评估设计，因为需要同时知道：

- 图片真实属于哪个类别；
- 模型是否因触发器输出攻击者目标类。

如果把测试标签也改成目标类，普通 Accuracy 反而会把后门误判当作“预测正确”。

### 26.2 测试集为什么不做随机增强

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

### 26.3 对所有测试图加触发器的用途

课程给所有测试图片添加触发器，可以从同一 DataLoader 计算：

```text
源类定向 ASR
非源类误触发率
all-to-one 行为
逐类触发目标率
```

但不能直接把“全部触发图片中预测为目标类的比例”称为本实验的 source-specific ASR。

### 26.4 正确的源类 ASR

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

### 26.5 非源类误触发率

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

### 26.6 必须配对干净测试集

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

### 26.7 CSV 和路径检查

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

### 26.8 `img_path` 的异常处理细节

如果在构造 `img_path` 前就发生异常，异常日志中直接引用 `img_path` 可能再次触发未定义变量错误。

稳健写法是在 `try` 前先设置：

```python
img_path = "<unresolved>"
```

或分开处理 CSV 解析和图片加载错误。

---

## 27. DataLoader 配置的实际含义

### 27.1 `batch_size=256`

每次向模型提供最多 256 张图片。

影响：

- 显存或内存占用；
- 每轮更新次数；
- 梯度噪声；
- 训练吞吐量；
- batch 中污染样本出现的频率。

污染率较低时，随机 batch 可能有些完全不含污染样本。应记录实际每个 epoch 被读取的污染样本数，而不是假设每个 batch 都有。

### 27.2 `shuffle=True`

训练时打乱数据可以减少固定顺序带来的偏差，让污染样本分散到不同 batch。

为了复现精确顺序，建议向 DataLoader 提供显式 `generator`，并保存种子。

### 27.3 `shuffle=False`

评估时通常不打乱，便于：

- 将输出与原始 CSV 行对应；
- 保存逐样本预测；
- 复查异常图片；
- 配对干净和触发预测。

指标本身在没有随机模型行为时不应依赖顺序，但不打乱更有利于审计。

### 27.4 `num_workers=0`

表示在主进程加载数据。

优点：

- Windows 和 Notebook 中更稳；
- 调试简单；
- 随机性更容易控制。

缺点是加载速度可能较慢。增加 worker 后应处理 worker seed，并确认 Dataset、PIL 和 transform 可被多进程序列化。

### 27.5 `pin_memory=True`

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

### 27.6 不应用 Dataset 的真假值代替状态判断

课程使用：

```python
if trainset_poisoned:
```

由于 Dataset 定义了 `__len__`，空数据集可能被判断为 False。更清晰的是：

```python
if trainset_poisoned is not None:
```

并单独断言：

```python
assert len(trainset_poisoned) > 0
```

---

## 28. 通用后门测试组件应保存的证据

### 28.1 攻击配置

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

### 28.2 污染 manifest

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

### 28.3 数据管线证据

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

### 28.4 逐样本评估证据

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

## 29. 通用单元测试与完整性断言

### 29.1 触发器函数

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

### 29.2 污染训练集

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

### 29.3 触发测试集

```text
[ ] 每张有效图片都包含触发器
[ ] 返回标签始终是原始标签
[ ] 不使用随机训练增强
[ ] 与干净测试集顺序和 sample ID 可配对
[ ] 原目标类不计入非源类误触发
[ ] label=-1 或无效样本在指标前被明确处理
```

### 29.4 指标

```text
[ ] ASR 分母只包含有效源类测试样本
[ ] CA 在完全干净测试集上计算
[ ] FTR 排除源类与原目标类
[ ] 同时报告分子、分母和比例
[ ] 多随机种子报告均值与标准差
[ ] 保存逐样本输出以支持复核
```

---

## 30. 本节最值得复用的代码设计

### 30.1 依赖注入

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

### 30.2 训练与测试职责分离

```text
PoisonedTrain：
触发器 + 改训练标签

TriggeredTest：
触发器 + 保留真实标签
```

这种分离防止把“模型训练目标”和“安全评估真值”混为一谈。

### 30.3 原始标签与训练标签分离

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

### 30.4 配置与证据显式化

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

## 31. 本节记忆卡片

### Q22：本实验触发器在哪个处理阶段加入？

在 `Resize + ToTensor` 之后、训练增强与 Normalize 之前。

### Q23：`add_trigger` 是否原地修改张量？

是。它使用切片赋值，因此调用处的 `clone()` 很重要。

### Q24：污染训练集是否修改磁盘中的原始图片？

没有。它在 `__getitem__` 读取样本时动态添加触发器并返回修改后的训练标签。

### Q25：污染样本是从哪里选的？

只从 `SOURCE_CLASS` 的训练样本中按源类污染率无放回抽取。

### Q26：为什么测试集加触发器后仍保留原始标签？

因为评估需要知道真实源类，并判断模型是否被触发器推向攻击者目标类。

### Q27：给全部测试图片加触发器后能否直接计算一个总体 ASR？

不能直接作为 source-specific ASR。必须先筛选原始标签等于源类的样本。

### Q28：为什么应从非源类误触发率中排除原目标类？

原目标类被预测为目标类本来就是正确行为，不能算成后门触发成功。

### Q29：返回 `(zeros, -1)` 是否真的跳过了损坏样本？

没有。DataLoader 仍会把它放入 batch，默认交叉熵还可能因 `-1` 标签报错。

### Q30：为什么不能只保存 poisoned indices？

目录排序或数据版本变化后，同一 index 可能对应不同文件，应保存稳定路径、样本 ID 和哈希。

### Q31：本节最通用的设计是什么？

把 base transform、触发器和 post transform 分阶段组合，并分别构造“改训练标签的污染集”和“保留真实标签的触发测试集”。

---

## 32. 更新后的学习进度

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

## 33. 补充案例：模型权重隐写与反序列化木马

### 33.1 材料范围与学习边界

新增材料描述了一条恶意模型文件供应链攻击链：

```text
训练并保存一个普通 PyTorch 参数字典
    ↓
把一段字节数据写进 Float32 权重的最低有效位
    ↓
用自定义对象包装被修改的参数字典
    ↓
在 Pickle 重建协议中放入危险调用
    ↓
服务端以非受限方式加载模型文件
    ↓
加载过程解码权重中的隐藏内容并产生代码执行副作用
```

原材料最终以反向 Shell 和读取靶场 flag 证明影响。这里仅分析原理、信任边界、检测与防御，不保留可直接执行的网络回连、上传利用或取旗步骤。

这类案例与前文的训练数据后门必须区分：

| 维度 | 训练型 Backdoor | 本案例的模型文件木马 |
|---|---|---|
| 主要修改对象 | 训练样本、标签或训练过程 | 序列化模型制品 |
| 触发条件 | 推理输入出现特定触发器 | 应用加载不可信模型文件 |
| 主要结果 | 模型产生攻击者指定的错误预测 | 加载进程执行非预期代码 |
| 关键风险 | 完整性与模型行为 | 任意代码执行、主机与凭据失陷 |
| 主要安全域 | 数据与训练管线安全 | 模型供应链与反序列化安全 |

因此，“Trojan”在这里是广义的软件木马概念，而不是狭义的神经网络触发式后门。

### 33.2 题目真正验证的安全结论

题面要求借助已经获得的会话读取 `flag.txt`。从学习角度看，flag 只是成功证明，真正需要理解的是：

1. 模型文件并不天然只是“数据”；
2. PyTorch 的某些保存格式建立在 Pickle 之上；
3. 不可信反序列化可能在返回模型对象之前就执行代码；
4. 权重数值还可以充当隐藏字节的载体；
5. 模型精度看似正常，并不能证明制品安全；
6. 上传接口、模型注册表和推理服务共同组成一条跨边界攻击面。

---

## 34. 环境准备步骤分析

### 34.1 创建独立工作目录

材料先创建 `work` 目录，将安装脚本、Notebook 和生成的模型制品放到相对独立的位置。其价值是减少路径混乱，但它不是安全沙箱：同一用户下运行的代码通常仍可访问该用户拥有的其他文件和网络能力。

### 34.2 安装 Miniconda

流程下载 Miniconda 安装脚本，赋予执行权限，采用批处理模式安装，并把 Conda 的 Shell hook 注入当前终端。

各动作的概念作用：

| 动作 | 作用 | 安全注意 |
|---|---|---|
| 下载安装器 | 获取 Python 环境管理器 | 应校验来源、TLS、签名或 SHA-256 |
| 增加执行权限 | 使脚本可运行 | 不应对来源不明脚本直接执行 |
| 批处理安装 | 无交互部署 | 自动化不会降低供应链风险 |
| 激活 Shell hook | 让当前终端识别 Conda | 会改变 PATH 与当前环境解析顺序 |

材料中的 `-u` 表示更新已有安装的行为倾向，若环境需要严格复现，更稳妥的做法是固定 Miniconda、Python 和依赖版本，而不是始终使用 `latest`。

### 34.3 接受 Conda 服务条款

对 `pkgs/main` 和 `pkgs/r` 两个 channel 分别接受服务条款，只是允许后续包解析和下载，不是依赖真实性或安全性的证明。

### 34.4 安装 Jupyter 与 PyTorch 依赖

依赖分成两组：

- Jupyter、JupyterLab、Notebook、IPython kernel：提供交互式实验环境；
- NumPy、Torch、Torchvision、Torchaudio：提供数组、模型、序列化和深度学习能力。

材料使用 CPU 版 PyTorch 索引，是为了降低 GPU、CUDA 和磁盘需求。实际防御实验应额外保存：

```text
Python 版本
Conda / pip 版本
完整依赖锁文件
每个安装包的来源与哈希
操作系统与架构
```

“安装失败就卸载、清缓存再装”只能处理部分缓存或版本冲突，不是通用诊断方法，也会降低复现性。应先记录错误、解析依赖图，再决定是否清理。

### 34.5 启动 JupyterLab

启动日志中的随机 token 是访问凭据，不应复制到公开笔记、截图或聊天中。材料只绑定 `localhost`，意味着默认仅本机可访问；若改为对外监听，则必须配合身份认证、TLS、防火墙和最小暴露策略。

---

## 35. 九个 Notebook 单元逐步分析

### 35.1 单元一：定义 `SimpleNet`

模型包含：

```text
fc1：输入层到隐藏层
ReLU：非线性激活
fc2：隐藏层到输出层
large_layer：额外的大型线性层
```

关键异常是 `large_layer` 被注册为模型参数，却没有出现在 `forward()` 中。

这意味着：

- 它会进入 `state_dict` 并随模型参数保存；
- 它不参与前向预测；
- 修改它不会直接改变当前模型输出；
- 它提供了较大的隐写容量；
- “已保存但未使用的参数”本身就是值得审计的结构异常。

这里的 `state_dict` 是参数名到张量的映射。打印 key、shape 和 `numel()` 是在做容量盘点，也是模型结构审计的基础。

### 35.2 单元二：生成虚拟数据并训练

材料构造随机输入，并用随机线性关系加噪声生成回归目标，然后使用：

- `TensorDataset` 保存输入与目标；
- `DataLoader` 以 batch 方式迭代；
- `MSELoss` 计算回归误差；
- Adam 更新参数；
- 五轮 epoch 展示一个最小训练闭环。

标准训练步骤是：

```text
清空上一批梯度
    ↓
前向计算
    ↓
计算损失
    ↓
反向传播
    ↓
更新参数
```

由于 `large_layer` 不参与前向传播，它不会获得有效梯度，训练它也不会改变预测。这进一步说明该层主要为制品构造服务，而不是任务需要。

### 35.3 单元三：保存正常参数字典

`torch.save(target_model.state_dict(), ...)` 保存的是参数字典，而不是整个自定义模型实例。原则上，纯参数保存比直接保存任意 Python 对象更容易约束和审计，但文件仍应视为不可信输入。

需要区分：

```text
保存 state_dict
≠ 文件格式天然无执行风险
≠ 后续任何 torch.load 调用都安全
```

加载侧仍应使用受限策略、可信来源和完整性校验。

### 35.4 单元四：定义 LSB 编码与解码

编码器把 Float32 的位模式解释为 32 位无符号整数，清除最低若干位，再写入载荷位。数据格式为：

```text
[4 字节大端序长度] [载荷字节]
```

解码器先读取 32 位长度，再按长度读取后续比特并还原为字节。

设：

- \(L\)：载荷字节数；
- \(b\)：每个 Float32 元素使用的最低有效位数；
- \(M\)：目标张量元素数；
- 长度前缀固定为 4 字节。

所需比特数：

\[
B=8(L+4)
\]

所需张量元素数：

\[
N=\left\lceil\frac{8(L+4)}{b}\right\rceil
\]

理论最大载荷容量：

\[
C=\left\lfloor\frac{Mb}{8}\right\rfloor-4
\]

材料使用 2 LSB，因此一字节通常占用 4 个 Float32 元素。修改最低位往往只带来很小的数值扰动，但“变化很小”不等于“不可检测”，也不保证经过量化、格式转换或重新保存后仍能保留。

实现层面的重要注意点：

- 编码和解码必须使用一致的大小端与位顺序；
- 仅支持 Float32，dtype 转换会破坏假设；
- 长度字段必须有业务上限和张量容量上限；
- NaN、Inf、量化和跨格式转换可能改变位模式；
- 隐写数据应使用 magic、版本、长度和完整性字段，防御解析器则应拒绝未知格式；
- 正常训练权重的低位也可能近似随机，不能仅凭“LSB 看起来随机”直接定罪。

### 35.5 单元五：准备最终载荷

原材料在这一单元设置网络目标并构造交互式命令通道。为保持学习边界，这里不复写其实现。

从结构上只需理解：

```text
源代码字符串
    ↓ UTF-8
字节序列
    ↓ 按位拆分
LSB 隐写数据
```

安全审计时可搜索的行为特征包括：

- socket 或异常出站连接；
- 标准输入、输出、错误流重定向；
- PTY、Shell 或子进程创建；
- 动态代码执行；
- 强制结束当前加载进程。

授权防御验证不需要真实命令通道。应以无害 marker 替代，例如仅返回固定值或记录一次隔离环境事件，而且不得访问网络、敏感文件或启动子进程。

### 35.6 单元六：把字节写入目标权重

该单元完成四件事：

1. 加载正常 `state_dict`；
2. 定位 `large_layer.weight`；
3. 根据载荷长度计算所需元素数并检查容量；
4. 克隆并修改目标张量，再替换参数字典中的对应值。

选择大张量的原因是容量充足。选择未参与前向计算的层，则可进一步避免影响当前模型行为。

值得注意的检测信号：

- 架构中存在从未被 `forward` 使用的大参数层；
- 单个层集中出现低位修改；
- 参数 key 与批准的模型清单不一致；
- 模型文件与可信发布版本哈希不一致；
- 重新导出仅实际需要的权重后，文件结构或大小显著变化。

### 35.7 单元七：自定义 Wrapper 与 `__reduce__`

这是执行链的关键。

Pickle 在保存自定义对象时，可调用 `__reduce__()` 获取“如何重建对象”的描述。危险设计返回的逻辑可抽象为：

```text
(危险可调用对象, (参数,))
```

在非受限反序列化时，Unpickler 会调用该对象完成重建。如果可调用对象是动态执行函数，参数又是代码字符串，模型加载就会越过“数据解析”边界，变成代码执行。

时间点必须说清：

- 保存对象时会调用 `__reduce__()` 生成重建说明；
- 保存阶段不等于一定执行了返回的危险 callable；
- 真正危险副作用通常发生在后续反序列化阶段；
- 载荷字节藏在张量中不会自行运行，必须有外层加载器定位、解码并执行它。

材料中的加载器又包含嵌套反序列化和第二次动态执行，因此存在多重危险边界：

```text
外层 Pickle 反序列化
    ↓
执行 Loader
    ↓
内层 Pickle 反序列化 state_dict
    ↓
从权重解码字符串
    ↓
再次动态执行
```

这个 Wrapper 也不是真的为了恢复一个正常模型对象。危险 callable 的返回值可能是 `None`，所以“加载结果类型异常”是一个很有价值的检测信号。

### 35.8 单元八：生成最终模型制品

该单元实例化 Wrapper，并通过 `torch.save` 写出最终文件。输出扩展名仍是 `.pth`，但扩展名不能证明其内容只是张量。

制品审查不能只看文件名，应检查：

- 顶层对象是否为预期的纯参数映射；
- 全部 key、shape、dtype 是否在清单内；
- 是否包含未知全局对象、重建函数或自定义类；
- Pickle opcode 是否引用动态执行、进程、网络或文件操作；
- 文件摘要、签名、来源和构建证明是否可信；
- 文件大小和对象层级是否偏离基线。

### 35.9 单元九：上传模型

原材料把制品作为 multipart 文件提交给模型上传接口。这里不保留可执行上传流程。

需要理解的系统信任边界是：

```text
外部客户端
    ↓ 上传
API 接收与临时存储
    ↓
模型校验 / 注册
    ↓
模型加载进程
    ↓
推理服务身份、文件权限与网络权限
```

如果上传后立即在高权限、可联网的服务进程中反序列化，那么单个文件解析漏洞会升级为主机级安全事件。HTTP 200 只表示接口请求成功，不代表模型安全，也不必然表示载荷成功。

---

## 36. 原材料最后阶段的含义

原材料在另一终端启动网络监听，再触发 Notebook 上传或服务端加载，最后通过回连会话读取 flag。

从安全分析角度，各阶段分别证明：

| 现象 | 证明内容 |
|---|---|
| 上传成功 | 外部制品进入了目标数据流 |
| 加载时产生出站连接 | 模型加载发生了非预期代码执行 |
| 获得目标进程身份 | 代码继承了加载服务的权限 |
| 能读取 flag | 该身份对目标文件具有读取权限 |

这不是四个独立漏洞。根因通常是：

```text
不可信模型制品
+ 非受限反序列化
+ 加载进程权限过大
+ 缺少出站网络隔离
+ 缺少制品完整性与结构门禁
```

网络监听和 flag 只是影响验证，最早的安全失败点发生在服务端把不可信对象交给危险反序列化器时。

---

## 37. 攻击链中的关键知识

### 37.1 数据与代码边界

模型参数在逻辑上应是数据，但容器格式可能同时表达对象构造逻辑。安全设计必须确保：

```text
外部输入只能描述批准的数据结构
不能选择任意可调用对象
不能在解析时执行用户提供的代码
```

### 37.2 隐写不是初始执行机制

LSB 隐写只负责隐藏和运输字节。真正的初始执行来自反序列化重建逻辑。没有 Loader，张量里的字节只是静态数据；没有隐藏张量，外层 Pickle 本身仍可能直接造成代码执行。

所以两层技术的关系是：

```text
Pickle gadget：负责首次执行
张量 LSB：负责隐藏第二阶段内容
```

### 37.3 “模型功能正常”不是安全证据

本例刻意把数据放进未使用层，预测可能完全不变。即使写入的是已使用层，少量低位变化也可能不明显影响精度。因此以下判断都不成立：

- Accuracy 正常，所以模型安全；
- 能成功加载，所以文件可信；
- 扩展名是 `.pth`，所以只有权重；
- 文件来自模型上传接口，所以可直接交给 `torch.load`。

### 37.4 最小权限决定影响上限

代码执行后的能力等于模型加载进程拥有的能力。加载器若同时具备敏感文件读取、云凭据、容器控制接口和任意出站网络，影响会显著扩大。

有效隔离应包括：

- 独立低权限 UID；
- 只读根文件系统和最小挂载；
- 无宿主机 Socket；
- 无生产密钥和云凭据；
- 默认拒绝出站网络；
- 禁止启动不必要子进程；
- CPU、内存、时间和文件大小限制；
- 失败后不进入无限重启。

---

## 38. 防御与安全审查清单

### 38.1 制品进入系统之前

```text
[ ] 只接受受信模型仓库或签名发布者
[ ] 校验签名、SHA-256 和构建证明
[ ] 固定允许的格式、架构、key、shape 与 dtype
[ ] 限制文件大小、压缩比、张量总元素数
[ ] 上传文件先进入隔离区，不直接加载
[ ] 拒绝未知扩展并检查真实文件结构
```

### 38.2 静态审查

```text
[ ] 在不执行对象构造的前提下检查容器
[ ] 审计 Pickle opcode 和引用的全局对象
[ ] 搜索 exec / eval / os / subprocess / socket / pty 等高风险引用
[ ] 顶层对象必须符合批准的数据结构
[ ] 参数清单与架构清单完全匹配
[ ] 标记未被前向图使用的大参数
[ ] 分层比较文件大小、摘要和参数差异
[ ] 对低位统计异常只作线索，不作单独定罪证据
```

### 38.3 安全加载

对于只需要权重的 PyTorch 场景，应显式采用受限加载方式，并在 CPU 上完成初步验证：

```python
state = torch.load(
    model_path,
    map_location="cpu",
    weights_only=True,
)
```

随后还要验证：

```text
type(state) 是批准类型
keys 精确匹配
每个 value 都是批准 dtype / shape 的 Tensor
不存在额外对象
总参数量与模型清单一致
```

`weights_only=True` 是重要控制，但不能代替来源校验、签名、结构验证、隔离和版本治理。旧版本行为、显式关闭受限模式、允许列表扩张及其他解析器都可能重新引入风险。

更适合纯张量分发的场景可优先采用不允许任意 Python 对象构造的格式，例如经过治理的 `safetensors` 流程；格式选择仍需配合完整性与资源限制。

### 38.4 动态隔离验证

必要的动态检查应在一次性沙箱中进行：

```text
[ ] 无外网与内网访问
[ ] 无敏感挂载和环境变量
[ ] 低权限、只读文件系统
[ ] 监控进程树、文件访问与网络尝试
[ ] 设置时间、内存、CPU 与输出上限
[ ] 加载失败即销毁环境
```

不要为了证明风险而运行真实回连或读取真实敏感数据。无害 marker、拒绝事件和系统调用审计已经足以验证控制。

### 38.5 运行时检测信号

重点关联模型加载时间点附近的：

```text
python → sh / bash / cmd / powershell
首次异常出站 TCP
访问凭据、密钥、用户目录或系统配置
创建 PTY、临时脚本或持久化文件
模型加载返回类型异常
进程突然退出、崩溃或重启
日志出现未知全局对象或受限反序列化拒绝
```

单一信号可能有正常解释，应结合批准基线、进程身份、目标地址、模型摘要与加载时间线判断。

---

## 39. 原材料中的查漏点与易错理解

### 39.1 `latest` 破坏严格复现

始终下载安装最新版 Miniconda、未固定 pip 依赖，会使相同 Notebook 在未来得到不同环境。教学方便与取证级复现不是一回事。

### 39.2 删除安装器不等于消除供应链风险

删除下载脚本只回收磁盘，不能证明此前执行内容可信，也不能撤销安装器已经做出的系统变化。

### 39.3 Jupyter token 不应写入永久笔记

token 等同临时访问凭据。截图和日志在共享前应脱敏。

### 39.4 未使用层是人为扩大隐写容量

正常模型可能存在训练期辅助层或兼容参数，但一个很大的、完全不参与前向的层应有明确设计说明，否则应进入复核。

### 39.5 长度前缀缺少严格上限

仅从前 32 位读取长度并按其循环，可能引入拒绝服务或异常资源消耗。解析器必须先验证：

\[
0 \le L \le \min(C,\ L_{\text{business max}})
\]

### 39.6 `__reduce__` 的保存与加载时机容易混淆

保存时调用 `__reduce__` 取得重建描述；加载时才根据描述调用危险对象。审计时必须分别观察构造端日志和消费端日志。

### 39.7 文件上传成功不等于利用成功

还需要目标确实加载文件、使用危险路径、未被受限加载器阻止，并且运行时能力允许产生可观察结果。

### 39.8 直接封禁某个地址或端口不是根治

载荷目标可变化。根治优先级应是：

```text
消除危险反序列化
    ↓
限制可接受数据结构
    ↓
验证来源和完整性
    ↓
隔离加载身份与网络
    ↓
行为监控与事件响应
```

---

## 40. 本案例记忆卡片

### Q32：本案例是传统训练数据后门吗？

不是。它主要是恶意模型制品、Pickle 反序列化和张量隐写组合而成的供应链攻击。

### Q33：第一次代码执行来自哪里？

来自非受限 Pickle 反序列化根据 `__reduce__` 返回的重建描述调用危险 callable。

### Q34：张量 LSB 中的字节会自行执行吗？

不会。需要外层 Loader 定位张量、解码字节并把结果交给执行机制。

### Q35：为什么使用未参与前向计算的大层？

它同时提供较大容量，并减少参数变化对当前预测行为的影响。

### Q36：为什么要在载荷前放 4 字节长度？

让解码器知道后续要读取多少字节；防御解析器必须验证该长度不超过张量容量和业务上限。

### Q37：使用 2 LSB 时，长度为 \(L\) 的载荷需要多少元素？

\[
N=4(L+4)
\]

其中额外 4 字节用于长度前缀。

### Q38：保存 `state_dict` 是否绝对安全？

不是。安全性取决于实际文件内容、加载方式、PyTorch 版本、允许对象范围、来源完整性和运行时隔离。

### Q39：最直接的防篡改控制是什么？

校验可信发布者提供的数字签名或已知 SHA-256，并把摘要与模型版本、架构清单和构建证明绑定。

### Q40：为什么正常 Accuracy 发现不了这种问题？

攻击藏在序列化和加载链中，且隐藏层可能不参与预测；它不是通过明显降低模型精度来实现影响。

### Q41：防御验证是否需要真实反向 Shell？

不需要。受限加载拒绝、无害 marker、系统调用审计和零出站沙箱足以验证控制。

### Q42：最关键的单点修复是什么？

不要把不可信模型文件交给可执行任意对象重建逻辑的反序列化路径；只允许经过来源校验和结构验证的纯张量数据进入隔离加载流程。

---

## 41. 本案例最终总结

这份材料展示的不是“权重自己变成了木马”，而是三个安全问题的组合：

```text
模型文件被当作可信数据
    +
Pickle 允许对象重建时调用代码
    +
张量低位可隐藏不易察觉的第二阶段字节
```

完整因果链是：

```text
构造普通模型外观
    ↓
利用未使用的大张量提供隐写空间
    ↓
把字节编码进 Float32 最低有效位
    ↓
用自定义 Wrapper 规定危险重建行为
    ↓
将制品送入模型上传与加载管线
    ↓
非受限反序列化首次执行 Loader
    ↓
Loader 解码张量中的隐藏内容
    ↓
最终影响受加载进程权限与隔离强度决定
```

学习时最应该记住的是：

> 模型制品既要按“数据文件”做来源、签名、结构和数值完整性检查，也要按“潜在代码容器”处理反序列化风险；任何外部模型都应在受限格式、受限加载器、低权限隔离环境和默认拒绝出站网络的条件下完成验证。

---

## 42. Trojan 题代码主线：变量如何一步步流动

先把九个单元中的核心变量串起来：

```text
target_model
    ↓ state_dict()
victim_model_state.pth
    ↓ torch.load
loaded_state_dict
    ↓ 修改 large_layer.weight
modified_state_dict
    ↓ 传给 TrojanModelWrapper
wrapper_instance
    ↓ torch.save
malicious_trojan_model.pth
    ↓ 上传并由服务端加载
触发外层 Pickle 重建逻辑
```

另有一条隐藏数据流：

```text
payload_code_string
    ↓ encode("utf-8")
payload_bytes_to_hide
    ↓ encode_lsb
modified_target_tensor
    ↓ 写回 target_key
modified_state_dict["large_layer.weight"]
    ↓ Loader 中 decode_lsb
extracted_payload_bytes
    ↓ decode("utf-8")
extracted_payload_code
```

理解这两条数据流，比孤立记住每个代码块更重要：第一条负责生成和运输模型制品，第二条负责把隐藏内容放入权重并在加载时取回。

---

## 43. 模型定义代码逐行讲解

### 43.1 导入模块

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
import numpy as np
import os
```

分别用于：

| 代码 | 作用 |
|---|---|
| `torch` | 张量、随机数据、保存与加载 |
| `torch.nn` | 神经网络层和损失函数 |
| `torch.optim` | Adam 优化器 |
| `TensorDataset` | 把输入和标签封装为数据集 |
| `DataLoader` | 按 batch 迭代数据 |
| `numpy` | 设置 NumPy 随机种子 |
| `os` | 文件存在性、大小和环境信息 |

### 43.2 固定随机种子

```python
SEED = 1337
np.random.seed(SEED)
torch.manual_seed(SEED)
```

这使 NumPy 和 PyTorch CPU 随机序列更容易复现，但并不保证所有平台、版本和并行后端逐位一致。

### 43.3 类继承

```python
class SimpleNet(nn.Module):
```

继承 `nn.Module` 后，赋给对象属性的 `nn.Linear` 会自动注册为子模块，其参数会自动出现在：

```text
model.parameters()
model.state_dict()
```

### 43.4 第一层、激活层和输出层

```python
self.fc1 = nn.Linear(input_size, hidden_size)
self.relu = nn.ReLU()
self.fc2 = nn.Linear(hidden_size, output_size)
```

数据形状变化：

```text
[batch, 10]
    ↓ fc1
[batch, 64]
    ↓ ReLU
[batch, 64]
    ↓ fc2
[batch, 1]
```

### 43.5 额外大层

```python
self.large_layer = nn.Linear(hidden_size, hidden_size * 5)
```

在本题参数下：

```text
输入维度：64
输出维度：320
weight shape：[320, 64]
weight numel：20,480
bias numel：320
```

如果使用 2 LSB，仅 `weight` 的理论隐藏容量为：

\[
\left\lfloor\frac{20480\times2}{8}\right\rfloor-4
=5116\text{ bytes}
\]

### 43.6 `forward()` 的关键点

```python
def forward(self, x):
    x = self.fc1(x)
    x = self.relu(x)
    x = self.fc2(x)
    return x
```

`large_layer` 没有被调用，因此：

```text
它会被保存
但不参与预测
也不会从当前损失获得梯度
```

验证这一点可以在无害实验中检查：

```python
assert target_model.large_layer.weight.grad is None
```

在一次正常反向传播之后，该断言应成立。

---

## 44. 训练代码逐行讲解

### 44.1 生成输入

```python
X_train = torch.randn(num_samples, input_dim)
```

生成形状为 `[100, 10]` 的标准正态随机输入。

### 44.2 生成回归目标

```python
true_weights = torch.randn(input_dim, output_dim)
y_train = X_train @ true_weights + noise
```

矩阵乘法形状为：

```text
[100, 10] @ [10, 1] → [100, 1]
```

附加高斯噪声后，模型学习的是一个带噪声的线性回归问题。

### 44.3 数据加载

```python
dataset = TensorDataset(X_train, y_train)
dataloader = DataLoader(dataset, batch_size=16)
```

100 个样本、batch size 16 会产生 7 个 batch：6 个完整 batch 和 1 个不足 16 的尾 batch。

### 44.4 损失与优化器

```python
criterion = nn.MSELoss()
optimizer = optim.Adam(target_model.parameters(), lr=0.01)
```

虽然优化器接收了 `target_model.parameters()` 中的全部参数，但只有参与前向图并获得梯度的参数会被实际更新。`large_layer` 没有梯度，因此不会被这个训练目标更新。

### 44.5 训练循环

```python
optimizer.zero_grad()
outputs = target_model(inputs)
loss = criterion(outputs, targets)
loss.backward()
optimizer.step()
```

逐行含义：

1. `zero_grad()`：清除上一个 batch 累积的梯度；
2. `target_model(inputs)`：调用 `forward()`；
3. `criterion(...)`：计算预测与目标的均方误差；
4. `backward()`：沿计算图求梯度；
5. `step()`：Adam 根据梯度更新参数。

### 44.6 损失输出的细节

```python
epoch_loss += loss.item()
epoch_loss / len(dataloader)
```

这里计算的是“各 batch 平均损失的算术平均”。由于最后一个 batch 样本较少，它与严格的逐样本平均损失可能略有差异。教学演示足够，但精确统计应按 batch 样本数加权。

---

## 45. `state_dict` 保存与加载代码讲解

### 45.1 保存参数字典

```python
torch.save(target_model.state_dict(), legitimate_state_dict_file)
```

调用顺序是：

```text
target_model.state_dict()
    ↓
生成 OrderedDict 风格的参数映射
    ↓
torch.save 序列化到文件
```

典型 key 包括：

```text
fc1.weight
fc1.bias
fc2.weight
fc2.bias
large_layer.weight
large_layer.bias
```

### 45.2 为什么保存 `state_dict` 而不是整个模型

保存整个模型对象会依赖 Python 类的导入路径和对象重建。保存纯参数映射通常更便于版本迁移、结构检查和受限加载。

### 45.3 材料中的加载语句

```python
loaded_state_dict = torch.load(legitimate_state_dict_file)
```

问题在于它没有显式声明受限加载。防御侧更合适的是：

```python
loaded_state_dict = torch.load(
    legitimate_state_dict_file,
    map_location="cpu",
    weights_only=True,
)
```

随后还应检查顶层类型、key、shape、dtype 和参数总量，而不是加载成功后直接信任。

---

## 46. `encode_lsb()` 代码逐段讲解

### 46.1 输入约束

```python
if tensor_orig.dtype != torch.float32:
    raise TypeError(...)
if not 1 <= num_lsb <= 8:
    raise ValueError(...)
```

原因是实现把每个元素严格按 IEEE 754 Float32 的 32 位模式处理。Float16、Float64 或整型都不符合当前编码协议。

### 46.2 克隆张量

```python
tensor = tensor_orig.clone().detach()
tensor_flat = tensor.flatten()
```

- `clone()`：避免修改原张量；
- `detach()`：切断 autograd 计算图；
- `flatten()`：建立一维访问视图或连续结果，便于按元素写入。

### 46.3 增加长度前缀

```python
data_len = len(data_bytes)
data_to_embed = struct.pack(">I", data_len) + data_bytes
```

`>I` 表示：

```text
>：大端序
I：32 位无符号整数
```

因此解码器的前 4 字节不是载荷，而是载荷长度。

### 46.4 容量检查

```python
total_bits_needed = len(data_to_embed) * 8
capacity_bits = n_elements * num_lsb
```

若需求超过容量立即报错，避免静默截断：

```python
if total_bits_needed > capacity_bits:
    raise ValueError(...)
```

### 46.5 Float32 与整数位模式互转

```python
packed_float = struct.pack(">f", original_float)
int_representation = struct.unpack(">I", packed_float)[0]
```

这里没有做数值上的“浮点转整数”，而是：

```text
同一组 4 字节
Float32 解释 ↔ UInt32 解释
```

例如某个浮点数的符号位、指数位和尾数位全部保留，只准备修改最右侧最低位。

### 46.6 构造掩码

```python
mask = (1 << num_lsb) - 1
```

若 `num_lsb=2`：

```text
1 << 2 = 二进制 100
减 1 = 二进制 011
mask = 0b11
```

清除最低位：

```python
cleared_int = int_representation & (~mask)
```

写入新数据：

```python
new_int_representation = cleared_int | data_bits_for_float
```

### 46.7 位读取顺序

```python
data_bit = (current_byte >> bit_index_in_byte) & 1
```

`bit_index_in_byte` 从 7 递减到 0，说明每个字节按最高位到最低位的顺序写入。

使用 2 LSB 时，每个 Float32 承载 2 bit：

```text
1 byte = 8 bit = 4 个 Float32 元素
```

### 46.8 写回浮点值

```python
new_packed_float = struct.pack(">I", new_int_representation)
new_float = struct.unpack(">f", new_packed_float)[0]
tensor_flat[element_index] = new_float
```

这一步把修改后的 32 位模式重新解释为 Float32，再写回张量。

---

## 47. `decode_lsb()` 代码逐段讲解

### 47.1 `get_bits(count)` 的作用

内部函数从当前 `element_index` 开始：

1. 读取一个 Float32；
2. 取得其整数位模式；
3. 用 `mask` 截取最低 `num_lsb` 位；
4. 按高到低顺序追加到 `bits`；
5. 推进到下一个张量元素。

### 47.2 读取长度

```python
length_bits = get_bits(32)
```

随后通过左移逐位还原整数：

```python
length_int = (length_int << 1) | bit
```

### 47.3 读取载荷

```python
payload_bits = get_bits(payload_len * 8)
```

每收集 8 bit 就组装成一个字节：

```python
current_byte_val = (current_byte_val << 1) | bit
```

### 47.4 一个重要的通用实现缺陷

材料允许 `num_lsb` 为 1–8，但当前 `get_bits()` 每次调用结束时不会保存“同一个张量元素中尚未消费的低位”。

因此当 `num_lsb` 不能整除 32 时：

```text
读取 32 位长度
    ↓
最后一个元素可能还有未消费位
    ↓
element_index 已推进
    ↓
读取 payload 时这些位被丢弃
```

当前题使用 `NUM_LSB=2`，而 2 能整除 32，所以不会触发该问题。若要声称支持全部 1–8，应使用连续 bitstream 游标，或限制：

```text
num_lsb ∈ {1, 2, 4, 8}
```

### 47.5 长度字段的防御问题

代码把解出的长度直接乘以 8 后读取。安全解析器应先验证：

```text
payload_len ≤ 张量剩余理论容量
payload_len ≤ 业务最大值
payload_len × 8 不产生异常资源消耗
```

否则恶意长度字段可能导致超长循环或拒绝服务。

---

## 48. 隐藏载荷准备代码讲解

### 48.1 字符串为什么使用外层 f-string

材料通过多行 f-string 把网络目标写进最终源代码字符串。外层变量先被替换，最终得到一段独立的 Python 文本。

如果嵌套代码中还包含自己的 f-string，就必须用双花括号：

```text
外层 {{name}}
    ↓ 外层格式化后
内层 {name}
```

否则外层会提前尝试解析内层变量。

### 48.2 载荷模块的语义

危险片段导入的模块分别表达：

| 模块 | 在原材料中的语义 |
|---|---|
| `socket` | 建立网络连接 |
| `os` | 文件描述符操作、环境和进程退出 |
| `pty` | 创建伪终端，提高交互性 |
| `sys` | 标准流和错误日志 |
| `traceback` | 输出异常堆栈 |
| `subprocess` | 子进程能力；片段中主要作为可疑能力导入 |

### 48.3 标准流重定向

原代码把文件描述符 0、1、2 指向同一个网络 Socket：

```text
0 = stdin
1 = stdout
2 = stderr
```

这样 Shell 的输入和输出都经过网络通道。它是高风险行为特征，不是模型推理的正常需求。

### 48.4 超时与异常分支

连接阶段设置短超时，用于区分：

- 连接超时；
- 连接被拒绝；
- 其他异常。

连接成功后取消超时，允许交互会话长期存在。

### 48.5 `finally` 与强制退出

材料最后关闭 Socket，并使用强制进程退出。它可能直接终止 Notebook kernel 或模型服务进程，绕过常规清理，是明显的可用性和事件检测信号。

---

## 49. 把隐藏字节写回模型的代码讲解

### 49.1 选择参数 key

```python
target_key = "large_layer.weight"
```

字符串必须与 `state_dict` 中的 key 完全一致，所以代码先检查：

```python
if target_key not in loaded_state_dict:
    raise KeyError(...)
```

### 49.2 计算需要的元素数

```python
bytes_to_embed = 4 + len(payload_bytes_to_hide)
bits_needed = bytes_to_embed * 8
elements_needed = (bits_needed + NUM_LSB - 1) // NUM_LSB
```

最后一行是整数向上取整：

\[
\left\lceil\frac{\text{bits needed}}{\text{NUM\_LSB}}\right\rceil
\]

避免使用浮点除法和 `ceil()`。

### 49.3 浅复制为何在这里够用

```python
modified_state_dict = loaded_state_dict.copy()
modified_state_dict[target_key] = modified_target_tensor
```

字典的 `.copy()` 是浅复制，其他 key 仍引用原张量。但目标张量已经由 `encode_lsb()` 通过 `clone()` 生成独立副本，随后整个 key 被替换，因此不会修改原目标张量。

如果后续还要原地修改其他共享张量，浅复制就不够安全。

---

## 50. `TrojanModelWrapper` 代码逐行讲解

### 50.1 `__init__()` 接收什么

```python
def __init__(self, modified_state_dict, target_key, num_lsb):
```

三个参数分别告诉 Wrapper：

- 完整的已修改参数字典在哪里；
- 隐藏内容在哪个参数 key；
- 每个元素使用多少个最低位。

### 50.2 类型检查

代码验证：

```text
target_key 存在
对应值是 Tensor
dtype 是 Float32
num_lsb 位于允许范围
```

这些检查保证内层解码器的基本假设成立。

### 50.3 为什么再次 `pickle.dumps`

```python
self.pickled_state_dict_bytes = pickle.dumps(modified_state_dict)
```

Wrapper 没有把字典直接作为普通属性保存，而是先转换为 Pickle 字节。这样外层 Loader 可以把整份参数字典作为字节字面量嵌入自己的代码字符串。

代价是：

- 文件结构更复杂；
- 出现嵌套 Pickle；
- 制品体积增大；
- 静态扫描更容易发现异常字节串和反序列化调用。

### 50.4 `get_state_dict()`

```python
return pickle.loads(self.pickled_state_dict_bytes)
```

它提供恢复内部字典的方法，但真正的危险加载链并不依赖外部调用该方法；`__reduce__()` 构造的 Loader 自己会执行类似逻辑。

### 50.5 `__reduce__()` 的返回值

核心可抽象为：

```python
return (exec, (loader_code,))
```

Pickle 把它理解为：

```text
为了重建这个对象
请调用 exec(loader_code)
```

这正是数据反序列化越界为代码执行的地方。

### 50.6 保存阶段与加载阶段

执行时序：

```text
torch.save(wrapper_instance)
    ↓
调用 wrapper_instance.__reduce__()
    ↓
取得 (exec, (loader_code,))
    ↓
把这份重建说明写入文件

后续 torch.load(...)
    ↓
Unpickler 读取重建说明
    ↓
调用 exec(loader_code)
```

所以日志中的“`__reduce__ activated`”可在保存时出现，但真正的 Loader 副作用通常在目标加载文件时发生。

### 50.7 为什么加载结果可能是 `None`

`exec()` 通常返回 `None`。因此 Unpickler 得到的“重建对象”不是正常模型，而是 `None`。这说明该设计只追求加载副作用，不追求恢复可用模型。

---

## 51. Loader 字符串内部代码讲解

Loader 的执行顺序是：

```text
导入依赖
    ↓
定义一份内嵌 decode_lsb
    ↓
恢复被嵌入的 state_dict 字节
    ↓
pickle.loads 重建参数字典
    ↓
检查字典与 target_key
    ↓
取出 payload_tensor
    ↓
decode_lsb 得到隐藏字节
    ↓
UTF-8 解码成字符串
    ↓
动态执行最终字符串
```

### 51.1 `repr()` 的作用

```python
pickled_state_dict_literal = repr(self.pickled_state_dict_bytes)
```

`repr(bytes)` 会生成类似 Python 字节字面量的文本，使原始二进制内容能被嵌入 Loader 源代码。

同理：

```python
embedded_target_key = repr(self.target_key)
```

会为字符串自动处理引号和转义，降低直接拼接引发的语法错误。

### 51.2 为什么把解码函数源码也嵌进去

目标加载环境未必已经定义 Notebook 中的 `decode_lsb`。把函数源码放进 Loader 后，文件变成自包含制品，但也因此出现明显的代码字符串和动态执行信号。

### 51.3 两次动态执行

执行边界有两层：

```text
外层 exec(loader_code)
内层 exec(extracted_payload_code)
```

外层负责恢复与解码，内层执行隐藏内容。即使防御工具只发现外层 `exec`，也已经足以拒绝该文件，不需要把隐藏内容真实运行出来。

---

## 52. 最终保存与上传代码讲解

### 52.1 实例化 Wrapper

```python
wrapper_instance = TrojanModelWrapper(
    modified_state_dict=modified_state_dict,
    target_key=target_key,
    num_lsb=NUM_LSB,
)
```

关键是三个值必须与编码阶段保持一致。尤其 `target_key` 或 `NUM_LSB` 不一致时，Loader 无法正确恢复隐藏字节。

### 52.2 保存最终制品

```python
torch.save(wrapper_instance, final_malicious_file)
```

保存的是 Wrapper 实例，不再是纯 `state_dict`。这是正常文件与危险文件在顶层对象结构上的根本差别。

### 52.3 multipart 上传结构

材料中的文件映射表达：

```text
表单字段名：model
文件名：本地文件 basename
内容：二进制文件流
MIME：application/octet-stream
```

字段名必须与服务端读取的表单字段一致。`finally` 中关闭文件句柄是正确的资源管理意识，更简洁的实现通常使用 `with open(...)`。

### 52.4 HTTP 结果判断

代码尝试优先解析 JSON，失败后输出文本，并按状态码判断上传是否成功。

需要避免的误解：

```text
HTTP 200
只表示服务器接受或处理了请求
不等于文件安全
不等于服务端一定加载了文件
也不等于隐藏代码一定成功执行
```

---

## 53. Trojan 题代码审计速查

阅读类似代码时，可按以下顺序定位风险：

```text
1. 顶层保存的是 state_dict 还是自定义对象
2. 是否定义 __reduce__ / __setstate__
3. 重建 callable 是否包含 exec / eval / os.system
4. 是否存在嵌套 pickle.loads
5. 是否把大段 bytes 或源码字符串嵌入对象
6. 是否有未参与 forward 的异常大层
7. 是否按位修改 Float32 权重
8. 是否出现 socket / pty / subprocess
9. 模型上传后是否立即由高权限服务加载
10. 加载进程是否具备出站网络和敏感文件权限
```
