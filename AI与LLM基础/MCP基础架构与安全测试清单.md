---
id: coae-base-d7ca6584
title: 'MCP 基础架构与安全测试清单'
aliases: []
domain:
  - 'AI与LLM基础'
note_type:
  - concept
  - checklist
attack_phase:
  - foundation
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-12
---
# MCP 基础架构与安全测试清单

> 适用范围：Model Context Protocol（MCP）Host、Client、Server、server primitives、client features、JSON-RPC 生命周期、stdio 与 Streamable HTTP 的学习、联调和授权安全评估。本文以 MCP `2025-11-25` 规范为当前基线；协议更新时应重新核对官方规范，不能把某一版字段和行为永久写死。

## 0. 核心判断

```text
MCP 解决的问题
  = 用统一协议连接 AI 应用与外部工具、数据和提示模板

MCP 不自动解决的问题
  = 身份认证、业务授权、最小权限、内容可信度、用户确认和下游实现安全

统一接口的双重影响
  = 降低集成成本
  + 让一个 Host 可以连接更多 Server
  + 同时集中并扩大工具、数据和跨系统信任风险
```

一句话类比：

```text
MCP 类似“AI 集成的 USB”
但能插上不等于应该信任；设备身份、权限、数据范围和执行副作用仍需独立控制。
```

## 0.1 进入 MCP 环境后的 5 分钟路线

### 第 1 分钟：画出参与者

```text
[ ] 标记用户实际交互的 MCP Host
[ ] 列出 Host 创建的全部 MCP Client
[ ] 确认每个 Client 只维护与一个 Server 的直接连接
[ ] 标记每个 Server 是本地进程还是远程服务
[ ] 标记 Server 背后的文件、数据库、Git、API 和 SaaS 系统
```

### 第 2 分钟：识别传输与身份

```text
[ ] 本地 Server 是否使用 stdio
[ ] 远程 Server 是否使用 Streamable HTTP
[ ] 是否仍启用旧版 HTTP+SSE 兼容端点
[ ] 远程连接使用什么认证主体、Token 和授权范围
[ ] 本地进程继承了哪些环境变量、工作目录和操作系统权限
```

### 第 3 分钟：枚举能力

```text
[ ] Server：prompts、resources、tools、logging、completions、tasks
[ ] Client：roots、sampling、elicitation、tasks
[ ] 记录 capability negotiation 的请求与响应
[ ] 未协商能力不得在 operation 阶段使用
```

### 第 4 分钟：枚举可见对象

```text
[ ] `prompts/list`
[ ] `resources/list`
[ ] `resources/templates/list`
[ ] `tools/list`
[ ] 记录名称、描述、URI、Schema、注解和潜在副作用
```

### 第 5 分钟：验证最低影响调用

```text
[ ] 先读取固定合成 Resource
[ ] 再获取无副作用 Prompt
[ ] 最后调用只返回固定 marker 的只读 Tool
[ ] 记录用户目标、模型选择、Host 决策、Server 执行和最终结果
[ ] 未经明确授权不测试写文件、发送消息、购买、删除或外部发布
```

## 1. MCP 架构盘点清单

### 1.1 Host

Host 是用户接触的 AI 应用和协调者，一个 Host 可以管理多个 Client。

```text
[ ] Host 是否清晰展示已连接的 MCP Server？
[ ] Host 是否为每个 Server 创建独立 Client 与连接状态？
[ ] Host 是否隔离不同 Server 的凭据、上下文和工具结果？
[ ] Host 是否决定哪些能力暴露给模型？
[ ] Host 是否在敏感调用前执行用户确认与策略检查？
[ ] Host 是否能禁用、断开和撤销单个 Server？
[ ] Server 异常时是否只影响对应 Client，而非整个 Host？
[ ] 多个 Server 的同名 Tool 是否有明确命名空间和来源显示？
```

### 1.2 Client

Client 是 Host 内负责 MCP 协议连接的组件。一个 Client 对应一个 Server，但远程 Server 可以服务多个 Client。

