## ADDED Requirements
### Requirement: 单用户工作区创建
系统 MUST 支持绑定到一个 Vite React 演示仓库的单用户工作区，并包含 `repoUrl`、`rootPath` 和 `defaultBranch` 元数据。

#### Scenario: 用户打开演示工作区
- **GIVEN** 本地演示环境正在运行
- **WHEN** 用户打开 AgentHub
- **THEN** 系统显示一个可选的工作区，该工作区由已配置的 Vite React 演示仓库提供支持
- **并且** 该工作区可用于创建编码会话

### Requirement: 多会话管理
系统 MUST 允许用户在一个工作区内创建并切换至少三个会话。

#### Scenario: 用户在会话之间切换
- **GIVEN** 存在一个工作区
- **WHEN** 用户创建三个会话，并从会话列表中选择每个会话
- **THEN** 界面中显示的聊天流、任务状态和制品与所选会话匹配

### Requirement: 会话级工作树绑定
系统 MUST 在 P0 阶段为每个会话创建并持久化恰好一个 git 工作树。

#### Scenario: 会话获取工作树
- **GIVEN** 工作区已存在
- **WHEN** 用户创建新会话
- **THEN** 系统创建或分配一个确定性的会话级 Git 工作树
- **并且** 将路径存储在 `Session.worktreePath` 上

#### Scenario: TaskRun 复用会话工作树
- **GIVEN** 会话拥有一个 `worktreePath`
- **WHEN** 多个 TaskRun 在该会话中执行
- **THEN** 每个 TaskRun 使用相同的会话工作树路径
- **并且** 每个 TaskRun 记录该路径以实现可追溯性

### Requirement: 跨会话工作树隔离
系统 MUST 阻止多个会话共享同一工作树路径。

#### Scenario: 多个会话使用独立的工作树
- **GIVEN** 同一工作区内存在两个会话
- **WHEN** 每个会话启动代理执行
- **THEN** 各会话具有不同的 `worktreePath` 值
- **并且** 一个会话的变更不会出现在另一个会话的工作树中

### Requirement: 会话状态与最近使用
系统 MUST 维护会话的 `status` 和 `lastMessageAt`，以便 UI 能够显示活跃会话和最近会话。

#### Scenario: 新消息更新会话时效性
- **GIVEN** 存在一个会话
- **WHEN** 用户在该会话中发送了一条聊天消息
- **THEN** 会话的 `lastMessageAt` 被更新
- **并且** 该会话仍可被选中，且不会丢失之前的消息
