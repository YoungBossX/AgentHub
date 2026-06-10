# AgentHub 项目状态

本文档记录了稳定的项目状态，后续的 Codex 提示可引用此文档，而无需重复长上下文块。

## 非 Git 外部项目证据链状态

2026-06-10 修复了新项目外部目录的 Diff/Review 证据链。AgentHub 现在在非 Git 外部 target 创建 TaskRun 时，会在现有 `preRunCheckpoint` 指标中记录允许路径内的文件快照。TaskRun 完成后，如果目标目录没有 Git `baseRef`，Diff 采集会使用执行前快照和当前文件树生成统一的 Diff artifact，后续 Review、ArtifactVersion、Ledger 和右侧证据工作台继续消费同一套 Diff/Review 产物。

为兼容修复前已经创建的非 Git 外部 TaskRun，如果没有历史文件快照，Diff 采集可以使用空基线补采允许路径内的当前文件，作为 `filesystem-snapshot:empty` 来源的新增文件 Diff。这用于恢复已落盘项目的证据可见性；后续新运行仍优先使用真实执行前/执行后快照。

Diff 或 Review 收尾失败不再只在后台包装层被静默吞掉。系统会写入 `artifact.diff.failed` / `artifact.review.failed` TaskRunEvent，并由 Run Diagnostics 归类为 `artifact_collection_failed`，因此 completed run 也能显示“代码执行完成但证据收集失败”的 contributing factor。

## 项目工作区准备边界

2026-06-09 新增了第一版项目工作区准备边界，用于修复新项目和已有项目混用 target 时的规划/校验问题。

当前能力：

- AgentProfile target 匹配现在统一支持 `external-frontend-*` 和 `external-backend-*`，避免 PlanValidator 与 Agent Directory / AgentSelectionPolicy 规则漂移。
- 新增 dry-run 项目准备合约和 `/workspaces/{workspace_id}/project-provisioning/plan` API。它只生成计划，不创建目录、不安装依赖、不运行 agent。
- 新项目请求可被表达为 frontend/backend target 草案、默认技术栈、ProjectProfile、safe validation commands 和 approval-required install commands。
- PlannerResponse 支持可选 `projectSetup` 元数据，用于后续让 LLM Planner 表达“先创建/注册项目边界，再分派 coding tasks”。

边界：

- 该切片不创建真实项目目录，不执行 scaffold，不运行 Claude/Codex，不绕过 Target Registry / PlanValidator / Guardrails。
- 依赖安装、网络访问、数据库迁移仍需审批；ProjectProfile 中的 build/test/check/dev 命令才是默认可验证命令来源。
- UI 配置卡片暂不实现。

## V2.6 事务性交付状态

V2.6 于 2026-06-09 启动。当前切片新增了一个独立的事务性交付合约，包含检查点证据、待定验证、回滚预检和显式重试模式决策。它读取现有的 TaskRun `preRunCheckpoint` 指标，但尚未执行实际的工作树回滚或重新连接 Run Engine 的终结逻辑。

该实现仍为 delivery/evidence 层。V2.1 持久化 Run Engine、V2.3 queue/target 锁、V2.5 策略引擎和 V2.7 诊断保持完整。

交付验证辅助函数现在可以将失败的命令证据、高风险审查证据或被拒绝的策略证据转换为 `review_required`。这仍然不会重新连接 Run Engine 的终结逻辑；集成是后续 V2.6 的任务。

接受和回滚辅助函数现在记录制品状态证据和检查点恢复意图。它们仍然不执行实际的工作树恢复；实际的 Run Engine / 恢复集成仍是 V2.6 的下一步。

交付决策现在可以记录为 TaskRunEvent，Run Diagnostics 将交付验证事件映射到验证时间线。此集成增加了证据可见性，但不改变 Run Engine 终结器的行为。

V2.6 冻结保留了此边界：事务性交付现在以证据和诊断的形式表示，而实际的破坏性回滚执行和硬终结器门控仍是后续工作。

## V2.5 策略引擎状态

V2.5 于 2026-06-09 启动。当前切片新增了一个独立的策略引擎合约，包含类别、结果、风险等级、审批类型、证据序列化和元数据编辑。它尚未接入 Run Engine、审批、部署或事务性交付的执行路径。

该引擎现在拥有用于命令、路径、网络、部署和平台维护决策的无副作用辅助函数。这些辅助函数复用了现有的目标注册表、护栏和项目命令策略语义，但执行路径尚未重新连接以依赖它们。

策略证据辅助函数现在将决策序列化为稳定、经过编辑的 `policy.decision` 负载。审批超时决策默认为拒绝；AgentHub 不得将缺失的 frontend/SSE 审批视为隐式批准。

V2.5 仍为 contract/helper 层。执行路径有意未完全重新连接；这属于 V2.6 事务性交付及后续集成阶段。

策略引擎仍为 decision/evidence 层；目标注册表、PlanValidator、护栏、项目命令策略和提供者网关仍是硬安全边界。

## V2.4 项目配置文件边界状态

V2.4 于 2026-06-09 启动。当前实现新增了 ProjectProfile 合约，并将配置文件摘要附加到外部项目分析、外部目标和工作区目标注册表响应中。配置文件描述了项目类型、框架、包管理器、允许和禁止的路径、配置的项目命令、预览策略、置信度、状态和警告。

配置文件元数据从现有目标字段派生，而非存储为新的数据库列，并且不改变执行行为。目标注册表、PlanValidator、护栏、提供者网关和现有命令策略仍是硬执行边界。

V2.4 还增加了对 project/profile 命令的命令策略覆盖，并将配置文件 ID、状态、预览策略和配置的配置文件命令注入到编码代理的目标指令中。通用仓库保持保守：不允许未配置的 shell 命令。

## V2.7 Run Diagnostics 后端状态

V2.7 后端诊断于 2026-06-09 添加，作为现有 TaskRun、TaskRunEvent、制品、预览和部署证据的投影层。AgentHub 现在在 `/task-runs/{task_run_id}/diagnostics` 暴露了 TaskRun 的安全只读诊断，并在 `/sessions/{session_id}/run-diagnostics-summary` 暴露了会话摘要。

该投影对常见的提供者、适配器、队列、锁、工作树、验证、审批、预览、部署、制品收集和未知故障进行分类；构建运行时间线；总结 provider/queue/lock/preview/deploy 健康状态；并返回下一步建议。诊断元数据在 API 响应序列化之前进行编辑和截断。

此后端切片不改变执行语义、不添加适配器、不添加 WebSocket/Docker/PR/external IM 行为，也不实现 V2.7 前端 UI。前端集成仍待定，因为在后端实现期间，现有的 `apps/web/src/components/**` 文件存在并发的未提交更改。

## V2.1 持久化 Run Engine 状态

V2.1 于 2026-06-09 完成。AgentHub 现在拥有一个持久的 TaskRun 执行边界，包含 `run_engine.py`、`RunSupervisor` 注册表、共享调度入口点、工作者声明/租约/心跳、最大运行超时处理、基于监督器的中断尝试、陈旧恢复、已完成运行的终结器边界以及任务跟踪持久化运行证据。
该实现保留了现有的适配器、调度器、目标注册表、
PlanValidator、worktree/diff/review/preview/deploy 证据以及 ScriptedMock
兜底行为。一个独立的长期运行工作进程、提供者断路器、显式数据库目标锁、完整策略引擎和事务性
回滚将推迟到后续的 Reliability V2 阶段。

## P24 状态

### P24-2 部署请求与状态证据

P24-2 在 2026-06-08 上添加了诚实的部署 request/status 证据。AgentHub
现在可以持久化手动外部交接部署卡片，以及针对不可用提供者（如 Vercel、Netlify 和自定义
静态主机）的阻塞外部提供者卡片。这些卡片记录提供者元数据、源预览链接、日志
和状态历史，但不声明第三方成功。

现有的模拟和本地暂存部署行为保持兼容。本地暂存仍基于真实的 build/serve 证据记录 ready/failed 状态。

### P24-1 部署提供者注册表

P24-1 在 2026-06-08 上添加了一个安全的部署提供者注册表。AgentHub 现在
通过 `/deployment-providers` 暴露本地暂存、手动外部交接、Vercel、Netlify 和自定义
静态主机部署提供者的元数据。

该注册表报告提供者 ID、显示名称、提供者类型、支持的制品
类型、支持的目标类型、auth/config 状态、可用性、
审批要求和密钥环境变量名称。它从不返回原始密钥值，也不执行第三方部署。

## P23 状态

### P23-6 聊天上下文中的制品引用

P23-6 在 2026-06-08 上添加了消息级别的制品上下文。后续消息现在
可以携带选定的制品 ID、制品版本 ID、安全摘要、选定的
text/section 元数据和引用的消息上下文。AgentHub 将其存储为
`Message.context_json`，并将其合并到 Planner 和编码代理使用的会话上下文包中。

除了差异、审查、预览和部署证据外，制品引用现在还支持 Markdown、文本和代码工作台制品。
在构建提供者可见上下文之前，元数据会被编辑。可执行的后续更改仍通过
对话路由器/Planner、PlanValidator、调度器和编码代理进行。

### P23-5 制品编辑器与版本历史 UI

P23-5 在 2026-06-08 上添加了轻量级制品编辑器控件。可编辑的
工作台制品现在在右侧制品面板中显示编辑、保存和取消控件。保存会调用制品工作台编辑 API 以创建新的制品版本并刷新工作台元数据；它不会直接写入存储库文件。

该面板显示版本历史，包括版本号、内容哈希和摘要。
未知或不支持的制品保持只读，并且不暴露 edit/save
控件。

### P23-4 制品工作台 UI

P23-4 在 2026-06-08 上添加了制品工作台 UI 支持。右侧制品
面板现在加载会话工作台元数据，将其与现有的
diff/review/preview/deploy 证据合并，并为尚未被证据卡片覆盖的制品显示一个专用的 document/workbench
轨道。

该面板渲染 markdown/text/code-like 制品版本，包括内容、
内容哈希、渲染器类型、可编辑性和版本历史。未知
制品使用安全的元数据兜底。聊天工作区保持简单：
详细信息保留在右侧制品面板中。

### P23-3 安全制品编辑 API

P23-3 在 2026-06-08 上添加了一个安全的制品工作台编辑 API。可编辑的
markdown/text/code 制品现在可以保存为新的 ArtifactVersion 记录，
包含父版本 ID、内容、内容哈希、编辑器来源和摘要。

制品编辑不会写入存储库文件、创建 git 差异或改变
TaskRun 证据。不支持的制品（如差异、审查、部署、
二进制或未知类型）会被诚实地拒绝。现有的 SQLite 数据库会获得
用于制品版本编辑元数据的兼容性列。

### P23-2 制品工作台 API

P23-2 在 2026-06-08 上添加了后端制品工作台 API 路由。AgentHub 现在
可以列出工作台的会话制品、加载制品渲染器元数据、
加载工作台安全版本元数据、暴露稳定的内容哈希，并返回
安全的编辑后元数据，而不暴露受保护的主机路径或密钥。

P23-2 保持现有的 `/artifacts/{artifact_id}/versions` 响应不变以实现向后兼容。制品编辑和工作台 UI 仍推迟到后续的 P23 任务。

### P23-1 制品版本元数据基础

P23-1 在 2026-06-08 上添加了制品工作台元数据辅助函数。AgentHub 现在
可以对 Web 预览、markdown/text 文档、代码片段、差异、审查、部署和未知兜底制品的制品渲染器类型进行分类。它还会从现有的 Artifact/ArtifactVersion 存储中派生可编辑标志、编辑后的安全元数据、稳定的内容哈希和版本元数据。

P23-1 中未实现制品编辑。该辅助函数仅为后续的工作台 API 和 UI 暴露安全的元数据基础。

## P22 状态

### P22 冻结

P22 已完成实现，并于 2026-06-08 进入冻结审查。该阶段
添加了代理目录 backend/API、兼容性策略、安全的仅元数据
草稿、运行时配置兼容性强制、Agent 目录设置 UI 以及安全草稿 UI。

P22 保留了 Planner 运行时提供者与编码代理之间的分离。它没有添加任意的 shell 命令代理、OpenCode、提供者市场、新的适配器或可执行的定制草稿代理。

### P22-6 草稿代理 UI

P22-6 在 2026-06-08 上的 Agent 目录设置页面中添加了一个安全的定制代理草稿表单。该表单支持仅元数据草稿的保存和取消控件。新的草稿使用安全的 `scripted_mock` 仅审查路径，声明 review/read-only 模式，保持 `safeForWrite=false`，并在验证前显示为 `draft_only` / 不可用 / 不兼容。

该 UI 不暴露任意的 shell 命令、不安全的工具权限或不受限制的文件系统控件。后端验证错误会被如实显示，而不会创建可执行的代理。

### P22-5 Agent 目录 UI

P22-5 在 2026-06-08 的 `/settings/agents` 处添加了一个专用的 Agent 目录设置页面。该页面加载工作区 Agent 目录 API，并显示联系人风格的卡片，其中包含提供者 ID、适配器类型、能力、支持的目标、支持的模式、安全标志、可用性、运行时选择的角色以及兼容性 reasons/warnings.。

目录页面支持按角色、提供者、能力、目标和状态进行本地筛选。筛选不会改变运行时配置。聊天侧边栏现在链接到 Agent 目录设置页面，同时将详细的提供者和兼容性配置保留在聊天工作区之外。

### P22-4 运行时配置兼容性集成

P22-4 在 2026-06-08 上将运行时配置验证与 Agent 目录兼容性连接起来。前端、后端和审查运行时角色选择现在复用驱动 Agent 目录的相同兼容性检查，包括提供者可用性、适配器对齐、角色支持、模式支持、能力支持、write/review 安全性以及仅草稿拒绝。

Planner 运行时验证仍然与编码代理兼容性分开：Planner 提供者配置会根据 Planner 提供者元数据和审查安全的 Planner 配置文件要求进行检查，从而保留了 P17 中 Conversation/Planner LLM 与编码代理之间的分离。无效的运行时选择会如实失败，并且仅验证请求不会持久化候选配置。

### P22-3 安全草稿代理管理

P22-3 在 2026-06-08 上验证了安全的定制代理草稿行为。草稿创建是仅元数据、工作区范围的，并限制为 review/read-only/debug 模式。草稿拒绝启用写入的配置文件、任意的 shell 命令、不安全的工具权限、不受限制的文件系统访问、未知的提供者以及适配器不匹配。

草稿会出现在 Agent 配置文件和 Agent 目录元数据中，但在存在后续经过验证的可执行策略之前，它们仍然保持 `draft_only`、不可用且不兼容执行。失败的、不安全的草稿请求不会持久化草稿。

### P22-2 Agent 兼容性策略

P22-2 在 2026-06-08 上添加了显式的 Agent 目录兼容性策略。AgentHub 现在会检查选定的 profile/provider 是否能够满足请求的角色、适配器、目标、模式、所需能力、提供者可用性以及 write/review 安全标志。

目录条目包含兼容性元数据，并且工作区范围的兼容性端点：

- `POST /workspaces/{workspace_id}/agent-directory/check-compatibility`

返回用户可读的原因和警告，而不暴露机密。仅草稿的配置文件在验证之前对于写入执行仍然不兼容。

### P22-1 Agent 目录后端

P22-1 在 2026-06-08 上添加了后端 Agent 目录基础。AgentHub 现在有一个派生的、工作区范围的 Agent 目录端点，它结合了现有的 AgentProfile 注册表条目、ProviderConfig 元数据、AgentRuntimeConfig 选择以及 AgentProfileDraft 元数据。

该目录包含内置条目和草稿条目，其中包含提供者 ID、适配器类型、能力标签、支持的目标、支持的模式、安全标志、状态、认证状态、可用性以及 `runtimeSelectedForRoles`。草稿条目默认情况下对于执行保持不可用。目录响应是仅元数据的，并且不暴露原始的 API 密钥、令牌、凭据或机密字段。

## P21 状态

### P21 冻结

P21 在 2026-06-08 上完成并通过了冻结验证。完整验证通过：

- `pnpm check`；
- `pnpm test`；
- `pnpm demo:api:test`；
- `git diff --check`；
- `openspec validate agenthub-p21-main-agent-orchestrator-pmo --strict`。

P21 仍然限定于 PMO 协调和说明。它没有添加任意的计划编辑、自动冲突合并、auto-stash/discard 行为、新的编码适配器或多用户审批工作流。

### P21-5 PMO 工作区 UI

P21-5 在 2026-06-08 上添加了 PMO 协调 UI。任务卡片现在显示 `planJson.pmoDecision` 状态、参与者、原因、下一步操作摘要，以及用于批准、拒绝或请求对待审查计划进行澄清的控件。这些控件调用 P21-2 中添加的窄范围 PMO 计划决策端点，并刷新任务时间线。

mission/context 面板现在显示一个紧凑的 PMO 就绪摘要，该摘要源自
当前任务：就绪、等待、阻塞，以及最多三条推荐的下一个操作标签。这保持了聊天界面的轻量化，同时使主代理/PMO 的协调可见。

### P21-4 PMO 任务追踪证据

P21-4 在 2026-06-08 上为任务追踪响应添加了经过编辑的 PMO 协调证据。任务追踪现在包含 PMO 计划决策、调度器阻塞、规划器兜底和冲突摘要的 `pmoEvidence` 条目。该证据源自现有的任务计划元数据和阻塞状态；它不声称执行成功。

PMO 证据会编辑类似机密的值和受保护的主机路径，例如 `.env`、`.git`、`node_modules`、`.venv` 和 `secrets` 路径，同时保留检查所需的安全相对应用程序路径。

### P21-3 PMO 图就绪状态和下一步操作

P21-3 在 2026-06-08 上添加了 PMO 派生的任务追踪协调元数据。任务追踪响应现在包含就绪、等待依赖、等待目标锁定、阻塞、运行中和已完成任务的 `taskGraphReadiness` 组。这些组源自现有的任务状态和调度器元数据；它们不会单独持久化。

任务追踪 `nextActions` 现在包含可审计的 PMO 指导，用于启动就绪任务、检查阻塞器、对 PMO 审查的计划进行 approving/rejecting/requesting 澄清、重试失败任务、选择显式兜底，以及批准或拒绝等待中的 TaskRun。这些下一步操作仅为指导：实际执行仍通过现有的 TaskRun、重试、兜底和批准端点进行。

### P21-2 PMO 计划决策操作

P21-2 在 2026-06-08 上添加了狭窄的 PMO 计划决策 API 操作：

- `POST /tasks/{task_id}/plan-decision/approve`；
- `POST /tasks/{task_id}/plan-decision/reject`；
- `POST /tasks/{task_id}/plan-decision/clarification`。

这些端点仅接受可选的 `reason`。它们通过 PMO 元数据助手更新 `planJson.pmoDecision`，并拒绝原始计划变更字段，例如客户端提供的 `planJson`。批准使任务保持有资格通过现有的调度器和 TaskRun 创建路径；它不会直接启动 TaskRun，也不会绕过 PlanValidator 或目标注册表行为。拒绝和澄清将任务标记为阻塞，并且不会创建 TaskRun。

### P21-1 PMO 决策元数据基础

P21-1 在 2026-06-08 上添加了第一个主代理/PMO 基础。AgentHub 现在拥有稳定的任务 `plan_json` 元数据助手，用于 `pmoDecision` 状态：`pending_review`、`approved`、`rejected` 和 `clarification_needed`。

决策元数据包括模式版本、状态、执行者、原因、时间戳和下一步操作摘要。它存储在现有任务计划 JSON 中，并通过任务追踪任务条目公开，因此没有引入新的持久化表。不受支持的原始计划变更字段（例如客户端提供的 `planJson`）会被 PMO 助手边界拒绝。

P21-1 不添加 approve/reject/clarification API 端点，不启动或停止 TaskRun，也不更改调度器、PlanValidator、目标注册表或护栏行为。这些是后续 P21 任务。

## P20 状态

### P20-5 制品导航工作台

P20-5 在 2026-06-08 上改进了制品导航。任务时间线制品现在作为面向用户的证据卡片呈现，带有中文操作标签，用于查看差异、审查、预览、部署、创建 review/deploy 卡片，以及将制品用作后续上下文。右侧制品面板的空状态现在说明可以从任务时间线中选择差异、审查、预览和部署证据。P20-5 不添加制品编辑功能。

### P20-4 代理、目标、记忆和证据摘要

P20-4 在 2026-06-08 上改进了 mission/context 面板。该面板现在显示当前目标、活跃角色代理、选定的 frontend/backend 目标、缩短的记忆快照 ID、最新证据状态、上次成功的适配器、最近更改的文件和部署 provider/status.。它从现有的会话和账本响应中派生这些信息；不需要 API/schema 更改。

### P20-3 只读计划审查界面

P20-3 在 2026-06-08 上完成了只读计划审查界面。任务卡片已经显示规划器理由、角色、目标、计划文件、验收标准、验证期望和只读状态。P20-3 添加了用户可读的规划器证据，用于兜底 source/reason、提供者 ID、验证结果、错误代码和安全错误摘要。未添加计划变更控件。

### P20-2 对话模式和上下文显示

P20-2 在 2026-06-07 上添加了本地 Direct/Group 对话模式显示。模式控制仅为 UI 框架，不会更改后端路由、调度器、PlanValidator 或任务创建行为。消息编辑器现在在发送前显示引用的消息和选定的制品作为待处理上下文，并带有一个清除上下文控件。

### P20-1 会话导航优化

P20-1 在 2026-06-07 上添加了每日工作区会话过滤。左侧边栏现在包含一个会话搜索字段、过滤后的会话计数、选定会话的任务焦点摘要和一个空搜索状态。过滤是本地 UI 行为：它不会清除选定的会话，不会创建消息，也不会
创建任务或 TaskRun。

## 本地文件夹选择器目标注册

从 2026-06-07 开始，运行时工作区设置可以通过本地文件夹选择器注册外部前端或后端目标，而无需用户手动输入允许的路径。选择器会暴露安全起始位置，例如桌面、文档和工作区相邻文件夹，过滤 hidden/protected 文件夹，并支持 parent/child 文件夹导航。

