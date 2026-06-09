## 总体设计

V2.3 将调度从“根据当前 active TaskRun 推导软锁”升级为“持久 Session Queue
+ 显式 DB Target Lock”。它承接 V2.1 Durable Run Engine 的 worker/lease
思路，但关注点是执行前的可运行判断和互斥边界。

目标架构：

```text
TaskRun created
  -> SessionQueue enqueue
  -> Scheduler readiness
  -> TargetLock acquire when write
  -> Durable Run Engine claim/execute
  -> TargetLock release
  -> Queue advance

Preview/Deploy requested
  -> PreviewDeployJobQueue
  -> Preview/Deploy worker
  -> evidence/event finalization
```

V2.3 仍保持本地单用户 demo 边界：SQLite、FastAPI、SSE、session worktree、
Target Registry、CodexAdapter、ClaudeCodeAdapter、ScriptedMockAdapter、
Vite React preview 和 mock deploy。

## 当前问题

当前调度可从 active TaskRun 推导出目标正在被写入，但该方式有几个缺口：

- 两个请求同时创建或 retry 写任务时，可能在彼此看到 active run 之前同时启动。
- 服务重启后，active run、锁定原因、等待队列和释放责任不够明确。
- 同 Session 的写任务串行规则没有一条持久 queue 作为事实来源。
- 同 Session 只读任务是否可并发缺少明确模型。
- 不同 Session 并发时，worktree 隔离和 target/project 写锁需要被同时检查。
- preview/deploy 与编码执行后处理混在一起，可能让排队、失败原因和诊断混乱。

V2.3 不要求一次性建设通用分布式队列；它要求把本地 SQLite demo 所需的互斥
和排队状态变成持久、原子、可审计。

## 数据模型建议

具体字段由实现阶段结合现有 SQLModel 决定，但语义应覆盖以下实体。

### SessionQueueEntry

用于描述一个 TaskRun 在 Session 内的调度位置。

建议字段：

- `id`
- `session_id`
- `task_id`
- `task_run_id`
- `queue_kind`：例如 `main`
- `access_mode`：`write` 或 `readonly`
- `target_id`
- `target_lock_key`
- `position`
- `state`：`queued`、`ready`、`waiting_dependency`、`waiting_lock`、
  `running`、`completed`、`failed`、`cancelled`
- `blocked_reason`
- `created_at`
- `started_at`
- `finished_at`

如果实现可用现有 TaskRun 字段承载一部分状态，也可以采用轻量表加事件模型。
但 queue position 和等待原因必须能通过 API 或 mission trace 查询。

### TargetLock

用于显式保护 target/project/worktree 写入。

建议字段：

- `id`
- `lock_key`
- `target_id`
- `project_id` 或等价目标归属字段
- `session_id`
- `task_run_id`
- `worker_id`
- `mode`：首版只要求 `write`
- `state`：`held`、`released`、`stale_released`
- `lease_expires_at`
- `acquired_at`
- `released_at`
- `release_reason`

SQLite 下不能假设 Postgres 行级锁。实现应使用唯一约束、事务、条件插入或
条件更新确保同一 active `lock_key` 同一时间最多只有一个写锁持有者。

### PreviewDeployJob

preview/deploy 不应阻塞主编码队列。它们进入独立 job queue。

建议字段：

- `id`
- `session_id`
- `source_task_run_id`
- `job_type`：`preview` 或 `deploy`
- `state`：`queued`、`running`、`completed`、`failed`、`cancelled`
- `attempt`
- `port` 或 deployment metadata
- `error_code`
- `evidence_json`
- `created_at`
- `started_at`
- `finished_at`

首版可只覆盖现有 Vite React preview 和 mock deploy，不扩展真实部署矩阵。

## Session Queue 规则

### 同 Session 写任务串行

同一 Session 内，`access_mode=write` 的主执行 TaskRun 必须按 queue position
串行执行。后一个写任务只有在前一个写任务 terminal、相关 finalizer 完成、
且所需 target lock 可获取时才能运行。

这条规则保护用户对同一会话工作树的连续修改，也让第二次“小改动”在第一轮
diff/review/preview 证据之后接续。

### 同 Session 只读任务可并发

只读任务可以在同 Session 中并发运行，但必须满足：

- 不需要写入 session worktree；
- 不需要 target write lock；
- 不依赖仍在运行或未 finalized 的写任务；
- 不会修改 artifacts、preview/deploy 状态之外的源代码结果；
- 遵守现有审批、命令和路径边界。

如果无法证明只读安全，调度器必须保守排队或等待。

### 不同 Session 可并发

不同 Session 可并发执行，只要满足：

- 每个 Session 使用自己的持久 worktree path；
- 不同 Session 不共享 worktree；
- 写任务能够获取目标对应的 DB Target Lock；
- 依赖、审批、Provider Gateway 和 Durable Run Engine 约束均满足。

如果两个 Session 写同一 target/project，它们必须竞争同一个 `lock_key`。

## Target Lock 规则

### 锁键

首版锁键应来自 Target Registry 的稳定标识。建议：

```text
target:<target_id>:write
```

