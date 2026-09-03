# AgentHub 项目状态

本文档只保留当前可执行基线。历史阶段叙述已移入
[历史文档索引](history/README.md)，避免旧的“进行中”描述覆盖现状。

## 当前快照

截至 2026-09-03，AgentHub 仍是本地单用户 Agent Coding Workspace / 强演示 MVP。
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
| `agenthub-session-sse-backpressure` | 1/1，Complete | 每订阅者单个无载荷合并 wake、固定 high-water 的 100 行 SQLite 回放批次 |
| `agenthub-source-structure-modularization` | 5/5，Complete | API、Planner、workspace shell 拆分及最终验证/文档收尾完成 |
| `agenthub-windows-scope-observation-stability` | 1/1，Complete | Windows 瞬态目录观察兼容；此前 9 项 API 失败闭合 |
| `agenthub-current-baseline-delivery-readiness` | 1/1，Complete | 真实 Codex 有界运行、Windows launcher 修复、全量门禁与候选集审计 |
| `agenthub-production-dependency-security-refresh` | 1/1，Complete | Web 生产依赖审计从 34 项告警降至 0 |
| `agenthub-development-toolchain-security-refresh` | 1/1，Complete | 完整开发/测试依赖审计从 19 条 advisory 降至 0；本机 pnpm shim 恢复 |
| `agenthub-browserslist-security-refresh` | 1/1，Complete | 最终候选审计新增的 2 条 high advisory 闭合；Vite override 不再污染 Demo peer 范围 |
| `agenthub-subprocess-environment-isolation` | 1/1，Complete | 项目子进程最小环境、provider 环境分离及持久证据脱敏 |
| `agenthub-real-adapter-execution-containment` | 1/1，Complete | Codex 原生 workspace sandbox 与 Claude restricted/safe file-only 边界由构造器和命令守卫双重强制 |
| `agenthub-preview-iframe-sandbox` | 1/1，Complete | Preview iframe 最小 sandbox、Permissions Policy 与 no-referrer 边界 |
| `agenthub-generated-project-dependency-pinning` | 1/1，Complete | 生成清单直接依赖与 pnpm 版本精确固定；真实生成项目安装/check/build/audit 通过 |

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

### Session SSE backpressure

同进程通知不再为每个 publish 保存完整 `TaskRunEvent` 或调度一个 callback。每个打开的
Session 订阅现在只保留一个无 payload wake 状态；第一个生产线程调度 event-loop wake，
后续通知在消费者确认前合并。无论客户端暂停期间产生多少事件，本地 subscriber 状态
都不会按事件数增长，SQLite 仍是唯一事件事实源。

初始 backlog、one-shot replay、local wake 和周期 poll 均先捕获本轮固定 high-water
cursor，再以最多 100 行的批次推进。批次到达 high-water 后本轮结束；之后提交的事件
留给下一次 wake、poll 或请求，因此持续生产不能使 one-shot 请求永不结束，也不会让
初始 backlog 永远阻塞 live loop。该上界按行数而非单事件字节数计算，不是事件保留或
payload 大小策略。

RED 证据确认旧实现的 1,000 次 publish 形成 `maxsize=0 / qsize=1000`，且旧 replay
没有批次/high-water 边界。修复后 SSE 聚焦 25 passed，相邻 event producer/Session
queue/target lock 为 95 passed，Web EventSource 回归 15 passed，最终完整 API 为
1,193 passed / 2 skipped；严格 OpenSpec 和独立复核通过。复核发现的持续生产追逐问题
已通过固定 high-water 修复并加入后续事件不丢失回归。

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

### Development and test dependency security refresh

2026-09-01 的完整 `pnpm audit` 在生产审计归零后仍报告 19 条开发/测试 advisory：
14 high、4 moderate、1 low、0 critical。路径集中在 Demo Vite/esbuild/PostCSS/nanoid、
Web Vitest/Vite、ESLint/js-yaml/brace-expansion 和 jsdom/ws。

