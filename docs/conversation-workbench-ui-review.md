# 对话工作台 UI 验收记录

日期：2026-10-07。范围：`agenthub-conversation-workbench-ui` 任务 1.1。
本轮仅修改前端及工程记录，未修改后端执行规则、数据库模型或适配器；没有安装依赖、提交或推送。

## PDF 与实现的对应关系

参考用户提供的《AgentHub- 多Agent协作平台设计.pdf》（3 页）与已认可的浅色工作台设计。
PDF 是产品参考材料，其平台规划不自动扩大本轮实现范围。

| PDF 要求 | 当前实现 | 验证边界 |
|---|---|---|
| 第 1 页：以聊天为核心，会话列表、多轮历史、选择 Agent | 左侧会话搜索/切换/新建与 Agent 联系人；点击联系人预填稳定 mention，显示自定义名称、头像缩写和能力 | 使用既有 Session 与 Agent API；单聊/群聊仍为既有本地视觉模式 |
| 第 1、2 页：对话内的 Diff、网页、文件卡片 | 对话内协作进度与成果摘要；独立成果视图；右侧 Diff/Preview/Review/Deployment/文档检查面板 | 卡片来自服务端真实制品；未实现二进制上传、完整文件编辑或 PPT |
| 第 2 页：分解、委派、执行和汇总过程可见 | 「对话 / 执行过程 / 成果」三个视图；实际任务依赖 SVG、最新任务状态、执行门禁/诊断详情、SSE 时间线 | 箭头仅表示依赖；保留已有运行重叠证据与限制说明，不据依赖图声称已并发 |
| 第 2 页：复制、引用、可展开产物 | 保留消息复制/引用、制品作为上下文、追问/修改/交给 Agent；面板展开/恢复 | 保留既有权限、范围、审批、重试与中断行为 |
| 第 3 页：聊天、预览和产物的展示效果 | 浅色三栏、紧凑进度、真实 Diff 红绿补丁、可选只读并排比较、可展开检查面板、窄屏抽屉 | Preview 沿用安全 iframe；本轮没有取得新健康 Preview 的浏览器证据 |

置顶/归档持久化、完整新建 Agent 选择器、消息再生成、上传/PPT、移动端原生客户端、
多用户 IM、MCP 市场与真实云部署不属于本任务。联系人能力展示不表示这些规划能力已全部可执行；
尚无独立 mention 路由的 Review/Fallback 联系人禁用。

## 数据与显示边界

- 顶部「需求 → 计划 → 执行 → Diff → 预览 → 交付」分别依据当前会话消息、任务、最新运行和制品。
  `completed` 不自动证明非空 Diff 或健康 Preview；失败重试不能被旧成功记录掩盖。
- 对话摘要只显示最新运行的制品；完整成果页保留历史制品，并标出来源 TaskRun。
  模拟部署和脚本评审保留提供方标签，不表示真实云部署或真实模型评审。
- 时间线按事件 ID 去重、每会话最多 60 条，仅展示事件类型、UTC 时间、来源任务及白名单状态。
  不展示任意 provider payload 或私有推理。SSE 同时刷新任务和消息，保留原有游标/重连机制。
- 任务、消息、制品和引用上下文按当前 Session 隔离；切换视图保留一个挂载的任务列表，
  不因重复挂载启动运行。异步客户端操作期间保持忙碌态。
- Diff 默认直接显示真实补丁；只读 Monaco 并排比较需要显式打开，加载失败时仍可查看补丁。

## 浏览器验收与来源

实际启动 Next.js 与 FastAPI，使用临时 SQLite 副本完成 UI 验收。最终浏览器展示端口
为 `3000`（Web）及 `8006`（API，历史基准副本），未停止用户原有 `8000` 服务。
浏览器操作没有在该历史基准副本中启动新 Provider 任务。

先在原有演示数据副本中创建 Session `8c1f3260-8985-4894-989c-5ee639efe881`，
发送 `@orchestrator build a login page for the demo app`，实际生成规划/前端/QA 三步计划。
执行暴露了现有后端联动缺口：

