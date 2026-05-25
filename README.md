# AgentHub

AgentHub 是一个本地单用户 Agent 编码工作区 / 强 Demo MVP。它使用 IM 风格的命令中心界面，但不是完整的多用户微信、飞书式协作平台。已验证的 Demo 循环是：

```text
需求 -> 协调器规划 -> Agent 执行 -> 真实 Git Diff -> 真实预览 -> 部署卡片
```

## 当前技术栈

- 产品 UI：Next.js App Router、TypeScript、Tailwind CSS，以及 `apps/web` 中的本地 shadcn/ui 风格组件
- 后端：FastAPI、Pydantic、SQLModel，以及 `apps/api` 中的 SQLite
- Agent 修改的 Demo 应用：仅 `apps/demo` 中的 Vite React
- 实时通信：由持久化的 `TaskRunEvent` 记录支持的 SSE
- 隔离机制：每个 AgentHub Session 一个 Git Worktree
- 执行适配器：本地 CLI `CodexAdapter`、本地 CLI `ClaudeCodeAdapter` 和 `ScriptedMockAdapter`
- 产物：Git Diff 卡片、Vite React 预览卡片和 Mock 部署卡片

## 前置条件

- Node.js 和 pnpm。本仓库在 `package.json` 中声明了 `pnpm@10.33.4`
- Python 3.9 或更高版本
- Git
- 真实 Codex 适配器路径可选：本地 Codex CLI，已登录，可通过 `CODEX_CLI_PATH` 或 `apps/api/app/codex_adapter.py` 使用的默认 macOS 应用路径访问
- 真实 Claude Code 适配器路径可选：本地 Claude Code CLI，已登录，可作为 `claude` 或通过 `CLAUDE_CODE_CLI_PATH` 访问

## 安装设置

从仓库根目录运行这些命令。

安装 JavaScript 工作区依赖：

```bash
pnpm install
```

创建并填充后端脚本使用的 Python 虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/api/requirements.txt
```

在设置期间安装 Vite React Demo 应用依赖：

```bash
pnpm demo:setup
```

Agent 执行和预览启动不得运行依赖安装。上面的设置步骤是创建 `node_modules` 的预期时间。

初始化并填充本地 SQLite 数据库：

```bash
pnpm db:init
```

`pnpm db:init` 创建 SQLModel 表并填充：

- 一个 Demo 用户
- 一个指向 `apps/demo` 的 `AgentHub Demo` 工作区
- 启用的协调器、前端、后端和 QA Agent

要重新填充现有数据库而不重新创建表：

```bash
pnpm db:seed
```

默认数据库 URL 是 `sqlite:///data/agenthub.sqlite3`，相对于 `apps/api`。

## 安全 Demo 重置

当本地 Demo 数据库积累了旧的 Session、Task Run、预览或冒烟测试记录时，使用重置辅助工具：

```bash
pnpm demo:reset
```

该辅助工具默认是非破坏性的：

- 它拒绝在 API 进程打开 SQLite 数据库时运行
- 它将 `apps/api/data/agenthub.sqlite3` 和任何 SQLite WAL/SHM 文件备份到 `apps/api/data/backups/demo-reset-<timestamp>/`
- 它在备份后仅删除活动的 SQLite 文件
- 它通过现有的 SQLModel 初始化路径重新创建并填充数据库
- 它不删除 `.worktrees`、源代码、依赖项或预览文件
- 它不停止正在运行的预览或开发服务器进程

重置后，启动 `pnpm dev:api` 和 `pnpm dev:web`，在 UI 中创建一个新的 Session，然后再次发送固定的 Demo 请求。

要恢复之前的数据库，停止 API 并将备份的文件复制回 `apps/api/data/agenthub.sqlite3`。重置命令每次运行时都会打印确切的备份路径和恢复命令。

## 本地运行

启动后端：

```bash
pnpm dev:api
```

后端默认监听 `http://127.0.0.1:8000`。使用 `AGENTHUB_API_PORT` 覆盖端口。

在第二个终端中启动产品 UI：

```bash
pnpm dev:web
```

前端默认监听 `http://127.0.0.1:3000` 并调用后端 `http://127.0.0.1:8000`。使用 `BACKEND_URL` 覆盖 Next.js 应用的后端 URL。

当你只想检查基线 Vite React Demo 应用时，手动启动 Demo 应用：

```bash
pnpm demo:dev
```

仓库级 Demo 命令默认使用端口 `5173`。固定的预览命令形式是：

```bash
pnpm dev --host 127.0.0.1 --port <port>
```

后端预览运行器在 Session Worktree 内部执行该命令，不安装依赖项。

## 验证命令

从仓库根目录运行这些命令：

```bash
pnpm check
pnpm test
git diff --check
```

有用的更窄命令：

```bash
pnpm check:web
pnpm check:api
pnpm check:demo
pnpm test:web
pnpm test:api
```

## 产品界面

本地 UI 当前包括：

- Session 列表和 `New session` 控件
- 选中 Session 的聊天流
- 协调器计划消息
- 带有分配的角色 Agent 和依赖项的任务卡片
- 每个任务的运行历史
- 运行控件：`Start run`、`Interrupt`、`Retry`、`Force Codex failure` 和 `Retry with ScriptedMockAdapter`
- 带有更改文件、补丁摘要和可展开 Monaco Diff 检查的 Diff 卡片
- 带有状态、URL、端口、刷新/打开操作和右侧 iframe 面板的预览卡片
- 由持久化 Mock Deployment 记录支持的部署卡片

