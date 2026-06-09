## 为什么

AgentHub 已经具备真实规划器、运行时配置、Target Registry、工作区、
diff/review/preview/deploy 证据，以及 Claude Code / Codex 编码 Agent。
但当前任务执行仍主要通过 FastAPI `BackgroundTasks` 启动，这适合早期
demo，不适合真实开发任务。

当前执行链的主要风险是：

- 服务进程重启后，已经处于 `queued` / `starting` / `streaming` 的
  TaskRun 可能没有可靠恢复路径。
- `TaskRun` 已经有 lease / heartbeat 字段，但执行期间缺少统一的周期
  续租循环。
- interrupt API 主要更新数据库状态，尚未可靠连接到正在运行的
  Claude Code / Codex 子进程生命周期。
- adapter stream 没有统一的 max runtime / idle timeout 包装，真实 CLI
  卡住或长期无输出时用户只看到排队或执行中。
- 执行、diff 收集、review、preview、deploy、下游任务启动混在请求后
  后台函数里，失败恢复与幂等边界不清晰。

V2.1 的目标是先建立 AgentHub 的 Durable Run Engine：把任务执行从
请求生命周期里抽离出来，变成可排队、可认领、可续租、可中断、可超时、
可恢复、可审计的运行内核。后续 Provider Gateway、显式 Target Lock、
Policy Engine、事务化交付和诊断 UI 都应建立在这条稳定执行生命周期上。

## 变更内容

- 新增 Durable Run Engine 后端边界：
  - `TaskRunQueue`
  - `RunWorker`
  - `RunSupervisor`
  - `AdapterProcess`
  - `ArtifactCollector`
- 将任务执行生命周期建模为持久状态，而不是只依赖 FastAPI 请求后
  `BackgroundTasks`。
- 引入 worker claim / lease / heartbeat 语义：
  - queued run 可以被 worker 认领；
  - worker 定期刷新 heartbeat 和 lease；
  - stale run 在恢复扫描中被重新认领或诚实失败化。
- 建立真实 interrupt 设计：
  - interrupt 记录用户意图；
  - 如果子进程仍在运行，RunSupervisor 调用 adapter interrupt；
  - 必要时 terminate / kill；
  - 事件和最终状态必须可审计。
- 建立 max runtime 与 idle timeout 设计：
  - 每个 run 有最大运行时间；
  - adapter 长时间无输出时进入 timeout 处理；
  - timeout 不得被标记为成功。
- 收敛执行阶段：
  - preflight
  - claim
  - execute
  - collect artifacts
  - finalize
  - recover
- 保留现有 Scheduler、PlanValidator、Target Registry、worktree、diff、
  review、preview、deploy、runtime config、ClaudeCodeAdapter、CodexAdapter、
  ScriptedMockAdapter。
- 不在 V2.1 中实现 Provider Gateway、显式 DB TargetLock、完整 Policy
  Engine 或事务化 rollback；这些作为后续 V2 阶段。

## 能力

### 新能力

- `durable-run-engine`：定义持久化 TaskRun 执行队列、worker lease、
  heartbeat、supervisor 中断、超时、恢复扫描和执行证据要求。

### 修改后的能力

- `scheduler`：任务启动应进入 Durable Run Engine，而不是直接绑定请求
  生命周期。
- `task-run`：TaskRun 状态、heartbeat、lease、interrupt、stale recovery
  必须通过统一执行内核保持一致。
- `mission-trace`：任务追踪应能展示 worker、lease、interrupt、timeout、
  recovery 和最终化证据。

## 影响

- 预计影响 `apps/api/app/main.py`、`apps/api/app/task_runs.py`、
  `apps/api/app/adapters.py`、`apps/api/app/codex_adapter.py`、
  `apps/api/app/claude_code_adapter.py`、`apps/api/app/recovery.py`、
  `apps/api/app/scheduler.py`、`apps/api/app/mission_trace.py` 以及新增
  `run_engine` / `run_supervisor` 等模块。
- 需要新增针对 claim、heartbeat、stale recovery、interrupt、timeout、
  重启恢复、终态幂等和不伪造 provider 成功的测试。
- 需要更新 `docs/change-log.md` 和 `docs/project-state.md`。
- 不应修改 README 或无关 UI。

