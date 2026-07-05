# AgentHub 评委演示脚本

本文档用于 3-10 分钟比赛 Demo 视频、现场演示和答辩。主线只展示已经落地的本地单用户 Agent Coding Workspace，不承诺多用户 IM、真实第三方生产部署、Docker 沙箱或外部飞书/微信集成。

## 一句话定位

AgentHub 是一个 IM 风格的多 Agent 编程工作台：用户像发群聊消息一样提出需求，Orchestrator 拆解任务，前端、后端、QA 等角色 Agent 在受控项目目录里执行，最后用真实 Diff、Review、网页预览、部署状态卡片和运行诊断证明交付结果。

## 演示前检查

在仓库根目录完成一次准备：

```bash
pnpm install
python -m venv .venv
.venv\Scripts\pip install -r apps/api\requirements.txt
pnpm demo:setup
pnpm db:init
```

启动两个终端：

```bash
pnpm dev:api
```

```bash
pnpm dev:web
```

打开：

```text
http://127.0.0.1:3000
```

真实 Agent 可选项：

- Codex：本机已登录 Codex CLI；必要时配置 `CODEX_CLI_PATH`。
- Claude Code：本机 `claude` 命令可用；必要时配置 `CLAUDE_CODE_CLI_PATH`。
- 如果真实 CLI 不稳定，演示使用显式 `ScriptedMockAdapter` 兜底，不伪造真实 Agent 成功。

## 3 分钟主路径

### 0:00-0:20 开场

可以直接说：

> 这个项目解决的问题不是再做一个聊天 UI，而是让 AI 编程协作可验证。AgentHub 用 IM 式交互承接需求，用 Orchestrator 拆解任务，用角色 Agent 执行代码变更，再把每一步沉淀成 Diff、Review、Preview、Deploy card 和诊断证据。

### 0:20-0:50 展示工作台

操作：

1. 打开 `http://127.0.0.1:3000`。
2. 指向左侧 Session 列表，说明这是 IM 式多会话。
3. 指向 Agent 联系人，说明支持 `orchestrator`、`frontend`、`backend`、`qa` 等角色。
4. 指向右侧产物面板，说明 Agent 回复不只是一段文本，还会生成可检查制品。

讲解要点：

- 左侧是会话，中央是聊天和任务，右侧是产物证据。
- 当前是本地单用户 demo，不冒充完整飞书/微信式多用户平台。

### 0:50-1:20 发送需求

在输入框发送：

```text
@orchestrator build a login page for the demo app
```

讲解要点：

- `@orchestrator` 会先理解需求，不直接黑盒改代码。
- Planner 会生成任务计划，并分派给合适角色。
- 每个任务后续都会进入 TaskRun 生命周期。

### 1:20-2:10 启动执行并展示证据

操作：

1. 在任务卡片点击 **Start run**。
2. 等待运行完成。
3. 打开 Diff 卡片，展示真实文件变更。
4. 打开 Review 卡片，展示 QA/审查证据。
5. 点击 **Start preview** 或打开已有 Preview，在右侧 iframe 查看页面。
6. 点击 **Create deploy card**，展示部署状态卡片。

讲解要点：

- Diff 来自真实文件变更，不是聊天文本模拟。
- Preview 使用 Vite React 本地服务。
- Deploy card 是诚实状态卡片；没有第三方生产部署时不会伪造成第三方成功。

### 2:10-2:40 展示可靠性兜底

如果真实 Codex/Claude CLI 不可用或现场网络/登录不稳定，走兜底路径：

1. 点击 **Force Codex failure**。
2. 展示失败的 TaskRun 状态。
3. 点击 **Retry with ScriptedMockAdapter**。
4. 展示兜底运行同样生成真实文件修改、Diff、Preview 和部署卡片。

讲解要点：

- 失败不会被吞掉，会作为 TaskRun/diagnostics 证据展示。
- ScriptedMockAdapter 是显式兜底，不冒充真实 Codex/Claude。
- 评委仍能看到完整产品闭环。

### 2:40-3:00 收束

可以直接说：

