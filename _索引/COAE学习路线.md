---
id: coae-index-b4f4f4e4
title: 'COAE 学习路线'
aliases: []
domain:
  - 'vault'
note_type:
  - index
attack_phase:
  - governance
status: draft
tags:
  - coae
  - ai-security
updated: 2026-08-17
---
# COAE 学习路线

## 第一阶段：建立共同语言

1. [大模型与数学基础](../AI与LLM基础/大模型与数学基础_从零到AI安全完整总结.md)
2. [LLM 基础](../AI与LLM基础/LLM基础.md)
3. [AI 安全框架](../AI安全框架/安全框架.md)
4. [MCP 基础架构与安全测试清单](../AI与LLM基础/MCP基础架构与安全测试清单.md)

## 第二阶段：理解训练前与训练期攻击

1. [AI 数据管线与攻击面](../AI数据攻击/AI数据管线与攻击面.md)
2. [AI 数据攻击总结](../AI数据攻击/AI数据攻击总结详解与测试笔记.md)
3. [标签翻转](<../AI数据攻击/标签翻转Label Flipping攻击测试与笔记.md>)
4. [定向标签攻击](<../AI数据攻击/定向标签攻击Targeted Label Attacks测试与笔记.md>)
5. [Clean Label Attack](<../AI数据攻击/干净标签攻击Clean Label Attacks原理与安全测试笔记.md>)
6. [木马与后门攻击](<../AI数据攻击/木马攻击Trojan Attacks原理与安全测试笔记.md>)

## 第三阶段：理解模型制品和供应链

1. [模型文件安全审查速查表](../AI模型供应链安全/模型文件安全审查速查表.md)
2. [Pickle 反序列化原理与防御](../AI模型供应链安全/Pickle反序列化在AI安全中的原理与防御.md)
3. [Pickle 与张量隐写测试笔记](../AI模型供应链安全/Pickle反序列化与张量隐写原理和安全测试笔记.md)
4. [框架与依赖漏洞](<../AI模型供应链安全/AI框架与依赖漏洞Vulnerable Framework Code安全测试与笔记.md>)
5. [模型部署篡改](<../AI模型供应链安全/模型部署篡改Model Deployment Tampering安全测试与笔记.md>)

## 第四阶段：理解推理期模型攻击

1. [Evasion Attacks 与 GoodWords](<../AI应用与系统安全/Evasion Attacks与GoodWords攻击安全测试清单与学习笔记.md>)
2. [一阶梯度规避攻击 FGSM 与 I-FGSM](<../AI应用与系统安全/一阶梯度规避攻击FGSM与I-FGSM从零学习笔记.md>)
3. [DeepFool 最小扰动规避攻击](../AI应用与系统安全/DeepFool最小扰动规避攻击从零学习笔记.md)
4. [稀疏规避攻击与 EAD](../AI应用与系统安全/稀疏规避攻击与EAD从零学习笔记.md)
5. [JSMA 显式 L0 稀疏规避攻击](../AI应用与系统安全/JSMA显式L0稀疏规避攻击从零学习笔记.md)
6. [模型逆向](<../AI应用与系统安全/模型逆向Model Reverse Engineering原理与防御笔记.md>)
7. [ML 服务拒绝与 Sponge Examples](<../AI应用与系统安全/ML服务拒绝Denial of ML Service与Sponge Examples笔记.md>)

## 第五阶段：测试 LLM 应用和 Agent

1. [越狱](../LLM应用测试与提示词攻击/越狱.md)
2. [间接提示词注入](../LLM应用测试与提示词攻击/间接提示词注入.md)
3. [数据外泄](<../LLM应用测试与提示词攻击/LLM数据外泄Exfiltration攻击测试与笔记.md>)
4. [Function Calling](<../LLM应用测试与提示词攻击/LLM输出Function Calling测试与笔记.md>)
5. [MCP 常见漏洞](<../AI应用与系统安全/MCP Server常见漏洞安全测试清单.md>)
6. [恶意 MCP Server](<../AI应用与系统安全/恶意MCP Server攻击与安全测试清单.md>)

## 第六阶段：综合复习

- 按 [攻击生命周期](攻击生命周期.md) 串联不同领域。
- 使用 [安全测试矩阵](安全测试矩阵.md) 设计授权测试。
- 使用 [通用测试记录模板](../_模板/测试记录-通用.md) 保存证据。
- 使用 [考试可复用代码块索引](考试可复用代码块索引.md) 直接跳到各专题代码模板。
- 使用 [全库代码块跳转索引](全库代码块跳转索引.md) 检索所有包含代码块的小节。
- 从各领域索引中的速查、误区和记忆卡片进行复习。
