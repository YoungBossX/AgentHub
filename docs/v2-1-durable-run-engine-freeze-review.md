# V2.1 持久化运行引擎冻结评审

**日期：** 2026-06-09

## 范围

V2.1 重构了 TaskRun 执行边界，但未替换现有的 ClaudeCodeAdapter、CodexAdapter、Scheduler、Target Registry、PlanValidator、diff/review/preview/deploy 证据或 ScriptedMock 兜底。

已实现：

- `run_engine.py` 执行边界。
- `run_supervisor.py` 活跃运行注册表。
- 共享运行调度辅助函数。
- Worker 认领 / 租约 / 心跳。
- 基于队列 TaskRun 的持久化 Worker `run_once`。
- 活跃运行监督器注册。
- 来自 `run_adapter_event_stream` 的适配器运行 ID 回调。
- 中断路径：在数据库状态转换前尝试监督器适配器中断。
- 最大运行超时失败路径。
- 使用现有陈旧 TaskRun 恢复机制的 startup/stale 恢复辅助函数。
- 针对 diff/review/ledger/preview/deploy 和下游自动启动的已完成运行终结器边界。
- 任务追踪持久化运行证据。

## 验证

| 命令 | 结果 |
|---|---|
| `cd apps/api && ../../.venv/bin/python -m pytest tests/test_task_runs.py -q` | 通过 |
| `pnpm check` | 通过 |
| `pnpm demo:api:test` | 通过 |
| `openspec validate agenthub-v2-1-durable-run-engine --strict` | 通过 |
| `git diff --check` | 通过 |

## 证据

TaskRun 和任务追踪现在暴露：

- `runnerId`
- `adapterRunId`
- `startedAt`
- `endedAt`
- `lastHeartbeatAt`
- `leaseExpiresAt`
- `staleDetectedAt`
- `staleReason`
- 提供者分配和运行时配置证据已存在于指标中

## 限制

- V2.1 仍使用进程内 FastAPI 后台任务作为 Worker 唤醒机制。工作本身现在通过 `RunWorker` 路由，但独立的长期运行 Worker 进程被推迟。
- SQLite 认领仍是最小实现，将在 V2.3 中通过显式 queue/target 锁工作得到加强。
- 提供者速率限制、断路器、兜底策略和提供者健康对齐推迟到 V2.2。
- 细粒度空闲 stdout 超时推迟到 provider/process 网关层，因为当前适配器在内部流式传输 stdout。
- 事务性 rollback/accept 流程推迟到 V2.6。

## 后续

推荐的下一实现阶段：V2.2 提供者网关，然后是 V2.3 会话队列和目标锁。
