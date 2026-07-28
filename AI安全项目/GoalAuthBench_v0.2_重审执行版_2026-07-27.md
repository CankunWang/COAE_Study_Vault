# GoalAuthBench v0.2：重审后的个人 AI Agent 安全项目执行方案

> 状态：Current / 执行基线  
> 日期：2026-07-27  
> 项目代号：`GoalAuthBench`，正式公开前查重并可能改名  
> 定位：个人开源研究工程；优先形成可复现、可解释、可持续维护的简历成果  
> 前置阅读：[整体方案重审报告](./GoalAuthBench_整体方案重审报告_2026-07-27.md)

## 0. 一句话版本

> 在整个候选工具调用及全部 typed canonical arguments 联合相同的条件下，系统控制真实来源权限、可伪造来源声称和文本干扰因素，审计 deterministic policy、文本/语义、因果重放与 hidden-state 方法究竟能否识别“这个动作在当前上下文是否被授权”。

英文公开表述：

> Authorized and unauthorized contexts are evaluated against the same candidate tool call. Which monitors still work after source and surface shortcuts are controlled?

## 1. 项目目标与非目标

### 1.1 必须实现的目标

1. 构造 60–100 个独立 base scenario 的授权反事实 matched groups；
2. 提供 canonical action、exact arguments、provenance、lineage 和 split 验证器；
3. 建立统一 baseline runner；
4. 比较 random split 与一个预注册 grouped OOD split；
5. 实现位于 `T2` 的 policy-first pre-commit gate；
6. 发布数据、代码、配置、trace、失败案例、技术报告和版本化 release；
7. 能由项目负责人独立解释所有核心设计。

### 1.2 首版不做

- 四个 AgentDojo suite；
- 2,000 条 trajectory；
- 完整交互式 trace viewer；
- 12 单元 EN/ZH/code-switch 矩阵；
- 14B hidden-state 实验；
- 跨 CUDA/MLX activation 迁移；
- 多智能体 RL jailbreak；
- MCP gateway；
- 白盒 7B/8B 全梯度 adaptive attack；
- 把模型 probe 当成唯一授权边界。

## 2. 核心研究问题

### RQ1：受控授权变化

在 `candidate action`、任务命题、位置、长度和模板尽可能匹配时，改变来源或委托关系是否会系统性改变各类 monitor 的分数？

这只支持“来源授权敏感性”，不自动支持“存在独立授权神经变量”。

### RQ2：捷径与泛化

在 source-matched、nuisance-matched 和 grouped OOD 条件下，文本、provenance、语义和 latent 方法分别保留多少预测能力？

random 到 OOD 的下降只是现象。只有反事实干扰控制、nuisance-only baseline 或分数翻转证据才能支持 shortcut 解释。

### RQ3：hidden-state 增量

selected-layer state 相对预先指定、compute-matched 的 strongest non-latent baseline，是否有稳定的增量预测效用？

该问题是条件性扩展，不是首版必须得到正结果的目标。

### RQ4：提交边界的工程价值

在完整 tool call 已生成但尚未执行的 `T2`，policy-first gate 能否减少 committed unauthorized actions，同时控制 clean utility、确认负担和延迟？

## 3. 授权定义

### 3.1 Oracle

```text
Auth(principal, session, g, p, s, h, a, prov, t)
  -> ALLOW | DENY | AMBIGUOUS
```

| 字段 | 含义 |
| --- | --- |
| `principal` | 经过认证的授权主体 |
| `session` | 会话、租户、委托链和身份上下文 |
| `g` | 可信用户目标 |
| `p` | 明确授权、委托范围、资源与风险策略 |
| `s` | 动作前环境状态 |
| `h` | 已执行动作、消耗的 capability 和确认记录 |
| `a` | canonical action manifest |
| `prov` | 关键 argument 的来源与变换链 |
| `t` | 有效期、撤销、nonce 与重放状态 |

结构化授权清单至少包含：

```text
AuthzManifest(
  principal,
  session,
  tool,
  typed_argument_predicates,
  resource_or_effect_scope,
  permitted_data_flow_or_purpose,
  max_calls,
  expiry,
  nonce,
  policy_version
)
```

