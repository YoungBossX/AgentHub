# AgentHub 项目状态

本文档只保留当前可执行基线。历史阶段叙述已移入
[历史文档索引](history/README.md)，避免旧的“进行中”描述覆盖现状。

## 当前快照

截至 2026-08-31，AgentHub 仍是本地单用户 Agent Coding Workspace / 强演示 MVP。
核心闭环为：

```text
requirement -> orchestrator plan -> agent execution -> real git diff -> real preview -> deploy card
```

当前基线使用 FastAPI、SQLModel、SQLite、Next.js、Vite React、SSE 和每个 Session
一个持久工作树。运行时保留 `CodexAdapter`、`ClaudeCodeAdapter` 与
`ScriptedMockAdapter`，真实 provider 不可用时必须诚实失败或显式降级，不能伪造成功。

### 已闭合的 OpenSpec

| Change | 当前状态 | 关键证据 |
|---|---:|---|
| `agenthub-p18b-memory-effectiveness-rehearsal` | 19/19，Complete | [P18b 冻结审查](p18b-freeze-review.md)、[有界证据](p18b-bounded-workflow-evidence.json) |
| `agenthub-p18c-live-memory-compliance-library-app` | 24/24，Complete | [P18c 冻结审查](p18c-freeze-review.md)、[有界证据](p18c-bounded-rehearsal-evidence.json) |
| `agenthub-p19-planner-routing-hardening` | Complete | [P19 冻结审查](p19-freeze-review.md) |
| `agenthub-taskrun-scope-preview-hardening` | 1.1-1.7 Complete | 受保护路径、工作树身份和 preview 边界实现及测试 |
| `agenthub-session-sse-recovery` | 6/6，Complete | Session 级持久游标、标准 SSE 消息帧、原生重连和刷新重试回归 |
| `agenthub-session-sse-heartbeat-polling` | 4/4，Complete | SQLite 周期重放、跨 worker 有界可见性和无载荷空闲心跳 |
| `agenthub-source-structure-modularization` | 5/5，Complete | API、Planner、workspace shell 拆分及最终验证/文档收尾完成 |
| `agenthub-windows-scope-observation-stability` | 1/1，Complete | Windows 瞬态目录观察兼容；此前 9 项 API 失败闭合 |
| `agenthub-current-baseline-delivery-readiness` | 1/1，Complete | 真实 Codex 有界运行、Windows launcher 修复、全量门禁与候选集审计 |

`openspec list` 中的 `No tasks` 只表示该 change 没有任务清单，不能据此推导功能已实现
或未实现。判断项目状态必须同时核对代码、对应 OpenSpec 制品和
[变更日志](change-log.md)。

## 当前证据边界

### P18b

P18b 的 fresh 有界产品工作流证明：

- 普通“你好”消息通过真实路由后保持 0 Task / 0 TaskRun；
- 编码请求通过公开 PlanValidator 和 scheduler `ready` 边界，并创建 queued TaskRun；
- 用户偏好与项目规则 MemoryItem 进入同一 Planner/coding snapshot；
- 证据 SHA-256 为
  `42bfc7a1d61bd6efaa4e6dfc3e7b2b371de7e6e2ae43f7e396ab6cfeab3f968b`。

该演练有意不执行 adapter，因此不声称真实 TaskRun 成功或 changed-files。P18b 的范围是
记忆有效性与执行边界闭合，不是 live provider 成功证明。

为单独满足 provider 可用性记录要求，2026-08-30 的 ephemeral/read-only Codex CLI
探针在 6,234 ms 内返回预期文本，exit 0 且无 tool-call 事件；详见
[provider 探针证据](p18b-provider-probe-evidence.json)。该探针不改变上述 TaskRun/adapter
证据边界，也不声明具体 model 或 upstream provider。

### P18c

P18c 保存了一次 Windows 有界 live-memory 演练的实际指令哈希、MemoryItem ID、
changed-files、Diff/Review、检查、预览和暂存证据。真实 Codex provider turn 完成且
作用域通过；TaskRun 后处理因修复前 Git 文本解码缺陷保持 failed。修复后只从同一
Session/Task/Git 基线补采证据，没有改写 TaskRun 终态，也没有把补采 Diff 宣称为成功运行。

### P19

P19 冻结的是 Planner 路由和相关回归。它不扩大产品范围，也不替代 P18b/P18c 的独立
证据边界。

### Session SSE recovery

