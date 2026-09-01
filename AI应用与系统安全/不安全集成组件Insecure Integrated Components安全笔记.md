---
id: coae-appsec-375946db
title: '不安全集成组件（Insecure Integrated Components）安全笔记'
aliases: []
domain:
  - 'AI应用与系统安全'
note_type:
  - concept
attack_phase:
  - inference
  - agent
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-12
---
# 不安全集成组件（Insecure Integrated Components）安全笔记

> 适用范围：AI/ML 应用架构审计、LLM 插件与工具调用安全、Web/API 集成测试和授权安全评估。所有测试必须在自有系统、隔离靶场或明确授权范围内进行。

> 当前进度：已完成集成组件攻击面、Web 应用漏洞、插件级 IDOR、LLM 代传身份导致的授权绕过、输入输出信任边界和分层防御分析。

> 相关笔记：[[模型逆向Model Reverse Engineering原理与防御笔记]]、[[ML服务拒绝Denial of ML Service与Sponge Examples笔记]]、[[LLM输出Function Calling测试与笔记]]。

---

## 0. 一页速记

### 0.1 定义

真实 AI 应用不是只有一个模型，而是由大量组件共同构成：

```text
用户界面
    ↓
Web / Mobile 应用
    ↓
API Gateway / 身份认证
    ↓
AI 编排层 / System Prompt
    ↓
LLM / ML 模型
    ↓
插件、工具、数据库、搜索、文件和第三方 API
```

任意集成组件存在漏洞，都可能危及整个 AI 应用。模型本身即使没有漏洞，也不能抵消 Web、API、插件或数据库层的安全缺陷。

### 0.2 核心风险

- Web 应用存在 SQL 注入、IDOR、XSS 或会话漏洞；
- 插件没有执行对象级授权；
- 插件信任 LLM 提供的 `user_id`、`role` 或 `tenant_id`；
- LLM 输出未经验证就进入 SQL、Shell、模板或外部 API；
- 第三方插件拥有过大的数据、网络或操作权限；
- 同一业务在 Web 路径和 AI 工具路径上采用不同安全策略。

### 0.3 最重要的原则

```text
用户说自己是谁       不可信
Prompt 中出现的身份   不可信
LLM 生成的 user_id    不可信
工具参数里的角色声明  不可信

服务端认证会话中的身份  才是授权依据
```

### 0.4 一句话记忆

> AI 应用的安全强度取决于最弱的集成组件；LLM 可以帮助表达意图，但绝不能替代服务端身份认证和授权。

---

## 1. 为什么这是系统问题而不是模型问题

一个 LLM 购物助手可能同时连接：

- 用户账户；
- 订单系统；
- 历史对话数据库；
- 产品库存；
- 支付系统；
- 邮件或消息服务；
- 第三方搜索和推荐 API。

模型只负责把自然语言转换为工具调用意图：

```text
“查询我的订单”
    ↓ LLM 解析
get_order_status(order_id="B0548AF6")
```

真正访问订单的是插件或后端服务。因此安全结论必须覆盖整个数据流：

```text
谁发起请求？
    ↓
LLM 选择了什么工具？
    ↓
工具参数来自哪里？
    ↓
后端使用哪个身份查询？
    ↓
返回了哪些数据？
    ↓
模型是否有权看到并输出这些数据？
```

只测试“模型会不会拒绝”无法证明插件安全。

---

## 2. Pixel Forge 案例架构

材料中的 Pixel Forge 是一个带聊天助手的游戏主机商店。用户可以：

- 注册和登录；
- 浏览商品；
- 下单；
- 查询订单状态；
- 与聊天机器人交互；
- 查看历史 LLM 对话；
- 让插件总结历史对话。

可抽象为：

```text
                         ┌→ Orders Database
用户 → Web Application ──┼→ Conversation Database
                         └→ Product Database

用户 → Chatbot → LLM → Plugins ─→ 相同的后端数据
```

这里存在两条访问路径：

1. Web 页面直接访问数据；
2. 聊天机器人通过插件访问数据。

安全控制必须在两条路径上一致生效。

---

## 3. Web 应用中的 IDOR

### 3.1 什么是 IDOR

Insecure Direct Object Reference 指应用直接接受对象标识符，却没有确认当前用户是否有权访问该对象。

例如：

```text
/query/5
```

