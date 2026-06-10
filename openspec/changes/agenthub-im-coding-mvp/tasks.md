## 1. 第 1 周 - 基础、演示仓库与可行性

- [x] 1.1 搭建固定栈前端和后端应用。
  - 目标：建立 Next.js App Router 产品 UI 和 FastAPI 后端基线。
  - 范围：TypeScript、Tailwind CSS、shadcn/ui 配置、Python FastAPI 应用、Pydantic 模式、SQLModel 配置、SQLite 本地数据库配置。
  - 影响模块：前端应用外壳、后端应用、数据库配置、开发者脚本。
  - 验收标准：前端和后端在本地启动；前端可调用后端健康检查端点；通过 SQLModel 初始化 SQLite。
  - 测试或验证方法：运行本地开发命令并执行健康检查；验证数据库文件和初始模式创建。
  - 明确非目标：无生产部署、无认证提供者集成、无 Postgres 要求、无 Alembic 要求（除非已可用）。

- [x] 1.2 添加 AGENTS.md，包含 P0 实现护栏。
  - 目标：为未来的编码代理提供一个本地指令文件，以保留 MVP 范围和安全性规则。
  - 范围：固定技术栈、Vite React 演示应用边界、会话级工作树规则、本地 Codex CLI 规则、无 P0 Docker/WebSocket/marketplaces/multi-user/external IM、受保护路径、命令白名单、演示成功标准。
  - 影响模块：仓库根目录文档、未来代理工作流。
  - 验收标准：AGENTS.md 存在并明确说明 P0/P1/P2 边界和实现约束。
  - 测试或验证方法：对照此 OpenSpec 设计和非目标进行人工审查。
  - 明确非目标：无实现代码、无广泛流程手册、无企业策略文档。

- [x] 1.3 实现 P0 SQLModel 模式并添加种子记录。
  - 目标：仅持久化所需的 P0 实体，并将 TaskRunEvent 作为唯一的支持实体。
  - 范围：User、Workspace、Session、Message、Agent、Task、TaskRun、TaskRunEvent、Artifact、Diff、Preview、Deployment 模型；TaskRun `baseRef`/`headRef`；Preview command/process/status 字段；种子数据包含一个演示用户、工作区以及已启用的 orchestrator/frontend/backend/qa 个 Agent。
  - 影响模块：后端模型、模式初始化、种子脚本、仓库层。
  - 验收标准：规范中的所有必填字段均已存在；TaskRunEvent 已包含；未引入无关的 P0 领域实体；种子 Agent 和工作区可查询。
  - 测试或验证方法：运行模式初始化，并执行一个 model/repository 冒烟测试，该测试需创建会话、消息、任务、任务运行、任务运行事件和制品。
  - 明确非目标：不包含企业级 RBAC、多租户管理、审计后端、计费、提供商市场模式或 Alembic 迁移工作流（除非已存在）。

- [x] 1.4 添加 Vite React 演示仓库和设置时依赖安装路径。
  - 目标：为 5 分钟演示提供固定的、由智能体修改过的演示应用。
  - 范围：Vite React 应用、用于登录页面和按钮文本更改的确定性演示文件、安装依赖项的设置脚本、指向演示根目录的工作区种子。
  - 影响模块：演示仓库资源、设置脚本、种子配置、README 草案。
  - 验收标准：设置后演示应用可在本地启动；`node_modules` 仅通过设置时安装存在；脚本化兜底具有已知的可修改文件。
  - 测试或验证方法：运行设置命令，手动运行 `pnpm dev --host 127.0.0.1 --port <port>`，验证基线页面是否加载。
  - 明确非目标：无 Next.js 演示应用、无通用多框架预览运行器、无智能体执行期间的依赖项安装。

- [x] 1.5 在会话工作区内运行 Codex CLI 可行性验证
  - 目标：确认 P0 CodexAdapter 能够在 git 工作区内通过本地 CLI 调用方式运行。
  - 范围：手动或脚本化验证，创建会话级工作区，使用简短指令调用 Codex CLI，观察进程行为、认证假设、stdout/stderr、退出码、中断可行性、输出格式及失败模式。
  - 影响模块：适配器设计说明、工作区服务假设、AGENTS.md 或 docs/adapter-notes.md.
  - 验收标准：在任务 2.4 开始前，记录发现的 Codex CLI 调用方式；文档需包含精确的命令格式、工作目录假设、所需认证或登录状态、stdout/stderr 行为、退出码行为、中断行为、已知失败模式及兜底触发条件；文档存储于 AGENTS.md 或 docs/adapter-notes.md.
  - 测试或验证方法：运行一次性工作区实验，记录命令、当前工作目录、预期 output/events 及错误映射说明。
  - 明确非目标：不涉及 Codex API/cloud 封装器、不进行生产级适配器加固、不开发第二个真实适配器。

