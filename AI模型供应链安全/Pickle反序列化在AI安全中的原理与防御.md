---
id: coae-supply-d970f810
title: 'Pickle 反序列化在 AI 安全中的原理与防御'
aliases: []
domain:
  - 'AI模型供应链安全'
note_type:
  - concept
attack_phase:
  - artifact
  - deployment
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-12
---
# Pickle 反序列化在 AI 安全中的原理与防御

> 定位：聚焦 Pickle 的 AI 模型供应链安全讲义。先理解“为什么加载文件会执行行为”，再学习 PyTorch 场景、审计与防御。
>
> 安全边界：只在自有或明确授权的环境中测试。未知 Pickle 不能用“先加载看看”来检查，因为危险行为可能发生在加载返回之前。
>
> 版本基线：PyTorch 2.6 起，在没有显式传入 `pickle_module` 时，`torch.load` 默认使用 `weights_only=True`。工程代码仍应显式写出安全参数并固定版本。

---

## 1. 先记住四句话

1. Pickle 不是纯数据格式，而是一套“如何重建 Python 对象”的指令协议。
2. 攻击者控制 Pickle，应用又执行非受限反序列化时，数据边界可能变成代码执行边界。
3. `weights_only=True` 只缩小反序列化攻击面，不证明模型权重、行为或来源可信。
4. 应组合使用非可执行权重格式、可信来源与签名、结构验证、隔离加载和行为评估。

一句话判断：

```text
谁控制文件？谁执行加载？加载器允许重建什么？加载进程拥有什么权限？
```

若答案是“外部人员可控制文件 + 高权限进程允许任意对象重建”，风险就很高。

---

## 2. 为什么它属于 AI 安全

AI 工程常见制品流：

```text
训练平台
  → 模型仓库 / 对象存储 / Hugging Face Hub
  → CI/CD 或模型注册表
  → 推理服务下载
  → Python 进程加载
```

模型文件常被误认为“只是一堆数字”，但实际生态中存在：

| 产物或接口 | 与 Pickle 的关系 | 典型风险 |
|---|---|---|
| `.pkl` / `.pickle` | 通常直接使用 Pickle | 非受限加载可触发对象重建行为 |
| PyTorch `.pt` / `.pth` / 某些 `.bin` | `torch.save` 使用 Pickle 相关机制恢复元数据和对象 | 非受限 `torch.load` 风险高 |
| `joblib` 模型 | 常用于 scikit-learn 等 Python 对象 | 加载不可信文件同样危险 |
| `cloudpickle` / `dill` | 支持更多 Python 对象 | 需要信任的恢复面通常更大 |
| `.safetensors` | 面向张量的非任意对象格式 | 避免 Pickle 式执行，但不保证模型无后门 |

扩展名不是安全属性。审计必须看真实格式、生成方式、框架版本和实际加载 API。

---

## 3. Pickle 为什么可能执行行为

### 3.1 从“数据”到“对象重建指令”

```text
序列化：Python object → bytes
反序列化：bytes → reconstructed Python object
```

JSON 主要表达字符串、数字、数组和映射。Pickle 为恢复 Python 对象，还要描述：

- 从哪个模块寻找类或函数；
- 使用什么参数创建对象；
- 如何恢复属性和内部状态；
- 如何处理对象之间的引用关系。

因此，Unpickler 不只是字节解析器，更像解释对象重建指令的小型虚拟机。

### 3.2 `__reduce__()` 是关键

对象可以用 `__reduce__()` 描述如何重建自己，核心形式可抽象为：

```python
(callable, arguments)
```

反序列化器会执行近似操作：

```python
result = callable(*arguments)
```

如果不可信文件能指定 callable 和参数，“读取数据”就可能变成“调用函数”。

### 3.3 无破坏性概念演示

下面只用 `print` 展示副作用发生在加载阶段，不包含系统命令、文件或网络操作：

```python
import pickle


class TeachingDemo:
    def __reduce__(self):
        return (print, ("[demo] 这行文字由反序列化阶段输出",))


blob = pickle.dumps(TeachingDemo())
restored = pickle.loads(blob)
print(restored)  # print 的返回值是 None
```

观察：

