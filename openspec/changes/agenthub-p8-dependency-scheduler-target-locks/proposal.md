## 为什么

P6 验证了一个有界全栈迷你 CRM 垂直切片，P7 使执行具备目标感知能力，但 AgentHub 仍然没有成熟的调度器来处理依赖顺序、目标写入锁、自动流水线推进或下游阻塞状态。因此需要 P8，以便 Manager / PMO Agent 能够安全地协调多智能体执行，而不仅仅是创建任务图。

## 变更内容

- 添加一个依赖感知调度器，在启动任务运行前评估 `dependsOn`。
- 添加目标写入锁，使同一目标写入任务不会并发执行。
- 为有界全栈应用流程添加自动流水线推进：
  合约 -> 后端 -> 前端 -> Review/QA -> 预览 -> 模拟部署。
- 为依赖等待、目标锁等待、上游失败、重试可用性和兜底可用性添加阻塞和等待状态。
- 在现有任务时间线/执行跟踪 UI 中展示调度器状态。
- 针对 P6/P7 迷你 CRM 路径演练 P8，并验证目标锁、下游阻塞行为、预览和模拟部署。

P8 保留了 P6 全栈迷你 CRM 能力和 P7 目标注册表。
它不添加分布式工作节点、多用户即时通讯、外部即时通讯集成、
生产环境部署、Docker 沙箱、提供商市场、PR 创建或
任意 SaaS 生成。

## 能力

### 新能力

- `scheduler`：依赖感知的任务调度、目标写入锁、
  自动有界流水线推进、blocked/fallback状态处理，以及
  调度器 UI 追踪。

### 修改后的能力

P8 引入了调度器能力，同时保留了 P4/P5/P6/P7 基线。

## 影响

OpenSpec 制品：

- `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/proposal.md`
- `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/design.md`
- `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/tasks.md`
- `openspec/changes/agenthub-p8-dependency-scheduler-target-locks/specs/scheduler/spec.md`

P8 后续应用时的预期实现影响：

- 后端：
  - 调度服务或模块；
  - 任务图的依赖就绪评估；
  - 使用 P7 目标 ID 进行目标锁的获取/释放；
  - 现有 `TaskRunEvent` / 任务状态界面中的调度事件；
  - 使用现有 API 自动推进至审查、预览和模拟部署；
  - 下游任务的 blocked/failure 传播。
- 前端：
  - 任务卡片、时间线和执行轨迹中的调度状态；
  - 为依赖等待、目标锁等待、阻塞、可重试、有兜底可用、运行中和已完成状态提供清晰标签。
- 数据模型：
  - P8 可从现有 `Task`、`TaskRun` 和 `TaskRunEvent` 字段开始，若足够则加上 plan/context 元数据；
  - 仅当持久化调度状态或锁需要时，才允许添加持久化字段。
- 运行时：
  - 同一会话中的写入任务仍按目标锁串行执行；
  - 普通后端任务仍限定于 `demo-backend`；
  - `agenthub-platform` 执行仍受审批控制；
  - 模拟部署仍明确标记为模拟。