所选文件夹的注册使用 `allowedPaths: ["*"]`，因此选定的项目文件夹成为写入范围，而受保护路径（例如 `.git`、`node_modules`、`.env`、虚拟环境、构建输出和密钥）仍被目标策略和防护机制拒绝。运行时设置 UI 允许用户选择所选文件夹应成为前端目标还是后端目标。

## P18c 状态

### P18c 实时内存合规库应用冻结

P18c 于 2026-06-07 完成。

最终的实时内存合规冒烟测试使用了仅限业务的提示：
```text
帮我在桌面开发一个简单的图书管理系统。有登录页面，初始账户和密码是 18088888888 / 888888。登录后进入管理页面，只需要有图书管理功能：加入图书、删除图书、修改图书、查询图书。
```
提示未重申长期记忆规则。AgentHub 将任务路由至外部前端目标 `external-p18c-library-app`，并通过真实的 CodexAdapter 运行，在 `/Users/luotianhang/Desktop/agenthub-rehearsals/p18c-library-app` 下创建了一个 Vite + React + TypeScript 图书馆管理应用。

最终证据：

- 会话：`9dd8ff1d-be15-4114-b47c-4d3664838e53`
- 任务：`11dda813-bfb6-4130-b410-08fe90a74c95`
- 任务运行：`09d77fb3-f81a-44e0-9b47-3f403ac58579`
- `memorySnapshotId`：`3a77e409-daae-428a-b739-6bc187105c70`
- Adapter/provider：`codex` / `local-codex-cli`
- 差异：`7a6dd596-3d9d-4810-b1fb-c7a66d3ac67f`
- 审查：`a9ac0c07-547a-4bbd-b2a1-6aa867524304`
- 通过 check/test/build 的证据：
  `801bad3c-a9f7-479f-8e09-59e1eaadf9e8`、
  `c1a86bc8-7eba-48c5-a377-c65a0f488941` 和
  `34d4070e-cd5d-450f-bd79-ca449f6b9511`
- 预览：`53d8cd5e-0322-449e-a10d-9456633a23e2`，冒烟测试期间健康
- 预发布：`20d26ddf-736e-49d6-abe0-25e7b0b843db`，冒烟测试期间就绪

生成的应用包含使用 `18088888888 / 888888` 的登录功能、一个管理页面、
add/delete/edit/search 图书流程以及 localStorage 持久化。未创建后端或数据库。

合规性指标：

- 偏好召回率：`1.0`
- 项目记忆召回率：`0.8333`
- 跨代理一致性率：`1.0`
- 快照一致性率：`1.0`
- 变更日志缺失率：`0.0`
- 目标边界违规次数：`0`
- 持久化记忆违规次数：`0`
- 提供者证据违规次数：`0`
- 任务成功增量：未知/不确定，因为对照组是确定性空运行，而非可比较的实时无记忆运行

后续操作是必需的，并已如实记录。初始的 check/test/build 失败，因为外部 Vite 项目没有 `node_modules`；在用户明确允许为外部 P18c 项目安装依赖后，仅在该处运行了 `pnpm install`，且 check/test/build 通过。Preview/staging 还暴露了一个外部目标预览根目录的缺口，已通过提交 `15e4702` 修复。

配置的 DeepSeek 规划器未运行，因为 API 进程环境无法使用 `DEEPSEEK_API_KEY`；该任务使用了经审计的外部目标兜底规划器。此限制已记录在 `docs/p18c-freeze-review.md` 中。

### P18c 记忆规则简化

在首次实时规划器尝试将图书馆管理应用视为更广泛的 frontend/backend 计划（而非仅使用 localStorage 的应用）之后，P18c 记忆规则于 2026-06-07 进行了简化。当前测试中的活跃规则现以通用中文长期记忆形式编写：

- 若无特殊说明，新建项目统一存放至 `~/Desktop/agenthub-rehearsals/` 目录下；
- 前端项目默认采用 Vite + React + TypeScript 技术栈；
- 应用若无明确要求，默认使用 localStorage 做数据持久化，不对接后端 / 数据库；
- 涉及代码变更时，需同步更新 `docs/change-log.md`；
- 未明确开启平台维护模式时，禁止修改 AgentHub 平台底层代码；
- 若无任务运行记录、代码差异文件、构建日志等佐证材料，不得宣称第三方模型服务调用成功。

P18c 记忆播种辅助工具在创建或重用当前规则之前，会从同一来源归档过时的活跃 P18c 规则，以便新快照不会将先前狭窄的英文演示措辞与新的通用规则混合。

### P18c-3 实时图书馆应用执行阻塞

在简化记忆规则后，P18c-3 于 2026-06-07 重试。

证据：

- 会话：`b11777d4-3dea-47e0-8a71-da8e5749c38a`
- 消息：`f9ded109-47ac-4ff8-9569-c450c189b67e`
- 任务：`0d85e40e-9626-496b-bdff-234415e47ac1`
- 任务运行：`1f44056b-b1d9-420b-9bb3-98b984760d18`
- `memorySnapshotId`：`a27dec94-85c9-4d4d-b5be-6564b8320125`
- 适配器：`claude_code`
- 提供者：`local-claude-code-cli`
- 最终状态：`failed`
- 错误：`CLAUDE_CODE_EXIT_ERROR`，`API Error: Unable to connect to API (ConnectionRefused)`
- 制品：无

简化的记忆规则充分改善了路由，得以创建外部前端任务并启动真实的 ClaudeCodeAdapter 任务运行。实时应用未实现，因为 Claude Code 无法连接到其 API 运行时。未使用 ScriptedMock 来声称实时记忆合规性。

### P18c-2 会话与外部目标设置

P18c-2 于 2026-06-07 完成。

AgentHub 现在拥有一个 P18c 设置辅助工具，用于准备允许的桌面演练根目录、创建空的目标外壳
`~/Desktop/agenthub-rehearsals/p18c-library-app/src`、注册或重用
外部前端目标 `external-p18c-library-app`、在活跃记忆存在后创建新的 P18c
会话，并记录设置证据：

- `memorySnapshotId`；
- 活跃的 P18c 记忆规则 ID；
- AGENTS.md 哈希值；
- CLAUDE.md 哈希值；
- 目标注册表版本；
- 运行时配置版本；
- 上下文包哈希值。

P18c-2 不实现图书馆管理应用，也不运行 ClaudeCodeAdapter、CodexAdapter 或 ScriptedMock。准备的目标外壳仅是后续实时提供者任务的安全外部工作区边界。

### P18c-1 记忆合规性测试框架

P18c-1 于 2026-06-07 完成。

AgentHub 现在拥有一个用于 P18c 实时图书馆管理应用记忆冒烟测试的确定性合规性测试框架。该框架定义了精确的纯业务用户提示、正在测试的六条活跃记忆规则、预期的桌面演练位置、Vite + React + TypeScript 技术栈、localStorage 持久化、变更日志要求、平台边界、提供者证据要求，以及
快照一致性要求。

检查器报告：

- `project_location_memory_violation`；
- `frontend_stack_memory_violation`；
- `persistence_memory_violation`；
- `memory_compliance_violation`；
- `target_boundary_violation`；
- `provider_evidence_violation`；
- `snapshot_consistency_violation`。

P18c-1 不运行 ClaudeCodeAdapter、CodexAdapter 或 ScriptedMock。它不实现图书馆管理应用，也不改变运行时提供者行为、目标注册表、PlanValidator 或 Guardrails。后续的 P18c 任务将创建新会话，在可用时运行实时提供者冒烟测试，并收集 TaskRun/diff/build/review/preview 证据。

## P18b 状态

### P18b 内存有效性演练

P18b 于 2026-06-05 完成。

AgentHub 现在在 P18 内存控制平面之上拥有一个有界的内存有效性演练层。它定义了确定性的、逼真的场景，用于：

- 中文用户偏好回忆；
- 项目规则对变更日志期望的合规性；
- stale/archived 内存排除；
- 对不受信任的外部建议的提示注入阻止。

P18b 评估器将内存最小化控制上下文与启用内存的处理上下文进行比较，记录内存快照 ID，计算偏好回忆率、内存精度@5、陈旧内存注入计数、提示注入写入阻止率、快照一致性率，并在缺乏可比较的实时任务证据时，明确将任务成功增量/变更日志缺失率标记为未知。

P18b 冒烟测试结果显示，所有四个内置场景在没有陈旧内存注入的情况下都有确定性改进。没有声称实时 Planner 或编码代理成功，因为 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`MIMO_API_KEY` 和 `ANTHROPIC_API_KEY` 在进程环境中未设置。详细信息记录在 `docs/p18b-freeze-review.md` 中。

P18b 不添加自动长期学习、embeddings/RRF/graph 检索、提供者市场、生产部署或任何护栏绕过。内存仅作为指导；目标注册表、PlanValidator、Guardrails、运行时配置和调度器策略仍然是执行边界。

## P17 状态

### P17c 后 UI 和工作区设置更新

截至 2026-06-02，工作树包含超出冻结的 P17c OpenSpec 范围的 UI 和设置更新。一旦提交，将其视为当前实现事实，但不要假设它们代表新的完整平台范围。

聊天工作区已视觉刷新为更简单的三面板工作台。详细配置已从主聊天页面移出，进入设置路由：

- `/settings/contacts` 显示当前内置的 Agent 联系人列表和本地 Direct/Group 视觉模式控件；
- `/settings/runtime` 包含 Agent 运行时提供者设置以及工作区目标设置；
- `/settings/other` 是保留的占位路由。

运行时设置页面现在也公开了以前仅在后端的工作区配置：

- 通过 `GET /workspaces/{workspaceId}/targets` 加载工作区目标列表；
- 通过 `POST /workspaces/{workspaceId}/external-targets/analyze` 进行外部项目分析；
- 通过 `POST /workspaces/{workspaceId}/external-targets` 进行外部项目注册；
- 通过 `PATCH /sessions/{sessionId}/target-selection` 进行每个会话的 frontend/backend 目标选择。

这使得 P9 外部工作区模式和 P16 运行时配置对用户可见，但不会创建多用户工作区共享、云项目导入、任意文件系统访问或生产部署。产品边界仍然是：具有 IM 风格交互的本地单用户 Agent 编码工作区。

### P17c 运行时设置页面

P17c 于 2026-06-01 完成。

AgentHub 正在将详细的 Agent 运行时设置从主聊天工作区移出，放入专用的 `/settings/runtime` 页面。聊天页面现在只保留一个紧凑的设置入口点，以便会话列表、Agent 联系人、聊天线程、任务、制品和任务轨迹仍然是主导的工作区体验。

运行时设置页面重用现有的 P16/P17b 运行时配置 API，并保持 Planner、前端、后端和审查运行时配置分离。编辑内容作为草稿状态保存，直到点击保存；取消会恢复已持久化的配置；诸如 `unchecked`、`missing_key` 和 `not_required` 之类的 provider/runtime 状态会以面向用户的中文标签和仅环境变量的 API 密钥指导来呈现。

### P17b 多提供者 Planner API

P17b 实现和演练于 2026-06-01 完成。

AgentHub 现在拥有 AgentHub 原生 Planner API 提供者支持，用于协议族和预设：

- `openai_responses` / `openai_api`；
- `openai_compatible_chat` / `deepseek_api`、`mimo_api` 和 `custom_openai_compatible`；
- `anthropic_messages` / `anthropic_api`；
- 现有的 `claude_cli`、`fake_test` 和 `disabled`。

Planner API 提供者仅生成 `ConversationOutcome` / PlanDraft。它们不执行代码，也不替代 ClaudeCodeAdapter 或 CodexAdapter 编码代理。运行时配置仅存储提供者 preset/model/baseUrl/timeout/apiKeyEnv 元数据；原始 API 密钥从环境变量读取，并且不
返回给 UI、任务追踪、规划器证据或日志。

冻结演练并未声称真实的 DeepSeek 或 MiMo 成功，因为
`DEEPSEEK_API_KEY` 和 `MIMO_API_KEY` 不在进程
环境中。缺失密钥行为、伪造客户端 OpenAI/OpenAI-compatible/
Anthropic 成功路径、`你好` 聊天路由、Breakout 任务规划、不安全
请求拒绝以及 P6-P17 回归测试均已通过。详情记录在
`docs/p17b-freeze-review.md` 中。

### P17-8 演练与冻结审查

P17-8 于 2026-05-29 完成。

P17 已准备好冻结。AgentHub 现在拥有一个以 ConversationOutcome 为先的
编排器边界，用于处理无提及和 `@orchestrator` 消息：

- 普通聊天（如 `你好`）可以生成 `orchestrator` 回复，而无需
  创建 Task 或 TaskRun；
- 编程请求可以生成一个经过验证的 `task_plan`，该对象进入
  PlanValidator，然后进入现有的 scheduler/execution 路径；
- LLM 任务计划绕过传统的信号词门控，直接进入模式
  验证和 PlanValidator；
- 澄清、拒绝、需要批准以及不支持的结果仍保持为不可执行回复；
- 后续消息可以通过相同的 LLM 边界进行路由，并携带任务追踪
  和会话上下文；
- disabled/unavailable LLM 路由在创建安全兜底任务时，返回友好的聊天兜底
  和经过审计的前端兜底元数据。

P17 保留了 P16 建立的运行时边界：规划器运行时处理
对话和 PlanDraft 生成，而 Frontend/Backend/Review 编码
代理仅在经过验证的可执行任务被调度后运行。详情记录在
`docs/p17-freeze-review.md` 中。

## P16 状态

### P16-7 演练与冻结审查

P16-7 于 2026-05-29 完成。

P16 已准备好冻结。冻结审查复用了 P15b 风格的 Breakout 真实
planner/coding 证据，并通过自动化模型、API、UI、解析、证据和安全测试验证了新的 P16 运行时配置层。

配置的 P16 目标为：

- 规划器：`claude-cli-planner` / `claude_cli`；
- 前端：`local-claude-code-cli` / `claude_code`；
- 后端：`local-codex-cli` / `codex`。

运行时配置现在会影响实际的 Planner/Frontend/Backend 解析，并且
在 TaskRun 响应和任务追踪中可见。无效或不安全的配置会被
拒绝，平台维护仍然需要明确的平台模式和批准。详情记录在 `docs/p16-freeze-review.md` 中。

### P16-6 安全与策略执行

P16-6 于 2026-05-29 完成。

运行时配置现在被明确的安全测试和 role/mode 验证所覆盖：

- 后端运行时配置无法以 `platform_maintenance` 模式保存；
- 运行时选择的后端提供者不会绕过目标注册表、
  平台模式元数据或批准要求；
- 平台维护仍然进入 `waiting_approval` 并保持可审计；
- ScriptedMock 仍然表示为 mock/fallback 元数据，而非真实提供者
  成功。

P16-6 未添加新的权限范围或自定义 shell 命令代理。

### P16-5 运行时配置证据

P16-5 于 2026-05-29 完成。

运行时配置解析现在在执行证据中明确显示：

- 规划器证据记录所选的运行时配置 source/provider/profile
  （当运行时配置选择规划器提供者时）；
- TaskRun API 响应除了 `metricsJson` 之外，还暴露了
  `providerAssignment` 和
  `runtimeConfigResolution` 作为顶层字段；
- 任务追踪的任务运行条目包含 `runtimeConfigResolution`，以便 UI
  和下游工具可以审计哪个已保存的配置影响了执行。

证据仅包含 provider/profile/adapter/config-source/fallback-policy
元数据。它不会暴露密钥或受保护的主机路径。

### P16-4 运行时配置解析

P16-4 于 2026-05-29 完成。

已保存的工作区运行时配置现在参与提供者解析：

- 启用的规划器配置在选择规划器提供者时优先于环境
  默认值；
- 启用的前端配置在选择 TaskRun adapter/provider 时优先于
  `AGENTHUB_DEFAULT_CODE_ADAPTER`；
- 启用的后端配置在选择 TaskRun adapter/provider 时优先于
  `AGENTHUB_DEFAULT_CODE_ADAPTER`；
- 显式的 TaskRun 适配器覆盖仍然保持显式且可审计；
- 未配置的角色保留之前的默认行为。

运行时选择记录在 TaskRun 指标中，位于提供者分配
元数据和 `runtimeConfigResolution` 下。P16-5 将扩展这些证据在
API 响应和任务追踪中的暴露位置。

### P16-3 代理运行时设置 UI

P16-3 于 2026-05-29 完成。

Web 工作区现在在侧边栏中包含一个代理运行时设置面板。
它加载工作区运行时配置，并允许用户仅从现有的安全 AgentProfile 和
ProviderConfig 选项中配置核心的规划器、前端和后端角色。

UI 显示提供者徽章数据、适配器类型、能力标签、支持的
目标、模式、status/auth 可用性、配置来源以及运行时配置 API 返回的验证
warnings/errors。保存操作会通过 P16-2 API 持久化工作区配置。

P16-3 仅涉及 UI。它尚未使 planner/frontend/backend 执行
使用已保存的运行时配置；这仍是 P16-4 的任务。
### P16-2 运行时配置 API

P16-2 于 2026-05-29 完成。

AgentHub 现在暴露了工作区运行时配置 API：

- `GET /workspaces/{workspaceId}/runtime-config`；
- `POST /workspaces/{workspaceId}/runtime-config/validate`；
- `PUT /workspaces/{workspaceId}/runtime-config`。

该 API 返回有效配置、配置来源、可选的 AgentProfile 元数据、可选的 ProviderConfig 元数据以及验证 errors/warnings.。在持久化之前，它会诚实地拒绝无效的 profile/provider/role/mode 组合。

Provider 元数据现在包含 Planner Agent 配置路径的 `claude-cli-planner`。P16-2 仅暴露和验证运行时配置；实际的 planner/frontend/backend provider 解析仍推迟到 P16-4。

### P16-1 Agent 运行时配置模型

P16-1 于 2026-05-29 完成。

AgentHub 现在拥有一个工作区范围的 Agent 运行时配置持久化模型，用于核心角色：

- planner；
- frontend；
- backend；
- review。

每个角色配置可以存储 `agentProfileId`、`providerId`、`adapterType`、`mode`、`enabled` 和 `fallbackPolicy`。当不存在运行时配置时，有效配置来源为 `default`，并且所有角色覆盖保持禁用，因此现有的 environment/default provider 行为得以保留。

P16-1 仅添加了模型、序列化辅助函数、默认解析和测试。它尚未添加 API 端点、UI、provider 解析、证据集成或策略执行。

## P15b 状态

### P15b-7 真实 LLM Planner Breakout 演练与冻结审查

P15b-7 于 2026-05-29 完成。

AgentHub 使用真实的 LLM planner provider 验证了 P15b 的验收路径：

- `AGENTHUB_LLM_PLANNER_PROVIDER=claude_cli` 为 Breakout 请求生成了真实的 `llm_v1` 计划；
- planner 证据记录了 provider 来源 `real_llm` 并通过了验证；
- 首次编码运行使用了 `ClaudeCodeAdapter`，完成，生成了差异，产生了脚本化的审查制品，并生成了健康的预览；
- 本地暂存部署最初失败，因为 `pnpm build` 在 `apps/demo/src/components/BreakoutGame.tsx` 中捕获了 `TS18047: 'ctx' is possibly 'null'`；
- 后续的修复任务保留了构建失败的上下文，并通过现有的 TaskRun 路径运行；
- 使用 `ClaudeCodeAdapter` 的首次重试失败，出现真实的 provider/runtime JSON 角色错误，该错误被如实记录；
- 后续真实的 `CodexAdapter` 后续任务完成了修复，收集了差异和审查，通过了 `pnpm build`，生成了健康的预览，并创建了就绪的本地暂存部署。

P15b-7 还强化了演练路径，其中烟雾测试暴露了真实的协调问题：

- 真实的 planner 提示约束现在阻止散文、重复的 JSON、过多的任务、不支持的制品类型以及不稳定的依赖别名；
- 安全的标量归一化处理 planner `version` 和 `guardrailNotes` 变体，而不接受不安全的字段；
- PlanValidator 允许配置的命令期望，并带有安全的结果后缀，例如 `pnpm build succeeds`；
- 来自 LLM 输出的基于目标的依赖别名在任务图验证之前被归一化；
- 直接的前端分配包括用户请求中显式引用的安全文件路径；
- 计划的 `llm_v1` 审查任务可以通过生成的审查制品来满足；
- 下游写入任务可以将已完成的上级依赖差异文件视为安全的脏工作区上下文。

详细证据记录在 `docs/p15b-freeze-review.md` 中。推荐标签：`p15b-real-llm-planner-engine-freeze`。

### P15b-6 Planner 证据与任务追踪

P15b-6 于 2026-05-28 完成。

AgentHub 现在记录已创建的 `llm_v1` 任务的 planner 证据：

- provider ID 和 provider 类型；
- planner 来源，例如 `real_llm`、`fake_test`、`disabled`、`fallback` 或 `deterministic`；
- provider 持续时间；
- 验证结果；
- planner 状态；
- 计划理由和计划 ID；
- 已创建的任务 ID；
- 可用的兜底原因和归一化错误摘要。

任务追踪条目暴露了 LLM 创建任务的 `plannerEvidence`、disabled/fallback 确定性计划以及普通确定性计划。证据不包括原始 provider 输出、凭据或受保护的主机路径。

P15b-6 不运行真实的 Breakout planner 演练；这仍由 P15b-7 负责。

### P15b-5 针对真实 LLM 输出的 PlanValidator 强化

P15b-5 于 2026-05-28 完成。

PlanValidator 现在是一个针对真实 LLM planner 输出的更强安全门：

- 验证已注册的目标路径策略和受保护的目标边界；
- 要求 `agenthub-platform` 工作的平台模式和审批元数据；
- 检查 AgentProfile 支持的目标和支持的模式；
- 拒绝分配给不安全写入的 agent 的写入生成计划；
- 拒绝分配给不安全审查的 agent 的审查计划；
- 验证候选任务图内部的依赖键引用；
- 拒绝未为目标配置的验证命令。

不安全的 LLM 候选计划在任务持久化或 TaskRun 自动启动之前被拒绝。P15b-5 尚未将 planner 证据添加到任务追踪或运行真实的 Breakout planner 演练。
### P15b-4 结构化输出解析与验证

P15b-4 于 2026-05-28 完成。

AgentHub 规划器解析现在更安全地支持真实提供者输出：

