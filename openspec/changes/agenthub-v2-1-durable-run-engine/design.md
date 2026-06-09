## 总体设计

V2.1 将 AgentHub 的执行链从 “endpoint 创建 TaskRun 后丢给
FastAPI BackgroundTasks” 改造成 “endpoint 创建/排队 TaskRun，Durable
Run Engine 认领并执行”。

目标不是一次性替换所有平台能力，而是建立一个稳定的执行内核边界：

```text
TaskRunQueue
  -> RunWorker
  -> RunSupervisor
  -> AdapterProcess
  -> ArtifactCollector
  -> Finalizer
```

V2.1 仍复用现有：

- PlanValidator
- Scheduler readiness
- Target Registry
- session worktree
- ClaudeCodeAdapter / CodexAdapter / ScriptedMockAdapter
- diff/review/preview/deploy evidence
- MissionTrace

V2.1 不实现 Provider Gateway、显式 DB TargetLock、完整 Policy Engine、
rollback 事务或新的 provider marketplace。

## 当前路径问题

当前路径大致为：

```text
create_message / run endpoint
  -> create_task_run
  -> background_tasks.add_task(...)
  -> execute_task_run
  -> run_adapter_event_stream
  -> collect diff / review / preview / deploy
  -> maybe start downstream task
```

问题：

- `BackgroundTasks` 是进程内请求后执行，不 durable。
- active run 的进程句柄不归统一 supervisor 管理。
- interrupt API 难以触达正在运行的 adapter 子进程。
- heartbeat 字段存在，但缺少执行期周期续租。
- adapter stream 卡住时缺少统一 idle timeout。
- terminal side effects 分散，恢复时难以做到幂等。

## 核心组件

### TaskRunQueue

V2.1 可以先复用 `TaskRun.state=queued` 作为最小持久队列，不强制新增独立
queue 表。若实现需要，可引入轻量 queue service，但不应在 V2.1 中扩大到
完整多队列调度。

职责：

- 接受已通过 PlanValidator/Scheduler 的 TaskRun。
- 保留 queued 状态直到 worker claim。
- 支持按 session/task 创建时间选择可执行 run。
- 不绕过现有 scheduler readiness。

### RunWorker

RunWorker 是执行循环，负责：

- 查找可认领的 queued/stale-eligible TaskRun。
- 以 worker id 认领 run。
- 设置 `runner_id`、`started_at`、`last_heartbeat_at`、`lease_expires_at`。
- 启动 heartbeat loop。
- 调用 RunSupervisor 执行 adapter。
- 调用 ArtifactCollector 收集 diff/review/preview/deploy。
- 调用 Finalizer 写入 terminal 状态和 scheduler refresh。

SQLite 下不依赖 Postgres `SELECT FOR UPDATE`。实现应使用 SQLite 可用的
条件更新或事务检查，确保同一 TaskRun 不被多个 worker 同时认领。

### RunSupervisor

RunSupervisor 统一管理当前进程内正在运行的 adapter：

- 注册 `task_run_id -> adapter_run_id/process handle`。
- 记录 start time、last output time、max runtime deadline。
- 支持 interrupt：
  - 首先调用 adapter `interrupt(adapter_run_id)`；
  - 未退出时 terminate；
  - 仍未退出时 kill；
  - 每一步写 TaskRunEvent。
- 支持 timeout：
  - max runtime timeout；
  - idle output timeout；
  - timeout 后不得继续标记 completed。

### AdapterProcess

V2.1 不要求重写 Claude/Codex adapter，但要在执行层包装：

- stdout/stderr streaming 事件；
- last output timestamp；
- interrupt/terminate/kill 行为；
- adapter error normalization 的最小字段。

详细 provider 熔断和 fallback 留给 V2.2 Provider Gateway。

### ArtifactCollector

ArtifactCollector 保留现有 diff/review/preview/deploy 逻辑，但将边界从
endpoint helper 抽到执行内核后处理阶段。

要求：

