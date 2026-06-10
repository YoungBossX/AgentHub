## ADDED Requirements
### Requirement: Agent 目录条目
系统 SHALL 暴露一个工作区范围的 Agent 目录，其中包含内置 Agent 和安全的草稿 Agent 元数据。

#### Scenario: 列出内置代理
- **WHEN** 用户打开代理目录
- **THEN** 系统列出可用的内置规划器、前端、后端、审查、QA 和具备编排能力的条目
- **并且** 每个条目包含显示名称、头像缩写、角色、提供者 ID、适配器类型、能力标签、支持的目标、支持的模式、安全标志、状态、认证状态、可用性和描述

#### Scenario: 目录条目显示运行时选择
- **WHEN** 运行时配置为某个角色选择了一个 agent/profile/provider
- **THEN** 匹配的目录条目在 `runtimeSelectedForRoles` 中暴露该选定的角色

### Requirement: 安全的自定义 Agent 草稿
系统 SHALL 允许仅包含元数据的自定义 Agent 草稿，而无需启用不安全的执行。

#### Scenario: 创建安全草稿元数据
- **WHEN** 用户仅使用安全元数据创建草稿
- **THEN** 系统将草稿存储为禁用或仅审查元数据
- **并且** 该草稿在代理目录中显示为 `entryType=draft`

#### Scenario: 拒绝任意 shell 命令
- **WHEN** 草稿包含 shell 命令
- **THEN** 系统如实拒绝该草稿

#### Scenario: 拒绝不安全的工具权限
- **WHEN** 草稿请求不安全的工具权限或不受限制的文件系统访问
- **THEN** 系统如实拒绝该草稿

#### Scenario: 草稿未作为编码代理执行
- **WHEN** 草稿尚未被验证为可安全执行
- **THEN** 运行时配置和调度器路径不将其用于代码编写
  TaskRuns

### Requirement: Agent 兼容性检查
系统 SHALL 提供用于选择 Agent 的显式兼容性元数据。

#### Scenario: 兼容的前端代理
- **WHEN** 根据前端安全配置文件检查前端运行时角色
  该配置文件包含兼容的提供商、适配器、模式、能力和目标
- **THEN** 兼容性报告为 true

#### Scenario: 角色或适配器不兼容
- **WHEN** 前端角色与仅后端配置文件或 provider/adapter 不匹配
- **THEN** 兼容性为 false，并附带用户可读的原因

#### Scenario: 不支持的目标或能力
- **WHEN** 配置文件不支持请求的目标、模式或能力
- **THEN** 兼容性为 false，并附带用户可读的原因

### Requirement: 运行时配置使用目录兼容性
系统 SHALL 将 Planner、Frontend、Backend 和 Review 的运行时选择限制为兼容的安全条目。

#### Scenario: 有效的运行时选择
- **WHEN** 用户为规划器、前端、后端和审查选择了兼容的目录条目
- **THEN** 运行时配置已保存，并记录了所选的代理配置文件、提供商、适配器、模式和配置源

#### Scenario: 无效的运行时选择
- **WHEN** 用户选择了不可用的提供商、适配器不匹配、不安全的配置文件、不兼容的角色或不受支持的 target/mode/capability
- **THEN** 运行时配置诚实地拒绝该选择

#### Scenario: 密钥不被暴露
- **WHEN** 目录或运行时配置响应中包含提供者可用性信息
- **THEN** 原始 API 密钥、令牌、凭据和受保护的主机路径不被
  暴露

### Requirement: Agent 目录 UI
系统 SHALL 提供一个设置界面，用于查看和管理 Agent 目录条目，而不会使聊天工作区变得杂乱。

#### Scenario: Agent 卡片展示提供商与能力元数据
- **WHEN** 用户打开 Agent 目录界面
- **THEN** 每张卡片展示提供商徽章、适配器类型、角色、能力标签、
  支持的目标、支持的模式、安全标志、状态和可用性

#### Scenario: 筛选目录条目
- **WHEN** 用户按角色、提供者、能力、目标或状态进行筛选
- **THEN** 界面显示匹配的条目，但不更改运行时配置

#### Scenario: 草稿表单包含保存和取消功能
- **WHEN** 用户创建草稿
- **THEN** 表单包含保存和取消控件
- **并且** 取消操作不会持久化草稿

#### Scenario: 聊天保持简洁
- **WHEN** 用户返回聊天工作区
- **THEN** 详细的 provider/agent 配置控件不会内联显示在
  聊天流中

### Requirement: Agent 目录证据
系统 SHALL 需暴露足够的元数据，以便审计 Agent 为何可选、被选中、不可用或被拒绝。

#### Scenario: 兼容性原因可见
- **WHEN** 某个条目不兼容
- **THEN** API 响应和 UI 显示原因，但不暴露机密信息

#### Scenario: 运行时选择可审计
- **WHEN** 运行时配置解析出一个 agent/provider
- **THEN** TaskRun、规划器证据、任务追踪或 API 响应继续
  显示已解析的代理配置文件 ID、提供者 ID、适配器类型、配置来源，
  以及适用的兜底原因