当前 Demo manifest 将 Vite 7 floor 提升到 7.3.6，不迁移 Vite 8；Web 工具链在
既有主版本内解析 Vitest 4.1.11、ESLint 9.39.5 和 jsdom 27.4.0。最终锁文件解析
Vite 7.3.6 / 8.0.16、esbuild 0.28.2、PostCSS 8.5.26、nanoid 3.3.18、
js-yaml 4.3.2、brace-expansion 1.1.18 / 5.0.9 和 ws 8.21.3。四个精确
override 仅替换 pnpm 保留的已审计脆弱快照，不扩展为无关依赖大版本升级。

根 manifest 现声明共同 Node 边界 `^20.19.0 || ^22.12.0 || >=24.0.0`。在 conda
`agent` 的 Node 25.7 / pnpm 10.33.4 下，冻结安装、Demo/Web 定向门禁、Next build、
完整 `pnpm check` 和全量测试均通过；全量测试为 Web 102 passed、API 1,152 passed /
2 skipped、demo-api 5 passed。有界 Demo smoke 返回 HTTP 200，仅监听
127.0.0.1:4187，并包含 Vite HMR client、React entry 与 root。

最终完整审计覆盖 630 个依赖、生产审计覆盖 74 个依赖，两者所有严重级别均为 0。
本机 pnpm shim 由兼容 Node 22.11 的用户级 Corepack 0.34.5 重建，普通
`pnpm --version` 返回 10.33.4，未关闭签名校验；受 ACL 保护的全局 Corepack 包未被
破坏性替换。

### Final Browserslist security refresh

2026-09-03 的最终候选 `pnpm audit` 在此前归零后新增报告 Browserslist 4.28.2 的
2 条 high advisory。该快照由 Demo `@vitejs/plugin-react` 与 Web
`eslint-config-next` 经共享 Babel 7 工具链引入；依赖路径得到确认，但没有把 advisory
路径直接表述为已证明可利用的 AgentHub 运行时漏洞。

pnpm 10.33.4 的定向 lock-only 更新没有重选该兼容 transitive，因此根策略仅将
`browserslist <=4.28.6` 映射到首个修复版 4.28.7。锁文件最终只有一个 Browserslist
版本。重新解析同时发现既有全局 Vite override 会把 `@vitejs/plugin-react` 的 Vite 4-8
peer 范围改写成精确 Vite 8，导致使用 Vite 7.3.6 的 Demo 出现 peer conflict。当前
override 已收窄到 `vitest@4.1.11` 与 `@vitest/mocker@4.1.11` 两个实际父依赖：Demo
保持 Vite 7.3.6，Web 测试工具链保持 Vite 8.0.16，冻结安装不再报告 peer conflict。

Node 25.7 / pnpm 10.33.4 下，完整和生产审计均为 0 known vulnerabilities；Demo
check/build、Web check/102 tests/build、根 `pnpm check` 以及 Web 102 + API 1,193 passed /
2 skipped + demo-api 5 的完整测试均通过。该结果是包管理器 advisory 快照，不是“项目
不存在任何安全漏洞”的泛化证明。

### Production dependency security refresh

2026-09-01 的 fresh `pnpm audit --prod` 在已交付锁文件上发现 34 项 Web 生产依赖
告警：9 high、21 moderate、4 low、0 critical。路径集中在 Next.js 16.2.6 及其
PostCSS/nanoid/sharp 依赖，以及 Monaco Editor 0.55.1 的 DOMPurify 依赖。

当前 manifest 将 Next.js 与 `eslint-config-next` 的兼容 floor 同步到 16.3.3、将
Monaco Editor 提升到 0.56.0；锁文件解析 Next 16.3.4、PostCSS 8.5.23、
nanoid 3.3.18、sharp 0.35.4 和 Monaco 0.56.0。根 pnpm override 固定
DOMPurify 3.4.13 与 Babel 7.29.6，分别闭合 sanitizer advisories 和升级后暴露的
source-map 任意文件读取 low 告警。最终 `pnpm audit --prod` exit 0，所有严重级别为 0。

