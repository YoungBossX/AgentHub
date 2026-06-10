## 背景

AgentHub 是一款 IM 风格的编码智能体协作产品，而非通用聊天机器人、全功能 AI IDE 或企业级智能体平台。P0 产品必须展示一个可靠且可验证的闭环：

```text
requirement -> orchestrator plan -> agent execution -> real git diff -> real preview -> deploy card
```

用户体验应更接近以编码为核心的群聊，而非 IDE 插件。用户通过消息、提及、任务卡片、差异卡片、预览卡片和审批控件与编排器和角色代理进行交互。

研究简报通过将工作树、审批控制、差异对比、预览和可部署制品确定为现代编码代理工具的共享产品语言，为这一方向提供了支持。对于本设计而言，该简报仅作为背景参考。固定技术栈、护栏、验收标准和演示脚本共同定义了 P0 范围。

## 目标 / 非目标

**目标：**
- 构建一个单用户本地演示，支持多个会话和 IM 风格聊天。
- 在一个会话流中展示用户、编排器和角色代理的消息。
- 解析 `@orchestrator`、`@frontend`、`@backend` 和 `@qa` 的提及。
- 每个编排请求生成 2-4 个可见任务。
- 通过 `CodexAdapter` 使用本地 CLI 调用执行至少一个任务。
- 提供 `ScriptedMockAdapter` 兜底，实际修改 Vite React 演示仓库。
- 在 P0 中使用会话级 git worktree 隔离。
- 通过 Git CLI 生成真实差异，并在 UI 中渲染。
- 为 Vite React 演示应用启动真实预览。
- 预览成功后显示部署卡片，P0 可靠性可接受模拟部署。
- 支持中断、重试和基本审批控制。
- 持久化任务运行事件，以便 UI 在刷新或 SSE 重连后恢复。
- 保留扩展接口，用于未来适配器、API/cloud Codex 包装器、Docker 沙箱、PR 工作流和更丰富的编排。

**非目标：**
- 不包含企业级 RBAC、计费、多租户管理、完整的外部 IM 集成、完整的 IDE 编辑器、任意 DAG 构建器、提供商市场、完整部署矩阵、多人协作、复杂的自主智能体团队、推理可视化、长期记忆或完整的 MCP 市场。
- P0 阶段不涉及 WebSocket。
- Docker 沙箱不作为 P0 阶段的阻塞项。
- 不提供通用的多框架预览运行器。
- P0 阶段不依赖 LangGraph 或 CrewAI。
- P0 阶段不包含 ClaudeCodeAdapter 或 HumanAgentAdapter。
- P0 阶段不包含 Codex API/cloud 任务包装器。

## 系统架构

```text
Next.js App Router product UI
  - Workspace and session shell
  - Session list and chat stream
  - Task state cards
  - Diff card using Monaco Diff Editor
  - Preview side panel or iframe
  - Approval, retry, interrupt, and deploy cards

FastAPI backend
  - Pydantic request/response/event contracts
  - SQLModel persistence
  - SQLite database for P0
  - SSE event stream and replay
  - Orchestrator service
  - Adapter service
  - Worktree service
  - Diff service
  - Preview service
  - Deploy service
  - Permission guardrail service
  - Event persistence and recovery service

Execution layer
  - Git CLI session worktree manager
  - CodexAdapter local CLI process runner
  - ScriptedMockAdapter controlled script runner
  - Command allowlist
  - Protected path checks
  - Approval gate integration

Agent-modified demo repo
  - Vite React only
  - Dependencies installed during setup
  - Preview command: pnpm dev --host 127.0.0.1 --port <port>
```

前端不实现代理执行。它显示后端发出的权威状态和制品。后端拥有任务规划、适配器执行、会话工作树路径、差异收集、预览生命周期、部署卡片生成、护栏执行以及流式传输前的事件持久化。

## 固定技术栈