## Demo 请求

在选中的 Session 中使用这个固定请求：

```text
@orchestrator build a login page for the demo app
```

当前规划器创建一个 3 步计划：

1. 规划登录页面更改。
2. 构建 Vite React 登录页面。
3. 审查登录页面 Demo 路径。

确定性 Demo 变异目标位于 `apps/demo/src/App.tsx` 中：

- `data-agenthub-target="login-page-slot"`
- `data-agenthub-target="primary-action-button"`

## Demo 脚本

使用 `docs/demo-script.md` 进行带旁白的 Demo。它包括：

- 通过 Session 创建、规划、任务卡片、真实本地 Agent Direct Start 执行、Diff、预览和 Mock 部署的主 Demo 路径
- 显示失败的 Codex 运行保留在历史记录中以及成功的 `ScriptedMockAdapter` 重试的失败恢复路径

当前 P4 状态：`Start run` UI 调度真实本地 Agent Direct Start 执行。P1-11 通过真实 Codex 文件变异、Diff、健康的 Vite 预览和 Mock 部署卡片验证了干净的 SQLite 演练。P4-0 通过面向浏览器的 API 路径验证了 Claude Code 默认适配器路径，以及降级和后续路径。如果真实本地 Agent 执行不可用、未认证、使用受限或对于 Demo 窗口太慢，强制失败的 `ScriptedMockAdapter` 路径仍然是可靠性降级方案。

要使用 Claude Code 作为前端/后端编码任务的默认编码适配器：

```bash
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api
```

## 当前 Demo 边界

当前本地 Demo 包括：

- 单用户本地工作区和 Session
- SSE，不是 WebSocket
- Session 级别的 Git Worktree，不是 Docker 沙箱
- 仅 Vite React 预览
- SQLite，不是 Postgres
- 本地 Codex CLI 和本地 Claude Code CLI 作为真实适配器路径
- `ScriptedMockAdapter` 作为可靠性降级方案，具有真实文件更改
- Git CLI Diff 收集和持久化 Diff 产物
- 当真实部署不可用时，由 Mock 支持的部署卡片

延迟的平台项目包括：

- `HumanAgentAdapter`
- Docker 沙箱
- WebSocket
- Provider Marketplace 或 MCP Marketplace
- PR 创建或补丁导出
- 外部飞书、Slack、微信或其他 IM 集成
- 多人协作
- 企业 RBAC、计费或管理策略控制台
- 生产部署矩阵或一键生产部署指南

## P1 重置说明

- `pnpm db:init` 初始化并填充 SQLite 数据库。
- 运行时 Worktree 位于 `.worktrees/` 下。
- 运行时 API 数据库文件位于 `apps/api/data/` 下。
- 在 Demo 重置期间不要删除 `.git/`、`.env*`、`node_modules/` 或不相关的用户文件。
- 对于 P1-11 干净状态演练，在运行 `pnpm db:init` 之前，之前的 SQLite 数据库被移动到 `/tmp/agenthub-p1-11-backup-20260517-095901/agenthub.sqlite3.before-p1-11`。现有的 `.worktrees` 检出保持原位，以避免干扰 Git 注册的 Worktree 元数据。
- 要恢复该 P1-11 之前的数据库，首先停止开发服务器，如果需要保留当前的 `apps/api/data/agenthub.sqlite3` 则备份它，然后将 P1-11 备份文件移回 `apps/api/data/agenthub.sqlite3`。

## 故障排除

### 前端无法启动

从仓库根目录运行 `pnpm install`，然后 `pnpm dev:web`。除非设置了 `BACKEND_URL`，否则 Web 应用期望后端在 `http://127.0.0.1:8000`。

### 后端无法启动

创建 Python 虚拟环境并安装后端依赖项：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r apps/api/requirements.txt
```

然后运行 `pnpm dev:api`。

### 数据库缺失或未填充

运行：

```bash
pnpm db:init
```

刷新 Web 应用。健康卡片应显示后端可访问，工作区应为 `AgentHub Demo`。

### 真实 Agent CLI 不可用、未认证或使用受限

阅读 `docs/adapter-notes.md` 了解 Codex 说明，阅读 `docs/claude-code-adapter-notes.md` 了解 Claude Code 说明。使用可见的恢复路径：`Force Codex failure`，然后 `Retry with ScriptedMockAdapter`。

### 预览端口不可用

预览运行器为后端启动的预览分配端口。对于手动 Demo 应用启动，设置不同的端口：

```bash
AGENTHUB_DEMO_PORT=5174 pnpm demo:dev
```

### Vite Demo 依赖项缺失

运行设置时安装：

```bash
pnpm demo:setup
```

不要将依赖安装添加到适配器执行或预览启动中。

### 降级方案未生成 Diff

检查选中的 Session 有一个 Git Worktree 并且降级运行已完成。`ScriptedMockAdapter` 期望 Session Worktree 内的 `apps/demo/src/App.tsx` 并使用上面列出的确定性目标。

### Mock 部署卡片未出现

首先创建或刷新健康的预览。Mock 部署卡片从预览卡片通过 `Create deploy card` 创建；它由后端持久化，不是仅前端的占位符。

### 开发控制台中的特定区域 Hydration 警告

在 P1-11 期间，观察到围绕特定区域 Session 日期格式化的非阻塞开发 Hydration 警告。它没有阻止干净状态演练、降级演练、Diff 卡片、预览 iframe 或 Mock 部署卡片。
