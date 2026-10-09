# 外部编码任务基准

这是三个固定的小型合成任务，验证现有编码执行链路与验收证据。它不是通用代码能力榜单，也不是生产项目负载。

| 任务 | 目标 | 固定验收 |
|---|---|---|
| `title-normalization` | 修复标题 slug 规范化 | 分隔符、Unicode、空值，3 项 Node 测试 |
| `invoice-discount` | 添加整分折扣计算与输入验证 | 最终舍入、默认值、非法整数/溢出、输入不变，4 项测试 |
| `catalog-search` | 添加标题/作者搜索 | 大小写/空白、中文、顺序/对象身份，3 项测试 |

所有目标都是独立注册的 Vite React 夹具，只允许修改 `src/domain.mjs`。React 页面使用该函数；本轮验收只运行不需要依赖的 Node 内置测试，不安装依赖、不启动网页、不声明 build/视觉通过。

从仓库根目录在 PowerShell 中运行，使用现有 virtualenv、Git 与 Node 22.13+：

```powershell
$benchmarkRun = Join-Path $env:TEMP ("agenthub-benchmark-" + [guid]::NewGuid())
Push-Location apps/api
& ..\..\.venv\Scripts\python.exe -m app.external_benchmark --output $benchmarkRun --prepare-only
Pop-Location
```

每次运行必须使用新的外部目录；已存在的目录、仓库内部目录与系统路径会被拒绝，不会清理或覆盖历史结果。准备模式验证每个原始实现确实未通过验收，不调用 Provider。

先用一个小任务确认真实执行环境：

```powershell
$benchmarkRun = Join-Path $env:TEMP ("agenthub-benchmark-" + [guid]::NewGuid())
Push-Location apps/api
& ..\..\.venv\Scripts\python.exe -m app.external_benchmark --output $benchmarkRun --case title-normalization
Pop-Location
```

去掉 `--case` 可运行全部三项。真实模式使用既有 `CodexAdapter` 和现有 `CODEX_CLI_PATH` 配置，不自动切换到 Mock。授权、配额、权限或环境错误保留在真实 TaskRun 和报告中；CLI 非零退出表示至少一个案例未通过。每个 TaskRun 沿用适配器 600 秒运行上限。

输出包括 `report.json`、独立 `benchmark.sqlite3`、三个外部 Git 基线与目标文件，以及放在目标之外的不可由 Agent 修改的验收脚本。Git 提交只用于这些新夹具的基线，不提交或推送 AgentHub 开发仓库。

报告保存源码与任务输入哈希、失败基线、真实 TaskRun 状态、Provider 事件 ID、快照/记忆 receipt、作用域、Diff、制品、功能测试及失败门禁。仅有 `completed` 标签、回答中的代码或测试退出零都不够：实际成功还要求观察到 Provider thread/turn、功能测试通过、验收脚本/脚手架未改、规则 receipt 完整、作用域通过以及非空且匹配工作树的 Diff。计时是整个执行尝试的时间，不是模型推理耗时或加速证明。

准备模式的 `successRate` 为 `null`。真实模式分母是本次选择的全部案例，包含失败和尚未尝试的案例。不同输入版本、不同输出目录的结果分别保留，不使用历史通过记录替代新运行。

本基准从固定 Task plan 开始，未验证 LLM Planner、聊天界面、多 Agent DAG、Preview 或部署，也未自动断言模型或上游服务身份。测试代码使用的明确替身只验证报告逻辑和执行接入，不属于真实 Provider 结果。

验收进程使用 Node Permission Model，只授予夹具和验收目录读取，不授予文件写入或子进程；执行后再次核对不可变文件与 Diff，并要求完整测试数量通过。该权限模型用于减少意外访问，不是敌对代码沙箱，边界依据 [Node 22 官方说明](https://nodejs.org/download/release/v22.19.0/docs/api/permissions.html)。