- 产品 UI：Next.js App Router、TypeScript、Tailwind CSS、shadcn/ui、Monaco Diff Editor。
- 后端：Python、FastAPI、Pydantic、SQLModel。
- 数据库：P0 阶段使用 SQLite；Schema 保持与 Postgres 兼容。Alembic 为 P1 阶段内容（除非已可用）。
- 实时：P0 阶段使用 SSE，基于持久化的 `TaskRunEvent` 记录实现回放与恢复。
- 差异对比：Git CLI、`git diff -p`、变更文件、统计信息、可选的 `git apply --check`。
- 被智能体修改的演示应用：仅限 Vite React。
- 预览：依赖项在设置阶段安装；预览运行器在智能体执行期间不得运行 `pnpm install`；命令为 `pnpm dev --host 127.0.0.1 --port <port>`。
- 部署：基础部署卡片。若真实 Vercel 演示部署不稳定，允许使用模拟部署卡片。
- Sandbox/isolation：每个会话对应一个 Git 工作树、命令白名单、受保护路径、审批关卡。Docker 沙箱为 P1 阶段内容。

## 适配器生命周期

适配器的生命周期有意保持简短：

```text
getCapabilities()
createRun(request)
streamEvents(runId)
interrupt(runId)
approve(runId, approval)
collectArtifacts(runId)
cleanup(runId)
```

### 适配器能力

每个适配器都暴露一个轻量级的能力描述符，使得编排器和 UI 无需硬编码提供者行为即可做出安全决策。

```ts
interface AdapterCapabilities {
  supportsStreaming: boolean
  supportsInterrupt: boolean
  supportsApproval: boolean
  supportsFileEdit: boolean
  supportsShellCommand: boolean
  supportsDiffArtifact: boolean
  supportsPreviewArtifact: boolean
  supportsNetwork: boolean
  maxRuntimeSec?: number
}
```

P0 使用此功能处理 `CodexAdapter` 和 `ScriptedMockAdapter`。P1 适配器（如 `ClaudeCodeAdapter`、`HumanAgentAdapter` 以及 Codex API/cloud 任务包装器）可在不更改核心生命周期的情况下添加。

### AgentRunRequest

```ts
interface AgentRunRequest {
  taskRunId: string
  sessionId: string
  workspaceId: string
  worktreePath: string
  agentId: string
  adapterType: 'codex' | 'scripted_mock' | 'claude_code' | 'human'
  instruction: string
  planContext?: Record<string, unknown>
  permissionProfile: PermissionProfile
  demoMode?: boolean
  fallbackPolicy?: 'none' | 'scripted_mock_on_failure'
}
```

### AgentEvent

```ts
interface AgentEvent {
  type:
    | 'message.delta'
    | 'task.state'
    | 'approval.requested'
    | 'artifact.diff.ready'
    | 'artifact.preview.ready'
    | 'artifact.deploy.ready'
    | 'error'
    | 'completed'
  taskRunId: string
  sequence: number
  payload: Record<string, unknown>
  createdAt: string
}
```

所有重要事件在通过 SSE 发出之前，必须持久化为 `TaskRunEvent`。UI 将 SSE 视为传输通道，而非数据源。

## P0 适配器

### CodexAdapter

`CodexAdapter` 是唯一的 P0 真实编码适配器。它使用本地 CLI 调用，并在分配的会话工作树内运行。API/cloud 任务包装器为 P1。

职责：
- 在 `Session.worktreePath` 内运行。
- 每次接收一条任务指令。
- 发出标准化的生命周期事件。
- 修改工作区中的文件。
- 遵守命令白名单、受保护路径检查和审批关卡。
- 在可能的情况下支持中断。
- 将执行失败映射为标准化的 `TaskRun.errorCode` 和 `TaskRun.errorMessage`。
- 在执行到达终止点或收集点后调用制品收集。

P0 验收：
- 至少有一个任务能够通过 `CodexAdapter` 执行并产生真实的文件变更。
- 如果 Codex CLI 执行不可用或不稳定，重试路径可以兜底到 `ScriptedMockAdapter`。

### ScriptedMockAdapter

