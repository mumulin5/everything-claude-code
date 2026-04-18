---
name: workbuddy-evolving-skill
description: WorkBuddy-ready self-evolving skill plugin that combines ECC core capabilities, Claude harness orchestration, and Nüwa evolution patterns.
origin: ECC
version: 1.0.0
---

# WorkBuddy Evolving Skill

This is a bilingual (English + 中文) WorkBuddy skill blueprint for a self-evolving plugin.
面向 WorkBuddy 的自我进化型技能插件模板，融合 Everything Claude Code 核心能力、Claude Harness 核心逻辑与 Nüwa 进化闭环：

1. **Everything Claude Code 核心能力层**：agents、skills、commands、hooks、rules、MCP orchestration、verification loops。
2. **Claude Harness 核心逻辑层**：任务编排、工具路由、记忆检索、执行反馈闭环（plan → act → observe → recover → verify）。
3. **女娲（Nüwa）核心层**：经验沉淀、策略重写、能力进化、安全约束。  
   Nüwa here means a learning-and-evolution layer that turns execution feedback into safer, better next-run policies.

## When to Activate

- 在 WorkBuddy 中需要搭建可持续迭代的智能插件时
- 需要同时覆盖任务规划、执行、复盘与自进化时
- 需要把 Claude 工具调用和企业内部工具统一编排时

## Capability Mapping

| Layer | Core Functions | WorkBuddy Output |
|---|---|---|
| ECC Core | agent-first delegation, command workflows, hooks automation, rules guardrails, MCP tool integration | reusable and standardized delivery pipeline |
| Claude Harness | extended thinking, tool use, vision, caching, action/observation contract, recovery loop | high-quality reasoning with controllable execution |
| Nüwa | pattern mining, policy evolution, confidence scoring | continuously improving prompt and workflow policy |

## ECC Core Capability Set

1. **Agent-First Delegation**：优先将复杂任务分配给专用 agents（planner/tdd/security/code-review 等）。
2. **Workflow Commands**：通过 `/plan`、`/tdd`、`/code-review`、`/build-fix` 等命令形成可复用流程。
3. **Hook Automation**：在 pre/post tool 阶段执行自动检查、会话持久化与一致性校验。
4. **Rules Guardrails**：统一执行安全、测试、代码风格与提交规范。
5. **Verification Loop**：以测试、评审、安全扫描、回归验证作为发布门禁。

## Claude Harness Core Logic

1. **Plan**：解析意图，拆分任务，定义成功标准和停止条件。
2. **Act**：调用最小必要工具，使用结构化参数，保持可追踪执行。
3. **Observe**：记录工具输出（status/summary/next_actions/artifacts）用于后续决策。
4. **Recover**：失败时提供根因提示、安全重试路径与明确 stop condition。
5. **Verify**：执行测试/评估/安全检查后再提交最终答案或策略更新。

## WorkBuddy Runtime Contract

1. **Input**
   - user_intent
   - context (chat history, project metadata, memory keys)
   - tools (WorkBuddy 可用工具清单)
2. **Processing**
   - Harness Router 选择模型与工具
   - Claude 执行推理与工具调用
   - ECC Guardrails 进行规则与验证检查
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
- 执行遵循 harness 闭环：plan → act → observe → recover → verify。
- 进化策略必须可回滚，禁止覆盖历史稳定策略。
- 对外部输入执行白名单校验，敏感信息脱敏后入库。

## Quick Start Prompt

在 WorkBuddy 的系统提示或插件初始化提示中使用以下模板：

```text
Use workbuddy-evolving-skill mode.
Goal: solve the user task and improve future success rate.
Apply ECC core capabilities, Claude harness loop (plan-act-observe-recover-verify), and Nüwa learning for post-run evolution.
Return: answer, tool trace, and optional evolution patch with confidence score.
```