- `pickle.dumps()` 保存重建说明；
- `pickle.loads()` 按说明调用 `print`；
- 副作用发生在 `loads()` 返回之前；
- 最终对象为 `None`，因为 `print()` 返回 `None`。

现实攻击可能把 `print` 换成危险 callable。安全问题的根不是某个特殊字符串，而是协议允许表达对象重建调用。

### 3.4 操作码怎样理解

| 操作码概念 | 作用 |
|---|---|
| `GLOBAL` / `STACK_GLOBAL` | 引用模块中的全局对象 |
| `REDUCE` | 使用 callable 与参数重建对象 |
| `BUILD` | 恢复对象状态 |
| `NEWOBJ` / `NEWOBJ_EX` | 创建类实例 |

这些操作码也会出现在正常文件中。审查重点是“引用了什么、参数是什么、调用链最终能做什么”。

---

## 4. 典型攻击链与影响

```text
攻击者获得模型制品写入能力
  → 构造带危险对象重建语义的文件
  → 文件进入模型仓库、上传接口或共享目录
  → 服务调用 pickle.load 或非受限 torch.load
  → Unpickler 按指令调用危险 callable
  → 行为继承模型加载进程的权限
```

可能受影响的资产：

- 云凭据、数据库口令、API Token；
- 训练数据、模型权重和私有代码；
- 推理主机、GPU 节点、共享文件系统；
- CI/CD 身份、模型注册表和对象存储；
- 同一网络内的其他服务。

所以它属于模型供应链和基础设施安全，不只是“模型预测不准”。

---

## 5. 三类模型风险不要混淆

| 风险 | 最早发生阶段 | 核心问题 | 主要控制 |
|---|---|---|---|
| 不安全反序列化 | 加载时 | 文件能否让加载器执行行为 | 非可执行格式、受限加载、隔离 |
| 模型后门 / 木马 | 特定输入推理时 | 模型是否产生攻击者指定输出 | 行为评估、触发测试、数据治理 |
| 权重篡改 / 张量隐写 | 制品流转或推理时 | 参数是否被替换、投毒或藏数据 | 签名、摘要、基线对比 |

```text
weights_only=True 成功
  ≠ 模型来源可信
  ≠ 权重没有被篡改
  ≠ 模型没有后门
  ≠ 张量中没有隐藏数据
```

---

## 6. PyTorch 场景

### 6.1 整个模型与 `state_dict`

保存整个模型：

```python
torch.save(model, "model.pt")
```

它把恢复过程与 Python 类、模块路径和环境绑定，加载时往往需要更广泛的对象恢复能力。

推荐保存普通参数映射：

```python
torch.save(model.state_dict(), "weights.pt")
```

由受审查代码创建架构，再加载参数：

```python
import torch

model = build_model_from_trusted_code()
state = torch.load(
    "weights.pt",
    map_location="cpu",
    weights_only=True,
)
model.load_state_dict(state, strict=True)
model.eval()
```

- `weights_only=True`：限制可构建对象；
- `map_location="cpu"`：便于设备与资源控制；
- `strict=True`：发现缺失或多余参数名；
- 可信代码创建架构：把程序逻辑留在受审查代码中。

### 6.2 `weights_only=True` 的准确边界

它使用受限制的 Unpickler，允许普通张量 `state_dict` 所需的对象、部分基础类型和显式允许的类型，并禁止反序列化期间动态导入任意内容。

它显著缩小代码执行面，但官方文档明确说明：

- 不防拒绝服务；
- 仍可能存在内存损坏风险；
- 加载结果可能使下游代码进入不安全路径；
- 不验证文件来源、签名或摘要；
- 不检测模型后门、投毒或张量隐写。

所以它是“受限加载器”，不是“模型安全验证器”。

### 6.3 允许列表的陷阱

错误流程：

```text
加载失败 → 改成 weights_only=False
        或 → 把所有报错类型加入 safe globals
```

正确流程：

```text
识别缺失类型
  → 定位源码、包名和精确版本
  → 审查导入、构造和状态恢复行为
  → 确认业务需要
  → 只允许最小集合
  → 在隔离环境复测
```

`add_safe_globals()` 是授权加载器构建对应对象。允许列表每扩大一项，信任边界也随之扩大。

### 6.4 为什么仍要显式写参数

即使新版本默认更安全，实际行为仍可能被这些因素改变：