`ScriptedMockAdapter` 是 P0 可靠性路径。它不能仅仅是虚假的聊天。它在会话工作树中对 Vite React 演示仓库执行受控脚本，发出真实的生命周期事件，可以模拟审批或失败状态，并且仍然依赖 Git CLI 差异收集来生成最终制品。

职责：
- 修改 Vite React 演示仓库中的实际文件。
- 模拟真实的编码代理进度消息。
- 模拟成功、失败、中断和审批状态。
- 遵守命令白名单和受保护路径规则。
- 生成实际的差异对比和可预览的应用变更。

## 编排器状态机

P0 编排器是一个简单的服务，而非通用的 DAG 引擎。它从聊天消息中解析用户意图，创建 2-4 个可见任务，将任务分配给角色代理，支持简单的串行依赖，最多支持一个简单的并行组，流式传输状态变更，附加制品，并汇总结果。

任务状态：
```text
pending
planning
running
waiting_approval
completed
failed
interrupted
```

TaskRun 状态：
```text
created
queued
streaming
waiting_approval
applying_changes
collecting_diff
starting_preview
completed
failed
interrupted
```

重试会为同一个 `Task` 创建新的 `TaskRun`。中断会将当前运行移至 `interrupted`，尽可能停止适配器执行，并保留已收集的消息、事件和制品。失败或中断的运行仍然可见，重试的运行不会覆盖之前的运行历史。

## 事件持久化与 SSE 恢复

P0 使用 SSE，而非 WebSocket。后端在发出状态转换和适配器追踪事件之前，会先持久化这些事件。

`TaskRunEvent` 是核心领域模型之外唯一允许的 P0 支持实体。它用于 SSE 重放、调试和适配器可追溯性。它不得为无关的 P0 领域实体打开大门。

```text
TaskRunEvent:
- id
- taskRunId
- eventType
- payloadJson
- sequence
- createdAt
```

页面刷新或 SSE 重连后，UI 必须重建会话消息、当前任务、当前任务运行、终端状态、可用制品、差异卡片、预览卡片、部署卡片以及仍等待用户操作的审批请求。

## 工作树与差异设计

P0 使用会话级工作树隔离：

```text
One Session -> One Git worktree
Multiple TaskRuns in that Session -> Reuse the Session worktree
```

理由：
- 一个会话代表一个连续的编码上下文。
- 后续请求可以基于之前的变更进行构建。
- 预览可以保持附着在同一工作树上。
- 差异可以显示会话的累积变更。
- 对于为期3周的项目，实现更简单且更可靠。

`TaskRun.worktreePath` 存储解析后的工作树路径以实现可追溯性，在 P0 阶段等同于 `Session.worktreePath`。每个 TaskRun 还会记录 `baseRef` 和 `headRef` 用于差异收集。P1 阶段可能支持任务运行级别的工作树，以实现高级并行执行。

### TaskRun baseRef/headRef 规则

P0 使用会话级工作树，但每个 TaskRun 拥有自己的差异边界：

- 在每个 TaskRun 启动前，系统必须记录当前会话工作区 `baseRef`。
- `baseRef` 应为 TaskRun 启动时的 git 提交 SHA 或后续可解析的其他显式 git 引用。
- TaskRun 执行结束后，系统记录 `headRef`。
- 当工作区保持未提交状态时，`headRef` 可以是执行完成的提交 SHA、临时引用或工作树快照标记。
- 差异收集必须使用该 TaskRun 的 `baseRef`/`headRef` 语义生成 TaskRun 差异。
- 同一会话中的后续变更复用同一会话工作区，但需使用新的 `baseRef` 创建新 TaskRun。
- 重试的 TaskRun 会创建新记录，且不得覆盖先前 TaskRun 的 `baseRef` 或 `headRef` 值。

最简单的 P0 实现是：

1. 在 TaskRun 执行前，将 `git rev-parse HEAD` 记录为 `baseRef`。
2. 让适配器修改会话工作区中的文件。
3. 使用 `git diff -p baseRef -- .` 或基于会话工作区的等效命令生成本次运行的差异。
4. 执行后，将当前的 HEAD 或工作区快照标记记录为 `headRef`。

