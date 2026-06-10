## ADDED Requirements
### Requirement: Policy Engine 返回统一策略决策
系统 SHALL 提供统一 Policy Engine，用于返回 allow、deny、require_approval 或 require_elevated_approval 决策。

#### Scenario: 允许安全操作
- **WHEN** 请求的命令、路径或操作符合 target/profile/guardrail 配置
- **THEN** Policy Engine MUST 返回 `allow`
- **且** 决策 MUST 包含 category、reason、risk level 和 safe metadata

#### Scenario: 拒绝不安全操作
- **WHEN** 请求触及受保护路径、未配置命令、target 外路径或禁止操作
- **THEN** Policy Engine MUST 返回 `deny`
- **且** 系统 MUST 不得创建绕过 Target Registry、PlanValidator 或 Guardrails 的执行任务

#### Scenario: 普通风险需要审批
- **WHEN** 请求需要外部网络、成本超阈值、手动部署交接或未明确授权的高风险步骤
- **THEN** Policy Engine SHOULD 返回 `require_approval`
- **且** approval evidence MUST 说明 requested action 和 risk level

#### Scenario: 平台维护或破坏性操作需要高级审批
- **WHEN** 请求修改 AgentHub platform target、执行破坏性 host 操作或触发 platform maintenance
- **THEN** Policy Engine MUST 返回 `require_elevated_approval`
- **且** 普通 runtime config 或 agent profile MUST 不得绕过该结果

### Requirement: Command Policy 复用 target/profile 配置
系统 SHALL 使用 target/profile 配置命令判断项目命令是否可执行。

#### Scenario: 配置命令匹配时允许
- **WHEN** command type 和 command 与 target/profile 配置完全匹配
- **THEN** command policy decision MUST 为 `allow`

#### Scenario: 命令缺失或不匹配时拒绝
- **WHEN** target/profile 没有配置该 command type 或请求命令不匹配
- **THEN** command policy decision MUST 为 `deny`
- **且** 系统 MUST 不得猜测替代命令

#### Scenario: Generic Repo 不开放任意命令
- **WHEN** target 使用 Generic Repo profile 且未显式配置命令
- **THEN** command policy decision MUST 为 `deny`
- **且** AgentHub MUST 不得允许任意 shell command agent

### Requirement: Path Policy 保护 target 边界
系统 SHALL 只允许 target-scoped 的安全路径操作。

#### Scenario: allowed path 内路径允许
- **WHEN** path 位于 target allowedPaths 且不匹配 deniedPaths
- **THEN** path policy decision SHOULD 为 `allow`

#### Scenario: protected path 被拒绝
- **WHEN** path 匹配 `.git`、`.env*`、`secrets`、`node_modules`、venv/cache/build 输出或 target 外路径
- **THEN** path policy decision MUST 为 `deny`
- **且** provider-visible evidence MUST 不得暴露受保护 host path

#### Scenario: platform path 需要高级审批
- **WHEN** path 位于 AgentHub platform target 且 platform maintenance 未明确批准
- **THEN** path policy decision MUST 为 `require_elevated_approval` 或 `deny`

### Requirement: Network、Cost、Destructive 和 Deploy Policy 保守默认
系统 SHALL 对外部网络、成本、破坏性变更和部署保持保守默认。

#### Scenario: 外部网络默认需要审批
- **WHEN** 请求需要外部网络访问且没有明确批准上下文
- **THEN** network policy decision MUST 为 `require_approval`

#### Scenario: 成本超阈值需要审批
- **WHEN** 请求的成本或预算风险超过配置阈值
- **THEN** cost policy decision SHOULD 为 `require_approval`

#### Scenario: 破坏性变更需要高级审批或拒绝
- **WHEN** 请求删除大量文件、执行 `rm -rf`、修改迁移/配置或重写项目结构
- **THEN** destructive policy decision MUST 为 `require_elevated_approval` 或 `deny`

#### Scenario: 生产部署不被默认允许
- **WHEN** 请求生产部署或第三方云部署
- **THEN** deploy policy decision MUST 不得默认为 `allow`
- **且** 系统 MUST 不得伪造第三方部署成功

### Requirement: Approval 超时默认拒绝
系统 SHALL 在审批等待超时时默认拒绝。

#### Scenario: 普通审批超时
- **WHEN** approval wait 超过配置时间且用户没有批准
- **THEN** Policy Engine MUST 返回或记录 `deny`
- **且** 系统 MUST 不得因前端断开、SSE 失败或审批通道异常而放行

#### Scenario: Evidence 脱敏
- **WHEN** policy decision 被记录到 evidence、MissionTrace 或 Diagnostics
- **THEN** safe metadata MUST 不得包含 raw secrets、tokens、API keys、`.env` 内容或未授权 host paths
