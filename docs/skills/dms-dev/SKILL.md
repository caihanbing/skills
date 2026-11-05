---
name: dms-dev
description: 在 DMS 需求、修复、继续开发或交接恢复中识别当前阶段，衔接必要的规划、执行、验证与审查；已有明确阶段请求可直接使用对应 Skill，普通问答和单独审查不扩成开发任务。
---

# DMS 开发入口

先对照当前请求、已有批准决定、实际工作区和有效证据，选择下一项必要工作。形成或承接设计前，按 [工作流契约](references/workflow-contract.md#授权与阶段) 核对本轮目标依据。明确的小任务直接执行；已核对且仍适用的决定、计划、实现和证据直接承接，不要求重新启动全流程。

读取 [工作流契约](references/workflow-contract.md) 判断阶段、权限和交付条件，按 [DMS 项目依据](references/dms-project-context.md) 选择本任务需调查的入口、模块、数据边界和适用规范。只有需要拆分任务、持久化进度或恢复时，再读 [任务契约](references/task-contract.md)；委派、失败处置、停止与恢复读 [执行策略](references/execution-policy.md)。

| 当前缺口 | 使用的能力 |
| --- | --- |
| 目标、业务期望或关键取舍仍不明确 | [dms-grill-me](../dms-grill-me/SKILL.md)；事实先调查，已有决定直接复用 |
| 目标已明确，但缺少足以实施的技术设计 | 主会话依据实际项目补设计，说明接口、数据、异常和兼容影响，再用 [dms-spec-check](../dms-spec-check/SKILL.md) 核对；任务清单不能替代设计 |
| 关键可行性尚不清楚 | 主会话先界定调查问题和允许的验证范围，交付结论、证据与限制；探索不自动转为实现 |
| 方案需要核对范围、歧义和验收 | [dms-spec-check](../dms-spec-check/SKILL.md) |
| 批准方案需要转成可执行任务 | 主会话沿用已有方案，按 [任务契约](references/task-contract.md) 明确任务、依赖与验证 |
| 已授权实施、继续或恢复 | 主会话直接推进，按需读取 [执行策略](references/execution-policy.md)，承接已有进度和有效证据 |
| 错误、构建或集成异常尚未定位 | [dms-systematic-debugging](../dms-systematic-debugging/SKILL.md) |
| 实现/修复需要场景、有效测试及完成证据 | [dms-test-gate](../dms-test-gate/SKILL.md)，在写目标测试前安排适用前置分析 |
| 项目代码需要独立审查或反馈复核 | [dms-review-changes](../dms-review-changes/SKILL.md)，按其适用范围执行 |
| 仅需要提交说明 | [dms-commit-msg](../dms-commit-msg/SKILL.md) |

只在新请求、阶段切换、关键阻断或证据失效时重新判断。下游阶段连续完成自身工作并返回主会话，不递归调用本入口。计划模式由成员选择，规划或执行任务不要求切换模式。报告本轮已完成事实、必要下一步及限制；自动选择 Skill 不增加操作授权。