工作树约束：
- 多个会话绝不能共享同一工作树路径。
- 工作树路径必须持久化。
- 工作树创建必须使用基于 workspace/session 标识符的确定性命名。
- 工作树清理必须显式且安全。
- 受保护的主机路径绝不能暴露给适配器。

差异收集由后端负责：
1. 确保适配器执行已结束或到达制品收集点。
2. 在会话工作树内运行 `git diff -p`。
3. 从 Git CLI 收集已变更文件及统计信息。
4. 从差异中排除 `node_modules`，并保护其免受代理编辑。
5. 可选地对生成的补丁文本运行 `git apply --check`（在有用的情况下）。
6. 存储类型为 `diff` 的 `Artifact`。
7. 存储包含 `baseRef`、`headRef`、`patchText`、`changedFilesJson` 和 `statsJson` 的 `Diff`。
8. 发出 `artifact.diff.ready`。

UI 渲染已更改的文件、补丁摘要、可展开的文件级变更，以及用于详细检查的 Monaco Diff 编辑器。Monaco 仅用于差异详情，不作为通用 IDE。

## 预览设计

P0 仅支持一个演示栈：Vite React。

预览运行器：
- 在会话工作树内启动 Vite React 应用。
- 仅使用白名单命令。
- 假设依赖项已在设置阶段安装完成。
- 在代理执行期间不得运行 `pnpm install`。
- 运行 `pnpm dev --host 127.0.0.1 --port <port>`。
- 分配或记录预览端口。
- 执行健康检查。
- 持久化预览状态。
- 健康时触发 `artifact.preview.ready`。
- 在会话关闭或重置时清理预览进程。

UI 在右侧面板或 iframe 中打开预览，并在第二次更改后刷新。预览进程必须受 session/task 生命周期约束。不允许存在不受限的后台进程。

预览记录要求：
```text
Preview:
- id
- artifactId
- port
- url
- command
- processId
- healthStatus
- statusReason
- expiresAt
- lastCheckedAt
```

## 部署卡片设计

部署卡片是一个 P0 制品视图，而非完整的部署平台。预览成功后，后端会创建一条 `Deployment` 记录并触发 `artifact.deploy.ready`。

P0 可以展示两条路径之一：
1. 如果团队环境中稳定，则展示真实的 Vercel 演示部署。
2. 如果真实部署不可靠，则展示模拟部署卡片。

模拟部署卡片仍须由后端创建并持久化为 `Deployment` 记录，不得为仅前端硬编码的卡片。部署操作需要审批。P0 阶段不支持多部署提供商、部署矩阵、生产发布管理、git push 要求或未经审核的部署。

## 权限护栏与审批设计

P0 防护措施简单但真实：
- 使用命令白名单。
- 阻止受保护路径。
- 保护 `.git/`、`.env`、`.env.*`、`secrets/`、`node_modules/` 及系统路径。
- 默认禁用网络，除非明确批准。
- 部署操作需审批。
- 推送操作需审批。
- 破坏性文件操作需审批。
- 编辑受保护文件需审批。
- 非白名单命令需审批。

系统区分产品确认与安全审批：

```text
product_confirmation
security_approval
```

审批请求负载：

```ts
interface ApprovalRequestPayload {
  approvalType: 'product_confirmation' | 'security_approval'
  reason: string
  requestedAction: string
  riskLevel: 'low' | 'medium' | 'high'
  command?: string
  path?: string
  expiresAt?: string
}
```

UI 可能使用相同的卡片组件渲染两种审批类型，但载荷必须区分它们。审批请求会将相关的 Task 和 TaskRun 移入 `waiting_approval` 状态，直到被批准、拒绝、过期、失败或中断。

## 数据模型概述

P0 使用以下实体。除非某个任务在没有额外领域实体的情况下无法满足演示循环，否则不应引入额外的 P0 领域实体。`TaskRunEvent` 是唯一允许的支持实体，因为它能显著改善事件恢复和调试。