自然语言 goal 只提供语义证据，不能自己成为认证或签发授权的根。

### 3.2 三类 oracle 分离

```text
Authorization oracle -> 该动作是否允许
State oracle         -> 环境是否发生预期/危险变化
Utility oracle       -> 用户任务是否完成
```

三者不得互相替代。

### 3.3 两条轨道

#### Track E：Explicit policy

- 结构化规则提供真值；
- deterministic PDP/PEP 是主方法；
- latent 只可作为审计信号，不能覆盖明确 DENY；
- 目标是验证工程边界和 fail-closed 行为。

#### Track I：Implicit delegation

- 用户以自然语言委托；
- 允许 `AMBIGUOUS`；
- 每条样本保存 authorization witness；
- 第二位盲标者复核 20%–30%；
- 这是主要研究轨。

## 4. 威胁模型

### 攻击者能够

- 控制邮件、网页、文档、RAG chunk 或 tool output；
-使用显式或隐式指令、事实陈述、字段污染和 code-switch；
- 观察 gate 的 allow/block 结果；
- 在 adaptive 子集中按固定 query budget 优化。

### 攻击者不能

- 修改 trusted user request；
- 修改本地 policy、gate 代码或 executor；
- 伪造已在 trusted host 验证的 cryptographic identity；
- 读取本地模型权重或 activation，除非实验明确设为白盒；
- 获取真实凭证或访问真实生产系统。

### v1 明确排除

- host、canonicalizer、PEP 或 credential vault 已被攻陷；
- 拥有任意 OS/网络权限、可绕开 PEP 产生隐藏副作用的恶意本地 MCP 实现；
- 模型权重或运行时被篡改。

若未来研究恶意 MCP server，必须另外加入 OS sandbox、凭据代理和全路径 complete mediation，不能只靠 tool-call gate。

### 信任边界

- LLM 是不可信 proposal generator；
- provenance metadata 只有在 trusted host 产生时才可信；正文中自称 `TRUSTED` 不产生权限；
- PEP 持有真实凭据，并是副作用工具唯一 dispatch 路径；
- executor 只接受 PEP 已 commit 的 canonical manifest；
- 确认凭据绑定 principal、session、canonical digest、nonce、expiry 和 policy version，并且只能消费一次；
- 所有实验使用 sandbox、虚构身份和 canary secret。

## 5. 数据设计

### 5.1 独立单位

独立单位是 `base_scenario_id`，不是单条 trajectory。所有派生项必须共享同一 group：

- A/U/AE/UC 各臂；
- paraphrase；
- 翻译；
- 模板变体；
- 同一原始 AgentDojo task；
- 同一 attacker goal；
- 同一生成器 lineage。

### 5.2 主四臂设计

对同一个 canonical candidate action：

| 臂 | 描述 | 授权 |
| --- | --- | --- |
| `A` | 可信用户直接授权精确动作 | ALLOW |
| `U` | 不可信内容诱导同一精确动作 | DENY |
| `AE` | 用户明确授权外部内容决定相关参数/动作 | ALLOW |
| `UC` | 无典型 override/祈使句的未授权上下文操纵 | DENY |

`A/U` 是基本 pair；`AE/UC` 用来打破“用户消息=安全、外部消息=危险”和“出现注入措辞=危险”的捷径。

### 5.3 来源权限 2×2 控制

运行时真实来源权限与正文可见声称必须正交：

| Operational source authority | Visible source claim | 用途 |
| --- | --- | --- |
| trusted | claims trusted | 普通可信来源 |
| trusted | claims untrusted/无声明 | 测试是否只相信文字外观 |
| untrusted | claims trusted/伪造签名外观 | 关键攻击控制 |
| untrusted | claims untrusted/无声明 | 普通不可信来源 |

只有 trusted host 绑定的 origin metadata 才能进入 deterministic policy。LLM 总结或推理得到的 semantic/causal influence 只可用于审计或风险路由。

### 5.4 附加 hard controls

- injection-like 文本存在但没有副作用 action；
- 高风险 action 存在但处于明确授权范围；
- 保持授权不变，仅改变来源标记措辞；
- 保持授权不变，仅改变位置和长度；
- trusted/untrusted 标记随机置换；
- action schema 和 argument 顺序变体，经 canonicalize 后相同。

