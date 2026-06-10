## ADDED Requirements
### Requirement: 目标注册表数据源
系统 MUST 提供一个目标项目注册表，作为受支持执行目标（包括演示前端、演示后端和 AgentHub 平台目标）的真实数据源。

#### Scenario: 目标注册表已被检查
- **WHEN** 维护者检查目标注册表
- **THEN** 它包含一个针对 `apps/demo` 的 `demo-frontend` 目标
- **并且** 包含一个针对 `apps/demo-api` 的 `demo-backend` 目标
- **并且** 包含一个针对 AgentHub 平台代码的 `agenthub-platform` 目标
- **并且** 每个目标在适用时包含目标 ID、名称、类型、根目录、允许路径、
  禁止路径、命令、允许的代理以及 approval/platform-mode 元数据。

#### Scenario: 演示后端目标已解析
- **WHEN** 系统解析 `demo-backend` 目标
- **THEN** 目标类型为 `backend`
- **且** 根路径为 `apps/demo-api`
- **且** 基础 URL 为 `http://127.0.0.1:5174`
- **且** 普通后端应用工作仅允许在演示后端目标的允许路径内进行
- **且** 普通演示后端工作禁止使用 `apps/api`。

#### Scenario: AgentHub 平台目标已解析
- **WHEN** 系统解析 `agenthub-platform` 目标
- **THEN** 目标类型为 `platform`
- **且** 目标要求显式平台模式
- **且** 目标在适配器执行前需要审批
- **且** 目标使用比普通应用目标更严格的验证。

### Requirement: 目标感知合约规划
系统 MUST 通过引用目标 ID 和注册表解析的元数据，为有界全栈应用请求生成目标感知的应用合约和任务。

#### Scenario: 编排器规划一个迷你 CRM 请求
- **WHEN** 用户请求一个受支持的迷你 CRM 联系人应用
- **THEN** 编排器创建一个应用合约，其中 `frontendTargetId` 设置为 `demo-frontend`
- **并且** 该应用合约的 `backendTargetId` 设置为 `demo-backend`
- **并且** 该应用合约使用目标注册表中的演示后端基础 URL
- **并且** 生成的前端和后端任务引用其目标 ID
- **并且** 生成的任务还包含已解析的安全路径，以兼容现有执行路径。

#### Scenario: 请求了不支持的目标操作
- **WHEN** 用户请求的操作无法映射到受支持的目标
- **THEN** 系统MUST不得静默执行适配器运行
- **并且** 它MUST应请求澄清或返回诚实的“不支持”响应。

### Requirement: 目标感知指令
系统 MUST 根据目标注册表元数据构建角色指令，而非分散的硬编码路径和 URL。

#### Scenario: 前端 Agent 指令专为全栈应用工作而构建
- **WHEN** 前端任务的目标是 `demo-frontend`，并引用了后端目标
- **THEN** 指令要求代理仅在 `demo-frontend` 允许的路径内工作
- **并且** 指令包含注册表解析后的后端基础 URL
- **并且** 指令要求代理不得为生成的应用程序数据调用 AgentHub 平台 API。

#### Scenario: 后端 Agent 指令专为应用后端工作构建
- **WHEN** 后端任务的目标是 `demo-backend`
- **THEN** 指令要求智能体仅在
  `demo-backend` 允许的路径内工作
- **并且** 指令要求智能体不得修改 `apps/api`
- **并且** 当目标注册表中存在演示后端验证命令时，指令需包含该命令。

#### Scenario: 平台维护指令已构建
- **WHEN** 任务的目标是 `agenthub-platform`
- **THEN** 指令将该任务标识为平台维护
- **并且** 包含更严格的验证预期
- **并且** 声明需要平台模式与审批。

### Requirement: 权限化执行边界
系统 MUST 对适配器任务强制执行目标感知的执行边界，并
MUST 保留受保护路径的防护措施。

#### Scenario: 普通后端任务尝试平台变更
- **WHEN** 一个普通应用后端任务的目标是 `demo-backend`
- **并且** 该任务或生成的差异试图修改 `apps/api`
- **THEN** 系统 MUST 报告目标策略违规
- **并且** 系统 MUST 未声明无限制的后端成功。

#### Scenario: 前端任务编辑超出允许路径
- **WHEN** 前端任务的目标为 `demo-frontend`
- **且** 生成的差异包含目标允许路径之外的文件
- **THEN** 审查 MUST 报告允许路径违规
- **且** 受保护路径（如 `.env`、`.git`、`node_modules` 和 `secrets`）
  MUST 保持拒绝访问状态。

#### Scenario: 明确请求平台维护
- **WHEN** 用户明确请求 AgentHub 平台维护模式
- **THEN** 系统可以创建一个针对 `agenthub-platform` 的任务
- **并且** 任务 MUST 在适配器执行前需要审批
- **并且** 任务 MUST 使用平台目标的更严格验证预期。

### Requirement: 目标感知审查与质量保证
系统 MUST 根据目标注册表策略审查差异和应用合约。

#### Scenario: 全栈差异已审查
- **WHEN** 全栈应用差异已审查
- **THEN** 审查检查前端变更文件是否位于前端目标允许路径内
- **且** 审查检查后端变更文件是否位于后端目标允许路径内
- **且** 审查检查禁止路径未被修改
- **且** 审查检查契约目标 ID 是否与任务目标 ID 匹配。

#### Scenario: 前端调用了错误的后端基础 URL
- **WHEN** 前端差异调用了一个后端基础 URL，该 URL 与注册表解析的后端目标基础 URL 不匹配
- **THEN** 审查 MUST 报告后端基础 URL 不匹配
- **并且** 发现结果 SHOULD 标识了预期的目标基础 URL。

#### Scenario: 最终 P6 迷你 CRM 路径通过 P7 进行审查
- **WHEN** P6 迷你 CRM 垂直切片通过目标注册表元数据进行演练
- **THEN** 当累积差异仅涉及允许的 `demo-frontend` 和 `demo-backend` 路径时，评审通过
- **并且** 前端使用注册表解析的 `demo-backend` 基础 URL
- **并且** 模拟部署保持标记为模拟状态。

### Requirement: P7 基线保留
系统 MUST 保留 P4/P5/P6 本地单用户工作区基线，
同时添加目标注册表和权限化执行。

#### Scenario: 执行 P7 冻结评审
- **WHEN** P7 已审核完毕，准备冻结
- **THEN** P6 迷你 CRM 垂直切片仍能通过目标注册表元数据正常工作
- **并且** `CodexAdapter`、`ClaudeCodeAdapter` 和 `ScriptedMockAdapter` 仍然是有效的适配器
- **并且** 普通应用任务仍限定在演示目标范围内
- **并且** 平台代码变更被阻止或需审批，除非显式启用平台模式
- **并且** P7 不声称支持多用户即时通讯、生产部署、Docker 沙箱、PR 创建、无限制仓库编辑、分布式调度或任意 SaaS 生成。
