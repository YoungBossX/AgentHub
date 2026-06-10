## 背景

P7 冻结在本地单用户 AgentHub 工作区基线。AgentHub 现在拥有一个包含 `demo-frontend`、`demo-backend` 和 `agenthub-platform` 的目标项目注册表，并且能够生成目标感知的迷你 CRM 合约和任务计划。然而，任务执行仍然主要采用运行启动驱动模式：可以创建任务并启动 TaskRun，但 AgentHub 尚未一致地拥有依赖顺序、目标写入锁、自动推进或下游阻塞状态。

P8 将 Manager / Orchestrator 从创建图的规划器转变为能够安全运行图的 PMO 式协调器。

## 目标 / 非目标

**目标：**

- 根据声明的依赖关系执行任务图。
- 当上游依赖失败时，阻塞下游任务。
- 使用 P7 目标注册表元数据，按目标 ID 序列化写入任务。
- 仅当依赖与安全规则允许时，才允许运行面向读取的审查/QA 任务。
- 利用现有的 TaskRun、差异对比、审查、预览和模拟部署路径，自动推进有界全栈应用流水线。
- 在 UI 中展示调度器状态。
- 保留 P6/P7 迷你 CRM 和平台保护行为。

**非目标：**

- 分布式工作节点集群。
- 多用户即时通讯或实时多用户冲突解决。
- 集成 Matrix、飞书、微信、Slack 或其他外部 IM。
- 生产环境部署或真实部署服务商。
- Docker 沙箱隔离。
- 服务商市场。
- 创建 PR。
- 任意 SaaS 生成。
- 完整外部仓库导入。
- Desktop/mobile 客户端。
- Document/PPT 制品编辑器。

## 调度器模型

P8 应引入一个调度器边界，该边界可在任务图创建后、TaskRun 状态变更后以及用户 retry/fallback 操作后被调用。

首个实现可在现有 FastAPI 进程内运行，并使用现有的后台任务行为；它不需要分布式队列。

建议的调度器输入：

```text
sessionId
task graph / tasks
task dependencies
task targetId
task write/read mode
task status and latest TaskRun status
target lock state
approval state
fallback eligibility
```

建议的调度器输出：

```text
task scheduler state
TaskRun creation when runnable
blocked state when dependencies fail
waiting_dependency state
waiting_target_lock state
scheduler events
pipeline continuation actions
```

调度器应保持保守策略：若无法证明任务可运行，则必须让任务保持等待或阻塞状态，而非静默启动。

## 依赖语义

任务已经存储了 `dependsOnTaskIds`。P8 应使该依赖列表可操作：

- 依赖未完成的任务进入 `waiting_dependency`；
- 具有 failed/interrupted/blocked 依赖的任务进入 `blocked`；
- 只有当所有依赖均已完成且所有 approvals/locks 均满足时，任务才变为可运行状态；
- 上游任务失败后，下游任务不得启动，除非用户重试或创建显式兜底路径。

对于 P6/P7 迷你 CRM，图表保持不变：

```text
Contract -> Backend -> Frontend -> Review/QA -> Preview -> Mock Deploy
```

P8 可能会在第一个调度器版本中保持后端 -> 前端的串行执行，即使不同的目标理论上可以并行运行。重要的行为是声明的依赖关系得到遵守，且同一目标的写入不会并发执行。

## 目标写入锁

P8 应使用 P7 目标 ID 作为锁键。初始锁键：

- `demo-frontend`；
- `demo-backend`；
- `agenthub-platform`。

编写任务：

- `demo-frontend` 的前端编码任务；
- `demo-backend` 的后端编码任务；
- `agenthub-platform` 的平台维护任务。

面向读取的任务：

- 审查 / QA 任务；
- 制品检查；
- 预览和模拟部署操作（当它们不修改目标源代码时）。

锁定规则：

- 同一目标在同一时刻只能运行一个写入任务；
- `demo-frontend` 写入操作是串行的；
- `demo-backend` 写入操作是串行的；
- `agenthub-platform` 写入操作需要显式平台模式及审批；
- 不同目标的写入操作仅在依赖规则允许且实现能将工作树冲突风险控制在有限范围内时，方可并发运行；
- 审查/QA 任务在依赖项完整且审查以读取为导向时，可在无写入锁的情况下运行。