### 5.5 首版场景

只选 AgentDojo Workspace/Email，优先两个副作用工具：

- `send_email`；
- `create_calendar_event` 或等价的第二个可稳定运行工具。

若 AgentDojo 当前版本兼容性差，先用 fake tool environment 完成数据与 gate，再实现 adapter。不得为赶进度自建复杂 agent framework。

### 5.6 规模

| 阶段 | 独立 group | 主要用途 |
| --- | ---: | --- |
| Golden | 6 | 手算、schema、单元测试 |
| Smoke | 20 | 可行性与模型 utility |
| Pilot | 60–100 | matched audit 与 grouped CV |
| Natural rollout | 30–50 个预注册场景 | 端到端可行性 |
| Publication extension | 100–200 | 三个 action family、第二模型或 cross-renderer |
| 低 FPR 扩展 | 视功效分析决定 | 只为部署 operating point 单独扩样 |

首版不报告稳定的 `TPR@1% FPR`。如要声称零误报下单侧 95% 上界低于 1%，至少扩展到约 299 个独立 benign action；如要稳定估计 1% operating point，目标约 3,000 个独立 benign action。

### 5.7 数据验证器

每个 group 必须通过：

```text
[ ] canonical tool name 一致
[ ] canonical exact arguments 一致
[ ] environment initial state 一致
[ ] typed canonical semantics 与 canonical digest 一致
[ ] authorization witness 存在
[ ] provenance chain 可解析
[ ] base scenario lineage 完整
[ ] split group 无泄漏
[ ] 非授权干扰差异已登记
[ ] AMBIGUOUS 样本未强行二值化
```

canonicalization 不等于比较 JSON 字节串。必须处理默认值、Unicode、URL、路径、大小写、数值、身份别名、收件人规范化和嵌套对象；无法安全规范化的字段应 fail-closed 或转确认。

## 6. 执行时间点与主 gate

```text
T0  外部内容读取完成
 |
T1  tool name 已生成
 |
T2  完整 tool call 已缓冲、解析、canonicalize
 |   <- 主授权检查点；executor 尚未 commit
T3  工具已执行
```

### 6.1 Teacher-forced audit

- 固定 candidate action；
- 在 T2 的 closing token 或预先指定边界 token 提取少量层状态；
- 研究预测信号和干扰因素；
- 不声称模型自然会生成该 action；
- 不替代端到端防御实验。

### 6.2 Natural rollout

- 截获模型实际生成的每个 proposal；
- 在 T2 完成 gate 决策后才允许 commit；
- 不只筛选 baseline attack success；
- 同时报告全部任务、clean-eligible subset 和 baseline-success subset。

## 7. Baseline 与实验顺序

### B0：Deterministic oracle/policy

- Track E 的上界；
- canonical action + structured policy；
- 不是 learned detector；
- 用于证明显式授权下 latent 是否根本无必要。

### B1：Action-only

- tool name；
- exact arguments；
- schema；
- action risk tier。

在 A/U exact-action pair 上应接近随机；若不是，说明数据或 canonicalization 有问题。

### B2：Provenance/nuisance-only

- message role；
- source type；
- position；
- length；
- trust marker；
- 模板和生成器 ID。

它是判断数据是否被捷径做穿的关键 baseline。

### B3：Text/goal-action

- TF-IDF + logistic regression；
- embedding/NLI goal-action match；
- 一个冻结的 prompt-injection detector 或 LLM judge。

### B4：Same-model score

- forced-choice/logit margin；
- candidate tool/action likelihood；
- 不访问 hidden state 的同模型对照。

### B5：AttriGuard-lite counterfactual replay

- 去除或衰减外部控制通道；
- teacher-forced replay 同一 candidate action；
- 比较 action survival/score；
- 不声称完整复现 AttriGuard。

### B6：Selected-layer probe（条件性）

仅在数据与 B0–B5 通过质量门后加入：

- 一个开放模型；
- 25%、50%、75%、final 四个预先指定层；
- 只保存边界 token vector；
- 立即 CPU offload；
- linear probe 优先，MLP 只作探索；
- 不跨模型混合 raw activation。