- [x] 1.6 构建 workspace/session UI/API，支持会话级工作区创建。
  - 目标：让用户创建并切换至少三个会话，每个会话拥有独立的工作区。
  - 范围：工作区读取端点、会话 CRUD 端点、确定性会话工作区创建、会话列表 UI、选中会话状态、`lastMessageAt` 更新。
  - 影响模块：前端会话侧边栏、后端 workspace/session API、工作区服务、持久化层。
  - 验收标准：用户可创建三个会话并切换；每个会话拥有唯一工作区路径；会话中的 TaskRun 可复用该路径。
  - 测试或验证方法：针对会话创建和唯一工作区路径的 API 测试；通过三个会话进行手动 UI 验证。
  - 明确非目标：P0 阶段不涉及任务运行级工作区策略、无多用户协同、无共享功能、无外部 IM 导入。

- [x] 1.7 构建即时通讯风格聊天流、持久化消息及 SSE 重放基础。
  - 目标：渲染会话聊天，并创建用于可恢复状态更新的后端事件路径。
  - 范围：消息 create/list API、Markdown 显示、发送者渲染、SSE 端点、TaskRunEvent append/query API、序列处理。
  - 影响模块：前端聊天视图、后端消息 API、TaskRunEvent 仓库、SSE 事件服务。
  - 验收标准：消息在重新加载后持久化；TaskRunEvent 可按序列追加和查询；前端可订阅 SSE。
  - 测试或验证方法：对消息和 TaskRunEvent 持久化进行后端测试；通过发送消息并重新加载进行手动 UI 验证。
  - 明确非目标：无 WebSocket、打字指示器、多人协作、外部聊天集成或事件总线基础设施。

- [x] 1.8 实现 @mention 解析与简单编排器规划。
  - 目标：路由 P0 提及，并为演示请求创建 2-4 个可见任务。
  - 范围：针对 `@orchestrator`、`@frontend`、`@backend`、`@qa` 的提及解析器；确定性规划模板；角色-代理分配；任务卡片；简单的串行依赖关系及至多一个并行组。
  - 影响模块：后端聊天命令解析器、编排器服务、Agent/Task 仓库、前端任务卡片。
  - 验收标准：`@orchestrator build a login page for the demo app` 创建 2-4 个任务，并分配角色代理和可见状态。
  - 测试或验证方法：提及解析与编排器规划的单元测试；手动聊天验证。
  - 明确非目标：无任意 DAG 构建器、LangGraph/CrewAI 依赖、递归代理树、自主团队、提供商市场发现。

## 2. 第 2 周 - 执行、事件、差异、控制与预览骨架

- [x] 2.1 实现适配器接口、AdapterCapabilities 和事件持久化。
  - 目标：提供共享的适配器契约，并保证事件在 SSE 投递前完成持久化。
  - 范围：`getCapabilities`、`createRun`、`streamEvents`、`interrupt`、`approve`、`collectArtifacts`、`cleanup`；AdapterCapabilities 模型；标准化事件映射器；发送前的 TaskRunEvent 持久化。
  - 影响模块：后端适配器层、TaskRunEvent 服务、SSE 事件服务、编排器服务。
  - 验收标准：两个 P0 适配器均暴露能力；标准化事件创建 TaskRunEvent 记录；SSE 能够投递已持久化的事件。
  - 测试或验证方法：使用模拟适配器事件和序列断言的单元测试。
  - 明确非目标：不涉及 ClaudeCodeAdapter、HumanAgentAdapter、WebSocket、提供商市场或外部事件总线。

- [x] 2.2 实现权限护栏和 ApprovalRequestPayload。
  - 目标：强制执行 P0 命令、路径、网络和审批规则。
  - 范围：命令白名单、受保护路径（包括 `node_modules`）、默认网络关闭、`ApprovalRequestPayload`、审批卡片事件、Task/TaskRun `waiting_approval` 状态、approve/deny 端点。
  - 影响模块：后端护栏服务、适配器服务、审批 UI、TaskRun 状态处理。
  - 验收标准：高风险操作发出审批负载；待审批状态将 TaskRun 置于 `waiting_approval`；未列入白名单的命令和受保护路径被阻止或需要审批。
  - 测试或验证方法：针对 command/path 策略和审批负载的单元测试；手动审批延续验证。
  - 明确非目标：无企业级 RBAC、策略管理控制台、任意 shell、完全主机访问、无限制后台进程或未经审查的部署。

