## ADDED Requirements
### Requirement: TaskRun 创建交付检查点证据
系统 SHALL 为可写 TaskRun 提供可审计的交付检查点证据。

#### Scenario: TaskRun 有检查点
- **WHEN** TaskRun 创建并进入可写执行路径
- **THEN** 交付证据 SHOULD 包含检查点 ID、工作树、目标 ID 和允许路径
- **并且** 证据 MUST 不包含密钥或受保护的主机路径

#### Scenario: 缺少检查点时拒绝回滚
- **WHEN** 用户请求回滚但 TaskRun 没有检查点证据
- **THEN** 系统 MUST 拒绝回滚
- **并且** MUST 记录 `delivery.rollback_refused` 或等效事件

### Requirement: 验证失败进入 review_required
系统 SHALL 在交付验证失败时进入 review_required，而不是宣称交付成功。

#### Scenario: 命令证据失败
- **WHEN** build/test/check 命令证据失败
- **THEN** 交付状态 MUST 为 `review_required` 或等效失败状态
- **并且** 系统 MUST 不得声称编码任务已完全交付

#### Scenario: 差异或审查证据失败
- **WHEN** 差异收集失败、审查高风险或证据不足
- **THEN** 交付门禁 SHOULD 进入 `review_required`
- **并且** 诊断信息 SHOULD 能展示交付验证问题

#### Scenario: 验证失败不启动成功后处理
- **WHEN** 交付验证失败
- **THEN** preview/deploy 就绪证据 MUST 不得被视为成功交付结果

### Requirement: 接受记录制品状态
系统 SHALL 在用户接受交付时记录当前制品状态。

#### Scenario: 接受记录证据
- **WHEN** 用户接受 TaskRun 交付
- **THEN** 交付证据 MUST 记录差异制品 ID、审查制品 ID、命令证据 ID、acceptedAt 和 acceptedBy
- **并且** 接受操作 MUST 不得伪造提供商成功

### Requirement: 回滚恢复检查点
系统 SHALL 支持基于检查点的安全回滚。

#### Scenario: 回滚成功
- **WHEN** 检查点存在且回滚路径在目标允许路径内
- **THEN** 系统 SHOULD 恢复检查点状态
- **并且** MUST 记录 `delivery.rolled_back` 证据

#### Scenario: 回滚拒绝不安全路径
- **WHEN** 回滚会触碰目标拒绝路径、平台代码、其他会话工作树或受保护路径
- **THEN** 系统 MUST 拒绝回滚
- **并且** MUST 记录拒绝原因

### Requirement: 重试显式选择状态来源
系统 SHALL 明确重试基于当前状态还是检查点。

#### Scenario: 重试当前状态
- **WHEN** 用户选择从当前状态重试
- **THEN** 重试证据 MUST 记录 `retry_from_current_state`

#### Scenario: 重试检查点
- **WHEN** 用户选择从检查点重试
- **THEN** 重试证据 MUST 记录 `retry_from_checkpoint`
- **并且** 如果需要先回滚，系统 MUST 明确记录该行为

### Requirement: V2.6 保留既有可靠性和安全边界
系统 SHALL 保留 V2.1、V2.3、V2.5 和 V2.7 基线。

#### Scenario: 不重写执行内核
- **WHEN** 实现事务性交付
- **THEN** 系统 MUST 不得重写持久化工作器、提供商网关、会话队列、目标锁或诊断功能

#### Scenario: 不绕过安全策略
- **WHEN** 接受、回滚或重试被请求
- **THEN** 系统 MUST 继续遵守目标注册表、计划验证器、护栏和策略引擎决策