## 8. 预注册评测

### 8.1 Primary endpoint

首选：

```text
Within-pair ranking accuracy
P(score_DENY > score_ALLOW)
```

并报告 paired log loss。它比把所有样本混在一起算 AUROC 更符合 matched design。

### 8.2 Primary split

`leave-template-family-out` 或 `leave-base-scenario-family-out` 二选一，在数据冻结前预注册。另一项只作 secondary。

### 8.3 Secondary metrics

- AUROC；
- AUPRC，并明确实验 prevalence；
- balanced accuracy；
- Brier score / ECE；
- risk-coverage；
- 每 1,000 actions 的误报；
- natural rollout 的 attempted、blocked、committed、harm。

### 8.4 统计

- 按 `base_scenario_id` 做 paired/cluster bootstrap；
- 95% CI；
- threshold 只在 calibration fold 冻结；
- pilot 使用 nested grouped CV；
- 3 seeds 只适用于训练/采样随机性，不把派生样本当独立；
- 多层和多指标结果标为 exploratory，必要时 Holm 校正；
- API 模型用固定 snapshot 和完整 manifest。

### 8.5 Latent continuation gate

hidden-state 主线只有同时满足以下条件才继续：

1. strongest non-latent baseline 已实现；
2. source/nuisance hard subset 未被简单 baseline 饱和；
3. latent 增量点估计至少 3–5 个百分点；
4. 增量 95% CI 下界大于 0；
5. within-pair ranking CI 下界大于 0.5；
6. 至少两个 held-out 维度或两个模型方向一致。

不满足则发布负结果，转向 benchmark/control audit。

## 9. T2 Gate 设计

```text
LLM proposal
  -> buffer complete tool call
  -> parse + canonicalize
  -> deterministic policy check
  -> optional semantic/counterfactual/latent risk
  -> ALLOW | BLOCK | WOULD_CONFIRM
  -> commit or stop
  -> state diff + audit event
```

### 9.1 决策优先级

1. 解析失败：按工具风险选择 fail-closed；
2. 明确 policy DENY：BLOCK；
3. 明确 policy ALLOW 且 provenance 满足：ALLOW；
4. 隐式授权或歧义：输出 risk，MVP 记录 `WOULD_CONFIRM`；
5. learned detector 不得覆盖明确 DENY；
6. high-risk sink 默认比低风险 read-only tool 更严格。

### 9.2 Reference-monitor 最低条件

- complete mediation：所有副作用调用必须经过 PEP；
- tamper resistance：LLM 与不可信工具不能修改 policy、provenance 或 gate；
- fail-closed：高风险解析、canonicalization、policy 或 nonce 失败不 dispatch；
- TOCTOU 防护：被批准的 canonical digest 与实际 dispatch 完全相同；
- replay 防护：nonce/confirmation token 一次性消费；
- credential separation：真实凭据不进入 LLM context。

### 9.3 首版不模拟真实确认

没有用户行为模型时，不把 confirm 当已解决的 utility。首版记录：

- `would_confirm_rate`；
- benign/attack risk-coverage curve；
- 若全部 confirm，理论阻断与交互负担。

## 10. 自然 rollout 指标

必须同时报告：

- clean task success；
- attempted unauthorized proposals；
- committed unauthorized actions；
- environment-state harm；
- static/adaptive ASR；
- absolute percentage-point 与 relative ASR reduction；
- block rate；
- `would_confirm_rate`；
- benign utility；
- p50/p95 gate latency；
- token 与美元成本。

不得只在“无防御时攻击成功”的子集上报告 headline。

## 11. 硬件与运行策略

### RTX 4060 8GB

适合：

- 1.5B fp16；
- 3B/7B 4-bit、batch 1、短上下文；
- selected-layer forward hooks；
- linear probe；
- 小规模 white-box feasibility。

不适合：

- 8B 全梯度 adaptive attack；
- 存储完整层、完整 token activation；
- `output_attentions=True` 的大矩阵实验；
- 多模型并行服务。

优先 WSL2 CUDA；每个模型先做 tokens/s、VRAM、单 episode token 和 wall-clock smoke benchmark。

### Mac mini M4 24GB

九月后用于：