```text
[ ] Client 是否保存协商后的协议版本和能力集合？
[ ] Client 是否拒绝 Server 使用未协商能力？
[ ] Client 是否验证 JSON-RPC ID、响应关联和消息方向？
[ ] Client 是否对每个请求设置超时、取消和最大总时长？
[ ] Client 是否限制 Tool 循环次数、总成本和上下文增长？
[ ] Client 是否把 Server 返回内容标记为不可信数据？
[ ] Client 是否将用户身份正确映射到远程 Server 授权主体？
[ ] Client 是否在断开后清理会话、临时数据和凭据？
```

### 1.3 Server

Server 是提供上下文或动作能力的程序，可以运行在本机或远程基础设施上。

```text
[ ] Server 的所有者、来源、版本和发布摘要是否可验证？
[ ] Server 实际暴露的能力是否与声明一致？
[ ] Server 是否只访问完成任务所需的数据和系统？
[ ] Server 是否基于可信身份执行工具级和对象级授权？
[ ] Server 是否验证所有 Tool 参数和 Resource URI？
[ ] Server 是否限制输出大小、内容类型、调用时间和资源消耗？
[ ] Server 日志是否避免记录 Token、Prompt 敏感字段和 Tool 结果？
[ ] Server 下线后，Host 中的能力是否及时移除？
```

### 1.4 连接矩阵

| Host | Client | Server | 本地/远程 | Transport | 身份 | Server 能力 | Client 能力 | 数据/系统范围 |
|---|---|---|---|---|---|---|---|---|
| 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 |

## 2. MCP 能力与控制主体清单

### 2.1 Server primitives

| Primitive | 典型控制主体 | 主要方法 | 作用 | 主要风险 |
|---|---|---|---|---|
| Prompts | 用户选择、Host 展示 | `prompts/list`、`prompts/get` | 提供可复用提示模板 | 隐藏指令、参数注入、误导用户 |
| Resources | Host/应用选择 | `resources/list`、`resources/templates/list`、`resources/read` | 提供只读上下文 | 越权读取、数据泄露、间接提示词注入 |
| Tools | 模型提出、Host 决策 | `tools/list`、`tools/call` | 执行函数或外部动作 | 越权、副作用、参数注入、过度代理 |

这里的“控制主体”是常见交互模式，不是强制安全边界。无论由用户、应用还是模型选择，Host 与 Server 都必须独立执行授权和策略检查。

### 2.2 Client features

| Feature | 方向 | 典型方法 | 作用 | 主要风险 |
|---|---|---|---|---|
| Roots | Server → Client 请求范围 | `roots/list` | 告知 Server 应关注的文件根 | 被误当成强制沙箱、范围过宽 |
| Sampling | Server → Client | `sampling/createMessage` | 请求 Host 的模型完成生成 | Server 借用模型、上下文或工具能力 |
| Elicitation | Server → Client | `elicitation/create` | 请求用户补充信息或完成外部交互 | 欺骗性确认、过度收集、敏感信息索取 |
| Tasks | 双向、实验性 | `tasks/*` | 延迟执行、状态查询和取消 | 长生命周期权限、后台副作用、取消失效 |

重要边界：

```text
Roots 表达“建议操作范围”，本身不是操作系统沙箱。
Sampling 允许 Server 间接使用 Host 的模型能力，必须由 Client 保留控制权。
Elicitation 是 Server 发起的用户交互，不能把 Server 文案视为可信系统提示。
Tasks 在 2025-11-25 版仍属实验能力，启用前必须单独评估生命周期与取消语义。
```

## 3. JSON-RPC 消息检查清单

### 3.1 Request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

```text
[ ] `jsonrpc` 是否为正确版本？
[ ] `id` 是否在当前连接或会话中可唯一关联？
[ ] `method` 是否存在且方向正确？
[ ] `params` 是否符合协商能力和方法 Schema？
[ ] 未知字段、超深对象、超长字符串和错误类型是否被拒绝？
[ ] 同一 `id` 的重复请求是否产生歧义或重复副作用？
```

