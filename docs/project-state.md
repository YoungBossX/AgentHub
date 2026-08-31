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

完整回归在 Node 24.19 / pnpm 10.33.4 环境下通过：Web 102 项、API 1146 项通过并
跳过 1 项、demo-api 5 项。即时订阅仍是单进程内机制；若持久化成功后的唤醒完全丢失
且没有后续事件，已连接客户端需要等待原生重连恢复。该限制不改变持久事件作为事实源。

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

## 历史与维护

- 旧项目状态快照：[project-state-archive.md](history/project-state-archive.md)
- 旧变更记录：[change-log-archive.md](history/change-log-archive.md)
- 当前工程变更：[change-log.md](change-log.md)

历史文档只用于追溯当时的判断和命令输出；其中的“等待冻结”“后续任务”“正在进行”等
措辞不代表当前状态。
