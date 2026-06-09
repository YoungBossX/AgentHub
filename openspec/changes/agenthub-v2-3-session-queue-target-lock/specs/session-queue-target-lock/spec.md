## ADDED Requirements

### Requirement: 持久 Session Queue

系统 SHALL 为每个 Session 的主执行 TaskRun 维护持久 Session Queue，用于表示
队列顺序、可运行状态、等待原因和执行结果。

#### Scenario: TaskRun 创建时进入 Session Queue

- **WHEN** 系统为 Session 创建一个主执行 TaskRun
- **THEN** 系统 MUST 创建或更新对应的 Session Queue entry
- **AND** queue entry MUST 记录 session、task、task run、access mode、target id 和 queue position
- **AND** queue entry MUST 可在服务重启后恢复读取

#### Scenario: 队列位置可见

- **WHEN** 用户查看 TaskRun、任务追踪或等价诊断信息
- **THEN** 系统 SHOULD 暴露该 TaskRun 的 queue position
- **AND** 系统 SHOULD 暴露等待原因，例如依赖等待、目标锁等待或审批等待

#### Scenario: Terminal run 不重新入队执行

- **WHEN** TaskRun 已处于 completed、failed、interrupted、cancelled 或其他 terminal 状态
- **THEN** Session Queue MUST NOT 将该 TaskRun 重新变为 runnable
- **AND** worker MUST NOT 因 queue recovery 重复执行它

### Requirement: 同 Session 写任务串行

系统 SHALL 保证同一 Session 内的写任务按 Session Queue 顺序串行执行。

#### Scenario: 同 Session 已有写任务运行

- **WHEN** 一个 Session 中已有 `access_mode=write` 的 TaskRun 正在运行或 finalizing
- **AND** 同一 Session 的另一个写 TaskRun 已排队
- **THEN** 系统 MUST NOT 启动第二个写 TaskRun
- **AND** 第二个写 TaskRun MUST 保持 queued 或 waiting 状态
- **AND** 等待原因 MUST 可诊断

#### Scenario: 前一个写任务完成后推进队列

- **WHEN** 同 Session 的当前写 TaskRun 进入 terminal 状态
- **AND** 相关 finalizer 已完成必要的 queue 和 lock 释放步骤
- **THEN** 系统 MUST 重新评估同 Session 后续 queue entries
- **AND** 下一个满足依赖、审批和 target lock 条件的写 TaskRun MAY 变为 runnable

#### Scenario: 写任务 retry 不绕过队列

- **WHEN** 用户 retry 一个失败或中断的写 TaskRun
- **THEN** 系统 MUST 为 retry 创建新的可追踪 TaskRun 或等价运行历史
- **AND** retry MUST 进入同一 Session Queue
- **AND** retry MUST NOT 绕过当前排在前面的写任务

### Requirement: 同 Session 只读任务安全并发

系统 SHALL 允许同一 Session 中安全的只读任务并发执行，但不得让只读任务修改
session worktree 或绕过依赖边界。

#### Scenario: 只读任务依赖已满足

- **WHEN** 一个 `access_mode=readonly` 的 TaskRun 依赖已完成
- **AND** 该 TaskRun 不需要写入 session worktree
- **AND** 该 TaskRun 不需要 target write lock
- **THEN** 系统 MAY 与同 Session 的其他只读 TaskRun 并发执行它

#### Scenario: 只读任务依赖运行中的写任务

- **WHEN** 一个 readonly TaskRun 依赖同 Session 中仍在运行或未 finalized 的写 TaskRun
- **THEN** 系统 MUST NOT 启动该 readonly TaskRun
- **AND** 它 MUST 等待依赖写任务完成并完成必要 finalization

#### Scenario: 无法证明只读安全

- **WHEN** 调度器无法证明某个任务不会修改 worktree、源代码、diff 或主执行结果
- **THEN** 系统 MUST 将该任务按写任务或保守等待处理
- **AND** 系统 MUST NOT 因标记不清而并发执行它

### Requirement: 不同 Session 在锁允许时并发