Web lint/TypeScript、13 files / 102 tests、Next production build 和完整 `pnpm check`
通过；完整测试为 Web 102 passed、API 1,152 passed / 2 skipped、demo-api 5 passed。
两个 API skip 分别是 POSIX exact-case 与当前 Windows 未暴露瞬态目录位的条件测试，
不是依赖升级回归。

完整（含开发/测试依赖）审计仍有 14 high、4 moderate、1 low，全部位于 Vite/Vitest、
ESLint、jsdom 等工具链路径。它们不属于本次生产依赖任务，必须由后续单独 OpenSpec
升级和验证；因此当前只能声明 Web 生产依赖审计归零，不能声明全依赖审计归零。

### Subprocess environment isolation

2026-09-02 的单任务环境隔离为 Preview、staging build 和本地静态服务建立最小项目
环境，为 Codex、Claude Code、Claude Planner 和相关 CLI 探针建立 provider 专属环境；
数据库、其他 provider 和 AgentHub 控制面密钥不再默认继承。Adapter event、TaskRun
错误、Preview 诊断和 Deployment log 在持久化前执行精确敏感值与 assignment 脱敏。

独立复核发现并闭合 Planner/probe/TaskRun 错误字段旁路及 Claude gateway/corporate TLS
变量兼容缺口。最终 API 为 1,165 passed / 2 skipped，Web 102 tests、Demo TypeScript、
demo-api 5 tests 和严格 OpenSpec 均通过。该边界不等于 OS/container sandbox；selected
provider credential 仍是受信 CLI 的必要权限，任意变换/主动外传属于后续 containment
专项，而不是证据脱敏可以保证的能力。

### Real adapter execution containment

真实适配器的目标仓库执行面现在由固定命令形态约束。Codex 必须使用平台原生
`workspace-write`、`--ask-for-approval never`、ephemeral session，并忽略用户配置和
user/project execpolicy rules；Claude Code 必须同时启用 restricted、safe mode、strict
MCP、显式 `Read,Write,Edit,MultiEdit` 工具集和无会话持久化。两条命令都在用户派生指令
前插入 `--`，防止以短横线开头的文本被 CLI 当作降级参数。

中央命令守卫不再只识别 `codex` basename 或零散 Claude flag，而是独立验证完整命令
形态，并要求 Codex 的 `--cd` 与规范化后的 runner worktree 相同；遗漏沙箱、使用
`danger-full-access`、添加 `--add-dir`、启用 sandbox bypass、遗漏 Claude
restricted/MCP 边界或加入 Bash 工具都会在进程启动前被拒绝。Claude 的受限模式会
忽略项目设置并禁用命令/代码运行与 WebFetch，safe mode 与 strict MCP 再关闭
hook/plugin/MCP 等项目自定义入口。

最终聚焦测试为 69 passed，完整 API 为 1,190 passed / 2 skipped；严格 OpenSpec 和
Python compile 检查通过。独立只读复核发现的 Codex worktree 未绑定及负向用例复合缺失
均已修复并由最终门禁覆盖。

该任务闭合的是“受信 provider CLI 执行不受信目标仓库”边界，不把 Claude 的 CLI
tool-level enforcement 表述为通用 OS/container sandbox，也不声称能够约束被替换的恶意
provider 可执行文件。Codex 子命令继承其原生 sandbox；外部容器、provider-only 网络
endpoint allowlist、跨平台进程树 kill-on-close 和真实 hostile canary 仍是更高强度部署
加固，而非当前本地单用户基线已经验证的能力。

### Preview iframe sandbox

健康 Preview 仍从后端分配的独立 `127.0.0.1:<port>` 加载，右侧产物面板现在固定使用
`allow-forms allow-same-origin allow-scripts`。该集合保留 Vite module/HMR、React
交互、表单和 Preview-origin storage，同时不授予 top navigation、popup、download、
modal、pointer lock 或 presentation。因为 Web shell 与 Preview 使用不同端口，它们
仍是不同 origin；若未来改为同源反向代理，`allow-scripts + allow-same-origin` 必须
重新评审。

