# GoalAuthBench 整体方案重审报告

> 日期：2026-07-27  
> 审查对象：[GoalAuthBench v0.1 初版方案](./GoalAuthBench_个人AI安全项目初版方案.md)  
> 审查方式：系统安全、内生表征与实验方法、个人工程与简历价值三路独立审查，再做交叉核验  
> 结论强度：基于截至本日可检索的论文、预印本、公开代码和项目文档；预印本结论不等同于同行评审结论

## 1. 最终结论

**项目可以继续，但原方案不能按原样执行。**

原方案把以下四个足以独立成项的工作放进了一个首版：

1. 授权反事实 benchmark；
2. hidden-state 机制审计；
3. AgentDojo 端到端防御；
4. 可部署 authorization middleware 与可视化产品。

对个人、LLM 初学者和 RTX 4060 8GB 而言，这相当于一个小型实验室的连续研究路线，而不是一个高完成率的首个公开项目。更关键的是，2026 年 3–7 月出现了多项与原核心主张直接重合的工作。继续使用“提出上下文授权”“首次用相同动作区分授权”“首个 hidden-state 未授权动作 gate”等表述，已经不成立。

建议把项目改成：

> **一个面向 LLM Agent 的授权反事实与捷径审计项目：在整个候选工具调用及全部 typed canonical arguments 联合相同、并系统控制真实来源权限、可伪造来源声称与文本干扰因素时，比较 deterministic policy、文本/语义方法、因果重放和 hidden-state probe 对授权状态的增量判别能力。**

项目仍然有简历价值，因为价值从“抢一个宽泛的新概念”转为：

- 对刚出现的研究问题做及时、严谨、可复现的实证审计；
- 构造高质量控制组和数据验证器；
- 统一复现多类 baseline；
- 实现真正位于工具提交边界的安全 gate；
- 发布数据、代码、实验记录、负结果和失败案例。

但需要接受一个事实：**这是“研究工程 + 严格审计”的定位，不是目前就能承诺顶会算法创新的定位。**

## 2. 审查评分

| 维度 | v0.1 原方案 | v0.2 收缩方案 | 说明 |
| --- | ---: | ---: | --- |
| 个人可完成性 | 3/10 | 8/10 | 删除多语言全矩阵、四 suite、完整 viewer 和大规模 adaptive |
| 科学问题清晰度 | 4/10 | 8/10 | 拆分显式授权、隐式授权和注入检测 |
| 当前差异化 | 3/10 | 6.5/10 | 核心概念已被覆盖，剩余价值在严格控制与统一审计 |
| 实验可信度 | 5/10 | 8/10 | 增加授权 oracle、T2 边界、分组统计和干扰控制 |
| 简历可解释性 | 5/10 | 9/10 | 一句话问题、四个核心数字、可运行 artifact |
| GitHub 传播潜力 | 5/10 | 8/10 | 60 秒 quickstart、数据验证器、失败画廊和上游适配 |
| 硬件/预算匹配 | 5/10 | 9/10 | 1.5B–7B 量化、少层少 token、API 分阶段封顶 |

若按学术审稿口径，v0.1 当前更接近 **Weak Reject**；若按简历项目口径，v0.2 有机会成为高质量的研究型系统项目。

## 3. 对创新性的直接冲击

### 3.1 核心概念已被明确提出