系统 SHALL 允许不同 Session 的任务在 worktree 隔离和 target lock 允许时并发。

#### Scenario: 不同 Session 写入不同 target

- **WHEN** 两个不同 Session 各自拥有独立 session worktree
- **AND** 它们的写 TaskRun 面向不同 target lock key
- **AND** 依赖、审批、provider 和命令策略均允许执行
- **THEN** 系统 MAY 并发执行这两个写 TaskRun

#### Scenario: 不同 Session 不得共享 worktree

- **WHEN** 系统准备启动一个 Session 的 TaskRun
- **THEN** 系统 MUST 验证该 Session 使用自己的持久 worktree path
- **AND** 不同 Session MUST NOT 共享同一个 worktree path

#### Scenario: 不同 Session 写入同一 target

- **WHEN** 两个不同 Session 的写 TaskRun 面向同一 target lock key
- **THEN** 最多一个 TaskRun MUST 持有该 target write lock
- **AND** 未获得锁的 TaskRun MUST NOT 启动 adapter
- **AND** 未获得锁的 TaskRun MUST 暴露 waiting lock 状态或等价诊断

### Requirement: 显式 DB Target Lock

系统 SHALL 使用显式持久 DB Target Lock 保护同 target/project 的写任务，而不是
只从 active TaskRun 推导软锁。

#### Scenario: 写任务原子获取 target lock

- **WHEN** 写 TaskRun 准备进入 adapter 执行
- **THEN** 系统 MUST 在数据库中原子获取 target write lock
- **AND** lock MUST 记录 lock key、target id、session id、task run id、worker id 或等价 holder 信息
- **AND** adapter MUST NOT 在 lock 获取成功前启动

#### Scenario: 并发获取同一 lock

- **WHEN** 两个写 TaskRun 并发尝试获取同一个 target write lock
- **THEN** 最多一个获取 MUST 成功
- **AND** 失败的一方 MUST 不启动 adapter
- **AND** 失败的一方 MUST 记录 lock wait 或 acquire failed evidence

#### Scenario: 获取 lock 后记录事件

- **WHEN** target write lock 获取成功
- **THEN** 系统 MUST 记录可审计事件或 evidence
- **AND** evidence SHOULD 包含 lock key、holder task run、session 和 lease expiry

### Requirement: Target Lock 幂等释放

系统 SHALL 在写 TaskRun 进入 terminal finalization 时幂等释放其持有的 Target Lock。

#### Scenario: Completed run 释放 lock

- **WHEN** 持有 target write lock 的 TaskRun completed
- **THEN** finalizer MUST 释放该 TaskRun 持有的 lock
- **AND** 系统 MUST 记录 release evidence
- **AND** Session Queue MUST 重新评估后续等待项

#### Scenario: Failed interrupted timeout run 释放 lock

- **WHEN** 持有 target write lock 的 TaskRun failed、interrupted、timed out、cancelled 或 stale failed
- **THEN** finalizer MUST 释放该 TaskRun 持有的 lock
- **AND** 系统 MUST NOT 因释放 lock 而把该 TaskRun 标记为 completed

#### Scenario: 重复 release 不释放后来者

- **WHEN** release 逻辑被重复调用
- **AND** 同一 lock key 已被另一个 TaskRun 后来获取
- **THEN** 系统 MUST NOT 释放后来者的 lock
- **AND** release MUST 校验原 holder 的 task run id、session id 和 lock state

### Requirement: Stale Lock 恢复

系统 SHALL 在服务或 worker 启动恢复时扫描并处理 stale queue entries 和 stale
Target Locks。

#### Scenario: Terminal holder 的 lock 被恢复释放

- **WHEN** recovery scan 发现 held lock 的 holder TaskRun 已 terminal
- **THEN** 系统 MUST 将该 lock 作为 stale lock 释放
- **AND** 系统 MUST 记录 stale release evidence

#### Scenario: Lease 过期且 worker 心跳过期

- **WHEN** held lock 的 lease 已过期
- **AND** holder worker heartbeat 已过期或不可确认
- **THEN** 系统 MUST 执行 stale recovery
- **AND** 系统 MUST 释放 lock 或将 holder run 诚实失败化后释放 lock
- **AND** 系统 MUST NOT 声称真实 provider 已成功完成