- 使用旧版 PyTorch；
- 调用点写了 `weights_only=False`；
- 传入自定义 `pickle_module`；
- 封装层、环境变量或兼容逻辑改变调用；
- 加载失败后自动降级。

显式参数、固定版本和测试可让安全意图可审计。

---

## 7. 代码审计方法

至少搜索：

```text
pickle.load
pickle.loads
torch.load
joblib.load
dill.load
cloudpickle
weights_only=False
add_safe_globals
safe_globals
```

再追踪数据流：

```text
URL / 上传文件 / 对象存储 key / 用户配置
  → 下载或复制
  → 文件路径或内存字节
  → load / loads
  → Notebook、训练、评估或推理任务
```

重点不是只找到危险 API，而是确认攻击者能否影响输入。常见入口包括：

- “上传模型并评估”功能；
- Notebook 从公共链接直接下载并加载；
- 自动任务读取可被替换的对象存储路径；
- CI 拉取未经固定 commit 的模型；
- 请求参数可指定模型路径或 URL；
- 缓存、共享卷或注册表权限错误。

高风险示例：

```python
with open(user_supplied_path, "rb") as f:
    model = pickle.load(f)
```

```python
model = torch.load(downloaded_path, weights_only=False)
```

HTTPS 只保护传输的一部分，不自动证明发布者、仓库、构建流程和文件内容可信。

---

## 8. 静态检查与局限

标准库 `pickletools` 可在不执行对象重建的情况下反汇编 Pickle：

```powershell
python -m pickletools .\suspect.pkl
```

关注：

- 异常模块和全局对象；
- 动态执行、进程、网络或文件相关引用；
- 很长的代码样字符串或二进制数据；
- 多层嵌套 Pickle；
- 与预期 `state_dict` 无关的自定义类。

但必须牢记：

```text
没有发现明显危险引用 ≠ 文件安全
```

静态分析可能漏掉动态类型、复杂调用链和自定义模块行为；即使没有代码执行，合法张量也可能导致资源耗尽或恶意模型行为。

---

## 9. 防御性审查流程

### 第一步：不加载，先登记

```text
来源、提供者、下载地址和时间
仓库 commit 或模型版本
文件大小与 SHA-256
发布签名及验证结果
声称格式与真实格式
预期框架、版本、架构和参数量
审批工单
```

Windows 计算摘要：

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\model.pt'
```

摘要只证明两个字节流是否相同。可信渠道提供的摘要与文件匹配，才构成来源和完整性证据的一部分。

### 第二步：审查加载点

- 路径是否受用户、URL、配置或环境变量控制？
- 是否显式受限加载？
- 是否加载完整对象？
- 失败后是否降级为非受限加载？
- 是否自动放行未知 globals？
- 加载进程有哪些文件、网络和凭据权限？

### 第三步：严格隔离

```text
[ ] 临时、可销毁的虚拟机或专用沙箱
[ ] 非管理员用户
[ ] 默认禁止出站网络
[ ] 不挂载宿主根目录、Docker socket 或共享密钥
[ ] 不注入云凭据、SSH key、浏览器数据
[ ] 文件系统尽量只读
[ ] 限制 CPU、内存、磁盘、进程数和时间
[ ] 记录进程、文件和网络活动
```

容器不是天然的强边界；高权限模式和危险挂载会破坏隔离。

### 第四步：受限加载后验证结构

```text
[ ] 顶层对象类型符合预期
[ ] 参数 key 与可信清单一致
[ ] shape、dtype、device 符合架构
[ ] 总 numel、文件大小和内存占用合理
[ ] 无意外对象或额外嵌套数据
[ ] NaN、Inf 和极端值比例可解释
[ ] load_state_dict(..., strict=True) 通过
```

结构检查也要有资源上限，避免巨大 shape、稀疏结构或异常元数据造成 DoS。

### 第五步：验证模型行为

```text
可信签名 / 摘要
  + 参数结构和逐张量对比
  + 固定评估集
  + 关键类别与敏感分组指标
  + 后门 / 触发候选测试
  + 启动期进程、文件和网络监控
