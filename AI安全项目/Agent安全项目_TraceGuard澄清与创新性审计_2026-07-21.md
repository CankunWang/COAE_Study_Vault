# Agent 安全项目：TraceGuard 澄清、创新性审计与候选实验

> 调研截止：2026-07-21  
> 目标：为一个可写入简历、可公开复现、兼具研究价值与工程价值的 AI/LLM Agent 安全项目确定真实创新边界。  
> 证据优先级：正式会议论文与官方 proceedings > 作者论文/仓库 > arXiv 预印本。预印本结果均视为作者自报，不能等同于同行评审结论。

## 使用方式：创新性审计快速入口

评估任何候选主张时依次检查：

```text
[ ] 主张是否被拆成数据、任务、方法、评估和部署五部分
[ ] 是否存在同名项目、相同问题定义或近似方法
[ ] 引用是否为原始论文/官方仓库并支持当前表述
[ ] 作者自报、预印本和同行评审结论是否分开
[ ] 新意来自真实问题边界，还是只换名称、模型或数据集
[ ] 是否有可证伪实验和明确 baseline
[ ] 个人设备、时间和预算能否完成
```

候选方向只有同时满足以下条件才进入实现：

```text
问题重要
+ 现有工作存在明确缺口
+ 实验能区分新方法与已有方法
+ 数据与代码可公开复现
+ 结果无论正负都有解释价值
```

每次更新保存：检索日期、检索式、原始来源、支持/反驳证据、结论变化和待验证假设。不要把“暂未搜到”写成“从未有人做过”。

---

## 0. 结论摘要

1. 此前对话中的 **TraceGuard 是一个临时项目概念/系统架构代号，不是已经完成或可安装的应用，也不是从某一篇论文原样改名而来**。它把 provenance/taint、任务级能力、工具调用审计和可选的模型内生信号组合到一起。
2. 完成系统性检索后，这个名字和宽泛创新表述都应撤回：2026 年至少已有两篇 AI 安全论文直接使用 `TraceGuard`，另有同名 PyPI 包和商业产品；与此同时，原方案的大部分通用组件已有直接 prior art。
3. 不能再主张“首次提出字段级 Agent 污点传播”“首次提出任务意图绑定能力”“首次用 hidden state 防 Agent 注入”“首次发现跨工具分片注入”。
4. 仍有三条可以继续验证的窄路线：
   - **S：恶意 MCP server 与跨工具聚合条件下的协议级执行防护**；
   - **I：授权匹配（authorization-matched）的内生表征审计**；
   - **M：中英跨语言、code-switch 与自适应攻击评测**。
5. 若你最看重“大模型内生安全 + 研究创新”，当前首选是路线 I，暂用描述性名称 **GoalAuthBench**；若你最看重“工程落地 + GitHub 展示 + 低算力”，首选路线 S。路线 M 更适合作为 I 或 S 的 OOD 扩展，而不是单独做“翻译数据集”。
6. 在正式开发前先做 10–14 天的 **novelty gate**。只有 pilot 数据支持假设，才投入完整项目；否则及时转向，避免做出一个功能完整但研究主张站不住的项目。

---

## 1. TraceGuard 到底是什么

### 1.1 在本项目语境中的身份

此前对话里的 TraceGuard 是我为以下组合临时起的工作代号：

- 对 Agent 读取的外部数据记录来源与可信度；
- 将来源沿工具调用及参数传播；
- 根据用户任务为危险工具约束能力；
- 在危险 action 执行前进行审计或阻断；
- 可选地研究 hidden state/attention 是否能提前反映任务漂移。

因此当时它只是**提议中的研究系统**：如果实现，它可以成为 Python 库、MCP gateway、benchmark 和可视化 trace viewer；但在提出时并没有现成代码库，也不构成一个已经被学术界定义的独立概念。

它不是从用户截图中的某一篇论文直接改名，不过其组成机制确实受 AgentDojo、CaMeL、FIDES、TaskTracker、Task Shield 等研究范式启发。后续检索证明，这个组合不能被当成新的广义学术贡献。

### 1.2 为什么必须弃用这个名字

名称已严重冲突：