- [x] 2.3 实现 ScriptedMockAdapter 的真实变更兜底。
  - 目标：提供一个稳定的兜底适配器，能够真实修改 Vite React 演示仓库。
  - 范围：用于登录页面和按钮文本变更的受控脚本、逼真的进度事件、success/failure/interruption/approval 模拟、工作区范围的文件变更、护栏合规。
  - 影响模块：后端适配器层、演示脚本、SSE 事件服务、护栏服务。
  - 验收标准：ScriptedMockAdapter 能够完成登录页面演示并创建真实的文件变更；不访问外部网络或绕过允许列表。
  - 测试或验证方法：运行脚本化兜底的集成测试，并通过 Git CLI 验证变更的文件；手动故障恢复演示。
  - 明确非目标：无仅伪造的消息响应、无任意 shell 执行、无外部提供商调用。

- [x] 2.4 实现 CodexAdapter 本地 CLI 快乐路径与标准化错误
  - 目标：使用本地 CLI 调用添加 P0 真实编码适配器。
  - 范围：阅读来自 AGENTS.md 或 docs/adapter-notes.md 的 Codex CLI 可行性说明，然后在 Session 工作区内实现 Codex CLI 进程启动、指令传递、事件适配、中断尝试、制品收集钩子、错误映射到 TaskRun 字段。
  - 影响模块：后端适配器层、TaskRun 服务、TaskRunEvent 服务、护栏集成。
  - 验收标准：至少有一个任务能通过 CodexAdapter 本地 CLI 执行并产生真实文件修改；失败会创建标准化错误 code/message 并允许重试。
  - 测试或验证方法：本地集成测试或针对 Vite React 演示仓库手动运行；强制失败验证兜底路径。
  - 明确非目标：无 Codex API/cloud 包装器、无 ClaudeCodeAdapter、无 HumanAgentAdapter、无复杂提供者配置。

- [x] 2.5 实现 TaskRun 生命周期、中断、重试以及带兜底的重试。
  - 目标：在保留运行历史的前提下，使执行过程可通过聊天进行控制。
  - 范围：更新 TaskRun 状态、运行创建、状态转换、中断 endpoint/UI、重试 endpoint/UI、带 ScriptedMockAdapter 的重试路径、先前运行的可见性。
  - 涉及的模块：后端任务运行服务、编排器服务、前端任务控件、SSE 事件流。
  - 验收标准：用户可以中断正在运行的任务；用户可以重试失败或中断的任务；重试会创建新的 TaskRun 而不覆盖之前的历史；在 Codex 失败后可以选择兜底方案。
  - 测试或验证方法：后端状态转换测试；在 UI 中进行手动 interrupt/retry/fallback 验证。
  - 明确非目标：不涉及深度递归团队控制、任意 DAG 重新规划 UI、长时间运行的后台代理调度器。

- [x] 2.6 实现真实的 git diff 收集与存储。
  - 目标：将会话工作区的实际变更转化为 Diff 制品。
  - 范围：TaskRun `baseRef`/`headRef`、`git diff -p`、变更文件、统计信息、可选的 `git apply --check`、`node_modules` 排除规则、Artifact 与 Diff 持久化、`artifact.diff.ready` 事件。
  - 影响模块：后端 diff 服务、Artifact/Diff 仓库、适配器制品收集、工作区服务。
  - 验收标准：系统在 Codex 或脚本变更后存储补丁文本、变更文件 JSON、统计信息 JSON 及引用；`node_modules` 不参与 diff 计算。
  - 测试或验证方法：集成测试修改演示仓库文件，并验证存储的 diff 与 Git CLI 输出一致。
  - 明确非目标：不创建 PR，P0 阶段不导出补丁，不构建完整的代码审查系统。

- [x] 2.7 构建差异卡片，包含文件摘要和可展开的 Monaco 审查视图。
  - 目标：让用户能够审查聊天中的真实文件变更。
  - 范围：差异卡片、变更文件列表、补丁摘要、expand/collapse 行为、Monaco 差异编辑器详情视图。
  - 影响模块：前端制品卡片组件、后端制品读取 API。
  - 验收标准：用户可查看变更文件及补丁摘要；展开卡片后通过 Monaco 展示文件级变更。
  - 测试或验证方法：使用示例差异夹具进行组件测试；在 ScriptedMockAdapter 运行后手动验证。
  - 明确非目标：不包含完整 IDE 编辑、任意文件浏览器、内联代码编辑工作流。