其中 `5` 是对话对象 ID。安全判断不能只是：

```text
对象 5 存在吗？
```

还必须判断：

```text
当前已认证用户是否拥有或获准访问对象 5？
```

### 3.2 正确的对象级授权

不安全逻辑：

```sql
SELECT * FROM conversations
WHERE id = :conversation_id;
```

更安全的查询语义：

```sql
SELECT * FROM conversations
WHERE id = :conversation_id
  AND owner_id = :authenticated_user_id;
```

其中 `authenticated_user_id` 必须来自服务端验证过的会话或 token，不能来自 URL、请求正文、Prompt 或 LLM。

### 3.3 案例结论

材料首先测试 Web 路径中的递增对话 ID。应用只返回当前用户拥有的对话，说明这个路径可能实施了对象级授权。

但这只能证明：

```text
Web 路径 /query/{id} 在当前测试下未发现 IDOR
```

不能证明：

- 数据库本身安全；
- 插件路径也安全；
- 其他 HTTP 方法安全；
- 管理端和移动端采用相同控制；
- 不存在 SQL 注入等其他漏洞。

---

## 4. Web 路径中的 SQL 注入

### 4.1 根因

若应用把 URL 中的对话 ID直接拼接到 SQL：

```text
用户输入
    ↓ 字符串拼接
SQL 查询
    ↓
数据库执行
```

攻击者可能改变原查询结构，读取不应访问的数据。

### 4.2 为什么对象级授权与 SQL 注入是两回事

案例中 Web 路径可能正确阻止 IDOR，但仍存在 SQL 注入。

```text
IDOR 检查通过
≠ SQL 构造安全
```

对象级授权解决“当前用户能否访问这个对象”；参数化查询解决“用户输入能否改变 SQL 语义”。两者缺一不可。

### 4.3 防御

- 使用参数化查询或安全 ORM；
- 不通过字符串拼接构造 SQL；
- 数据库账户遵循最小权限；
- 生产环境不回显数据库错误和版本；
- 对所有数据访问路径执行统一授权；
- 对异常查询模式监控和告警。

仅进行输入字符过滤不是可靠的主要防线。

---

## 5. 插件路径中的对象级授权缺失

### 5.1 漏洞链

聊天助手提供“总结历史对话”工具：

```text
用户：“总结对话 5”
    ↓
LLM 选择 ConversationSummary 插件
    ↓
插件读取 conversation_id=5
    ↓
返回对话内容
    ↓
LLM 生成摘要
```

若插件只按对话 ID 查询，没有根据当前用户过滤：

```text
攻击者指定其他人的 conversation_id
    ↓
插件读取该对象
    ↓
LLM 总结并泄露敏感内容
```

这本质上仍是 IDOR，只是漏洞入口从 Web URL 变成自然语言和插件参数。

### 5.2 为什么 Web 安全但插件仍可能失守

两个路径可能使用不同实现：

```text
Web Controller
    → 检查 session.user_id
    → 查询当前用户对象

LLM Plugin
    → 只接收 conversation_id
    → 直接查询对象
```

插件绕过了 Web Controller 的授权逻辑。因此授权不能只写在页面或路由层，而应尽量集中到共享服务或数据访问策略中。

---

## 6. 最危险的设计：让 LLM 提供用户身份

### 6.1 看似有授权，实际可绕过

假设插件接受：

```json
{
  "conversation_id": 1,
  "user_id": 1
}
```

然后检查 `conversation.owner_id == user_id`。表面上存在授权，但如果 `user_id` 由 LLM 根据 Prompt 填写，攻击者可能诱导模型改成其他用户 ID。

```text
用户 Prompt
    ↓
影响 LLM
    ↓
LLM 生成攻击者指定的 user_id
    ↓
插件把它当成可信身份
    ↓
授权检查被绕过
```

这是典型的 confused deputy（混淆代理）问题：插件拥有访问能力，却让不可信的 LLM 决定以谁的身份行使该能力。

### 6.2 正确设计

工具公开给模型的参数：

```json
{
  "conversation_id": 1
}
```

服务端内部补充可信上下文：

```text
authenticated_user_id = server_session.user_id
tenant_id = verified_token.tenant_id
roles = authorization_service.get_roles(user_id)
```

最终调用：

```text
get_conversation(
    conversation_id = LLM 提供,
    authenticated_user_id = 服务端提供
)
```