- 直接 JSON 仍然被接受；
- 嵌入在散文或围栏块中的单个外层 JSON 对象可以被提取；
- 多个外层 JSON 负载被视为歧义并被拒绝；
- 提取的负载必须通过 `PlannerResponse` 模式；
- 未知的目标、角色和路径不会被静默归一化为有效值。

P15b-4 尚未在现有 target/task 图验证之外强化 PlanValidator 策略检查，未扩展任务追踪证据，也未运行真实的 Breakout 规划器演练。

### P15b-3 真实规划器提供者实现

P15b-3 于 2026-05-28 完成。

AgentHub 现在拥有一条真实的规划器提供者路径：

- `AGENTHUB_LLM_PLANNER_PROVIDER=claude_cli` 选择 Claude CLI 规划器提供者；
- 该提供者使用 Claude CLI 打印模式，带有仅规划提示，并要求 PlannerResponse JSON；
- `AGENTHUB_LLM_PLANNER_TIMEOUT_SEC` 控制规划器超时；
- stdout 被保留为原始规划器输出，供后续结构化解析使用；
- 认证、配额、超时、缺少可执行文件、空输出和运行时故障被归一化为规划器提供者结果元数据；
- 提供者结果元数据保持安全，不包含密钥或原始命令凭据。

P15b-3 未运行真实的 Claude 规划器冒烟测试。它仅使用假命令运行器实现并测试了提供者路径。结构化输出提取、PlanValidator 强化、任务追踪证据扩展和 Breakout 规划器演练仍是后续 P15b 任务。

### P15b-2 规划器请求/响应契约

P15b-2 于 2026-05-28 完成。

AgentHub 现在正式定义了 `llm_v1` 规划器 I/O：

- `PlannerRequest` 携带原始用户请求、CanonicalSharedContext 摘要、目标注册表摘要、项目分析器摘要、最近消息、制品引用、支持的 roles/modes/capabilities 和护栏；
- 提供者可见的请求负载在离开契约边界前会编辑掉类似密钥的值和受保护的绝对路径；
- `PlannerResponse` 定义了必需的 plan/task 字段，包括 `planId`、`planner`、`plannerMode`、理由、任务角色、目标 ID、意图类型、计划文件、依赖项、验收标准、风险级别和审批要求；
- `parse_llm_plan_output` 现在在现有任务图和 PlanValidator 检查之前，根据此契约验证规划器输出。

P15b-2 未添加真实提供者执行、从散文中提取 JSON、额外的 PlanValidator 强化、任务追踪证据扩展或真实的 Breakout 规划器演练。

### P15b-1 规划器提供者抽象

P15b-1 于 2026-05-28 完成。

AgentHub 现在拥有 `llm_v1` 的规划器提供者基础：

- `PlannerProvider` 接口，带有标准提供者结果元数据；
- 已禁用的规划器提供者，规划器来源为 `disabled`；
- fake/test 规划器提供者，规划器来源为 `fake_test`；
- 通过 `AGENTHUB_LLM_PLANNER_PROVIDER` 进行显式提供者选择；
- 针对未知提供者配置的归一化规划器提供者错误；
- LLM 规划器任务元数据记录提供者 ID、提供者类型、规划器来源、状态和安全的规划器提供者元数据；
- 确定性兜底计划记录所选的规划器提供者，而不仅仅是说 `llm_v1` 已被禁用。

默认规划器提供者仍然是 `disabled`，保留了 P15 的确定性兜底行为。P15b-1 未实现真实的 LLM 规划器提供者、超出现有解析器的结构化输出提取、PlanValidator 强化、任务追踪证据扩展或真实的 Breakout 规划器演练。

## P15 状态

### P15-7 冻结审查

P15-7 于 2026-05-28 完成。

P15 已准备好作为“真实编码助手升级”冻结。

冻结审查确认：

- P15 保留了 P6-P14 基线；
- 旧的确定性演示兜底仍然可用；
- ScriptedMock 仍然被明确标记为 fallback/review 证据，并未用于声称 Breakout 成功；
- 目标注册表、代理选择策略、调度器 locks/recovery、审查、预览和暂存部署路径仍然有效；
- Breakout 最终验收已通过 `passthrough_v1` 使用真实的 `ClaudeCodeAdapter` 执行完成。

详细的冻结说明记录在 `docs/p15-freeze-review.md` 中。
推荐标签：`p15-real-coding-assistant-upgrade-freeze`。

### P15-6 Breakout 游戏真实编码冒烟测试

P15-6 于 2026-05-28 完成。

AgentHub 通过真实的 Claude Code 前端运行验证了 P15 最终验收目标：

- 未提及 Breakout 的请求被路由到 Orchestrator；
- Orchestrator 创建了一个 `passthrough_v1` 前端任务，而不是硬编码的 Breakout 模板；
- 原始用户请求在计划和提供者指令中得以保留；
- TaskRun `8d719899-8042-49b0-8e26-79d065841a3c` 使用了 `adapterType=claude_code` 并已完成；
- diff 制品 `96b576ec-d673-49b7-a461-78e937f219b8` 包括 `apps/demo/src/App.tsx`、`apps/demo/src/styles.css` 和新的 `apps/demo/src/BreakoutGame.tsx`；
- 脚本化审查制品 `706265e5-91dc-4d90-a309-b0ca7c4700ad` 已通过；
- 目标作用域的构建证据制品
  `7dddb098-3e84-48c5-9855-4f2479a865f0` 记录 `pnpm build` 通过
  `demo-frontend`；
- 预览 `68d04a67-99d1-4fdb-8bfb-5ba584ae6f6c` 在
  `http://127.0.0.1:50086` 时健康；
- 本地暂存部署 `1747ed90-9999-4919-bfac-8b4cdfea13a4` 在
  `http://127.0.0.1:50424` 时就绪。

P15-6 新增：

- 针对有界实现请求的通用透传前端规划；
- Claude Code `Write` 工具权限，允许在分配的工作树内创建文件；
- 针对未跟踪文件的差异收集。

本次运行未自动化浏览器点击可玩性测试，因为工作区未安装浏览器自动化工具且未安装 Playwright。静态和预览证据显示生成的应用程序包含画布游戏玩法、键盘标记、得分、重启和 Breakout UI 代码。详细证据见 `docs/p15-breakout-smoke.md`。

### P15-5 规划器原理与任务审查元数据

P15-5 于 2026-05-28 完成。

AgentHub 任务响应现在包含从现有计划数据派生的只读 `planReviewMetadata`：

- 规划器模式；
- 原理；
- 分配的角色；
- 目标 ID；
- 依赖项；
- 计划文件；
- 验收标准；
- 验证预期；
- 任务图分解；
- 源任务 ID 和只读标记。

任务时间线将此元数据渲染为紧凑的计划审查摘要，使用户可以在执行前后检查任务存在的原因及其预期变更内容。

P15-5 不添加可编辑的计划审查、不改变调度器行为、不修改适配器分发、也不引入新的规划器模式。它仅通过 API/UI 表面暴露现有计划元数据。

### P15-4 项目命令策略

P15-4 于 2026-05-28 完成。

AgentHub 现在具有目标作用域的命令证据策略：

- 目标命令验证源自目标注册表元数据；
- 当提供了目标或可从任务计划推断出目标时，`check`、`test` 和 `build` 证据必须与所选目标配置的 `checkCommand`、`testCommand` 或 `buildCommand` 匹配；
- 命令证据制品现在在命令类型、命令字符串、退出码、stdout、stderr 和 pass/fail 状态之外，还保留 `targetId`；
- 命令证据事件现在还包括用于任务 trace/recovery 消费者的 `targetId`。

这支持配置的 pnpm/npm/pytest-style 项目命令，而无需开放任意主机命令执行。没有目标上下文的旧证据仍与现有的全局允许列表兼容。

P15-4 不自动执行命令、不添加任意命令代理、不启用生产部署、也不允许未配置的项目命令。

### P15-3 宽松目标护栏

P15-3 于 2026-05-28 完成。

AgentHub 现在根据所选目标注册表元数据评估写入安全性，而不是旧的狭窄仅演示路径列表。

当前行为：

- 注册目标 `allowedPaths` 可以允许在所选目标内进行有意义的代码更改，例如在 `apps/demo/src` 下新增前端文件；
- 目标 `deniedPaths` 和全局保护路径仍然阻止 `.git`、`.env`、密钥、`node_modules`、`.venv` 以及类似的不安全位置；
- 跨目标编辑、绝对路径、遍历路径和普通 AgentHub 平台后端编辑对于普通应用任务仍然被阻止；
- 安全演示 frontend/backend 任务的编排器自动启动现在在创建自动 TaskRun 之前检查所选目标元数据、允许的角色、安全目标和计划文件。

P15-3 不添加任意仓库范围的权限、生产部署、网络访问或平台代码写入权限。平台维护仍然需要现有的显式平台模式和审批路径。

### P15-2 透传指令模式

P15-2 于 2026-05-28 完成。

提供商指令生成现在在旧的确定性演示模板分支之前识别 `llm_v1` 和 `passthrough_v1` 计划。对于透传计划，AgentHub 保留：

- 原始用户请求；
- 任务描述；
- 目标 ID 和允许的路径；
- 验收标准；
- 验证预期；
- CanonicalSharedContext、artifact/handoff 上下文和现有护栏。

透传主体明确告知 Claude Code 或 Codex 不要将任务重写为旧的登录页面、按钮复制或演示槽模板，除非计划明确选择了确定性演示兜底。

P15-2 不扩展目标权限或命令执行策略。它仅更改已选择 `llm_v1` 或 `passthrough_v1` 的计划的提供商指令渲染。

### P15-1 LLM 规划器 v1

P15-1 于 2026-05-28 完成。

AgentHub 现在具有 `llm_v1` 规划器基础：

- `apps/api/app/llm_planner.py` 从原始用户请求、CanonicalSharedContext、目标注册表摘要、Project Analyzer 风格的目标元数据、最近消息、制品引用槽和护栏构建 LLM 规划器输入。
- LLM 规划器输出必须是结构化的 PlanDraft JSON，包含任务、角色、目标、依赖项、计划文件、原理、验收标准和验证预期。
- LLM 输出在任务持久化之前通过 PlanValidator 进行解析和验证。
- `PlanDraft` 元数据现在包含规划器模式、验收标准、
  验证期望、护栏说明和兜底原因字段。
- 现有的确定性规划器路径保持不变。由于默认未启用任何真实的 LLM
  规划提供者，编排器兜底任务会记录 `plannerFallback: { attemptedPlanner: "llm_v1", reason: "disabled" }`
  而不是声称 LLM 规划器成功。

P15-1 不实现透传提供者指令、扩展命令策略、Breakout 执行或真实的 Claude/Codex 规划器调用。这些保留在后续的 P15 任务中。

## P14 状态

### P14-7 演练与冻结审查

P14-7 于 2026-05-28 完成。

P14 已准备好作为自定义 Agent / 提供者 / 插件基础进行冻结。

演练已验证：

- 内置的编排器、前端、后端、QA、审查和兜底配置文件；
- 感知提供者的选择和分配元数据；
- 后端=Codex/frontend=Claude Code 确定性混合提供者证据；
- 拒绝无效的 target/capability/safety 分配；
- Agent 联系 UI provider/capability/target/status 元数据显示；
- 安全的自定义 AgentProfile 草稿创建和不安全的草稿拒绝；
- 通过完整验证套件的 P6-P13 基线覆盖。

详细证据和注意事项记录在 `docs/p14-freeze-review.md` 中。
推荐标签：`p14-custom-agent-provider-foundation-freeze`。

### P14-6 安全的自定义 Agent 草稿

P14-6 于 2026-05-28 完成。

AgentHub 现在拥有受控的安全自定义 AgentProfile 草稿基础：

- `AgentProfileDraft` SQLite 元数据表；
- `POST /workspaces/{workspace_id}/agent-profile-drafts`；
- `GET /workspaces/{workspace_id}/agent-profile-drafts`；
- 工作区 AgentProfile 注册表响应包含已创建的草稿配置文件。

草稿配置文件仅包含元数据。它们被强制设置为 `safeForWrite=false`，
只能使用 `draft_only` 或 `disabled` 状态，并且只能使用
`review`/`read_only`/`debug` 模式。草稿创建会拒绝写入能力、
未知提供者、adapter/provider 不匹配、任意 shell 命令、
不安全的工具权限、不受限制的文件系统访问和不安全的目标标识符。

P14-6 不添加市场行为、任意自定义 shell 命令 Agent、
自定义提供者安装、云令牌管理或草稿 Agent 的执行。

### P14-5 Agent 联系 UI 升级

P14-5 于 2026-05-28 完成。

工作区 Agent 联系 API 现在在与命令中心侧边栏使用的相同联系负载中公开提供者和目标元数据：

- `providerId`；
- `supportedTargets`；
- `supportedModes`。

Agent 联系 UI 现在渲染提供者徽章、支持的目标芯片、紧凑的能力芯片和更清晰的 unavailable/auth/draft/disabled 状态标签。直接聊天和组工作流仍然是本地视觉模式，开始、重试、兜底、审查、预览和部署行为保持不变。

P14-5 是信息性 UI 工作。它不添加提供者市场行为、自定义 Agent 创建、云令牌管理、适配器分发更改或多用户协作。

### P14-4 Agent 选择策略

P14-4 于 2026-05-28 完成。

TaskRun 创建现在在适配器执行之前应用 Agent 选择策略。该策略验证：

- 目标支持；
- 所需的执行模式；
- 所需的能力；
- `safeForWrite`；
- `safeForReview`。

成功的 TaskRun 将 `agentSelection` 元数据持久化到 `metricsJson` 中，使得所选角色、目标、所需模式、所需能力和安全标志可审计。

不支持的目标、不支持的模式、缺失的能力、不安全的写入或不安全的审查分配会在适配器执行之前诚实地失败。ScriptedMock 兜底通过现有的 retry/fallback 路径保持显式。

平台维护仍受现有平台模式和审批流程的保护；P14-4 仅使后端配置文件支持足够明确以进行验证。

### P14-3 能力与模式模式

P14-3 于 2026-05-28 完成。

AgentHub 现在拥有受控的 Agent 模式模式：

- `frontend`；
- `backend`；
- `qa`；
- `review`；
- `platform_maintenance`；
- `read_only`；
- `debug`。

AgentHub 现在拥有受控的能力标签模式：

- `code_write`；
- `code_review`；
- `test_run`；
- `diff_analysis`；
- `preview`；
- `deploy_staging`；
- `platform_change`。

内置的 AgentProfile 元数据和 ProviderConfig 支持的模式与受控模式对齐。不支持的能力标签或模式现在会失败验证，而不是成为临时的权限字符串。

P14-3 尚未强制执行完整的 Agent 选择策略或添加自定义 Agent 草稿创建。这些保留在后续的 P14 任务中。

### P14-2 提供者配置注册表

P14-2 于 2026-05-28 完成。

AgentHub 现在通过只读的 `/provider-configs` API 和 Web 客户端辅助函数 `listProviderConfigs` 公开非机密的提供者配置元数据。

当前提供者配置：

- `local-claude-code-cli` / `claude_code` / 认证状态 `unchecked`；
- `local-codex-cli` / `codex` / 认证状态 `unchecked`；
- `local-scripted-mock` / `scripted_mock` / 认证状态 `not_required`。

提供者配置响应包括提供者 ID、显示名称、适配器类型、
认证状态、可用性、默认角色及支持模式。它们不包含密钥、令牌、API密钥、原始凭证或云令牌管理。

P14-2 不实现提供商安装、市场行为、云凭证设置或适配器调度变更。

### P14-1 智能体配置文件注册表

P14-1 于 2026-05-28 完成。

AgentHub 现在暴露了一个注册表风格的 AgentProfile 合约。工作区 AgentProfile 响应包括：

- `id`；
- `displayName`；
- `avatarInitials`；
- `role`；
- `adapterType`；
- `providerId`；
- `capabilityTags`；
- `supportedRoles`；
- `supportedTargets`；
- `supportedModes`；
- `safeForWrite`；
- `safeForReview`；
- `description`；
- `status`。

该注册表保留了当前基于数据库的内置智能体，并添加了虚拟内置审查和兜底配置文件：

- 审查配置文件：`virtual-review-agent`，状态 `planned`，
  `safeForReview=true`；
- 兜底配置文件：`virtual-fallback-agent`，状态 `available`，
  基于 ScriptedMock 的兜底元数据。

P14-1 不添加提供商配置、能力执行、安全自定义智能体草稿创建、市场行为或适配器调度变更。这些留待后续 P14 任务处理。

## P13 状态

### P13-8 混合提供商预演与冻结审查

P13-8 于 2026-05-27 完成。

P13 已准备好冻结为“跨提供商智能体协调”。

冻结预演使用确定性本地执行，而非实时的 Claude Code 或 Codex 变更，因此不声称真实的提供商成功。预演验证了一个有界的混合提供商图：
```text
shared mini CRM contract
-> backend task assigned to Codex
-> backend diff/review
-> provider-aware handoff
-> frontend task assigned to Claude Code
-> frontend diff/review
-> healthy preview
-> local staging deploy
-> mission trace evidence
```
证据记录在 `docs/p13-freeze-review.md` 中，并由 `apps/api/tests/test_cross_provider_rehearsal.py` 涵盖。

P13 不增加提供商市场支持、OpenCode、用户创建的自定义代理、多用户 IM、生产部署、分布式工作器或调度器替换。

### P13-7 混合提供商调度器集成

P13-7 于 2026-05-27 完成。

调度器状态现在在终端运行上保留提供商协调元数据：

- `adapterType`；
- `providerId`；
- `providerAssignment`；
- `retryOfRunId`（若存在）；
- `fallbackFromRunId`（若存在）。

回归覆盖验证混合提供商任务图继续遵守 P8-P10 调度器规则：

- 前端 Claude Code 任务等待后端 Codex 依赖；
- 相同目标的写锁定无论提供商身份如何均适用；
- 不同的 frontend/backend 目标可以在没有依赖或冲突阻塞时，与不同提供商排队；
- 失败的混合提供商运行仍可重试，并在调度器元数据中保留提供商分配证据。

P13-7 不运行真实的 Claude/Codex、添加提供商市场、更改适配器分发语义或替换调度器。混合提供商预演和冻结审查仍属于 P13-8。

### P13-6 跨提供商证据标准化

P13-6 于 2026-05-27 完成。

基于 TaskRun 的制品现在携带标准化的提供商证据，用于跨提供商协调。差异、脚本化审查、预览和部署制品 metadata/events 包括：

- 任务运行 ID 和运行状态；
- 适配器类型和提供商 ID；
- 提供商分配元数据（若可用）；
- 相关更改文件和日志；
- 制品引用，如差异、预览、审查和部署 ID；
- retry/fallback 引用（若存在）。

脚本化审查制品还存储 `originProviderEvidence`，因此确定性审查不会隐藏生成被审查差异的编码运行的提供商身份。

P13-6 不更改调度器行为、运行真实的 Claude/Codex、实现提供商市场或添加用户创建的自定义代理。混合提供商调度器集成和预演仍属于后续 P13 任务。

### P13-5 提供商特定指令映射

P13-5 于 2026-05-27 完成。

Codex 和 Claude Code 指令适配器现在添加提供商特定的包装文本，同时保留相同的共享角色指令和规范共享上下文。Codex 包装强调面向补丁的执行；Claude Code 包装要求在编辑前提供简洁的实现计划。

回归覆盖验证两个提供商指令保留相同的关键事实：

- 共享应用合约 ID；
- frontend/backend 目标 ID；
- 上游交接 artifact/provider 引用；
- 已实现路由详情；
- 验证期望；
- 护栏。

P13-5 不标准化执行证据、更改调度器行为或运行真实的 Claude/Codex 预演。这些仍属于后续 P13 任务。

### P13-4 交接协议 v1

P13-4 于 2026-05-27 完成。

交接制品现在包含提供商感知的元数据，用于跨提供商任务转换：

- `fromProviderId` 和 `fromAdapterType`；
- `toProviderId` 和 `toAdapterType`；
- `fromTaskRunId` 和任务角色元数据；
- 更改文件，优先使用最新差异制品元数据；
- 已实现路由和组件提示；
- 制品引用；
- 审查警告和建议的后续范围；
- 验证状态和风险说明。

前端到审查以及审查到修复的交接现在保留足够的提供商身份，用于下游上下文、任务追踪和后续的混合提供商预演。下游规范共享上下文通过现有的 `handoffNotes` 字段包含丰富的交接说明。

P13-4 不实现提供商特定指令语义比较、所有制品类型的证据标准化、调度器混合提供商集成或真实的 Claude/Codex 预演。这些仍属于后续 P13 任务。

### P13-3 规范上下文使用强制

P13-3 于 2026-05-27 完成。

基于提供商的 TaskRun 指令现在渲染一个 `Canonical Shared Context` 部分，该部分源自过滤后的 `canonical_shared_context_v1` 合约。指令不再包含作为 `legacyContext` 的遗留会话上下文负载。

规范上下文包括提供商可见的安全表示：

- 会话和用户目标；
- 当前任务；
- 任务图（若可用）；
- 目标上下文和相关目标；
- 安全路径；
- 最近消息；
- 相关制品；
- 最新 diff/review/preview/deployment；
- 交接说明；
- 护栏和验证期望。

TaskRun `metricsJson.canonicalContextSnapshot` 仍然是为提供商执行准备的上下文的可审计快照。

P13-3 还防止原始计划 `files` 被直接复制到前端指令中。首选文件列表源自规范安全路径，因此受保护的计划值（如依赖目录路径、绝对主机路径或包含秘密的元数据）不会通过指令文本泄露。

P13-3 不实现交接协议 v1 更改、提供商特定语义映射测试、证据标准化、混合提供商调度器集成或真实的 Claude/Codex 预演。这些仍属于后续 P13 任务。
集成，或真正的 Claude/Codex 演练。这些仍是后续 P13 阶段的任务。

### P13-2 提供商感知的 Agent 配置文件

P13-2 于 2026-05-26 完成。

AgentProfile 响应现在为内置 agent 暴露了提供商感知的角色能力元数据。API 响应包含：

- `providerId`；
- `adapterType`；
- `supportedRoles`；
- `supportedTargets`；
- `supportedModes`；
- `safeForWrite`；
- `safeForReview`。