### 3.2 Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": []
  }
}
```

```text
[ ] Response 的 `id` 是否对应未完成 Request？
[ ] 是否只包含 `result` 或 `error` 中的一种？
[ ] 未知、过期或已取消 `id` 的 Response 是否被忽略？
[ ] Error 是否避免泄露文件路径、Token、栈和内部实现？
[ ] Result 是否通过内容类型、大小和结构校验？
```

### 3.3 Notification

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

```text
[ ] Notification 是否不包含 `id`？
[ ] 接收方是否不会为 Notification 返回 JSON-RPC Response？
[ ] 未协商的 list-changed、progress 或 logging Notification 是否被拒绝或忽略？
[ ] Notification 洪泛是否受到速率和队列限制？
[ ] 通知内容是否不能直接授权 Tool 或改变用户确认？
```

## 4. 生命周期测试清单

### 4.1 Initialization

当前规范基线使用 `2025-11-25`：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": {},
    "clientInfo": {
      "name": "authorized-test-client",
      "version": "1.0.0"
    }
  }
}
```

验证清单：

```text
[ ] `initialize` 是否为连接后的首次协议交互？
[ ] Client 是否发送自己支持的协议版本？
[ ] Server 是否返回相同版本或自己支持的另一版本？
[ ] Client 不支持 Server 返回版本时是否断开？
[ ] Client 与 Server 是否交换实现名称和版本？
[ ] 双方是否明确声明可用 capabilities？
[ ] Client 是否在成功响应后发送 `notifications/initialized`？
[ ] 初始化完成前，是否只允许规范规定的有限消息？
[ ] Server 提供的 `instructions` 是否作为不可信提示处理？
[ ] HTTP 后续请求是否携带协商后的 `MCP-Protocol-Version`？
```

### 4.2 Operation

```text
[ ] 双方只使用已经协商的能力
[ ] `*/list` 结果支持分页时是否正确处理 cursor
[ ] list-changed 后是否重新获取并重新评估能力
[ ] 长操作是否发送有限、可关联的 progress
[ ] 请求超时后是否发送取消并停止等待
[ ] progress 是否不能无限延长最大总超时
[ ] Tool 多轮循环是否受次数、成本、时间和副作用预算限制
[ ] 连接恢复后是否避免重放已成功的非幂等 Tool
```

### 4.3 Shutdown

MCP 没有统一的协议级 shutdown 方法，使用底层 Transport 结束连接。

```text
[ ] stdio 是否先关闭子进程输入并等待正常退出？
[ ] 子进程超时不退出时是否采用受控终止流程？
[ ] HTTP 是否关闭关联连接或显式结束受支持的会话？
[ ] 关闭后是否拒绝旧 Session ID 和后续消息？
[ ] 未完成 Request、Task 和 Tool 是否取消或标记状态不确定？
[ ] Token、临时文件、管道和子进程是否清理？
[ ] 断开与异常关闭是否记录原因和最后请求 ID？
```

## 5. stdio Transport 测试清单

stdio 通常由 Client 启动本地 Server 子进程，并通过 stdin/stdout 交换按换行分隔的 UTF-8 JSON-RPC 消息。

```text
[ ] Server 可执行文件或脚本来自可信、固定版本和受控路径
[ ] 启动命令使用固定 argv，不经过 Shell 字符串拼接
[ ] 工作目录明确且不指向敏感或全盘根目录
[ ] 继承环境变量采用 allowlist，移除不必要凭据
[ ] 子进程使用独立低权限账户或沙箱
[ ] Server 只在 stdout 输出合法 MCP 消息
[ ] 日志仅写 stderr，不污染 JSON-RPC 消息流
[ ] 单条消息不得包含未编码的嵌入换行造成帧混淆
[ ] Client 限制单条消息大小、行长、解析深度和速率
[ ] Server 无法借 Host 权限访问 roots 之外的文件
[ ] 进程退出、崩溃和 stderr 输出不会被误当作 Tool 结果
[ ] 关闭连接后子进程、子孙进程和文件句柄全部退出
```

stdio 不是天然安全边界：本地 Server 默认继承启动用户可用的文件、网络和进程权限，必须使用操作系统权限或沙箱真正限制。

## 6. Streamable HTTP 测试清单

当前标准远程传输使用单一 MCP Endpoint，通过 HTTP POST 发送消息；HTTP GET 可选择建立 SSE 流。旧 HTTP+SSE 仅作为旧版兼容路径。

### 6.1 基础协议

