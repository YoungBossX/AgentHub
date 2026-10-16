# AgentHub 技术架构说明

本文档描述本地个人项目的已实现架构（2026-10-16），比赛基线保留为历史背景。
当前能力的实际验收与本地/远程交付边界以 [项目状态](project-state.md) 和各专项记录为准。

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
| `apps/api/app/main.py` | FastAPI composition root，配置生命周期、CORS、领域 router，以及少量既有 helper 兼容桥接 |
| `apps/api/app/dependencies.py` | FastAPI 共享依赖入口，集中提供数据库会话、worktree、preview 和 deploy service |
| `apps/api/app/routes/health.py` | 基础健康检查路由 |
| `apps/api/app/routes/registries.py` | Provider config 和 deployment provider registry 只读路由 |
| `apps/api/app/routes/agent_settings.py` | Agent directory、profile draft、runtime config 和 memory settings 路由及响应映射 |
| `apps/api/app/routes/task_runs.py` | Task、PMO plan decision 和 TaskRun 生命周期路由及响应映射 |
| `apps/api/app/routes/task_artifacts.py` | Diff、Review、Workbench、command evidence、Preview 和 Deployment 路由 |
| `apps/api/app/routes/session_events.py` | Session SSE 持久游标重放、跨进程轮询和空闲心跳 |
| `apps/api/app/routes/message_history.py` / `message_history.py` | 稳定消息游标、独立 SQL 预览/分段全文读模型，不改写原消息或 Planner 输入 |
| `apps/api/app/routes/review_repairs.py` / `review_repairs.py` | 具体评审发现、源码绑定草稿/显式确认与原运行/修复历史 |
| `apps/api/app/automatic_validation.py` / `backend_validation.py` | 按内置 Vite/FastAPI 配置执行固定验证，并绑定源码、策略与执行代次 |
| `apps/api/app/context_budget.py` | 最终托管请求字符/字节/图片计量、冻结来源诊断及调用前门禁 |
| `apps/api/app/workflow_suite.py` / `workflow_evaluation.py` | 隔离代表性任务、显式业务契约与独立检查，保留首次/重试/分角色耗时和失败 |
| `apps/api/app/workflow_cohort.py` / `workflow_review_evidence.py` / `workflow_profiles.py` | 真实 Planner/编码/原生 QA 的同源码批次、冻结档案与完整 Read/报告/源码证据，不将配置或脚本等同模型审查 |
| `apps/api/app/contacts_contract.py` / `workflow_acceptance.py` | 固定 v1/v2 联系人浏览器/ASGI 契约、精确检查集合、双源码与验证策略绑定 |
| `apps/api/app/local_data.py` / `local_data_cleanup.py` / `maintenance_lease.py` | 离线 SQLite/Git/工作树一致快照、恢复、容量清单与受限缓存隔离；API 生命周期共享锁 |
| `apps/api/app/routes/workspaces.py` | Demo workspace 读取路由 |
| `apps/api/app/routes/targets.py` | Workspace targets、外部项目分析/注册、本地文件夹浏览和项目 provisioning 路由 |
| `apps/api/app/planning.py` | Planner 稳定入口与 LLM/fallback 路由编排，继续导出 `plan_for_message` 和既有解析 helper |
| `apps/api/app/planning_intents.py` | 提及、前端/应用契约意图、目标选择和安全边界解析 |
| `apps/api/app/planning_tasks.py` | Orchestrator/direct assignment/fallback Task 图构建与元数据生成 |
| `apps/api/app/run_engine.py` | TaskRun 编排、启动/提交门禁、执行控制器和收尾，保留兼容入口 |
| `apps/api/app/execution_ownership.py` | 不依赖引擎的不可变所有权记录、精确 run/queue/lock 校验和事务续租，旧入口只转发时钟 |
| `apps/api/app/provider_gateway.py` | provider 选择、健康、容量、熔断、fallback 证据和错误分类 |
| `apps/api/app/process_environment.py` | 按子进程角色构造最小环境，并在证据持久化前脱敏已配置密钥 |
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
| `apps/web/src/components/workspace-shell.tsx` | 主工作台 composition component，连接 Session、消息、任务、制品和上下文托盘 |
| `apps/web/src/components/use-session-event-refresh.ts` | SSE cursor、single-flight task refresh 和有界退避重试 hook |
| `apps/web/src/components/use-message-history.ts` | 初始 80/DOM 200 的稳定历史窗口，历史阅读期间合并更新与窗口外定位 |
| `apps/web/src/components/long-message-content.tsx` | 长正文按 12,000 Unicode 字符分段读取，只挂载当前段 |
| `apps/web/src/components/session-guidance.tsx` | 根据持久状态解释阶段、阻塞及现有下一步入口 |
| `apps/web/src/components/skill-references-editor.tsx` | 有界路径/内容与 UTF-8 文件导入，保留原 Skills 版本校验 |
| `apps/web/src/components/use-task-artifact-actions.ts` | TaskRun、PMO plan、Review、Preview、Deployment 和 Workbench 操作 hook |
| `apps/web/src/components/workspace-shell-header.tsx` | 当前会话 header、单聊/群聊切换和 demo pipeline 展示 |
| `apps/web/src/components/workspace-shell-state.ts` | 产物合并、预览选择和 composer context 的纯状态 helper |
| `apps/web/src/components/session-sidebar.tsx` | 左侧 Session 和 Agent 联系人入口 |
| `apps/web/src/components/chat-thread.tsx` | 中央聊天消息流 |
| `apps/web/src/components/message-composer.tsx` | 消息输入、制品上下文引用和发送载荷 |
| `apps/web/src/components/task-card-list.tsx` | 任务卡片取数/状态/编排、运行控制与 artifact chips |
| `apps/web/src/components/task-card-data.ts` | 纯计划/调度数据解释，统一解析与格式化 helper |
| `apps/web/src/components/task-plan-summary.tsx` / `artifact-message-cards.tsx` | 计划/PMO 摘要、制品卡片与操作门禁，继承现有 client boundary |
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
| TaskRunEvent | 持久化事件流，以 Session 级 `(created_at, id)` 游标支持 SSE 恢复和运行诊断 |
| Artifact | Diff、Review、Preview、Deploy、Workbench 等制品的统一载体 |
| Diff | 真实 Git Diff 或文件快照 Diff |
| Preview | Vite React 本地预览 URL、端口和健康状态 |
| Deployment | 诚实部署状态卡片，不伪造第三方成功 |
| Review | 非阻塞审查制品 |
| SessionExecutionLedger | 会话执行账本，用于摘要和上下文展示 |
| User | 本地用户记录，不代表已实现多用户认证 |
| ExternalProjectTarget | 外部目标注册和明确允许/禁止范围 |
| MemorySnapshot / MemoryItem | 冻结上下文及分作用域、可信度和版本的记忆条目 |
| AgentProfileDraft / AgentRuntimeConfig | 自定义档案/创建草稿、运行配置及冻结来源 |
| WorkspaceSkill / WorkspaceMcpConnection | 工作区技能包与受控文档连接配置 |
| MessageAttachment | 有界附件字节、提取元数据及不可变消息绑定 |
| SessionQueueEntry / TargetLock | 持久排队/访问模式与目标写互斥 |
| PreviewDeployJob | 有界预览/交付后台作业状态，不是通用后台 Agent |
| ArtifactVersion | 文档/制品版本，用户操作沿用既有证据来源 |