内置配置文件默认值现在将角色映射到具体的提供商身份：

- frontend/backend 编码 agent 默认使用 `local-codex-cli`；
- QA/review 默认使用 `local-scripted-review`；
- 编排器默认使用 `local-scripted-mock`。

如果 `AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX.roles` 配置了某个角色，对应的 AgentProfile 将反映已配置的 adapter/provider 对。这使可见的 agent 元数据与 P13-1 TaskRun 提供商分配保持一致，且不改变适配器分发语义。

P13-2 不包含提供商市场、OpenCode、用户创建的自定义 agent UI、规范上下文强制、交接协议变更或真正的混合提供商执行。

### P13-1 提供商分配矩阵

P13-1 于 2026-05-26 完成。

AgentHub 现在拥有一个明确的提供商分配基础，用于跨提供商协调。`apps/api/app/provider_assignments.py` 定义了分配解析器和内置角色默认元数据。运行时分配可通过 `AGENTHUB_PROVIDER_ASSIGNMENT_MATRIX` 提供：
```json
{
  "roles": {
    "backend": {"adapterType": "codex", "providerId": "local-codex-cli"},
    "frontend": {
      "adapterType": "claude_code",
      "providerId": "local-claude-code-cli"
    },
    "review": {
      "adapterType": "scripted_mock",
      "providerId": "local-scripted-review"
    }
  },
  "targets": {
    "demo-frontend": {
      "frontend": {
        "adapterType": "claude_code",
        "providerId": "local-claude-code-cli"
      }
    }
  }
}
```
解析顺序：

1. TaskRun 请求上的显式适配器覆盖；
2. `targetId + role` 的特定目标矩阵分配；
3. 角色级矩阵分配；
4. 从 Agent 元数据和 `AGENTHUB_DEFAULT_CODE_ADAPTER` 中选取的旧版适配器。

TaskRun `metricsJson` 现在记录 `providerAssignment`，包含角色、适配器类型、提供商 ID、来源、目标 ID、支持的模式和兜底策略。任务追踪 TaskRun 条目暴露相同的元数据，因此在此基础任务期间无需运行真实的 Claude Code 或 Codex 即可看到提供商选择。

无效的分配适配器类型会在 TaskRun 创建之前诚实失败。P13-1 不添加提供商市场支持、OpenCode、用户创建的自定义 Agent UI、规范上下文强制执行、交接协议变更或真实的混合提供商执行演练。这些将保留到后续的 P13 任务中。

## P12 状态

### P12-10 端到端演练与冻结审查

P12-10 于 2026-05-26 完成。

结果：P12 已准备好作为平台核心整合阶段冻结。

冻结演练使用了全新的 SQLite 数据库 `sqlite:///data/p12-freeze-rehearsal-3.sqlite3` 和新的会话工作树。它验证了整合后的本地演示路径：
```text
new session -> @orchestrator login-page request -> plan/task graph
-> ScriptedMock frontend run -> diff -> review -> handoff -> preview
-> local staging deploy -> follow-up button text change -> artifact version v2
-> updated preview -> updated local staging deploy
```
证据：

- 会话 ID: `3745b760-ff59-449a-a06b-b00a4cf2e4a2`；
- 首次前端运行 ID: `89dd57d7-c003-4a5e-b9fa-a4ca6ed0e326`；
- 首次差异制品 ID: `b3272f5c-109d-423e-9c06-867dc06a6a7a`；
- 首次审查制品 ID: `255ad376-128f-4c55-8328-4a5bfe6f6f4b`；
- 交接制品 ID: `5327d10d-3dcc-4422-ab90-802fbe15807d`；
- 首次预览 ID/status: `9e578e93-ced3-41ed-a8c2-5f6752f4b455`，
  `healthy`；
- 首次本地暂存部署 ID/status：
  `bf87222a-ce40-4de5-85d7-a5f7964c5640`, `ready`；
- 后续运行 ID: `c5d852b8-1347-48ad-91f2-4c8e92f94800`；
- 后续差异制品 ID: `4f1ba32b-ba9e-40bb-b1c3-6aa258b8dcd0`；
- 后续审查制品 ID: `bea796fe-71c7-4643-a857-42c09694d521`；
- 制品版本 v2 ID: `5f1e1516-33a3-4951-bde4-c68da759e1f6`；
- 后续预览 ID/status: `049ca7aa-c7e0-46a9-ba06-ffc81d77b347`，
  `healthy`；
- 后续本地暂存部署 ID/status：
  `b7e52a37-09a6-4246-9f87-b406f02a251a`, `ready`。

在 P12-10 期间未运行新的 Claude Code 或 Codex 变更。演练使用 ScriptedMockAdapter 获取确定性本地证据，并通过完整验证保留了 P6-P11 基线。

当前注意事项：

- 如果默认本地 SQLite 数据库早于 P11 外部目标部署列，可能需要 reset/migration；
- 工作区设置中 `node_modules` 的符号链接应在本地忽略，以免触发脏工作区冲突检测；
- 本地暂存 URL 在创建时正常，但在一次性演练进程退出后未保持长期存活；
- 交接证据是在 diff/review/deploy 制品存在后通过 P12 交接服务显式生成的，因此制品引用可用。

完整证据和验证结果请参见 `docs/p12-freeze-review.md`。

推荐的冻结标签：
`p12-platform-core-consolidation-freeze`。

## P11 状态

### P11-6 端到端演练与冻结审查

P11-6 于 2026-05-25 完成。

结果：P11 已准备好作为真实暂存部署提供者冻结。

冻结演练使用了内置的 `demo-frontend` 目标和真实的本地暂存部署路径。该提供者在 `apps/demo` 中运行了 `pnpm build`，在本地 URL 上提供 `apps/demo/dist`，验证该 URL 返回了构建后的 HTML，并记录了 deployment/source/log/status 元数据。

证据：

- 提供者：`local_staging`；
- 环境：`staging`；
- 部署状态：`ready`；
- 部署 ID：`8c776325-e98a-435c-ab1c-6a2d71c6946f`；
- 制品 ID：`949c9411-98c6-4e0c-978f-96bc7ac88f0c`；
- 目标 ID：`demo-frontend`；
- 记录了源 preview/diff/review 制品引用；
- 状态历史：`queued -> building -> deploying -> ready`。

P11-6 还修复了一个真实的演练阻塞问题：静态服务器现在使用 `sys.executable`，而不是假设主机上存在 `python` 命令。

完整证据表、注意事项和推荐标签请参见 `docs/p11-freeze-review.md`。

推荐的冻结标签：
`p11-real-staging-deploy-provider-freeze`。

### P11-5 部署门禁

P11-5 于 2026-05-25 完成。

暂存部署请求现在在 `local_staging` 提供者执行之前通过保守的部署门禁。P11 拒绝 production/prod 部署请求，要求健康的预览，在最新相关审查失败时阻止部署，并阻止违反目标注册表 allowed/denied 路径策略的已更改文件。模拟部署仍可用于传统的 demo/fallback 路径。

当前限制：P11-5 是服务级别的部署门禁。它不添加多用户审批工作流、云部署审批、回滚或生产部署。P11-6 仍负责真实暂存演练和冻结审查。

### P11-4 部署日志与状态制品

P11-4 于 2026-05-25 完成。

部署制品现在更直接地暴露提供者证据。部署元数据记录提供者类型、目标 ID、源 preview/diff/review 引用、提供者日志和状态历史。部署 API 响应包含这些字段，因此 UI 客户端无需解析原始制品元数据。

现有的部署卡片现在渲染 target/source 引用、状态历史和日志，同时保留模拟部署行为。本地暂存失败（如构建失败、输出目录缺失或健康检查失败）会作为带有日志的失败部署制品持久化，而不会静默丢失。

当前限制：P11-4 将状态历史记录为提供者生成的元数据和部署事件。它尚未强制执行 review/preview/policy 部署门禁；这仍是 P11-5 的任务。

### P11-3 本地暂存部署提供者

P11-3 于 2026-05-25 完成。

AgentHub 现在包含一个 `local_staging` 部署提供者，与现有的模拟提供者并存。本地暂存提供者从目标注册表解析目标部署配置，在目标根目录中运行配置的构建命令，验证配置的输出目录，启动本地静态文件服务器，对生成的 URL 进行健康检查，并在提供者成功时持久化一个就绪的暂存部署制品。

部署 API 保持向后兼容：`POST /previews/{previewId}/deploy` 默认为 `providerId: mock`，而调用者可以请求 `providerId: local_staging`。失败的构建、缺失的输出目录和失败的
健康检查状态被如实报告，且不会创建就绪部署。

当前限制：P11-3 将提供者日志存储在制品元数据和就绪事件中，但尚未持久化完整的部署状态转换历史或 UI 日志展开。这是 P11-4 的内容。超出 preview/task 先决条件的部署门控仍属于 P11-5。

### P11-2 目标感知的部署配置

P11-2 于 2026-05-25 完成。

目标注册表现在为可部署的前端目标公开了预发布部署元数据。内置的 `demo-frontend` 目标包含构建命令、预发布输出目录、预发布服务命令模板以及允许的部署提供者 ID。外部项目注册和工作区目标响应也可以携带 `stagingOutputDir`、`stagingServeCommand` 和 `deployProviderIds`。

`resolve_deploy_config()` 集中了部署配置查找功能，并在目标不是可部署的前端目标或缺少所需的 build/output/provider 元数据时如实失败。`demo-backend` 和 `agenthub-platform` 通过此预发布配置路径仍保持不可部署状态。

当前限制：P11-2 仅提供目标感知的部署配置。它尚未运行构建、提供静态输出、记录展开的部署日志或执行部署门控。

### P11-1 部署提供者抽象

P11-1 于 2026-05-25 完成。

AgentHub 现在为现有部署路径提供了一个精简的部署提供者抽象。`DeployService.create_deployment()` 按 ID 选择提供者，如实拒绝未知提供者，在不创建成功部署制品的情况下拒绝失败的提供者结果，并保留 `create_mock_deployment()` 作为围绕提供者兼容模拟路径的向后兼容包装器。

模拟提供者仍然生成现有的模拟部署 URL 和制品形状，而部署制品元数据现在包含一个标准的 `providerResult` 负载，其中包含提供者 ID、提供者类型、目标 ID、构建命令、部署命令、输出 URL、状态、日志和环境。

当前限制：P11-1 仅引入了提供者抽象和模拟兼容性。目标感知的预发布配置、本地静态服务、部署日志 UI/status 展开、部署门控以及真实的预发布演练仍属于后续的 P11 任务。

## P10 状态

### P10-8 健壮性演练与冻结审查

P10-8 于 2026-05-24 完成。

结果：P10 已准备好作为“调度器健壮性与冲突恢复”进行冻结。

冻结审查使用了确定性的本地测试，并未运行新的真实 Claude/Codex 变更。涵盖的演练场景包括：

- TaskRun 心跳和租约；
- 过期的 TaskRun 检测；
- 活动锁保护；
- 过期的目标锁清理；
- 运行前检查点；
- 重试幂等性和不安全重试阻止；
- 失败的依赖项传播；
- preview/mock 部署先决条件门控；
- 文件重叠、脏工作树和契约漂移冲突；
- 可审计的恢复操作。

参见 `docs/p10-freeze-review.md` 获取证据表、注意事项和验证记录。

推荐的冻结标签：
`p10-scheduler-robustness-conflict-recovery-freeze`。

### P10-7 恢复操作

P10-7 于 2026-05-24 完成。

AgentHub 现在拥有一个专注于调度器健壮性场景的恢复服务：

- 将过期的 TaskRun 标记为失败，并附带恢复审计事件；
- 释放过期的目标锁并重新评估等待中的任务；
- 从当前状态重试，并附带重试元数据和审计事件；
- 在通过重试所使用的相同安全检查后，从检查点重试；
- 通过显式的阻塞调度器状态停止下游流水线推进；
- 通过重新评估依赖项和调度器就绪状态来恢复下游推进。

每个恢复操作都会写入一个 `recovery.action` `TaskRunEvent`，其中包含执行者、原因、操作和受影响的 ID。过期的锁释放还会保留来自 P10-2 的 `target_lock.released` 审计事件。

当前限制：P10-7 为 API/test 演练公开了服务级别的恢复操作。它没有添加新的 UI 按钮或自动的 Git reset/merge 行为。

### P10-6 冲突检测

P10-6 于 2026-05-24 完成。

调度器就绪状态现在在启动写入型 TaskRun 之前执行保守的冲突检测：

- 具有重叠计划文件的非顺序写入任务被阻止，标记为 `file_overlap`；
- 外部或注册目标中，脏工作树包含计划安全文件之外的脏文件，被阻止，标记为 `dirty_worktree`；
- 其 `contractId` 或 `contractHash` 不再匹配嵌入的 `appContract` 的任务被阻止，标记为 `contract_drift`；
- 冲突详情被写入任务调度器元数据，包括冲突类型、冲突任务以及可用的冲突文件。

P10-6 不会自动合并冲突。它会在不安全执行之前停止，并将恢复决策留给明确的 P10-7 操作。

当前限制：文件重叠检测有意限定在非顺序写入任务范围内，以便现有的依赖顺序 P8/P9 流水线能继续工作。

### P10-5 失败传播强化

P10-5 于 2026-05-24 完成。

预览和模拟部署创建现在受成功先决条件的门控：

- 预览要求源 TaskRun 已完成；
- 预览拒绝失败、中断、过期、超时或仍在运行的 TaskRun；
- 预览拒绝依赖缺失或未完成的任务；
- 模拟部署需要基于已完成 TaskRun 的健康预览；
- 模拟部署拒绝失败或不完整的上游依赖。

现有的调度器依赖阻塞、retry/fallback 下游重新评估，以及兜底 diff -> 预览 -> 模拟部署路径保持不变。

当前限制：P10-5 强化了下游门控，但尚未执行文件重叠、脏工作树或合约漂移冲突检测。这些内容保留至 P10-6。

### P10-4 重试幂等性

P10-4 于 2026-05-24 完成。

重试 TaskRun 现在携带幂等性元数据：

- `previousRunId` 将重试链接到先前的 failed/interrupted 运行；
- `failureSummary` 记录先前状态、错误 code/message 和结束时间；
- `retryMode` 记录重试是来自当前状态还是脚本化兜底；
- `checkpointId` 在存在预运行检查点时指向先前的 TaskRun；
- `dirtyWorktreeDecision` 记录当前目标状态是否安全。

自动重试会将当前 git 脏文件与先前检查点的脏文件和计划文件进行比较。如果脏文件存在于 checkpoint/planned 安全路径之外，重试将被阻止，并显示明确的非安全重试错误，且不会创建新的 TaskRun。

当前限制：P10-4 阻止了非安全重试，但尚未提供独立的恢复决策 API。从检查点重试和显式恢复操作保留至 P10-7。

### P10-3 预运行快照/检查点

P10-3 于 2026-05-24 完成。

写入 TaskRun 现在在 `metrics_json.preRunCheckpoint` 中记录预运行检查点，并发出 `task.checkpoint.created` 事件。检查点记录：

- 目标 ID 和目标根目录；
- 目标注册表允许和拒绝的路径；
- 可用时的基础提交；
- git 状态可用性和限定的脏文件；
- 任务计划中的计划文件；
- 应用合约 ID 和存在时的确定性合约哈希；
- 检查点创建时间戳。

外部目标检查点使用已注册的外部目标根目录和路径策略。检查点元数据仅记录文件路径和 git 状态；不存储文件内容或拒绝路径的内容。

当前限制：P10-3 仅记录检查点元数据。重试幂等性、脏工作树重试阻止、冲突检测和恢复操作将在 P10-4 至 P10-7 中使用此元数据。

### P10-2 过期目标锁清理

P10-2 于 2026-05-24 完成。

目标写入锁仍源自活跃的 TaskRun，但清理现在具有所有者感知和可审计性：

- 具有有效心跳租约的活跃写入锁所有者不会被释放；
- 过期的写入锁所有者可以通过清理路径标记为过期；
- 过期所有者清理会写入 `target_lock.released` 审计事件，标识目标 ID、所属 TaskRun、任务、会话、锁模式、租约到期时间、释放时间戳和释放原因；
- 等待同一目标写入的任务在过期所有者清理后重新评估。

当前限制：P10-2 仍使用派生锁所有权，而非专用锁表。预运行检查点、重试幂等性、冲突检测和恢复操作 API 保留至 P10-3 至 P10-7。

### P10-1 TaskRun 心跳和租约

P10-1 于 2026-05-24 完成。

TaskRun 执行现在记录本地运行器存活元数据：

- `runner_id` 标识 TaskRun 的本地运行器所有者；
- `last_heartbeat_at` 记录最近一次活跃运行的心跳；
- `lease_expires_at` 记录当前心跳租约到期时间；
- `stale_detected_at` 和 `stale_reason` 记录诚实的过期检测。

新的 TaskRun 在创建时会收到心跳和租约元数据。活跃的 TaskRun 可以通过 TaskRun 生命周期服务刷新其心跳，过期的活跃租约可以通过 `TASK_RUN_STALE` 标记为失败，而无需声明适配器成功。过期状态转换会写入 `task.state` 和 `task.stale` 审计事件，并刷新下游调度器状态。

当前限制：P10-1 引入了存活元数据和过期标记，但尚未清理过期目标锁、创建检查点、强化重试幂等性、检测冲突或暴露恢复操作。这些内容保留至 P10-2 至 P10-7。

## P9 状态

### P9-8 外部项目端到端演练和冻结审查

P9-8 于 2026-05-24 完成。

结果：P9 已准备好冻结为外部项目工作区模式。

冻结演练使用了临时本地 Vite 风格的外部项目和受控的本地服务调用，而非全新的真实 Claude/Codex 变更。

P9 演练证据：

- 示例根目录：`/tmp/agenthub-p9-external-sample`；
- 工作区 ID：`deecb61e-8255-4f97-af36-668f8fefc66d`；
- 会话 ID：`09977dc0-1eac-49f6-ae78-cb7ae7aa9ccc`；
- 目标 ID：`external-p9-sample`；
- 分析状态/类型：`ready`、`vite-react`；
- 任务/运行：
  `ce8fe3de-6969-4273-84e9-274ab440f39b`、
  `1d6d2916-b179-4bb7-ad7a-642733dfd175`；
- 变更文件：`src/App.tsx`；
- diff 制品：`7bf6efa3-289b-4cb8-9644-6ca6e283b230`；
- 命令证据：
  `c6d581bf-e80a-4fb9-bb21-f0db1cb9ff4d`、
  `b01ccc78-b3d4-44fc-b758-4c9558d2f594`、
  `9a256f14-fe1f-4e4b-9dc7-78c4402edd01`；
- 审查 artifact/status/risk：
  `383e7822-0145-4950-9bd1-b3dffb170b36`、`passed`、`low`。

完整证据记录和注意事项见 `docs/p9-freeze-review.md`。

建议冻结标签：
`p9-external-project-workspace-mode-freeze`。

### P9-7 外部项目审查

P9-7 于 2026-05-24 完成。

脚本化审查现在检查已注册的外部目标策略和命令证据：

- 外部差异根据目标允许路径和拒绝路径进行审查；
- 拒绝路径编辑（如 `.env`）审查失败，风险等级为高；
- 在已注册允许路径之外的编辑会产生警告发现；
- 配置的 check/test/build 命令应包含命令证据；
- 命令证据失败会如实报告，并根据情况将审查状态保持在警告或失败；
- 通过配置证据的干净外部差异可通过审查。

当前限制：P9-7 是确定性的脚本化审查策略。它不运行真正的 Claude/Codex 审查；该审查仍是 P9-8 的可选证据。

### P9-6 外部证据管道

P9-6 于 2026-05-24 完成。

外部项目 TaskRun 现在拥有基于能力的证据路径：

- 外部 git 差异在收集变更文件和补丁文本时使用目标注册表的允许路径和拒绝路径；
- 命令证据制品可以记录配置的检查、测试和构建命令输出；
- 命令证据保留退出码，并将失败命令记录为 `failed`，而非将其转换为成功；
- 命令证据通过 TaskRun 事件和 list/read API 支持作为 `command_evidence` 制品发出；
- 会话上下文包包含最新的命令证据元数据，供后续审查和指令使用；
- 没有预览命令的目标仍可携带差异和命令证据。

当前限制：P9-6 记录由受控的 pipeline/API 提供的命令证据；它尚不执行任意外部命令。命令证据的审查策略为 P9-7。

### P9-5 外部项目任务执行

P9-5 于 2026-05-24 完成。

已注册的外部目标现在可以通过现有的路由和 TaskRun 路径接收可执行任务：

- 会话可以选择活跃的外部 frontend/backend 目标 ID；
- 目标选择验证该目标存在于工作区注册表中，且匹配请求的 frontend/backend 类型；
- 直接的 `@frontend` 和 `@backend` 分配在存在时路由到选定的外部目标；
- 当外部目标活跃时，直接的 `@qa` / `@review` 分配变为面向读取的外部审查任务；
- 当选定活跃的外部前端目标且请求为安全的 UI 变更时，编排器可以创建并自动启动一个受限的外部前端任务；
- 外部 TaskRun 使用外部目标根目录作为其执行工作树路径，而非内置的会话演示工作树；
- SQLite 初始化现在为现有的本地演示数据库回填会话活跃目标列。

当前限制：外部 diff/command 证据仍为基础级别，能力特定的证据制品为 P9-6。真正的 Claude/Codex 外部执行保留给 P9-8 演练。

### P9-4 外部目标指令构建器

P9-4 于 2026-05-24 完成。

角色指令现在使用已注册的外部目标元数据，而非假设内置演示路径：

- 外部前端指令包括目标根目录、允许路径、拒绝路径、项目类型、检测到的框架、包管理器以及配置的 validation/evidence 命令；
- 外部后端指令使用外部后端元数据，并明确保留 `apps/api` AgentHub 平台边界；
- 外部 QA/review 指令面向读取，要求诚实处理差异和 check/test/build 证据；
- 内置演示 frontend/backend/review 指令仍与 P4/P5/P6/P7/P8 路径兼容。

当前限制：指令已感知外部目标，但针对选定外部目标的路由和 TaskRun 执行仍为 P9-5。

### P9-3 外部目标注册表集成