- [x] 2.8 实现预览运行器后端骨架。
  - 目标：为 Vite React 预览添加后端进程与持久化基础。
  - 范围：端口分配、固定命令构建、进程 start/stop 骨架、健康检查端点、预览记录字段、`artifact.preview.ready` 事件结构、执行期间不安装依赖。
  - 影响模块：后端预览服务、预览 model/repository、护栏服务、TaskRunEvent 服务。
  - 验收标准：后端能够在会话工作区中启动 `pnpm dev --host 127.0.0.1 --port <port>`（含设置时依赖），并持久化预览状态。
  - 测试或验证方法：针对 Vite React 演示仓库的后端集成测试或手动调用。
  - 明确非目标：第 2 周不涉及预览 UI 打磨、无 Docker 化预览、无多框架运行器、无外部预览共享。

## 3. 第 3 周 - 预览打磨、部署卡片、恢复与演示质量保证

- [x] 3.1 优化预览卡片和右侧面板。
  - 目标：使预览功能可用，并在产品 UI 中达到可演示状态。
  - 范围：预览卡片状态、URL、打开操作、刷新操作、上次检查时间、右侧面板或 iframe、二次变更刷新行为。
  - 影响模块：前端预览 card/panel、后端预览 read/refresh API。
  - 验收标准：用户可以在右侧面板或 iframe 中打开 Vite React 预览；预览能反映同一会话中的第二次小变更。
  - 测试或验证方法：手动执行登录页面变更和按钮文本变更；验证预览健康状态和 iframe 显示。
  - 明确非目标：不新增预览框架支持，不在代理执行期间安装依赖，不提供外部预览共享。

- [x] 3.2 实现带模拟兜底的基础部署卡片。
  - 目标：预览成功后完成演示闭环。
  - 范围：部署记录创建、部署卡片 UI、模拟部署模式、可选单 Vercel 演示部署（若稳定）、真实部署前的审批关卡。
  - 影响模块：后端部署服务、前端部署卡片、审批控件。
  - 验收标准：预览成功后出现部署卡片；当真实部署不可用时，模拟部署记录保持演示路径可用。
  - 测试或验证方法：手动预览到部署卡片验证；强制真实部署不可用验证。
  - 明确非目标：无提供商矩阵、生产部署平台、完整部署矩阵、未经审查的部署、git 推送要求。

- [x] 3.3 实现并演练故障恢复演示流程。
  - 目标：证明演示能够承受 CodexAdapter 故障或中断。
  - 范围：强制 CodexAdapter 故障模式、重试 UI、使用 ScriptedMockAdapter 重试、真实文件变更、差异收集、预览、部署卡片。
  - 影响模块：适配器层、重试控件、TaskRun 错误处理、ScriptedMockAdapter、diff/preview/deploy 服务。
  - 验收标准：用户可在故障或中断后点击重试；ScriptedMockAdapter 完成真实变更文件、差异、预览和部署卡片。
  - 测试或验证方法：手动故障恢复演练以及兜底运行的集成测试。
  - 明确非目标：无通用提供商故障切换市场，无复杂自主恢复规划器。

- [x] 3.4 添加 README 和演示脚本。
  - 目标：使 MVP 可运行且可供评委演示。
  - 范围：本地环境搭建、搭建时依赖安装、frontend/backend 启动命令、数据库种子数据、Vite React 演示仓库设置、成功路径脚本、故障恢复脚本、已知 P0/P1/P2 边界。
  - 影响的模块：README、演示脚本文档、开发者脚本。
  - 验收标准：README 说明如何运行应用并触发演示；演示脚本包含一条成功路径和一条故障恢复路径。
  - 测试或验证方法：仅依据 README 和演示脚本进行全新本地运行测试。
  - 明确非目标：不包含完整的生产部署指南、企业运维手册、市场文档。

- [x] 3.5 最终 P0 验收检查清单与范围防护。
  - 目标：验证所有 P0 验收标准，并防止后期范围膨胀。
  - 范围：P0 验收检查清单、演示完成定义、P1/P2 延期项、chat/diff/preview/deploy 界面的视觉完整性检查、事件回放完整性检查。
  - 影响模块：所有 P0 模块、README、演示脚本。
  - 验收标准：最终演示展示需求 -> 计划 -> 智能体执行 -> 差异对比 -> 预览 -> 部署卡片；所有 P0 验收标准标记为通过，或记录有演示安全的兜底方案。
  - 测试或验证方法：运行 5 分钟评审脚本两次：一次成功路径，一次故障恢复路径。
  - 明确非目标：无 ClaudeCodeAdapter、HumanAgentAdapter、Docker 沙箱、WebSocket、提供商市场、MCP 市场、多用户协作、外部 Feishu/Slack 集成、完整部署矩阵、任意 DAG 构建器。
