AgentHub

IM 式 Multi-Agent Coding Workspace：把一次 AI 编程请求转换为可拆解、可执行、可追踪、可验证的工程任务。

AgentHub 面向本地开发工作流，将 Planner / Orchestrator、角色 Agent、Coding Provider、Git Worktree、TaskRunEvent 与 Artifact 组织成完整的多 Agent 编程协作链路。

用户在 Session 中提出需求后，系统会生成任务计划，由不同角色 Agent 在受控工作区内执行代码任务，并将结果沉淀为 Diff、Review、Preview 与运行事件，让 AI 编程过程从自然语言回答进一步转化为可检查的工程交付。

User Message
    ↓
Planner / Orchestrator
    ↓
Task Graph
    ↓
TaskRun + Scheduler
    ↓
ProviderGateway
    ↓
Coding Adapter
    ↓
Git Worktree / Project Target
    ↓
Diff · Review · Preview
    ↓
TaskRunEvent · SSE
    ↓
Web Workspace

Highlights

1. Multi-Agent Task Orchestration

AgentHub 将一次用户需求拆成多个可执行 Task，并通过任务图组织：

role：任务由哪个角色执行，例如 frontend / backend / qa；

target：任务允许作用于哪个代码目标；

dependsOn：任务之间的依赖关系；

intent：当前任务需要完成的工程目标。

planning.py 负责角色提及解析、Planner / LLM Planner 调用与计划生成，并通过任务图校验保证计划结构能够进入后续执行链路。

2. ProviderGateway & Runtime Mapping

Agent 角色不直接绑定具体模型或 CLI。

ProviderGateway 将业务编排与具体 Coding Provider 解耦，统一负责：

根据 role / target / capability 解析运行 Provider；

Provider 健康检查与运行时信息管理；

Provider 容量控制；

Adapter 能力映射；

Provider 运行证据记录。

当前 Coding Adapter 包括：

CodexAdapter

ClaudeCodeAdapter

这种设计使上层 TaskRun 只依赖统一执行接口，而不需要在业务逻辑中直接耦合某个模型或 CLI。

3. Git Worktree Isolation

多 Agent 同时执行代码任务时，最大的工程问题之一是写入冲突。

AgentHub 为 Session 建立独立 Git Worktree，使不同会话拥有各自的代码工作目录：

Repository
├── main working tree
├── session-A worktree
├── session-B worktree
└── session-C worktree

这样可以保留真实 Git Diff，同时避免不同 Session 直接修改同一个工作目录。

4. Session Queue & Target Lock

仅有 Worktree 不能覆盖所有并发写场景，因此执行层进一步加入 Session Queue 与 Target Lock。

TaskRun
   ↓
Session Queue
   ↓
Scheduler Readiness
   ↓
Target Lock
   ↓
Adapter Execution

当前策略包括：

readonly Task 可以安全并行；

write Task 进入 Session 写队列；

同一写目标通过 Target Lock 建立互斥边界；

TaskRun 生命周期与锁状态由执行引擎统一维护。

核心实现：

apps/api/app/session_queue.py

apps/api/app/target_locks.py

apps/api/app/scheduler.py

apps/api/app/run_engine.py

5. Persistent TaskRun Events + SSE

Agent 执行通常是一个持续产生状态变化的长任务。

AgentHub 将运行过程标准化为 TaskRunEvent，并持久化到 SQLite：

Agent / Adapter Event
        ↓
TaskRunEvent
        ↓
SQLite
        ↓
SSE
        ↓
Web UI

前端不需要持续轮询完整 TaskRun，而是通过 SSE 接收增量事件并更新：

Task 状态；

Provider 执行信息；

Queue / Lock 状态；

Artifact；

执行轨迹；

运行诊断。

持久化事件同时为会话恢复和运行回放提供数据基础。

6. Engineering Evidence Chain

AgentHub 不把“模型返回完成”作为任务完成的唯一依据。

每次 TaskRun 可以继续沉淀工程产物：

Artifact

作用

Diff

展示真实代码修改

Review

对代码变更进行审查

Preview

启动本地 Web 预览并记录状态

TaskRunEvent

保存完整运行轨迹

Diagnostics

将运行信息投影为可读诊断

核心链路：

TaskRun
  ├─ Adapter execution
  ├─ Diff collection
  ├─ Review
  ├─ Preview
  └─ TaskRunEvent persistence

Architecture

flowchart LR
    U[User Message] --> P[Planner / Orchestrator]
    P --> TG[Task Graph]
    TG --> TR[TaskRun]
    TR --> SQ[Session Queue / Scheduler]
    SQ --> PG[ProviderGateway]
    PG --> AD[Codex / Claude Code Adapter]
    AD --> WT[Git Worktree / Project Target]
    WT --> DF[Diff]
    WT --> RV[Review]
    WT --> PV[Preview]
    TR --> EV[TaskRunEvent]
    DF --> AR[Artifact]
    RV --> AR
    PV --> AR
    EV --> SSE[SSE]
    SSE --> WEB[Next.js Workspace]
    AR --> WEB

