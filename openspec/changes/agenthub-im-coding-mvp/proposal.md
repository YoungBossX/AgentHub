## 意图

构建 AgentHub IM 编码 MVP：一个单用户、聊天式多智能体开发平台，用户可以在其中 @ 编排器或角色智能体，观察任务状态变化，审查真实的 git 差异，打开真实的预览，并在一个可演示的工作流中查看部署卡片。

## 问题

AgentHub 不能看起来像一个通用的聊天机器人或宽泛的企业级 Agent 平台。为期 3 周的演示需要证明核心产品主张：编码 Agent 成为可见的即时通讯协作者，其工作产出的是可验证的制品，而不仅仅是文本。

研究简报指出了相同的行业模式：现代编码代理产品正趋于统一，涵盖计划、工作树隔离、审批控制、差异对比、预览和可部署制品。对于本次变更，简报仅作为背景参考；MVP 护栏、验收标准和演示脚本才是决定性约束条件。

## 目标

- 交付一条 5 分钟的演示路径：从用户需求到计划、代理执行、真实文件变更、Git 差异对比、预览和部署卡片。
- 使用固定技术栈：Next.js App Router 产品 UI、TypeScript、Tailwind CSS、shadcn/ui、Monaco Diff Editor、FastAPI、Pydantic、SQLModel、SQLite（用于 P0）、SSE（用于实时通信）、Git CLI（用于差异对比），以及 Vite React（作为代理修改的演示应用）。
- 支持单用户工作区操作，可包含多个会话，每个会话拥有一个独立的 Git 工作树。
- 提供 IM 风格聊天，包含用户、编排器和角色代理消息，并支持 `@orchestrator`、`@frontend`、`@backend` 和 `@qa` 的提及解析。
- 实现一个真实的编码适配器 `CodexAdapter`，以及一个可靠的 `ScriptedMockAdapter`，后者会真实修改演示仓库，确保兜底演示仍能产生真实的差异对比和预览。
- 保持编排简单：2-4 个可见任务、简单的串行依赖、最多一个简单的并行组、可见的状态变更、重试、中断和结果摘要。
- 提供针对高风险操作的基本审批控制，以及一个部署卡片（若真实部署不稳定，可使用模拟后端）。

## 非目标

- 无企业级 RBAC、计费、多租户管理、外部IM集成、完整IDE编辑器、任意DAG构建器、提供商市场、完整部署矩阵、多人协作、复杂自主智能体团队、模型推理可视化、长期记忆或完整MCP市场。
- 无P0 WebSocket实现；P0实时通信仅使用SSE。
- 无P0 Docker沙箱要求；P0隔离使用git工作树、命令允许列表和保护路径。
- 无通用预览运行器；P0仅支持一个演示栈。
- 无通用部署平台；P0展示基础部署卡片，若实际部署不可靠，可使用模拟部署卡片。

## 范围

P0 包括：
- 单用户工作区、多会话及会话切换。
- 包含用户、编排器和角色代理消息的 IM 风格聊天流。
- 针对编排器和角色代理的提及解析。
- 简单的编排器状态机与任务状态显示。
- 仅核心数据模型：用户、工作区、会话、消息、代理、任务、TaskRun、TaskRunEvent、制品、Diff、预览、部署。`TaskRunEvent` 是唯一允许超出原始核心模型的 P0 支持实体。
- 适配器生命周期，包含 `AdapterCapabilities`、本地 CLI `CodexAdapter` 和 `ScriptedMockAdapter`。
- 工作树隔离、命令白名单、受保护路径和审批门控。
- 使用 `git diff -p` 收集真实 git diff、变更文件及统计信息。
- Diff 卡片，包含变更文件、补丁摘要及可展开的文件级检查。
- 仅针对 Vite React 演示应用的预览运行器和预览卡片。
- 中断、重试、基础审批 UI、部署卡片、演示仓库、README 及演示脚本。

P1 可能包括 ClaudeCodeAdapter、HumanAgentAdapter、制品标签页、简化的审批策略配置、Docker 沙箱、补丁导出、PR 创建、简单的 cost/duration 指标、WebSocket、Codex API/cloud 包装器、Alembic 采用以及更完整的提供商配置。P1 不得阻塞 P0。

P2/mock-only 包含多用户协作、Slack/Feishu/WeChat 集成、提供商市场、完整 MCP 市场、后台代理、自动检查、企业权限管理、多租户管理、完整审计后端以及全栈一键部署。

