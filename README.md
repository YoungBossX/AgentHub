# AgentHub

AgentHub 是一个本地单用户、IM 风格的 Agent Coding Workspace / 多 Agent 编码协作平台原型。它已经支持 Planner、前端/后端/评审 Agent、外部项目目标和运行时 provider 配置，但还不是完整的多用户飞书/微信式协作平台。Demo 闭环是：

```text
用户需求 -> Orchestrator 拆解任务 -> Agent 执行 -> 真实 Git Diff -> 网页预览 -> 部署卡片
```

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 UI | Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui |
| 后端 | FastAPI, Pydantic, SQLModel, SQLite |
| Demo 应用 | Vite React (`apps/demo`) |
| 实时通信 | SSE (基于持久化 TaskRunEvent) |
| 隔离 | 每个 Session 一个 Git Worktree |
| Agent 适配器 | CodexAdapter, ClaudeCodeAdapter, ScriptedMockAdapter |

## 前置条件

两个平台都需要以下工具，请先安装：

- **Node.js** ≥ 18 + **pnpm** ≥ 9（项目 `package.json` 锁定了 `pnpm@10.33.4`）
- **Python** ≥ 3.9
- **Git**

可选（真实 Agent 执行时按需使用）：
- **Codex CLI**：已登录，macOS 默认路径 `/Applications/Codex.app/Contents/Resources/codex`，或通过 `CODEX_CLI_PATH` 环境变量指定
- **Claude Code CLI**：已登录，通过 `claude` 命令或 `CLAUDE_CODE_CLI_PATH` 环境变量指定

---

## 快速开始

以下命令**全部在仓库根目录执行**。请根据你的操作系统选择对应 tab。

### 1. 安装 JS 依赖

两个平台相同：

```bash
pnpm install
```

### 2. 创建 Python 虚拟环境并安装依赖

**macOS / Linux：**

```bash
python3 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.txt
```

**Windows (Git Bash / PowerShell)：**

```bash
python -m venv .venv
.venv\Scripts\pip install -r apps/api\requirements.txt
```

> 如果你安装了多个 Python 版本，把 `python3` / `python` 替换为具体版本号如 `python3.12`。

### 3. 安装 Demo 应用依赖

两个平台相同：

```bash
pnpm demo:setup
```

> 依赖安装在 setup 阶段一次性完成，Agent 执行期间不会运行 `npm install`。

### 4. 初始化数据库

```bash
pnpm db:init
```

这会创建 SQLite 表并写入 seed 数据：
- 1 个 demo 用户
- 1 个 `AgentHub Demo` 工作区（指向 `apps/demo`）
- 4 个 Agent：orchestrator, frontend, backend, qa

### 5. 启动后端和前端

**终端 1 — 启动后端：**

```bash
pnpm dev:api
```

后端默认监听 `http://127.0.0.1:8000`。可通过 `AGENTHUB_API_PORT` 覆盖端口。

**终端 2 — 启动前端：**

```bash
pnpm dev:web
```

前端默认监听 `http://127.0.0.1:3000`。可通过 `BACKEND_URL` 覆盖后端地址。

打开 `http://127.0.0.1:3000` 即可看到 AgentHub。

### 6. 发送第一条 Demo 请求

在 UI 中创建一个新 Session，输入：

```text
@orchestrator build a login page for the demo app
```

Orchestrator 会自动生成 3 个 Task，点击 **Start run** 即可触发 Agent 执行。

---

## 实际新建一个全栈应用

AgentHub 现在支持从一个空文件夹开始创建真实项目，而不是只能修改内置 Demo 应用。推荐流程：

1. 打开 `http://127.0.0.1:3000`，创建或选择一个 Session。
2. 进入左侧 **运行设置**（`/settings/runtime`）。
3. 在工作区目标区域选择一个空文件夹。
4. 点击 **新建全栈项目**。AgentHub 会在该目录中创建 frontend/backend 项目边界，注册对应的 external frontend/backend targets，并绑定到当前 Session。
5. 按页面展示的 setup steps 准备依赖。
6. 回到会话，发送需求，例如：

```text
@orchestrator 帮我做一个番茄钟软件，前后端分离
```

Orchestrator 会把任务规划给前端 / 后端 Agent。点击任务上的 **Start run** 后，Agent 会在当前 Session 绑定的项目目录中执行，并生成 Diff、Review、预览和部署卡片等证据。

当前这条路径适用于常见的本地全栈应用开发演示：前端默认 Vite React，后端默认 FastAPI。它不会在 Agent 执行期间自动安装依赖；依赖准备必须在 setup 阶段完成或经过显式审批。

---

## Windows 用户注意事项

项目脚本（`scripts/` 目录）使用 **bash** 编写，Windows 上需要以下方式之一执行：