- 用户: `id`, `email`, `name`, `avatarUrl`, `createdAt`
- 工作区: `id`, `name`, `repoUrl`, `rootPath`, `defaultBranch`, `createdAt`
- 会话: `id`, `workspaceId`, `title`, `sessionType`, `boundBranch`, `worktreePath`, `status`, `lastMessageAt`, `createdAt`, `updatedAt`
- 消息: `id`, `sessionId`, `senderType`, `senderId`, `contentMd`, `messageKind`, `parentMessageId`, `streamState`, `createdAt`
- 代理: `id`, `name`, `role`, `adapterType`, `provider`, `defaultModel`, `systemPrompt`, `capabilitiesJson`, `permissionProfileJson`, `enabled`, `createdAt`, `updatedAt`
- 任务: `id`, `sessionId`, `createdByMessageId`, `title`, `intentType`, `status`, `priority`, `planJson`, `dependsOnTaskIds`, `assignedAgentId`, `createdAt`, `updatedAt`
- TaskRun: `id`, `taskId`, `agentId`, `adapterRunId`, `state`, `startedAt`, `endedAt`, `worktreePath`, `baseRef`, `headRef`, `errorCode`, `errorMessage`, `metricsJson`, `createdAt`, `updatedAt`
- TaskRunEvent: `id`, `taskRunId`, `eventType`, `payloadJson`, `sequence`, `createdAt`
- 制品: `id`, `taskRunId`, `artifactType`, `title`, `status`, `version`, `storageUri`, `metaJson`, `createdAt`, `updatedAt`
- Diff: `id`, `artifactId`, `baseRef`, `headRef`, `patchText`, `changedFilesJson`, `statsJson`, `createdAt`
- 预览: `id`, `artifactId`, `port`, `url`, `command`, `processId`, `healthStatus`, `statusReason`, `expiresAt`, `lastCheckedAt`, `createdAt`, `updatedAt`
- 部署: `id`, `artifactId`, `provider`, `environment`, `commitSha`, `url`, `status`, `deployLogUri`, `createdAt`, `updatedAt`

## 真实实现 vs Mock 策略

P0 中的真实能力：
- 会话与任务持久化。
- TaskRunEvent 持久化与 SSE replay/recovery.
- 会话级 git 工作树创建。
- CodexAdapter 本地 CLI 执行路径。
- ScriptedMockAdapter 文件变更。
- Git 差异收集。
- Vite React 预览启动。
- 用于计划、任务状态、差异、预览、审批、重试、中断和部署的 UI 卡片。

P0 阶段模拟或受限：
- 部署可使用模拟后端。
- 只要可见任务与用户意图匹配，Agent 规划可使用确定性模板。
- ScriptedMockAdapter 可模拟事件、审批和错误，但必须产生真实的文件变更。
- 预览运行器仅支持 Vite React。

P1/P2：
- ClaudeCodeAdapter。
- HumanAgentAdapter。
- Codex API/cloud 任务包装器。
- 创建 PR。
- Docker 沙箱。
- WebSocket。
- 提供商市场。
- MCP 市场。
- 企业级控制。
- 外部 Feishu/Slack 集成。
- 多用户协作。
- 完整部署矩阵。
- 任意 DAG 构建器。

## 风险与缓解措施

- [风险] 演示期间真实 Codex CLI 执行不稳定 -> 缓解措施：将 ScriptedMockAdapter 作为一等兜底方案保留，它可修改演示仓库并执行相同的 diff/preview 流水线。
- [风险] 范围膨胀为完整代理平台 -> 缓解措施：强制执行 P0/P1/P2 边界，仅构建服务于 5 分钟演示路径的功能。
- [风险] 工作区跨会话泄漏状态 -> 缓解措施：使用会话级工作区，为每个会话持久化唯一路径，且绝不跨多个会话复用同一工作区。
- [风险] 任意命令执行不安全 -> 缓解措施：对命令设置白名单、阻止受保护路径、要求审批、默认禁用网络，并避免使用任意 shell。
- [风险] 预览运行器演变为框架矩阵 -> 缓解措施：P0 阶段仅支持 Vite React。
- [风险] SSE 流与数据库状态不一致 -> 缓解措施：在发送事件前持久化 TaskRunEvent 和规范状态；重连后重新加载规范状态。
- [风险] Monaco 集成消耗前端时间 -> 缓解措施：仅将 Monaco 用于文件级差异详情。
- [风险] 部署超出 P0 范围 -> 缓解措施：将部署视为后端创建的制品卡片，若真实 Vercel 部署不稳定则使用模拟部署。
- [风险] 实现过程中对 Codex CLI 行为理解有误 -> 缓解措施：在实现 CodexAdapter 前，将可行性验证结果写入 AGENTS.md 或 docs/adapter-notes.md。