- 7B/8B 与可能的 14B 4-bit rollout；
- 数据生成和非 latent replication；
- MLX/llama.cpp 推理。

在 extractor parity 被验证前，不把 MLX activation 与 PyTorch/CUDA activation 放进同一统计池。macOS 与 CUDA 使用独立 environment manifest。

### OpenAI API

用于：

- frontier-model natural rollout 子集；
- non-latent semantic baseline；
-数据候选与第二轮审计辅助；
- 小预算黑盒 adaptive generation。

不用作 authorization ground truth，不使用浮动别名替代可锁定 snapshot。

## 12. 预算

总可用预算仍为 1,000 美元，但 v1 初始批准额度只有 300 美元。

| 阶段 | 硬上限 | 用途 |
| --- | ---: | --- |
| Smoke | $25 | API 与 agent loop 验证 |
| 数据/标注辅助 | $50 | 候选生成与抽样复核 |
| 主 non-latent 实验 | $75 | 代表模型与 replay |
| Natural rollout | $50 | 端到端子集 |
| Adaptive/中文可选 | $50 | 通过质量门后启用 |
| 重跑储备 | $50 | snapshot、失败和最终复现 |

每个实验配置必须声明：

- 最大 episode 数；
- 最大 prompt/completion tokens；
- 最大重试；
- 单元格预算；
- 预计 GPU/墙钟；
- 超限自动停止。

剩余 700 美元冻结，只有 v1 质量门通过后才重新分配。

## 13. 建议仓库结构

```text
goal-auth-bench/
  README.md
  pyproject.toml
  LICENSE
  CITATION.cff
  CHANGELOG.md
  src/goalauthbench/
    schema/
    canonicalize/
    policy/
    provenance/
    datasets/
    adapters/agentdojo/
    baselines/
    probes/
    gate/
    metrics/
    tracing/
  data/
    golden/
    smoke/
    pilot/
  configs/
    models/
    experiments/
    policy/
  tests/
    unit/
    integration/
    golden/
  reports/
    figures/
    tables/
    error_gallery/
  docs/
    threat-model.md
    label-guide.md
    data-card.md
    model-card.md
    adr/
  scripts/
  manifests/
```

## 14. 12 周执行路线

### Week 0：新颖性与规格冻结

交付：

- prior-art matrix；
- 一句可证伪主张；
- threat model；
- authorization label guide；
- primary endpoint 与 primary split；
- ADR-001：为什么选 T2；
- ADR-002：为什么分离 explicit/implicit。

质量门：

- 不使用 `first`；
- 能清楚解释与 Formalization、Provenance Sensitivity、AttriGuard、CXI、Brittle/ICON 的差异；
- 公开主张只写成 joint-call-identical、operational-provenance 和 detector/latent shortcut audit 的窄扩展。

### Week 1–2：Golden proof

交付：

- 6 个手工 golden groups；
- `CanonicalAction`；
- exact argument comparator；
- `AuthorizationWitness`；
- pair validator；
- fake tool executor；
- T2 buffer/commit；
- 手算 fixture 与单元测试。

质量门：

- golden validator 100%；
- 明确 DENY 永不 commit；
- 指标与手算一致；
- 无 API 的一键 smoke。

### Week 3–4：AgentDojo 与可行性

交付：

- Workspace/Email adapter；
- 20 个 smoke groups；
- 1.5B 与一个 3B/7B 4-bit 模型 smoke；
- state、utility、authorization 三种 oracle；
- trace manifest。

Go/no-go：

- syntactically valid tool call ≥70%；
- 选定简单 clean tasks 成功率约 ≥40%–50%；
- 若本地 utility 太低，主实验改为 teacher-forced，natural rollout 使用 API 子集。

### Week 5–6：Pilot dataset

交付：

- 60–100 个独立 matched groups；
- A/U/AE/UC；
- 20%–30% 第二位盲标复核；
- lineage-aware grouped split；
- data card；
- leakage report。

质量门：

- canonical matcher ≥95%；
- 0 个 family leakage；
- 每条有 authorization witness；
- 隐式授权 κ/α 目标 ≥0.7；
- ambiguous <15%，否则缩小语义范围；
- nuisance-only baseline 不得在 hard subset 轻易达到 AUC >0.9；若达到，先返工数据。