```

通过后写入不可变模型注册表；生产端按固定标识拉取，并在启动时再次验证摘要。

---

## 10. 分层防御

| 层次 | 控制 | 解决的问题 |
|---|---|---|
| 格式层 | 优先 `.safetensors` 等非任意对象格式 | 减少“加载即执行” |
| 加载器层 | `weights_only=True`、最小 allowlist | 缩小对象恢复面 |
| 来源层 | 签名、可信摘要、固定 commit | 确认发布者与完整性 |
| 结构层 | key、shape、dtype、numel、数值检查 | 拒绝异常权重和资源滥用 |
| 行为层 | 评估集、后门测试、差异测试 | 检查模型功能 |
| 运行时层 | 低权限、断网、限额、监控 | 降低利用后的影响 |
| 流程层 | 注册表、审批、不可变版本 | 防止供应链替换和绕过 |

没有单个工具能覆盖所有层。

---

## 11. 常见误区

### “来自知名模型网站，所以安全”

网站、账户、仓库、依赖或构建任务都可能被接管，还要固定版本、验证发布者、签名和摘要。

### “扩展名是 `.pth`，所以只是数字”

扩展名不能证明真实格式或内部对象类型。

### “先 load，再检查对象类型”

类型检查太晚。副作用可能在 `load()` 返回前发生。

### “使用 `state_dict` 就绝对安全”

它是更好的设计，但未知文件仍应受限加载；合法张量也可能被投毒、藏数据或消耗资源。

### “`weights_only=True` 没报错，所以可部署”

它只说明受限 Unpickler 接受了恢复路径，不说明来源、完整性和模型行为通过审核。

### “Safetensors 解决所有模型安全问题”

它主要消除 Pickle 式任意对象反序列化风险。恶意权重、后门、资源耗尽和来源伪造仍需单独处理。

---

## 12. 复习题

### Q1：Pickle 的根本风险？

它不只表示数据，还表示对象如何重建；非受限反序列化可能调用文件指定的 callable。

### Q2：为什么不能加载后再检测？

副作用可能在 `load()` / `loads()` 返回前发生。

### Q3：`__reduce__()` 的核心返回形式？

可抽象为 `(callable, arguments)`。

### Q4：为什么推荐分发 `state_dict`？

把架构逻辑留在受审查代码中，使模型文件主要承载参数映射，减少任意 Python 对象恢复。

### Q5：`weights_only=True` 做什么？

使用受限 Unpickler，只允许普通张量字典所需的对象和明确允许的类型，并禁止动态导入任意内容。

### Q6：它没有解决什么？

来源伪造、篡改、DoS、模型后门、投毒、张量隐写和下游代码风险。

### Q7：静态扫描为什么不能单独证明安全？

它可能漏掉动态类型、复杂调用链和自定义模块行为，合法张量本身也可能恶意。

### Q8：最可靠的工程策略？

尽量不用 Pickle 分发纯权重，并组合签名与摘要、受限加载、结构验证、隔离、最小权限和行为评估。

---

## 13. 快速决策图

```text
不可信模型文件
     │
     ├─ 可执行对象格式？
     │      ├─ 是 → 拒绝、转换，或仅在严格隔离中受限处理
     │      └─ 否 → 继续
     ├─ 发布者、签名、摘要匹配？
     │      ├─ 否 → 拒绝并调查
     │      └─ 是 → 继续
     ├─ key / shape / dtype / numel 合规？
     │      ├─ 否 → 拒绝并调查
     │      └─ 是 → 继续
     ├─ 行为与安全评估通过？
     │      ├─ 否 → 不部署
     │      └─ 是 → 写入批准注册表
     └─ 生产端再次验签、验摘要，以低权限和受限网络运行
```

---

## 14. 官方参考与延伸

- [Python 官方文档：pickle](https://docs.python.org/3/library/pickle.html)
- [PyTorch 官方文档：torch.load](https://docs.pytorch.org/docs/stable/generated/torch.load.html)
- [PyTorch 官方文档：Serialization semantics](https://docs.pytorch.org/docs/stable/notes/serialization.html)
- [Hugging Face：Pickle Scanning](https://huggingface.co/docs/hub/security-pickle)
- [Hugging Face：Safetensors](https://huggingface.co/docs/safetensors/index)
- [综合延伸：Pickle 反序列化与张量隐写](Pickle反序列化与张量隐写原理和安全测试笔记.md)
- [实战检查：模型文件安全审查速查表](模型文件安全审查速查表.md)