Session 事件流保留 TaskRun 内的 `sequence`，并以持久化的 `(created_at, id)` 作为
跨 TaskRun 恢复游标。服务端输出浏览器 `EventSource.onmessage` 可接收的标准消息帧，
重连时优先采用 `Last-Event-ID`；订阅先于 backlog，内存 queue 只负责唤醒，事件内容
始终从 SQLite 按游标顺序重新读取。前端按 Session 保存游标，保持浏览器原生重连，
并对任务刷新执行 single-flight、dirty 合并和有界退避重试。

同进程 queue 继续提供低延迟唤醒；打开的流还会每秒用 fresh SQLite 事务按游标检查
持久事件，因此其他 worker 提交或本地通知丢失不会再让终态滞留到浏览器重连。连续
15 秒没有事件输出时，服务端发送 `: keep-alive` SSE 注释；它不触发 `onmessage`，也不
推进 `Last-Event-ID`。这是面向本地 SQLite 基线的跨进程有界可见性，不宣称分布式消息总线。

本项聚焦 SSE 验证为 22 项通过，Web 为 102 项通过，demo-api 为 5 项通过，
`pnpm check` 与严格 OpenSpec 校验通过。该任务完成时完整 API 保留 9 项已在基线
`d2b8f1b` 复现的 Windows TaskRun scope 路径观察失败，因此没有把它们误归为 SSE
回归。后续 `agenthub-windows-scope-observation-stability` 已单独修复共同根因，当前
完整 API 为 1,150 passed / 1 skipped。

### Source structure modularization

结构优化按 OpenSpec 单任务推进。任务 1.1 已将 agent directory、profile draft、runtime
config、memory settings 的 12 个 HTTP operations 及响应映射移至专用 router；任务 1.2
进一步将 Task/TaskRun、artifact/preview/deployment 和 Session SSE 分别移至三个 router。
`main.py` 从 1,843 行降至 193 行，并保留既有测试使用的 helper/monkeypatch 兼容桥接。

当前与基线完整 OpenAPI schema 的 SHA-256 均为
`f1aa309de4f27c15938497241e40b249a97d91be7c94c003d71d6fd49171c63f`；131 项
聚焦路由回归和 `pnpm check` 通过。结构拆分完成时保留的 9 项基线 scope 失败已由
后续 Windows 目录观察稳定性任务闭合；当前完整 API 为 1,150 passed / 1 skipped。

任务 1.3 已把原 2,127 行 `planning.py` 拆为 415 行稳定入口、586 行意图/目标解析和
1,244 行任务构建模块。`plan_for_message` 以及基线中 65 个 class/function/`TaskSpec`
符号仍可从 `app.planning` 访问；Planner、消息路由和 P18b 聚焦回归共 155 项通过。

任务 1.4 已将原 962 行 `workspace-shell.tsx` 拆为 501 行 composition component、
138 行 SSE refresh hook、235 行 TaskRun/artifact action hook、196 行 header/pipeline
组件和 80 行纯状态 helper。Web ESLint/TypeScript 通过，完整 Vitest 为
13 files / 102 tests passed；DOM 文案、测试标识和 API 调用回归保持通过。

任务 1.5 的结构验证得到 Web 13 files / 102 tests passed，demo-api 5 项通过且
`pnpm check` 通过。其当时保留的 9 项基线失败已有独立后续修复和全量绿色结果，不再是
当前项目失败项。

剩余体积主要在安全关键执行核心 `run_engine.py`（3,501 行）、`task_run_scope.py`
（2,966 行）、`task_runs.py`（2,802 行），以及 `task-card-list.tsx`（1,471 行）、
`api.ts`（1,384 行）、`planning_tasks.py`（1,244 行）和 `preview-card.tsx`（1,086 行）。
这些模块需要新的专项 OpenSpec 与不变量测试，未混入本次行为保持型拆分。

### Windows scope observation stability

当前 Windows Python 3.12 可在新建目录首次枚举前通过 `lstat().st_file_attributes`
报告未文档化的 `0x10000000` 位，而 Win32 `GetFileAttributesW` 与枚举后的 `lstat()`
均只报告持久目录属性。scope collector 过去把这一观察层瞬态位当作真实身份变化，导致
完整 snapshot fail-closed、空目录缺失，并连锁阻断 fallback 与 scripted write-scope。

当前修复只在 Windows 目录的路径观察层剔除该瞬态位；device、inode、文件类型、其余
属性、reparse、ADS、普通文件 descriptor 和 Git executable 身份仍严格检查。新增 RED
回归先稳定复现该差异；修复后原 9 项与新增 2 项共 11 项通过，相邻安全矩阵为
258 passed / 1 skipped。Node 24.19 + pnpm 10.33.4 完整门禁为 Web 102 passed、API
1,150 passed / 1 skipped、demo-api 5 passed，`pnpm check` 通过。