P9-3 于 2026-05-24 完成。

外部项目目标现在被适配为与内置目标相同的目标注册表形态：

- 感知工作区的注册表读取合并了 `demo-frontend`、`demo-backend`、`agenthub-platform` 和持久化的外部目标；
- 外部注册映射到 `TargetProject` 元数据，包括根目录、允许路径、拒绝路径、命令、包管理器、检测到的框架、项目类型和分析状态；
- 后端 API 通过 `/workspaces/{workspace_id}/targets` 暴露合并后的工作区目标；
- 会话上下文包可以解析外部 `targetId` 值，并将目标元数据传递给代理指令；
- 指令构建可以渲染外部目标元数据，而无需回退到演示目标 ID；
- P8 目标写入锁现在识别已注册的外部目标，因此同一会话中同一外部目标的写入任务被序列化。

当前限制：编排器尚未为用户请求选择外部目标，适配器也尚未在外部根目录内执行。这些仍为 P9-4 和 P9-5。

### P9-2 项目分析器

P9-2 于 2026-05-24 完成。
AgentHub 现在有一个针对本地已注册工作区候选项目的只读外部项目分析器：

- 无需安装依赖或运行命令，即可从项目文件中检测具有代表性的 Vite React、Next.js、FastAPI、Node API 和 Python 包项目；
- 从锁文件和项目标记推断包管理器；
- 从现有目录推断安全的 source/test 允许路径；
- 从包脚本或 Python/FastAPI 约定推断候选的开发、测试、检查、构建和预览命令；
- 始终返回注册使用的外部拒绝路径基线；
- 将未知或不完整的项目标记为 `needs_confirmation` 并附带警告；
- 暴露工作区范围的分析 API，用于未来的注册和选择流程。

当前限制：分析器输出尚未合并到目标注册表或执行路径中。P9-3 及后续任务将使用 analyzer/registration 元数据进行规划、指令、锁、证据和审查。

### P9-1 外部工作区注册

P9-1 于 2026-05-24 完成，作为 `agenthub-p9-external-project-workspace-mode` 的第一个实现步骤。

AgentHub 现在拥有针对外部本地项目目标的持久化注册边界：

- 外部目标按工作区存储，包含目标 ID、名称、解析后的根路径、项目类型、允许路径、拒绝路径、命令、包管理器、检测到的框架和分析状态；
- 注册需要显式限定的允许路径，并拒绝整个根目录、父目录遍历、绝对允许路径、缺失根目录、文件系统根目录、主目录和常见系统目录；
- 默认拒绝路径包括 `.env`、`.env.*`、`secrets`、`.git`、`node_modules`、`.venv`、依赖目录、缓存目录和构建输出目录；
- 后端 API 可以在工作区下创建、列出和读取已注册的外部目标；
- 内置的 `demo-frontend`、`demo-backend` 和 `agenthub-platform` 注册表目标保持不变。

当前限制：P9-1 仅注册外部目标。规划器、指令构建器、调度器、适配器执行、证据和审查集成仍为 P9-3 至 P9-7。

## P8 状态

### P8-6 P8 端到端演练与冻结审查

P8-6 于 2026-05-24 完成。

结果：P8 已准备好作为本地单用户 AgentHub 工作区的依赖感知调度器和目标锁进行冻结。

冻结演练使用了临时 git 工作树和受控的本地伪造适配器，而非全新的真实 Claude/Codex 变更。P6 仍然是最新的真实 `ClaudeCodeAdapter` 迷你 CRM 执行证据。

P8 演练证据：

- 会话 ID：`3fad4108-f0ea-4134-8b31-fb2ab911fadd`；
- 合约 ID：`contract-mini_crm_contacts`；
- 后端任务/运行：
  `e7f85f87-fa8a-4203-a33f-682e568a6d50`，
  `72cf0f92-1c65-460e-b697-4e37cbcefed0`；
- 前端任务/运行：
  `e37a46b0-834b-4396-b703-8ecdfd1bf27b`，
  `bb28106d-d1f8-4431-8245-d40db304edfa`；
- 审查任务：`336a0c82-6caf-4d84-b421-4ccfcdd17ad7`；
- 差异制品：
  `104f1a7b-fa6f-4842-9152-a8e2acc0bbce`，
  `e92f2e27-c463-4a41-8dad-c7fce2eb87ce`；
- 预览：`56d01fc3-affb-4f6a-bf46-973469a81e1d`，`healthy`；
- 模拟部署：`d94dade3-8b3e-4ea0-a0a9-61b2b085ce9e`，提供者 `mock`；
- 目标锁证据：等待任务
  `7e507b15-3cd6-4be3-89d1-893e3777045a`，持有者运行
  `3c241653-2a4e-4782-b58c-729cdc98d1bf`；
- 失败依赖证据：失败任务
  `39d5151f-888a-4790-bd66-9044f6328053`，阻塞的下游任务
  `84e11005-0148-4926-993c-6c002555507b`；
- 平台保护证据：平台任务/运行
  `4ed028eb-998c-4ca4-8aa0-e0c2dd9dd2f8`，
  `ca3f70d9-d4aa-49ed-9e47-c757c432bde5`，状态 `waiting_approval`。

参见 `docs/p8-freeze-review.md` 获取完整证据记录和注意事项。

推荐的冻结标签：
`p8-dependency-scheduler-target-locks-freeze`。

### P8-5 调度器 UI 跟踪

P8-5 于 2026-05-24 完成。

工作区 UI 现在在现有任务时间线和执行跟踪中展示来自 `planJson.scheduler` 的调度器状态：

- 任务状态标签包括 `waiting_dependency`、`waiting_target_lock`、`blocked`、`retryable` 和 `fallback_available`；
- 每个任务卡片可以显示调度器原因、目标 ID、阻塞依赖 ID、锁持有者 TaskRun ID、写锁指示器、可重试状态和兜底可用性；
- 执行跟踪头部突出显示依赖等待、目标锁等待和阻塞状态；
- 现有的制品芯片、制品消息卡片、右侧制品面板、开始、重试、兜底、审查、预览和部署操作仍然可用。

当前限制：P8-5 仅为 UI 可见性传递。它不会在 P8-1 至 P8-4 之外添加新的调度器后端语义。

### P8-4 故障恢复与阻塞状态

P8-4 于 2026-05-24 完成。

调度器可见的故障恢复状态现在记录在任务 `planJson.scheduler` 中：

- 已完成的 TaskRun 记录 `state: completed`；
- 失败或中断的编码 TaskRun 记录 `retryable: true`；
- failed/interrupted Codex 编码运行记录 `state: fallback_available` 和 `fallbackAvailable: true`；
- 失败的非 Codex 或非兜底任务记录 `state: retryable`；
- 下游依赖在上游失败时仍会移至 `blocked`；
- 完成的 retry/fallback 次运行会重新评估下游任务，并在依赖关系和目标锁满足条件时解除其阻塞；
- 在会话级锁刷新期间，终端任务调度器元数据得以保留。

当前限制：P8-4 在后端负载中暴露了 retry/fallback 状态，但尚未添加专门的 UI 处理。这仍属于 P8-5 的范围。

### P8-3 自动运行流水线

P8-3 于 2026-05-24 完成。

契约优先的全栈计划现在可以参与自动流水线推进：

- 迷你 CRM / 待办事项 / 笔记的契约优先后端和前端任务包含 `autoStart: true`；
- 一旦合成契约任务完成，初始后端任务将通过现有的 TaskRun 路径自动启动；
- 当编码 TaskRun 完成时，AgentHub 收集差异，创建脚本化审查制品，刷新账本状态，并启动下一个可运行的契约优先编码任务；
- 就绪的契约审查/QA 任务根据生成的审查制品标记为完成，而不是运行一个可变的 QA 适配器；
- 完成的契约优先前端运行会尝试现有的 Vite 预览路径，并且仅在预览健康且演示应用根目录存在时创建模拟部署。

当前限制：P8-3 仍使用现有的本地适配器执行路径；如果 Claude/Codex 失败，下游流水线步骤仍受 P8-1/P8-2 依赖和锁状态的约束。丰富的 retry/fallback 调度器状态仍属于 P8-4 的范围。

### P8-2 目标写锁

P8-2 于 2026-05-24 完成。

调度器现在从 P7 的目标感知任务计划中推导出目标写锁需求：

- `frontend_change`、`backend_change` 和 `platform_maintenance` 任务需要对其解析后的 `targetId` 持有写锁；
- 针对 `demo-frontend` 或 `demo-backend` 的同一会话写任务不会并发启动；
- 等待锁的任务被标记为 `waiting_target_lock`，并带有 `planJson.scheduler.targetId` 和 `lockHolderTaskRunIds`；
- 终端 TaskRun 转换会刷新调度器状态，以便等待锁的任务在锁持有者完成后可以返回到 `pending` / `ready` 状态；
- 审查/QA 任务默认保持只读导向，除非明确标记为写任务，否则不会获取写锁；
- 尝试在没有平台模式和审批的情况下针对 `agenthub-platform` 的普通后端任务，在 TaskRun 创建之前会被阻止。

当前限制：P8-2 尚未实现完整的 契约 -> 后端 -> 前端 -> 审查 -> 预览 -> 模拟部署 流水线的自动推进。这仍属于 P8-3 的范围。

### P8-1 依赖感知的任务调度器

P8-1 于 2026-05-24 完成，作为 `agenthub-p8-dependency-scheduler-target-locks` 的第一个实现步骤。

AgentHub 现在拥有一个针对任务图依赖关系的窄调度器边界：

- 上游依赖未完成的任务被标记为 `waiting_dependency`，并且不会自动启动；
- 上游依赖失败、中断或阻塞的任务被标记为 `blocked`；
- 依赖 wait/block 元数据在 `planJson.scheduler` 中可见，包括调度器状态、可运行标志、原因、依赖 ID 和阻塞依赖 ID；
- 仅代表已创建计划的合成 Manager 规划任务，在任务图创建时被标记为 `completed`，以便依赖的安全前端任务仍能通过 P6 路径自动启动；
- 当上游 TaskRun 达到终端状态时，会重新评估下游任务；
- 手动 TaskRun 创建在调度器自动启动路径之外保持其现有行为。

当前限制：P8-1 未添加目标写锁、自动全流水线推进、故障恢复能力或调度器 UI 跟踪。这些仍属于 P8-2 到 P8-5 的范围。

## P7 状态

### P7-6 端到端预演与冻结审查

P7-6 于 2026-05-24 完成。

结果：P7 已准备好作为本地单用户 AgentHub 工作区的“目标项目注册表 + 权限化执行”功能进行冻结。

P7 未运行新的真实 Claude/Codex 变更。冻结审查复用了 P6 最终的真实 `ClaudeCodeAdapter` 迷你 CRM 证据，用于差异、审查、预览和模拟部署循环，然后通过 API 预演和完整回归验证，验证了新的 P7 注册表和权限边界。

P7 API 预演证据：

- 迷你 CRM 预演会话 ID：`d0500f2c-a480-4903-aea5-5d2d72b2bf31`；
- 契约 ID：`contract-mini_crm_contacts`；
- 前端目标 ID / 后端目标 ID：`demo-frontend`, `demo-backend`；
- 注册表解析的演示 API 基础 URL：`http://127.0.0.1:5174`；
- 迷你 CRM 任务 ID：`952bcfd1-12b9-41ca-b81d-694a66b4dcea`, `d382a368-0cd2-4d46-86c6-790b691d4b58`, `5966d060-0df4-463d-94e1-d7bebdddf729`, `634bb541-3b0e-47ad-a408-13392b6dea11`；
- 平台预演会话 ID：`57d92dde-710f-484e-b86a-f7c0e06e22e6`；
- 平台任务/运行：`fc86452a-a92b-4894-844d-372b5df799e1`, `7ef6efcb-979c-4984-a1a2-2f29f893bc79`；
- 平台目标/状态/审批：`agenthub-platform`, `waiting_approval`, `security_approval`, `high`。

完整的证据记录和注意事项请参见 `docs/p7-freeze-review.md`。

推荐的冻结标签：`p7-target-registry-permissioned-execution-freeze`。

### P7-5 平台维护模式

P7-5 于 2026-05-24 完成。
AgentHub 现在将普通的应用后端工作与平台维护分离开来：

- 普通的 `@backend` 请求继续创建针对 `apps/demo-api` 的 `demo-backend` 任务；
- 明确的平台维护请求（如 `platform mode ...`）会创建针对 `agenthub-platform` 的 `platform_maintenance` 任务；
- 平台维护计划包括 `platformMode: true`、`requiresApproval: true`、更严格的验证期望以及 `safeTarget: apps/api`；
- 为平台维护任务创建 TaskRun 时，会以 `waiting_approval` 状态启动，并附带 `security_approval` 请求，而不是立即排队执行适配器。

这使得 AgentHub 平台后端代码免受普通应用后端任务的影响，同时为已批准的平台维护保留了明确的路径。

### P7-4 目标感知的审查/质量保证

P7-4 于 2026-05-24 完成。

脚本化审查现在会根据目标项目注册表策略评估合约差异：

- 变更的文件必须得到合约前端目标或后端目标的许可；
- 被拒绝的路径（如 `apps/api`、`.env*`、`.git`、`node_modules` 和 `secrets`）会被报告为目标策略违规；
- 修改 `apps/api` 的普通应用差异会被报告为 `failed` / `high` 风险；
- 前端本地 API 基础 URL 会与注册表解析的 `demo-backend` 基础 URL 进行比较；
- 任务目标 ID 会与合约 frontend/backend 目标 ID 进行核对。

审查在产品流程中仍保持建议性质：警告或失败会被记录为审查制品，不会在 P7-4 中引入新的阻塞性审批关卡。

### P7-3 目标感知的合约规划器

P7-3 于 2026-05-24 完成。

针对有界应用请求的合约优先规划现在通过目标项目注册表解析目标：

- 应用合约包括 `frontendTargetId: demo-frontend` 和 `backendTargetId: demo-backend`；
- 应用合约保留兼容性字段，如 `frontendTarget`、`backendTarget` 和 `demoApiBaseUrl`，但这些值源自注册表元数据；
- 生成的后端、前端和审查任务计划包含目标 ID 和注册表派生的安全路径；
- 任务图元数据包含任务映射到具体目标时的目标 ID。

P6 迷你 CRM 路径仍然创建相同的四个任务合约优先图：Manager 合约、后端 Agent、前端 Agent 和 Review/QA.。不受支持的广泛请求仍会避免静默执行。

### P7-2 目标感知的指令构建器

P7-2 于 2026-05-24 完成。

Agent 指令现在通过目标项目注册表边界生成：

- 前端指令解析 `demo-frontend`、其允许路径 `apps/demo/src` 以及相关的 `demo-backend` 基础 URL；
- 后端指令解析 `demo-backend`、其允许路径 `apps/demo-api`、其验证命令 `pnpm demo:api:test` 以及 `apps/api` 拒绝；
- 仅当任务明确针对 `agenthub-platform` 时，才能构建平台维护指令，并且这些指令声明需要平台模式和审批；
- 当任务计划包含目标 ID 时，会话上下文包现在包含已解析的目标元数据，同时保留 P6 遗留计划形状。

`apps/api/app/main.py` 中旧的未使用的 `instruction_for_task` 辅助函数已被移除，因此 `apps/api/app/instruction_builder.py` 仍然是唯一的指令构建器边界。

当前限制：规划器生成的应用合约和任务仍需要在 P7-3 中迁移，以默认发出目标 ID。审查策略执行仍需要 P7-4 的目标感知检查。

### P7-1 目标项目注册表

P7-1 于 2026-05-24 完成，作为 `agenthub-p7-target-registry-permissioned-execution` 的第一步。

AgentHub 现在拥有一个静态的后端目标项目注册表边界，包含三个初始目标：

- `demo-frontend`：`apps/demo`，前端应用目标，允许在 `apps/demo/src` 下写入，与 `demo-backend` 相关；
- `demo-backend`：`apps/demo-api`，后端应用目标，基础 URL `http://127.0.0.1:5174`，验证命令 `pnpm demo:api:test`；
- `agenthub-platform`：AgentHub 维护目标，需要明确的平台模式和审批，通过 `pnpm check && pnpm test` 进行更严格的验证。

注册表还集中了默认拒绝的路径，如 `.env*`、`node_modules`、`.git` 和 `secrets`，并且普通演示应用目标拒绝跨目标修改，例如 `apps/api`。

当前限制：P7-1 仅引入并测试注册表边界。规划器、指令构建器、上下文包、审查和平台维护路由仍使用其现有的 P6 行为，直到 P7-2 到 P7-5 将它们迁移以消费注册表元数据。

## P6 状态

### P6-7 最终全栈排练与冻结审查

P6-7 最终排练于 2026-05-23 通过，此前进行了 P6-7a API 基础对齐修复和一个小型演示 API CORS 加固修复。

结果：P6 已准备好冻结，作为本地单用户 Agent 编码工作区的实用 Agent 执行能力升级。它仍然不是一个通用的 SaaS 生成器或生产部署平台。

新的排练请求：
```text
帮我做一个 mini CRM，包含联系人和备注
```
最新证据：

- 会话 ID：`d39ed32a-8426-4c75-86a1-9fd10a57f44c`；
- 合约 ID：`contract-mini_crm_contacts`；
- 合约演示 API 基础 URL：`http://127.0.0.1:5174`；
- 后端任务/运行：`efe6482b-b2e3-43a7-bae9-2aa0b44dde41`，
  `908a5708-3334-474c-8af6-b18e6ceaa319`；
- 前端任务/运行：`f1d141d1-7fcb-4629-9ed1-20fd957d6ef4`，
  `7a01e9ea-8d5d-4690-ae4c-35fbca0b6309`；
- 两个编码运行的适配器类型：`claude_code`；
- 最终差异制品 ID：`a89dba5d-cc92-490c-aca1-6c00cd20cc5c`；
- 最终审查制品 ID：`076f01c5-1949-4fa6-9715-623e41642edb`；
- 最终审查状态/风险：`passed`，`low`；
- 预览 ID/URL/健康状态：
  `d515ffaf-bf9d-481d-9b51-77aa57eb2cef`，
  `http://127.0.0.1:62947`，健康；
- 模拟部署 ID/提供商/状态：
  `ff54062e-35ca-462d-a5f7-e9a4786517ec`，`mock`，`ready`。

最终前端差异包含 `http://127.0.0.1:5174`，未包含
`http://localhost:8000` 或 `http://127.0.0.1:8000`。对预览的浏览器检查显示联系人列表包含 `Ada Lovelace` 和 `Grace Hopper`，这
验证了浏览器可见的迷你 CRM 从演示 API 加载了数据，而不是
卡在 `Loading contacts...`。

演示 API 现在通过 CORS 允许本地预览源，因此全栈演练期间动态本地端口上的 Vite 预览可以调用 `apps/demo-api`。

剩余注意事项：

- 合约图中计划的 QA/Review 任务仍处于待处理状态；自动差异后审查制品提供合约一致性证据；
- 审查仍为确定性 `scripted_mock`，并非真正的 Claude 审查；
- 部署仍标记为模拟，并非生产部署；
- P6 仍限于待办事项、笔记和迷你 CRM 联系人风格的垂直切片，而非任意 SaaS 生成；
- 同会话写入任务仍为串行。

建议冻结标签：`p6-agent-execution-upgrade-freeze`。

### P6-7a 演示 API 基础对齐修复

P6-7a 于 2026-05-23 完成，作为 P6-7 冻结阻塞器的针对性修复。

变更内容：

- 合约优先应用合约现在包含
  `demoApiBaseUrl: "http://127.0.0.1:5174"`；
- 合约验证预期现在声明前端应用数据调用必须使用演示 API 基础 URL；
- 合约感知的前端代理指令现在明确要求使用合约中的演示后端基础 URL；
- 合约感知的前端代理指令明确禁止使用 `http://localhost:8000` 或 `http://127.0.0.1:8000` 处的 AgentHub 平台 API 用于生成的应用数据；
- 脚本化审查现在在前端合约差异引用 AgentHub 平台 API 基础而非演示 API 基础时发出警告。
- `apps/demo-api` 现在通过 CORS 允许本地预览源，因此动态本地端口上的 Vite 预览可以调用演示后端。

新增或更新的测试：

- 规划覆盖验证迷你 CRM `appContract` 中存在 `demoApiBaseUrl`；
- 指令覆盖验证前端代理提示包含 `http://127.0.0.1:5174` 并禁止 `http://localhost:8000`；
- 审查覆盖验证包含 `const API_BASE = "http://localhost:8000"` 的前端差异会产生警告并建议 `http://127.0.0.1:5174`。
- 演示 API 覆盖验证本地预览 CORS 对 `/contacts` 的预检。

P6-7a 最初未运行新的真实 Claude/Codex 变更。后续的 P6-7 演练验证了生成的前端代码使用演示 API 基础，并且浏览器可见的迷你 CRM 从 `apps/demo-api` 加载联系人。

### P6-7 全栈垂直切片演练与冻结审查

P6-7 冻结审查于 2026-05-23 运行。

结果：P6 尚未准备好冻结。P6-6 的证据对于合约优先编排、目标感知的 backend/frontend 任务创建、真实的 `ClaudeCodeAdapter` 执行、diff/review 制品创建、持久预览启动和模拟部署创建仍然有效。但是，浏览器可见的迷你 CRM 应用默认未与安全的演示后端完全集成。

复用的 P6-6 证据：

- 会话 ID：`ad122cf7-afe7-4921-bbd9-b7e815539427`；
- 合约 ID：`contract-mini_crm_contacts`；
- 后端任务/运行：`590cb06b-4a47-422e-b68f-79a873d4c84a`，
  `d6779d0f-afa3-4124-9117-c40b651dd79a`；
- 前端任务/运行：`12ffc19d-f483-4f8d-a541-4c5b935a49b4`，
  `ade5c49c-097d-448e-831c-d10c6bdc3a71`；
- 两个编码运行的适配器类型：`claude_code`；
- 最终差异制品 ID：`db403329-7f0c-4b2c-9134-d2d7ee652564`；
- 最终审查制品 ID：`1782b85d-c7f9-4d93-b699-27bd27a05ef7`。

持久预览证据：

