# V2.3 会话队列与目标锁冻结审查

**日期：** 2026-06-09

## 范围

V2.3 将调度从推断的活动运行软锁升级为持久化队列与锁证据。

已实现：

- `SessionQueueEntry` 模型与队列辅助函数。
- `TargetLock` 模型及兼容 SQLite 的 acquire/release 辅助函数。
- `PreviewDeployJob` 模型与 preview/deploy 任务证据辅助函数。
- TaskRun 创建与终态转换现维护 queue/lock 状态。
- 持久化运行引擎在启动适配器前检查队列与目标锁。
- 调度器就绪状态读取持久化的 queue/lock 状态。
- 过期队列与锁恢复记录证据，且在无法确认提供者结果时绝不声称提供者成功。
- MissionTrace 与 TaskRun 响应包含队列、锁及 preview/deploy 任务诊断信息。

## 安全性

- 同会话写入运行已序列化。
- 跨会话对同一目标的写入竞争同一数据库目标锁。
- 等待审批、阻塞依赖、不安全路径及终态运行不会绕过 queue/lock 门控。
- Preview/deploy 任务单独记录证据，不会覆盖编码运行的终态。

## 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_session_queue.py tests/test_target_locks.py tests/test_scheduler.py tests/test_task_runs.py -q` | 通过 |
| `pnpm test` | 通过 |
| `pnpm check` | 通过 |
| `pnpm demo:api:test` | 通过 |
| `openspec validate agenthub-v2-3-session-queue-target-lock --strict` | 通过 |
| `git diff --check` | 通过 |

## 限制

- 队列与锁状态仍为 SQLite/local-demo 作用域。
- 此阶段中 Preview/deploy 任务执行在终结阶段仍为同步，但证据现已表示为独立任务记录。
- 细粒度路径范围锁已推迟。
- 更广泛的策略审批、回滚及 ProjectProfile 行为将留待后续可靠性 V2 阶段处理。

## 后续工作

建议后续工作：完成 V2.7 UI，使 queue/lock/provider 诊断信息在任务卡片与任务面板中可见。