- [TraceGuard: Process-Guided Firewall against Reasoning Backdoors in LLMs](https://arxiv.org/abs/2603.02436)，2026 年预印本；
- [TraceGuard: Structured Multi-Dimensional Monitoring as a Collusion-Resistant Control Protocol](https://arxiv.org/abs/2604.03968)，2026 年预印本；
- [traceguard PyPI 包](https://pypi.org/project/traceguard/)，用于 LLM 历史回测与时间完整性；
- 还存在软件供应链、隐私监控等多个同名商业项目。

继续使用会导致 GitHub 搜索、论文检索、简历解释和包发布发生冲突。本文从此只称“旧 TraceGuard 设想”，不再将其作为项目正式名称。

---

## 2. 研究问题与威胁模型

后续方案共同关注以下场景：

1. 用户向 Agent 提交可信任务；
2. Agent 可以调用邮件、日历、文件、Web、数据库或 MCP 工具；
3. 工具描述、工具返回值、网页、邮件或第三方服务器中含攻击者可控内容；
4. 攻击者希望让 Agent 执行用户未授权的工具、参数、资源目标或数据流；
5. 模型本身可能被注入欺骗，因此不能把“LLM 说这是安全的”视为安全边界；
6. headline 安全指标必须优先由环境状态、工具参数和确定性 predicate 判定，而不是只依赖 LLM-as-a-judge。

暂不覆盖：训练数据投毒、模型权重后门、模型窃取、纯文本有害内容越狱。这些可以是未来项目，但会显著改变研究对象。

---

## 3. 宽泛创新主张的审计结果

| 原候选主张 | 审计结论 | 直接 prior art |
|---|---|---|
| 字段级 provenance/taint 跨工具传播 | 已被直接覆盖 | [FIDES](https://arxiv.org/abs/2505.23643)、[PACT](https://arxiv.org/abs/2605.11039)、[PFI](https://arxiv.org/abs/2503.15547)、[NeuroTaint](https://arxiv.org/abs/2604.23374) |
| task-scoped capability / intent binding | 高度重叠 | [CaMeL](https://arxiv.org/abs/2503.18813)、[Progent](https://arxiv.org/abs/2504.11703)、[MiniScope](https://arxiv.org/abs/2512.11147)、[NCS](https://arxiv.org/abs/2607.15596) |
| Agent source–sink reference monitor | 已是拥挤方向且进入框架产品 | FIDES、PFI、RTBAS；[Microsoft Agent Framework 已实验性集成 FIDES](https://learn.microsoft.com/en-us/agent-framework/agents/security) |
| MCP capability attestation / 消息签名 | 已有协议级方案 | [Breaking the Protocol / MCPSec](https://arxiv.org/abs/2601.17549)、[Securing MCP](https://arxiv.org/abs/2512.06556)、[MCPSHIELD](https://arxiv.org/abs/2604.05969) |
| 多工具协同、跨工具污染 | 已有正式会议工作 | [Les Dissonances，NDSS 2026](https://www.ndss-symposium.org/ndss-paper/les-dissonances-cross-tool-harvesting-and-polluting-in-pool-of-tools-empowered-llm-agents/) |
| 多份额/阈值式注入攻击 | 已被直接提出 | [ShareLock](https://arxiv.org/abs/2606.27027) 使用 Shamir threshold shares |
| 用 hidden state 检测 IPI/task drift | 已有正式会议工作 | [TaskTracker，SaTML 2025](https://arxiv.org/abs/2406.00799)、[InstructDetector，Findings EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.1060/) |
| 用 attention 检测/修复 Agent IPI | 已覆盖 | [Attention Tracker，Findings NAACL 2025](https://aclanthology.org/2025.findings-naacl.123/)、[ICON](https://arxiv.org/abs/2602.20708) |
| activation steering 防多模态 IPI | 已有正式会议工作 | [ARGUS，CVPR 2026](https://arxiv.org/abs/2512.05745) |
| 依据用户目标审核危险 action | 已覆盖 | [Task Shield，ACL 2025](https://aclanthology.org/2025.acl-long.1435/)、[MELON，ICML 2025](https://proceedings.mlr.press/v267/zhu25z.html)、AgentSentry/PlanGuard 预印本 |
| 通用 Agent 注入 benchmark | 已成熟 | [AgentDojo，NeurIPS 2024 D&B](https://arxiv.org/abs/2406.13352)、InjecAgent、ASB、MCP Security Bench |
| 自适应黑盒/RL 注入攻击 | 已覆盖 | [AutoDojo](https://arxiv.org/abs/2606.15057)、[PISmith](https://arxiv.org/abs/2603.13026)、[自动化攻击比较](https://arxiv.org/abs/2606.10525) |
| 简单多语言翻译 benchmark | 已覆盖且有有效性风险 | [MAPS](https://arxiv.org/abs/2505.15935)、[GAIA-v2-LILT](https://arxiv.org/abs/2604.24929) |

### 明确禁止的项目宣传语

- “首个 Agent 工具调用字段级污点系统”；
- “首个 task-scoped capability Agent 防御”；
- “首个 hidden-state IPI detector”；
- “首个 activation steering Agent 防御”；
- “首个多工具协同/分片 prompt injection”；
- “实现了 0% ASR，因此彻底解决 prompt injection”；
- 将 arXiv 预印本写成已被顶会录用。

---

## 4. 重点论文与实验审计

### 4.1 系统级信息流、能力与 MCP 执行安全

#### FIDES：信息流控制已从论文走向框架

- 论文：[Securing AI Agents with Information-Flow Control](https://arxiv.org/abs/2505.23643)，当前 OpenReview 标记为 ICML 2026 submission，不能写作已录用。
- 方法：完整性/机密性标签、标签传播、确定性 policy、选择性隐藏/隔离不可信内容。
- 实验：AgentDojo 多套环境与多种模型；作者报告可把违反策略的工具调用压到接近零，但存在 utility 与 token 开销。
- 工程状态：[微软教程仓库](https://github.com/microsoft/fides)；2026-06 起 [Agent Framework](https://learn.microsoft.com/en-us/agent-framework/agents/security) 已提供实验性的 `agent_framework.security`。
- 对本项目的含义：再做一个“给工具结果贴 trusted/untrusted 标签的 Python middleware”主要是复现或工程整合，不是研究创新。
- 仍有缺口：标签由可信 wrapper/config 提供；恶意 MCP server 主动伪造、剥离、重排标签时的完整性未被充分实证。

#### PACT：参数/字段级来源已经成为直接 prior art

- 论文：[The Granularity Mismatch in Agent Security](https://arxiv.org/abs/2605.11039)，2026-05 预印本。
- 方法：给工具参数分配语义角色，跨 replanning step 追踪 value provenance，并检查不同角色的 trust contract。
- 实验：oracle provenance 下作者报告 100% security/utility；完整 AgentDojo 中，三个较强模型达到 100% security，utility 约 38.1%–46.4%。
- 论文自己指出的剩余瓶颈是 **provenance inference 与 contract synthesis**。
- 对本项目的含义：“argument-level provenance”本身不能主张新；若研究模型内生信号，应瞄准 provenance inference，而不是重做 contract checker。

#### MiniScope / Progent / NCS：任务级最小权限与参数绑定

- [MiniScope](https://arxiv.org/abs/2512.11147)：基于真实 SaaS API 权限层级和 ILP 求最小 OAuth scope；作者报告 1%–6% 延迟开销。它明确留下 scope 内更换资源、收件人或参数的缺口。
- [Progent](https://arxiv.org/abs/2504.11703)：从可信用户任务生成 tool/argument policy DSL，deny-by-default，运行时检查；[代码](https://github.com/sunblaze-ucb/progent)可复现。
- [NCS](https://arxiv.org/abs/2607.15596)：2026-07 预印本，用签名、hash chain 和精确 JSON 参数绑定工作流步骤；因此“密码学 intent binding”也不能再宽泛宣称。
- 可继续研究的边界：开放式动态 MCP 任务、真实 resource downscoping、TTL/次数/金额限制、重放与 TOCTOU，而非“发明 capability”。

#### MCP 协议和跨工具攻击

- [Breaking the Protocol](https://arxiv.org/abs/2601.17549) 已讨论 capability attestation、origin authentication 和多服务器隐式信任，并提出 MCPSec。
- [MCP 威胁建模](https://arxiv.org/abs/2603.22489) 对七种客户端做 tool poisoning 实证，指出静态校验与参数可见性不足。
- [ShareLock](https://arxiv.org/abs/2606.27027) 把恶意指令拆成多个 Shamir shares，作者在两个 MCP clients、四类场景和多模型上报告平均 ASR 超过 90%。
- [Les Dissonances](https://www.ndss-symposium.org/ndss-paper/les-dissonances-cross-tool-harvesting-and-polluting-in-pool-of-tools-empowered-llm-agents/) 在 66 个真实工具上研究 cross-tool harvesting/pollution，正式发表于 NDSS 2026，并提供 [Chord 代码](https://github.com/systemsecurity-uiuc/Chord)。

系统路线真正还能争取的不是某个单独机制，而是：**在恶意、可串通的 MCP server 下，对标签层本身进行完整性保护，并在多工具 evidence 聚合后、危险 effect 执行前做状态化 enforcement。**

### 4.2 模型内生信号：hidden state、attention 与 steering

#### TaskTracker

- [论文](https://arxiv.org/abs/2406.00799)，正式发表于 IEEE SaTML 2025；[项目/代码](https://microsoft.github.io/TaskTracker/)。
- 比较模型读取外部内容前后的 activation delta，用线性 probe 识别 task drift。
- 数据规模超过 500K，覆盖六种模型；作者报告 OOD ROC-AUC 接近或超过 0.99。
- 直接碰撞：如果我们只做 `h(trusted + external) - h(trusted)`，基本就是复现。
- 仍需审计：高 AUC 是否来自“出现了第二条指令”、文本格式、长度或任务类别，而不是实际授权冲突。

#### InstructDetector

- [Findings EMNLP 2025 论文](https://aclanthology.org/2025.findings-emnlp.1060/)；[代码](https://github.com/MYVAE/Instruction-detection)。
- 使用中间层 hidden state 与反向梯度检测外部内容是否含 instruction；Llama-3.1-8B 上作者报告 ID accuracy 99.60%、OOD 96.90%。
- 优点：少量训练样本即可有高检测率。
- 局限：需要 forward + backward，部署与显存代价高；二分类“有无指令”并不等同于“该 action 是否获得用户授权”。RTX 4060 不适合把 8B backward 作为首轮主线。

#### Attention Tracker、ICON 与 ARGUS

- [Attention Tracker](https://aclanthology.org/2025.findings-naacl.123/) 已用注意力从原任务转向注入指令的 distraction effect 做检测。
- [ICON](https://arxiv.org/abs/2602.20708) 直接面向 Agent observation 导致的未授权工具调用，包含 latent prober 与 attention rectifier；截至调研日按预印本处理，未找到正式接收与官方代码证据。
- [ARGUS](https://arxiv.org/abs/2512.05745) 正式发表于 CVPR 2026，已对图像/视频/音频 IPI 做 activation probing/steering，训练使用多张高端 GPU，不适合本地 4060 复现。
- 对本项目的含义：不能主张“首次把 RepE/attention/steering 用于 Agent IPI”。更可靠的问题是：这些 detector 在 action 授权被严格配对后是否仍有效，以及能否在第一个危险工具 token 前给出稳定信号。

#### 工具调用本身也可从表征中读取

2026 年预印本已经研究：

- [Tool Calling is Linearly Readable and Steerable](https://arxiv.org/abs/2605.07990)；
- [Tool-Call Dependency Structure is Linearly Decodable](https://arxiv.org/abs/2605.25310)；
- [Internal Representations as Indicators of Hallucinations in Agent Tool Selection](https://arxiv.org/abs/2601.05214)。

因此“能否从 hidden state 看出将调用哪个工具”不是空白。仍可研究的是：**在工具和参数完全相同的前提下，表征是否编码了可信用户授权与外部诱导之间的差异。**

### 4.3 Benchmark、自适应攻击和评测可靠性

#### AgentDojo

- [NeurIPS 2024 Datasets & Benchmarks 论文](https://arxiv.org/abs/2406.13352)；[MIT 代码](https://github.com/ethz-spylab/agentdojo)。
- 97 个真实任务、629 个 security cases，覆盖 workspace、Slack、travel、banking。
- 最大优点：通过执行前后环境状态与确定性函数评分，避免 headline ASR 完全依赖 LLM judge。
- 截至调研日仓库约 582 stars，说明公开 benchmark、稳定 API、文档、扩展接口和论文共同构成了社区认可，而不是“仅把一个 demo 做完”。
- 最适合作为本项目的主实验框架和潜在 upstream 贡献目标。

#### AutoDojo 与 PISmith

- [AutoDojo](https://arxiv.org/abs/2606.15057) 对 AgentDojo 做黑盒自适应扩展；作者报告某 filter 在静态攻击上 0% ASR，但适应后总体恢复到 28%，action-open 任务达到 64%。[代码](https://github.com/xhOwenMa/AutoDojo)已公开。
- [PISmith](https://arxiv.org/abs/2603.13026) 用 RL 训练攻击模型，代码默认多 GPU，不适合作为 4060 上的 MVP；可把其已发布攻击或小规模子集当 stretch baseline。
- [自动化攻击比较](https://arxiv.org/abs/2606.10525) 显示在合理预算下黑盒 TAP 可优于白盒 GCG，并且小开源模型上的攻击未必能迁移到前沿模型。
- 结论：任何 defense 结果必须同时报告静态攻击和 defense-aware adaptive attack；只测固定模板会产生虚假安全感。

#### 评测器不能成为未审计的单点故障

- [JudgeFlip](https://github.com/gy15901580825/judgeflip) 显示表面 wrapper 可以大幅翻转 LLM judge，白盒攻击也可翻转专用分类器。
- 因此应优先使用 state-based oracle；确需语义 judge 时，要冻结版本、独立 reward judge 与 audit judge，并对分层样本做人类标注、precision/recall 与一致性审计。

#### 多语言不是“翻译一下”

- [MAPS](https://arxiv.org/abs/2505.15935) 已把四个 Agent benchmark 扩到十种语言，但未包含中文。
- [GAIA-v2-LILT](https://arxiv.org/abs/2604.24929) 证明简单机器翻译可能破坏任务功能、文化语境与难度；重新审计后成功率最高可改善 32.7 个百分点。
- 仍未发现一个成熟 benchmark 将“用户任务语言、工具输出语言、注入语言”独立析因，并重点研究中英 code-switch 下的**授权级** Agent 行为。
- 因此中文可成为有效 OOD 变量，但不能作为唯一创新点。

---

## 5. 三条仍可验证的候选路线

## 路线 I（内生安全首选）：GoalAuthBench

### 核心问题

> 现有 hidden-state/attention monitor 检测到的究竟是未授权 action，还是注入文本、工具身份、JSON 格式和长度等表面捷径？

### 关键设计：authorization-matched 四元组

针对同一个目标工具调用 `a* = tool(name, exact_args)` 构造：

- **A（Authorized）**：可信用户明确授权 `a*`，无注入；
- **U（Unauthorized）**：用户未授权，但外部工具内容诱导出完全相同的 `a*`；
- **D（Distractor）**：同域、同长度、无注入的 benign distractor；
- **I（Injection-only）**：有注入表面，但未导致未授权 action。

A/U 必须共享同一序列化 tool name 与 exact args。teacher-forced action 用于机制分析，另保留自然 rollout 子集验证系统级安全。这样才能剥离“工具/参数/格式”捷径，把标签真正定义为 authorization violation。

### 研究问题

- RQ1：TaskTracker、hidden-state probe、attention entropy 在 authorization-matched OOD split 上是否仍有效？
- RQ2：它们是否只学习 tool ID、攻击模板、长度或 instruction-like 文本？
- RQ3：goal-conditioned 表征差分是否在同工具同参数条件下提供额外信号？
- RQ4：信号是否在第一个危险工具 token 之前出现，足以支持 pre-execution gate？
- RQ5：英文训练后，中文与中英 code-switch 是否造成系统性失效？

### 基线与消融

- B0：tool + args only；
- B1：TF-IDF/轻量文本分类器；
- B2：TaskTracker activation delta；
- B3：跨层 residual trajectory / MTK-lite；
- B4：短 action-prefix 的 TrajGuard-lite；
- B5：小子集 ICON-lite attention entropy；
- B6：低秩 goal ↔ pre-action state probe；
- 消融：random labels、去掉用户目标、去掉外部数据、只保留工具 JSON、长度配平、攻击模板留一、工具族留一、suite 留一、语言留一、模型留一。

### 数据与 split

- 主框架：AgentDojo 四套环境；
- pilot：100–200 个严格配对 trajectory；
- MVP：800–1,200 个 trajectory；
- split 必须按 task/template/tool family/domain/injection goal 分组，禁止 paraphrase 泄漏到 train/test；
- 中文扩展采用功能对齐，不只做逐句翻译；工具返回语言和攻击语言独立变化。

### 指标

- 检测：AUROC、AUPRC、TPR@5% FPR、FPR@95% TPR、ECE、Brier；
- 增量：相对最强非 latent baseline 的 conditional ΔAUROC；
- 时序：首个工具 token 前的 lead time；
- 系统：ASR、clean utility、utility under attack、worst-suite；
- 工程：p50/p95 latency、VRAM、磁盘、每 trajectory 成本；
- 统计：3 seeds、trajectory-level bootstrap 95% CI。

### 预注册式成功/失败门槛

- H1：随机 clean-vs-attack AUC 显著高于 authorization-matched OOD AUC，支持“已有方法学习了 shortcut”；
- H2：最佳 latent 方法相对最强非 latent baseline 提升至少 5 个百分点，且 TPR@5%FPR ≥ 70%；否则结论应是“latent 未提供部署级增量”；
- H3：必须在首个危险工具 token 前告警；若等到完整调用/整段生成后才发现，不能声称 pre-execution；
- H4：action gate 将 ASR 相对降低至少 50%，clean utility 损失不超过 5 个百分点；否则仅作为分析工具，不包装成防御产品。

### 4060 可行配置

- 先用 Qwen2.5-1.5B-Instruct FP16 pilot；clean utility 不足再试 Qwen2.5-3B/Qwen3-4B 4-bit；
- context 1,024–1,536，batch 1；只 hook 25%/50%/75%/final 层和少量关键 token，立即搬到 CPU；
- 不保存全部 token × 全部层的 activation；
- attention O(n²)，只在 100–200 个短样本做 ICON-lite；
- 不做 8B backward 和多模态 ARGUS；
- 预计 pilot 约 10–30 GPU-hours，probe 训练可在 CPU 完成。实际时间须通过首批 20 trajectories 记录后修正。

### 研究价值与风险

- 价值：直接检验高 AUC 是否对应真实安全边界；负结果同样有价值；符合“内生安全”兴趣。
- 风险：小模型 Agent utility 可能太低；已有 workshop 已研究 latent shortcut，因此贡献必须严格落在“同 action/args 的授权配对 + end-to-end state oracle”。
- 名称：`GoalAuthBench` 仅为当前检索未发现明显冲突的临时名称，正式发布前仍需再次查重。

## 路线 S（系统与工程首选）：恶意 MCP server 下的状态化执行防护

### 核心问题

> 在 MCP server 本身恶意、会伪造/剥离来源标签或与其他工具协同时，透明 gateway 能否保持 provenance 完整性，并阻止聚合后才显现的未授权 effect？

### 可分解的三个实验假设

#### S1：防剥离 provenance

- 在透明 MCP proxy 中记录 out-of-band provenance；
- 跨 `tools/list`、`tools/call`、缓存、重试、多服务器和跨会话保持链；
- 测试 label stripping、伪造 trusted、JSON 重排/嵌套、schema drift、错误响应、摘要改写和 replay；
- 基线：普通 FIDES 风格标签、无标签、只做签名的 manifest。

注意：MVAR 已宣称 cryptographic provenance，MCPSec/MCPSHIELD 也覆盖相邻机制，因此贡献必须依赖**真实 MCP 互操作和恶意服务器实验**，不能只是“给日志加 hash”。

#### S2：资源/参数/时效绑定 capability

- capability 绑定 server、tool、文件/对象 ID、收件人、金额上限、TTL、调用次数；
- gateway/resource adapter 真正 downscope，而不只由 LLM 判断；
- 攻击：scope 内换收件人、换路径、换金额、审批后改参、token replay、并发与跨 server confusion；
- 基线：MiniScope-style scope、Progent-style local policy、无防护。

注意：不能声称发明 capability；只能主张 MCP intent 到可验证、可衰减能力的端到端落地与实证。

#### S3：ShareLock 的状态化聚合防御

- 逐工具 scanner 看不到单份 share，因此 monitor 必须跨工具描述、返回值、memory 和最终 sink 聚合；
- 扫描不同 `(n,t)`、share 顺序、单/多 server、更新前后和 defense-aware adaptive attacker；
- 指标：ASR@3、trigger completion rate、FPR、正常高熵 metadata 误报、utility、p95 latency；
- 结构性 enforcement 在检测不确定时 fail-closed，避免把防御完全押在语义 detector 上。

### 交付形态

- Python/Rust MCP transparent proxy；
- 可组合 policy/capability engine；
- 恶意 MCP fixture servers；
- ShareLock/Les Dissonances 风格 adaptive benchmark；
- trace viewer 展示 source → transform → argument → sink；
- Docker/Devcontainer、一键复现实验、完整 event log 与环境 diff。

### 研究价值与风险

- 价值：训练成本低、系统安全叙事清晰、demo 强、适合 GitHub；ShareLock 防御是很新的问题。
- 风险：2026 年 MCP 安全论文和产品增长极快；cryptographic provenance、capability gateway、FlowGuard/MCPShield 等名字与系统都很拥挤，必须持续做 prior-art watch。
- 不能再用 `TraceGuard`、`FlowGuard`、`MCP-FlowGuard`、`MCPShield` 等已冲突名称。

## 路线 M（作为扩展）：中英跨语言 × 自适应攻击

### 真正可研究的变量

不是“把英文任务翻成中文”，而是把以下变量独立控制：

- 用户任务：EN / ZH；
- 不可信工具内容：EN / ZH；
- 注入载荷：EN / ZH / code-switch；
- 任务开放度：fully specified / parameter-open / action-open；
- 攻击：静态模板 / AutoDojo 式 defense-aware 优化。

完整语言析因是 `2 × 2 × 3 = 12` 个条件。它最适合成为路线 I 的 OOD split，或路线 S 的跨语言攻击集。

### 评测要求

- 保持同一可执行任务、工具参数和安全目标功能对齐；
- headline 指标使用环境状态 predicate；
- 分语言报告 ASR、utility、invalid rate、cost 和 CI；
- 若使用 judge，抽取 10%–20% 分层样本做双人中英标注和第三方裁决；
- 检查 defense ranking 是否在语言切换与 adaptive attack 下反转。

---

## 6. 推荐选择与 14 天 novelty gate

### 当前排序

| 路线 | 研究新颖性 | 工程展示 | 4060 适配 | 发表风险 | GitHub 潜力 | 与“内生安全”匹配 |
|---|---:|---:|---:|---:|---:|---:|
| I：授权匹配 latent audit | 中高（条件性） | 中高 | 高 | 中高 | 中高 | 最高 |
| S：恶意 MCP + 状态化 enforcement | 中高（快速变化） | 最高 | 最高 | 中 | 高 | 中 |
| M：中英自适应 benchmark | 中 | 高 | 中高 | 中 | 高 | 中 |

推荐：如果你的第一优先级仍是“大模型内生安全”，以 **路线 I 为主、M 为 OOD 扩展**；如果更重视系统安全岗位和可演示产品，以 **路线 S 为主**。

### 第 1–3 天：环境与最小复现

- 跑通 AgentDojo 两个 clean tasks、两个 attack cases；
- 固定 Python/CUDA/模型版本、seed、prompt format；
- 验证 state-based scorer；
- 记录单 trajectory 的时间、VRAM、token 和失败类型。

### 第 4–7 天：两条小 pilot 并行

I-pilot：

- 手工构造至少 25 组 A/U 配对；
- 抽取四层 last-token/pre-action states；
- 比较 tool+args baseline、文本 baseline 和 TaskTracker-style delta；
- 检查随机 split 与 grouped OOD split 差距。

S-pilot：

- 构造两个本地 MCP servers，其中一个可修改 tool description/result；
- 复现单工具 poisoning 与最小多工具聚合攻击；
- 实现无模型的 sink allow/block policy；
- 测 label stripping、参数替换和 replay。

### 第 8–10 天：证伪与算力门槛

- 若开源小模型 clean tasks 可正确完成的数量过少，不做端到端防御主张，改为 teacher-forced mechanism audit；
- 若 TaskTracker-style 方法在 A/U 配对上仍近乎完美，说明路线 I 的 shortcut 假设不成立，应转向更强 OOD 或路线 S；
- 若结构 policy 已能完全阻断聚合攻击，研究重点应转为 utility/动态授权，而不是堆 detector；
- 若 MCP prior art 新检索已直接覆盖 S1–S3，则及时缩小或换题。

### 第 11–14 天：Go / Pivot 决策包

输出：

- 100–200 行可复现实验脚本；
- 25–100 个可审计样本；
- 一页结果表和失败案例；
- novelty matrix 更新；
- 实际算力/API 成本；
- Go/Pivot 决策及 8–12 周正式计划。

只有满足以下任一条件才进入完整开发：

1. 发现可重复的 authorization-matched shortcut/latent 增量；
2. 发现现有 MCP 防护在恶意 server/聚合攻击下的稳定缺口；
3. 发现中英语言交互导致防御排名或安全边界发生显著变化。

---

## 7. 简历与 GitHub 认可标准

“完成一个项目”当然可以写简历，但认可度取决于可验证证据，不取决于仓库是否有一个漂亮首页。最低合格线：

- 明确威胁模型和不覆盖范围；
- 可复现实验与固定环境；
- 与强 prior art/baseline 正面对比；
- state-based oracle、统计区间、成本与失败案例；
- 数据卡、模型卡、伦理与安全说明；
- 单元测试、CI smoke test、Docker/Devcontainer、release；
- 完整 trajectory、环境 diff 和可视化，而非只给最终 ASR；
- 尽量向 AgentDojo/相关基准提交 upstream PR；
- 发布技术报告或预印本，并用 Zenodo DOI 固化 release。

GitHub stars 是传播结果，不是研究质量的替代品。AgentDojo 约 582 stars、CaMeL 约 332 stars、FIDES 约 94 stars（均为 2026-07-21 附近检索快照）；它们同时具备机构/论文背书、清晰问题、开放 artifact 和社区时机。个人项目更现实的目标是：被复现、被引用、被 upstream 接受、获得真实 issue/PR，而不是先给自己设一个 star 数 KPI。

可安全写入简历的表述模板：

> 构建 AgentDojo 兼容的 authorization-matched 扩展集，在保持工具名与参数完全一致的条件下审计多类 latent monitors；采用 grouped OOD split、环境状态 oracle 和 bootstrap CI 量化表面捷径，并实现首个危险工具 token 前的 action gate，使 ASR 从 X 降至 Y，clean utility 损失 Z 个百分点。

或系统路线：

> 实现透明 MCP security gateway，在未修改 client/server 的条件下追踪跨工具 provenance，并以资源/参数/TTL 绑定能力阻断恶意服务器的 label stripping、参数替换、重放与阈值聚合攻击；在 N 个客户端/服务器组合上将 ASR 从 X 降至 Y，p95 增量延迟为 Z ms。

上述数字必须来自最终可复现实验，不能预填。

---

## 8. 当前仍需用户确认的信息

在确定 8–12 周实施计划前，需要确认：

1. 你更想把第一成果定位成“模型内生机制/论文型”还是“MCP 系统安全/工程型”？
2. RTX 4060 的显存是 8GB 还是 16GB？
3. 你当前对 Python、PyTorch hooks、Transformers、Docker、Agent/MCP 的熟悉程度分别如何？
4. 除本地算力外，可接受的 API/云算力总预算和目标完成日期是什么？
5. 目标更偏研究生申请/论文、AI 安全实习，还是安全工程/后端岗位？

这些答案会改变模型规模、实验矩阵、项目主线和最终交付物，不能用同一份模板代替。