- 持久 AgentHub API 于 `http://127.0.0.1:8010` 启动，因为旧的 `127.0.0.1:8000` 进程接受 TCP 连接但未响应 `/health`；
- 预览通过持久 API 为前端任务运行 `ade5c49c-097d-448e-831c-d10c6bdc3a71` 启动；
- 新预览 ID：`3e500940-4d46-423b-af66-b36f1e6ba604`；
- 新预览 URL/健康状态：`http://127.0.0.1:65046`，健康；
- `curl -I http://127.0.0.1:65046` 在预览创建后立即返回 `200 OK`，并在 20 秒延迟后再次返回；
- 新模拟部署 ID/提供商/状态：
  `6b14e81b-c1d6-40ed-b6c4-88a3f846db60`，`mock`，`ready`。

临时预览进程和临时 `8010` / `5174` 开发服务
在验证后已停止。

演示后端证据：

- `pnpm demo:api:dev` 在 `http://127.0.0.1:5174` 上提供了安全的演示后端；
- `GET /health` 返回了 `{"status":"ok","service":"agenthub-demo-api"}`；
- `GET /contacts` 返回了种子联系人。

冻结阻塞项：

- P6-6 会话工作区中生成的前端代码使用了 `const API_BASE = "http://localhost:8000"`；
- `apps/demo-api` 默认值为 `http://127.0.0.1:5174`；
- 预览的浏览器检查显示应用卡在 `Loading contacts...`；
- `curl http://127.0.0.1:8000/contacts` 对过时的 AgentHub API 进程超时；
- 因此最终的迷你 CRM 预览外壳可访问，但生成的前端无法可靠地调用安全的演示后端目标。

P6-7 在 OpenSpec 任务列表中故意保持未检查状态，直到此集成阻塞项通过新的演练重新验证。P6-7a 修复了规划、指令和审查路径，以便未来的全栈前端任务指向演示 API 基础 URL，并且 API 基础不匹配问题会在审查中被捕获。

### P6-6 迷你 CRM 全栈垂直切片

P6-6 于 2026-05-22 完成，作为 API 驱动的全栈垂直切片冒烟测试。

冒烟请求：
```text
帮我做一个 mini CRM，包含联系人和备注
```
结果：一个普通的无提及请求通过编排器路由，生成了共享的 `contract-mini_crm_contacts` 应用契约，创建了目标感知的后端 Agent 和前端 Agent 任务，使用 `ClaudeCodeAdapter` 运行了两个编码任务，生成了覆盖 demo 后端和 demo 前端目标的最终累积差异，生成了审查制品，创建了预览制品，并创建了模拟部署制品。

证据：

- 会话 ID：`ad122cf7-afe7-4921-bbd9-b7e815539427`；
- 契约 ID：`contract-mini_crm_contacts`；
- 后端任务/运行：`590cb06b-4a47-422e-b68f-79a873d4c84a`，`d6779d0f-afa3-4124-9117-c40b651dd79a`；
- 前端任务/运行：`12ffc19d-f483-4f8d-a541-4c5b935a49b4`，`ade5c49c-097d-448e-831c-d10c6bdc3a71`；
- 两个编码运行的适配器类型：`claude_code`；
- 最终差异制品 ID：`db403329-7f0c-4b2c-9134-d2d7ee652564`；
- 最终审查制品 ID：`1782b85d-c7f9-4d93-b699-27bd27a05ef7`；
- 预览 ID/URL/健康状态：`79bfff4f-4991-470b-8862-eb43e7dac852`，`http://127.0.0.1:55592`，创建时健康；
- 模拟部署 ID/提供商/状态：`e7b676d6-1505-43f8-be78-7120bfaef831`，`mock`，`ready`。

会话工作区中变更的文件：

- `apps/demo-api/app/main.py`；
- `apps/demo-api/tests/test_contacts.py`；
- `apps/demo/src/App.tsx`；
- `apps/demo/src/styles.css`。

最终审查制品通过，风险较低，并验证了 `contract-mini_crm_contacts` 的契约一致性：累积差异包含了 `apps/demo-api` 下的后端目标变更和 `apps/demo/src` 下的前端目标变更。

demo 后端测试在 smoke 工作区中从正确的 `apps/demo-api` 工作目录通过：`6 passed`。

注意事项：

- 这是 API 驱动的演练，而非浏览器点击演练；
- 审查制品使用了确定性的 `scripted_mock` 审查行为；
- 计划的 QA/Review 任务保持待处理状态，因为自动的后差异审查制品提供了契约一致性证据；
- 预览制品在创建时健康，但在一次性 TestClient smoke 进程退出后，后续对记录的预览 URL 的 `curl` 失败。在 P6-7 期间，应在持久化的 `pnpm dev:api` 下检查长期预览可用性。

详细证据记录在 `docs/p6-mini-crm-vertical-slice.md` 中。

### P6-5 目标感知的契约优先编排器

P6-5 于 2026-05-22 完成。

AgentHub 现在拥有针对有界全栈迷你应用请求的契约优先编排器规划。这仅是规划升级；尚未运行真正的 Claude/Codex 全栈生成。

支持的应用类型：

- 待办事项应用；
- 笔记应用；
- 迷你 CRM 联系人应用。

当普通的无提及或 `@orchestrator` 消息请求这些应用类型之一时，编排器会创建一个共享的 `appContract` 规划负载，包含：

- `appName`；
- `appType`；
- `userGoal`；
- `entities` 和 `fields`；
- `apiRoutes`；
- `frontendPages`；
- `backendTarget: apps/demo-api`；
- `frontendTarget: apps/demo`；
- `validationExpectations`；
- `taskGraph`。

生成的任务图是串行的且目标感知的：
```text
Manager / Contract task -> Backend Agent task -> Frontend Agent task -> QA / Review task
```
每个任务在 `planJson` 中存储相同的 `contractId` 和 `appContract`。
后端任务针对 `apps/demo-api`，前端任务针对 `apps/demo` 前端内部的 `apps/demo/src`，
而审查任务则验证后端和前端工作是否引用同一份契约。任务默认处于待处理状态，在 P6-5 中不会自动启动。

角色指令现在显式地展示了共享的应用契约：

- 后端 Agent 指令引用该契约并针对 `apps/demo-api`；
- 前端 Agent 指令引用同一份契约并针对 `apps/demo/src`；
- QA / 审查指令根据共享契约审查后端和前端的工作。

现有的登录页面、有边界的前端规划器、无提及的仪表盘自动运行、直接的 `@frontend` 以及直接的 `@backend` 路径保持不变。

不支持的宽泛 SaaS 请求，例如包含支付、认证或多租户的生产级 SaaS，仍然不会创建无限制的任务，并会收到诚实的边界响应。

P6-5 不实现实际的全栈应用生成、生产部署、认证、支付、多租户、Docker、云数据库、提供商市场、PR 创建，或任何修改 `apps/api` 作为应用后端代码的权限。

### P6-4 安全演示后端目标脚手架

P6-4 于 2026-05-22 完成。

AgentHub 现在在 `apps/demo-api` 下有一个隔离的演示后端目标，因此后端 Agent 的工作可以针对应用后端代码，而无需修改 `apps/api` 中的 AgentHub 平台后端。

演示后端脚手架：

- 框架：最小化的 FastAPI 应用；
- 持久化：第一个脚手架使用内存中的联系人；
- 端点：
  - `GET /health`；
  - `GET /contacts`；
  - `POST /contacts`；
- 本地开发命令：`pnpm demo:api:dev`；
- 测试命令：`pnpm demo:api:test`；
- 检查命令：`pnpm check:demo-api`。

当 `apps/demo-api` 存在时，`@backend` 的直接提及现在会创建一个分配给后端 Agent 的待处理 `backend_change` 任务。该任务被限定在 `apps/demo-api` 内，并包含 `apps/demo-api/app/main.py` 和 `apps/demo-api/tests/test_contacts.py` 作为第一个脚手架文件。它在 P6-4 中不会自动启动。

后端角色指令现在声明 `apps/demo-api` 存在，提及联系人 API 脚手架，并继续禁止编辑 `apps/api`，后者仍然是 AgentHub 控制平面后端。

P6-4 不实现契约优先编排、全栈应用生成、生产部署、Docker、认证、支付、云数据库、多租户行为，或与演示 API 的自动前端集成。

### P6-2 / P6-3 上下文包与基于角色的指令

P6-2 和 P6-3 于 2026-05-22 完成。

AgentHub 现在为 Agent 执行构建一个可重用的会话上下文包，并为 TaskRun 适配器请求使用基于角色的指令构建器。

上下文包字段包括：

- 原始用户请求；
- 当前任务 ID、标题、意图类型、描述和计划；
- 仅来自同一会话的最近消息，限制为八条消息；
- 会话执行账本摘要和最新账本 ID；
- 最近更改的文件；
- 最新的差异元数据，包括制品 ID、引用、更改的文件和统计信息；
- 最新的审查摘要、状态、风险、审查的文件、发现和建议；
- 最新的预览 ID、URL、健康状态和端口；
- 最新的模拟部署 ID、提供商、环境、状态和 URL；
- 当传递有效的当前会话制品 ID 时，选定的制品上下文；
- 安全目标路径；
- 任务角色和制品流程的验证期望。

上下文包作为 `sessionContext` 附加到适配器 `planContext`，并作为 JSON 块嵌入到生成的指令中。这为 Claude Code / Codex 提供了足够的会话状态以进行后续工作，同时不允许跨会话泄漏。

角色指令行为：

- 管理器 / 编排器指令侧重于路由、有边界的任务创建、澄清以及对不支持工作的诚实拒绝。
- 前端指令保留原始请求，包含会话上下文，保持旧的 login-page/button/title 模板不变，并仅允许在 `apps/demo/src` 内对通用演示前端请求进行有意义的更改。
- 后端指令为 `apps/demo-api` 做准备，但明确指出安全演示后端目标尚不可用，并且不得修改 `apps/api`。
- QA / 审查指令默认是只读的，侧重于差异、更改的文件、账本、preview/deploy 状态和建议性发现。

P6-2/P6-3 不添加 `apps/demo-api`、全栈应用生成、Manager/Worker 调度、生产部署、新适配器或更广泛的护栏权限。

验证通过：

- 针对性的 `pytest tests/test_planning.py tests/test_task_runs.py -q`（37 个测试）；
- 完整的验证结果记录在此任务的变更日志中。

### P6-1b 编排器自主性真实冒烟测试

P6-1b 于 2026-05-22 作为 API 驱动的真实执行冒烟测试完成。

冒烟测试请求：
```text
帮我把当前 demo app 改成一个 dashboard，有三张统计卡片和一个最近活动列表
```
结果：一个没有显式 `@mention` 的普通用户消息被路由到
编排器/管理器，创建了一个安全的前端演示任务，自动启动了一个
TaskRun，调用了 `ClaudeCodeAdapter`，生成了一个真实的 diff，生成了一个
非阻塞的脚本化审查制品，在冒烟测试期间启动了一个健康的预览，
并创建了一个模拟部署制品。

证据：

- 会话 ID：`cca9af54-1338-4cdd-b239-7f8b6e1dcc76`；
- 消息 ID：`48bad4c0-8ddf-4514-bf35-d2561082c22e`；
- 任务 ID：`63a8aded-b311-40f3-a54c-a40d232102c5`；
- 任务运行 ID：`210f3f89-df0f-4e72-8c20-d505faed5ea2`；
- 适配器类型：`claude_code`；
- 最终状态：`completed`；
- 变更的文件：`apps/demo/src/App.tsx`，
  `apps/demo/src/styles.css`；
- diff 制品 ID：`7114d52a-925a-4c4d-a00b-4d6c8775a20c`；
- 审查制品 ID：`ce989818-5d85-4f88-9f70-8b9b5e69d606`；
- 预览 ID / URL / 健康状态：`841f7fd6-bb75-4e80-b19c-9b228f5040fb`，
  `http://127.0.0.1:58487`，冒烟测试期间健康；
- 部署 ID / 提供商 / 状态：
  `7c9fab78-2b5f-44b3-a9fc-2af0d912a757`，`mock`，`ready`。

会话账本记录了原始目标，`frontend` 作为活跃代理，最新的
diff/review/preview/deploy 证据，以及 `claude_code` 作为最后一个
成功的适配器。

注意事项：

- 这是一个使用 FastAPI `TestClient` 的 API 驱动冒烟测试，而非浏览器点击
  演练；
- 在一次性 TestClient 进程退出后，后续的 `curl` 无法
  访问预览 URL，因此长时预览可用性应在后续浏览器演练中在
  `pnpm dev:api` 下验证；
- 审查制品使用了确定性的 `scripted_mock` 审查行为；
- 不需要 ScriptedMock 兜底执行，因为真实的 Claude Code
  运行成功。

详细证据记录在 `docs/p6-orchestrator-autonomy-smoke.md` 中。

### P6-1 编排器自主性冲刺

P6-1 于 2026-05-22 完成。

AgentHub 现在拥有第一个 P6 消息路由和执行自主性切片：

- 没有显式角色提及的普通用户消息默认路由到编排器/
  管理器；
- `@orchestrator` 也路由到编排器/管理器；
- `@frontend`，`@backend`，`@qa` 和 `@review` 是面向高级用户的显式分配模式；
- 编排器创建的安全前端演示任务可以通过现有的 TaskRun 路径自动启动；
- 通用前端演示指令保留原始用户请求，并允许在 `apps/demo/src` 内部进行更广泛的更改，而不是将每个任务
  简化为 login-page/button/title 模板。

第一个自动运行路径有意保持狭窄。P6-1 仅自动启动标记为
`autoStart` 和 `safeTarget=apps/demo/src` 的安全前端演示任务。
后端执行不会自动启动，因为安全演示后端目标尚不可用；直接的
`@backend` 请求现在会收到清晰的“缺少目标”响应，而不是针对 AgentHub 平台
后端创建一个不受限制的任务。

路由行为：

- 无显式提及：编排器决定是创建任务、询问有界演示目标，还是诚实地拒绝不受支持的请求；
- `@frontend`：当请求限定于演示应用 UI 时，创建一个待处理的前端任务；
- `@backend`：报告需要先提供一个安全演示后端目标；
- `@qa`：创建一个分配给 QA 代理的 QA 审查式任务；
- `@review`：创建一个分配给 QA 支持的审查路径的只读审查任务。

P6-1 保留了现有的 `CodexAdapter`，`ClaudeCodeAdapter` 和
`ScriptedMockAdapter` 执行路径。它没有添加完整的 approval/risk
引擎，Manager/Worker 调度器，全栈应用生成，多用户 IM，
提供商市场，生产部署或 PR 创建。

验证通过：

- `pnpm check`
- `pnpm test`（36 个 Web 测试，121 个 API 测试）
- `git diff --check`
- `openspec validate agenthub-p6-agent-execution-upgrade --strict`

P6-1 中未运行手动浏览器冒烟测试。自动运行行为通过 API 测试验证，这些测试确认一个无提及的演示仪表板请求会创建一个前端任务和带有已配置适配器的排队 TaskRun。此任务中未声明或重新运行真实的 Claude/Codex 成功。

## P5 状态

### P5-7 端到端演练与冻结审查

P5-7 于 2026-05-22 完成。

冻结结果：P5 已准备好冻结为本地单用户 IM 风格的多代理编码工作区 v1。它保留了 P4 最终演示基线，并且不声称是一个完整的多人 IM 平台。

审查依据：

- 初始工作树在 `d3b479d feat: add review workflow, execution trace, and artifact cards` 处是干净的；
- 审查了 `AGENTS.md`，项目 README，项目状态，变更日志，P4 审计和最终演示文档，平台路线图，以及 P5 OpenSpec 提案、设计、任务和规范；
- P5-7 期间未运行新的 Claude/Codex 变更，以避免在 P4 浏览器演练已验证真实和兜底执行路径后重复真实适配器工作；
- P5 特定行为通过已提交的 backend/frontend 测试和已实现任务切片的代码审查进行了验证。

P5 冻结证据：

- 代理联系人渲染管理器/编排器、前端、后端、QA、审查和兜底条目，包含角色、适配器类型、标签和状态。直接聊天
- 和群组工作流仍仅为本地可视化模式。
- 工作区上下文/执行账本通过 `GET /sessions/{session_id}/ledger` 持久化并暴露，测试覆盖了规划、差异、预览和模拟部署后的更新。
- 动态管理器规划器 v1 支持针对 heading/title 文本、主按钮文本、强调色、简单输入字段、status/help 文本以及小型布局文案变更的有界前端意图。不支持的广泛请求不会创建任务，也不声称提供支持。
- 审查制品在差异收集后创建，在 v1 中使用确定性 `scripted_mock` 审查行为，并且对预览和模拟部署保持非阻塞。
- 多智能体执行轨迹显示：管理器已规划、编码智能体已运行、差异已生成、审查智能体已审查、预览健康、模拟部署就绪。
- 制品消息卡片渲染差异、审查、预览和模拟部署卡片，选择正确的制品面板项，并且仅公开由现有 API 支持的操作。
- 预览和模拟部署继续使用现有的 preview/deployment API。
- P4 浏览器证据仍然是需求 -> 规划 -> 智能体执行 -> 差异 -> 预览 -> 模拟部署这一流程的真正端到端证明：真实的 Claude Code 运行 `f1e78e9e-2f6b-4b9c-b4a7-5879d513c555`，差异制品 `b4c0fae4-bfeb-4105-a506-64de639472c6`，预览 `4eb1622b-fb10-49e7-9b3d-5c256fad4b29`，部署 `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`；兜底运行 `36d68849-f644-4242-a64b-27c05b8cf2d8`，差异制品 `fbe67726-20e3-4ad5-9b08-d4514aa97cbe`，预览 `6c7f6f46-e287-4698-b6be-c99058f69b11`，部署 `a0b5d533-acee-4b2a-a384-103197d46481`。

剩余注意事项：

- P5 仍然是本地单用户软件，而非完整的多人 IM 产品。
- 直接聊天和群组工作流仅为可视化模式；未添加账户、多人同步或外部 IM 集成。
- 审查智能体在 v1 中是确定性和非阻塞的，并非企业安全网关或真正的 Claude/Codex 审查路径。
- 动态规划器是有界且基于规则的，并非不受限制的自然语言编辑或通用 LLM 规划器。
- 制品上下文选择仅为前端会话辅助功能；制品引用不会持久化到后端消息记录中。
- 模拟部署仍然是模拟证据，而非生产部署。

提交 P5 冻结审查后的推荐标签名称：
`agenthub-p5-platform-evolution-freeze`。

验证通过：

- `openspec validate agenthub-p5-platform-evolution --strict`
- `pnpm check`
- `pnpm test`（36 个 Web 测试，116 个 API 测试）
- `git diff --check`

### P5-6 制品消息卡片 v2

P5-6 于 2026-05-21 完成。

AgentHub 现在在任务时间线内将差异、审查、预览和模拟部署制品渲染为消息式卡片。这些卡片重用已加载的现有制品，并且不添加新的后端制品引用表。

制品卡片行为：

- 差异卡片显示更改的文件、additions/deletions、来源 task/run，以及检查差异、将差异用作本地后续上下文，或在尚未加载审查时触发现有审查 API 的操作。
- 审查卡片显示审查状态、风险、已审查文件、适配器类型、来源 task/run，以及检查或将审查用作本地后续上下文的操作。
- 预览卡片显示 URL、健康状态、状态、端口、来源 task/run，以及在预览健康时检查、打开预览或创建现有模拟部署卡片的操作。
- 模拟部署卡片显示提供商、环境、状态、URL、来源 task/run，并明确标记为模拟部署证据。

右侧的制品面板仍然是详细的检查器。选择一张卡片会打开匹配的面板项。当用户选择某个制品作为上下文时，编辑器现在会显示一个本地、会话范围的后续上下文标签。这仅为前端辅助功能；P5-6 不会持久化消息到制品的引用，也不会更改后端规划语义。

P5-6 不会添加生产部署、提供商市场、document/PPT 渲染、完整代码编辑器编辑、不受限制的任意编辑或适配器执行更改。

验证通过：

- `pnpm check`
- `pnpm test`（36 个 Web 测试，116 个 API 测试）
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-5 动态管理器规划器 v1

P5-5 于 2026-05-21 完成。

AgentHub 现在拥有一个有界的本地管理器规划器 v1，用于处理一小部分前端变更意图。该实现是确定性的且基于规则；它不会调用 LLM 规划器，也不声称支持不受限制的自然语言编辑。

支持的动态前端意图：

- 标题或标题文本更改；
- 主按钮文本更改；
- theme/accent 颜色更改；
- 添加简单输入字段；
- 添加简单 status/help 文本；
- 小型布局文案调整。

动态管理器规划将结构化的任务图元数据持久化到任务 `planJson` 中。该图包含目标、规划器版本、意图、任务节点、分配的智能体角色、优先级、依赖关系和预期的制品类型。对于新的编排器主导的有界前端请求，该图会创建管理器、前端编码和审查任务。对于同会话的后续请求，它
创建一个序列化的前端编码任务，随后是一个依赖于该编码任务的审查任务。

现有的确定性登录页面规划器保持不变，作为 `deterministic_login_v1`，已知的 button/title 后续路径仍然有效。不支持宽泛的请求（例如整个应用重构）会回退到现有的确定性行为，不会创建任务或声称提供支持。

P5-5 为新的目标添加了针对真实编码适配器的有限指令，但不会改变适配器分发、适配器运行时语义、Manager/Worker 调度、生产部署、多用户即时通讯或 P4 最终演示基线。`ScriptedMockAdapter` 仍然针对原始登录页面和复制-更改演示路径进行了优化。

验证已通过：

- `pnpm check`
- `pnpm test`（34 个 Web 测试，116 个 API 测试）
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-4 多智能体执行追踪 UI

P5-4 于 2026-05-21 完成。

AgentHub 现在在每个任务卡片内显示多智能体执行追踪。该追踪源自现有的任务、任务运行、加载的制品、审查、预览和部署；它不会添加新的后端追踪端点或更改适配器执行语义。

追踪阶段：

- 管理器已规划；
- 编码智能体已运行；
- 差异已生成；
- 审查智能体已审查；
- 预览健康；
- 模拟部署就绪。

