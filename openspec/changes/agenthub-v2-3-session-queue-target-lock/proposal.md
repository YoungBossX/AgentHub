## 为什么

AgentHub Reliability v2 已经把执行内核方向定为 durable、可恢复、可中断、
可诊断。V2.1 解决 TaskRun 从请求生命周期中抽离的问题，V2.2 规划 Provider
Gateway；但当前调度与互斥仍主要依赖“从 active TaskRun 推导软锁”的方式。
这种方式在并发点击、retry、服务重启、多个 session 同时操作同一 target 时
不够可靠。

V2.3 的目标是将调度升级为显式持久模型：

- 每个 Session 有可审计的执行队列；
- 同 Session 写任务串行；
- 同 Session 只读任务在安全时可并发；
- 不同 Session 在 worktree 与 target lock 允许时可并发；
- 同 target/project 的写任务必须通过数据库原子锁保护；
- preview/deploy 作为独立 job 队列执行，不阻塞主编码执行队列。

这不是要引入分布式任务平台，而是在当前本地单用户、SQLite、session
worktree、Target Registry 和现有 adapter 边界内，把“能否启动”的判断从
临时推导变为可恢复、可解释、可测试的持久调度状态。

## 变更内容

- 新增持久 Session Queue 设计：
  - 将可执行 TaskRun 排入 session-scoped queue；
  - 记录 queue position、ready/blocked/waiting_lock/running/terminal 状态；
  - 同 Session 写任务必须按队列顺序串行；
  - 同 Session 只读任务仅在不依赖未完成写入且不需要写锁时可并发。
- 新增显式 DB Target Lock 设计：
  - 以 target/project/worktree 相关锁键保护写任务；
  - acquire/release 必须在数据库事务或 SQLite 兼容条件更新中原子完成；
  - 锁归属、TaskRun、Session、worker、lease、原因和释放结果必须可审计；
  - stale lock 由恢复扫描释放或转为诚实失败状态。
- 明确跨 Session 并发规则：
  - 不同 Session 可并发执行；
  - 但同 target/project 写任务必须竞争同一 DB Target Lock；
  - 每个 Session 仍必须使用独立 session worktree；
  - 不得让两个 Session 共享同一 worktree。
- 将 preview/deploy 从主执行链中拆成独立 job queue：
  - preview/deploy job 使用自己的队列、状态和事件；
  - 失败只记录 preview/deploy evidence，不覆盖编码 TaskRun 的真实状态；
  - 不能因 preview/deploy 排队阻塞后续编码写任务，除非存在显式依赖。
- 为 queue/lock 状态提供后端可观测性：
  - queue position；
  - lock key；
  - lock holder；
  - wait reason；
  - stale recovery；
  - release evidence。
- 保留现有 P0/P5/P6-P25 demo 边界：
  - SQLite；
  - SSE；
  - Target Registry；
  - session-level worktree；
  - CodexAdapter、ClaudeCodeAdapter、ScriptedMockAdapter；
  - Vite React preview；
  - mock-backed deploy card。

## 能力

### 新能力

- `session-queue-target-lock`：定义持久 Session Queue、显式 DB Target Lock、
  session/write/read 并发规则、preview/deploy 独立 job queue，以及恢复和诊断
  要求。

### 修改后的能力

- `durable-run-engine`：worker 在 claim 执行前必须通过 Session Queue 与
  Target Lock 判断。
- `scheduler`：从 active TaskRun 推导软锁升级为读取持久 queue/lock 状态。
- `preview-deploy`：preview/deploy 进入独立 job queue，不再作为主执行队列的
  阻塞性后处理。
- `mission-trace`：展示 queue、lock、wait、release 与 stale recovery 证据。

## 影响

- 预计后续实现会新增 session queue / target lock / preview deploy job
  相关模型、服务、测试和恢复逻辑。
- 预计会影响 TaskRun claim、scheduler readiness、recovery scan、artifact
  finalizer、preview/deploy 创建路径和 mission trace 证据。
- 本 OpenSpec 只创建文档，不实现代码、不修改前端、不修改 adapter。
- 后续实现必须更新 `docs/change-log.md`，并在碰到持久化行为时验证数据库
  初始化和迁移/兼容路径。

## 非目标

- 不引入 Docker sandbox。
- 不引入 WebSocket。
- 不引入多用户协作、外部 IM、RBAC、billing 或多租户管理。
- 不引入 PR 创建、真实生产部署或 provider marketplace。
- 不新增 adapter。
- 不改变 demo app 仍为 Vite React 的边界。
- 不要求 Postgres、Redis 或分布式 worker 集群。
