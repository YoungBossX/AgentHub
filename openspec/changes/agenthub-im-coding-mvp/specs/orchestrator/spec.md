## ADDED Requirements
### Requirement: P0 任务规划
编排器 MUST 将 `@orchestrator` 编码请求转换为 2-4 个可见任务。

#### Scenario: 登录页面请求创建可见计划
- **GIVEN** 选择一个会话
- **WHEN** 用户发送 `@orchestrator build a login page for the demo app`
- **THEN** 编排器创建两到四个任务
- **并且** 聊天流将计划显示给用户

### Requirement: 角色-智能体分配
编排器 MUST 将已规划的任务分配给已启用的角色智能体，例如前端、后端或 QA。

#### Scenario: 前端任务被分配
- **GIVEN** 编排器创建一个 UI 实现任务
- **WHEN** 任务分配运行
- **THEN** 该任务引用一个已启用的前端代理
- **并且** UI 显示已分配的角色代理

### Requirement: 简单的依赖处理
编排器 MUST 支持简单的串行依赖，以及至多一个简单的并行组。

#### Scenario: 依赖任务等待前置任务
- **GIVEN** 编排器创建一个串行实现任务和 QA 任务
- **WHEN** 实现任务仍在运行
- **THEN** QA 任务保持待处理状态，直到其依赖项完成

### Requirement: 任务状态可见性
编排器 MUST 暴露任务状态 `pending`、`planning`、`running`、`waiting_approval`、`completed`、`failed` 和 `interrupted`。

#### Scenario: 执行期间的任务状态更新
- **GIVEN** 计划中的任务开始执行
- **WHEN** 任务经历执行和制品收集阶段
- **THEN** 聊天流中显示该任务的可见状态变更

### Requirement: 重试与中断编排
编排器 MUST 支持对失败或中断的任务进行重试，以及对运行中的任务进行中断。

#### Scenario: 用户重试被中断的任务
- **GIVEN** 任务被中断
- **WHEN** 用户点击重试
- **THEN** 系统为同一任务创建新的 TaskRun
- **并且** 任务可通过所选适配器路径继续执行

#### Scenario: 用户使用脚本化兜底重试
- **GIVEN** CodexAdapter 的 TaskRun 失败
- **WHEN** 用户选择使用兜底重试
- **THEN** 编排器为同一 Task 创建新的 TaskRun，使用 ScriptedMockAdapter
- **并且** 之前的 TaskRun 历史记录保持可见

### Requirement: 结果汇总
编排器 MUST 汇总已完成的工作并关联相关制品。

#### Scenario: 编排流程完成
- **GIVEN** 请求的所有必需任务均已完成
- **WHEN** 差异与预览制品已存在
- **THEN** 编排器发布摘要，其中引用了变更文件、预览和部署卡片