LLM 永远没有机会设置或覆盖：

- `user_id`；
- `tenant_id`；
- `role`；
- `is_admin`；
- 权限 scope；
- 数据所有者；
- 审批状态。

### 6.3 工具参数分层

| 参数类型 | 示例 | 来源 |
|---|---|---|
| 业务意图参数 | `conversation_id`、`order_id` | 可由用户/LLM提供，但需验证 |
| 身份参数 | `user_id`、`tenant_id` | 服务端认证上下文 |
| 授权参数 | roles、scopes、policy result | 授权服务 |
| 系统参数 | endpoint、credential、DB connection | 服务端配置 |
| 审批参数 | approval token、transaction limit | 独立可信工作流 |

不能把后四类暴露为可由模型自由填写的普通参数。

---

## 7. Prompt Injection 为什么能变成授权漏洞

Prompt injection 本身是模型指令边界问题。只有当系统把模型输出赋予真实权限时，它才会进一步成为数据泄露或越权操作。

```text
Prompt Injection
    ↓
模型行为被影响
    ↓
模型生成越权工具参数
    ↓
插件错误信任模型参数
    ↓
敏感数据泄露或操作越权
```

因此正确防线不能依赖：

```text
System Prompt：“不要访问别人的数据”
```

即使模型始终尽力遵守，也不应拥有绕过后端授权的能力。可靠原则是：

> 模型可以请求操作，后端必须独立决定该操作是否允许。

---

## 8. 输入与输出都不可信

### 8.1 输入方向

插件可能接收：

- 用户原始文本；
- LLM 提取出的参数；
- 外部网页内容；
- 数据库记录；
- 检索结果；
- 文件内容和元数据。

这些数据都可能包含恶意或异常内容。

### 8.2 输出方向

LLM 输出可能被传递给：

- SQL 查询；
- Shell 命令；
- Python/JavaScript 执行器；
- HTML 模板；
- 邮件和消息；
- 文件路径；
- 第三方 API；
- Function Calling 参数。

如果直接拼接或执行，可能导致：

- SQL injection；
- command injection；
- code injection；
- path traversal；
- SSRF；
- XSS；
- 非预期的批量操作。

### 8.3 安全数据流

```text
用户/外部内容
    ↓ 不可信
LLM
    ↓ 仍不可信
结构化解析与 schema 验证
    ↓
服务端授权与业务约束
    ↓
参数化 API / SQL / 固定命令映射
    ↓
最小权限执行
    ↓
输出过滤与审计
```

LLM 处理过的数据不会自动变得可信。

---

## 9. 第三方插件风险

第三方插件可能具有：

- 数据库访问权；
- 外网访问权；
- 内部 API 凭据；
- 文件读写能力；
- 用户身份信息；
- 发送邮件或消息的能力；
- 订单、支付或管理操作权限。

### 9.1 接入前审查

```text
[ ] 插件来自哪里，维护者是否可信
[ ] 是否能查看或审计源代码
[ ] 依赖项和版本是否可追踪
[ ] 插件实际需要哪些权限
[ ] 会把什么数据发送到哪里
[ ] 是否支持租户隔离和对象级授权
[ ] 凭据如何存储、轮换和撤销
[ ] 插件失败时是否安全停止
[ ] 是否保存充分审计日志
[ ] 是否真的有业务必要
```

### 9.2 运行时控制

- 独立服务账户；
- 独立网络策略；
- 只读优先；
- 精确 API scope；
- 短期凭据；
- 文件系统和进程沙箱；
- 请求和资源配额；
- 高影响操作人工确认；
- 可快速禁用和撤销。

“插件来源可信”不能替代运行时最小权限。

---

## 10. 统一授权架构

### 10.1 错误架构

```text
Web 路径 → 自己实现授权
Mobile 路径 → 自己实现授权
LLM 插件 → 自己实现授权
内部 API → 假设调用者可信
```

每条路径独立实现，容易出现策略漂移和遗漏。

### 10.2 推荐架构

```text
Web / Mobile / Chatbot / Internal Client
                  ↓
          统一业务服务层
                  ↓
       认证上下文 + 授权策略引擎
                  ↓
       受租户和所有权约束的数据访问
```

核心授权规则靠近资源执行：

