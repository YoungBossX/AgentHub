## ADDED Requirements

### Requirement: Coding TaskRun 通过 Provider Gateway 解析 provider

系统 SHALL 在执行 coding adapter 前通过 Provider Gateway 生成 provider resolution
plan，而不是让 Durable Run Engine、endpoint 或零散 helper 直接决定具体 adapter。

#### Scenario: 默认 coding provider 被解析
- **WHEN** Durable Run Engine 准备执行一个 coding TaskRun
- **AND** 用户没有显式指定 provider
- **THEN** Provider Gateway MUST 基于 workspace runtime config、role、target、mode 和 capability 选择 provider
- **AND** 系统 MUST 记录 selected provider 和 selection reason

#### Scenario: 显式 provider 请求被验证
- **WHEN** 用户或任务请求一个具体 coding provider
- **THEN** Provider Gateway MUST 验证该 provider 是否存在、可用于 coding adapter、兼容当前 role/target/mode/capability
- **AND** 不兼容时 MUST 拒绝或选择被策略允许的 fallback
- **AND** 拒绝原因 MUST 被记录为安全证据

#### Scenario: Planner provider 不进入 coding gateway
- **WHEN** workspace 同时配置 Planner provider 和 coding provider
- **THEN** Provider Gateway MUST 只解析 ClaudeCodeAdapter、CodexAdapter、ScriptedMockAdapter 等 coding adapter provider
- **AND** Planner provider MUST NOT 被作为 coding adapter candidate

### Requirement: Provider Registry 暴露安全编码 provider 元数据

系统 SHALL 为 coding providers 提供安全 registry 视图，供 resolution、health、
compatibility 和诊断使用。

#### Scenario: Registry 包含现有 coding adapters
- **WHEN** Provider Gateway 加载 registry
- **THEN** registry MUST 包含 ClaudeCodeAdapter、CodexAdapter 和 ScriptedMockAdapter 对应 provider
- **AND** registry MUST NOT 要求新增 adapter 才能满足 V2.2

#### Scenario: Registry 区分真实 provider 与 mock fallback
- **WHEN** registry 返回 ScriptedMockAdapter 元数据
- **THEN** 它 MUST 标记为 fallback/mock provider
- **AND** 它 MUST NOT 被描述为真实 Claude 或 Codex provider

#### Scenario: Registry 不泄露秘密
- **WHEN** registry metadata 被写入日志、API 响应或 mission trace
- **THEN** metadata MUST NOT 包含 raw API keys、tokens、credentials、secrets 或受保护 host paths

### Requirement: Health Probe 贴近实际启动路径

系统 SHALL 为每个 coding provider 提供健康检查或 probe，且结果必须与实际 adapter
launch path 对齐。

#### Scenario: 真实 provider 健康检查
- **WHEN** Provider Gateway 检查 Claude Code 或 Codex provider
- **THEN** health result MUST 反映配置、CLI 可用性和安全启动前 probe 的结果
- **AND** unknown 或 unavailable MUST 被诚实记录

#### Scenario: fallback 可用不代表真实 provider 健康
- **WHEN** Claude Code 或 Codex health 为 unavailable
- **AND** ScriptedMockAdapter 可用
- **THEN** 系统 MUST NOT 将 Claude Code 或 Codex 标记为 healthy
- **AND** 系统 MAY 将 ScriptedMockAdapter 作为 fallback candidate 记录

#### Scenario: Health evidence 被脱敏
- **WHEN** health probe 产生 stderr、路径或配置摘要
- **THEN** 系统 MUST redacted secrets、tokens、API keys 和受保护 host paths
- **AND** 只保存安全摘要

### Requirement: Provider Gateway 控制并发

系统 SHALL 在启动 coding adapter 前检查 provider/global 并发限制。

#### Scenario: capacity 可用时启动 provider
- **WHEN** selected provider 未超过并发限制
- **THEN** Provider Gateway MUST acquire capacity before launch
- **AND** TaskRun 结束后 MUST release capacity