- adapter failed/interrupted/timeout 时仍尽量保留可用 worktree/diff 证据。
- diff 收集失败不得伪造成任务成功。
- preview/deploy 失败应记录 evidence，不应覆盖编码 run 的真实失败原因。
- 自动下游任务启动必须幂等，避免恢复时重复启动。

### Finalizer

Finalizer 负责 terminal 状态统一化：

- completed
- failed
- interrupted
- timed_out
- stale_failed
- waiting_approval

它应统一执行：

- TaskRunEvent 写入；
- TaskRun terminal fields；
- lease release；
- scheduler refresh；
- mission trace evidence；
- downstream task readiness；
- idempotency guard。

## 状态与事件

V2.1 应继续兼容现有 TaskRun 状态，同时补充明确事件：

- `run.claimed`
- `run.heartbeat`
- `run.supervisor_started`
- `run.interrupt_requested`
- `run.interrupt_sent`
- `run.terminated`
- `run.killed`
- `run.timeout`
- `run.stale_recovered`
- `run.finalized`

如果模型不新增状态枚举，timeout 可以表现为 `failed` + `errorCode=TASK_RUN_TIMEOUT`；
interrupt 表现为 `interrupted`；stale 表现为 `failed` +
`errorCode=TASK_RUN_STALE`。

## 恢复策略

服务启动或 worker 启动时扫描：

- `queued`：可重新 claim。
- `starting` / `streaming` / `applying_changes` 等 active 状态：
  - lease 未过期：保持等待；
  - lease 过期：标记 stale 或重新认领，取决于实现是否能确认进程仍存在。
- `waiting_approval`：不自动执行。
- terminal 状态：不重复执行。

在 V2.1 中，跨进程精确恢复正在运行的子进程不是硬目标；若服务重启后无法
确认子进程归属，应诚实 stale failed，不得声称成功。

## Interrupt 设计

interrupt 不再只是 DB 状态更新。流程：

```text
POST /task-runs/{id}/interrupt
  -> record interrupt requested
  -> if supervisor owns active process:
       adapter.interrupt
       terminate after grace period
       kill after hard grace period
  -> finalize interrupted
```

如果 run 已 terminal，interrupt 应幂等返回当前状态。

如果 run 由已崩溃 worker 拥有且 lease 过期，interrupt 应转为 stale/recovery
处理，不应显示“已成功杀掉进程”。

## Timeout 设计

每个 run 应支持：

- `maxRuntimeSeconds`
- `idleTimeoutSeconds`
- `heartbeatIntervalSeconds`
- `leaseSeconds`

初始默认可以保守，例如：

- heartbeat 10-20 秒；
- lease 60-120 秒；
- idle timeout 5-10 分钟；
- max runtime 20-30 分钟。

具体默认值由实现结合现有测试决定，但必须可测试、可配置、可记录。

## 证据与诊断

TaskRun evidence / metrics / mission trace 应记录：

- worker id；
- claim time；
- heartbeat count 或 last heartbeat；
- lease expiry；
- supervisor status；
- interrupt requested by user/system；
- timeout reason；
- stale recovery reason；
- finalizer result；
- artifact collector result。

不得记录 secrets、原始 API key、受保护 host paths。

## 并行开发边界

V2.1 实现建议按顺序：

1. 抽出执行服务边界，但暂时保留 BackgroundTasks 调用。
2. 加入 claim / heartbeat / lease helper 与测试。
3. 加入 worker loop，endpoint 不再直接执行。
4. 接入 supervisor interrupt / timeout。
5. 接入 startup recovery scan。
6. 补全 mission trace / freeze review。

不要在第一步同时实现 Provider Gateway、显式 TargetLock、ProjectProfile、
Policy Engine 或前端大改。

## 风险

- `main.py` 当前承担大量职责，重构时容易引入行为回归。
- SQLite 并发有限，claim 逻辑必须避免假设 Postgres 行级锁。
- 子进程 interrupt 需要与 Claude/Codex adapter 现有实现兼容。
- preview/deploy 后处理可能失败，不能让其污染编码 run 的真实状态。
- 当前工作区已有未提交改动，实施时必须避免覆盖用户或其他任务改动。

