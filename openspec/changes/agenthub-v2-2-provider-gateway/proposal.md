## 为什么

AgentHub Reliability v2 的 V2.1 目标是把 TaskRun 执行抽到 durable run
engine。V2.2 要在这个执行内核与真实编码 adapter 之间增加 Provider
Gateway，使 Claude Code、Codex 和 ScriptedMock 的选择、健康、并发、失败
分类、fallback 和证据记录不再分散在 endpoint、运行时配置和各 adapter 内部。

当前风险是：

- ClaudeCodeAdapter、CodexAdapter、ScriptedMockAdapter 的 provider 选择逻辑
  分散，实际启动路径与配置健康状态不总是一致。
- auth、quota、rate limit、timeout、格式错误、工具失败、guardrail 拒绝、
  dirty worktree 等失败缺少统一 taxonomy，用户和后续恢复逻辑难以判断是否
  应 retry、fallback 或等待配置修复。
- fallback 仍然需要保留 P0 demo 可靠路径，但必须可审计，不能让
  ScriptedMockAdapter 看起来像真实 Claude/Codex 成功。
- 并发限制、rate limit 占位和 circuit breaker 尚未形成一个统一入口，真实
  provider 连续失败时可能继续被无意义调用。
- Planner provider 与 coding adapter provider 是不同平面；本阶段若混在一起
  会破坏 P17/P22 已建立的分离边界。

V2.2 的目标是定义一个只服务编码 adapter 的 Provider Gateway：它接收来自
Durable Run Engine 的 coding run 请求，解析 provider resolution plan，检查
健康与并发/cooldown 约束，调用现有 adapter，并把失败分类、fallback 决策和
证据写回 TaskRun / TaskRunEvent / MissionTrace。

## 变更内容

- 新增 `provider-gateway` OpenSpec 能力，定义 coding adapter gateway 的范围、
  事件、证据和验收。
- 引入 Provider Gateway 后端边界：
  - `ProviderGateway`
  - `ProviderRegistry`
  - `ProviderResolver`
  - `ProviderHealthProbe`
  - `ProviderConcurrencyLimiter`
  - `ProviderRateLimitPlaceholder`
  - `ProviderCircuitBreaker`
  - `ProviderErrorClassifier`
  - `FallbackPolicy`
- 统一 ClaudeCodeAdapter、CodexAdapter、ScriptedMockAdapter 的执行入口：
  Durable Run Engine 不应直接散落调用具体 coding adapter，而应通过 gateway
  选择并执行。
- 建立 provider resolution plan：
  - role / runtime config / requested provider；
  - provider availability 和 auth/config 状态；
  - target/mode/capability 兼容性；
  - fallback 候选与禁用原因。
- 建立 provider health 与 probe：
  - 健康状态必须贴近实际 launch path；
  - 不泄露 secrets、token、API key 或受保护 host path；
  - health 不得伪造真实 provider 可用。
- 建立并发限制与 rate limit 占位：
  - 每 provider 和全局 coding run 并发限制可配置、可测试；
  - rate limit 先记录 placeholder 与事件，不实现完整外部配额系统。
- 建立 circuit breaker：
  - 连续 auth/quota/rate/启动失败可以打开 cooldown；
  - cooldown 内 provider 不应继续启动真实 adapter；
  - circuit 状态和原因必须可审计。
- 建立 provider error taxonomy：
  - auth
  - quota
  - rate_limit
  - timeout
  - format
  - tool
  - guardrail
  - dirty_worktree
  - unavailable
  - unknown
- 建立 fallback evidence：
  - fallback 触发条件、原始 provider、fallback provider、分类错误、用户可读原因
    必须记录；
  - ScriptedMockAdapter fallback 必须明确标记为 fallback/mock evidence；
  - 不得声称 Claude/Codex 成功。
- 明确非目标：
  - 不把 Planner provider 纳入 coding Provider Gateway；
  - 不新增 adapter；
  - 不新增 provider marketplace；
  - 不实现 Codex API/cloud task wrapper；
  - 不实现完整外部 rate limit 计费系统；
  - 不改变 demo 的 SQLite、本地单用户、SSE、Vite React preview 边界。

## 能力

### 新能力

- `provider-gateway`：定义编码 adapter 的 provider resolution、健康、并发、
  rate limit placeholder、circuit breaker、错误分类、fallback policy 和
  fallback evidence。

### 修改后的能力

- `durable-run-engine`：执行 coding adapter 时应通过 Provider Gateway，而不是
  直接散落调用 ClaudeCodeAdapter、CodexAdapter 或 ScriptedMockAdapter。
- `agent-adapter`：现有 adapter 保持存在，但其启动、健康、错误归类和 fallback
  证据由 Provider Gateway 统一协调。
- `mission-trace`：任务追踪应展示 provider resolution、health、concurrency、
  circuit、error taxonomy 和 fallback evidence。

## 影响

- 预计后续实现会影响 adapter 执行编排、runtime config provider selection、
  TaskRunEvent / MissionTrace evidence、provider health API 或内部 health helpers。
- 预计新增 provider gateway 模块和针对 resolver、health、concurrency、
  circuit breaker、error classifier、fallback policy 的测试。
- 不应在本 OpenSpec 创建阶段修改 `apps/api/app/main.py`、`task_runs.py`、
  `adapters.py`、`codex_adapter.py`、`claude_code_adapter.py` 或前端实现。
- 实施阶段需要更新 `docs/change-log.md` 和 `docs/project-state.md`；本任务只创建
  OpenSpec，不更新工程代码。
