## 1. OpenSpec 与执行边界

- [x] 1.1 创建 V2.1 Durable Run Engine OpenSpec，定义范围、非目标、验收和风险。
- [x] 1.2 审查当前 `BackgroundTasks` 执行入口、TaskRun 状态、adapter stream、interrupt、stale recovery。
- [x] 1.3 标记 V2.1 只处理 durable execution，不实现 Provider Gateway、显式 DB TargetLock、Policy Engine 或 rollback 事务。
- [x] 1.4 验证 `git diff --check` 和 `openspec validate agenthub-v2-1-durable-run-engine --strict`。

## 2. 执行服务边界抽取

- [x] 2.1 新增 `run_engine` / `run_supervisor` 模块骨架，将执行编排从 endpoint helper 中抽出。
- [x] 2.2 保留现有 BackgroundTasks 调用作为临时启动方式，先不改变外部行为。
- [x] 2.3 将 `agent_run_request_for`、adapter 执行、diff/review/preview/deploy 后处理划入清晰服务边界。
- [x] 2.4 添加回归测试证明手动 run、auto-start run、retry run 仍能进入同一执行服务。
- [x] 2.5 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [x] 2.6 单独提交：`refactor: extract durable run execution boundary`。

## 3. Worker Claim、Lease 与 Heartbeat

- [x] 3.1 实现 SQLite 兼容的 TaskRun claim helper，确保同一 queued run 只能被一个 worker 认领。
- [x] 3.2 实现 heartbeat loop，执行中周期刷新 `last_heartbeat_at` 和 `lease_expires_at`。
- [x] 3.3 记录 `run.claimed`、`run.heartbeat`、worker id、lease 过期时间等事件或 metrics。
- [x] 3.4 添加测试覆盖：单 worker claim、双 worker 竞争、heartbeat 延长 lease、terminal run 不再 heartbeat。
- [x] 3.5 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [x] 3.6 单独提交：`feat: add task run worker lease heartbeat`。

## 4. Durable Worker Loop 与 BackgroundTasks 替换

- [ ] 4.1 实现 RunWorker 轮询 queued run 并执行的最小 loop。
- [ ] 4.2 将 message auto-start、manual run、retry run 从直接 BackgroundTasks 执行改为 durable queue/worker 入口。
- [ ] 4.3 保证 `waiting_approval`、blocked scheduler、unsafe request 不会被 worker 执行。
- [ ] 4.4 保证 completed/failed/interrupted terminal run 不会重复执行。
- [ ] 4.5 添加测试覆盖 endpoint 创建 run 后进入 worker claim 路径，而非直接绑定请求生命周期。
- [ ] 4.6 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [ ] 4.7 单独提交：`feat: execute task runs through durable worker`。

## 5. RunSupervisor 中断与超时

- [ ] 5.1 实现 supervisor active run registry，关联 `task_run_id`、adapter run id、进程句柄或 adapter interrupt handle。
- [ ] 5.2 修改 interrupt 路径，使其记录 interrupt request 并调用 supervisor/adapter interrupt。
- [ ] 5.3 添加 terminate / kill escalation 和可审计事件。
- [ ] 5.4 添加 max runtime timeout 与 idle output timeout 包装。
- [ ] 5.5 确保 timeout 和 interrupt 不会被 artifact collector 或 adapter late event 覆盖为 completed。
- [ ] 5.6 添加测试覆盖 active interrupt、terminal interrupt 幂等、timeout failed、late completed ignored。
- [ ] 5.7 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [ ] 5.8 单独提交：`feat: supervise task run interrupt and timeout`。

## 6. 恢复扫描与 Stale Run 处理

- [ ] 6.1 在服务启动或 worker 启动时扫描 queued/active/waiting/terminal TaskRuns。
- [ ] 6.2 queued run 可重新 claim；waiting approval 不自动执行；terminal run 不重复执行。
- [ ] 6.3 active run lease 过期时记录 stale recovery 事件，并诚实失败化或进入受控 retry 状态。
- [ ] 6.4 与现有 `mark_stale_task_runs` / recovery helpers 兼容，不破坏 scheduler refresh。
- [ ] 6.5 添加测试覆盖服务重启后的 queued 恢复、active stale failed、approval 不执行、terminal 不重复。
- [ ] 6.6 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [ ] 6.7 单独提交：`feat: recover stale durable task runs`。

## 7. Artifact Collector 与 Finalizer 幂等

- [ ] 7.1 将 diff/review/preview/deploy 后处理收敛到 ArtifactCollector / Finalizer 边界。
- [ ] 7.2 确保 adapter failed/interrupted/timeout 时仍保留可用 worktree/diff 证据，但不伪造成成功。
- [ ] 7.3 确保 preview/deploy 失败记录 evidence，不覆盖编码 run 的真实失败原因。
- [ ] 7.4 确保 downstream auto-start 在恢复和重试时幂等，不重复启动同一任务链。
- [ ] 7.5 添加测试覆盖 artifact collector failure、preview failure、finalizer 重入、downstream 不重复。
- [ ] 7.6 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [ ] 7.7 单独提交：`feat: finalize durable runs with artifact evidence`。

## 8. Mission Trace、诊断证据与冻结审查

- [ ] 8.1 在 TaskRun metrics/evidence 或 MissionTrace 中暴露 worker id、claim、heartbeat、lease、interrupt、timeout、stale recovery、finalizer 结果。
- [ ] 8.2 确保证据不泄露 secrets、API key、受保护 host paths。
- [ ] 8.3 更新 `docs/change-log.md` 和 `docs/project-state.md`。
- [ ] 8.4 创建 `docs/v2-1-durable-run-engine-freeze-review.md`，记录实现范围、验证、真实限制和后续 V2.2/V2.3 依赖。
- [ ] 8.5 运行完整验证：`pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check`、`openspec validate agenthub-v2-1-durable-run-engine --strict`。
- [ ] 8.6 单独提交：`test: freeze v2.1 durable run engine`。
