## 为什么

P20 让工作区更易用，但编排器基本上仍是一个 planner/router 加任务创建器。要成为日常使用的多智能体软件，AgentHub 需要一个更清晰的主智能体/PMO 层，该层能够呈现可审计的计划、协调并行的角色智能体、解释阻塞原因、处理重试和兜底，并在不绕过调度器、计划验证器、目标注册表或护栏的前提下引导冲突解决。

## 变更内容

- 在现有的 Planner、Scheduler 和 TaskRun 系统之上，引入一个主 Agent / PMO 编排模型。
- 新增计划审核 / 计划决策界面：
  - 任务计划草稿可在执行前进行审核；
  - 用户可批准、拒绝或要求对计划进行澄清；
  - P21 仅支持通过验证的有限安全调整。
- 改进任务图协调：
  - 展示依赖组和可并行执行的任务；
  - 揭示任务处于等待、阻塞、可重试或可兜底状态的原因；
  - 保持 Scheduler 作为可运行状态的来源。
- 新增编排器后续操作：
  - 重试失败运行；
  - 使用显式兜底进行重试；
  - 向用户询问 approval/clarification；
  - 提出冲突解决步骤；
  - 从最新证据继续执行。
- 改进代码冲突处理：
  - 以用户可读的形式暴露目标锁定和脏工作区阻塞因素；
  - 让用户选择 retry/refresh/inspect，而非静默继续；
  - 不自动合并冲突代码。
- 在任务追踪中记录 PMO 证据：
  - 计划决策状态；
  - approval/rejection/clarification 结果；
  - 兜底原因；
  - conflict/blocker 摘要；
  - 下一步推荐操作。

## 能力

### 新能力

- `main-agent-orchestrator-pmo`：定义 PMO 风格的编排行为、
  计划评审决策、任务图协调可见性、blocker/conflict
  处理、兜底指导以及任务追踪证据。

### 修改后的能力

- `daily-agent-workspace`: 工作区必须暴露 PMO 计划决策状态和后续操作，而无需将聊天界面重新变为配置页面。
- `planner-routing-hardening`: 已验证的任务计划应在需要审查时进入 PMO 审查和决策流程，同时安全的自动启动路径保持明确且可审计。

## 影响

- 可能影响 `apps/api/app/planning.py`、`apps/api/app/task_runs.py`、
  `apps/api/app/scheduler.py`、`apps/api/app/mission_trace.py`、
  `apps/api/app/schemas.py` 和 task/ledger 响应辅助函数。
- 可能影响 `apps/web/src/components/task-card-list.tsx`、
  `apps/web/src/components/mission-panel.tsx`、
  `apps/web/src/components/chat-thread.tsx` 以及工作区 shell 测试。
- 新增计划决策状态、approval/refusal/clarification
  行为、调度器阻塞证据及兜底引导的后端测试。
- 新增计划决策 UI、下一步操作、阻塞卡片及
  retry/fallback 功能的前端测试。
- 不实现多用户协作、任意计划编辑、
  提供商市场、新适配器、生产部署或自动代码冲突合并。
