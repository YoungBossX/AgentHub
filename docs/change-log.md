# AgentHub 变更日志

## 消息路由拆分与调度边界修复

**日期:** 2026-07-05

### 变更

- 新增 `apps/api/app/routes/messages.py`，将 Session message 读写、用户消息规划触发、自动启动安全判定从 `main.py` 拆出；`main.py` 仅挂载 `messages_router`，保留原 `/sessions/{session_id}/messages` API 行为。
- 迁移时保留 `autoStart`、`safeTarget`、目标 agent 权限和目标路径白名单校验，避免自动启动任务越过 demo target 边界。
- 修复外部项目 dirty-worktree 检查的路径坐标问题：当外部 target 位于 AgentHub 仓库子目录时，Git 返回的仓库根相对路径会先归一化为 target root 相对路径，再与计划文件比较，避免被父仓库未提交改动误判阻塞。
- 让调度器测试中的同目标写任务和 provisioned frontend run 任务显式设置 `priority`，避免同一时间戳下 UUID 排序导致“第二个任务”反向阻塞“第一个任务”的非确定性失败。
- 将 pytest `--basetemp .pytest-tmp` 生成的临时目录加入 `.gitignore`，避免测试产物进入提交候选或污染 `git status`。

### 验证

| 命令 | 结果 |
|---|---|
| `.\.venv\Scripts\python -m compileall apps\api\app` | 通过 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_chat_events.py apps\api\tests\test_planning.py apps\api\tests\test_scheduler.py -q --basetemp .pytest-tmp` | 通过，79 项测试 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_sessions.py apps\api\tests\test_external_workspaces.py apps\api\tests\test_project_provisioning.py -q --basetemp .pytest-tmp` | 通过，26 项测试 |
| `.\node_modules\.bin\tsc.cmd -p apps\web\tsconfig.json --noEmit` | 通过 |
| `git diff --check` | 通过；仅有 Windows CRLF 提示，无 whitespace 错误 |

## 对抗性审查修复与日志归档

**日期:** 2026-07-05

### 变更

- 修复 Windows 本地系统目录防护缺口：外部目标注册和本地文件夹浏览现在共用跨平台系统路径判定，并覆盖 `C:\Windows`、`Program Files`、`ProgramData` 等 Windows 根目录。
- 让 project provisioning 测试不再依赖真实 `git worktree add`：测试通过 fake worktree service 保持 HTTP API 流程，同时避免受限环境下提前失败；路径断言改为跨平台 `Path` 语义。
- 在 `pnpm-workspace.yaml` 启用 `strictDepBuilds`，并只显式允许 `esbuild`、`sharp`、`unrs-resolver` 构建脚本；README 补充依赖审批说明，避免全量 `approve-builds --all`。
- 新增 `apps/api/app/routes/sessions.py`，将 Session 创建、读取、更新、target selection 和 memory snapshot refresh 路由从 `main.py` 拆出。
- 新增 `apps/web/src/components/task-run-controls.tsx`，从任务卡片列表中拆出运行控制和审批卡片；新增 `apps/web/src/lib/api-core.ts`，集中 API URL、错误类型和错误消息解析。
- 修复 `task-card-list.tsx` 中预览制品 `Monitor` 图标缺失导入。
- 将 2026-06-10 及更早变更日志归档到 `docs/history/change-log-archive.md`，当前 `docs/change-log.md` 保留近期阶段和归档入口。

### 验证

