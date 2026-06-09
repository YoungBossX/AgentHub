## ADDED Requirements

### Requirement: TaskRun 使用持久执行入口

系统 SHALL 通过 Durable Run Engine 执行 TaskRun，而不是依赖请求生命周期内的
FastAPI `BackgroundTasks` 作为唯一执行机制。

#### Scenario: 手动启动进入持久执行入口
- **WHEN** 用户手动为一个可执行 Task 创建 TaskRun
- **THEN** 系统 MUST 持久化 TaskRun
- **AND** TaskRun MUST 进入 Durable Run Engine 的 queued/claim 流程
- **AND** API 请求完成不应是该 TaskRun 能否继续执行的唯一条件

#### Scenario: 自动启动进入持久执行入口
- **WHEN** 编排器创建了安全且允许 auto-start 的 Task
- **THEN** 系统 MUST 创建持久 TaskRun
- **AND** TaskRun MUST 由 Durable Run Engine 执行
- **AND** 它 MUST 继续遵守 Scheduler、PlanValidator、Target Registry 和 Guardrails

#### Scenario: 重试进入持久执行入口
- **WHEN** 用户重试一个允许重试的 TaskRun
- **THEN** 系统 MUST 创建新的持久 TaskRun 记录
- **AND** 新 TaskRun MUST 通过 Durable Run Engine 执行
- **AND** 旧 TaskRun 的证据 MUST 保留

### Requirement: Worker Claim 与 Lease

系统 SHALL 使用 worker claim 和 lease 防止同一 TaskRun 被多个 worker 同时执行。

#### Scenario: 单 worker 认领 queued run
- **WHEN** TaskRun 处于 `queued`
- **AND** worker 尝试认领该 TaskRun
- **THEN** 系统 MUST 设置 worker id、claim time、heartbeat time 和 lease expiry
- **AND** 系统 MUST 记录认领证据

#### Scenario: 多个 worker 竞争同一 run
- **WHEN** 两个 worker 同时尝试认领同一个 queued TaskRun
- **THEN** 最多一个 worker MUST 成功
- **AND** 失败 worker MUST 不得启动 adapter 子进程

#### Scenario: terminal run 不可认领
- **WHEN** TaskRun 已处于 completed、failed、interrupted 或其他 terminal 状态
- **THEN** worker MUST NOT 认领或重新执行该 run

### Requirement: 执行中心跳续租

系统 SHALL 在 TaskRun 执行期间周期刷新 heartbeat 与 lease。

#### Scenario: 运行中的任务刷新 heartbeat
- **WHEN** TaskRun 正由 worker 执行
- **THEN** worker MUST 定期更新 `last_heartbeat_at`
- **AND** worker MUST 延长 `lease_expires_at`
- **AND** 系统 MUST 记录 heartbeat 证据或 metrics

#### Scenario: 任务结束后停止 heartbeat
- **WHEN** TaskRun 进入 terminal 状态
- **THEN** worker MUST 停止 heartbeat
- **AND** 后续 heartbeat MUST NOT 将 terminal run 重新变成 active

### Requirement: RunSupervisor 管理 Adapter 生命周期

系统 SHALL 使用 RunSupervisor 管理 Claude Code、Codex 和 fallback adapter 的运行生命周期。

#### Scenario: supervisor 注册运行中的 adapter
- **WHEN** worker 启动 adapter 执行 TaskRun
- **THEN** supervisor MUST 记录 TaskRun 与 adapter run/process 的关联
- **AND** 该关联 MUST 支持 interrupt、timeout 和 cleanup

#### Scenario: adapter 完成后 cleanup
- **WHEN** adapter 结束并且 TaskRun 被 finalizer 处理
- **THEN** supervisor MUST 清理 active registry
- **AND** 后续 interrupt MUST 幂等返回 terminal 状态而不是误杀新进程

### Requirement: Interrupt 真实终止运行

系统 SHALL 将用户 interrupt 请求连接到正在运行的 adapter，而不是仅更新数据库状态。

#### Scenario: 中断 active run
- **WHEN** 用户请求 interrupt 一个 active TaskRun
- **THEN** 系统 MUST 记录 interrupt requested 事件
- **AND** 如果 supervisor 持有 active adapter，则 MUST 调用 adapter interrupt
- **AND** 如果 adapter 未在 grace period 内退出，则 MUST 尝试 terminate 或 kill
- **AND** TaskRun MUST 最终进入 interrupted 或诚实失败状态

#### Scenario: 中断 terminal run 幂等
- **WHEN** 用户请求 interrupt 一个已经 terminal 的 TaskRun
- **THEN** 系统 MUST NOT 启动新进程
- **AND** 系统 MUST 返回当前 terminal 状态

#### Scenario: 无法确认进程时不声称已杀掉
- **WHEN** TaskRun 的 worker 已崩溃或 lease 已过期
- **AND** supervisor 无 active adapter 句柄
- **THEN** 系统 MUST 进入恢复或 stale 处理
- **AND** 系统 MUST NOT 声称已经成功终止真实 provider 进程

