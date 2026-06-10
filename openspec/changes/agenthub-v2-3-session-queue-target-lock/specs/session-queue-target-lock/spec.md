## ADDED Requirements
### Requirement: 持久化 Session 队列
系统 SHALL 为每个 Session 的主执行 TaskRun 维护持久化 Session 队列，用于表示
队列顺序、可运行状态、等待原因和执行结果。

#### Scenario: TaskRun 创建时进入 Session 队列
- **WHEN** 系统为 Session 创建一个主执行 TaskRun
- **THEN** 系统 MUST 创建或更新对应的 Session 队列条目
- **并且** 队列条目 MUST 记录 session、task、task run、访问模式、目标 ID 和队列位置
- **并且** 队列条目 MUST 可在服务重启后恢复读取

#### Scenario: 队列位置可见
- **WHEN** 用户查看 TaskRun、任务追踪或等效诊断信息
- **THEN** 系统 SHOULD 暴露该 TaskRun 的队列位置
- **并且** 系统 SHOULD 暴露等待原因，例如依赖等待、目标锁等待或审批等待

#### Scenario: 终态运行不重新入队执行
- **WHEN** TaskRun 已处于 completed、failed、interrupted、cancelled 或其他终态
- **THEN** Session 队列 MUST 不会将该 TaskRun 重新变为可运行状态
- **并且** worker MUST 不会因队列恢复而重复执行它

### Requirement: 同 Session 写任务串行
系统 SHALL 保证同一 Session 内的写任务按 Session 队列顺序串行执行。

#### Scenario: 同 Session 已有写任务运行
- **WHEN** 一个 Session 中已有 `access_mode=write` 的 TaskRun 正在运行或进入终态化
- **并且** 同一 Session 的另一个写 TaskRun 已排队
- **THEN** 系统 MUST 不会启动第二个写 TaskRun
- **并且** 第二个写 TaskRun MUST 保持 queued 或 waiting 状态
- **并且** 等待原因 MUST 可诊断

#### Scenario: 前一个写任务完成后推进队列
- **WHEN** 同 Session 的当前写 TaskRun 进入终态
- **并且** 相关的终态化程序已完成必要的队列和锁释放步骤
- **THEN** 系统 MUST 重新评估同 Session 后续的队列条目
- **并且** 下一个满足依赖、审批和目标锁条件的写 TaskRun 可能变为可运行状态

#### Scenario: 写任务重试不绕过队列
- **WHEN** 用户重试一个失败或中断的写 TaskRun
- **THEN** 系统 MUST 为重试创建新的可追踪 TaskRun 或等效运行历史
- **并且** 重试 MUST 进入同一 Session 队列
- **并且** 重试 MUST 不会绕过当前排在前面的写任务

### Requirement: 同 Session 只读任务安全并发
系统 SHALL 允许同一 Session 中安全的只读任务并发执行，但不得让只读任务修改
session 工作树或绕过依赖边界。

#### Scenario: 只读任务依赖已满足
- **WHEN** 一个 `access_mode=readonly` 的 TaskRun 依赖已完成
- **并且** 该 TaskRun 不需要写入 session 工作树
- **并且** 该 TaskRun 不需要目标写锁
- **THEN** 系统可以与该 Session 的其他只读 TaskRun 并发执行它

#### Scenario: 只读任务依赖运行中的写任务
- **WHEN** 一个只读 TaskRun 依赖同 Session 中仍在运行或未完成终态化的写 TaskRun
- **THEN** 系统 MUST 不会启动该只读 TaskRun
- **并且** 它 MUST 等待依赖的写任务完成并完成必要的终态化

#### Scenario: 无法证明只读安全
- **WHEN** 调度器无法证明某个任务不会修改工作树、源代码、差异或主执行结果
- **THEN** 系统 MUST 将该任务按写任务或保守等待处理
- **并且** 系统 MUST 不会因标记不清而并发执行它

### Requirement: 不同 Session 在锁允许时并发
系统 SHALL 允许不同 Session 的任务在工作树隔离和目标锁允许时并发。