Layered View

Layer

Components

Responsibility

Interaction

Session, Message, Web Workspace

用户交互与上下文入口

Planning

Planner, LLM Planner, Task Graph

需求理解、角色路由、任务拆解

Execution

TaskRun, Scheduler, ProviderGateway, Adapter

运行调度与 Coding Provider 执行

Isolation

Git Worktree, Target Scope, Target Lock

控制代码访问和并发写入

Evidence

Diff, Review, Preview, Artifact

形成可验证工程产物

Observability

TaskRunEvent, SSE, Diagnostics

实时追踪与运行状态投影

Core Execution Flow

一次典型运行流程如下：

用户在 Session 中发送需求；

Planner 解析角色提及、上下文与任务意图；

Orchestrator / LLM Planner 生成 Task Graph；

TaskRun 创建并进入 Scheduler / Session Queue；

系统确认 Target、访问模式与写入边界；

ProviderGateway 解析 Coding Provider；

Adapter 在对应 Worktree / Target 中执行；

系统采集 Diff、Review 与 Preview；

执行过程持续写入 TaskRunEvent；

SSE 将运行状态和 Artifact 投影到 Web Workspace。

Tech Stack

Backend

Python

FastAPI

Pydantic

SQLModel

SQLite

Frontend

Next.js App Router

TypeScript

Tailwind CSS

shadcn/ui

Agent Runtime

Codex CLI

Claude Code CLI

ProviderGateway

Task Graph

Runtime Role Config

Engineering Infrastructure

Git Worktree

Session Queue

Target Lock

Server-Sent Events (SSE)

Vite React Preview

Repository Structure

AgentHub/
├── apps/
│   ├── api/                 # FastAPI backend
│   │   └── app/
│   │       ├── planning.py
│   │       ├── run_engine.py
│   │       ├── provider_gateway.py
│   │       ├── session_queue.py
│   │       ├── target_locks.py
│   │       ├── diffs.py
│   │       ├── reviews.py
│   │       ├── previews.py
│   │       └── models.py
│   │
│   ├── web/                 # Next.js workspace
│   ├── demo/                # Vite React target application
│   └── demo-api/            # FastAPI target application
│
├── docs/                    # Architecture and project documents
├── openspec/                # Feature specifications / changes
├── scripts/                 # Development scripts
└── README.md

Key Modules

Module

Responsibility

planning.py

Planner、角色提及、LLM Planner、Task Graph

run_engine.py

TaskRun 主执行链路与执行生命周期

provider_gateway.py

Provider 解析、健康、容量与运行上下文

session_queue.py

Session 任务队列与读写门控

target_locks.py

Target 写锁

diffs.py

Git Diff / 文件差异采集

reviews.py

Review Artifact

previews.py

本地 Preview 生命周期

run_diagnostics.py

运行事件与 Artifact 的诊断投影

apps/web

Session、消息、任务、执行轨迹和 Artifact UI

Quick Start

Requirements

Node.js >= 18

pnpm

Python >= 3.9

Git

如需连接真实 Coding Provider，请提前配置对应的 Codex CLI 或 Claude Code CLI。

1. Install JavaScript Dependencies

pnpm install

2. Create Python Environment

macOS / Linux:

python3 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.txt

Windows:

python -m venv .venv
.venv\Scripts\pip install -r apps\api\requirements.txt

3. Prepare Demo Target

pnpm demo:setup

4. Initialize Database

pnpm db:init

5. Start Backend

pnpm dev:api

Default API address:

http://127.0.0.1:8000

6. Start Web Workspace

pnpm dev:web

Open:

http://127.0.0.1:3000

Example

在 AgentHub Session 中输入：

@orchestrator build a login page for the demo app

系统会将需求转换为多个任务，并在工作台中展示：

Plan
 ↓
Task
 ↓
TaskRun
 ↓
Agent Execution
 ↓
Diff / Review / Preview
 ↓
TaskRunEvent

也可以为 Session 绑定外部 frontend / backend Target，使 Agent 在指定项目目录中执行代码任务。

Development Commands

# Start web
pnpm dev:web

# Start API
pnpm dev:api

# Initialize database
pnpm db:init

# Run checks
pnpm check

# Run tests
pnpm test

# Start demo target
pnpm demo:dev

Design Focus

AgentHub 重点解决的不是“如何让多个模型同时聊天”，而是 多个 Agent 如何在真实代码工作区中安全、可追踪地协作执行任务。

围绕这个目标，项目形成了四条核心设计主线：

Task Orchestration
      +
Execution Isolation
      +
Runtime Provider Abstraction
      +
Engineering Evidence

最终目标是让一次 AI 编程任务不仅有自然语言输出，还能够回答：

谁执行了这个任务？

使用了哪个运行 Provider？

修改了哪个代码目标？

是否存在并发写冲突？

实际修改了哪些文件？

是否生成了可预览结果？

整个执行过程能否被追踪和恢复？

这也是 AgentHub 与普通 Chat UI 的核心区别。

AgentHub — Multi-Agent Coding Workspace
