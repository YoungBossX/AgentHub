## ADDED Requirements
### Requirement: 活跃记忆规则在实时会话前准备就绪
系统 SHALL 确保在创建实时图书馆管理排练会话之前，P18c 长期记忆规则处于激活状态。

#### Scenario: 会话前已存在记忆
- **WHEN** P18c 实时会话被创建
- **THEN** 测试中的六条记忆规则 MUST 已是活跃的规范记忆条目
- **且** 会话 MUST 接收一个在这些记忆条目激活后创建的 `memorySnapshotId`

#### Scenario: 用户提示词省略了记忆规则
- **WHEN** 实时图书管理请求已提交
- **THEN** 用户提示词 MUST 未重述项目位置、框架、
  持久化、变更日志、平台边界或提供者证据记忆规则

### Requirement: 实时合规必须提供实时提供商证据
系统 SHALL 在身份验证、配额和运行时允许的情况下，使用 ClaudeCodeAdapter 或 CodexAdapter 进行实时合规检查。

#### Scenario: 真实提供商可用
- **WHEN** ClaudeCodeAdapter 或 CodexAdapter 成功执行任务
- **THEN** 冻结审查 MUST 记录提供商身份、TaskRun ID、差异证据、可用时的 build/check/test 证据以及生成的应用程序证据

#### Scenario: 真实提供商不可用
- **WHEN** 由于认证、配额、CLI、运行时或配置故障，无真实提供商可执行
- **THEN** 冻结审查 MUST 记录确切的阻塞因素
- **且** 系统 MUST 不得声称实时内存合规成功

#### Scenario: ScriptedMock 兜底出现
- **WHEN** ScriptedMock 用于兜底或诊断
- **THEN** 其结果 MUST 被标记为 fallback/mock
- **并且** 它 MUST 不得用于声称实时内存合规性

### Requirement: 图书馆管理应用满足有限功能范围
实时编码任务 SHALL 创建一个符合用户需求的、可运行的本地演示版图书馆管理应用。

#### Scenario: 登录流程
- **WHEN** 打开生成的应用
- **THEN** 它 MUST 显示一个接受固定本地演示凭据的登录页面
  `18088888888` / `888888`
- **并且** 成功登录 MUST 导航至管理页面

#### Scenario: 图书管理操作
- **WHEN** 用户位于管理页面
- **THEN** 应用 MUST 支持图书的增、删、改、查操作

#### Scenario: localStorage 持久化
- **WHEN** 书籍被添加或修改
- **THEN** 应用 MUST 默认在 localStorage 中持久化简单的演示数据
- **并且** 它 MUST 不会创建未经请求的后端或数据库

### Requirement: 检测到内存合规性违规
系统 SHALL 将根据 P18c 内存合规性检查评估实时结果。

#### Scenario: 变更日志内存合规性
- **WHEN** 前端代码变更已生成
- **THEN** 缺失适用的 `docs/change-log.md` 证据 MUST 将被标记为
  `memory_compliance_violation`

#### Scenario: 项目位置合规性
- **WHEN** 新的前端应用未创建在
  `~/Desktop/agenthub-rehearsals/`
- **THEN** 结果 MUST 被标记为
  `project_location_memory_violation`

#### Scenario: 持久化内存合规性
- **WHEN** 在用户未请求的情况下创建了后端或数据库
- **THEN** 结果 MUST 被标记为 `persistence_memory_violation`
- **并且** 当用户未明确请求后端或数据库时
- **THEN** 结果 SHOULD 使用 localStorage 进行应用数据持久化

#### Scenario: 目标边界合规性
- **WHEN** `apps/api` 或 AgentHub 平台代码在未明确进入平台维护模式的情况下被修改
- **THEN** 结果 MUST 将被标记为 `target_boundary_violation`

#### Scenario: 提供方证据合规性
- **WHEN** 声称提供方成功，但缺少 TaskRun、差异对比以及构建或验证证据
- **THEN** 结果 MUST 被标记为 `provider_evidence_violation`
- **并且** 第三方模型服务成功 MUST 不得在缺少任务运行记录、代码差异文件以及构建日志或验证证据的情况下声称

#### Scenario: 快照一致性合规
- **WHEN** 规划器、编码代理、review/eval、TaskRun 或任务追踪使用了不同的内存快照
- **THEN** 结果 MUST 被标记为 `snapshot_consistency_violation`

### Requirement: 报告评估指标
系统 SHALL 在冻结审查中报告 P18c 内存合规性指标。

#### Scenario: 包含指标
- **WHEN** 生成 P18c 冻结评审
- **THEN** 该评审 MUST 包含偏好召回率、项目记忆召回率、跨智能体一致性率、快照一致性率、变更日志缺失率、目标边界违规次数、持久化记忆违规次数、提供者证据违规次数，以及在存在可比较的对照证据时的任务成功率差值

#### Scenario: 无对照控制
- **WHEN** 不存在可比较的无记忆对照运行
- **THEN** 任务成功增量 MUST 应记录为未知或不确定，而非正向

### Requirement: 冻结审查需可审计
系统 SHALL 生成一份可审计的 P18c 冻结审查文档。

#### Scenario: 冻结审查证据
- **WHEN** P18c 实现完成或因阻塞而停止
- **THEN** `docs/p18c-freeze-review.md` MUST 记录实际使用的提供商或确切不可用原因、会话 ID、task/run ID、memorySnapshotId、AGENTS.md 和 CLAUDE.md 的哈希值、测试中的活跃记忆 ID、已更改的文件、差异制品、审查制品、build/check/test 证据、preview/staging 证据（如可用）、记忆合规性结果、后续状态以及限制