| 命令 | 结果 |
|---|---|
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_external_workspaces.py -q --basetemp .pytest-tmp` | 通过，11 项测试 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_project_provisioning.py -q --basetemp .pytest-tmp` | 通过，8 项测试 |
| `.\.venv\Scripts\python -m compileall apps\api\app` | 通过 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_sessions.py apps\api\tests\test_external_workspaces.py apps\api\tests\test_project_provisioning.py -q --basetemp .pytest-tmp` | 通过，26 项测试 |
| `.\node_modules\.bin\tsc.cmd -p apps\web\tsconfig.json --noEmit` | 通过 |
| `pnpm --filter @agenthub/web check` | 未运行到前端检查阶段；pnpm 要求清理/重建 `node_modules`，依赖重装和构建脚本执行审批被安全策略拒绝 |
| `pnpm --filter @agenthub/web test src/components/task-card-list.test.tsx -- --runInBand` | 未运行到测试阶段；同样受 pnpm 模块目录重建审批阻塞 |

## 轻量工程拆分与代码地图同步

**日期:** 2026-07-05

### 变更

- 新增 `apps/api/app/dependencies.py`，集中 FastAPI 共享依赖和 preview/deploy service 实例，保持现有运行语义不变。
- 新增 `apps/api/app/routes/registries.py`、`apps/api/app/routes/workspaces.py` 和 `apps/api/app/routes/targets.py`，将 provider/deployment registry、demo workspace、workspace targets、外部项目分析/注册、本地文件夹浏览和 project provisioning 路由从 `main.py` 拆出。
- `apps/api/app/main.py` 改为挂载 `health`、`registries`、`targets`、`workspaces` routers，保留尚未拆分的 session/task-run/artifact/runtime-config 等主业务路由。
- 新增 `apps/web/src/components/execution-trace.tsx`，从 `task-card-list.tsx` 抽出多 Agent 执行链路展示和 trace helper，降低任务卡片组件体积。
- 更新 `docs/architecture.md`，同步当前后端 router 地图、共享依赖模块、前端 execution trace 组件和剩余技术债。

### 验证

| 命令 | 结果 |
|---|---|
| `.\.venv\Scripts\python -m compileall apps\api\app` | 通过 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_external_workspaces.py apps\api\tests\test_project_analyzer.py apps\api\tests\test_health.py apps\api\tests\test_provider_configs.py apps\api\tests\test_deployment_providers.py -q --basetemp .pytest-tmp` | 通过，23 项测试 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_project_provisioning.py -q --basetemp .pytest-tmp` | 未通过，2 passed / 6 failed；5 个 apply 用例在 session 创建响应缺少 `id` 时提前失败，1 个计划用例命中 Windows 路径分隔符断言 |
| `pnpm --filter @agenthub/web check` | 未通过；sandbox 内 npm registry 返回 `EACCES`，联网授权后依赖下载完成，但被 `ERR_PNPM_IGNORED_BUILDS` 阻止，需要显式批准 `esbuild`、`sharp`、`unrs-resolver` build scripts |
| `pnpm --filter @agenthub/web test src/components/task-card-list.test.tsx -- --runInBand` | 未运行到测试阶段；同样受 `ERR_PNPM_IGNORED_BUILDS` build-script 审批阻塞 |

> 注：本节是当时的历史验证记录。project provisioning 失败和 `ERR_PNPM_IGNORED_BUILDS` 配置缺口已在上方“对抗性审查修复与日志归档”中处理；完整前端 `pnpm check/test` 仍需用户明确批准依赖重建和第三方构建脚本执行。

## 比赛交付说明与公开入口校准

**日期:** 2026-07-05

### 变更

- 在 `README.md` 增加比赛交付看点，按评分维度映射到仓库证据和现场演示动作。
- 在 `README.md` 增加 3 分钟 Demo 路径和交付文档入口，链接演示脚本、技术架构、AGENTS、OpenSpec 和变更日志。
- 新增 `docs/demo-script.md`，作为比赛录屏、现场演示和答辩脚本，覆盖开场话术、主路径、fallback 路径、扩展路径、答辩速答和失败预案。
- 新增 `docs/architecture.md`，作为技术文档和答辩说明，覆盖核心链路、运行时组件、后端/前端代码地图、数据模型、可靠性边界、技术选型和已知技术债。
- 调整 `.gitignore`，显式放行 `docs/demo-script.md` 和 `docs/architecture.md`，让比赛交付脚本和技术文档可进入仓库。
- 修复 README 中指向不存在的 `docs/adapter-notes.md` 和 `docs/claude-code-adapter-notes.md` 的说明，改为当前真实 CLI 配置方式和适配器代码入口。
- 轻调 `index.html` 首屏文案，将公开首页定位收敛为面向比赛题面的本地可运行多 Agent 协作 Demo。
- 新增 `apps/api/app/routes/health.py` 并在 `apps/api/app/main.py` 挂载，作为 FastAPI 路由拆分的第一步；`/health` 响应行为保持不变。

### 验证

| 命令 | 结果 |
|---|---|
| `python -m compileall apps\api\app` | 通过 |
| `python -m pytest apps\api\tests\test_health.py -q` | 未通过环境收集，当前工作区没有 `.venv`，系统 Python 缺少 `fastapi` |
| `rg -n "adapter-notes|claude-code-adapter-notes" README.md index.html` | 通过，无坏链接残留 |
| `git status --short docs/demo-script.md docs/architecture.md` | 通过，两个新增文档显示为未跟踪文件而非 ignored |
| `git diff --check -- .gitignore README.md index.html apps/api/app/main.py docs/change-log.md` | 通过 |
| `rg -n "[ \t]+$" .gitignore README.md index.html apps/api/app/main.py apps/api/app/routes/__init__.py apps/api/app/routes/health.py docs/demo-script.md docs/architecture.md docs/change-log.md` | 通过，无行尾空白 |

## 历史归档

- 2026-06-10 及更早阶段详见 [docs/history/change-log-archive.md](history/change-log-archive.md)。