```text
谁（subject）
要对什么对象（object）
执行什么动作（action）
在什么上下文（context）
```

即使上游 Web、模型或插件被影响，资源层仍会拒绝越权操作。

---

## 11. 测试方法

### 11.1 建立测试身份

至少准备：

```text
User A：拥有 Conversation A、Order A
User B：拥有 Conversation B、Order B
Admin：拥有明确管理权限
```

使用合成内容，避免真实敏感数据。

### 11.2 构造授权矩阵

| 主体 | 对象 | 动作 | 预期 |
|---|---|---|---|
| User A | Conversation A | read/summarize | Allow |
| User A | Conversation B | read/summarize | Deny |
| User B | Conversation A | read/summarize | Deny |
| Admin | Conversation A/B | 按政策读取 | Allow 或受审计 |

### 11.3 对所有路径复用矩阵

同一矩阵应测试：

- Web 页面；
- REST/GraphQL API；
- 移动端 API；
- LLM 插件；
- 后台任务；
- 导出和搜索；
- 管理接口。

正确结果不是“聊天机器人说不能”，而是：

```text
后端工具返回结构化 AuthorizationDenied
敏感对象内容从未发送给模型
审计日志记录被拒绝的主体、对象和动作
```

### 11.4 工具参数测试

确认用户或模型不能控制：

- 其他人的用户 ID；
- 租户 ID；
- 管理员标志；
- 后端 URL；
- 数据库查询；
- 任意 Shell 参数；
- 未经授权的批量范围；
- 隐藏或额外 JSON 字段。

使用严格 schema，并拒绝未知字段。

---

## 12. 日志与监控

一次工具调用至少应关联：

```text
request_id / trace_id
authenticated_user_id
tenant_id
session_id
model 与 prompt 版本
tool_name
validated_arguments
authorization_result
target_object_ids
execution_result
返回数据分类
最终向用户披露的内容
```

敏感原文、密钥和完整 Prompt 不应无控制地写入日志。日志本身也需要访问控制、保留期限和脱敏。

可疑信号包括：

- 用户连续枚举递增对象 ID；
- 同一会话尝试多个不属于自己的订单或对话；
- LLM 工具参数中的 `user_id` 与会话身份不一致；
- 模型反复尝试被后端拒绝的工具调用；
- 插件读取的数据范围突然扩大；
- 自然语言请求与实际工具动作不匹配。

---

## 13. 防御清单

### 13.1 身份与授权

```text
[ ] 身份只来自服务端认证上下文
[ ] 每次对象访问都执行对象级授权
[ ] 每次工具调用都执行动作级授权
[ ] 租户 ID 不可由用户或 LLM 覆盖
[ ] 管理操作需要独立策略和审计
[ ] 不以 System Prompt 作为授权控制
```

### 13.2 插件与工具

```text
[ ] 工具 schema 使用 allowlist
[ ] 拒绝未知字段和类型错误
[ ] 参数化 SQL 和固定操作映射
[ ] 插件使用独立最小权限身份
[ ] 外网、内网和文件访问受限制
[ ] 高影响操作需要确认或审批
[ ] 支持超时、取消、配额和熔断
```

### 13.3 数据

```text
[ ] 敏感数据在授权前不发送给模型
[ ] 返回结果按字段和记录最小化
[ ] 多租户数据在查询层强制隔离
[ ] LLM 输出在下游使用前重新验证
[ ] 日志、缓存和向量库实施同等授权
```

### 13.4 供应链

```text
[ ] 插件来源和维护者可追踪
[ ] 依赖版本锁定并持续扫描
[ ] 接入前代码与架构审查
[ ] 凭据可轮换、撤销和最小化
[ ] 插件可被快速隔离或下线
```

---

## 14. 常见错误认识

### 14.1 “Web 页面已经检查权限，所以数据是安全的”

错误。插件、导出、搜索和内部 API 可能采用不同路径。

### 14.2 “模型会拒绝访问别人的数据”

模型拒绝只是软控制，不能替代后端强制授权。

### 14.3 “插件有 user_id 参数，所以已经做了授权”

要看 `user_id` 的来源。如果由用户或 LLM提供，授权基础仍不可信。

### 14.4 “LLM 输出的是结构化 JSON，所以可以直接执行”

JSON 只说明格式可解析，不代表内容经过授权、符合业务规则或不存在注入风险。