## 迁移计划

1. 搭建固定的 frontend/backend/database 结构。
2. 添加 AGENTS.md，以便未来的编码智能体遵循 MVP 护栏。
3. 添加 SQLModel 模式，并初始化一个用户、工作区、智能体以及 Vite React 演示仓库配置。
4. 在会话工作树内运行一次 Codex CLI 可行性测试，并在实现 CodexAdapter 之前将结果写入 AGENTS.md 或 docs/adapter-notes.md。
5. 构建 workspace/session UI 和会话级工作树绑定。
6. 构建持久化聊天流，支持 SSE 和 TaskRunEvent 回放。
7. 添加对 `@orchestrator`、`@frontend`、`@backend` 和 `@qa` 的提及解析。
8. 添加结构化编排器规划和任务状态转换。
9. 添加包含 `getCapabilities()` 的适配器接口。
10. 添加 ScriptedMockAdapter。
11. 添加 CodexAdapter 本地 CLI 主路径和标准化错误。
12. 添加权限护栏和审批负载。
13. 添加差异收集和差异 UI。
14. 添加预览运行器后端骨架和预览 UI 优化。
15. 添加部署卡片和模拟部署后端路径。
16. 添加中断、重试和带兜底的重试控制。
17. 编写 README 和演示脚本。
18. 运行最终的成功与失败恢复演示排练。

演示不稳定性的回滚策略：使用 ScriptedMockAdapter、模拟部署卡片以及确定性的 Vite React 演示仓库路径，同时保留真实的 git diff 和真实的预览行为。

## P0 验收清单

- 用户可以在本地打开 AgentHub UI。
- 用户可以创建并切换至少三个会话。
- 每个会话拥有独立的工作树。
- 用户可以发送 `@orchestrator build a login page for the demo app`。
- 编排器会创建 2-4 个可见任务。
- 任务卡片显示分配的角色代理。
- 任务状态在聊天流中实时更新。
- TaskRunEvent 持久化存储并支持 SSE recovery/replay.。
- 至少有一个任务能通过 CodexAdapter 本地 CLI 执行。
- 若 Codex 失败，ScriptedMockAdapter 可完成相同流程。
- 兜底流程会修改 Vite React 演示仓库中的真实文件。
- 后端收集真实的 `git diff -p` 输出。
- UI 渲染已变更文件及补丁摘要。
- 用户可展开差异详情。
- 为 Vite React 演示应用启动预览，并附带 `pnpm dev --host 127.0.0.1 --port <port>`。
- 预览运行器在代理执行期间不运行依赖安装。
- 用户可在侧面板或 iframe 中打开预览。
- 用户可在同一会话中请求第二次小改动。
- 用户可中断正在运行的任务。
- 用户可重试失败或中断的任务。
- 对于风险操作或部署操作，会显示包含 ApprovalRequestPayload 的审批卡片。
- 预览成功后出现部署卡片。
- 当真实部署不可用时，模拟部署保持演示正常运行。
- README 说明本地设置。
- 演示脚本包含一条成功路径和一条失败恢复路径。

## 最终设计原则

AgentHub P0 不应试图成为一个完整的智能体平台。它应证明一个明确的产品主张：

```text
Coding agents become visible IM collaborators whose work produces verifiable artifacts.
```

P0 中的所有内容都应服务于该主张。其余一切均应推迟。