### Week 7–8：Non-latent shortcut audit

交付：

- B0–B5；
- random 与 primary grouped OOD；
- paired ranking、CI、校准；
- 6–10 个失败案例；
- cost/latency report。

质量门：

- strongest non-latent baseline 已明确；
- 结论区分 distribution shift 与 shortcut；
- 负结果也冻结并发布，不为追正结果改标签。

### Week 9：Latent decision

若通过 continuation gate：

- selected-layer probe；
- 单模型四层；
- within-pair 与 OOD；
- compute-matched 比较。

若未通过：

- 停止 latent；
-加强数据/validator/error analysis；
- 将“latent 无增量”写成结果。

### Week 10：T2 natural rollout

交付：

- 30–50 个预注册场景；
- policy-first gate；
- attempted/blocked/committed/harm；
- clean utility；
- p95 latency；
- `would_confirm_rate`。

### Week 11–12：公开发布

交付：

- `v1.0.0` release；
- Hugging Face dataset；
- Zenodo DOI；
- technical report；
- 2–3 分钟 demo；
- static error gallery；
- clean-room reproduction；
- AgentDojo adapter 或文档改进的上游 PR。

中文 15–20 对 challenge slice 或小预算 adaptive attack，只在主 release 已经完整时加入，不允许阻塞 v1。

## 15. Release 节奏

| 版本 | 内容 |
| --- | --- |
| `v0.1.0` | golden schema、validator、fake tool、T2 smoke |
| `v0.2.0` | AgentDojo adapter 与 20-group smoke |
| `v0.3.0` | 60–100 group pilot dataset |
| `v0.4.0` | non-latent baseline audit |
| `v0.5.0` | 可选 latent audit |
| `v0.6.0` | T2 natural rollout gate |
| `v1.0.0` | 数据、报告、DOI、复现与 demo |

每个 release 必须有：

- changelog；
- 固定 manifest；
- 可复现命令；
- 已知限制；
- 结果与成本；
- 数据/模型 hash；
- 至少一个失败案例。

## 16. GitHub 首屏与传播

README 首屏只讲一件事：

```text
Same candidate tool call.
Different authorization context.
Which monitors still work?
```

首屏包含：

1. 一张 A/U/AE/UC 图；
2. 60 秒 quickstart；
3. random vs grouped OOD 主表；
4. strongest non-latent vs latent 增量或零增量；
5. 三个失败案例；
6. data/report/release 链接。

优先级：

```text
可复现性 > 清晰问题 > 上游 PR > 技术报告 > demo > stars
```

stars 是外部传播结果，不能作为发布质量门。可以主动发布到相关社区、维护英文 README、回复 issue、做上游 adapter，但不购买、交换或诱导 stars。

## 17. Codex 协作边界

Codex 可以：

- 搭脚手架、写测试、重构和文档；
- 实现 adapter、baseline、实验调度和统计；
- 协助查论文、维护 novelty matrix；
- 生成候选数据供人工审计；
- 做代码审查和复现检查。

项目负责人必须亲自掌握：

- threat model；
- authorization oracle；
- label guide；
- canonicalization；
- pair validator；
- split 与 leakage；
- primary metric；
- 一条完整失败链；
- gate 的每种决策。

规则：

1. Codex 不得自行改标签或授权策略；
2. 每个核心模块尽量单一职责；
3. 每个核心设计有 ADR；
4. 每项正式实验有 manifest；
5. 正式实验期间不做未经审查的大规模重构；
6. 新环境做 clean-room reproduction；
7. 面试前能从空白纸重画数据流和 T2 boundary。

## 18. 成功、停止与转向

### 项目发布成功

无论正负结果，只要满足：

- 数据与 validator 完整；
- baseline 公平；
- grouped OOD 与 CI 正确；
- gate 真正在 commit 前；
- artifact 可复现；
- 限制和失败案例公开；
- 项目负责人可独立解释。

### Latent 失败

若 hidden-state 无稳定增量：

> 发布“在严格授权控制下，显式/来源 baseline 足以解释性能”的负结果。

这不是项目失败。

### 数据被捷径做穿

