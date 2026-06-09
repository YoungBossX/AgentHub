## ADDED Requirements

### Requirement: TaskRun 暴露运行诊断摘要

系统 SHALL 为 TaskRun 提供安全、用户可读的运行诊断摘要，而不是只暴露终态或
error code。

#### Scenario: 失败运行显示分类后的主因
- **WHEN** TaskRun 进入 failed、interrupted、timed out 或 blocked 等非成功状态
- **THEN** 诊断摘要 MUST 包含 primary failure category、用户可读说明、severity 和 retryability
- **AND** 原始 error code MAY 作为辅助字段保留
- **AND** UI MUST NOT 只显示裸 `failed` 或 `errorCode`

#### Scenario: 成功运行显示关键健康信号
- **WHEN** TaskRun completed
- **THEN** 诊断摘要 SHOULD 显示 provider、queue、lock、preview 和 deploy 的关键健康状态
- **AND** 如果 preview 或 deploy 后处理失败，诊断 MUST 将其显示为 contributing factor
- **AND** 系统 MUST NOT 因后处理失败而伪造编码 provider 失败或成功

#### Scenario: 证据不足时保守显示 unknown
- **WHEN** 系统缺少足够事件判断失败原因
- **THEN** primary failure category MUST 为 `unknown` 或等效保守分类
- **AND** 诊断 MUST 提供查看事件、日志或重试的安全建议
- **AND** 系统 MUST NOT 推断未验证的 provider 成功

### Requirement: Run Timeline 展示执行阶段

系统 SHALL 为 TaskRun 构建按时间排序的 Run Timeline，帮助用户理解运行卡在哪个阶段。

#### Scenario: Timeline 包含关键执行阶段
- **WHEN** 用户查看 TaskRun 诊断
- **THEN** timeline SHOULD 包含 queued、scheduler_check、dependency_wait、lock_wait、approval_wait、validation、provider_check、worker_claim、adapter_start、adapter_stream、adapter_finish、artifact_collection、diff、review、preview、deploy、finalize、recovery 中适用的阶段
- **AND** 每个 timeline item MUST 包含 timestamp、phase、status、title、description 和 source

#### Scenario: Timeline 关联制品
- **WHEN** 某个 timeline 阶段产生 diff、review、preview 或 deployment evidence
- **THEN** timeline item SHOULD 包含安全 artifact reference
- **AND** 用户 MUST 能从诊断 UI 打开对应制品

#### Scenario: Timeline 不泄露敏感信息
- **WHEN** timeline item 来自 provider stderr、adapter stream、路径错误或部署日志
- **THEN** 系统 MUST 对 secrets、tokens、API keys、受保护 host paths 和过长日志做脱敏或摘要化

### Requirement: Failure 分类覆盖常见运行失败

系统 SHALL 将常见运行失败映射到稳定的 failure category。

#### Scenario: Provider 失败被分类
- **WHEN** provider 因认证、配额、不可用、配置缺失或 gateway fallback 失败导致运行失败
- **THEN** 诊断 MUST 将主因分类为 provider_auth、provider_quota、provider_unavailable 或等效 provider 分类
- **AND** fallback 成功 MUST 明确标记为 fallback，而不是真实 provider 成功

#### Scenario: Adapter 超时或中断被分类
- **WHEN** adapter 因 max runtime、idle timeout、用户 interrupt 或系统 interrupt 结束
- **THEN** 诊断 MUST 将主因分类为 adapter_timeout 或 adapter_interrupted
- **AND** timeline MUST 展示 timeout 或 interrupt 发生的阶段

#### Scenario: Worktree 与 artifact 收集失败被分类
- **WHEN** worktree dirty、diff 收集失败、受保护路径拒绝或 artifact collector 失败导致运行不可完成
- **THEN** 诊断 MUST 将主因或 contributing factor 分类为 worktree_dirty、validation_failed 或 artifact_collection_failed
- **AND** 诊断 MUST 不暴露受保护 host path

#### Scenario: 调度、锁、审批和验证失败被分类
- **WHEN** 运行因 dependency blocked、queue stale、target lock timeout、validation failed 或 approval denied 停止
- **THEN** 诊断 MUST 分类为 queue_blocked、queue_stale、lock_timeout、validation_failed 或 approval_denied
- **AND** health summary SHOULD 展示对应子系统的 blocked 或 failed 状态

#### Scenario: Preview 和 deploy 失败被分类
- **WHEN** preview build/dev server/health check 失败或 deploy provider blocked/failed
- **THEN** 诊断 MUST 分类为 preview_failed、deploy_failed 或 deploy_blocked
- **AND** 如果编码运行本身已成功，preview/deploy 失败 MUST 作为后处理问题显示

