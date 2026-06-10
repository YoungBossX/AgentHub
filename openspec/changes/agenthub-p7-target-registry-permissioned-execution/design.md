## 背景

P6 已完成并在 `p6-agent-execution-upgrade-freeze` 处打标签。它验证了 AgentHub 能够将普通用户请求路由到 Orchestrator，生成共享的迷你 CRM 合约，使用 `ClaudeCodeAdapter` 运行后端代理和前端代理，生成 backend/frontend 差异，生成脚本化审查制品，预览应用，并创建模拟部署卡片。

P6 冻结还暴露了下一个结构性问题：目标知识分散在实现细节中。目前，AgentHub 按约定知道：

- 演示前端代码位于 `apps/demo`；
- 演示后端代码位于 `apps/demo-api`；
- AgentHub 平台后端位于 `apps/api`；
- 演示后端基础 URL 为 `http://127.0.0.1:5174`；
- 前端任务应使用 `apps/demo/src`；
- 后端应用任务不得修改 `apps/api`；
- 预览、测试和开发命令因目标而异。

P7 将这些分散的约定转化为目标项目注册表，使得规划、指令、审查和执行边界共享同一事实来源。

## 目标 / 非目标

**目标：**

- 为 `demo-frontend`、`demo-backend` 和 `agenthub-platform` 定义目标注册表记录。
- 存储或暴露包含允许路径、禁止路径、命令、基础 URL、允许的代理以及平台模式/审批要求的目标元数据。
- 使角色指令从注册表中读取目标元数据。
- 使契约优先规划引用 `frontendTargetId` 和 `backendTargetId`。
- 使前端指令使用注册表中的后端目标 `baseUrl`。
- 使审查检测：
  - 允许路径违规；
  - 禁止路径编辑；
  - 意外的平台代码变更；
  - 前端后端基础 URL 不匹配；
  - 契约目标不一致。
- 为 AgentHub 平台代码变更添加显式的平台维护模式。
- 保留 P6 迷你 CRM 垂直切片。

**非目标：**

- 多用户即时通讯。
- 集成 Matrix、飞书、微信、Slack 或其他外部即时通讯工具。
- 生产部署或真实部署提供商。
- Docker 沙箱。
- 提供商市场。
- 创建 PR。
- 无限制的仓库编辑。
- 分布式 Manager/Worker 调度器。
- 任意 SaaS 生成。

## 目标注册表形态

P7 应引入结构化目标记录。首次实现可在代码中静态完成，无需数据库持久化。

建议的字段：

```text
targetId
name
type: frontend | backend | platform
root
allowedPaths
deniedPaths
devCommand
testCommand
previewCommand
baseUrl
allowedAgents
requiresPlatformMode
requiresApproval
relatedTargetIds
```

初始目标：

```text
demo-frontend
  type: frontend
  root: apps/demo
  allowedPaths: apps/demo/src
  deniedPaths: apps/api, apps/demo-api, .env*, node_modules, .git, secrets
  devCommand: pnpm demo:dev
  previewCommand: pnpm dev --host 127.0.0.1 --port <port>
  allowedAgents: frontend, qa, review
  relatedTargetIds: demo-backend

demo-backend
  type: backend
  root: apps/demo-api
  allowedPaths: apps/demo-api
  deniedPaths: apps/api, apps/demo, .env*, node_modules, .git, secrets
  devCommand: pnpm demo:api:dev
  testCommand: pnpm demo:api:test
  baseUrl: http://127.0.0.1:5174
  allowedAgents: backend, qa, review

agenthub-platform
  type: platform
  root: .
  allowedPaths: apps/api, apps/web, scripts, docs, openspec, package metadata
  deniedPaths: .env*, node_modules, .git, secrets, unassigned host paths
  testCommand: pnpm check && pnpm test
  allowedAgents: orchestrator, backend, frontend, qa, review
  requiresPlatformMode: true
  requiresApproval: true
```