每个阶段显示负责的智能体或服务标识、adapter/service 类型、状态以及可用的制品链接。差异、审查、预览和模拟部署追踪节点重用现有的制品选择行为，因此右侧的制品面板仍然是详细的检查器。系统步骤（例如差异服务、预览服务和模拟部署服务）被标记为服务，而非自主智能体。

当 `scripted_mock` 运行从之前的运行中恢复时，追踪会突出显示回退恢复，并突出显示审查警告状态。P5-3 审查仍然是建议性的且非阻塞的。

P5-4 不会添加 Manager/Worker 调度、动态规划、真实的多用户即时通讯、生产部署、新的适配器或真实的 Claude/Codex 审查执行。

验证已通过：

- `pnpm check`
- `pnpm test`（34 个 Web 测试，113 个 API 测试）
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-3 审查智能体工作流

P5-3 于 2026-05-21 完成。

AgentHub 现在在生成编码差异后创建一个非阻塞的审查智能体制品。第一个实现是确定性的，并标记为 `scripted_mock`；它不声称执行真实的 Claude 或 Codex 审查。

审查行为：

- 差异收集仍然首先存储 Git 差异；
- 为 TaskRun 上的最新差异创建一个脚本化的审查制品；
- 对同一差异重复创建审查是幂等的；
- 审查状态是建议性的，可以是 `passed`、`warning` 或 `failed`；
- v1 审查不会阻止预览创建或模拟部署；
- `GET /task-runs/{task_run_id}/reviews` 列出持久化的审查制品；
- `POST /task-runs/{task_run_id}/review` 可以为 TaskRun 创建或返回当前的脚本化审查。

审查制品模式包括状态、风险级别、摘要、审查的文件、发现、建议的更改、审查的差异制品 ID 和适配器类型。

会话账本摘要现在在存在时包含最新的审查摘要。右侧制品面板和任务时间线可以显示审查制品，以及差异、预览和模拟部署制品。

P5-3 不会添加企业审批关卡、安全执行、真实的 Claude/Codex 审查执行、Manager/Worker 调度或任何针对 preview/deploy. 的阻塞策略。

验证已通过：

- `pnpm check`
- `pnpm test`（33 个 Web 测试，113 个 API 测试）
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-2 共享上下文和执行账本

P5-2 于 2026-05-21 完成。

AgentHub 现在在 SQLite 中持久化一个轻量级的会话范围执行账本，并通过 `GET /sessions/{session_id}/ledger` 暴露它。该账本是现有会话记录的确定性快照，而非长期记忆。它跟踪：

- 当前目标；
- 活跃的智能体角色；
- 最新的任务和任务运行；
- 最新的差异制品和更改的文件；
- 最新的预览 ID、URL 和健康状态；
- 最新的模拟部署 ID、提供者和状态；
- 最后成功的适配器；
- 一个紧凑的 Markdown 摘要和更新时间戳。

账本刷新点：

- 在用户消息创建和规划之后；
- 在成功收集差异之后；
- 在创建健康预览或刷新预览健康状态之后；
- 在创建模拟部署之后；
- 在读取账本时，以便可以从持久化的消息、任务、运行和制品中重建较旧的会话。

工作区 shell 现在为选定的会话显示一个小的 `Workspace Context` 卡片。它总结了当前目标、活跃的智能体、最新证据、适配器和更改的文件，而不会替换任务时间线。

P5-2 不会添加向量记忆、嵌入、跨会话记忆、审查智能体执行、Manager/Worker 调度或适配器分发更改。

验证已通过：

- `pnpm check`
- `pnpm test`（30 个 Web 测试，113 个 API 测试）
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

### P5-1 智能体注册表与即时通讯联系人界面

P5-1 于 2026-05-21 完成，是 `agenthub-p5-platform-evolution` 的第一个实现切片。

AgentHub 现在通过工作区作用域的只读 API 将已启用的内置智能体暴露为 IM 风格的联系人，并在工作区外壳中渲染它们。联系人注册表仅为 display/metadata 只读，不会改变适配器调度、规划、任务执行、差异收集、预览或模拟部署行为。

可见联系人：

- 管理者/编排器 (`@orchestrator`, `scripted_mock`)；
- 前端智能体 (`@frontend`, `codex`)；
- 后端智能体 (`@backend`, `codex`)；
- QA 智能体 (`@qa`, `scripted_mock`)；
- 审查智能体占位符 (`@review`, 计划于 `claude_code`)；
- 兜底智能体 / ScriptedMock (`@fallback`, `scripted_mock` 服务)。

UI 增加了本地可视化模式，用于直接聊天和群组工作流。这些仅为单用户产品模式；它们不增加多用户账户、外部 IM 集成、Manager/Worker 调度、动态规划或审查智能体执行。

验证通过：

- `pnpm check`
- `pnpm test` (28 个 Web 测试, 114 个 API 测试)
- `git diff --check`
- `openspec validate agenthub-p5-platform-evolution --strict`

## P4 状态

### P4-6 最终冻结审查

P4-6 最终冻结审查于 2026-05-20 完成。

冻结结果：准备冻结 `agenthub-final-demo-hardening` 基线。

已验证的文档一致性：

- `AGENTS.md`, README, `docs/project-state.md`, `docs/change-log.md`,
  `docs/e2e-capability-audit.md`, `docs/final-demo-checklist.md`,
  `docs/project-summary-for-interview.md`, `docs/platform-roadmap.md`, 以及
  `agenthub-final-demo-hardening` OpenSpec 制品一致地将 AgentHub 描述为本地单用户智能体编码工作区 / 强演示 MVP。
- 文档未声称是一个完整的 IM 多用户平台、生产部署、提供商市场、Docker 沙箱、PR 创建或广泛的任意自然语言编辑。
- 本次审查后，P4 任务 1.1 至 1.6 已完成。

剩余注意事项已记录：

- 部署由模拟支持，非生产部署；
- 浏览器点击自动化在 `docs/e2e-capability-audit.md` 中记录了本地 tooling/permission 注意事项；
- `pnpm demo:reset` 不删除 `.worktrees`；
- `pnpm demo:reset` 不停止旧的预览或开发服务器进程；
- mobile/responsive 打磨工作留待未来，不在最终演示范围内。

验证通过：

- `openspec validate agenthub-im-coding-mvp --strict`
- `openspec validate agenthub-final-demo-hardening --strict`
- `pnpm check`
- `pnpm test`
- `git diff --check`

提交最终冻结审查后推荐标签名：
`agenthub-final-demo-hardening-freeze`。

### P4-5 最终项目总结 / 面试说明

P4-5 增加了 `docs/project-summary-for-interview.md`，一份用于演示、审查和面试的真实最终项目总结。它将 AgentHub 定位为本地单用户智能体编码工作区 / 强演示 MVP，并解释了：

- AgentHub 解决的问题；
- 前端、后端、SQLite、会话工作树、适配器和制品流水线架构；
- 核心需求 -> 计划 -> 执行 -> 差异 -> 预览 -> 模拟部署工作流；
- `CodexAdapter`, `ClaudeCodeAdapter`, 以及 `ScriptedMockAdapter`；
- 强制失败的兜底恢复；
- 同会话后续文本变更流程；
- 什么是真实的、什么是模拟的、以及什么是故意未实现的；
- 设计权衡和面试讨论要点。

该总结引导读者参考 `docs/e2e-capability-audit.md` 获取证据 ID，而不是发明新证据。

### P4-4 最终演示检查清单

P4-4 增加了 `docs/final-demo-checklist.md`，作为最终 AgentHub 演示的以证据为先的排练检查清单。它涵盖：

- 使用 `pnpm demo:reset` 进行干净重置；
- backend/frontend 启动；
- 可选的 Claude Code 默认适配器启动；
- 固定需求消息；
- 任务运行、适配器、差异、预览和模拟部署验证；
- 通过强制 Codex 失败和 `ScriptedMockAdapter` 进行兜底恢复；
- 同会话后续请求 `把按钮文案改成 Sign in`；
- 证据 ID 捕获；
- 针对端口占用、API 缺失、auth/quota/runtime 问题、陈旧预览以及在 SQLite 打开时拒绝重置的故障排除。

该检查清单仅为文档，不改变应用行为。

### P4-3 演示重置 / 干净种子辅助工具

P4-3 为可重复的最终演示排练增加了安全的本地重置工作流：

- 命令：`pnpm demo:reset`
- 脚本：`scripts/demo-reset.sh`
- 活动 SQLite 数据库：`apps/api/data/agenthub.sqlite3`
- 备份位置：
  `apps/api/data/backups/demo-reset-<timestamp>/`
- 重置行为：
  - 当 SQLite 数据库被 API 进程打开时拒绝运行；
  - 备份活动数据库以及任何 SQLite WAL/SHM 文件；
  - 使用现有的 SQLModel 初始化路径重新创建并填充数据库；
  - 不删除 `.worktrees`、源代码、依赖项或预览文件；
  - 不停止正在运行的预览或开发服务器进程；
  - 打印所创建备份的恢复命令。

该辅助工具为现有的基线演示记录填充数据：一个演示用户、一个指向 `apps/demo` 的 `AgentHub Demo` 工作区，以及已启用的编排器、
前端、后端和 QA 智能体。它不会预先创建会话；演示
通过 UI 新建会话干净地启动。

在 2026-05-20 上重置演练：

- 第一次运行时 API 仍持有 SQLite：拒绝重置并打印了持有进程。
- 停止 API 后的第二次运行：将之前的数据库备份到
  `apps/api/data/backups/demo-reset-20260520-124612/`。
- 重置后的种子检查：1 个用户、1 个工作区、4 个智能体、0 个会话、0 个任务
  运行、0 个预览。
- `.worktrees` 仍然存在且未被删除。

### P4-2 浏览器端到端点击演练

P4-2 在 `http://127.0.0.1:3000` 处通过浏览器 UI 点击验证了最终演示循环，
此时 API 以 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api` 运行。

真实 Claude Code 路径通过了 UI 点击：

- 会话：`59ad209a-1f8d-4134-97c4-e4ad275b6f67`
- UI 标签：`会话 55`
- 任务：`eaac4f19-03c7-486f-b85a-1c4847cdcec8`
- 任务运行：`f1e78e9e-2f6b-4b9c-b4a7-5879d513c555`
- 适配器：`claude_code`
- 最终状态：`completed`
- 变更文件：`apps/demo/src/App.tsx`
- 差异制品：`b4c0fae4-bfeb-4105-a506-64de639472c6`
- 预览：`4eb1622b-fb10-49e7-9b3d-5c256fad4b29`
- 预览 URL：`http://127.0.0.1:49373`
- 预览 health/status：`healthy`、`ready`
- 部署：`6c5a423c-ec7b-4070-9a05-87a8dddd91a1`
- Provider/status：`mock`、`ready`

兜底路径通过了 UI 点击：

- 会话：`c148a1d6-8cd1-4efb-a797-7d10bbe475aa`
- UI 标签：`会话 56`
- 任务：`200e3d57-5856-41d1-9ec5-1ba203edc1f0`
- 失败的 Codex 任务运行：`e7cead6e-93cd-4195-9a53-e258da253a81`
- 失败错误码：`CODEX_DEMO_FORCED_FAILURE`
- 兜底任务运行：`36d68849-f644-4242-a64b-27c05b8cf2d8`
- 适配器：`scripted_mock`
- 最终状态：`completed`
- 变更文件：`apps/demo/src/App.tsx`
- 差异制品：`fbe67726-20e3-4ad5-9b08-d4514aa97cbe`
- 预览：`6c7f6f46-e287-4698-b6be-c99058f69b11`
- 预览 URL：`http://127.0.0.1:49752`
- 预览 health/status：`healthy`、`ready`
- 部署：`a0b5d533-acee-4b2a-a384-103197d46481`
- Provider/status：`mock`、`ready`

重载注意事项：持久化的运行、标签和制品面板在重载后仍然存在。右侧
制品面板在重载后默认回到差异视图；点击 `预览1` 可再次显示
持久化的预览 URL 和 iframe。

在 2026-05-20 上进行的后续浏览器抽查重新打开了持久化的 P4-2
会话，未再次运行真实的智能体变更：

- 真实 Claude Code 会话
  `59ad209a-1f8d-4134-97c4-e4ad275b6f67` 仍然显示已完成的
  `claude_code` 运行、`apps/demo/src/App.tsx` 差异标签、位于
  `http://127.0.0.1:49373` 的 `预览1` iframe，以及模拟部署
  `6c5a423c-ec7b-4070-9a05-87a8dddd91a1`。
- 兜底会话 `c148a1d6-8cd1-4efb-a797-7d10bbe475aa` 仍然显示
  `CODEX_DEMO_FORCED_FAILURE`、`scripted_mock`、`兜底已恢复`、`Diff 就绪`、
  `预览健康` 和 `模拟部署就绪`。

### P4-1 基线治理清理

P4-1 使仓库治理与当前项目身份保持一致：

- AgentHub 是一个本地单用户智能体编码工作区 / 强演示 MVP，而非
  完整的多人即时通讯协作平台。
- `CodexAdapter`、`ClaudeCodeAdapter` 和 `ScriptedMockAdapter` 都是当前
  的适配器，不得移除或退化。
- 基于兜底的 P0 路径、P1/P2/P3 验证的路径以及 P4-0 真实智能体
  证据均予以保留。
- 生产部署、提供商市场、WebSocket/multiplayer、Docker
  沙箱、外部即时通讯集成、PR 创建、广泛的任意编辑以及
  企业工作流仍被推迟。

### P4-0 完整端到端智能体执行能力审计

P4-0 验证了 AgentHub 能够通过面向浏览器的 API 路径驱动完整的编码智能体执行
流水线：
```text
requirement -> orchestrator plan -> Direct Start -> agent execution -> file mutation -> diff -> preview -> mock deploy
```
使用 Claude Code 默认适配器的真实代理路径已通过：

- 会话：`ebec86df-90bf-47ed-a5f1-b4f3b82a6c84`
- 任务：`7c0fab95-e929-4252-9231-d92c2cc7e2e1`
- TaskRun：`ab038575-a4e4-406c-bfcf-e0ae3ca4a318`
- 适配器：`claude_code`
- 最终状态：`completed`
- 变更文件：`apps/demo/src/App.tsx`
- Diff 制品：`1c53db5d-94ba-4667-af09-c8e5b8a2214f`
- 预览：`51e6c80f-006f-48e5-b1f7-2ecd629de442`
- 预览 URL：`http://127.0.0.1:62044`
- 预览 health/status：`healthy`，`ready`
- 部署：`2b9e1c5e-c936-47c5-bd2a-4b29e243cca1`
- Provider/status：`mock`，`ready`

兜底路径已通过：

- 会话：`52836726-e895-43da-964a-3244a30d5948`
- 任务：`773483a0-e026-4aa0-b816-0cb4decdfaf4`
- 失败的 Codex TaskRun：`608113c6-a5f8-4df1-9742-8db1db7934de`
- 失败错误码：`CODEX_DEMO_FORCED_FAILURE`
- 兜底 TaskRun：`9662bb80-70dc-4d47-b82d-4ea1c9effb89`
- 适配器：`scripted_mock`
- 最终状态：`completed`
- Diff 制品：`8007fd66-6f6b-4e9d-b61f-abf946cc9a08`
- 预览：`38b3e7c9-2ec6-4fb0-ad7f-f4fc142f6b64`
- 预览 URL：`http://127.0.0.1:62136`
- 预览健康检查：`healthy`
- 部署：`fd5ca6bb-ae1c-4ce3-b0f2-dfd50e04eb3f`
- Provider/status：`mock`，`ready`

同一真实代理会话中的跟进路径已通过：

- 请求：`把按钮文案改成 Sign in`
- 跟进任务：`81aeff37-608c-4708-a8c1-284e73b6ba2d`
- 跟进 TaskRun：`62c9ff50-7772-4000-9fe5-77a6596d7f92`
- 适配器：`claude_code`
- 最终状态：`completed`
- Diff 制品：`a76d098b-f16c-4823-ac40-22062515edf0`
- 预览：`b850d9c8-5e3f-4862-96aa-6cd0cb5942fa`
- 预览 URL：`http://127.0.0.1:62341`
- 预览健康检查：`healthy`

浏览器自动化注意事项：本次审计打开了被审计的会话 URL，但完整的自动化浏览器按钮点击被阻止，因为未安装 Playwright 且 Chrome AppleScript 控制遇到了 macOS Apple Events 权限提示。因此，审计验证了面向浏览器的 API 执行路径，并如实记录了浏览器点击自动化的缺口。

## P0 基线

P0 已完成，且可供评审演示的路径仍基于兜底方案：
```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```
在进行 P1 变更时保留此路径。

## P1 状态

### P1-10 冻结演示基线

P1 已冻结为稳定的本地演示基线。

冻结路径：
```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```
验收清单位于 `docs/p1-acceptance-checklist.md`。

冻结基线证据为 P1-9 冷启动演练：

- 会话：`666fa20b-6f54-4342-b844-39594b903da3`
- TaskRun：`b1882cda-47f6-4035-b12d-ba3d72d67939`
- 差异制品：`c832b249-c2c3-444c-ac97-6b3e811e5c70`
- 预览：`b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- 部署：`d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- Provider/status：`mock`、`ready`

兜底路径仍然可用：
```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```
### P1-6 已验证

P1-6 已验证：

- HTTP 直接启动
- 真实的 Codex 文件变更
- 差异制品生成

已验证路径：
```text
HTTP Direct Start -> real Codex file mutation -> diff artifact
```
### P1-7 通过后端 API 验证

P1-7 通过后端 API 验证：

- 真实 Codex 直接启动
- 真实 diff 制品
- 健康的 Vite 预览
- 模拟部署

验证路径：
```text
real Codex Direct Start -> real diff artifact -> healthy Vite preview -> mock deploy
```
P1-7 证据：

- TaskRun：`fa23fb4a-6506-4b0e-a608-3197356d0628`
- Diff 制品：`782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- 预览：`877daf34-cabe-4ddf-8726-94677ba18831`
- 预览 URL：`http://127.0.0.1:53089`
- 部署：`9ba427d9-1ea8-454a-8890-e243075fcec7`
- Provider/status：`mock`、`ready`

### P1-8 通过浏览器 UI 验证

P1-8 通过浏览器 UI 交互验证了 diff 后的制品路径：

- 真实的 Codex Direct Start 运行在 UI 中仍然可见。
- 持久化的真实 diff 制品以 diff 卡片形式呈现。
- 从 UI 启动了预览。
- 健康的 Vite 预览在右侧 iframe 面板中打开。
- 从 UI 创建了模拟部署卡片。
- 重新加载后，diff、预览和部署卡片仍然可见。

已验证路径：
```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```
P1-8 证据：

- TaskRun：`fa23fb4a-6506-4b0e-a608-3197356d0628`
- Diff 制品：`782e16f4-36b5-46f3-86cf-42c3fb6119e9`
- UI 创建的预览：`810324d7-2ba9-47e6-b676-7391e87cb131`
- UI 创建的预览 URL：`http://127.0.0.1:64067`
- UI 创建的部署：`58c7812c-31f8-49ee-8b08-28d38264cd87`
- Provider/status：`mock`、`ready`

### P1-9 全新启动演示排练

P1-9 验证了从全新服务器启动开始的浏览器 UI 演示路径：

- 后端使用 `pnpm dev:api` 启动。
- 前端使用 `pnpm dev:web` 启动。
- 从 UI 创建了一个新会话。
- 从 UI 发送了固定的演示请求。
- 直接 UI 启动调用了真实的 Codex TaskRun。
- 真实的 Codex 完成并生成了真实的 diff 制品。
- 从 UI 启动预览，并在右侧 iframe 面板中打开。
- 从 UI 创建了模拟部署卡片。
- 重新加载后，diff、预览和部署卡片仍然可见。

已验证路径：
```text
clean start -> real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```
P1-9 证据：

- 会话：`666fa20b-6f54-4342-b844-39594b903da3`
- 任务：`c90396af-1b9f-42f4-a6dd-9daa4f3913f6`
- TaskRun：`b1882cda-47f6-4035-b12d-ba3d72d67939`
- 基础引用：`ad9136f91fe9776c33e839359a2203d64fbbf322`
- 头引用：`ad9136f91fe9776c33e839359a2203d64fbbf322+worktree`
- 差异：`8a0155a6-b865-4cee-987e-82d773b9f20e`
- 差异制品：`c832b249-c2c3-444c-ac97-6b3e811e5c70`
- 变更文件：`apps/demo/src/App.tsx`
- 差异统计：1 个文件变更，14 处新增，4 处删除
- 预览：`b363eb09-7251-4b8e-a5b4-3c59775b58b7`
- 预览制品：`f93ebc25-b8c7-47e9-ac11-aeee777c604e`
- 预览 URL：`http://127.0.0.1:51763`
- 部署：`d97e447a-c8d0-41b7-95f8-e40008d83eb0`
- 部署制品：`d85e9bcf-9b92-4c3c-958a-352f855e59a9`
- Provider/status：`mock`, `ready`

### P1-11 干净状态与兜底排练

P1-11 通过非破坏性的干净状态排练，弥补了主要的 P1 演示就绪差距。

Backup/reset 方法：

- 将活动的 SQLite 数据库移至
  `/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`。
