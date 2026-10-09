# ScriptedMock 结构化意图路由修复

2026-10-07：`agenthub-scripted-mock-intent-routing` 1.1 已完成（本地未提交）。

## 问题与修改

旧实现对完整 instruction 搜索 title/heading/button。任务标题、历史上下文中的这些词
会覆盖真正的登录页或按钮修改意图；非空 Diff 和 completed 不能证明生成了正确功能。

现有 `planContext.target` 优先选择三个已有脚本：`login_page`、
`primary_action_button_text`、`demo_heading_text`。结构化文案修改要求非空字符串
`targetText`，不从冲突指令或 script 提示补全文案。显式未知、null、非字符串目标或
无效文案在写入前产生 `SCRIPTED_MOCK_MUTATION_FAILED`；仅没有 target 键的旧请求
保留关键词兼容路径。源文件按 UTF-8 读写，包含中文文案回归。

未扩大文件权限、执行范围或支持的脚本；沿用路径/网络限制、审批、中断、失败、
目标锁、scope 和非空 Diff 完成门禁。没有改变 Planner、QA 调度或完成判定的语义。

## 验证

- 新增回归在修改前复现关键词误选和无效结构化目标仍写入的问题。
- Adapter、Planning、Guardrails 最终 **136 passed**；实际后台引擎的
  scripted/fallback/request-boundary/completion 相关测试 **13 passed / 284 deselected**。
  合计 **149 项相关测试通过**，未重跑 API/Web 全量。
- `pnpm check`、strict OpenSpec、Git 空白检查通过。

HTTP 登录消息生成真实持久 Task；临时 Git/SQLite 夹具使用正式 ScriptedMock 和执行
引擎，检查邮箱/密码表单、保留原始标题及非空 Diff。随后在同一产品 Session 显式创建
依赖前端任务，经过真实请求构造与执行，引擎两次 scope/completion 均为 passed，第二次
仅将原按钮 Continue 改为 Sign in，保留登录表单。

测试第二次执行使用独立数据库 Session，与后台执行入口每次打开连接会话的方式一致；
最初复用前次长生命周期数据库会话触发租约不可验证，未删除、伪造或放宽租约检查。
移除 targetId/safeTarget 的负例仍在启动前失败，且无制品和文件变化。

复跑命令（工作目录 `apps/api`，Python 为仓库根 `.venv/Scripts/python.exe`）：

```text
python -m pytest tests/test_scripted_mock_adapter.py tests/test_planning.py tests/test_guardrails.py --basetemp=<独立可写临时目录> -q
python -m pytest tests/test_task_runs.py -k "scripted or fallback or agent_run_request_bounds or completion" --basetemp=<另一独立可写临时目录> -q
```

## 验收边界与后续

按钮后续修改使用显式创建的依赖前端 Task；不是普通第二条 HTTP 聊天消息完整验收。
登录计划的 QA 仍是后续动态计划的依赖，现有自动评审任务闭合逻辑仅覆盖部分 Planner；
这条依赖路径需独立修复并验收，不能将固定测试夹具视为完整聊天闭环通过。

本轮功能检查针对实际生成的源文件；引擎 `functionalAcceptance` 仍为 not_evaluated。
未启动健康 Preview、build 或部署，未调用真实 Codex/Claude，也未重新验收浏览器闭环。
未触碰用户运行数据库、Session 工作树或服务，未安装依赖、提交或推送。