### Requirement: Timeout 防止卡死运行

系统 SHALL 对每个 TaskRun 执行 max runtime timeout 和 idle output timeout。

#### Scenario: 超过最大运行时间
- **WHEN** TaskRun 执行超过配置的 max runtime
- **THEN** supervisor MUST 中断 adapter
- **AND** TaskRun MUST 记录 timeout 事件
- **AND** TaskRun MUST NOT 被标记为 completed

#### Scenario: adapter 长时间无输出
- **WHEN** adapter 子进程仍在运行但超过 idle timeout 没有输出
- **THEN** supervisor MUST 中断 adapter 或将 run 标记为 timeout failure
- **AND** 系统 MUST 保留 stderr/stdout 中已收集的证据

#### Scenario: timeout 后迟到 completed 事件被忽略
- **WHEN** TaskRun 已因 timeout 进入 terminal failed 状态
- **AND** adapter 之后产生 completed 事件
- **THEN** 系统 MUST 不得将 TaskRun 改回 completed

### Requirement: 服务重启恢复

系统 SHALL 在服务或 worker 启动时扫描并恢复持久 TaskRun 状态。

#### Scenario: queued run 可恢复执行
- **WHEN** 服务重启后存在 `queued` TaskRun
- **THEN** worker MUST 能够认领并继续执行它

#### Scenario: waiting approval 不自动执行
- **WHEN** 服务重启后存在 `waiting_approval` TaskRun
- **THEN** worker MUST NOT 自动执行它
- **AND** 它 MUST 等待显式审批或拒绝

#### Scenario: active run lease 过期
- **WHEN** 服务重启后存在 active TaskRun
- **AND** 其 lease 已过期
- **THEN** 系统 MUST 记录 stale recovery 证据
- **AND** 系统 MUST 将其诚实失败化或进入受控 retry 状态
- **AND** 系统 MUST NOT 声称 provider 已成功完成

#### Scenario: terminal run 不重复执行
- **WHEN** 服务重启后存在 terminal TaskRun
- **THEN** worker MUST NOT 重新执行它

### Requirement: Artifact Finalizer 幂等

系统 SHALL 将 adapter 执行、artifact 收集和 terminal finalization 保持幂等。

#### Scenario: 成功运行收集证据
- **WHEN** adapter 成功完成 TaskRun
- **THEN** 系统 MUST 收集可用 diff/review/build/preview/deploy evidence
- **AND** 系统 MUST 记录 artifact collector 结果
- **AND** TaskRun completed MUST 只在执行和必要验证成功后写入

#### Scenario: 失败运行保留可用证据
- **WHEN** adapter failed、interrupted 或 timeout
- **THEN** 系统 SHOULD 保留可用 worktree/diff/log evidence
- **AND** 系统 MUST NOT 将失败伪装为成功

#### Scenario: finalizer 重入安全
- **WHEN** recovery 或 late event 重复调用 finalizer
- **THEN** terminal side effects MUST 保持幂等
- **AND** downstream task MUST NOT 被重复启动

### Requirement: MissionTrace 记录执行内核证据

系统 SHALL 在任务追踪或 TaskRun evidence 中暴露 Durable Run Engine 关键证据。

#### Scenario: 追踪显示 worker 与 lease
- **WHEN** 用户查看 mission trace 或 TaskRun 详情
- **THEN** 系统 SHOULD 暴露 worker id、claim time、last heartbeat、lease expiry 和 run phase

#### Scenario: 追踪显示中断和超时
- **WHEN** TaskRun 被 interrupted 或 timeout
- **THEN** 系统 SHOULD 暴露 interrupt requester、timeout reason、supervisor action 和 final state

#### Scenario: 证据不泄露敏感信息
- **WHEN** Durable Run Engine evidence 被写入日志、API 响应或 mission trace
- **THEN** 它 MUST NOT 包含 raw secrets、API keys、tokens 或受保护 host paths

### Requirement: V2.1 不绕过既有安全边界

系统 SHALL 保留 P6-P25 既有执行安全边界。

#### Scenario: PlanValidator 仍是任务创建前置条件
- **WHEN** Durable Run Engine 执行一个 TaskRun
- **THEN** 该 TaskRun MUST 来自已通过现有规划、验证和调度流程的 Task
- **AND** Durable Run Engine MUST NOT 绕过 PlanValidator

#### Scenario: Target Registry 仍限制路径与命令
- **WHEN** worker 执行 adapter
- **THEN** adapter 可见路径和命令 MUST 继续受 Target Registry、allowedPaths、deniedPaths 和 command policy 限制

#### Scenario: 不伪造真实 provider 成功
- **WHEN** Claude Code 或 Codex auth/quota/runtime/timeout 失败
- **THEN** 系统 MUST 记录真实错误
- **AND** 系统 MUST NOT 使用 ScriptedMock 或 fallback 声称真实 provider 成功
