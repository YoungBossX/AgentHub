# AgentHub 技术架构说明

本文档用于比赛技术文档和答辩。它描述当前已实现的本地单用户 Agent Coding Workspace，不把未来平台能力说成已完成能力。

## 核心链路

AgentHub 的核心不是普通聊天，而是把一次 AI 编程请求变成可审查的执行证据链：

```text
Message
-> Planner
-> Task
-> TaskRun
-> ProviderGateway
-> Adapter
-> Diff / Review / Preview / Deploy
-> TaskRunEvent / SSE
-> Web UI
```

对应到用户体验：

1. 用户在 IM 式会话中发送需求。
2. Planner 解析 `@orchestrator`、`@frontend`、`@backend`、`@qa` 等提及和任务意图。
3. Orchestrator 生成 2-4 步任务计划。
4. 用户或调度器启动 TaskRun。
5. ProviderGateway 选择 Codex、Claude Code 或 ScriptedMock 执行路径。
6. Adapter 在 Session 绑定的 worktree/target 内执行。
7. 系统采集真实 Diff、Review、Preview 和 Deploy card。
8. TaskRunEvent 通过 SSE 推送到前端，右侧产物面板展示证据。

## 运行时组件

| 组件 | 位置 | 职责 |
|---|---|---|
| Web 工作台 | `apps/web` | Next.js App Router UI，提供 Session、聊天、任务卡片、产物面板和运行设置 |
| API 后端 | `apps/api` | FastAPI 服务，承载会话、任务、运行、制品、预览、部署和诊断 API |
| Demo 应用 | `apps/demo` | Vite React 目标应用，用于 Agent 修改、Diff 和 Preview 演示 |
| Demo API | `apps/demo-api` | 独立 FastAPI demo backend target，用于后端 Agent 路径演示 |
| OpenSpec | `openspec/changes` | 记录功能演进、约束、验收标准和 AI 协作过程 |
| 项目文档 | `README.md`、`docs/*` | 记录运行方式、演示路径、架构说明和变更日志 |

## 后端代码地图

| 模块 | 作用 |
|---|---|
| `apps/api/app/main.py` | FastAPI 应用入口，配置生命周期、CORS，并挂载已拆分的领域 router；仍保留尚未拆出的会话、任务、运行、制品等主业务路由 |
| `apps/api/app/dependencies.py` | FastAPI 共享依赖入口，集中提供数据库会话、worktree、preview 和 deploy service |
| `apps/api/app/routes/health.py` | 基础健康检查路由 |
| `apps/api/app/routes/registries.py` | Provider config 和 deployment provider registry 只读路由 |
| `apps/api/app/routes/workspaces.py` | Demo workspace 读取路由 |
| `apps/api/app/routes/targets.py` | Workspace targets、外部项目分析/注册、本地文件夹浏览和项目 provisioning 路由 |
| `apps/api/app/planning.py` | 解析提及、识别任务意图、生成 Orchestrator/role task plan |
| `apps/api/app/run_engine.py` | TaskRun 执行入口，连接 adapter、diff/review/preview/deploy 收尾和后台运行 |
| `apps/api/app/provider_gateway.py` | provider 选择、健康、容量、熔断、fallback 证据和错误分类 |
| `apps/api/app/codex_adapter.py` | Codex CLI 适配器 |
| `apps/api/app/claude_code_adapter.py` | Claude Code CLI 适配器 |
| `apps/api/app/scripted_mock.py` | 确定性 fallback 适配器，会产生真实文件修改和 Diff |
| `apps/api/app/diffs.py` | Git Diff 和非 Git 文件快照 Diff 采集 |
| `apps/api/app/previews.py` | Vite React 本地预览启动、健康检查和 preview artifact |
| `apps/api/app/deployments.py` | Mock/local staging/manual handoff 部署卡片和状态证据 |
| `apps/api/app/run_diagnostics.py` | 将 TaskRunEvent、Artifact、Preview、Deployment 等投影为用户可读诊断 |
| `apps/api/app/session_queue.py` | Session 内运行队列与 target lock gate |
| `apps/api/app/target_registry.py` | workspace target 注册、allowed/denied path 和 preview/deploy 元数据 |
| `apps/api/app/models.py` | SQLModel 数据模型 |
| `apps/api/app/schemas.py` | API 响应和请求 schema |

## 前端代码地图

| 模块 | 作用 |
|---|---|
| `apps/web/src/app/page.tsx` | 读取后端健康、workspace、agents、sessions，并渲染主工作台 |
| `apps/web/src/components/workspace-shell.tsx` | 主工作台状态容器，管理 Session、消息、任务、SSE、产物选择和上下文托盘 |
| `apps/web/src/components/session-sidebar.tsx` | 左侧 Session 和 Agent 联系人入口 |
| `apps/web/src/components/chat-thread.tsx` | 中央聊天消息流 |
| `apps/web/src/components/message-composer.tsx` | 消息输入、制品上下文引用和发送载荷 |
| `apps/web/src/components/task-card-list.tsx` | 任务计划、TaskRun 状态、执行按钮、fallback 和 artifact chips |
| `apps/web/src/components/execution-trace.tsx` | 多 Agent 执行链路展示，汇总 Manager、Coding、Diff、Review、Preview 和 Deploy 阶段证据 |
| `apps/web/src/components/preview-card.tsx` | 右侧 Diff/Review/Preview/Deploy/Workbench 产物面板 |
| `apps/web/src/lib/api.ts` | 前端 API client 和共享类型 |