如果后续 ProjectProfile 引入更细粒度 project/worktree 维度，可扩展为：

```text
project:<project_id>:target:<target_id>:write
```

V2.3 不要求复杂 path-range lock。路径级并发留给后续更细的 policy/profile。

### 获取

写任务启动前必须原子获取 TargetLock：

1. 检查 queue entry 已 ready；
2. 检查 TaskRun 未 terminal；
3. 检查 session worktree 已存在且属于该 Session；
4. 原子插入或更新 TargetLock；
5. 记录 `target_lock.acquired` 事件；
6. 才允许 Durable Run Engine 进入 adapter 执行。

如果获取失败，queue entry 进入 `waiting_lock`，TaskRun 不得启动 adapter。

### 释放

释放发生在 TaskRun terminal finalizer 中：

- completed；
- failed；
- interrupted；
- timed out；
- stale failed；
- cancelled。

释放必须幂等。重复 release 不得释放另一个 TaskRun 后来获取的锁。实现应校验
`lock_key`、`task_run_id`、`session_id` 和持有状态。

### Stale Lock 恢复

服务或 worker 启动时扫描：

- lock holder 的 TaskRun 已 terminal：释放 stale lock；
- lock lease 过期且 worker 心跳过期：记录 stale recovery 并释放或失败化；
- lock lease 未过期：保留；
- 无法确认真实 provider 结果：不得声称成功。

恢复事件应写入 TaskRunEvent 或等价 evidence。

## Preview/Deploy 独立队列

preview/deploy 作为独立 job queue：

- 编码 TaskRun 成功完成后可创建 preview/deploy job；
- preview/deploy job 排队不阻塞后续主编码写任务；
- preview/deploy 失败不把已成功的编码 TaskRun 改为失败；
- preview/deploy 成功或失败都必须有 evidence；
- 如果某个后续任务显式依赖 preview/deploy 成功，调度器可以等待对应 job。

首版 preview 仍只支持 Vite React：

```bash
pnpm dev --host 127.0.0.1 --port <port>
```

deploy 仍保持 mock-backed deploy card，不新增真实部署 provider。

## 事件与诊断

建议事件：

- `session_queue.enqueued`
- `session_queue.ready`
- `session_queue.waiting_dependency`
- `session_queue.waiting_lock`
- `session_queue.running`
- `session_queue.advanced`
- `target_lock.acquire_attempt`
- `target_lock.acquired`
- `target_lock.acquire_failed`
- `target_lock.released`
- `target_lock.stale_released`
- `preview_job.queued`
- `preview_job.running`
- `preview_job.completed`
- `preview_job.failed`
- `deploy_job.queued`
- `deploy_job.running`
- `deploy_job.completed`
- `deploy_job.failed`

Mission trace 或 TaskRun evidence 应能显示：

- queue position；
- access mode；
- target id；
- lock key；
- lock holder；
- wait reason；
- lease expiry；
- release reason；
- preview/deploy job 状态。

不得暴露 secrets、API keys、tokens、受保护 host paths 或未分配给当前
Session 的 host 路径。

## 与现有能力关系

- Durable Run Engine：V2.3 在 worker claim 前增加 queue/lock gates。
- Provider Gateway：如果 V2.2 已实现 provider 并发和 circuit breaker，V2.3
  的 queue/lock 判断应先于真实 provider 启动；provider 失败不得释放错误锁。
- Scheduler：scheduler readiness 应读取持久 queue/lock 状态，不再只依赖
  active TaskRun 推导。
- Artifact Finalizer：释放锁和推进 queue 应在 terminal finalizer 中幂等完成。
- Preview/Deploy：从编码 run finalizer 中创建独立 job，而不是把 preview/deploy
  作为主队列的阻塞步骤。

## 风险与权衡

- **SQLite 并发有限。** 需要条件写入和唯一约束，不能依赖行级锁语义。
- **过度串行会降低并发。** 首版优先正确性：同 Session 写串行，同 target 写
  串行；只读并发必须可证明安全。
- **锁释放错误风险高。** release 必须校验 holder 身份，防止释放后来者的锁。
- **preview/deploy 拆队列会改变诊断路径。** 需要清楚区分编码 TaskRun 状态与
  preview/deploy job 状态。
- **多个线程同时开发。** 实现阶段应拆分新模块、测试和文档，避免同时修改
  hot files；本 OpenSpec 不触碰实现文件。

## 迁移计划

1. 新增持久 queue/lock/job 的模型或等价存储边界。
2. 在 scheduler readiness 中引入 queue position 和 access mode。
3. 在 TaskRun claim 前加入 TargetLock acquire。
4. 在 terminal finalizer 中幂等释放 TargetLock 并推进 Session Queue。
5. 将 preview/deploy 创建改为独立 job queue。
6. 加入 recovery scan，释放 stale lock 并恢复 queued/waiting 状态。
7. 在 mission trace/API 中暴露 queue/lock/job 诊断。
8. 完成并发、retry、interrupt、stale、preview/deploy 队列测试。

回滚策略：保留现有手动执行路径，但禁用自动并发启动；若 queue/lock 初始化
失败，系统应保守拒绝启动写任务，而不是绕过锁。
