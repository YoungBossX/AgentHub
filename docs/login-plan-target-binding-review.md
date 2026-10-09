# 登录页计划目标绑定修复

2026-10-07：`agenthub-login-plan-target-binding` 1.1 已完成（本地未提交）。

## 问题与修改

确定性登录页计划的 `planDraft` 根据文件列表推断出 `demo-frontend`，但实际
frontend/QA Task plan 没有 `targetId` 或 `safeTarget`。执行引擎不能以展示用推断
代替执行绑定，因此写任务在 Adapter 启动前正确失败为 `TASK_RUN_SCOPE_UNVERIFIABLE`。

`planning_tasks.py` 从现有注册表解析内置 Demo Frontend，使用其注册允许路径生成
`safeTarget` 与前端文件列表，并在 frontend/QA task specs 中持久化 `targetId`。
任务图也随之记录目标。三步串行依赖、合成规划完成、QA 只读语义、预期制品及
现有 target lock/scope/完成门禁保持原有行为；没有增加调度默认授权或修改受保护路径。
没有迁移、重写既有任务；验证和后续使用应新建计划。

## 验证

- 修复前新增/加强的两项回归均失败：HTTP 持久计划缺少 `targetId`，实际执行报
  `TASK_RUN_SCOPE_UNVERIFIABLE`，复现此前浏览器暴露的问题。
- 规划、调度、P18b 有界演练、ScriptedMock 回归 **90 passed**。
- TaskRun 的 scope/completion/target_lock 相关回归 **96 passed / 201 deselected**。
  本轮合计 **186 passed**，没有重跑 API 全量或 Web 全量测试。
- `pnpm check` 通过 Web ESLint/TypeScript、API compileall、Demo TypeScript 和
  Demo API compileall。仅在检查进程 PATH 加入已安装的 Git Bash 路径。
- strict OpenSpec 与 Git 空白检查通过。

执行回归从 HTTP 聊天消息生成并持久化计划，使用临时 Git 夹具和内存 SQLite，
显式选择真实 ScriptedMock 实现，通过实际后台执行引擎产生 `App.tsx` 文件变化与
非空 Diff；持久化 scope 和 completion 两个门禁均为 passed。
缺失绑定负例移除任务 `targetId`/`safeTarget` 后仍失败，且没有制品或文件变化。
测试夹具没有依赖链接，未触碰用户已有数据库、Session 工作树或运行服务。

复跑命令（工作目录 `apps/api`，Python 为根目录 `.venv/Scripts/python.exe`）：

```text
python -m pytest tests/test_planning.py tests/test_scheduler.py tests/test_p18b_workflow_rehearsal.py tests/test_scripted_mock_adapter.py --basetemp=<独立可写临时目录> -q
python -m pytest tests/test_task_runs.py -k "scope or completion or target_lock" --basetemp=<另一独立可写临时目录> -q
```

## 剩余边界

本轮没有调用真实 Codex/Claude，没有启动 Preview/build/部署，也没有取得完整浏览器
闭环成功。`completionValidation.functionalAcceptance=not_evaluated`；有变更不等于
功能正确。

这次实际 ScriptedMock 输出未生成登录表单：`_apply_mutation` 对完整指令做关键词
匹配，出现 `title` 时优先选择标题变更。当前集成回归仅验收目标绑定、执行门禁和
真实 Diff，没有将该输出计为登录页功能通过。此问题应独立修复，以结构化任务意图
选择脚本并验收表单和第二次修改。

Windows 初始化依赖符号链接被 Git 视为未跟踪、导致工作树脏状态阻塞的问题也仍待
独立修复。本轮未修改依赖链接或忽略规则，未安装依赖、提交或推送开发工作区。