### Requirement: Health Summary 汇总关键子系统状态

系统 SHALL 在运行诊断中汇总 provider、queue、lock、preview 和 deploy 健康状态。

#### Scenario: Provider health 显示真实 provider 状态
- **WHEN** 诊断包含 provider health
- **THEN** 它 MUST 显示 provider id、adapter type、auth/config 状态、availability 和 fallback 状态
- **AND** 它 MUST 区分真实 provider 成功、真实 provider 失败和 fallback 成功

#### Scenario: Queue health 显示 worker 与 lease 状态
- **WHEN** 诊断包含 queue health
- **THEN** 它 SHOULD 显示 queued 时长、worker claim、last heartbeat、lease expiry 和 stale recovery 状态

#### Scenario: Lock health 显示目标锁状态
- **WHEN** 运行等待或失败于目标锁
- **THEN** lock health MUST 显示目标 ID、锁状态、等待时长和 timeout 信息
- **AND** 不同 Session 的 worktree MUST NOT 被错误归为同一个锁健康信号

#### Scenario: Preview 和 deploy health 显示后处理状态
- **WHEN** 运行产生 preview 或 deployment evidence
- **THEN** health summary MUST 显示 preview status、preview URL 可用性、deployment provider、environment、status 和 source artifact reference
- **AND** blocked 外部部署 MUST 显示为 blocked 或 failed，不得显示为生产部署成功

### Requirement: Next-step Suggestions 可行动且诚实

系统 SHALL 基于诊断分类生成下一步建议。

#### Scenario: Provider 问题给出设置或 fallback 建议
- **WHEN** primary failure 属于 provider_auth、provider_quota 或 provider_unavailable
- **THEN** suggestions SHOULD 包含检查 runtime/provider 设置、等待或切换 provider、选择可用 fallback 的建议
- **AND** fallback 建议 MUST 明确说明它不是真实 provider 成功

#### Scenario: Timeout 或 dirty worktree 给出重试范围建议
- **WHEN** primary failure 属于 adapter_timeout 或 worktree_dirty
- **THEN** suggestions SHOULD 包含查看 timeline/log、缩小任务范围、查看 diff、重试或创建新 Session 的建议

#### Scenario: Validation 或 approval 问题不绕过安全边界
- **WHEN** primary failure 属于 validation_failed 或 approval_denied
- **THEN** suggestions MUST NOT 建议绕过 PlanValidator、Target Registry、approval 或 protected path 规则
- **AND** suggestions SHOULD 建议修改需求、请求审批或选择允许的目标

#### Scenario: Preview 或 deploy 问题链接到对应制品
- **WHEN** primary failure 或 contributing factor 属于 preview_failed、deploy_failed 或 deploy_blocked
- **THEN** suggestions SHOULD 包含打开 preview/deploy 制品、查看日志、选择 local staging/manual handoff 或补全 provider 配置的建议

### Requirement: 诊断 API 与 UI 保持安全兼容

系统 SHALL 通过安全 API 和前端 UI 展示 Run Diagnostics，同时保持现有 demo 边界。

#### Scenario: API 响应稳定且脱敏
- **WHEN** 前端请求 TaskRun 或 Session 诊断
- **THEN** API MUST 返回稳定字段，包含 summary、timeline、health summary 和 suggestions
- **AND** API MUST 对 secrets、tokens、API keys、受保护 host paths、`.env` 内容和过长日志做脱敏或省略

#### Scenario: 旧 TaskRun 仍可显示诊断
- **WHEN** TaskRun 缺少新诊断 metadata 或旧事件不完整
- **THEN** 系统 MUST 构建 best-effort 诊断
- **AND** UI MUST 显示 unknown/limited evidence 状态，而不是崩溃

#### Scenario: UI 保留现有制品与操作
- **WHEN** 用户查看包含诊断的任务卡片或右侧面板
- **THEN** 现有 diff、review、preview、deploy 制品卡片 MUST 保持可用
- **AND** retry、interrupt、approval、fallback 等现有操作 MUST 按当前规则继续生效

#### Scenario: V2.7 不扩大平台能力
- **WHEN** 实现 Run Diagnostics
- **THEN** 系统 MUST 保留 SQLite、本地单用户、SSE、Vite React preview 和 mock-backed deploy demo 边界
- **AND** 系统 MUST NOT 新增 WebSocket、Docker sandbox、PR 创建、外部 IM 集成、provider marketplace 或新 adapter