> AgentHub 的核心价值是把“AI 帮我写代码”变成一个可审查、可回放、可诊断的协作流程。它现在不是完整企业 IM 平台，但已经跑通了比赛最关键的闭环：需求、规划、执行、真实 Diff、预览和交付证据。

## 5-10 分钟扩展路径

如果演示时间更长，可以追加以下内容。

### 多 Session 与上下文连续

操作：

1. 新建第二个 Session。
2. 发送一个小修改需求，例如：

```text
@orchestrator change the login button text to Continue
```

讲解要点：

- 同一个 Session 复用自己的 worktree。
- 不同 Session 不共享工作树，避免并发污染。
- 后续修改会产生新的 Diff 和预览刷新。

### 新建全栈项目路径

操作：

1. 进入 **运行设置**。
2. 选择一个空文件夹。
3. 点击 **新建全栈项目**。
4. 回到会话发送：

```text
@orchestrator 帮我做一个番茄钟软件，前后端分离
```

讲解要点：

- AgentHub 不只会改内置 demo，也能为外部空目录创建 frontend/backend 项目边界。
- 依赖安装仍放在 setup/审批阶段，不在 Agent 执行期偷偷安装。
- 外部项目同样走 target、PlanValidator、queue、lock、Diff/Review/Preview 证据链。

### Run Diagnostics

操作：

1. 找一个失败或重试过的 TaskRun。
2. 展示诊断摘要或任务时间线。

讲解要点：

- 系统会区分 provider、队列、锁、工作树、预览、部署、制品收集等失败来源。
- 诊断用于决定重试、fallback 或人工处理，而不是把错误藏在后台日志里。

## 答辩速答

### 为什么用 IM 作为交互入口？

因为多 Agent 协作天然像群聊：用户提出目标，Orchestrator 分派任务，角色 Agent 按职责回复。相比表单或流水线编辑器，IM 更适合承载多轮需求、上下文和产物回传。

### 为什么用 SSE，不用 WebSocket？

当前 demo 是本地单用户执行流，主要需要服务端向前端推送 TaskRunEvent。SSE 更简单、足够稳定，也符合当前单向事件流需求。WebSocket 留给未来多用户协作和双向实时编辑。

### 为什么不用 Docker 沙箱？

比赛当前目标是本地可运行 MVP。AgentHub 用 session worktree、target registry、allowed/denied path、命令 allowlist 和审批边界控制风险。Docker 是后续平台化能力，不在当前演示基线内。

### ScriptedMockAdapter 会不会算造假？

不会。它被明确标记为 fallback/mock，只在真实 CLI 不可用或需要稳定演示时使用。它仍然会修改真实文件、生成真实 Diff、走同一套 Preview/Deploy 证据链，但不声称自己是 Codex 或 Claude 成功。

### 项目最有技术含量的地方是什么？

不是聊天 UI，而是把 AI 执行变成可靠证据链：Message 到 Planner，到 Task/TaskRun，到 ProviderGateway/Adapter，再到 Diff、Review、Preview、Deploy、TaskRunEvent 和 Run Diagnostics。每一步都能解释、检查和恢复。

## 失败预案

| 现场问题 | 处理方式 |
|---|---|
| Codex/Claude CLI 登录或配额异常 | 走 **Force Codex failure** -> **Retry with ScriptedMockAdapter** |
| 预览端口不可用 | 重新点击预览刷新，或设置 `AGENTHUB_DEMO_PORT=5174 pnpm demo:dev` |
| 数据库状态太乱 | 执行 `pnpm demo:reset`，再重新打开 Web 端 |
| 后端不可访问 | 确认 `pnpm dev:api` 正在运行，默认地址 `http://127.0.0.1:8000` |
| 前端页面未刷新 | 重新启动 `pnpm dev:web`，浏览器强刷 |

## 不要在演示中承诺

- 不承诺多用户实时协作已经完成。
- 不承诺外部飞书/微信/Slack 集成已经完成。
- 不承诺第三方生产部署已经完成。
- 不承诺 Docker 沙箱已经完成。
- 不把 ScriptedMockAdapter 说成真实 Codex/Claude 成功。