```text
[ ] MCP Endpoint 同时按规范处理 POST，并按能力处理 GET
[ ] Client POST 的 `Accept` 同时支持 `application/json` 与 `text/event-stream`
[ ] Request 响应只返回 JSON 或与该请求关联的 SSE 流
[ ] Notification/Response 被接受时返回适当的空响应状态
[ ] GET SSE 不支持时返回明确的 Method Not Allowed
[ ] UTF-8、Content-Type、消息大小和 JSON 深度得到校验
[ ] 非 MCP 路径不能绕过认证进入同一处理器
```

### 6.2 网络与 Origin

```text
[ ] 本地 HTTP Server 默认只绑定 loopback，而不是 `0.0.0.0`
[ ] 所有入站连接都验证 `Origin`，无效 Origin 返回拒绝
[ ] DNS rebinding 场景不能从恶意网页访问本地 MCP Server
[ ] 反向代理不会删除、伪造或错误信任 Origin 与身份头
[ ] TLS 验证、主机名、代理和重定向策略正确
[ ] CORS 不允许任意站点携带 MCP 凭据访问
[ ] 防火墙、网络策略和服务发现只暴露必要范围
```

### 6.3 认证与会话

```text
[ ] 远程 Server 对所有连接实施适当认证
[ ] Token 具有受众、范围、过期时间和最小权限
[ ] 不接受为其他服务签发的 Token
[ ] Session ID 由 Server 安全生成，不含权限声明或可猜值
[ ] 后续请求必须绑定正确的 Session ID、用户和协议版本
[ ] 跨用户、跨租户或跨 Client 复用 Session ID 被拒绝
[ ] Session 终止后旧 ID 不可继续使用
[ ] 重连和恢复不会重复执行已成功的非幂等 Tool
[ ] SSE 断线重连不会泄露其他会话消息
[ ] 日志不记录完整 Authorization 或 Session ID
```

### 6.4 旧 HTTP+SSE 兼容

```text
[ ] 是否确实需要兼容 `2024-11-05` 的旧 Transport？
[ ] 旧 GET/SSE 与 POST Endpoint 是否执行相同认证授权？
[ ] Client 降级仅在规范允许的失败条件下发生？
[ ] 攻击者能否强制降级到更弱认证的旧路径？
[ ] 旧 Endpoint 是否增加重复路由、CORS 或会话混淆风险？
[ ] 停用计划、监控和客户端迁移状态是否明确？
```

## 7. Prompts 测试清单

```text
[ ] `prompts/list` 只返回当前用户和租户可见模板
[ ] Prompt 名称、描述和参数 Schema 与实际行为一致
[ ] `prompts/get` 对名称和参数执行严格校验
[ ] 未知参数、错类型、超长值和控制字符被拒绝
[ ] 模板内容清晰展示给用户，不隐藏高影响指令
[ ] Prompt 不能提升 Server、Tool 或用户权限
[ ] 模板参数按数据处理，不进入可执行代码或未转义指令
[ ] Prompt 返回的嵌入 Resource 仍执行独立授权
[ ] Server 更新 Prompt 后触发 list-changed，并由 Host 重新审查
[ ] 同名 Prompt 的来源 Server 在 UI 中可辨识
[ ] Prompt 内容被视为不可信输入，不可覆盖 Host 安全策略
```

## 8. Resources 测试清单

Resources 语义上用于读取上下文，但“只读”不代表“无风险”。读取仍可能泄露敏感信息或向模型注入恶意指令。

```text
[ ] `resources/list` 不枚举无权读取的 URI 和元数据
[ ] Resource URI 使用明确 Scheme、规范化和 allowlist
[ ] `resources/read` 基于当前可信身份执行对象级授权
[ ] 文件 Resource 限制在真实沙箱根，不只依赖 roots 声明
[ ] 数据库 Resource 强制租户过滤和字段最小化
[ ] Resource Template 参数执行类型、格式、长度和范围校验
[ ] 禁止路径穿越、符号链接逃逸、SSRF 和任意 Scheme
[ ] 文本、图片、音频和二进制内容限制大小及 MIME 类型
[ ] Resource 内容进入 LLM 前标记来源和信任级别
[ ] 外部内容中的指令不能授权 Tool 或改变系统策略
[ ] `subscribe` 和 list-changed 不泄露其他用户资源变化
[ ] 缓存按 Server、用户、租户、URI 和授权上下文隔离
[ ] 错误不泄露真实路径、SQL、内部 URL 和对象存在性
```