## MVP 定义

当评审员能够打开 AgentHub，创建或选择一个工作区，创建一个会话，发送 `@orchestrator build a login page for the demo app`，看到 2-4 步的计划，观察至少一个角色代理执行，检查来自演示仓库的真实 git diff 输出，在右侧面板或 iframe 中打开预览，请求第二个小改动，看到更新后的 diff 和刷新后的预览，并到达部署卡片时，MVP 即告完成。如果真实适配器失败，重试必须能够通过 `ScriptedMockAdapter` 完成演示，同时仍然创建真实的文件更改。

## 验收标准

- 用户可创建并切换至少 3 个会话。
- 用户可输入 `@orchestrator build a login page`。
- 编排器创建 2-4 个可见任务。
- 任务状态在聊天流中可见变化。
- 至少有一个任务可通过 `CodexAdapter` 执行。
- 若 `CodexAdapter` 失败，`ScriptedMockAdapter` 可运行稳定的兜底流程。
- 兜底流程在演示仓库中创建真实的文件变更。
- 系统根据工作区变更生成真实的 `git diff`。
- UI 渲染变更文件及补丁摘要。
- 用户可展开差异卡片并检查文件级变更。
- 系统为支持的演示应用启动预览 URL。
- 用户可在右侧面板或 iframe 中打开预览。
- 用户可中断正在运行的任务。
- 用户可重试失败或中断的任务。
- 多个会话可共存且不共享同一工作树，同一会话中的多个 TaskRun 复用该会话工作树。
- 预览成功后显示部署卡片。
- 当真实部署不可用时，演示路径仍可工作。
- README 说明如何运行应用并触发演示。
- 演示脚本包含一条成功路径和一条故障恢复路径。
- 最终演示展示：需求 -> 计划 -> 智能体执行 -> 差异 -> 预览 -> 部署卡片。

## 变更内容

- 为 P0 编码智能体协作添加一个以 IM 为先的 AgentHub 产品外壳和后端契约。
- 为单用户本地演示添加 workspace/session 管理。
- 添加包含编排器和角色智能体提及解析的聊天消息流。
- 添加一个最小化编排器，用于创建可见任务并跟踪简单的状态转换。
- 添加包含 `CodexAdapter` 和 `ScriptedMockAdapter` 的适配器层。
- 添加会话级工作树隔离、command/path 护栏和审批控制。
- 添加 TaskRunEvent 持久化，用于 SSE 重放、调试和适配器可追溯性。
- 添加真实的 git diff 收集和 diff 制品渲染。
- 添加单栈预览运行器、预览卡片和基本部署卡片。
- 添加演示仓库、README 和演示脚本，用于 5 分钟成功与恢复路径。

## 能力

### 新能力
- `workspace-session`：单用户工作区设置、会话 creation/switching 以及会话级工作树绑定。
- `chat-collaboration`：即时通讯聊天流、消息角色，以及用于编排器和角色代理的 @mention 路由。
- `agent-adapter`：最小适配器生命周期、适配器能力、本地 CLI `CodexAdapter`、`ScriptedMockAdapter`、统一事件、兜底行为以及权限护栏。
- `orchestrator`：P0 规划、任务分配、简单依赖处理、状态展示、重试、中断及结果汇总。
- `task-run-artifact`：核心 task/run/artifact 生命周期、TaskRunEvent 持久化以及 P0 实体边界。
- `worktree-diff`：Git 工作树隔离与真实差异 collection/rendering.
- `preview-deploy`：Vite React 预览运行器、预览卡片及基础部署卡片。
- `approval-control`：审批请求负载、基础审批界面，以及对部署、推送、受保护路径、非许可名单命令、破坏性编辑和网络访问的强制执行。

### 修改后的能力

## 影响

- 前端：Next.js App Router UI、聊天流、会话导航、任务卡片、带 Monaco 的差异卡片、预览 panel/iframe、部署卡片、审批控件。
- 后端：FastAPI API、SSE 事件流与回放、Pydantic 模式、SQLModel 持久化、编排器服务、适配器服务、worktree/diff/preview/deploy 服务。
- 数据库：SQLite P0 模式，设计为后续兼容 Postgres。
- 执行：Git CLI 会话工作树管理、命令白名单、受保护路径检查、Codex 本地 CLI 集成、脚本化演示变异运行器。
- 演示资源：Vite React 演示仓库、README、AGENTS.md 和演示脚本。
