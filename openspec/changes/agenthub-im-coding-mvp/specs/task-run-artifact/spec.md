## ADDED Requirements
### Requirement: 核心实体持久化边界
系统 MUST 使用 User、Workspace、Session、Message、Agent、Task、TaskRun、TaskRunEvent、Artifact、Diff、Preview 和 Deployment 实体实现 P0 持久化。

#### Scenario: 任务运行创建制品和事件
- **GIVEN** 任务运行完成并产生文件变更
- **WHEN** 后端收集差异、预览和部署输出
- **THEN** 系统使用 Artifact、Diff、Preview 和 Deployment 记录存储这些输出
- **并且** 使用 TaskRunEvent 记录存储运行追踪事件
- **并且** 主路径不需要无关的 P0 领域实体

### Requirement: TaskRunEvent 支持实体
系统 MUST 将 TaskRunEvent 作为核心领域模型之外唯一的 P0 支持实体纳入。

#### Scenario: 适配器事件被持久化
- **GIVEN** 适配器发出标准化事件
- **WHEN** 后端处理该事件
- **THEN** 后端存储一个包含 `taskRunId`、`eventType`、`payloadJson`、`sequence` 和 `createdAt` 的 TaskRunEvent
- **并且** 存储的序列可用于回放或调试

### Requirement: TaskRun 生命周期
系统 MUST 暴露 TaskRun 状态 `created`、`queued`、`streaming`、`waiting_approval`、`applying_changes`、`collecting_diff`、`starting_preview`、`completed`、`failed` 和 `interrupted`。

#### Scenario: 成功的任务运行达到已完成状态
- **GIVEN** 适配器运行开始
- **WHEN** 适配器流式传输变更，差异收集成功，预览开始
- **THEN** TaskRun 经历所需的生命周期状态转换
- **并且** 最终处于 `completed` 状态

#### Scenario: 审批暂停任务运行
- **GIVEN** 任务运行需要用户审批
- **WHEN** 审批请求被发出
- **THEN** TaskRun 状态变为 `waiting_approval`
- **并且** 在审批通过或请求被拒绝、过期、失败或中断之前，运行不会继续

### Requirement: TaskRun 差异引用
每个 TaskRun MUST 在执行前记录 `baseRef`，并在执行后记录 `headRef`，用于收集 TaskRun 特定的差异。

#### Scenario: baseRef 在执行前被捕获
- **GIVEN** 一个 TaskRun 即将在会话工作树中启动
- **WHEN** 后端准备适配器执行
- **THEN** 在适配器执行开始前，它将 `baseRef` 记录为当前的 git 提交 SHA 或其他显式 git 引用

#### Scenario: headRef 在执行后被捕获
- **GIVEN** TaskRun 已完成适配器执行
- **WHEN** 后端准备差异收集或运行完成
- **THEN** 它将 `headRef` 记录为当前 HEAD，一个临时引用，或工作树快照标记
- **并且** Diff 制品使用 TaskRun 的 `baseRef` 和 `headRef` 以实现可追溯性

#### Scenario: 重试保留之前的引用
- **GIVEN** 一个 TaskRun 因已有的 `baseRef` 或 `headRef` 而失败或被中断
- **WHEN** 用户重试该任务
- **THEN** 系统使用新的 `baseRef` 创建一个新的 TaskRun
- **并且** 不会覆盖之前 TaskRun 的 `baseRef` 或 `headRef`

### Requirement: 制品关联
系统 MUST 将制品与生成它们的 TaskRun 关联起来。

#### Scenario: Diff 制品属于任务运行
- **GIVEN** 任务运行产生一个 diff
- **WHEN** 后端存储该 diff 制品
- **THEN** Artifact 记录引用该 TaskRun
- **并且** Diff 记录引用该 Artifact

### Requirement: 错误映射
系统 MUST 在失败的 TaskRun 上持久化标准化的 `errorCode` 和 `errorMessage`。

#### Scenario: 适配器失败
- **GIVEN** 适配器运行遇到已知故障
- **WHEN** 该运行被标记为失败
- **THEN** TaskRun 存储标准化的错误码和人类可读的消息
- **并且** UI 可从该失败状态提供重试功能

### Requirement: 从持久化状态恢复 SSE
系统 MUST 允许 UI 在页面刷新或 SSE 重连后恢复会话消息、任务、任务运行、终端状态、制品、审批请求以及可重放的任务运行事件。

#### Scenario: 用户在执行期间或执行后刷新页面
- **GIVEN** 会话包含消息、TaskRun、TaskRunEvent 和制品
- **WHEN** 用户刷新页面或重新连接 SSE
- **THEN** UI 从持久化的后端记录中重建当前会话状态
- **并且** 在可用时，能够重放自上次接收序列之后的任务运行事件