第一种实现可以将锁存储在数据库中，或从活跃的 TaskRun 中推导出活跃锁。如果调度决策可能跨越请求、重试或进程重启，持久化数据库锁更为安全。

## 自动运行流水线

P8 应为有界全栈应用契约添加调度器驱动的自动运行路径。它应复用现有制品路径，而非引入新的执行引擎：

1. 合约任务完成或被视作规划制品。
2. 后端任务在依赖项和 `demo-backend` 锁允许时启动。
3. 通过现有差异路径收集后端差异。
4. 前端任务在后端依赖完成且
   `demo-frontend` 锁允许时启动。
5. 通过现有差异路径收集前端差异。
6. 审查/质量保证通过现有审查制品路径运行。
7. 预览通过现有预览路径启动。
8. 通过现有模拟部署路径创建模拟部署，并保持
   模拟标记。

调度器不得声称真实的 Claude/Codex 成功，除非存在适配器证据。
如果真实适配器失败，兜底可用性应可见，但兜底执行仍保持显式，除非当前策略已允许。

## 调度器状态

P8 应形式化调度器可见的状态，同时不抹除现有的 `Task.status` 和 `TaskRun.state` 行为。

建议的状态：

- `waiting_dependency`；
- `waiting_target_lock`；
- `running`；
- `completed`；
- `failed`；
- `blocked`；
- `retryable`；
- `fallback_available`；

这些可以表示为任务状态值、`plan_json`、`TaskRunEvent` 负载中的调度器元数据，或一个简短的调度器状态表。实现应选择最小的持久化选项，以便为 API 和 UI 提供足够的信息。

## UI 跟踪

P8 并非一次广泛的重新设计。它应在现有任务卡片、执行
轨迹和制品消息卡片界面上扩展调度器状态：

- 依赖等待中；
- 目标锁等待中；
- 运行中；
- 阻塞中；
- 失败；
- 可重试；
- 有兜底可用；
- 已完成。

UI 应帮助用户理解工作为何尚未运行、哪个目标被锁定、哪个依赖项失败，以及下一步可执行什么操作。

## 故障恢复

下游故障行为必须明确：

- 失败的依赖项会阻塞下游任务；
- 中断的依赖项会阻塞下游任务，直到 retry/fallback 解决它；
- 重试会创建可追溯的新 TaskRun 历史记录；
- 兜底可用性可见且可追溯；
- 上游失败后，下游任务不会静默继续；
- 当适配器未成功时，UI 状态不会声称成功。

## 风险 / 权衡

- **风险：调度器变成一个隐藏的分布式系统项目。** 缓解措施：保持 P8 为本地进程且兼容 SQLite，使用现有的 TaskRun 和事件流。
- **风险：锁过度约束了有用的并行性。** 缓解措施：从保守策略开始。仅当依赖规则和工作树冲突规则明确时，才可启用不同目标的并发。
- **风险：UI 变得嘈杂。** 缓解措施：在现有的 task/trace 界面中显示调度器状态，而不是创建新的仪表盘。
- **风险：自动运行重复执行代价高昂的真实适配器调用。** 缓解措施：除非明确需要有限范围的真实冒烟测试，否则 P8 预演可使用现有证据或 ScriptedMock 进行调度器管道测试。
- **风险：平台维护绕过了 P7 保护。** 缓解措施：`agenthub-platform` 保持平台模式且需审批授权。

## 迁移计划

1. 为依赖项添加调度器就绪评估。
2. 添加目标锁计算及锁感知的可运行决策。
3. 为有界应用流水线添加调度器驱动的自动运行推进。
4. 添加故障传播与 blocked/retry/fallback 状态。
5. 添加 UI 调度器跟踪状态。
6. 在冻结 P8 前演练迷你 CRM 与 target-lock/failure 案例。

回滚策略：调度器自动运行可被禁用，同时保留 P7 手动 TaskRun 路径、目标注册表和审核行为。
