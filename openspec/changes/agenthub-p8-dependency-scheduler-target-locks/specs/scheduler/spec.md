## ADDED Requirements
### Requirement: 依赖感知的任务调度
系统 MUST 根据声明的任务依赖关系调度任务执行。

#### Scenario: 任务等待未完成的依赖项
- **WHEN** 一个任务有一个或多个 `dependsOnTaskIds`
- **并且** 至少有一个依赖项未完成
- **THEN** 调度器 MUST 不会为该任务启动 TaskRun
- **并且** 该任务 MUST 暴露的调度器状态等同于
  `waiting_dependency`。

#### Scenario: 依赖完成后任务变为可运行状态
- **WHEN** 任务的所有依赖项已完成
- **且** 没有目标锁定或审批规则阻止该任务
- **THEN** 调度器可通过现有 TaskRun 路径创建 TaskRun
- **且** 任务 MUST 在执行开始后暴露与 `running` 等效的调度器状态。

#### Scenario: 失败的依赖项阻塞下游任务
- **WHEN** 某个依赖任务失败、被中断或阻塞
- **THEN** 依赖该任务的下游任务 MUST 不会自动启动
- **并且** 下游任务 MUST 暴露的调度器状态等同于
  `blocked`
- **并且** 阻塞原因 MUST 标识出失败的依赖项。

### Requirement: 目标写入锁
系统 MUST 通过使用 P7 目标项目注册表中的目标元数据，防止对同一目标执行并发的写入任务。

#### Scenario: 同一前端目标写入已在运行中
- **WHEN** 针对 `demo-frontend` 的写入任务处于活跃状态
- **且** 另一针对 `demo-frontend` 的写入任务变为可运行状态
- **THEN** 调度器 MUST 不会启动第二个写入任务
- **且** 第二个任务 MUST 暴露的调度器状态与 `waiting_target_lock` 等效
- **且** 锁定原因 MUST 标识为 `demo-frontend`。

#### Scenario: 同一后端目标写入已在运行中
- **WHEN** 针对 `demo-backend` 的写入任务处于活跃状态
- **且** 另一针对 `demo-backend` 的写入任务变为可运行状态
- **THEN** 调度器 MUST 不会启动第二个写入任务
- **且** 第二个任务 MUST 暴露的调度器状态与 `waiting_target_lock` 等效
- **且** 锁定原因 MUST 标识为 `demo-backend`。

#### Scenario: 请求写入平台目标
- **WHEN** 写入任务的目标是 `agenthub-platform`
- **THEN** 任务 MUST 需要显式平台模式
- **并且** 任务 MUST 需要在适配器执行前获得批准
- **并且** 普通应用后端任务 MUST 不获取 `agenthub-platform` 写入锁。

#### Scenario: 只读审查被评估
- **WHEN** 审核或 QA 任务为只读型
- **且** 其依赖项已完成
- **THEN** 调度器 MUST 不需要对该任务获取写锁
- **且** 调度器 MUST 仍需遵守依赖与审批规则。

### Requirement: 自动有界流水线推进
系统 MUST 会在依赖项、目标锁和审批条件允许时，自动推进有边界的全栈应用流水线。

#### Scenario: Mini CRM 流水线推进
- **WHEN** 编排器创建受支持的小型 CRM 应用合约任务图
- **THEN** 调度器 MUST 按依赖顺序推进流水线：
  合约、后端、前端、Review/QA、预览、模拟部署
- **并且** 后端代理执行 MUST 目标 `demo-backend`
- **并且** 前端代理执行 MUST 目标 `demo-frontend`
- **并且** 审查/质量保证 MUST 在所需编码差异存在后运行
- **并且** 预览 MUST 使用现有预览路径
- **并且** 部署 MUST 保持模拟标记状态。

#### Scenario: 流水线步骤不可运行
- **WHEN** 流水线步骤存在不完整的依赖、被阻塞的依赖、不可用的审批或目标锁冲突
- **THEN** 调度器 MUST 在该步骤停止推进
- **并且** 下游步骤 MUST 不得静默继续执行。

### Requirement: 故障恢复与阻塞状态
系统 MUST 使调度器故障、重试和兜底状态变得明确且可追踪。

#### Scenario: 适配器运行失败
- **WHEN** 适配器执行期间 TaskRun 失败
- **THEN** 所属任务 MUST 暴露与 `failed` 或 `retryable` 等效的调度器状态
- **且** 下游依赖任务 MUST 暴露 `blocked`
- **且** 调度器 MUST 未声明 Claude/Codex 成功。

#### Scenario: 兜底可用
- **WHEN** 失败的编码 TaskRun 可在现有兜底策略下使用 `ScriptedMockAdapter` 兜底
- **THEN** 任务 MUST 暴露与 `fallback_available` 等效的调度器状态
- **并且** 兜底执行 MUST 通过新的 TaskRun 或等效的运行历史保持可追溯性。

#### Scenario: 用户重试失败的依赖项
- **WHEN** 用户重试或兜底一个失败的依赖项
- **并且** 重试或兜底的运行完成
- **THEN** 调度器 MUST 重新评估下游被阻塞的任务
- **并且** 如果依赖和锁规则得到满足，下游任务可能变为可运行状态。

### Requirement: 调度器 UI 追踪
系统 MUST 在现有任务时间线或执行跟踪 UI 界面中展示调度器状态。

#### Scenario: 任务正在等待依赖项
- **WHEN** 任务正在等待依赖项
- **THEN** UI MUST 显示等待依赖状态
- **并且** UI MUST 在可用时识别该依赖项。

#### Scenario: 任务正在等待目标锁
- **WHEN** 任务正在等待目标写入锁
- **THEN** UI MUST 显示等待目标锁状态
- **并且** UI MUST 标识被锁定的目标 ID。

#### Scenario: 下游任务被阻塞
- **WHEN** 下游任务因上游故障被阻塞
- **THEN** UI MUST 显示阻塞状态
- **并且** UI MUST 在现有 API 支持的情况下保留重试和兜底操作。

#### Scenario: 调度器追踪与制品共存
- **WHEN** 调度器状态在 UI 中显示
- **THEN** 现有制品面板行为 MUST 保持可用
- **并且** Diff、Review、Preview 和 Mock Deploy 制品卡片 MUST 保持可用。

### Requirement: P8 基线保留
系统 MUST 保留 P6/P7 本地工作区行为，同时增加了依赖感知调度和目标锁。

#### Scenario: 执行 P8 冻结评审
- **WHEN** P8 已审核冻结
- **THEN** 迷你 CRM 路径 MUST 仍生成合同、后端任务、前端任务、审查、预览和模拟部署证据
- **且** 目标锁定 MUST 保护 `demo-frontend` 和 `demo-backend`
- **且** 失败依赖 MUST 阻塞下游任务
- **且** 普通后端任务 MUST 不得修改 `apps/api`
- **且** `agenthub-platform` 执行 MUST 保持显式平台模式与审批门控
- **且** P8 MUST 不得声称具备分布式工作节点、多用户即时通讯、生产部署、Docker 沙箱、PR 创建、提供商市场或任意 SaaS 生成能力。
