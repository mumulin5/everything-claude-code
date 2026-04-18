---
name: workbuddy-evolving-skill
description: WorkBuddy-ready self-evolving skill plugin that combines modern Claude capabilities with Herms orchestration and Nüwa evolution patterns.
origin: ECC
version: 1.0.0
---

# WorkBuddy Evolving Skill

This is a bilingual (English + 中文) WorkBuddy skill blueprint for a self-evolving plugin.
面向 WorkBuddy 的自我进化型技能插件模板，融合三层能力：

1. **Claude 最新能力层**：Messages API、Tool Use、Vision、Streaming、Extended Thinking、Prompt Caching、Batches、Agent SDK。
2. **Herms 核心层**：任务编排、工具路由、记忆检索、执行反馈闭环。
3. **女娲（Nüwa）核心层**：经验沉淀、策略重写、能力进化、安全约束。  
   Nüwa here means a learning-and-evolution layer that turns execution feedback into safer, better next-run policies.

## When to Activate

- 在 WorkBuddy 中需要搭建可持续迭代的智能插件时
- 需要同时覆盖任务规划、执行、复盘与自进化时
- 需要把 Claude 工具调用和企业内部工具统一编排时

## Capability Mapping

| Layer | Core Functions | WorkBuddy Output |
|---|---|---|
| Claude | extended thinking, tool use, vision, caching, batch async | high-quality reasoning + cost-efficient async throughput |
| Herms | intent parsing, router, memory lookup, action pipeline | stable and controllable execution pipeline |
| Nüwa | pattern mining, policy evolution, confidence scoring | continuously improving prompt and workflow policy |

## WorkBuddy Runtime Contract

1. **Input**
   - user_intent
   - context (chat history, project metadata, memory keys)
   - tools (WorkBuddy 可用工具清单)
2. **Processing**
   - Herms Router 选择模型与工具
   - Claude 执行推理与工具调用
   - Nüwa Learner 记录结果并更新策略
3. **Output**
   - final_answer
   - tool_trace
   - evolution_patch (可选，策略更新建议)

## Self-Evolution Loop

1. **Observe**：记录输入、工具轨迹、成功率、失败模式。
2. **Extract**：提取高频意图和失败根因，形成候选规则。
3. **Validate**：通过回放样本和置信度阈值过滤低质量规则。
4. **Evolve**：仅对通过验证的规则生成策略增量更新。
5. **Guard**：安全审查后再发布到下一轮 WorkBuddy 会话。

## Minimal Operating Rules

- 默认使用 Claude Sonnet 作为执行模型，复杂规划可切换 Claude Opus。
- 工具调用必须带结构化参数并保留调用日志。
- 进化策略必须可回滚，禁止覆盖历史稳定策略。
- 对外部输入执行白名单校验，敏感信息脱敏后入库。

## Quick Start Prompt

在 WorkBuddy 的系统提示或插件初始化提示中使用以下模板：

```text
Use workbuddy-evolving-skill mode.
Goal: solve the user task and improve future success rate.
Apply Herms routing for planning/execution and Nüwa learning for post-run evolution.
Return: answer, tool trace, and optional evolution patch with confidence score.
```