#### Scenario: capacity 不可用时不启动 adapter
- **WHEN** selected provider 或全局 coding run capacity 已耗尽
- **THEN** Provider Gateway MUST NOT 启动 adapter 子进程
- **AND** 系统 MUST 记录 capacity blocked evidence

#### Scenario: release 幂等
- **WHEN** TaskRun finalizer、recovery 或 late event 多次释放同一 capacity
- **THEN** release MUST 保持幂等
- **AND** 不得让并发计数变成负数或错误允许过量运行

### Requirement: Rate Limit Placeholder 记录限流状态

系统 SHALL 建立 provider rate limit placeholder，用于记录和传播限流状态，即使本阶段
不实现完整外部配额系统。

#### Scenario: provider 报告 rate limit
- **WHEN** adapter 或 health probe 返回可识别的 rate limit 错误
- **THEN** Provider Gateway MUST 将其分类为 `rate_limit`
- **AND** 系统 SHOULD 记录 provider、窗口摘要、next eligible time 或 unknown

#### Scenario: placeholder 不执行外部计费
- **WHEN** Provider Gateway 使用 rate limit placeholder
- **THEN** 系统 MUST NOT 要求 provider marketplace、billing、token budget 或外部 quota sync
- **AND** 它 MUST 保留后续扩展所需的证据字段

### Requirement: Circuit Breaker 阻止冷却中的 provider

系统 SHALL 为 coding providers 提供 circuit breaker，避免连续不可恢复 provider 失败后继续
启动 adapter。

#### Scenario: 连续 provider 失败打开 circuit
- **WHEN** provider 连续出现 auth、quota、rate_limit 或 unavailable 类失败并达到策略阈值
- **THEN** circuit breaker SHOULD 打开该 provider 的 cooldown
- **AND** 系统 MUST 记录 circuit opened evidence

#### Scenario: open circuit 阻止启动
- **WHEN** selected provider 的 circuit 处于 open cooldown
- **THEN** Provider Gateway MUST NOT 启动该 provider adapter
- **AND** 系统 MUST 记录 circuit blocked reason 和 cooldown 信息

#### Scenario: 本地 guardrail 不误开 provider circuit
- **WHEN** TaskRun 因 guardrail 或 dirty_worktree 分类失败
- **THEN** circuit breaker SHOULD NOT 将该失败计为 provider 健康失败
- **AND** 系统 MUST 保留本地安全失败证据

### Requirement: Provider Error Taxonomy 统一失败分类

系统 SHALL 将 coding provider 和 gateway 失败归类到统一 taxonomy。

#### Scenario: 失败被分类
- **WHEN** adapter、health probe、concurrency limiter、circuit breaker 或 gateway control path 失败
- **THEN** ProviderErrorClassifier MUST 产生 category、provider id、retryable、fallbackEligible、circuitBreakerEligible、userMessage 和 safeEvidence

#### Scenario: taxonomy 覆盖核心类别
- **WHEN** 失败被分类
- **THEN** category MUST 是 auth、quota、rate_limit、timeout、format、tool、guardrail、dirty_worktree、unavailable 或 unknown 之一

#### Scenario: unknown 不被包装成成功
- **WHEN** 系统无法识别 provider 失败
- **THEN** category MUST 为 unknown
- **AND** TaskRun MUST NOT 被标记为真实 provider 成功

### Requirement: Fallback Policy 可审计

系统 SHALL 使用明确 FallbackPolicy 决定是否从失败或不可用 provider 切换到 fallback。

#### Scenario: fallback 被选择
- **WHEN** selected provider 因 health、capacity、circuit 或 error taxonomy 无法执行
- **AND** FallbackPolicy 允许 fallback
- **THEN** Provider Gateway MUST 记录 original provider、fallback provider、trigger category 和 reason
- **AND** fallback provider MUST 重新经过兼容性和安全检查

#### Scenario: ScriptedMock fallback 明确标记
- **WHEN** Provider Gateway 使用 ScriptedMockAdapter 执行 fallback
- **THEN** TaskRun evidence MUST 明确标记 `fallback=true` 和 `mock=true`
- **AND** evidence MUST NOT 声称 Claude Code 或 Codex 成功