## 9. Tools 测试清单

### 9.1 枚举与 Schema

```text
[ ] `tools/list` 仅返回当前会话可以实际调用的 Tool
[ ] Tool 名称包含明确 Server 来源或命名空间
[ ] 描述准确说明读取、写入、网络和高影响副作用
[ ] `inputSchema` 使用明确类型、required、范围和 additionalProperties 策略
[ ] 若声明 `outputSchema`，结果在返回前验证
[ ] read-only、destructive、idempotent 等注解只作为提示，不替代强制策略
[ ] 动态 Tool 列表变化后，Host 撤销旧能力并重新确认新增能力
```

### 9.2 调用与授权

```text
[ ] 模型只能提出调用，Host 保留最终执行决策
[ ] 每次 `tools/call` 使用真实用户或服务身份重新鉴权
[ ] 普通用户不能通过 Tool 名或参数自述管理员身份
[ ] 对象级权限不信任模型生成的 user_id、tenant_id 或 owner
[ ] 参数在 Server 端严格校验并规范化
[ ] 下游 SQL、命令、文件、URL 和 API 使用安全实现
[ ] 敏感调用在执行前展示 Tool、对象、关键参数和副作用
[ ] 用户确认绑定当前调用，不能重放或覆盖多个动作
[ ] 非幂等 Tool 使用幂等键并处理超时后的不确定状态
[ ] 一次 Run 的 Tool 数量、深度、成本和持续时间有上限
[ ] 取消后排队中或进行中的 Tool 不继续产生副作用
[ ] Tool 结果被视为不可信内容，不能自动批准下一次调用
```

### 9.3 Tool 结果

```text
[ ] `content` 中每个 ContentBlock 的类型与大小有效
[ ] `structuredContent` 符合 Tool 声明的输出 Schema
[ ] `isError` 与实际执行状态一致
[ ] 错误结果不会被模型误当作成功结果继续执行
[ ] Resource Link 和 Embedded Resource 重新执行访问控制
[ ] Tool 结果不包含无关字段、凭据、栈或内部标识
[ ] HTML、Markdown、终端和日志输出在各自 Sink 正确编码
[ ] Tool 调用日志记录主体、参数摘要、授权、结果和副作用
```

## 10. Roots、Sampling、Elicitation 与 Tasks 测试清单

### 10.1 Roots

```text
[ ] Host 仅暴露用户明确选择的最小文件根
[ ] Roots 不包含主目录、凭据目录、全盘根或无关仓库
[ ] Root 变化需要用户可见并触发权限重新评估
[ ] Server 不能通过 `..`、符号链接、挂载点或路径编码逃逸
[ ] 操作系统沙箱独立限制实际文件访问
[ ] 多个 Server 不共享不必要的 Root 与文件缓存
[ ] 日志记录 Server、Root、文件对象和访问结果
```

### 10.2 Sampling

```text
[ ] Client 仅在初始化中声明实际支持的 Sampling 能力
[ ] Server 的 Sampling 请求显示来源、目的、Prompt 和数据范围
[ ] 用户可以审查、修改或拒绝请求与生成结果
[ ] Server 不能选择超出 Host 策略的模型或成本
[ ] Sampling 不自动包含其他 Server 的上下文
[ ] `includeContext` 兼容行为受到显式能力与最小化控制
[ ] Sampling with Tools 只在协商相应能力时启用
[ ] 嵌套 Tool 循环使用独立授权、次数、成本和时间预算
[ ] Server 返回的 Prompt 不能覆盖 Host 的系统安全策略
[ ] 生成结果返回 Server 前执行用户控制和敏感数据检查
```

### 10.3 Elicitation