#### Scenario: Lease 未过期

- **WHEN** recovery scan 发现 held lock 的 lease 未过期
- **THEN** 系统 MUST NOT 抢占释放该 lock
- **AND** 等待该 lock 的 queue entries MUST 继续保持 waiting lock 或等价状态

### Requirement: Preview Deploy 独立 Job Queue

系统 SHALL 将 preview 和 deploy 建模为独立 job queue，而不是阻塞主编码执行队列。

#### Scenario: 编码成功后创建 preview job

- **WHEN** 编码 TaskRun completed
- **AND** 当前流程需要预览
- **THEN** 系统 MUST 创建 preview job 或等价持久 job record
- **AND** preview job MUST 有独立状态、attempt、evidence 和错误信息
- **AND** 主 Session Queue 的后续编码写任务 MUST NOT 仅因 preview job queued 而被阻塞，除非存在显式依赖

#### Scenario: Preview job 失败

- **WHEN** preview job failed
- **THEN** 系统 MUST 记录 preview failure evidence
- **AND** 系统 MUST NOT 将已经 completed 的编码 TaskRun 改为 failed
- **AND** 用户或诊断界面 SHOULD 能区分编码成功与 preview 失败

#### Scenario: Deploy job 保持 mock-backed

- **WHEN** 当前 demo 流程创建 deploy job
- **THEN** deploy job MUST 保持 mock-backed deploy card 语义
- **AND** 系统 MUST NOT 声称完成真实生产部署

#### Scenario: 显式依赖 preview deploy

- **WHEN** 后续任务显式依赖 preview 或 deploy job 成功
- **THEN** scheduler MUST 等待对应 job terminal success
- **AND** job failed MUST 阻塞该显式依赖任务或暴露 retryable 状态

### Requirement: Queue Lock 诊断可见

系统 SHALL 在 TaskRun evidence、TaskRunEvent、MissionTrace 或等价 API 中暴露
Session Queue 和 Target Lock 的关键诊断信息。

#### Scenario: 等待 target lock 可解释

- **WHEN** TaskRun 因 target lock 不可用而等待
- **THEN** 系统 SHOULD 暴露 lock key、target id、当前 holder task run 或等价摘要
- **AND** 系统 SHOULD 暴露该 TaskRun 的 queue position 或等待顺序

#### Scenario: Queue 推进可审计

- **WHEN** Session Queue 从一个 TaskRun 推进到后续 TaskRun
- **THEN** 系统 SHOULD 记录 queue advance evidence
- **AND** evidence SHOULD 标识完成的 run、后续候选 run 和阻塞原因

#### Scenario: 诊断不泄露敏感信息

- **WHEN** queue、lock、preview 或 deploy evidence 写入日志、API 响应或 MissionTrace
- **THEN** evidence MUST NOT 包含 raw secrets、API keys、tokens、受保护 host paths 或未分配给当前 Session 的 host 路径

### Requirement: V2.3 保留现有 demo 边界

系统 SHALL 在引入 Session Queue 和 DB Target Lock 时保留当前 AgentHub 本地
demo 边界。

#### Scenario: 不引入平台扩展

- **WHEN** V2.3 被实现
- **THEN** 系统 MUST NOT 因该变更引入 Docker sandbox、WebSocket、多用户 IM、外部 IM、PR 创建、生产部署、provider marketplace、Postgres 要求或分布式 worker 集群

#### Scenario: 保留现有 adapter

- **WHEN** V2.3 被实现
- **THEN** CodexAdapter、ClaudeCodeAdapter 和 ScriptedMockAdapter MUST 保持可用
- **AND** 系统 MUST NOT 新增 adapter 作为完成 V2.3 的必要条件

#### Scenario: 保留 Vite React preview 边界

- **WHEN** preview job 执行本地 demo app preview
- **THEN** preview MUST 继续使用 Vite React demo app 边界
- **AND** preview command MUST 保持受允许命令与 target/worktree 边界约束
