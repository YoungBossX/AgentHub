## 为什么

AgentHub Reliability v2 已经将执行可靠性拆分为 Durable Run Engine、Provider Gateway、调度、锁、预览和部署等阶段。但前端诊断体验仍停留在“failed”、“errorCode”或零散日志层面。真实开发任务失败时，用户往往不知道问题属于：

- provider 配额、认证、不可用或 provider gateway 兜底；
- adapter 超时、空闲超时、中断或子进程退出；
- session 工作区脏状态、diff 收集失败或受保护路径拒绝；
- queue/worker 租约、目标锁超时或陈旧恢复；
- 计划验证、策略验证、审批拒绝；
- preview/build 失败、部署 blocked/failed；
- 或后续任务被上游失败阻塞。

这会削弱本地 demo 的可信度：AgentHub 明明已经记录了部分执行事件和制品，但用户看到的只是一个不可操作的失败标签。V2.7 的目标是把运行过程转化为可读、可审计、可操作的 Run Diagnostics：用户能看到运行时间线、失败分类、健康摘要和下一步建议，而系统不伪造 provider 成功、不泄露敏感信息，也不扩大到生产级可观测平台。

## 变更内容

- 新增 Run Diagnostics 能力，面向单个 TaskRun 和当前 Session 汇总运行状态。
- 定义标准化的 failure category、failure reason、severity、retryability 和 next-step suggestion 模型。
- 增加 Run Timeline 设计，将 queued、claimed、provider、adapter、lock、validation、approval、diff、review、preview、deploy、finalizer 等阶段汇总为用户可读事件。
- 增加 provider / queue / lock / preview / deploy 健康摘要，说明当前 Session 或 TaskRun 的关键健康信号。
- 在 UI 中展示诊断面板或卡片：
  - 不再只显示 `failed` 或 `errorCode`；
  - 显示最可能失败原因、影响范围、是否可重试、可采取的下一步；
  - 保留原始事件和制品入口。
- 在 API 层暴露安全、脱敏、稳定的诊断响应。
- 增加测试覆盖典型失败：provider quota/auth、超时、脏工作区、锁超时、验证失败、审批拒绝、预览失败、部署 failed/blocked。
- 保留现有 adapters、SSE、SQLite、单用户本地 demo、Vite React preview 和 mock-backed deploy card。

## 能力

### 新能力

- `run-diagnostics`：定义 TaskRun 诊断模型、Run Timeline、失败分类、下一步建议、运行健康摘要以及安全 UI/API 呈现。

### 修改后的能力

- `mission-trace`：任务追踪应能链接或内联 Run Diagnostics 摘要。
- `task-run`：TaskRun 详情应暴露足够的安全诊断字段，而不是只暴露终态和 error code。
- `provider-gateway`：provider auth/quota/unavailable/fallback 结果应映射到统一诊断分类。
- `scheduler`：queue、dependency、target lock 和 approval 状态应进入诊断 timeline 与 health summary。
- `preview` / `deployment`：preview/deploy 失败或阻塞状态应作为后处理健康信号展示，不覆盖编码运行的真实失败原因。

## 影响

- 预计后续实现会新增或修改诊断服务、TaskRun 详情 API、session/mission trace API、前端任务卡片、右侧制品/诊断面板和测试。
- 后续实现需要更新 `docs/change-log.md` 和 `docs/project-state.md`。
- V2.7 不新增 adapter、不改 provider 执行语义、不引入 WebSocket、不引入 Docker sandbox、不创建 PR、不接入外部 IM、不改变 SQLite demo 边界。
- V2.7 不应将 ScriptedMock 兜底包装成真实 Codex/Claude 成功；诊断必须明确区分真实 provider 失败与兜底成功。