实现过程中可以缩小允许的精确路径范围，但注册表必须保持为唯一真实来源。

## 决策

### 决策 1：静态注册表优先

P7 应从静态注册表模块开始，而非动态数据库模型。目标集合规模小、已知且直接关联本地演示工作区。这使 P7 专注于执行正确性，而非管理界面或租户配置。

考虑的替代方案：立即将目标持久化到 SQLite 中。这在以后可能有用，但在注册表契约得到验证之前，这会增加迁移和 UI 的范围。

### 决策 2：计划与合约中的目标 ID

契约和任务应引用目标 ID，例如 `demo-frontend` 和 `demo-backend`。原始路径可作为已解析的元数据保留以保持兼容性，但目标 ID 是稳定的规划边界。

考虑的替代方案：继续仅存储原始路径。这导致了 P6
API 基础不匹配，并使得审查/指令逻辑随时间推移产生偏差。

### 决策 3：注册表解析的后端基础 URL

前端指令应从后端目标记录中派生应用数据的基础 URL。对于 P6 迷你 CRM 路径，前端目标引用 `demo-backend` 目标并使用其 `baseUrl`。

考虑的替代方案：将 `demoApiBaseUrl` 保持为规划器常量。这修复了
P6-7a，但该值仍分散在目标关系之外。

### 决策 4：审查检查目标策略

审查应检查变更的文件和补丁内容是否符合目标策略：

- 任何位于允许路径之外的文件应产生警告或失败；
- 任何被拒绝的路径至少应产生警告，且平台代码的编辑应导致普通应用任务失败；
- 前端代码不应调用 AgentHub 平台 API 获取应用数据；
- 合约目标 ID 应与任务目标 ID 匹配。

P7 评审仍为建议性质，除非后续变更引入阻塞性关卡。

### 决策 5：平台维护需要显式模式

普通 `@backend` 或编排器创建的应用后端任务必须针对
`demo-backend`，而非 `apps/api`。针对 AgentHub 本身的工作需要显式启用平台维护模式，目标为 `agenthub-platform`，并使用更严格的验证与审批流程。

考虑的替代方案：从"后端"或"API"等短语推断平台维护。这太容易误路由，并且存在控制平面变更的风险。

## 风险 / 权衡

- **风险：注册表间接引用破坏了现有的 P6 行为。** 缓解措施：在过渡期间将原始解析路径保留在计划上下文中，并演练 P6 迷你 CRM 流程。
- **风险：平台模式成为逃生舱。** 缓解措施：要求对 `agenthub-platform` 使用显式模式、审批和更严格的验证。
- **风险：审查对于部分串行任务过于严格。** 缓解措施：允许仅在后端发出中间警告，同时要求累积的最终全栈差异通过目标一致性检查。
- **风险：静态注册表变得过时。** 缓解措施：集中管理所有目标元数据，并添加测试，当规划器、指令和审查出现偏差时，测试会失败。

## 迁移计划

1. 添加静态目标注册表记录及测试。
2. 将目标 ID 和已解析的目标元数据贯穿到计划、合约、上下文包及适配器运行请求中。
3. 更新角色指令以使用注册表值。
4. 更新合约优先规划器，使其通过注册表解析 frontend/backend 关系。
5. 更新审查检查以强制执行目标策略。
6. 添加显式平台维护模式。
7. 通过注册表演练 P6 迷你 CRM，并仅在 diff/review/preview/mock 部署循环保持完整后冻结 P7。

回滚很简单：规划器和指令构建器可以兜底到 P6 常量，同时将 P6 冻结标签作为稳定基线。

## 待定问题

- `agenthub-platform` 最初应同时允许 `apps/api` 和 `apps/web`，还是后续拆分为 `agenthub-api` 和 `agenthub-web`？
- 平台维护模式应通过命令、UI 开关还是显式提及（如 `@orchestrator platform mode ...`）来触发？
- 在 P7 阶段，目标注册表记录应在 UI 中暴露，还是作为后端能力保留到后续 UX 任务？
