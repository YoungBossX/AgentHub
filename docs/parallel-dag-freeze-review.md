# Parallel DAG 第 5 阶段冻结审查

日期：2026-09-04。范围：`agenthub-parallel-dag-execution`，本地单用户工作区。

状态：第 5 阶段已完成；在下述本地测试适配器与回归边界内冻结。

## 实现与证据边界

- 默认共享工作树写入仍串行，线性计划保留前后依赖。新 Contract-first 计划只有显式开启
  `AGENTHUB_ISOLATED_WRITES=1` 才请求内置 Backend/Frontend 独立 execution worktree。
- DAG 就绪、Session Queue、Target Lock、审批、scope、provider 容量仍是不同门禁。
  `parallelGroup` 不授予并发权限；串行回退也不绕过 dirty/conflict gate。
- 分支只写各自 target 并保留真实 Diff；服务端候选工作树合并、prepared journal、
  clean canonical 快进、历史冲突与只重试失败分支沿用第 4 阶段实现。
- UI 依据 persisted dependencies 展示 Root/Fork/Join；按完整 UTC 时间区间展示生命周期
  重叠，不声称 provider 内部执行重叠或性能加速。未结束的运行不被补造结束时间。
- 集成制品只读投影经过服务端证据复验；`verified` 证明已纳入 canonical 历史，并不
  取代 preview/deploy 对当前 HEAD、clean worktree 和空闲状态的更严格检查。
- 历史 ready、prepared 和冲突记录与已验证集成分别展示；ready/merged 计划或 metrics
  自报不是证明。任务刷新复用现有 SSE 游标、single-flight 和有界重试。

## 本轮有界预演

这些是阻塞型测试适配器经过实际 dispatcher/scope/diff/join 链路的 Git/SQLite 演练。
所有更改发生在独立临时仓库，不调用 Codex/Claude provider，不启动真实 Vite，不做生产
部署；测试写入内容用于验证路径归属和合并，不是可运行的前后端应用成品。

| 场景 | 可核实结果 | 证据 |
|---|---|---|
| Parallel join | 2 个 adapter 区间重叠约 93 ms；独立 Diff；join 完成且 canonical HEAD 等于集成 commit | [parallel_join.json](evidence/parallel-dag-phase5/parallel_join.json) |
| 单失败分支 retry | 初次区间重叠约 94 ms；只重跑失败分支，成功 Run/Diff/hash 不变 | [failed_branch_retry.json](evidence/parallel-dag-phase5/failed_branch_retry.json) |
| Conflict retry | 初次区间重叠约 94 ms；失败候选不修改 canonical；冲突修正后重试，无分支重跑 | [conflict_retry.json](evidence/parallel-dag-phase5/conflict_retry.json) |
| 串行依赖链 | 同一共享工作树，后继 checkpoint 在前驱完成后创建，适配器区间不重叠 | [serial_control.json](evidence/parallel-dag-phase5/serial_control.json) |

毫秒值只证明受控区间存在交集；不是吞吐量或加速比 benchmark。JSON 还记录 Run/Diff IDs、
patch SHA-256、基线、merge commit、canonical 状态检查、失败恢复来源和临时目录。

证据文件 SHA-256：

```text
parallel_join.json       6A648F2EA84FDED01C2EF361274CAB3CDD602CE668E55407A41B7DF5E5CAFC90
failed_branch_retry.json 4D3FEAEE8FB5B6E7B6AAA48DD0178590109F3B063DBD3F5AE69324489861E67F
conflict_retry.json      9506F328BE102CA0D3AD794B171F5F80B9A575D2737884E14367DE88049F83BA
serial_control.json      FAA3001B562F8D5B5141A0D4B44E723A382A91547E741B5681937B09E79E2BB3
```

## 验证记录

- Web：`pnpm test:web`，109 passed（含 6 个 DAG UI 测试与 synthetic Review join 展示回归）；
  `pnpm check` 通过，最后前端增量另经完整 Web tests + eslint/tsc 验证。
- demo-api：从 `apps/demo-api` 运行 `python -m pytest`，5 passed。
- 本轮新增有界预演 4 场景及 Task API 集成证据投影测试通过。
- API 全量：**1,242 passed / 1 skipped，0 failures/errors**，683.79 秒。
  Windows 上跳过 `test_posix_exact_case_semantics_keeps_distinct_git_spelling_ordinary`
  （`exact-case POSIX semantics regression`）；不将此项算作已验证通过。
  18,360 条警告来自已有 `datetime.utcnow()` 弃用用法，未扩大本任务修复范围。
- 首次串行预演错误地预先创建两个无依赖、共享工作树写 Run；后者被 dirty gate 拦截。
  已改为有显式依赖的真实串行链，不放宽安全门禁以迁就测试。
- 首次 API 全量发现默认 AnyIO Trio 参数化失败；基础 Python 没有 Trio。临时加载此前
  已获授权安装在 Conda `agent` 中的 Trio 再复验，仍有 29 个原生 asyncio 调用失败。
  修正是统一 API 测试后端为实际支持的 asyncio（`tests/conftest.py`），不是安装新依赖、
  跳过产品用例或声明支持 Trio。旧全量运行已停止，上述结果来自重新收集的完整 asyncio 回归。
- OpenSpec strict validation 和 `git diff --check` 通过。

复现预演：从 `apps/api` 执行以下命令（Python 需具备现有 API 开发依赖）：

```powershell
$env:AGENTHUB_DAG_EVIDENCE_DIR = '<新的证据输出目录>'
python -m pytest tests/test_parallel_rehearsal.py -q -p no:cacheprovider --basetemp='<新的临时目录>'
```

日常回归使用 `pnpm check` 和 `pnpm test`。本次测试直接调用相同的 Web/API/demo-api
测试入口，避免既有 shell 包装器的自动删除步骤触及环境删除策略；没有绕过删除拒绝。

## 冻结核对与限制

- 无数据库实体迁移；新增内容只是 TaskResponse 只读字段、UI、测试与文档。
- 既有四角色与三种 adapter 保留；未引入 DAG 编辑器、WebSocket、Docker、多用户或部署平台。
- 此轮不包含真实 provider 并行演练、真实浏览器视觉验收或负载/长稳测试。
- 故障与准备态恢复、候选所有权、scope、canonical 漂移、preview/deploy 来源检查由
  API 回归验证；不声称 Git 与 SQLite 跨资源原子事务。
- 冻结验收时工作区包含第 1–5 阶段未提交更改；验收过程没有提交或推送。
  后续经用户授权保存的本地版本以 Git 日志为准，不改变本报告的测试证据边界。
- 临时目录和失败候选保留供核验；本轮不绕过此前环境删除策略。清理不作为运行成功证明。

本次测试的 5 个临时目录保留：`C:\Users\XCC\AppData\Local\Temp\agenthub-phase5-20260904-`
加后缀 `full`、`rehearsal`、`serial`、`trio`、`verified`。完整 JUnit XML 位于同一 Temp
目录的 `agenthub-phase5-20260904-verified.xml`；仓库内另保存
[验证摘要](evidence/parallel-dag-phase5/verification.json)。

任务 5.1–5.3 全部勾选。冻结验收没有启动后续任务，也没有执行提交或推送。