### Current baseline delivery readiness

最终有界演练在独立注册的外部 Vite 目标上通过公开消息、计划、调度和 TaskRun 链路，
由真实本地 Codex CLI 完成。成功 TaskRun 为
`dd120d84-11ad-4d4f-91f8-799b84aa1970`，指令 SHA-256 为
`23580d1ae4342abcfe4f540c335ee87b33efe81aac774a7623412e93faacdbe6`；最终 Diff
只包含 `src/App.tsx`，1 行增加、1 行删除，patch SHA-256 为
`d78ecf6bd58995c25e58acd6db5d8c128ee0140dfbcc0e98673a9c6eb5ee1519`。
同一演练保存了实际 MemoryItem ID、memory snapshot、provider 事件、Review、通过的
`pnpm check` / `pnpm build` 证据和健康后主动停止的 Preview。首个被护栏拒绝的运行仍
保留为失败，未重写或冒充 provider 成功。

演练暴露并闭合两个 Windows 启动边界：命令护栏现在只额外接受精确 basename
`codex.exe`，Preview 启动层只把精确 Windows `pnpm` token 解析为 `pnpm.cmd`；包装器
名称仍被拒绝，持久证据继续记录可移植的 `pnpm dev` 命令。收尾审计还发现旧停止路径
只终止 `pnpm.cmd` 包装器、遗留 Vite/esbuild 子进程；当前 Windows 停止路径会终止
完整进程树并删除 runner 临时日志，真实 Vite lifecycle smoke 验证停止后相关进程为 0、
日志不存在。机器证据见
[交付就绪证据](current-baseline-delivery-readiness-evidence.json)，人工边界审查见
[交付就绪审查](current-baseline-delivery-readiness-review.md)。

Node 24.19 + pnpm 10.33.4 最终门禁为 Web 13 files / 102 passed、API
1,153 passed / 1 skipped、demo-api 5 passed，`pnpm check`、35 个严格 OpenSpec、
168 个 Markdown 文件相对链接、433 个文本文件 UTF-8 解码和候选集空白检查均通过。

## 安全与产品边界

- SQLite 是演示数据库，不要求 Postgres。
- 实时链路使用 SSE，不引入 WebSocket。
- 每个 Session 恰好复用一个受控工作树，不同 Session 不共享工作树。
- adapter 只能在已分配的 Session 工作树或注册目标中运行。
- `.git/`、`.env*`、`secrets/`、`node_modules/`、系统路径和未分配主机路径受保护。
- Agent 执行期间不安装依赖；依赖准备只发生在 setup 或明确批准的维护阶段。
- Docker sandbox、多用户协作、外部 IM、provider marketplace、PR 自动创建和生产部署
  仍属于延后范围。

## 运行与验证入口

仓库根目录的标准入口为：

```bash
pnpm check
pnpm test
pnpm demo:api:test
```

`scripts/python-env.sh` 使 Bash 包装脚本同时支持显式 `AGENTHUB_PYTHON_BIN`、Unix
`.venv/bin/python`、Windows `.venv/Scripts/python.exe`、Git worktree 主检出目录的共享
`.venv`，以及激活的 Conda 环境。这只解决开发/验证包装脚本的环境定位，不改变
Agent 运行时的命令与路径护栏。

## 交付状态

2026-08-31，Session SSE recovery 实现提交 `54d0586` 已依次快进到远端 `dev` 与
`main`；该提交同时包含完整回归、OpenSpec 和本轮文档同步。此前的 `affdb73` 仍是
P18b、Windows 验证脚本兼容和上一轮文档收尾的已交付基线。后续分支 tip 可能因纯文档
收尾继续前进，实际远端状态仍应以 `git ls-remote` 回读为准。

Windows scope 观察修复、SSE heartbeat polling 与结构拆分当前仍在本地 `dev` 工作树，
交付就绪补丁和证据也尚未提交或推送。当前候选集已经通过全量门禁与文件审计，可以
进入显式暂存、复核、提交和推送流程；远端 `dev`/`main` 仍指向 `d2b8f1b`，不能把
上述当前全绿结果表述为已远程交付。

## 历史与维护

- 旧项目状态快照：[project-state-archive.md](history/project-state-archive.md)
- 旧变更记录：[change-log-archive.md](history/change-log-archive.md)
- 当前工程变更：[change-log.md](change-log.md)

历史文档只用于追溯当时的判断和命令输出；其中的“等待冻结”“后续任务”“正在进行”等
措辞不代表当前状态。
