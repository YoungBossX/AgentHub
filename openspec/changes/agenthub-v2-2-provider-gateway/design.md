## 总体设计

V2.2 在 Durable Run Engine 与现有编码适配器之间增加 Provider Gateway。
它不是新的 agent，也不是 provider marketplace，而是一个执行时控制面：
```text
Durable Run Engine
  -> ProviderGateway
      -> ProviderResolver
      -> ProviderHealthProbe
      -> ProviderConcurrencyLimiter
      -> ProviderCircuitBreaker
      -> ProviderErrorClassifier
      -> FallbackPolicy
  -> ClaudeCodeAdapter / CodexAdapter / ScriptedMockAdapter
```
Provider Gateway 只处理 coding adapter 平面。Planner provider 继续走现有
Conversation Router / Planner runtime 配置与 P17/P22 兼容性边界，不混入本阶段。

## 核心原则

- 保留现有 ClaudeCodeAdapter、CodexAdapter、ScriptedMockAdapter，不新增 adapter。
- Provider Gateway 统一选择和控制启动路径，但不把失败包装成虚假成功。
- fallback 是可靠性路径和 demo fallback，不是隐藏真实 provider 失败。
- health 必须与实际 launch path 对齐，不能只检查配置字段存在。
- circuit breaker、并发限制和 rate limit placeholder 必须有证据，便于后续
  V2.7 诊断 UI 展示。
- 不暴露 secrets、tokens、API keys、受保护 host paths 或 adapter 原始危险日志。

## Provider Registry

Provider Registry 描述 coding provider 的静态和运行时元数据：

- provider id：`claude_code`、`codex`、`scripted_mock`；
- adapter type；
- 支持的 role / target / mode / capability；
- 是否允许 write execution；
- 是否是真实 provider 或 fallback/mock provider；
- auth/config status；
- launch command 或 CLI path 的安全摘要；
- 当前 availability、cooldown 和限制状态。

该 registry 可以复用已有 runtime config 和 agent profile 元数据，但 gateway 的
输出必须是 coding adapter 专用视图，不把 Planner provider 混进来。

## Provider Resolution

ProviderResolver 接收 coding run context：

- workspace id、session id、task id、task run id；
- requested role；
- requested provider 或 runtime-selected provider；
- target/project profile；
- execution mode；
- write/read capability；
- current provider health 与 circuit 状态。

输出 resolution plan：

- selected provider；
- ordered fallback candidates；
- rejected candidates 与原因；
- selected provider 是否真实 provider；
- 是否需要等待、失败、或使用 fallback；
- provider-visible context 的安全摘要。

Resolution plan 必须写入 TaskRunEvent 或 TaskRun evidence，至少包含 provider id、
selection reason、fallback candidates 和 rejection reasons。不得记录 raw secret。

## Health And Probe

HealthProbe 应贴近实际启动路径：

- Claude Code：配置、CLI 可用性、认证/启动前 probe 的安全结果；
- Codex：配置、CLI 可用性、认证/启动前 probe 的安全结果；
- ScriptedMock：demo app boundary 和 mock 脚本可用性；
- provider unavailable 时返回明确状态，不执行真实 coding run。

Health 不要求在 V2.2 实现完整云端连通性测试，但 probe 结果必须诚实：
未知就是 unknown，不可用就是 unavailable。不能因为 fallback 可用而把真实
provider 标为 healthy。

## Concurrency Limiter

ProviderConcurrencyLimiter 控制：

- 每 provider 同时运行的 coding TaskRun 上限；
- 全局 coding provider 上限；
- fallback/mock provider 是否有独立限制；
- acquire/release 的幂等性。

当没有 capacity 时，gateway 可以让 run 保持 queued/waiting capacity，或返回
可恢复失败，具体由后续实现结合 Durable Run Engine 决定。但不得绕过限制直接
启动 adapter。

## Rate Limit Placeholder

V2.2 只建立 rate limit 占位：

- 记录 provider rate-limit 状态、窗口、原因和 next eligible time 的结构；
- 将 provider 报告或 classifier 推断出的 rate limit 错误转成统一 taxonomy；
- 支持后续接入真实配额/窗口算法。