## 数据与证据模型

当前 demo 使用 SQLite。核心实体包括：

| 实体 | 说明 |
|---|---|
| Workspace | 工作区，当前 seed 会创建 `AgentHub Demo` |
| Session | IM 式会话，每个 Session 拥有独立 worktree 绑定 |
| Message | 用户和 Agent 消息，支持上下文制品引用 |
| Agent | Orchestrator、frontend、backend、qa 等角色 |
| Task | Planner 生成的可执行任务 |
| TaskRun | 一次任务执行尝试，记录 adapter、状态、错误和指标 |
| TaskRunEvent | 持久化事件流，用于 SSE 恢复和运行诊断 |
| Artifact | Diff、Review、Preview、Deploy、Workbench 等制品的统一载体 |
| Diff | 真实 Git Diff 或文件快照 Diff |
| Preview | Vite React 本地预览 URL、端口和健康状态 |
| Deployment | 诚实部署状态卡片，不伪造第三方成功 |
| Review | 非阻塞审查制品 |
| SessionExecutionLedger | 会话执行账本，用于摘要和上下文展示 |

## 可靠性边界

AgentHub 当前采用“本地可验证、边界保守”的可靠性策略：

- 每个 Session 一个 worktree，不把不同 Session 写到同一个工作区。
- Adapter 只能在分配的 worktree 或 target allowed path 内工作。
- `.git/`、`.env*`、`node_modules/`、`secrets/` 等路径受保护。
- Agent 执行期不静默安装依赖。
- TaskRun 终态会释放 target lock，避免旧运行长期阻塞。
- Diff/Review/Preview/Deploy 失败会写入事件和诊断，而不是只在后台日志里消失。
- ScriptedMockAdapter 是显式 fallback，不伪装成真实 Codex/Claude 成功。

## 技术选型理由

| 选择 | 理由 |
|---|---|
| FastAPI | 适合快速构建清晰 API，Python 生态便于连接 CLI、文件系统和测试 |
| SQLModel + SQLite | 单用户本地 demo 足够稳定，避免引入 Postgres/Alembic 运维复杂度 |
| Next.js + TypeScript | 前端状态复杂，TypeScript 能降低 API 类型漂移风险 |
| SSE | 当前主要是服务端向前端推送 TaskRunEvent，SSE 比 WebSocket 更简单且足够 |
| Session worktree | 比直接修改主仓库安全，能保留真实 Git Diff 和隔离每个会话 |
| ProviderGateway | 把 provider 选择、健康、容量、错误分类和 fallback 从业务路由中拆出 |
| ScriptedMockAdapter | 保证比赛现场可演示完整闭环，同时保持真实文件变更和诚实标记 |

## 当前优势

- 闭环完整：需求、规划、执行、Diff、Review、Preview、Deploy card 均可展示。
- 证据真实：Diff 来自文件变更，Preview 来自本地 Vite 服务。
- 边界诚实：不把 mock/fallback 说成真实 provider 成功。
- AI 协作过程可追溯：`AGENTS.md`、OpenSpec、change log 共同构成开发过程证据。
- 故障可解释：Run Diagnostics 能把 provider、queue、lock、preview、deploy 等问题分类。

## 已知技术债

这些问题是后续工程优化方向，不影响当前比赛主路径：

| 问题 | 影响 | 建议 |
|---|---|---|
| `apps/api/app/main.py` 仍保留部分主业务路由 | 已拆出 health、registries、workspaces、targets 和共享 dependencies，但 session/task-run/artifact/runtime-config 等路径仍较长 | 后续按 session、task-run、artifact、runtime-config 继续拆 FastAPI routers |
| `apps/api/app/planning.py` 规划逻辑集中 | 意图识别、fallback、任务生成耦合度较高 | 后续拆为 contracts、routing、fallback、normalization、validation |
| `apps/web/src/components/task-card-list.tsx` 较大 | execution trace 已拆出，但 run controls、artifact action 和 plan review 仍在同一组件 | 后续继续拆出 run controls、artifact chips、plan review panel |
| `apps/web/src/lib/api.ts` 类型和 client 集中 | API 类型很多，局部改动容易影响阅读 | 后续按 workspace/session/task-run/artifact/runtime 拆客户端模块 |
| 部分冻结/内部文档未公开跟踪 | 历史证据完整但公开入口需要筛选 | 当前只放行比赛必要文档，避免一次性提交内部草稿 |

## 答辩推荐讲法

技术讲解可以按 4 层展开：

1. 交互层：IM 式 Session、Agent 联系人、任务卡片和右侧产物面板。
2. 编排层：Message 进入 Planner，Orchestrator 生成 Task，TaskRun 承载每次执行。
3. 执行层：ProviderGateway 选择 Codex/Claude/ScriptedMock，Adapter 在 worktree/target 中执行。
4. 证据层：Diff、Review、Preview、Deploy、TaskRunEvent 和 Run Diagnostics 证明结果真实、可检查、可恢复。

收束时强调：

> AgentHub 现在不是完整企业协作平台，而是一个边界清晰、可运行、可验证的多 Agent 编程协作 MVP。它把 AI 产出从“聊天回答”推进到“有证据的工程交付”。