| 方式 | 推荐度 | 说明 |
|---|---|---|
| **Git Bash** | 推荐 | 安装 Git for Windows 时自带，直接运行所有 `pnpm` 命令 |
| **WSL 2** | 推荐 | 完整 Linux 环境，Python venv 路径与 macOS 一致 |
| **PowerShell** | 可 | 手动执行脚本内容，详见下方 |

**PowerShell 手动启动方式**（如果不用 Git Bash）：

```powershell
# 初始化数据库
cd apps\api
..\..\.venv\Scripts\python -m app.db

# 启动后端
..\..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 启动前端（仓库根目录）
pnpm dev:web
```

> Python venv 路径对照：macOS 用 `.venv/bin/python`，Windows 用 `.venv\Scripts\python.exe`。

---

## 常用命令

| 命令 | 说明 |
|---|---|
| `pnpm dev:api` | 启动后端 (127.0.0.1:8000) |
| `pnpm dev:web` | 启动前端 (127.0.0.1:3000) |
| `pnpm demo:dev` | 单独启动 Vite Demo 应用 |
| `pnpm db:init` | 初始化数据库 + seed |
| `pnpm db:seed` | 仅重新 seed（不重建表） |
| `pnpm demo:reset` | 安全重置 Demo 数据库（自动备份） |
| `pnpm check` | 全部代码检查 |
| `pnpm test` | 全部测试 |
| `pnpm test:api` | 仅后端测试 |
| `pnpm test:web` | 仅前端测试 |

### 使用 Claude Code 作为默认 Agent

```bash
# macOS
AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code pnpm dev:api

# Windows (PowerShell)
$env:AGENTHUB_DEFAULT_CODE_ADAPTER="claude_code"; pnpm dev:api
```

---

## Demo 重置

当本地数据库积累过多测试数据时：

```bash
pnpm demo:reset
```

- 自动备份当前数据库到 `apps/api/data/backups/demo-reset-<timestamp>/`
- 保留 `.worktrees`、源代码、依赖
- 不停止正在运行的预览进程
- 重置命令会打印备份路径和恢复命令

---

## 故障排除

### 前端启动失败

```bash
pnpm install
pnpm dev:web
```

确认后端在 `http://127.0.0.1:8000` 运行。如后端地址不同，设置 `BACKEND_URL`。

### 后端启动失败

```bash
# macOS
python3 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.txt

# Windows
python -m venv .venv
.venv\Scripts\pip install -r apps/api\requirements.txt
```

### 数据库缺失

```bash
pnpm db:init
```

### Agent CLI 不可用

- Codex：参阅 `docs/adapter-notes.md`
- Claude Code：参阅 `docs/claude-code-adapter-notes.md`
- 降级路径：UI 中点击 **Force Codex failure** → **Retry with ScriptedMockAdapter**，使用确定性 mock 执行，仍然产生真实文件修改和 diff

### 预览端口被占用

```bash
AGENTHUB_DEMO_PORT=5174 pnpm demo:dev
```

### Demo 依赖缺失

```bash
pnpm demo:setup
```

### 降级路径无 Diff

确认 Session 有 Git Worktree，降级 run 已完成。`ScriptedMockAdapter` 需要 worktree 中存在 `apps/demo/src/App.tsx`。

### Mock 部署卡片未出现

先创建健康的预览，再在预览卡片上点击 **Create deploy card**。

---

## 项目边界

当前包括：
- 单用户本地工作区
- SSE 实时推送（非 WebSocket）
- Session 级 Git Worktree 隔离（非 Docker）
- Vite React 预览
- SQLite
- Codex CLI + Claude Code CLI 真实适配器
- ScriptedMockAdapter 降级适配器
- Git Diff + 预览 + Mock Deploy
- 空文件夹新建全栈项目路径
- external frontend/backend targets 绑定到 Session
- 非 Git 外部项目的文件快照 Diff / Review 证据链
- Target 写锁恢复、队列调度、provider 失败诊断和 Review 中文证据面板

当前可靠性能力：

- 同一个 Session 复用已绑定的项目 target，不把不同 Session 写到同一个工作区。
- TaskRun 开始前为非 Git 外部目标记录文件快照，完成后可生成真实 Diff。
- Diff/Review 收尾失败会写入诊断事件，不再静默丢失证据。
- Provider 连接失败、限流、不可用等常见问题会进入 Run Diagnostics，便于判断是否重试或切换 provider。
- completed/failed/interrupted 终态会释放 target 写锁，避免旧 run 长时间阻塞后续任务。

明确排除（P1/P2+）：
- HumanAgentAdapter、Docker、WebSocket
- Provider Marketplace、MCP Marketplace
- PR 创建、外部 IM 集成（飞书/微信/Slack）
- 多用户协作、RBAC
- 生产部署
