## ADDED Requirements

### Requirement: TaskRun 创建交付 checkpoint evidence

系统 SHALL 为可写 TaskRun 提供可审计的交付 checkpoint evidence。

#### Scenario: TaskRun 有 checkpoint
- **WHEN** TaskRun 创建并进入可写执行路径
- **THEN** delivery evidence SHOULD 包含 checkpoint id、worktree、target id 和 allowed paths
- **AND** evidence MUST 不包含 secrets 或受保护 host paths

#### Scenario: 缺少 checkpoint 时拒绝 rollback
- **WHEN** 用户请求 rollback 但 TaskRun 没有 checkpoint evidence
- **THEN** 系统 MUST 拒绝 rollback
- **AND** MUST 记录 `delivery.rollback_refused` 或等效事件

### Requirement: Validation failure 进入 review_required

系统 SHALL 在交付验证失败时进入 review_required，而不是宣称交付成功。

#### Scenario: Command evidence 失败
- **WHEN** build/test/check command evidence 失败
- **THEN** delivery state MUST 为 `review_required` 或等效失败状态
- **AND** 系统 MUST NOT 声称 coding task fully delivered

#### Scenario: Diff 或 review 证据失败
- **WHEN** diff collection failed、review high risk 或 evidence 不足
- **THEN** delivery gate SHOULD 进入 `review_required`
- **AND** diagnostics SHOULD 能展示 delivery validation 问题

#### Scenario: Validation failure 不启动成功后处理
- **WHEN** delivery validation failed
- **THEN** preview/deploy ready evidence MUST NOT 被当成成功交付结果

### Requirement: Accept 记录 artifact state

系统 SHALL 在用户接受交付时记录当前 artifact state。

#### Scenario: Accept 记录证据
- **WHEN** 用户接受 TaskRun 交付
- **THEN** delivery evidence MUST 记录 diff artifact ids、review artifact ids、command evidence ids、acceptedAt 和 acceptedBy
- **AND** accept MUST NOT 伪造 provider success

### Requirement: Rollback 恢复 checkpoint

系统 SHALL 支持基于 checkpoint 的安全 rollback。

#### Scenario: Rollback 成功
- **WHEN** checkpoint 存在且 rollback 路径在 target allowed paths 内
- **THEN** 系统 SHOULD 恢复 checkpoint 状态
- **AND** MUST 记录 `delivery.rolled_back` evidence

#### Scenario: Rollback 拒绝不安全路径
- **WHEN** rollback 会触碰 target denied paths、platform code、其他 session worktree 或受保护路径
- **THEN** 系统 MUST 拒绝 rollback
- **AND** MUST 记录拒绝原因

### Requirement: Retry 显式选择状态来源

系统 SHALL 明确 retry 基于 current state 还是 checkpoint。

#### Scenario: Retry current state
- **WHEN** 用户选择 retry from current state
- **THEN** retry evidence MUST 记录 `retry_from_current_state`

#### Scenario: Retry checkpoint
- **WHEN** 用户选择 retry from checkpoint
- **THEN** retry evidence MUST 记录 `retry_from_checkpoint`
- **AND** 如果需要先 rollback，系统 MUST 明确记录该行为

### Requirement: V2.6 保留既有可靠性和安全边界

系统 SHALL 保留 V2.1、V2.3、V2.5 和 V2.7 基线。

#### Scenario: 不重写执行内核
- **WHEN** 实现 transactional delivery
- **THEN** 系统 MUST NOT 重写 durable worker、provider gateway、session queue、target lock 或 diagnostics

#### Scenario: 不绕过安全策略
- **WHEN** accept、rollback 或 retry 被请求
- **THEN** 系统 MUST 继续遵守 Target Registry、PlanValidator、Guardrails 和 Policy Engine 决策