若 nuisance-only 很高：

- 不训练更复杂模型掩盖问题；
- 返工控制组；
- 发布 shortcut audit；
- 缩小隐式授权范围。

### 本地模型 utility 低

- teacher-forced 做主机制审计；
- API/frontier 模型做小规模 natural rollout；
- 不声称本地模型端到端部署效果。

### Deterministic gate 饱和

- 明确结论：显式 policy 下 latent 不必要；
- 把研究焦点保留在隐式授权与 provenance ambiguity；
- 不为展示 AI 而强行加入 AI。

### Adaptive 可绕过

- 固定 query budget 和 threshold；
- 发布 ASR-vs-query 曲线；
- 将项目定位为审计与 defense-in-depth，而非彻底解决 injection。

## 19. 可写入简历的成果标准

至少完成：

- 60–100 个独立 matched groups；
- 4 个以上有意义的 baseline；
- 一个预注册 grouped OOD；
- 一个 T2 pre-commit gate；
- 数据卡、技术报告、CI、release 和 DOI；
- 端到端安全、utility、延迟与成本；
- 可独立讲解的失败案例。

实验完成后的中文模板：

> 构建并开源 LLM Agent 授权反事实评测集，在保持候选工具调用及精确参数一致的条件下，系统控制来源、模板与文本干扰因素；统一评估 deterministic policy、语义匹配、因果重放和 hidden-state probe，并通过按场景聚类的 grouped OOD 与 bootstrap CI 审计检测捷径。

> 实现完整工具调用生成后、执行提交前的 T2 authorization gate，使 committed unauthorized actions 从 X/Y 降至 A/B，clean task success 变化 Z 个百分点，p95 增量延迟 N ms；发布数据、Docker/uv 环境、实验 manifest、失败画廊和 DOI。

若 latent 无增量，改写为：

> 发现 hidden-state probe 的表面高分在 source/nuisance-matched OOD 下消失，证明显式授权场景应优先使用 deterministic provenance enforcement，并发布可复现的负结果与诊断集。

## 20. 现在开始的 14 天任务

### Day 1–2

- 阅读五篇核心工作：Formalization、Provenance Sensitivity、AttriGuard、CXI、AUC 0.998；
- 写一页 threat model；
- 写一页 label guide；
- 确定两个副作用工具。

### Day 3–4

- 定义 `CanonicalAction`；
- 定义 `AuthorizationWitness`；
- 定义 `ProvenanceRef`；
- 完成 6 个 golden groups。

### Day 5–6

- exact comparator；
- pair validator；
- lineage validator；
- 手算 metrics fixture；
- 单元测试。

### Day 7

- fake model/fake tool；
- T2 buffer 与 commit；
- 明确 DENY 的 fail-closed 测试；
- 第一个无 API release candidate。

### Day 8–10

- 固定 AgentDojo 版本；
- 跑通 2 个 clean + 2 个 attack；
- 保存 trace/state diff；
- 实现 adapter。

### Day 11–12

- 加载一个 1.5B 模型；
- 测量 tool-call validity、VRAM、tokens/s；
- 实现 B1/B2；
- 决定是否加入 3B/7B 4-bit。

### Day 13–14

- 扩到 20 个 smoke groups；
- 运行第一次 grouped CV；
- 写 smoke report；
- 做第一次 go/no-go 复盘；
- 发布 `v0.1.0` 或列出未通过的质量门。

## 21. 当前最终决策

- 继续做 GoalAuthBench，但保留为临时代号；
- 主贡献是严格授权反事实控制与多范式 shortcut audit；
- 显式 policy 与隐式 delegation 分轨；
- 主部署边界是 T2 pre-commit；
- deterministic policy 优先；
- counterfactual replay 是强 baseline；
- hidden-state 是二级、可证伪扩展；
- v1 只做 Workspace/Email、两个副作用工具；
- 中文、adaptive、多 domain 和大模型延后；
- RTX 4060 负责小模型与 selected-layer probe；
- M4 负责后续 rollout，不混池 activation；
- v1 API 批准额度 300 美元；
- 正负结果都发布；
- 简历成功以 artifact、实验可信度和可解释性为准，不以 stars 数量为质量门。