#### Scenario: 不同 Session 写入不同目标
- **WHEN** 两个不同 Session 各自拥有独立的 session 工作树
- **并且** 它们的写 TaskRun 面向不同的目标锁键
- **并且** 依赖、审批、提供者和命令策略均允许执行
- **THEN** 系统可以并发执行这两个写 TaskRun

#### Scenario: 不同 Session 不得共享工作树
- **WHEN** 系统准备启动一个 Session 的 TaskRun
- **THEN** 系统 MUST 验证该 Session 使用自己的持久化工作树路径
- **并且** 不同 Session MUST 不得共享同一个工作树路径

#### Scenario: 不同 Session 写入同一目标
- **WHEN** 两个不同 Session 的写 TaskRun 面向同一目标锁键
- **THEN** 最多一个 TaskRun MUST 持有该目标写锁
- **并且** 未获得锁的 TaskRun MUST 不会启动适配器
- **并且** 未获得锁的 TaskRun MUST 暴露等待锁状态或等效诊断

### Requirement: 显式数据库目标锁
系统 SHALL 使用显式持久化数据库目标锁保护同 target/project 的写任务，而不是
仅从活跃 TaskRun 推导软锁。

#### Scenario: 写任务原子获取目标锁
- **WHEN** 写 TaskRun 准备进入适配器执行
- **THEN** 系统 MUST 在数据库中原子获取目标写锁
- **并且** 锁 MUST 记录锁键、目标 ID、session ID、task run ID、worker ID 或等效持有者信息
- **并且** 适配器 MUST 在锁获取成功前不会启动

#### Scenario: 并发获取同一锁
- **WHEN** 两个写 TaskRun 并发尝试获取同一个目标写锁
- **THEN** 最多一个获取 MUST 成功
- **并且** 失败的一方 MUST 不启动适配器
- **并且** 失败的一方 MUST 记录锁等待或获取失败证据

#### Scenario: 获取锁后记录事件
- **WHEN** 目标写锁获取成功
- **THEN** 系统 MUST 记录可审计事件或证据
- **并且** 证据 SHOULD 包含锁键、持有者 task run、session 和租约到期时间

### Requirement: 目标锁幂等释放
系统 SHALL 在写 TaskRun 进入终态终态化时幂等释放其持有的目标锁。

#### Scenario: 已完成运行释放锁
- **WHEN** 持有目标写锁的 TaskRun 完成
- **THEN** 终态化程序 MUST 释放该 TaskRun 持有的锁
- **并且** 系统 MUST 记录释放证据
- **并且** Session 队列 MUST 重新评估后续等待项

#### Scenario: 失败/中断/超时运行释放锁
- **WHEN** 持有目标写锁的 TaskRun 失败、中断、超时、取消或陈旧失败
- **THEN** 终态化程序 MUST 释放该 TaskRun 持有的锁
- **并且** 系统 MUST 不会因释放锁而把该 TaskRun 标记为已完成

#### Scenario: 重复释放不释放后来者
- **WHEN** 释放逻辑被重复调用
- **并且** 同一锁键已被另一个 TaskRun 后来获取
- **THEN** 系统 MUST 不会释放后来者的锁
- **并且** 释放 MUST 校验原持有者的 task run ID、session ID 和锁状态

### Requirement: 陈旧锁恢复
系统 SHALL 在服务或 worker 启动恢复时扫描并处理陈旧的队列条目和陈旧
目标锁。

#### Scenario: 终态持有者的锁被恢复释放
- **WHEN** 恢复扫描发现持有的锁的持有者 TaskRun 已处于终态
- **THEN** 系统 MUST 将该锁作为陈旧锁释放
- **并且** 系统 MUST 记录陈旧释放证据

#### Scenario: 租约过期且 worker 心跳过期
- **WHEN** 持有的锁的租约已过期
- **并且** 持有者 worker 心跳已过期或不可确认
- **THEN** 系统 MUST 执行陈旧恢复
- **并且** 系统 MUST 释放锁或将持有者运行诚实失败化后释放锁
- **并且** 系统 MUST 不会声称真实提供者已成功完成

#### Scenario: 租约未过期
- **WHEN** 恢复扫描发现持有的锁的租约未过期
- **THEN** 系统 MUST 不会抢占释放该锁
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
