## ADDED Requirements
### Requirement: 命令允许列表强制执行
系统 MUST 在 P0 适配器、差异对比、预览和部署流程中仅执行允许列表中的命令。

#### Scenario: 请求了未列入白名单的命令
- **GIVEN** 适配器或脚本请求了白名单之外的命令
- **WHEN** 后端评估该命令
- **THEN** 命令被阻止
- **并且** 根据策略发出审批请求或错误

### Requirement: 受保护路径强制机制
系统 MUST 保护 `.git/`、`.env`、`.env.*`、`secrets/`、`node_modules/` 及系统路径免受未经批准的编辑。

#### Scenario: 适配器尝试编辑受保护路径
- **GIVEN** 任务运行处于活跃状态
- **WHEN** 提议的文件操作指向受保护路径
- **THEN** 除非显式审批策略允许，否则后端会阻止该操作
- **并且** UI 显示审批或错误状态

### Requirement: 审批请求载荷
系统 MUST 使用 ApprovalRequestPayload 表示审批请求，其中包含 `approvalType`、`reason`、`requestedAction`、`riskLevel` 以及可选的 `command`、`path` 和 `expiresAt`。

#### Scenario: 请求安全审批
- **GIVEN** 适配器请求一个高风险操作
- **WHEN** 后端发出 `approval.requested`
- **THEN** 事件负载标识其为 `product_confirmation` 或 `security_approval`
- **并且** 包含原因、请求的操作、风险等级以及任何相关命令或路径

### Requirement: 需审批的操作
系统 MUST 要求对部署、Git 推送、删除文件、编辑受保护路径、运行未列入白名单的命令以及网络访问进行审批。

#### Scenario: 部署需要审批
- **GIVEN** 预览已成功
- **WHEN** 用户发起实际部署操作
- **THEN** 系统在执行部署前请求审批
- **并且** 相关的 TaskRun 可以进入 `waiting_approval` 状态

### Requirement: 等待审批状态
当审批请求处于待处理状态时，系统 MUST 将相关的 Task 和 TaskRun 移至 `waiting_approval`。

#### Scenario: 用户审批待处理
- **GIVEN** TaskRun 发出审批请求
- **WHEN** 审批尚未被批准、拒绝、过期、失败或中断
- **THEN** TaskRun 保持 `waiting_approval` 状态
- **并且** UI 显示包含批准和拒绝操作的审批卡片

### Requirement: 默认关闭网络
系统 MUST 在 P0 智能体执行期间默认保持网络访问关闭，仅支持可选的允许列表行为。

#### Scenario: 适配器请求网络访问
- **GIVEN** 一个任务运行处于活跃状态，且具有默认权限
- **WHEN** 适配器请求网络访问
- **THEN** 除非已列入白名单并获得批准，否则系统会阻止该访问

### Requirement: 禁止任意主机访问
系统 MUST 不得在 P0 阶段授予完全的主机访问权限、任意 shell 执行、无限制的后台进程或未经审查的部署。

#### Scenario: 脚本请求任意 shell
- **GIVEN** `ScriptedMockAdapter` 正在执行
- **WHEN** 其脚本请求任意 shell 访问权限
- **THEN** 后端拒绝该操作
- **并且** 任务运行记录护栏错误或审批状态

### Requirement: 基础审批 UI
系统 MUST 为待审批请求提供基础审批 UI。

#### Scenario: 用户批准请求的操作
- **GIVEN** 聊天流中显示一条审批请求
- **WHEN** 用户批准该请求
- **THEN** 后端调用适配器 `approve`
- **并且** 任务运行可以从 `waiting_approval` 继续执行
