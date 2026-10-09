# 评审依赖与后续聊天衔接修复

2026-10-07：`agenthub-review-dependency-handoff` 1.1 已完成（本地未提交）。

## 问题与修改

完成代码修改后，引擎生成建议性质的 Review 制品；原来的评审任务闭合逻辑只覆盖
contract_first_v1/llm_v1，遗漏 deterministic_login_v1/dynamic_manager_v1。
登录 QA 一直 pending，使普通后续聊天被当作仍需等待的活动计划。

扩展既有闭合机制，要求每个依赖属于同一产品 Session、最新 TaskRun 已完成，且最新
Review 引用该运行的 Diff 制品。已有显式 TaskRun 的评审任务保留执行路径，不用生成
报告覆盖其状态。计划保存 reviewSatisfaction，包含 task/run/review/diff ID、Adapter
和原始报告 verdict。报告的 warning/failed 不改成 passed；任务完成只表示建议报告
已生成，不表示功能正确，也不伪造 QA Agent 的执行记录。

动态修改 autoStart 任务加入既有受调度门禁约束的后续启动路径，使登录完成前发送的
修改也能在 QA 依赖解除后启动。新用户消息规划前核对既有待评审任务与持久报告，
恢复旧代码遗漏的 QA；只读请求不触发恢复，不迁移或改写已完成 TaskRun 的历史证据。

实际 Dispatcher 验收还发现完成围栏的验证读取会触发 ORM autoflush：过期父对象查询
先刷写 completed，再检查 collecting_diff 状态历史，造成正常执行被误拒绝。验证读取
增加 db.no_autoflush，保留原始 durable identity、queue、target lock、lease 和
supervisor generation 校验，未删除或放宽失败判定。

## 验证与证据边界

临时 Git/SQLite 夹具发送真实 HTTP 登录消息，执行正式 ScriptedMock；随后普通 HTTP
消息“把按钮文案改成 Sign in”经过真实 Planner、自动启动、Dispatcher/执行引擎。
分别验证登录完成后发送、登录 TaskRun 排队且尚未启动 Adapter 时发送、旧代码遗留
pending QA 但已有报告时发送三种场景。第一种生成新的已完成规划步骤，第二种等待
原 QA 再自动续接，第三种先恢复旧 QA；未人工构造后续 Task。排队场景不是 Provider
正在写文件时的并发发送证明。

生成邮箱/密码表单且保留标题，第二次仅改按钮；两次 scope/completion 为 passed，
有真实非空匹配 Diff。QA/Review 状态、原报告 verdict、来源引用通过 API/数据库读取
验证，未为报告满足的 QA/Review 伪造 TaskRun。

四类 Planner 各覆盖 passed/warning/failed、缺失 Review、非 Diff 引用、其他运行的
Diff、新运行缺报告、新运行失败、跨 Session 依赖、显式评审运行，共 40 项证据测试。
完成围栏 30 项回归包括租约过期、执行代次替换、中断、队列状态错配与回滚失败。

- TaskRun 的 finalizer/planned-review/pipeline/completion/fallback 回归：**81 passed**。
- 最终完整 Planning/HTTP 聊天回归：**60 passed**，包含新增的旧 QA 恢复场景。
- Planning/ScriptedMock/Scheduler/External Review/DAG 基础回归：**122 passed**；
  其中 Planning 58 项已被最终的 60 项复验覆盖，其余 64 项通过。TaskRun 81 项也在
  收尾后复验。合计 **205 项相关测试通过**，不重复累计复跑项。
- `pnpm check`、最终 `pnpm check:api`、strict OpenSpec 和空白检查通过。

复跑命令（工作目录 apps/api，Python 为仓库根 .venv/Scripts/python.exe）：

```text
python -m pytest tests/test_planning.py tests/test_scripted_mock_adapter.py tests/test_scheduler.py tests/test_external_reviews.py tests/test_dag_integration.py --basetemp=<独立可写临时目录> -q
python -m pytest tests/test_task_runs.py -k "finalizer or planned_review_is_satisfied or pipeline or completion or fallback" --basetemp=<另一独立可写临时目录> -q
```

验证使用真实本地文件/Git Diff 和正式脚本适配器，后台数据库入口重定向到隔离夹具，
不是运行中的用户服务。未调用真实 Codex/Claude，未启动健康 Preview/build/部署，
未完成新的浏览器闭环；functionalAcceptance 仍为 not_evaluated。后续应独立验收
新会话聊天至健康 Preview 的实际浏览器过程。

未安装依赖，未触碰用户数据库或既有 Session 工作树，未提交或推送。
