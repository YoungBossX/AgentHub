## ADDED Requirements
### Requirement: 最小适配器生命周期
系统 MUST 定义了一个统一的适配器接口，包含 `getCapabilities`、`createRun`、`streamEvents`、`interrupt`、`approve`、`collectArtifacts` 和 `cleanup`。

#### Scenario: 后端启动适配器运行
- **GIVEN** 任务被分配给已启用的代理
- **WHEN** 后端开始执行
- **THEN** 读取适配器能力
- **并且** 为所选适配器调用 `createRun`
- **并且** 通过 `streamEvents` 消费适配器事件

### Requirement: 适配器能力
系统 MUST 为每个适配器暴露 AdapterCapabilities，包含流式传输、中断、审批、文件编辑、Shell 命令、差异制品、预览制品、网络以及可选的最大运行时间支持标志。

#### Scenario: 编排器检查适配器能力
- **GIVEN** 代理配置了适配器类型
- **WHEN** 编排器向该代理分配任务
- **THEN** 后端可检查适配器能力描述符
- **并且** 避免假设不支持的适配器行为

### Requirement: CodexAdapter 本地 CLI 执行
系统 MUST 将 `CodexAdapter` 作为唯一的 P0 真实编码适配器，通过本地 CLI 调用实现。

#### Scenario: CodexAdapter 在会话工作树中修改代码
- **GIVEN** TaskRun 拥有一个会话工作树
- **WHEN** `CodexAdapter` 成功执行任务
- **THEN** 适配器在会话工作树内调用本地 Codex CLI
- **并且** 它能够生成真实的文件修改，这些修改稍后可通过 git diff 收集

#### Scenario: P0 中未使用 Codex API 封装器
- **GIVEN** `CodexAdapter` 已为 P0 配置
- **WHEN** 适配器运行启动
- **THEN** 系统使用本地 CLI 调用
- **并且** 不需要 API 或云任务封装器

### Requirement: ScriptedMockAdapter 兜底
系统 MUST 包含 `ScriptedMockAdapter`，该适配器执行受控脚本，对真实的 Vite React 演示仓库文件进行更改。

#### Scenario: 兜底在真实适配器失败后完成
- **GIVEN** `CodexAdapter` 在演示任务中失败
- **WHEN** 用户使用兜底重试
- **THEN** `ScriptedMockAdapter` 在会话工作树中执行受控脚本
- **并且** Vite React 演示仓库在兜底完成后包含真实的文件变更

### Requirement: 统一适配器事件
系统 MUST 将适配器输出规范化为 `message.delta`、`task.state`、`approval.requested`、`artifact.diff.ready`、`artifact.preview.ready`、`artifact.deploy.ready`、`error` 和 `completed` 事件。

#### Scenario: 适配器发出进度
- **GIVEN** 适配器运行处于活跃状态
- **WHEN** 适配器报告进度、审批、制品、失败或完成
- **THEN** 后端为标准化事件持久化一个 TaskRunEvent
- **并且** 向会话流发出对应的事件类型

### Requirement: 适配器清理
系统 MUST 在完成、失败或中断后清理适配器拥有的前台或后台资源。

#### Scenario: 中断的适配器被清理
- **GIVEN** 适配器运行正在流式传输
- **WHEN** 用户中断了该运行
- **THEN** 后端调用 `interrupt`
- **并且** 在标记清理完成之前调用 `cleanup`

### Requirement: P1 适配器推迟
系统 MUST 将 ClaudeCodeAdapter、HumanAgentAdapter 和 Codex API/cloud 任务包装器保留在 P0 之外。

#### Scenario: P0 适配器列表已加载
- **GIVEN** P0 系统启动
- **WHEN** 可用适配器已注册
- **THEN** 演示路径仅需要 `CodexAdapter` 和 `ScriptedMockAdapter`
- **并且** P1 适配器不是 P0 验收的必要条件