#### Scenario: fallback 不覆盖原始失败
- **WHEN** 原始 provider 失败后 fallback 成功
- **THEN** 系统 MUST 同时保留原始 provider failure evidence 和 fallback success evidence
- **AND** mission trace MUST 能展示最终执行 adapter 与原始失败 provider 不同

#### Scenario: fallback 不被允许时诚实失败
- **WHEN** selected provider 失败
- **AND** FallbackPolicy 不允许 fallback 或没有可用 fallback
- **THEN** TaskRun MUST 进入诚实失败状态
- **AND** 系统 MUST 记录无 fallback 的原因

### Requirement: Provider Gateway 与 Durable Run Engine 分工明确

系统 SHALL 保持 Durable Run Engine 和 Provider Gateway 的职责分离。

#### Scenario: RunWorker 通过 gateway 启动 coding adapter
- **WHEN** RunWorker 执行 coding TaskRun
- **THEN** RunWorker SHOULD 调用 ProviderGateway 获取 resolution 和 adapter execution result
- **AND** 不应在 endpoint 或 RunWorker 内散落 provider fallback 判断

#### Scenario: RunSupervisor 仍负责进程中断与超时
- **WHEN** coding adapter 已被 gateway 启动
- **THEN** RunSupervisor MUST 继续负责 interrupt、terminate、kill、max runtime timeout 和 idle timeout
- **AND** Provider Gateway MUST 保留 provider 分类和 fallback 证据

#### Scenario: Artifact Collector 不被 gateway 扩大范围
- **WHEN** coding adapter 执行结束
- **THEN** diff、review、preview、deploy evidence SHOULD 继续由 ArtifactCollector/Finalizer 处理
- **AND** Provider Gateway MUST NOT 变成 preview/deploy 执行器

### Requirement: MissionTrace 记录 Provider Gateway 证据

系统 SHALL 在任务追踪或 TaskRun evidence 中展示 Provider Gateway 的关键诊断信息。

#### Scenario: 追踪显示 provider resolution
- **WHEN** 用户查看 mission trace 或 TaskRun 详情
- **THEN** 系统 SHOULD 显示 selected provider、selection reason、rejected candidates 和 fallback candidates 的安全摘要

#### Scenario: 追踪显示 gateway 控制状态
- **WHEN** TaskRun 受 health、capacity、rate limit placeholder 或 circuit breaker 影响
- **THEN** 系统 SHOULD 显示对应状态、原因和下一步建议的安全摘要

#### Scenario: 追踪显示 fallback chain
- **WHEN** TaskRun 使用 fallback
- **THEN** 系统 SHOULD 显示 original provider、fallback provider、trigger category、mock/fallback 标记和最终 adapter

### Requirement: V2.2 保留现有 demo 与安全边界

系统 SHALL 在引入 Provider Gateway 时保留当前本地单用户 demo、安全边界和 adapter 集合。

#### Scenario: 不新增 adapter
- **WHEN** V2.2 实现 Provider Gateway
- **THEN** 系统 MUST 保留 CodexAdapter、ClaudeCodeAdapter 和 ScriptedMockAdapter
- **AND** 系统 MUST NOT 要求新增 HumanAgentAdapter、Docker sandbox、provider marketplace 或 Codex cloud wrapper

#### Scenario: 不改变 demo app boundary
- **WHEN** gateway 执行 coding provider
- **THEN** agent-modified demo app boundary MUST 仍是 Vite React
- **AND** provider execution MUST 继续遵守受保护路径和命令 allowlist

#### Scenario: 不伪造真实 Codex 或 Claude 成功
- **WHEN** CodexAdapter 或 ClaudeCodeAdapter auth、quota、rate、timeout、tool、format 或 unavailable 失败
- **THEN** 系统 MUST 记录真实失败类别
- **AND** 系统 MUST NOT 用 fallback/mock 结果覆盖为真实 provider 成功