SQLite 仍使用现有幂等增量初始化，没有新引入迁移框架。以上当前实体来自 `models.py`，
原 P0 核心表限制不代表后续已验收专项未增加支持实体。

## 验证、上下文和数据维护

写入完成、Diff 就绪、固定检查通过、需求交互验收及模型评审为不同证据。
内置前端执行固定类型检查/可信构建/产物及有覆盖契约的浏览器检查；内置 FastAPI 执行
临时副本语法/七组 ASGI 契约，build 不适用。QA 不用模型 passed 覆盖硬失败或缺失证据。
回执绑定源码、策略、目标和执行代次，后续修改会过期；外部项目不是通用自动验收环境。
详见 [分项 QA 使用说明](local-usage.md#查看分项-qa-结果)。

最终请求在序列化/原生契约加入后统一检查 200,000 Unicode 字符、48 MiB 托管载荷及
4 张/32 MiB 图片上限（既有更严限制仍适用），超限在调用前拒绝，不截断必要规则或冻结选择。
此项不统计模型 Token、CLI 隐式输入或后续工具输出。Skills/MCP 仍受原工具和路径权限约束。

工作台用独立预览 DTO 与消息 `(created_at,id)` 索引进行有界读取，UI 不把截断正文写回 ORM。
维护 CLI 使用 API 共享/维护独占的 OS 文件锁和 SQLite 写保留；WAL 数据经 backup API 捕获。
恢复演练只修改新副本 Git 指针，DB 历史路径不改写。缓存预览绑定引用视图、完整候选哈希与
Git 注册，显式应用只移动已知缓存到隔离区，不永久删除，不清理会话/工作树/用户目标。

新增读写接口（本机 Host/Origin/控制头边界不变）：

| 接口 | 行为 |
| --- | --- |
| `GET /sessions/{id}/messages/page` | 默认 80、最多 200，before/after/around 互斥，置顶独立最多 16 |
| `GET /sessions/{id}/messages/{messageId}` | 单条有界元数据/预览，保留重新生成操作身份恢复 |
| `GET /sessions/{id}/messages/{messageId}/content` | offset/limit 按 Unicode 字符分段，最多 12,000；NUL 明确 409 |
| `GET /sessions/{id}/reviews/{artifactId}/repair` | 当前问题及修复/确认历史，不启动任务 |
| `POST /sessions/{id}/reviews/{artifactId}/repair/prepare` | 选择 1–8 项准备草稿，显式消息发送才进入既有执行路径 |
| `POST /sessions/{id}/reviews/{artifactId}/repair/confirm` | 依源码及记录版本明确标记用户核验；不冒充自动测试 |

客户端细节与开发维护命令见 [本地使用说明](local-usage.md)，对应专项验收保留夹具/真实执行边界。

## 可靠性边界

AgentHub 当前采用“本地可验证、边界保守”的可靠性策略：

- 每个 Session 一个 worktree，不把不同 Session 写到同一个工作区。
- Adapter 只能在分配的 worktree 或 target allowed path 内工作。
- `.git/`、`.env*`、`node_modules/`、`secrets/` 等路径受保护。
- Preview、staging build 和本地静态服务使用项目进程环境白名单，不继承 provider、
  数据库或 AgentHub 控制面密钥；Codex、Claude Code、Claude Planner 及 CLI 探针只接收
  对应 provider 的运行时环境。公开前缀变量由配置者负责保证确实可公开。
- Adapter、Preview 和 Deployment 的子进程输出在进入事件、TaskRun 错误或 artifact
  前执行精确敏感值与 secret assignment 脱敏；这属于意外回显防护，不替代 OS 沙箱，
  也不宣称阻止受信 provider CLI 主动变换自身凭据。
- Agent 执行期不静默安装依赖。
- TaskRun 终态会释放 target lock，避免旧运行长期阻塞。
- Diff/Review/Preview/Deploy 失败会写入事件和诊断，而不是只在后台日志里消失。
- SSE 使用标准消息帧；重连优先读取 `Last-Event-ID`。同进程低延迟快路径为每订阅者
  一个无 payload 的合并 wake，SQLite 回放按固定 high-water cursor 分成最多 100 行的
  批次；流同时每秒轮询持久事件，并在空闲 15 秒后发送无载荷注释心跳。
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

这些是后续工程方向，不能通过机械拆分或增加适配器数量证明改进：

| 问题 | 影响 | 建议 |
|---|---|---|
| `apps/api/app/planning_tasks.py` 仍包含较多任务构建器 | 27 个相关 builder 已与路由和意图解析隔离，但新增更多产品模式时可能再次增长 | 仅在新任务类型实质增加时再按 demo/external/fallback builder 拆分 |
| 执行核心仍较大：引擎 3,743、scope 2,989、task_runs 3,067 行 | 本轮已集中所有权/续租至独立 419 行模块，启动/提交门禁和编排仍复杂 | 后续按生命周期、快照和持久化职责继续专项拆分，保留精确所有权/代次/状态回归 |
| 任务卡片入口已降至 767 行 | 纯数据、计划摘要、制品卡片已分离；取数和状态编排仍集中 | 有实质新需求时再分离 artifact fetching hook，保持选中/错误/恢复状态一致 |
| `apps/web/src/components/preview-card.tsx` 较大 | Diff、Review、Preview、Deployment 和 Workbench renderer 仍集中 | 后续按 artifact kind 拆 renderer，并保持统一 card shell |
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