```text
[ ] UI 明确标识请求来自哪个 MCP Server
[ ] 文案说明为何需要信息以及将发送给谁
[ ] 用户可以提供、拒绝或取消
[ ] Form Schema 限制字段类型、长度、格式和数量
[ ] 不通过表单索取密码、API Key、恢复码或支付秘密
[ ] Server 不能把 Elicitation 响应当作新权限或永久同意
[ ] URL mode 只导航到可信 HTTPS 来源并显示目标域名
[ ] URL mode 返回后只接收必要结果，不泄露浏览器会话
[ ] Elicitation 不能伪造 Host 原生确认对话框
[ ] 输入在发送 Server 前进行最小化与敏感性提示
```

### 10.4 Tasks（实验性）

```text
[ ] 只有双方协商相应 Tasks 子能力时才创建 Task
[ ] Task ID 随机、不可猜且绑定用户、Server 和会话
[ ] `tasks/list` 只返回当前主体可见任务
[ ] `tasks/cancel` 验证所有权并真正传播取消
[ ] Task 超时、过期、结果保留和清理策略明确
[ ] 后台任务不能继续使用已撤销 Token 或权限
[ ] 延迟执行前重新验证权限、参数和用户确认是否仍有效
[ ] Task 结果和错误不跨租户泄露
[ ] 重试、恢复和查询不会重复产生非幂等副作用
[ ] 实验能力可独立禁用并具有版本兼容测试
```

## 11. MCP 端到端流程测试清单

```text
用户输入
  -> Host 确定可用 MCP Client
  -> Client/Host 获取已协商的 Tool 与 Resource
  -> Host 将必要能力描述提供给 LLM
  -> Host 按需读取经过授权的 Resource
  -> LLM 生成回答或提出 Tool Call
  -> Host 校验意图、权限、参数和用户确认
  -> Client 发送 `tools/call`
  -> Server 再次鉴权、校验并执行固定实现
  -> 结果作为不可信数据返回 Host 与 LLM
  -> 达到预算或无需 Tool 时返回最终响应
```

逐步检查：

```text
[ ] 用户原始目标被原样记录
[ ] Tool 与 Resource 枚举发生在正确身份和租户上下文
[ ] 只把任务所需的能力和数据放入模型上下文
[ ] Resource 内容不能变成更高优先级指令
[ ] LLM 选择 Tool 后，Host 独立判断是否允许执行
[ ] Server 不相信 Host 传入的自述身份字段
[ ] Tool 结果与原始请求使用 JSON-RPC ID 和关联 ID 绑定
[ ] 结果进入下一轮前执行数据最小化和注入防护
[ ] 多轮调用达到预算后安全停止
[ ] 最终回答说明已执行和未执行的动作
```

## 12. 快速测试用例表

| 编号 | 测试目标 | 无害操作 | 风险信号 |
|---|---|---|---|
| MCP-01 | Host/Client/Server 映射 | 建立连接矩阵 | 无法确定能力来源和责任边界 |
| MCP-02 | 协议版本 | 请求当前支持版本 | 不兼容版本仍继续通信 |
| MCP-03 | 初始化顺序 | 初始化前发送普通请求 | Server 接受未初始化操作 |
| MCP-04 | 能力协商 | 调用未声明能力 | 未协商能力仍执行 |
| MCP-05 | JSON-RPC ID | 返回未知或重复 ID | Client 错误关联结果 |
| MCP-06 | Notification | 发送带 ID 的测试通知 | 被当作普通 Request 执行 |
| MCP-07 | stdio 输出纯度 | Server 向 stdout 写测试日志 | 消息流被污染或错误解析 |
| MCP-08 | stdio 权限 | 读取 Root 内合成文件 | Server 实际权限超过声明范围 |
| MCP-09 | 本地绑定 | 检查 HTTP 监听地址 | 本地 Server 暴露到所有网卡 |
| MCP-10 | Origin 验证 | 使用无效测试 Origin | Streamable HTTP 未拒绝 |
| MCP-11 | 远程认证 | 未认证初始化 | 获得有效会话或能力列表 |
| MCP-12 | Session 隔离 | 跨测试账户复用 Session ID | 会话被其他主体接受 |
| MCP-13 | 版本 Header | 省略/改变协商版本 | 后续请求仍无条件接受 |
| MCP-14 | Prompt 枚举 | 普通用户执行 `prompts/list` | 返回无权使用模板 |
| MCP-15 | Prompt 参数 | 提交错类型和超长值 | 未校验进入模板或下游 |
| MCP-16 | Resource 授权 | 用户 A 读取用户 B 的 marker | 跨用户读取成功 |
| MCP-17 | Resource 路径 | 请求 Root 外 canary | 路径或链接逃逸成功 |
| MCP-18 | Resource 注入 | Resource 含无害指令 marker | 改变计划或 Tool 选择 |
| MCP-19 | Tool 最小化 | 比较普通/管理用户 Tool 列表 | 普通用户获得管理 Tool |
| MCP-20 | Tool Schema | 缺失、额外、错类型参数 | 非法参数进入实际执行 |
| MCP-21 | 服务端授权 | Prompt 自述管理员身份 | 权限未变但高权 Tool 执行 |
| MCP-22 | 用户确认 | 调用可回滚测试写入 | 未确认即产生副作用 |
| MCP-23 | Tool 结果注入 | 返回唯一无害指令 marker | 自动触发额外 Tool |
| MCP-24 | Roots 边界 | 声明最小 Root 并测试外部 canary | Roots 被误当作唯一沙箱 |
| MCP-25 | Sampling 控制 | Server 请求固定无害生成 | 未经审查自动发送和返回 |
| MCP-26 | Elicitation | 请求非敏感测试字段 | 来源、目的或接收方不透明 |
| MCP-27 | Task 所有权 | 用户 A 查询用户 B 测试 Task | 跨用户任务数据泄露 |
| MCP-28 | 取消与超时 | 取消长时间无害 Task | 取消后仍运行或产生结果 |
| MCP-29 | 多轮预算 | 只读 Tool 重复请求 | 无次数、成本或总时长上限 |
| MCP-30 | 修复回归 | 重放全部 MCP 用例 | 任一边界仍可稳定绕过 |