- 在以下位置记录了排练前的 Git 工作树注册表和目录清单：
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-list-before.txt`
  - `/tmp/agenthub-p1-11-backup-20260517-095901/worktree-dirs-before.txt`
- 保留现有的 `.worktrees` 检出，以避免干扰 Git
  已注册的工作树元数据。
- 使用 `pnpm db:init` 重新初始化了一个干净的 SQLite 数据库。
- 在排练期间，从干净的数据库创建了全新的会话级工作树。

恢复说明：先停止开发服务器，如果需要保留当前的
`apps/api/data/agenthub.sqlite3`，请备份，然后将
`/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`
移回 `apps/api/data/agenthub.sqlite3`。

干净状态的直接 Codex 排练已通过：
```text
clean SQLite -> fresh session worktree -> real Codex Direct Start -> real diff -> healthy Vite preview -> mock deploy card
```
干净状态证据：

- 会话：`72668a90-74a0-45c6-a0c4-98e8cfa54c27`
- 会话工作树：
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/72668a90-74a0-45c6-a0c4-98e8cfa54c27`
- 任务：`7e0a4e97-1b80-404d-bcab-4616418627e3`
- 任务运行：`4c92132f-3c89-47cc-b8a4-3f1395825c39`
- 适配器：`codex`
- 最终任务运行状态：`completed`
- 错误 code/message：无
- 基础引用：`abdcd88e200ce8c39f50ed38f244d40cb52295bb`
- 头引用：`abdcd88e200ce8c39f50ed38f244d40cb52295bb+worktree`
- 差异：`bb45131e-42f8-47d7-88eb-c8126d694b0a`
- 差异制品：`243ce682-748b-42ad-9354-dd8eed1f3e67`
- 变更文件：`apps/demo/src/App.tsx`
- 差异统计：1 个文件变更，15 处新增，4 处删除
- 预览：`a30d07e2-470c-4614-a864-c21ac0b52363`
- 预览制品：`4b3475ad-0d1f-4980-ab80-18abb50492fd`
- 预览 URL：`http://127.0.0.1:58634`
- 预览 health/status：`healthy`，`ready`
- 部署：`448b7d91-5064-43c2-a849-3e89634e14bd`
- 部署制品：`717d28cc-eb3e-47cb-9950-cee1985ea798`
- Provider/environment/status：`mock`，`preview`，`ready`

手动强制失败兜底演练通过：
```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```
兜底证据：

- 会话：`695287ed-2967-4360-8520-a5fdc1be46e3`
- 会话工作树：
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/695287ed-2967-4360-8520-a5fdc1be46e3`
- 任务：`1a790664-c817-42eb-a953-d7c0f11cccb0`
- 失败的 Codex TaskRun：`1b50d047-0c08-4ff2-a4d7-12412b36f786`
- 失败运行错误码：`CODEX_DEMO_FORCED_FAILURE`
- 兜底 TaskRun：`c35d52f5-bf27-4656-aee1-b0321eb2bd96`
- 兜底适配器：`scripted_mock`
- 最终兜底 TaskRun 状态：`completed`
- 差异：`8a8f05bf-6559-44f4-bafc-fb87881c4750`
- 差异制品：`91b6c898-bf2b-4c0c-b44b-f6a236a72ef0`
- 变更文件：`apps/demo/src/App.tsx`
- 差异统计：1 个文件变更，11 处新增，4 处删除
- 预览：`e1be7c11-1cc7-42f9-8441-62c7eb0a1b92`
- 预览制品：`4ed1465f-f887-4680-b9a1-6893e593468d`
- 预览 URL：`http://127.0.0.1:59152`
- 预览 health/status：`healthy`、`ready`
- 部署：`cb8c7f95-42f7-4213-8273-4201500bf8b3`
- 部署制品：`43e15df7-5fb4-4711-85b6-94c485b0b4cb`
- Provider/environment/status：`mock`、`preview`、`ready`

重新加载后，失败的 Codex 运行、兜底运行、差异、预览和部署卡片在浏览器 UI 中均保持可见。

### P1 最终冻结审查

最终冻结审查确认：

- P1-11 已在 `faca556` 提交。
- 当前没有标签指向 P1-11 HEAD。
- README、演示脚本、项目状态、变更日志和 P1 检查清单在 P1 直接 Codex 路径和基于兜底的 P0 路径上保持一致。
- 自然语言二次变更编排仍是一个注意事项。
- 审批卡片 UI 不在冻结的 P1 判定路径内。
- 生产部署仍不在范围内。
- 在 P1-11 期间观察到与会话日期格式相关的特定区域开发水合警告，但未阻塞干净状态或兜底预演。

## P2 状态

### P2-1 区域水合警告已修复

P2-1 将工作区外壳和预览卡片中的运行时区域时间戳渲染替换为确定性紧凑格式。手动重新加载验证确认之前特定区域的水合覆盖层未出现。

### P2-2 审批卡片 UI/Rehearsal 已验证

P2-2 暴露了等待中 TaskRun 上现有的 P0 审批请求负载，添加了 approve/deny 端点，并在任务卡片运行控件中渲染了紧凑的审批卡片。

已验证的审批预演状态：

- 会话：`67421999-3b16-44c4-ade3-98cb31331549`
- 已审批 TaskRun：`5653e8f9-0057-478f-913c-ac25b4484216`
- 拒绝预演 TaskRun：`54bde1de-b9f7-4f2b-9357-98d51b3675c7`
- 渲染的审批类型：`product_confirmation`、`security_approval`

手动浏览器验证确认 `product_confirmation` 审批卡片已渲染，且“审批”操作将运行从 `waiting_approval` 移至 `queued`。`security_approval` 卡片也已渲染；拒绝行为由 backend/API 测试和前端按钮接线测试覆盖。

### P2-3 自然语言二次变更编排已验证

P2-3 在现有会话内为简单的 UI 文本变更请求添加了确定性的后续规划。支持的演示安全示例包括：

- `change the primary button text to Sign in`
- `把按钮文案改成 Sign in`
- `把标题改成 Welcome back`

已验证路径：
```text
initial plan -> fallback run -> first diff/preview -> natural-language follow-up -> follow-up frontend task -> fallback run -> second diff/preview
```
P2-3 演练证据：

- 会话：`d65fc331-39f2-432b-9828-89723b9f3c32`
- 会话工作树：
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/d65fc331-39f2-432b-9828-89723b9f3c32`
- 初始前端任务：`3f7f6f65-9f72-4add-ab0a-c9a944dc3b23`
- 初始兜底 TaskRun：`607ad185-8eb2-4158-8219-e124880e68a7`
- 初始差异制品：`c83c21d5-dad8-4d56-b0b8-cf1bc9de2bc3`
- 初始预览：`511ee0ca-e0dc-4054-8775-e487e81f7303`
- 初始预览健康状态：`healthy`
- 后续请求：`把按钮文案改成 Sign in`
- 后续任务：`3ce6aa3d-97bf-4e16-b85a-33676e62bef2`
- 后续任务标题：`Change primary button text to Sign in`
- 后续任务目标：`primary_action_button_text`
- 后续任务目标文本：`Sign in`
- 后续兜底 TaskRun：`7a4f5763-ebbe-4d51-a207-b36b1fff7091`
- 后续差异制品：`f1ca4318-0b41-48a8-9b27-acb957448734`
- 后续预览：`551aa58f-ab73-49f3-96c2-e6db8994bdd6`
- 后续预览健康状态：`healthy`
- 后续任务总数：4

后续运行复用了同一个会话工作树，并为 `apps/demo/src/App.tsx` 生成了第二个差异制品。第二次变更后的预览刷新已通过后端预览 API 验证，返回了健康的预览。

已知 P2-3 限制：

- 执行演练使用了 `ScriptedMockAdapter` 兜底路径，而非真实的 Codex，以避免此任务期间的配额依赖。
- 第二次变更后的浏览器 iframe 刷新未单独演练。
- 广泛的任意自然语言代码编辑仍不在范围内；P2-3 有意限制为确定性的 button/title 文本变更。

### P2-4 浏览器预览 Iframe 刷新已验证

P2-4 通过浏览器 UI 交互验证了剩余的第二次变更预览缺口。无需更改产品代码。

已验证路径：
```text
browser UI initial task -> ScriptedMockAdapter fallback -> first diff -> Start preview -> iframe at first preview URL -> natural-language follow-up -> ScriptedMockAdapter fallback -> second diff -> Start preview -> iframe refreshed to second preview URL
```
P2-4 浏览器演练证据：

- 会话：`cb653482-c31a-48da-a8ee-31ed8cd367e3`
- 会话工作树：
  `/Users/luotianhang/Desktop/agenthub/.worktrees/0474f8b8-499e-4117-afab-c780bd562446/cb653482-c31a-48da-a8ee-31ed8cd367e3`
- 初始前端任务：`5f2c26c2-6511-4b8f-b359-b9de5c9e5a50`
- 初始兜底 TaskRun：`cfeff131-8cbf-4bcc-95b9-1aa84dbf5130`
- 初始差异制品：`737085ee-7b73-4715-8303-df64b3a14132`
- 初始预览：`c077ba2d-7bd4-4c49-8e0c-313e2ecd641c`
- 初始预览 URL：`http://127.0.0.1:61087`
- 初始预览健康状态：`healthy`
- 后续请求：`把按钮文案改成 Sign in`
- 后续任务：`0f9ff26c-8216-4489-b71a-3628c1a7ab7a`
- 后续兜底 TaskRun：`f8d78651-5347-43de-8553-12b29c8c3647`
- 后续差异制品：`b48b3b33-feb2-4313-805d-89811a5cb51c`
- 后续预览：`44ea9495-04b5-419a-ba64-0701eaa83ec8`
- 后续预览 URL：`http://127.0.0.1:61292`
- 后续预览健康状态：`healthy`

右侧预览面板从初始 iframe URL
`http://127.0.0.1:61087` 变更为后续 iframe URL
`http://127.0.0.1:61292`。应用内浏览器无法直接检查跨域 iframe
DOM，因此通过截图验证了可见面板的刷新，并通过将 `http://127.0.0.1:61292` 作为
顶级页面打开来验证后续预览内容，其中 DOM 和截图显示了 `Sign in` 按钮。

已知 P2-4 限制：

- P2-4 执行部分未使用真实 Codex；演练使用了可靠的强制失败加 `ScriptedMockAdapter` 兜底路径。
- 浏览器验证确认了 iframe URL 和可见面板刷新，但当前应用内浏览器运行时不支持对跨域 iframe 进行直接 DOM 检查。

### P2-5 新增 GitHub Actions CI

P2-5 为拉取请求和推送新增了一个最小化的 GitHub Actions 工作流。该工作流镜像了重复的本地验证路径：
```text
pnpm install --frozen-lockfile -> Python .venv API dependency install -> pnpm check -> pnpm test -> git diff --check
```
CI 使用：

- Node.js 22
- pnpm 10.33.4，与 `package.json` 匹配
- Python 3.11
- 现有的仓库脚本，包括基于 `.venv/bin/python` 的 API 检查
  和测试包装器

未添加任何应用代码、测试行为、部署、Docker 或生产发布工作流。

### 新增最小化 Claude Code 适配器

后端现在包含一个最小化的 `ClaudeCodeAdapter` 运行时选项，位于现有适配器契约之后。它是 `CodexAdapter` 的兄弟组件，使用子进程 `cwd` 进行会话工作区隔离，并将 Claude Code `stream-json` 的标准输出映射为规范化的 AgentHub 事件。

当前已验证状态：

- 假运行器测试涵盖了命令构建、增量流式 JSON 事件解析、持久化 `TaskRunEvent` 序列排序、缺失 CLI、需要认证、使用限制、解析错误、启动超时和中断规范化。P2-7 增加了对真实 Claude `stream_event` text-delta 映射和 thinking-delta 过滤的覆盖。
- 后端适配器分发支持 `adapterType: claude_code`。
- 防护措施允许有界的 `claude --print --output-format stream-json` 命令族，使其能够通过与 Codex CLI 相同的命令策略路径进行评估。

当前限制：

- P2-7 仅运行了一次明确批准的真实 Claude Code 变更冒烟测试。更广泛的提示词、浏览器 UI 接线、认证失败文本和使用限制文本尚未验证。
- `ScriptedMockAdapter` 仍然是可靠性兜底方案，P1 真实 Codex 路径保持不变。

### P2-7 真实 Claude Code 冒烟测试已验证

P2-7 在分离的一次性会话工作区中运行了一次有界的真实 Claude Code 适配器冒烟测试：
```text
ClaudeCodeAdapter -> real Claude CLI -> stream-json events -> file mutation -> completed TaskRun -> diff artifact
```
一次性工作树：
```text
/Users/luotianhang/Desktop/agenthub/.worktrees/claude-smoke-96d46af7-dc74-4d71-a062-c9be42cd1332
```
第一次尝试在变异前发现了一个本地适配器 bug：

- 失败的任务运行：`c66f1f86-2407-487a-b18f-cf01abd3a7f3`
- 错误码：`CLAUDE_CODE_EXIT_ERROR`
- 错误消息：
  `Error: When using --print, --output-format=stream-json requires --verbose`

适配器命令已更新，加入了 `--verbose`，第二次有界冒烟测试成功：

- 会话：`4cf32311-1a9b-4eda-9ec3-ab0d010691fc`
- 任务：`a5557a9a-99de-4962-9d25-86ed548ea7ca`
- 任务运行：`095ae634-c188-4ffc-a502-53a500d20e14`
- 适配器运行：`claude-code-94cc6074-f15d-4290-b050-c2383363f44d`
- 最终状态：`completed`
- 基础引用：`0066dea6c7f6a235cb2c2e0361624a1116d66dad`
- 头引用：`0066dea6c7f6a235cb2c2e0361624a1116d66dad+worktree`
- 差异制品：`95bb1d0b-12a3-4a0e-be3e-c07cf1bf79d4`
- 差异：`9f69bc39-6b32-42ca-8a86-cf9fbfa62343`
- 变更文件：`apps/demo/src/App.tsx`
- 差异统计：1 个文件变更，1 处新增，1 处删除

在一次性工作区中直接执行 git diff 显示，主按钮文本从 `Continue` 变更为 `Claude smoke`。

已知的 P2-7 限制：

- 这是直接的后端冒烟测试，而非完整的浏览器 UI 流程。
- 仅验证了一条微小的变异指令。
- Claude `stream-json` 包含冗长的底层 `stream_event` 记录；适配器现在能映射文本差异并过滤思考差异，但更广泛的流事件形态仍未验证。
- 认证失败和使用限制的真实输出仍未验证。

### P2-8 Claude Code 直接启动选择已添加

P2-8 为常规演示执行增加了一条基于环境变量的最小化适配器选择路径。直接启动默认仍使用已分配代理所配置的适配器，但设置：
```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code
```
导致 frontend/backend 编码任务（其种子适配器为 `codex`）创建带有 `adapterType: claude_code` 的新 TaskRun。显式适配器选择仍然有效，因此强制的 Codex 失败、重试历史记录以及使用 ScriptedMockAdapter 的重试兜底保持其现有行为。非代码代理（包括 `scripted_mock` QA 路径）不受此环境变量影响。

已验证状态：

- 服务测试覆盖了前端任务的默认 Claude 选择。
- 服务测试覆盖了显式 Codex 保留其请求的适配器。
- 服务测试覆盖了 ScriptedMockAdapter 保留非代码兜底行为。
- 服务测试覆盖了无效环境变量值会大声失败。

已知 P2-8 限制：

- P2-8 未运行新的真实 Claude 变更；P2-7 仍然是真实 Claude 的冒烟证据。
- 这是一个 env/config 开关，而非提供商市场或 UI 选择器。

### P2-9 Claude 默认适配器模式已记录

P2-9 记录了如何以 Claude Code 作为默认编码适配器启动 API：
```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api
```
最小化直接启动验证使用了内存中的 API 演练，而非真实的 Claude 执行。在设置环境变量后，`POST /tasks/{task_id}/runs` 创建了一个带有 `adapterType: claude_code` 的排队 TaskRun。

证据：

- 会话：`1c662ede-d0be-4349-8c86-20f49be6fb53`
- 任务：`c28cda5b-67c7-44a8-bd2b-e43ebbc64217`
- TaskRun：`a1c191ea-1414-4746-95ca-d6c51b36b4f8`
- 适配器类型：`claude_code`
- 状态：`queued`
- 排队事件负载：`{"adapterType":"claude_code","state":"queued"}`

已知的 P2-9 限制：

- P2-9 未运行真实的 Claude 变更。
- 通过 diff/preview/deploy 的完整浏览器 UI Claude 默认执行仍未演练。
- P2-7 仍然是真实的 Claude 变更和差异制品证据。

### P2 最终冻结审查

P2 最终冻结审查确认文档与当前 P2 基线保持一致：

- P2 稳定化工作已完成至 P2-9。
- P2 验证在 `pnpm check`、`pnpm test` 和 `git diff --check` 下保持绿色。
- P1 真实 Codex 演示路径和基于兜底的 P0 演示路径保持不变。
- Claude Code 默认模式已通过 `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` 记录。
- P2 注意事项仍然可见：
  - 通过 diff/preview/deploy 的完整浏览器 UI Claude 默认执行未演练
  - 真实的 Claude 认证失败和使用限制输出部分未验证
  - 广泛的任意自然语言编辑仍不在范围内
  - 生产部署仍不在范围内

在 P2 最终冻结审查期间，未更改任何应用代码、适配器代码、后端 API 行为、前端行为或测试。

### P18 记忆与指令控制平面

P18 添加了 AgentHub 规范记忆，作为 Planner LLM、Claude Code、Codex、审查代理和未来编码代理的可审计事实来源。

当前 P18 基线：

- 管理带有确定性哈希的 `AGENTS.md` / `CLAUDE.md` 桥接。
- 会话级别的 `memorySnapshotId` 记录在规划器证据、TaskRun 指标、规范上下文和任务轨迹中。
- 规范记忆项模型，具有 active、pending_review、warm、archived、rejected 和 deleted 状态。
- 明确的用户记忆写入策略和提示注入防护。
- 具有范围、目标、角色、状态、评分和过时记忆过滤的 Keyword/BM25-style 检索。
- 将外部 AGENTS/CLAUDE 扫描为带有冲突检测的待处理建议。
- 用于审查和管理记忆状态的 `/settings/memory` 页面。

P18 将目标注册表、PlanValidator、护栏、运行时配置和调度器作为硬安全边界。记忆指导代理行为，但不授予权限。

### P19 规划器路由加固

P19 正在进行中，已通过新颖应用回归集完成了路由加固核心。

当前 P19 基线：

- API 规划器提供者和 Claude CLI 规划器使用一个规范规划器提示合约。
- 规范提示要求安全的软件构建/实现/创建/开发/修改请求返回带有完整 `planDraft` 的 `task_plan`。
- 正常的问候和能力问题保持为 `assistant_reply`，不会创建任务。
- 澄清、拒绝和需要批准的结果保持不执行。
- 被错误分类为 `assistant_reply` 的安全外部前端编码请求会回退到经过审计的确定性前端任务。
- 回退任务在 `plannerEvidence` 中记录 `plannerSource=fallback`、`fallbackReason`、`llmOutcomeType`、提供者元数据、验证结果、安全错误摘要和创建的任务 ID。
- 在创建任何确定性回退任务之前，无效的 LLM `task_plan` 输出会记录验证失败证据。
- 诸如登录、待办事项、笔记、迷你 CRM 和 Breakout 等固定模块是回归基线，而非能力限制。
- P18c 库管理应用路由现在会在存在准备好的外部前端目标时创建一个目标范围的前端任务。
- 缺失的 desktop/external 目标会要求设置目标，而不是写入任意主机路径。

P19 尚未完成最终冻结审查。P18c 实时执行保持暂停，直到 P19 冻结证据确认规划器路由不再是阻塞因素。

### P24 部署提供者状态卡片

P24 正在进行中。已完成的工作：

- P24-1 为本地暂存、手动外部移交和不可用的外部静态提供者添加了部署提供者注册表。
- P24-2 为就绪、阻塞、失败和移交结果添加了诚实的部署状态证据，而不声称第三方部署成功。
- P24-3 升级了部署卡片 UI，以显示提供者类型、环境、源 preview/diff/review 引用、日志、状态历史记录，以及仅在存在 URL 时的打开 URL 操作。
- P24-4 允许部署卡片通过安全的 provider/source/log 元数据和类似机密的文本编辑参与制品上下文后续操作。
- P24-5 冻结审查通过了针对本地暂存部署卡片和阻塞的 Vercel 卡片的有限演练。第三方提供者执行仍被推迟；外部卡片仅为阻塞或移交证据。

P24 在冻结提交后即可冻结。

### P25 上下文控制与二次交互
P25 正在进行中。P25-1 为显式的 `contextItems`、遗留的选中制品上下文以及引用的消息上下文添加了后端上下文条目规范化。在后续规划器交接集成之前，上下文条目现在具有确定性的限制，并对受保护路径、类密钥字符串、选中文本、注释和元数据进行编辑。

P25-2 将规范化的上下文条目连接到会话上下文包、规范/提供者可见上下文、规划器证据和任务追踪。上下文感知的后续操作现在携带可审计的 `contextHandoff` 元数据，但不会授予任何新的执行权限。

P25-3 将编辑器升级为紧凑的多条目上下文托盘。用户现在可以暂存多个 message/artifact/deployment 上下文条目、移除它们、重新排序、清空托盘，并发送包含规范化 `contextItems` 及遗留兼容性字段的有效载荷。

P25-4 为制品和部署卡片添加了次要交互操作：询问此项、修订此项以及发送至 Agent。这些操作仅暂存上下文并预填编辑器；带上下文的纯聊天仍会产生聊天回复而不触发 TaskRun，而可执行的后续操作在发送后继续通过常规的路由器/规划器路径。

P25-5 冻结审查通过了结合部署、差异、工作台制品版本和引用消息上下文的有限演练。P25 在冻结提交后即可准备冻结。

### 运行时设置提供者覆盖保存修复

运行时设置现在允许用户将内置角色配置文件（例如 `Frontend Agent`）与选定的运行时编码提供者（例如 `Claude Code CLI`）结合使用。后端验证将配置文件视为 role/capability 模板，并使用选定的提供者作为运行时 adapter/provider 执行的权威来源。选定适配器与选定提供者不匹配的有效载荷仍然无效。

### 通用新项目可靠执行路径

截至 2026-06-10，AgentHub 增加了通用 selected-folder new project runtime：

- 用户可在运行设置中选择一个空文件夹并新建全栈项目。
- 后端会在该目录中创建通用 Vite React TS frontend、FastAPI backend、API contract、README 和 AgentHub metadata。
- 新项目会注册为 frontend/backend external targets，并绑定到当前 Session 的 active targets。
- orchestrator 对已绑定的新项目目标优先生成 frontend/backend coding tasks；番茄钟、Todo、读书笔记等请求共享同一路由，不依赖业务名特化。
- 新项目 TaskRun 使用现有 durable run engine：session queue、target lock、provider assignment、diagnostics、retry 和 terminal lock release 保持同一套机制。

仍然保持的边界：这不是多用户 IM 平台、Docker sandbox、WebSocket、provider marketplace 或生产部署矩阵；依赖安装和网络访问仍按审批/命令策略处理。
