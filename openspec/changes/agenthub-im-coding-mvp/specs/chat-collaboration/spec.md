## ADDED Requirements
### Requirement: IM 风格的消息流
系统 MUST 渲染一个包含用户、编排器、角色代理、系统以及制品相关消息的 IM 风格聊天流。

#### Scenario: 来自多个发送者的消息出现在同一会话中
- **GIVEN** 选中一个会话
- **WHEN** 用户发送请求，编排器将任务分配给角色代理
- **THEN** 聊天流按时间顺序显示来自用户、编排器以及已分配角色代理的消息

### Requirement: 编排器提及解析
系统 MUST 解析 `@orchestrator` 提及，并将消息路由至编排器流程。

#### Scenario: 用户要求编排器构建一个登录页面
- **GIVEN** 选择一个会话
- **WHEN** 用户发送 `@orchestrator build a login page`
- **THEN** 系统创建一条由编排器处理的消息
- **并且** 编排器开始为该请求规划可见任务

### Requirement: 角色-智能体提及解析
系统 MUST 解析角色-智能体提及，包括 `@frontend`、`@backend` 和 `@qa`。

#### Scenario: 用户提及前端代理
- **GIVEN** 角色代理已启用
- **WHEN** 用户发送包含 `@frontend` 的消息
- **THEN** 系统将提及解析为已启用的前端角色代理
- **并且** 创建的任务或直接消息引用了该代理角色

### Requirement: 流式聊天更新
系统 MUST 使用 SSE 实现 P0 实时聊天、任务和制品更新，并基于 TaskRunEvent 提供恢复能力。

#### Scenario: 任务状态更新流式进入聊天
- **GIVEN** 任务运行处于活跃状态
- **WHEN** 后端发出任务状态事件
- **THEN** 前端通过 SSE 接收事件
- **并且** 聊天流无需页面刷新即可更新

#### Scenario: SSE 重连时重放遗漏的任务运行事件
- **GIVEN** 前端最后收到的 TaskRunEvent 序列号
- **WHEN** SSE 连接重新建立
- **THEN** 后端可重放该序列号之后已持久化的 TaskRunEvent
- **并且** 前端能够恢复遗漏的任务、审批、制品、错误及完成状态更新

### Requirement: 消息持久化
系统 MUST 需持久化聊天消息，包含 `sessionId`、发送者字段、Markdown 内容、类型、父级关联、流状态和创建时间。

#### Scenario: 用户重新加载会话
- **GIVEN** 会话包含先前的用户、编排器和代理消息
- **WHEN** 用户重新加载页面并打开该会话
- **THEN** 系统恢复该会话的持久化消息历史记录

### Requirement: 审批卡片消息
系统 MUST 将待审批请求渲染为聊天流审批卡片。

#### Scenario: 审批请求出现在聊天中
- **GIVEN** 一个 TaskRun 进入 `waiting_approval`
- **WHEN** 后端发出一个 `approval.requested` 事件
- **THEN** 聊天流显示一个审批卡片
- **并且** 卡片显示审批类型、原因、请求的操作、风险等级，以及相关的命令或路径（若存在）