1. 确定性登录页计划未带目标绑定，Run `15d3610a-6d5e-49f2-adc5-186c6e8ef9a9`
   在 CLI 执行前以 `TASK_RUN_SCOPE_UNVERIFIABLE` 失败。界面显示失败、后续 QA 受阻和队列事件。
2. 仅为继续诊断，在**临时数据副本**中给前端/QA 任务计划补上 `demo-frontend` 的 `targetId`。
   没有手工写入成功状态、scope 结果、Diff 或 Preview。显式 ScriptedMock 重试仍被工作树脏状态阻塞：
   Windows `node_modules` 符号链接被 Git 报为未跟踪文件。随后通过 UI 中断，保留真实中断结果。

移除这两个测试工作树依赖符号链接的操作被自动审批审查拒绝，仅返回“被策略阻止”，
没有具体原因；链接保持原样。本任务未放宽执行/受保护路径规则来绕过这些问题。

成果视觉验收改用既有真实 Windows Codex 基准数据库的副本：
`agenthub-windows-sandbox-fixed-suite-20261007/benchmark.sqlite3`。
Session `c346a0a2-fcc3-4a59-8f63-347d768f36cb`、
Run `582527fa-1112-48f1-9c51-ce76dca304e6` 的 `src/domain.mjs` 真实变更为 1 文件、+1/-1。
这是历史真实运行的 UI 展示，**本轮没有重新运行三项基准或取得新的真实 Provider 成功**。
其中 Review 是 `scripted_mock`，界面明确标注。健康预览/部署没有记录，进度保持待完成。

服务恢复时曾错误使用无前缀 `DATABASE_URL`，短暂启动了默认数据库上的既有初始化/seed，
没有发送任务/写文件请求；发现 Session 404 后即停止，改用正确的 `AGENTHUB_DATABASE_URL`。
因此不声称整个验收期间默认数据库零触碰。最终截图与制品比较均来自正确临时基准副本。

| 截图 | 验收内容 |
|---|---|
| [桌面工作台](evidence/conversation-workbench/agenthub-workbench-desktop.jpg) | 1440×900，对话摘要、联系人、真实 Diff 补丁 |
| [执行过程](evidence/conversation-workbench/agenthub-workbench-process.jpg) | 实际任务依赖与执行卡片；本历史基准仅有一个任务 |
| [实时失败过程](evidence/conversation-workbench/agenthub-process-failure.jpg) | 临时演示会话三步依赖、失败/受阻与队列事件（收尾样式调整前） |
| [展开成果](evidence/conversation-workbench/agenthub-result-expanded.jpg) | 1440×900，展开与恢复布局 |
| [移动宽度](evidence/conversation-workbench/agenthub-workbench-mobile.jpg) | 390×844，成果与输入框可达；DOM 实测页面宽度为 390，无整体横向溢出 |

另实际检查了窄屏会话抽屉开/关、成果开/关、空成果面板关闭及三个视图切换。
图片是浏览器实际截屏，未生成假数据或编辑截图。来源、源码和截图哈希见
[机器记录](evidence/conversation-workbench/ui-validation.json)。

## 自动验证

- Web 全量：**16 files / 143 passed**。覆盖最新/历史证据、非空 Diff、Preview 健康、fork/join 图、
  非法依赖/循环、事件字段白名单、SSE 去重/数量上限、消息刷新、跨会话引用隔离、面板及既有回归。
- `pnpm check`：Web ESLint/TypeScript、API compileall、Demo TypeScript、Demo API compileall 全部通过。
- 本轮未修改后端代码，没有重跑 API 全量；没有执行新的生产 build 或完整健康 Preview 闭环。
- strict OpenSpec 与 Git 空白检查在任务关闭时通过。开发工作区包含前几轮未提交修改，未在本轮提交/推送。
- Next.js dev 自动生成了 Web 的 `AGENTS.md` / `CLAUDE.md` 和 dev 类型引用；这些不计为产品功能。

## 后续单任务

下一项应单独修复确定性计划的目标绑定和 Windows 依赖符号链接对工作树干净状态的影响，
并执行一次新的「聊天 → 计划 → 执行 → 非空 Diff → 健康 Preview」浏览器验收。
本轮只记录缺口，没有开始第二项 OpenSpec 实现。
