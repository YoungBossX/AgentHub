## ADDED Requirements
### Requirement: 用于差异比较的会话工作树隔离
系统 MUST 从该会话中所有 TaskRun 使用的会话工作树收集差异。

#### Scenario: 会话变更保持隔离
- **GIVEN** 同一工作区仓库存在两个会话
- **WHEN** 两个会话均运行代理任务
- **THEN** 它们的文件修改发生在不同的会话工作树路径中
- **并且** 它们的差异被独立收集

### Requirement: 真实 Git 差异收集
系统 MUST 使用 Git CLI 和 `git diff -p` 从实际工作区变更中生成差异。

#### Scenario: 文件变更成为补丁文本
- **GIVEN** CodexAdapter 或 ScriptedMockAdapter 在会话工作区中修改文件
- **WHEN** 后端收集差异制品
- **THEN** 在该会话工作区中运行 Git CLI
- **并且** 存储从真实文件变更生成的补丁文本

### Requirement: TaskRun 差异引用
系统 MUST 在执行前记录每个 TaskRun 的 `baseRef`，并在收集和存储差异制品时使用该 TaskRun 特定的边界。

#### Scenario: TaskRun 在执行前记录 baseRef
- **GIVEN** 一个 TaskRun 即将在会话工作区中启动
- **WHEN** 执行已排队
- **THEN** 系统从当前会话工作区提交 SHA 或显式 git ref 中记录 `baseRef`
- **并且** 适配器执行仅在存储了 TaskRun 特定的 `baseRef` 之后才开始

#### Scenario: Diff 使用 TaskRun 特定的边界
- **GIVEN** 某个 TaskRun 已记录 `baseRef`
- **WHEN** 差异收集在适配器执行之后运行
- **THEN** 该差异通过 `git diff -p baseRef -- .` 或等效语义从该 TaskRun 的 `baseRef` 生成
- **并且** Diff 记录存储了该 TaskRun 的基础引用和头部引用

#### Scenario: 后续运行获取独立的差异边界
- **GIVEN** 会话的工作树中已包含已完成的 TaskRun
- **WHEN** 同一会话中启动了一个后续 TaskRun
- **THEN** 该后续 TaskRun 记录了一个新的 `baseRef`
- **并且** 其差异收集不会覆盖先前 TaskRun 的差异引用或制品

### Requirement: 变更文件与统计信息
系统 MUST 需在补丁文本之外，一并收集变更文件及其差异统计信息。

#### Scenario: Diff 卡片接收摘要数据
- **GIVEN** 会话工作树包含已修改的文件
- **WHEN** 差异收集完成
- **THEN** Diff 记录包含 `changedFilesJson` 和 `statsJson`
- **并且** UI 能够渲染已更改文件列表和补丁摘要

### Requirement: 保护生成的依赖项
系统 MUST 将 `node_modules` 排除在差异收集之外，并保护其免受代理编辑的影响。

#### Scenario: 演示仓库中存在 node_modules
- **GIVEN** 设置期间已安装 Vite React 依赖项
- **WHEN** 差异收集运行或适配器提议编辑
- **THEN** `node_modules` 未包含在差异制品中
- **并且** 代理对 `node_modules` 的编辑被受保护路径规则阻止

### Requirement: 可展开的差异检查
系统 MUST 允许用户展开差异卡片并检查文件级别的变更。

#### Scenario: 用户打开差异卡片
- **GIVEN** 存在一个差异制品
- **WHEN** 用户展开差异卡片
- **THEN** 界面显示文件级变更
- **并且** 可通过 Monaco 差异编辑器或等效的基于 Monaco 的差异视图检查详细变更

### Requirement: 可选补丁验证
当补丁验证启用时，系统 MUST 支持对生成的补丁进行可选的 `git apply --check` 验证。

#### Scenario: 补丁验证运行
- **GIVEN** 已生成补丁
- **WHEN** 已启用补丁验证
- **THEN** 后端运行 `git apply --check` 而不修改工作区
- **并且** 存储或报告验证结果