[A Framework for Formalizing LLM Agent Security](https://arxiv.org/abs/2603.19469) 已明确指出：

- 同一个动作会因授权者、目标和上下文不同而合法或违规；
- Agent 安全应包含 task alignment、action alignment、source authorization 和 data isolation；
- 可用目标、轨迹、动作、指令归因和来源归因等 oracle 来形式化安全性质。

因此，“动作是否安全取决于上下文授权，而不是动作内容本身”不能再作为本项目的概念创新。

2026-07-24 发布的 [Agent Security Needs Redefinition through a Holistic Framework](https://arxiv.org/abs/2607.22024) 又对 AgentDojo 和 WASP 中的攻击任务构造了同动作的合理授权场景，进一步表明“同动作、不同授权”已成为公开论证的核心观点。

### 3.2 来源授权受控审计已有直接近邻

[Auditing Provenance Sensitivity in LLM Agent Action Selection](https://arxiv.org/abs/2607.20827) 于 2026-07-23 发布，已经：

- 固定任务、命题、位置与策略；
- 只改变命题的来源授权；
- 构造 450 个受控 next-action 任务；
- 测试来源变化、证据弱化和上下文子集交互；
- 使用按 source task 聚类的置信区间。

这与 v0.1 的“authorization-matched 数据 + source swap”高度重合。它并未完全覆盖“固定候选工具调用后的 hidden-state 增量审计”，但已经使数据配对本身不再足以成为主要新意。

### 3.3 行为因果归因已有强基线

[AttriGuard](https://arxiv.org/abs/2603.10749) 使用 action-level causal attribution、teacher-forced shadow replay 和控制衰减，判断工具调用是否由用户目标支持。

[CausalArmor](https://arxiv.org/abs/2602.07918) 在高权限决策点使用 leave-one-out 因果归因和选择性净化。

这两项工作直接覆盖“为什么产生该工具调用”“工具调用是否由不可信观察驱动”的问题。任何新的实验都必须至少把轻量 counterfactual replay 作为强 baseline，而不能只和 TF-IDF 或普通 prompt-injection classifier 比较。

### 3.4 hidden-state 未授权动作检测已有直接近邻

[Your Agent is More Brittle Than You Think](https://arxiv.org/abs/2604.03870) 已在动态多步工具环境中，于 tool-input 位置提取 hidden state，并用 Representation Engineering circuit breaker 拦截未授权动作。

[ICON](https://arxiv.org/abs/2602.20708) 已覆盖 latent trace prober 与 attention steering。

[When AUC 0.998 Is Not Enough](https://arxiv.org/abs/2606.22864) 则直接警告：teacher-forced hidden-state probe 的极高 AUC 可能来自配对构造和视觉/文本表面干扰，不能直接解释为学到了恶意语义。

所以 hidden-state 只能保留为以下窄问题：

> 在 exact-candidate-action、来源匹配和干扰控制下，hidden-state 相对最强非 latent baseline 是否仍有可重复的增量预测效用？

不能宣称发现了独立的“授权神经变量”，也不能把线性可解码等同于模型在因果上使用了该表征。

### 3.5 显式授权 gate 已高度拥挤

以下工作已覆盖显式策略、provenance、精确参数或提交边界：

- [Context-to-Execution Integrity](https://arxiv.org/abs/2607.06000)：field authority、exact-effect authorization、invocation authority 与 action manifest；
- [PACT](https://arxiv.org/abs/2605.11039)：参数角色与跨步骤 provenance contract；
- [Capability Gates Are Not Authorization / ScopeGate](https://arxiv.org/abs/2606.28679)：逐调用、逐值授权；
- [NetInjectBench](https://arxiv.org/abs/2607.10490)：分离不可信 artifact、可信 policy metadata 与高影响控制；
- [FIDES](https://arxiv.org/abs/2505.23643) 与 [CaMeL](https://arxiv.org/abs/2503.18813)：信息流、能力和确定性执行边界。

因此，authorization gate 应是 benchmark 的演示消费者和工程交付物，不应与 benchmark 并列宣称为第二项研究创新。

## 4. 原方案的关键科学问题

### 4.1 Authorization 没有被形式化为可判定真值

授权不是 action 或 activation 的固有标签。至少需要定义：

```text
Auth(principal, session, goal, policy, state, history, action, provenance, time)
  -> ALLOW | DENY | AMBIGUOUS
```

其中：

- `principal`：经过认证的授权主体；
- `session`：会话、租户与委托链上下文；
- `goal`：可信用户目标；
- `policy`：授权范围、委托边界和资源约束；
- `state`：动作前环境状态；
- `history`：已执行动作与已消耗授权；
- `action`：canonical action manifest；
- `provenance`：关键参数的来源；
- `time`：有效期、撤销和重放状态。

AgentDojo 的 state scorer 能证明任务结果或攻击结果，不能单独证明逐动作授权。项目必须分别维护：

1. authorization oracle；
2. environment state oracle；
3. task utility oracle。

### 4.2 显式授权与隐式授权混成了一题

显式结构化 policy 下，deterministic PDP/PEP 往往应该饱和；这时 latent detector 没有必要。

自然语言隐式委托下，规则需要语义解释，标签可能歧义；这时必须允许 `AMBIGUOUS`，并需要第二位盲标者复核一部分样本。

两者应拆成：

- **Track E：Explicit policy**，工程上界与确定性 gate；
- **Track I：Implicit delegation**，研究主线；
- **Track D：Injection/drift diagnostics**，攻击与困难控制组。

### 4.3 A/U 同 action 不等于只改变了授权因果变量

A/U 上下文仍会改变用户目标、消息角色、位置、措辞、长度或来源标记。probe 可能只学到：

- user/tool role；
- `trusted`/`untrusted` 字样；
- 祈使句和 override 词；
- 上下文位置或长度；
- 特定模板和生成器风格。

因此 matched pair 只能支持“受控预测评测”，不能自动支持“识别到授权因果表征”。必须增加：

- role/source-matched controls；
- authorized external delegation；
- 没有典型注入措辞的未授权操纵；
- 同长度、同位置、同领域控制；
- provenance-only 与 nuisance-only baseline；
- 保持授权不变、只改变表面因素的反事实。

特别需要将两种“来源”分开：

- trusted runtime 产生、内容无法伪造的 operational provenance；
- 攻击者可在正文中写出的 `TRUSTED`、签名外观或来源声称。

首版应使用 `真实 source authority × 可见 source claim` 的 2×2 控制，避免把相信字符串标记误写成来源授权。

### 4.4 随机到 OOD 的下降不等于证明捷径

性能在 grouped OOD 下降只能证明分布转移。要论证 shortcut，至少需要以下证据之一：

- nuisance-only predictor 已能取得很高性能；
- 保持授权不变、仅改变干扰因素会让分数系统性翻转；
- 去除或平衡干扰因素后性能显著下降；
- source-matched hard subset 上原高分消失。

### 4.5 Teacher forcing、自然 rollout 与部署时间点混淆

统一定义：

- `T0`：读完外部内容，尚未生成 tool call；
- `T1`：生成 tool name，arguments 未完整；
- `T2`：完整 tool call 已缓冲、解析并 canonicalize，但 executor 尚未 commit；
- `T3`：工具执行后。

首版部署主张只能是 **T2 pre-commit gate**。在完整 forced action 后提取状态再声称是“生成前检测”会使用未来 token。

Teacher-forced 实验只回答表示审计问题。Natural rollout 必须单独报告：

- 模型产生未授权 proposal 的比例；
- proposal 被 gate 阻断的比例；
- committed unauthorized action；
- 最终环境 harm；
- clean utility 与延迟。

### 4.6 统计功效不足

25 组 pair 足以验证管线，不足以支持 1% FPR、跨模型、跨语言和多个 OOD 结论。

- 若观察到 0 个 benign false positive，要让单侧 95% 上界低于 1%，至少约需 299 个独立 benign 样本；
- 若希望在 1% FPR 附近观察约 30 个误报以稳定估计，需要约 3,000 个独立 benign 样本；
- 独立单位应是 base scenario/task，而不是同一任务派生出的 trajectory；
- pair、翻译、paraphrase、相同原任务和生成器 lineage 必须处于同一 split；
- threshold 必须在独立 calibration split 冻结。

首版不应把 `TPR@1% FPR` 作为主结论。

## 5. 保留、修改、推迟和删除

| 原组件 | 决策 | 新定位 |
| --- | --- | --- |
| authorization-matched pair | 保留但改写 | 受控审计方法，不再称概念创新 |
| exact tool + arguments | 保留 | 候选 action 控制与验证器核心 |
| A/U/D/I 四分类 | 修改 | A/U 为主；AE/UC 为控制；D/I 降为 hard controls |
| AgentDojo | 保留 | 首版只做 Workspace/Email 和 2 个副作用工具 |
| state-based oracle | 保留但拆分 | 只判断环境结果；授权另有 policy oracle |
| TF-IDF/goal-action | 保留 | 最低 baseline |
| provenance/nuisance-only | 新增 | 检验 source shortcut |
| counterfactual replay | 新增 | AttriGuard-lite 强非 latent baseline |
| hidden-state probe | 降为可选 | 通过 novelty gate 后再做 |
| action-prefix early warning | 首版删除 | 与 T2 主问题不同 |
| allow/block/confirm | 修改 | MVP 为 policy-first allow/block；confirm 仅记录 `would_confirm` |
| 完整 viewer | 删除 | 静态 error gallery 替代 |
| 四个 AgentDojo suite | 推迟 | v1 后扩展 |
| 12 单元多语言矩阵 | 推迟 | 后续只加 15–20 对中文 challenge slice |
| adaptive white-box attack | 推迟 | 首版只做小预算黑盒子集 |
| 14B/跨 CUDA-MLX activation | 删除 | 不混合后端 activation |
| MCP gateway | 删除 | 与首版研究问题无直接关系 |

整体范围减少约 60%–70%。

## 6. 三个可能转向的比较

| 路线 | 差异化 | 可完成性 | 简历价值 | 风险 |
| --- | ---: | ---: | ---: | --- |
| A. 继续做“大而全授权防御” | 低 | 低 | 中 | 与 CXI、FIDES、ScopeGate 等正面重合 |
| B. 只做 hidden-state 新方法 | 中低 | 中 | 中 | ICON、Brittle、TaskTracker 已拥挤，容易做成高 AUC shortcut |
| **C. 授权反事实 + 多范式审计** | **中高** | **高** | **高** | 创新较窄，但问题诚实、artifact 可用 |

推荐 C。

## 7. 新的贡献层级

### 必须交付的主贡献

1. 一个严格 schema 化的授权反事实控制集；
2. exact action、参数、来源和 split lineage 验证器；
3. deterministic、文本、语义、provenance 和 counterfactual replay 的统一评测；
4. random split 与预注册 grouped OOD 的捷径诊断；
5. 可复现的负结果/失败案例。

### 工程交付

1. 完整 tool call 缓冲；
2. canonical action manifest；
3. policy-first T2 PEP，持有真实凭据并成为副作用工具的唯一 dispatch 路径；
4. state diff、事件日志和静态 error gallery；
5. CLI、测试、Docker/uv、release 和数据卡。

### 条件性研究扩展

只有强非 latent baseline 完成、数据控制通过质量门后，才加入 selected-layer hidden-state probe。只有 probe 在预注册 OOD 上有稳定增量，才继续跨模型、中文或 adaptive evasion。

## 8. 可以与不可以写的创新表述

### 可以写

> We build a controlled, exact-candidate-action audit that measures whether practical authorization detectors retain predictive utility after source, template, action, and nuisance controls.

> We compare deterministic policy checks, provenance/text baselines, counterfactual replay, and selected-layer probes under grouped out-of-distribution evaluation.

> We release paired data, validators, traces, manifests, failure cases, and a pre-commit tool-call gate.

### 不可以写

- 首次提出上下文授权；
- 首次证明同动作可因来源不同而违规；
- 首个检测未授权工具调用的 hidden-state 方法；
- state scorer 就是 authorization oracle；
- 线性可解码证明模型使用了授权机制；
- 随机到 OOD 下降自动证明 shortcut；
- teacher-forced 高 AUC 等同于端到端安全。

相对 [2607.20827](https://arxiv.org/abs/2607.20827)，仍可检验的最窄差异是：

1. 整个 canonical call 与全部 typed arguments 联合固定，而不是只对单个 target 做审计；
2. 系统比较第三方 detector、goal/policy matcher、counterfactual replay 与 model-internal probe；
3. 区分 trusted runtime provenance 与正文中可伪造的 source claim；
4. 检查跨 renderer/tool family 的 shortcut failure；
5. 将检测结果接到完整调用解析后、PEP dispatch 前的工程边界。

这属于窄扩展，不能再称“首个 authorization-matched benchmark”。

在完成系统性查重和实验证据前，不使用 `first`。

## 9. 简历与开源价值判断

GitHub stars 不是可预先保证的成果，也不是项目可信度的充分条件。一个更可靠的成果栈是：

1. 可安装和可运行；
2. 有版本化数据和稳定 schema；
3. 有复现实验与明确负结果；
4. 有技术报告、数据卡、模型卡和 DOI；
5. 有 AgentDojo adapter 或上游 PR；
6. 有清晰 issue、release 和 changelog；
7. 能在面试中独立解释 threat model、标签、指标和一个失败案例。

README 首屏应该让访问者在 15 秒内理解：

> Authorized and unauthorized contexts are evaluated against the same candidate tool call. Which monitors still work after source and surface shortcuts are controlled?

最终简历最好只呈现四类实测数字：

- 独立 matched group 数；
- random 到 grouped OOD 的变化；
- strongest non-latent 到 latent 的增量或“无增量”结论；
- gate 对 committed unauthorized action、utility 与 p95 latency 的影响。

负结果并不会让项目失去简历价值。一个控制严谨、可复现的“显式授权下 latent 不必要”或“高 AUC 来自来源捷径”的结论，通常比一个无法解释的 99% accuracy 更有辨识度。

## 10. 最终建议

1. 冻结 v0.1 为历史文件，不继续在其宽范围上编码；
2. 以 [v0.2 重审执行版](./GoalAuthBench_v0.2_重审执行版_2026-07-27.md) 为唯一执行计划；
3. 保留 `GoalAuthBench` 作为临时代号，公开前再做名称查重；
4. 第一阶段只投入 4 周和不超过 50 美元，先证明数据与评测设计成立；
5. 第一公开版本以 benchmark、validator 和 baseline audit 为主；
6. hidden-state、中文、adaptive attack 依次通过质量门后加入；
7. deterministic gate 作为工程演示，不宣称新安全架构；
8. 每月更新 prior-art matrix，因为该方向当前变化非常快。

目前没有阻止启动 Phase 0 的待澄清问题。模型具体选择、AgentDojo 版本和公开项目名称应在实现时依据兼容性 smoke test 决定，而不是现在过早锁死。

## 11. 核心参考

- [A Framework for Formalizing LLM Agent Security](https://arxiv.org/abs/2603.19469)
- [Agent Security Needs Redefinition through a Holistic Framework](https://arxiv.org/abs/2607.22024)
- [Auditing Provenance Sensitivity in LLM Agent Action Selection](https://arxiv.org/abs/2607.20827)
- [AttriGuard](https://arxiv.org/abs/2603.10749)
- [CausalArmor](https://arxiv.org/abs/2602.07918)
- [Context-to-Execution Integrity](https://arxiv.org/abs/2607.06000)
- [Your Agent is More Brittle Than You Think](https://arxiv.org/abs/2604.03870)
- [When AUC 0.998 Is Not Enough](https://arxiv.org/abs/2606.22864)
- [AgentDojo](https://arxiv.org/abs/2406.13352)
- [TaskTracker](https://arxiv.org/abs/2406.00799)
- [Task Shield](https://aclanthology.org/2025.acl-long.1435/)
- [FIDES](https://arxiv.org/abs/2505.23643)
- [CaMeL](https://arxiv.org/abs/2503.18813)
- [PACT](https://arxiv.org/abs/2605.11039)
- [AutoDojo](https://arxiv.org/abs/2606.15057)
- [The Attacker Moves Second](https://arxiv.org/abs/2510.09023)
- [MUZZLE](https://arxiv.org/abs/2602.09222)