本阶段不实现完整计费、token 预算、外部 provider 配额同步或 provider marketplace。

## Circuit Breaker

Circuit breaker 基于 provider、workspace 和错误类别维护 cooldown 状态。

建议最小状态：

- closed：允许启动；
- open：阻止启动并返回 cooldown evidence；
- half_open：允许有限 probe/run 验证恢复。

触发来源包括：

- 连续 auth 失败；
- quota 或 rate limit 失败；
- provider CLI 启动失败；
- health probe 连续 unavailable；
- timeout 是否触发 circuit 由实现策略决定，但必须可审计。

guardrail、dirty_worktree 等本地安全失败通常不应打开 provider circuit，因为它们
不代表 provider 不健康。

## Error Taxonomy

ProviderErrorClassifier 将 adapter 异常、退出码、stderr 摘要、health probe 结果
和 gateway 控制失败归类为：

- `auth`
- `quota`
- `rate_limit`
- `timeout`
- `format`
- `tool`
- `guardrail`
- `dirty_worktree`
- `unavailable`
- `unknown`

每个分类都应包含：

- provider id；
- category；
- retryable；
- fallbackEligible；
- circuitBreakerEligible；
- userMessage；
- safeEvidence；
- raw error 是否已 redacted。

## Fallback Policy

FallbackPolicy 决定是否从真实 provider 切换到另一个 coding provider 或
ScriptedMockAdapter。

必须满足：

- fallback 只在明确允许的 coding run 中发生；
- fallback 触发原因来自 resolution、health、concurrency、circuit 或 error taxonomy；
- fallback 使用 ScriptedMockAdapter 时，证据中必须写明它是 mock/fallback；
- fallback 结果不得覆盖原始 provider 失败；
- 若真实 provider 失败但 fallback 完成，TaskRun evidence 必须同时展示真实失败和
  fallback 成功，不得表述为真实 provider 成功。

## 与 Durable Run Engine 的关系

Durable Run Engine 负责 claim、lease、heartbeat、interrupt、timeout、recovery 和
finalization。Provider Gateway 负责在 execute 阶段选择并启动 coding adapter。

边界：

- RunWorker 调用 ProviderGateway 执行 coding run；
- Gateway 向 RunSupervisor 暴露 adapter process/interrupt handle；
- RunSupervisor 仍负责进程级 interrupt / terminate / kill；
- Gateway 分类 provider 失败并返回 safe result；
- Finalizer 保存 gateway evidence 和 artifact collector result。

## 事件与证据

建议事件名：

- `provider.resolution_started`
- `provider.resolved`
- `provider.health_checked`
- `provider.capacity_acquired`
- `provider.capacity_released`
- `provider.circuit_opened`
- `provider.circuit_blocked`
- `provider.error_classified`
- `provider.fallback_selected`
- `provider.fallback_completed`
- `provider.gateway_completed`

证据至少包含：

- selected provider；
- resolution reasons；
- health status；
- capacity/circuit 状态；
- error category；
- fallback chain；
- adapter used for final execution；
- safe stdout/stderr summary 或 redacted error summary。

## 非目标

- 不新增 HumanAgentAdapter、OpenCode adapter、Docker sandbox、WebSocket、PR 创建或
  production deploy。
- 不把 Planner provider 纳入 coding adapter gateway。
- 不实现 provider marketplace 或完整 MCP marketplace。
- 不实现 Codex API/cloud task wrapper。
- 不把 SQLite 替换成 Postgres，也不引入 Alembic 作为本阶段要求。
- 不改变 demo app boundary：agent-modified demo app 仍是 Vite React。

## 风险

- provider selection 已与 runtime config、agent directory、adapter invocation 交织，
  实施时需要分阶段抽边界。
- fallback 证据如果设计不清，容易让用户误以为 Claude/Codex 成功。
- circuit breaker 若过于激进，可能阻塞可恢复的本地临时失败。
- health probe 若过于重，会拖慢 run 启动；若过轻，又会误报可用。
- 当前工作区可能有其他线程改动，实施时必须避免覆盖热文件中的他人修改。