### 14.5 “第三方插件来自知名厂商，所以可以给全部权限”

来源信誉只是风险信号之一。插件仍应采用最小权限、隔离、监控和可撤销设计。

### 14.6 “没有 IDOR 就没有数据泄露”

SQL 注入、日志泄露、缓存错误、Prompt injection 和过度返回同样可能泄露数据。

---

## 15. 记忆卡片

### Q1：Insecure Integrated Components 的核心是什么？

AI 应用中的 Web、API、数据库、插件或第三方服务存在漏洞，使模型相关数据和操作受到影响。

### Q2：Web 路径安全是否代表插件路径安全？

不代表。每条访问路径都必须执行相同的对象级和动作级授权。

### Q3：插件为什么不能接受 LLM 提供的 user_id？

LLM 输出可被 Prompt injection 影响，不能作为可信身份来源。

### Q4：conversation_id 可以由 LLM 提供吗？

可以作为请求的业务参数，但后端必须使用已认证用户身份检查其访问权。

### Q5：模型拒绝越权请求是否足够？

不够。即使模型发起越权工具调用，后端也必须独立拒绝。

### Q6：对象级授权应在哪里执行？

尽可能靠近实际资源访问的服务或数据层，并由所有入口统一复用。

### Q7：LLM 输出为什么仍是不可信输入？

它可能包含错误、被注入影响或违反业务规则，进入 SQL、Shell 或 API 前必须验证。

### Q8：IDOR 和 SQL 注入有什么区别？

IDOR 是缺少对象级授权；SQL 注入是输入改变查询语义。系统必须分别防御。

### Q9：插件最小权限包括什么？

只允许其访问完成任务所需的数据、API、网络位置和操作，并限制时间、数量和影响范围。

### Q10：最可靠的架构原则是什么？

模型负责提出操作意图；可信服务端负责身份、授权、参数验证和最终执行。

---

## 16. 最终总结

Insecure Integrated Components 提醒我们：AI 应用并不是一个孤立模型，而是一条跨越界面、身份系统、编排层、插件、数据库和外部 API 的执行链。

```text
AI 系统风险
≠ 只看模型是否安全

AI 系统风险
= 每个组件自身漏洞
+ 组件之间的信任假设
+ 多条访问路径的策略差异
+ 模型输出获得的真实权限
```

Pixel Forge 案例揭示了两个关键问题：

1. Web 路径可能实施了对象级授权，但仍可能有 SQL 注入；
2. Web 路径即使安全，LLM 插件也可能因缺少授权或信任模型提供的身份而泄露其他用户对话。

正确安全边界应是：

```text
LLM 产生意图和业务参数
    ↓
严格 schema 验证
    ↓
服务端注入可信身份
    ↓
统一授权服务检查主体、对象和动作
    ↓
最小权限插件执行
    ↓
最小化结果返回模型
    ↓
输出验证、审计与监控
```

## 17. 可复用考试代码块：顺序 IDOR 枚举

用途：登录后页面 URL 出现 `/query/5`、`/order/12`、`/conversation/7` 这类顺序对象 ID，怀疑对象级授权缺失。

```bash
TARGET="http://STMIP:STMPO"
SESSION="session=<SESSION_VALUE>"

for i in $(seq 1 50); do
  curl -s "$TARGET/query/$i" -b "$SESSION"
done | grep -E 'HTB\{|flag|Please hold'
```

Python 版本：

```python
import re
import requests

TARGET = "http://STMIP:STMPO"
COOKIES = {"session": "<SESSION_VALUE>"}

for object_id in range(1, 51):
    url = f"{TARGET}/query/{object_id}"
    r = requests.get(url, cookies=COOKIES, timeout=10)
    if re.search(r"HTB\{|flag|Please hold", r.text, re.I):
        print(f"[+] {url}")
        print(r.text)
```

核心技术点：

```text
[ ] 先正常创建对象，确认自己的对象 ID
[ ] 观察 ID 是否自增、可预测
[ ] 带自己的 session 横向访问其他 ID
[ ] 成功信号是返回他人对话、订单、文件或 flag
[ ] 根因是对象级授权缺失，而不是登录缺失
```

一句话总结：

> 永远不要让 LLM 决定“调用者是谁、拥有什么权限”；这些信息必须来自不可被 Prompt 控制的服务端认证与授权上下文。
