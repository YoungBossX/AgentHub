## ADDED Requirements
### Requirement: TaskRun 暴露运行诊断摘要
系统 SHALL 应为 TaskRun 提供安全、用户可读的运行诊断摘要，而不是只暴露终态或错误码。

#### Scenario: 失败运行显示分类后的主因
- **WHEN** TaskRun 进入 failed、interrupted、timed out 或 blocked 等非成功状态
- **THEN** 诊断摘要 MUST 包含主失败类别、用户可读说明、严重程度和可重试性
- **并且** 原始错误码可作为辅助字段保留
- **并且** UI MUST 不得只显示裸 `failed` 或 `errorCode`

#### Scenario: 成功运行显示关键健康信号
- **WHEN** TaskRun 已完成
- **THEN** 诊断摘要 SHOULD 显示 provider、queue、lock、preview 和 deploy 的关键健康状态
- **并且** 如果 preview 或 deploy 后处理失败，诊断 MUST 应将其显示为促成因素
- **并且** 系统 MUST 不得因后处理失败而伪造编码 provider 失败或成功

#### Scenario: 证据不足时保守显示 unknown
- **WHEN** 系统缺少足够事件判断失败原因
- **THEN** 主失败类别 MUST 应为 `unknown` 或等效保守分类
- **并且** 诊断 MUST 应提供查看事件、日志或重试的安全建议
- **并且** 系统 MUST 不得推断未验证的 provider 成功

### Requirement: 运行时间线展示执行阶段
系统 SHALL 应为 TaskRun 构建按时间排序的运行时间线，帮助用户理解运行卡在哪个阶段。

#### Scenario: 时间线包含关键执行阶段
- **WHEN** 用户查看 TaskRun 诊断
- **THEN** 时间线 SHOULD 应包含 queued、scheduler_check、dependency_wait、lock_wait、approval_wait、validation、provider_check、worker_claim、adapter_start、adapter_stream、adapter_finish、artifact_collection、diff、review、preview、deploy、finalize、recovery 中适用的阶段
- **并且** 每个时间线项 MUST 应包含时间戳、阶段、状态、标题、描述和来源

#### Scenario: 时间线关联制品
- **WHEN** 某个时间线阶段产生 diff、review、preview 或部署证据
- **THEN** 时间线项 SHOULD 应包含安全的制品引用
- **并且** 用户 MUST 应能从诊断 UI 打开对应制品

#### Scenario: 时间线不泄露敏感信息
- **WHEN** 时间线项来自 provider stderr、adapter stream、路径错误或部署日志
- **THEN** 系统 MUST 应对 secrets、tokens、API keys、受保护主机路径和过长日志做脱敏或摘要化

### Requirement: 失败分类覆盖常见运行失败
系统 SHALL 应将常见运行失败映射到稳定的失败类别。

#### Scenario: Provider 失败被分类
- **WHEN** provider 因认证、配额、不可用、配置缺失或网关兜底失败导致运行失败
- **THEN** 诊断 MUST 应将主因分类为 provider_auth、provider_quota、provider_unavailable 或等效 provider 分类
- **并且** 兜底成功 MUST 应明确标记为兜底，而不是真实 provider 成功

#### Scenario: 适配器超时或中断被分类
- **WHEN** 适配器因最大运行时间、空闲超时、用户中断或系统中断结束
- **THEN** 诊断 MUST 应将主因分类为 adapter_timeout 或 adapter_interrupted
- **并且** 时间线 MUST 应展示超时或中断发生的阶段

#### Scenario: 工作树与制品收集失败被分类
- **WHEN** 工作树脏、diff 收集失败、受保护路径拒绝或制品收集器失败导致运行不可完成
- **THEN** 诊断 MUST 应将主因或促成因素分类为 worktree_dirty、validation_failed 或 artifact_collection_failed
- **并且** 诊断 MUST 不应暴露受保护主机路径

#### Scenario: 调度、锁、审批和验证失败被分类
- **WHEN** 运行因依赖阻塞、队列过期、目标锁超时、验证失败或审批拒绝停止
- **THEN** 诊断 MUST 应分类为 queue_blocked、queue_stale、lock_timeout、validation_failed 或 approval_denied
- **并且** 健康摘要 SHOULD 应展示对应子系统的阻塞或失败状态

#### Scenario: 预览和部署失败被分类
- **WHEN** 预览 build/dev server/health 检查失败或部署 provider blocked/failed
- **THEN** 诊断 MUST 应分类为 preview_failed、deploy_failed 或 deploy_blocked
- **并且** 如果编码运行本身已成功，preview/deploy 失败 MUST 应作为后处理问题显示

### Requirement: 健康摘要汇总关键子系统状态
系统 SHALL 应在运行诊断中汇总 provider、queue、lock、preview 和 deploy 健康状态。

#### Scenario: Provider 健康显示真实 provider 状态
- **WHEN** 诊断包含 provider 健康
- **THEN** 它 MUST 应显示 provider id、适配器类型、auth/config 状态、可用性和兜底状态
- **并且** 它 MUST 应区分真实 provider 成功、真实 provider 失败和兜底成功

#### Scenario: 队列健康显示 worker 与租约状态
- **WHEN** 诊断包含队列健康
- **THEN** 它 SHOULD 应显示排队时长、worker 认领、最后心跳、租约过期和过期恢复状态

#### Scenario: 锁健康显示目标锁状态
- **WHEN** 运行等待或失败于目标锁
- **THEN** 锁健康 MUST 应显示目标 ID、锁状态、等待时长和超时信息
- **并且** 不同会话的工作树 MUST 不得被错误归为同一个锁健康信号

#### Scenario: 预览和部署健康显示后处理状态
- **WHEN** 运行产生预览或部署证据
- **THEN** 健康摘要 MUST 应显示预览状态、预览 URL 可用性、部署 provider、环境、状态和源制品引用
- **并且** 阻塞的外部部署 MUST 应显示为 blocked 或 failed，不得显示为生产部署成功

### Requirement: 下一步建议可行动且诚实
系统 SHALL 应基于诊断分类生成下一步建议。

#### Scenario: Provider 问题给出设置或兜底建议
- **WHEN** 主失败属于 provider_auth、provider_quota 或 provider_unavailable
- **THEN** 建议 SHOULD 应包含检查 runtime/provider 设置、等待或切换 provider、选择可用兜底的建议
- **并且** 兜底建议 MUST 应明确说明它不是真实 provider 成功

#### Scenario: 超时或脏工作树给出重试范围建议
- **WHEN** 主失败属于 adapter_timeout 或 worktree_dirty
- **THEN** 建议 SHOULD 应包含查看 timeline/log、缩小任务范围、查看 diff、重试或创建新会话的建议

#### Scenario: 验证或审批问题不绕过安全边界
- **WHEN** 主失败属于 validation_failed 或 approval_denied
- **THEN** 建议 MUST 不得建议绕过 PlanValidator、Target Registry、approval 或 protected path 规则
- **并且** 建议 SHOULD 应建议修改需求、请求审批或选择允许的目标

#### Scenario: 预览或部署问题链接到对应制品
- **WHEN** 主失败或促成因素属于 preview_failed、deploy_failed 或 deploy_blocked
- **THEN** 建议 SHOULD 应包含打开 preview/deploy 制品、查看日志、选择本地 staging/manual 交接或补全 provider 配置的建议

### Requirement: 诊断 API 与 UI 保持安全兼容
系统 SHALL 应通过安全 API 和前端 UI 展示运行诊断，同时保持现有 demo 边界。

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