iframe 同时使用 `no-referrer`，并通过 Permissions Policy 明确拒绝 camera、microphone、
geolocation、payment、USB 与 clipboard。聚焦组件 9 项、完整 Web 13 files / 102 项、
ESLint 和 TypeScript 均通过；严格 OpenSpec 与独立只读复核通过。该 sandbox 不等于
浏览器网络出口控制：Preview 脚本仍可发起浏览器允许的 fetch/WebSocket/资源请求，
CSP/代理隔离不在当前本地演示任务范围内。

### Generated project dependency pinning

selected-folder provisioning 不再把 9 个前端直接依赖写成 `latest`，而是使用当前仓库
已验证快照的精确版本；生成的 `package.json` 同时声明 `pnpm@10.33.4`，避免 Corepack
在没有 package-manager 约束时自动切换到新的 pnpm 主版本。后端 requirements 现在精确
固定 FastAPI、HTTPX、Uvicorn 与 pytest；其中 HTTPX 是生成的 `TestClient` 健康测试所需
的直接依赖。既有 repairable scaffold 继续完全跳过 skeleton 写入，用户已有 manifests
不会被替换。

全新生成目录的真实 smoke 使用 Node 25.7 / pnpm 10.33.4 完成 install、TypeScript
check、Vite production build、完整 audit（0 known vulnerabilities）及 frozen-lockfile
重装；固定版本的后端健康测试为 1 passed。聚焦 provisioning 为 8 passed，相邻
provisioning/target analysis 为 26 passed，完整 API 为 1,190 passed / 2 skipped，严格
OpenSpec 通过。独立只读复核未发现明确阻断项；其输出截断限制由主代理的完整静态追踪、
生成文件断言和真实 smoke 补足。

该边界只固定生成清单的直接依赖与包管理器。首次批准安装所生成并保留的项目自身
`pnpm-lock.yaml` 才能冻结 JavaScript 传递图；Python 传递依赖锁定仍不在此单任务范围。

## 安全与产品边界

- SQLite 是演示数据库，不要求 Postgres。
- 实时链路使用 SSE，不引入 WebSocket。
- 每个 Session 恰好复用一个受控工作树，不同 Session 不共享工作树。
- adapter 只能在已分配的 Session 工作树或注册目标中运行。
- `.git/`、`.env*`、`secrets/`、`node_modules/`、系统路径和未分配主机路径受保护。
- Preview、staging build 和本地静态服务不继承控制面密钥；Codex、Claude Code、
  Claude Planner 和相关 CLI 探针只接收对应 provider 的环境配置。输出在持久化前执行
  精确敏感值与 secret assignment 脱敏。
- Agent 执行期间不安装依赖；依赖准备只发生在 setup 或明确批准的维护阶段。
- 当前子进程环境与真实适配器 containment 不等于通用外部 OS/container；Preview
  iframe sandbox、生成项目直接依赖固定和 SSE backpressure 已按独立 OpenSpec
  闭合，但这些边界不能替代更高强度的 OS/container 隔离或分布式消息总线。
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

`be48efa` 是本轮候选集之前已交付到 `origin/dev` 与 `origin/main` 的共同基线。先行候选
`fc70f29` 已在 2026-09-03 回读到 `origin/dev`，但 `origin/main` 当时仍为 `be48efa`。
最终审计随后发现其全局 Vite override 的 peer 范围污染，并完成上述收窄修正；因此
`fc70f29` 不能单独作为最终修正已交付的证据。

最终候选是否已远程交付，必须以包含当前 Browserslist/Vite 修正的 `fc70f29` 后继提交
以及 `git ls-remote` 回读为准。本地分支名、工作树测试或本状态文档都不能替代该证据，
也不能据此推断 `main` 已同步。

## 历史与维护

- 旧项目状态快照：[project-state-archive.md](history/project-state-archive.md)
- 旧变更记录：[change-log-archive.md](history/change-log-archive.md)
- 当前工程变更：[change-log.md](change-log.md)

历史文档只用于追溯当时的判断和命令输出；其中的“等待冻结”“后续任务”“正在进行”等
措辞不代表当前状态。