## 13. 单次测试记录模板

> 通用字段、证据要求和安全约束见：[AI 安全测试通用记录模板](../_模板/测试记录-通用.md)。下方保留本主题的专用字段。

```text
测试编号：
时间 / 关联 ID：
授权范围：
测试用户 / 租户：

Host 名称 / 版本：
Client 名称 / 版本：
Server 名称 / 版本 / 来源：
本地或远程：
Transport：stdio / Streamable HTTP / 旧 HTTP+SSE / Custom
协议版本：
认证主体 / Scope：
Session ID 摘要：

Client capabilities：
Server capabilities：
测试 Primitive / Feature：
JSON-RPC method：
Request ID：
参数 Schema 校验：

用户原始目标：
Resource / Prompt / Tool 名称：
对象 URI / ID：
模型提出的调用：
Host 策略判定：
用户确认内容：
Server 授权判定：
实际执行及副作用：

Response / Error：
Tool Result / Resource 内容：
是否进入下一轮模型上下文：
是否触发额外调用：
超时 / 取消结果：

日志 / 截图：
清理状态：
最终判定：符合预期 / 信息暴露 / 调用被阻断 / 未授权读取 / 未授权动作
```

## 14. 根因审计清单

```text
[ ] 是否把 MCP 标准化接口误认为安全边界？
[ ] 是否无法识别 Tool、Prompt 和 Resource 来自哪个 Server？
[ ] 是否在能力协商前或未协商情况下接受操作？
[ ] 是否把 Tool 描述和注解当作强制授权策略？
[ ] 是否把 roots 当作操作系统级文件沙箱？
[ ] stdio Server 是否继承 Host 全部用户权限和秘密环境变量？
[ ] 本地 HTTP Server 是否绑定所有网卡且不验证 Origin？
[ ] 远程 Server 是否缺少认证、Audience、Scope 或租户隔离？
[ ] Session 是否未绑定用户、Client 和协议版本？
[ ] Prompt、Resource 和 Tool Result 是否被当作可信指令？
[ ] 模型是否直接决定敏感 Tool 的最终执行？
[ ] Tool 是否缺少服务端 Schema、工具级和对象级授权？
[ ] 用户确认是否可被 Prompt、Server 或 Tool Result 伪造？
[ ] Sampling 是否让 Server 获得超出预期的模型和上下文能力？
[ ] Elicitation 是否被用于索取秘密或制造欺骗性确认？
[ ] Tasks 是否在权限撤销或用户取消后继续执行？
[ ] 多轮 Tool 是否缺少次数、成本、时间和副作用预算？
[ ] 旧 Transport 兼容是否形成认证或策略降级？
[ ] 日志是否无法还原用户目标、模型提议、授权和实际执行？
```

