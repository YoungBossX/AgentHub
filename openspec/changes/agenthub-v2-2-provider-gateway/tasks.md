## 1. OpenSpec 与范围确认

- [x] 1.1 创建 V2.2 Provider Gateway OpenSpec，定义范围、非目标、验收和风险。
- [x] 1.2 明确 Provider Gateway 只服务 coding adapters，不混入 Planner provider。
- [x] 1.3 标记 V2.2 不新增 adapter、provider marketplace、Codex API/cloud wrapper、Docker sandbox、WebSocket 或生产部署。
- [x] 1.4 验证 `git diff --check` 和 `openspec validate agenthub-v2-2-provider-gateway --strict`。

## 2. Gateway 合同与数据模型

- [x] 2.1 新增 Provider Gateway 后端边界和类型定义，覆盖 provider id、resolution plan、health、capacity、circuit、error taxonomy 和 fallback evidence。
- [x] 2.2 保留 ClaudeCodeAdapter、CodexAdapter、ScriptedMockAdapter，不新增 adapter。
- [x] 2.3 添加单元测试覆盖 gateway result、redacted evidence、planner provider 不被纳入 coding gateway。
- [x] 2.4 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [x] 2.5 单独提交：`feat: define coding provider gateway contract`。

## 3. Provider Resolution 与 Registry

- [x] 3.1 实现 coding ProviderRegistry，派生 Claude Code、Codex 和 ScriptedMock 的安全元数据。
- [x] 3.2 实现 ProviderResolver，基于 role、runtime config、target/mode/capability、availability 和 fallback policy 输出 resolution plan。
- [x] 3.3 记录 provider resolution TaskRunEvent 或 evidence，包含 selected provider、候选和拒绝原因。
- [x] 3.4 添加测试覆盖默认 provider、显式 provider、不可用 provider、fallback candidates、Planner provider 隔离。
- [x] 3.5 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [x] 3.6 单独提交：`feat: resolve coding providers through gateway`。

## 4. Health Probe 与 Launch Path 对齐

- [x] 4.1 实现 provider health/probe helper，使健康状态贴近 Claude/Codex/ScriptedMock 实际启动路径。
- [x] 4.2 确保 health 结果不泄露 secrets、API key、token 或受保护 host path。
- [x] 4.3 记录 health checked evidence，不因 fallback 可用而把真实 provider 标为 healthy。
- [x] 4.4 添加测试覆盖 healthy、unavailable、unknown、redaction、ScriptedMock demo boundary。
- [x] 4.5 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [x] 4.6 单独提交：`feat: add coding provider health probes`。

## 5. Concurrency、Rate Limit Placeholder 与 Circuit Breaker

- [x] 5.1 实现 provider/global coding run concurrency acquire/release，确保 release 幂等。
- [x] 5.2 添加 rate limit placeholder 结构和事件，先不实现完整外部配额系统。
- [x] 5.3 实现 circuit breaker 最小状态 closed/open/half_open 与 cooldown evidence。
- [x] 5.4 确保 auth/quota/rate/unavailable 等 provider 失败可打开 circuit，guardrail/dirty_worktree 不误开 provider circuit。
- [x] 5.5 添加测试覆盖 capacity exhausted、release on terminal、circuit open blocked、cooldown evidence、half-open 恢复路径。
- [x] 5.6 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [x] 5.7 单独提交：`feat: guard coding providers with limits and circuit breaker`。

## 6. Error Taxonomy 与 Fallback Policy

- [x] 6.1 实现 ProviderErrorClassifier，覆盖 auth、quota、rate_limit、timeout、format、tool、guardrail、dirty_worktree、unavailable、unknown。
- [x] 6.2 实现 FallbackPolicy，基于 taxonomy、health、capacity、circuit 和配置决定是否 fallback。
- [x] 6.3 确保 ScriptedMock fallback 明确记录为 mock/fallback evidence。
- [x] 6.4 确保 fallback 完成不覆盖原始 Claude/Codex 失败，不伪造真实 provider 成功。
- [x] 6.5 添加测试覆盖各错误分类、fallback eligible/non-eligible、fallback chain evidence、无 fallback 时的诚实失败。
- [x] 6.6 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [x] 6.7 单独提交：`feat: classify provider failures and record fallback evidence`。

## 7. Durable Run Engine 集成

- [x] 7.1 将 coding adapter 执行入口改为 Durable Run Engine 调用 ProviderGateway。
- [x] 7.2 保持 RunSupervisor 负责 interrupt、timeout、terminate、kill，Gateway 负责 provider 选择和分类。
- [x] 7.3 将 gateway result、provider events、fallback evidence 接入 TaskRunEvent、metrics/evidence 和 MissionTrace。
- [x] 7.4 确保 preview/diff/review/deploy 后处理仍由 ArtifactCollector/Finalizer 处理，不被 gateway 扩大范围。
- [x] 7.5 添加集成测试覆盖 Claude/Codex 失败后 fallback、capacity block、circuit block、真实 provider 成功路径、mock fallback 证据。
- [x] 7.6 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。
- [x] 7.7 单独提交：`feat: execute coding runs through provider gateway`。

## 8. 文档、诊断与冻结审查

- [ ] 8.1 更新 `docs/change-log.md` 和 `docs/project-state.md`，记录 V2.2 Provider Gateway 实施结果。
- [ ] 8.2 创建 V2.2 freeze review，记录范围、验证、真实限制和 V2.3/V2.7 后续依赖。
- [ ] 8.3 确认 provider evidence 不泄露 secrets、tokens、受保护 host paths 或 raw dangerous logs。
- [ ] 8.4 运行完整验证：`pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check`、`openspec validate agenthub-v2-2-provider-gateway --strict`。
- [ ] 8.5 单独提交：`test: freeze v2.2 provider gateway`。