## 15. 修复与回归清单

### 15.1 架构和身份

```text
[ ] 维护 Host、Client、Server、能力和数据范围清单
[ ] 每个 Server 使用独立连接、身份、权限和审计范围
[ ] 本地 Server 固定来源并使用操作系统沙箱
[ ] 远程 Server 使用适当认证、最小 Scope 和租户隔离
[ ] 管理、写入和高影响 Server 默认不向普通会话连接
```

### 15.2 协议与 Transport

```text
[ ] 严格实现初始化、版本和能力协商状态机
[ ] 验证 JSON-RPC 消息方向、ID、Schema、大小和速率
[ ] stdio stdout 仅传协议消息，日志进入 stderr
[ ] Streamable HTTP 验证 Origin、认证、Session 与协议版本
[ ] 本地 HTTP 只绑定 loopback，远程连接使用 TLS
[ ] 不需要的旧 HTTP+SSE 与自定义 Transport 关闭
```

### 15.3 内容与动作

```text
[ ] Prompt、Resource 和 Tool Result 全部按不可信内容处理
[ ] Resource 使用真实数据边界、对象授权和最小字段
[ ] Tool 使用严格 Schema、固定实现和服务端独立鉴权
[ ] 高影响动作执行前显示最终参数并绑定用户确认
[ ] Roots 之外使用操作系统权限与沙箱强制阻断
[ ] Sampling、Elicitation 和 Tasks 默认关闭，按需逐项启用
[ ] Tool 循环、Task 和流式连接具有预算、超时、取消与幂等控制
```

### 15.4 修复后复测顺序

```text
1. 不兼容协议版本无法进入 operation 阶段
2. 初始化前和未协商能力的请求被稳定拒绝
3. stdio Server 不污染 stdout，且无法越过操作系统沙箱
4. 本地 HTTP 不对外暴露，无效 Origin 被拒绝
5. 远程认证、Session、协议版本和租户绑定正确
6. Prompt、Resource 和 Tool 列表仅包含当前用户可见对象
7. Resource 无法路径逃逸、跨租户读取或授权 Tool
8. Tool 非法参数、角色自述和对象越权在执行前阻断
9. 敏感副作用必须经过绑定最终参数的用户确认
10. Roots、Sampling、Elicitation 和 Tasks 均符合最小能力策略
11. 取消、超时、重连和重试不会重复非幂等副作用
12. 日志能关联用户目标、Server 来源、JSON-RPC ID、授权和执行结果
13. 重放 MCP-01～MCP-30，确认全部边界稳定
```

## 16. 最终判定口径

```text
安全：MCP 连接来源可信、协议状态正确、能力最小化；所有数据读取和 Tool 动作基于真实身份独立授权，并具有用户控制、预算、审计和沙箱。

中风险：存在版本、能力或 Server 信息暴露，但越权读取和动作在执行前被 Host 或 Server 稳定阻断。

高风险：普通用户可跨对象读取 Resource、调用管理 Tool、逃逸 Root、复用其他会话，或由不可信内容改变 Tool 调用。

严重：恶意或被攻陷 Server 可利用 Host 权限读取广泛文件、窃取凭据、执行高权限外部动作，或通过 Sampling/Tool 链持续扩大控制范围。
```

## 17. 官方规范参考

- [MCP Architecture Overview](https://modelcontextprotocol.io/docs/learn/architecture)
- [MCP 2025-11-25 Lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
- [MCP 2025-11-25 Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP 2025-11-25 Schema](https://modelcontextprotocol.io/specification/2025-11-25/schema)
- [MCP Resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)
- [MCP Sampling](https://modelcontextprotocol.io/specification/2025-11-25/client/sampling)
- [MCP Elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)
- [MCP Tasks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks)

一句话总结：**MCP 标准化了连接，不替代安全控制；Host 决定信任与用户体验，Client 执行协议边界，Server 必须对每次数据访问和动作实施真实授权。**
