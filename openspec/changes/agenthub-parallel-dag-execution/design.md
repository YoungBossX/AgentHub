## 总体设计

并行能力由三层共同决定，而不是由单个 `parallelGroup` 字段决定：

```text
Declared DAG readiness
  -> Session Queue / Target Lock / Conflict gates
  -> bounded dispatcher claim
  -> isolated execution and deterministic join
```

依赖图回答“哪些节点逻辑上可以同时运行”；queue、lock、审批和冲突检查回答“这些节点
当前是否安全”；dispatcher 只启动同时满足两类条件的 TaskRun。

## 兼容依赖语义

`TaskGraphTaskSpec.plan` 使用以下规则：

- 没有 `dependsOn` 键：保留旧的线性默认值，除首节点外依赖前一节点；
- `dependsOn: []`：显式 root，不自动依赖前一节点；
- `dependsOn: [key, ...]`：依赖列出的所有先前节点；
- 依赖必须引用当前拓扑顺序中更早的节点，拒绝未知、前向或自依赖；
- `parallelGroup` 是展示和诊断元数据，不能替代依赖，也不能绕过运行门禁。

该兼容规则避免把登录页、动态前端修改、直接分派等既有串行路径意外变成并行。

## 第一阶段任务图

Contract-first 计划改为：

```text
Planning
  |-- Backend  (parallelGroup=contract-implementation)
  `-- Frontend (parallelGroup=contract-implementation)

Backend + Frontend -> Review/QA
```

Planning 是 synthetic completed 节点，因此 Backend 和 Frontend 在依赖层可以同时 ready。
当前 V2.3 Session Queue 仍会保守串行化同 Session 写 TaskRun；第一阶段必须诚实展示为
queue/lock 等待，而不能把 DAG ready 表述为 adapter 已并发执行。

## 有界并发 Dispatcher

本地后台入口使用一个默认并发度为 2 的 dispatcher。dispatcher 先重新运行完整 scheduler
和 Session Queue gate，再通过 TaskRun `state + runner_id` 条件更新竞争持久化 claim；每个
获胜 TaskRun 使用独立数据库 Session 进入既有 `execute_task_run_background` 路径。执行前
仍会再次检查 scheduler、queue 和 target lock，因此 gate 与 claim 之间发生状态变化时
保持 fail closed。

同一批 claim 使用 `asyncio.gather` 并发等待，但不会共享 SQLModel Session。没有跨过执行
门禁的 claim 会被释放，并保留 `run.claim_released` 事件；一次 drain 不会立即重试同一
TaskRun，避免阻塞条件下忙循环。provider resolution、health 和 capacity lease 仍由既有
执行路径负责，dispatcher 不自行伪造或绕过 provider 可用性。

共享同一 Session worktree 的写任务仍由 write queue 串行化。隔离写例外必须满足下述
第三阶段的实际 Git 归属验证，不能只依赖计划字段。

## 第三阶段：显式隔离写分支

- 默认保留完整串行 demo。启动 API 前设置 `AGENTHUB_ISOLATED_WRITES=1`，只对新建
  Contract-first Backend/Frontend 计划增加 `executionMode=isolated_write`。单个任务可
  使用同一显式计划字段；`parallelGroup` 仍不授予并发权限。
- 仅支持 `demo-backend`、`demo-frontend` 写任务。保留 canonical Session worktree；
  每个 TaskRun 在其同级 `.executions-<session UUID>/<run UUID>` 获得独立工作树和
  `codex/agenthub-execution/<session UUID>/<run UUID>` 分支。
- 只从干净、可证明 Git 根目录归属的 Session HEAD 创建分支。不复制未提交改动，
  不安装依赖，不共享可变执行目录。未启用、非内置 target、脏基线或预检无法证明
  归属时保守使用原串行路径；若原 scheduler/conflict gate 拒绝，则继续拒绝执行。
- `TaskRun.metrics.executionWorktree` 持久化 owner、target、canonical/execution 路径、
  branch、baseCommit、previousRunId 和 unmerged 状态。执行前和 Diff 采集前核对
  UUID 推导路径、Git common dir、注册工作树、当前 branch 与 HEAD；不接受元数据自证。
- write queue 仅允许两个已验证独立、同基线且不同 target 的分支互相越过；其他组合
  继续 FIFO，同 target 写锁、审批、provider 容量、作用域校验不放宽。运行中的 queue
  entry 在 sibling 完成触发的调度刷新中不得回退为 ready。
- 分支产物使用现有 TaskRun + Diff/Artifact 持久化真实 patch（不由 adapter 提交 Git）。
  终态、基线和重试关联各自独立；失败目录保留，未经 scope 验证的失败输出不冒充
  已验证 Diff。隔离重试从相同基线分配新分支，记录 `executionRetry.strategy`，保留原
  分支/产物；原归属或基线漂移时失败关闭，不退回共享路径。
- 没有可验证的集成制品时，隔离分支仍视为未集成；不能把两个 completed 分支直接
  声明为全栈交付完成。第四阶段集成规则见下文。
- 这是本地进程并发，不替代 provider 配额或安全沙箱。真实 provider 能否同时执行仍
  受既有容量限制；并发证明使用阻塞型测试适配器实际写文件，不声称真实 Codex 成功。

## 第四阶段：Join、确定性合并和恢复

- Join coordinator 是现有 Review/QA join 前的服务端步骤，不新增角色或通用 DAG 编辑器。
  所有声明依赖必须属于同一 Session 且已完成；每个写分支仅选择最新 completed TaskRun，
  旧 failed/interrupted 尝试不参与合并。一个分支未完成时不开始集成。
- 使用现有 Artifact 持久化 `integration` / `conflict` 制品，不新增数据库模型。分支按
  `(Task.priority, Task.id)` 固定顺序应用；记录 sourceRunIds、Diff ID、patch SHA-256、
  sourceHead、mergeCommit、changedFiles 和独立 candidate worktree 路径。
- 先验证分支工作树归属、scope guard 和 Diff baseline/owner，再从干净 canonical HEAD
  创建 `.integrations-<session UUID>/<artifact UUID>` 隔离工作树。通过二进制 UTF-8 stdin
  向 Git 传入 patch，避免 Windows CRLF 管道转换；应用前后都校验 target paths，拒绝
  受保护路径、symlink 和 submodule。`git apply --3way --index` 只发生在候选工作树。
- 候选通过后由服务端创建本地 integration commit（禁用 hooks/签名）；先持久化
  `prepared` 制品，再以 SQLite `BEGIN IMMEDIATE` 排他写事务重新核对 inputs、Session
  路径和活动执行，最后 `git merge --ff-only` 更新 canonical。不会 reset、覆盖脏用户文件、
  修改分支原产物或推送远端。此运行时提交不等于提交 AgentHub 开发工作区改动。
- Git 与 SQLite 不声称跨资源原子事务：prepared journal 能恢复“快进完成、ready 未写入”
  的中断；恢复时验证 canonical HEAD 和候选 commit/parent/目录，再确认 ready，不重复合并。
  多 coordinator 竞争受数据库写锁和 prepared/ready 检查约束。主目录漂移会拒绝推广。
- 冲突仅留在独立候选中，创建可审计 Conflict Artifact；同输入/同 HEAD 不自动忙重试。
  活动执行导致的等待不伪造冲突。`POST /tasks/{joinTaskId}/integration/retry` 提供有界重试；
  失败分支沿用现有 TaskRun retry，成功分支的 Run/Diff 不重复执行或覆盖。
- Scheduler 只接受已验证 integration artifact，不接受 `integrationStatus=merged` 自报。
  集成成功后既有 Review/QA 才能满足依赖。Dispatcher 启动时也扫描恢复，避免仅依赖
  最后一个 adapter 的完成回调。串行场景没有 isolated outputs 时不触发集成流程。
- 隔离分支的 preview/deploy 从已验证且干净的 canonical 集成结果读取，不从单分支目录
  读取；Preview 与 Deployment 记录 integration commit，拒绝不匹配当前集成的旧 Preview。
  既有 provider、scope、健康检查和 staging gates 继续生效。不声称测试替身等于真实预览。

## 第五阶段：UI 诊断与有界预演

- 任务列表添加按持久化依赖推导的 Root/Fork/Join 摘要；线性依赖链保留串行标签。
  并行组只是提示。展示已分配隔离分支、串行回退原因、scheduler/queue gate 和 provider
  错误；不由前端字段推导执行授权。
- Task API 只读投影 integration/conflict 制品，隐藏候选宿主目录。ready 制品必须通过
  服务端证据复验才标记 verified；历史 ready、prepared 和冲突分别展示。既有 SSE 任意
  持久事件均触发任务刷新，因此复用原有 single-flight/retry/reconnect 路径。
- UI 仅从完整 startedAt/endedAt 显示 TaskRun 生命周期重叠；无时区时间按 UTC 解析。
  不把生命周期区间当作 provider 内部执行或性能加速证明。测试预演另外记录 adapter
  内部单调时钟区间、真实文件写入、Diff 哈希和集成 commit。
- 预演覆盖 parallel join、单失败分支重试、conflict retry 和串行依赖链对照。全部在
  临时仓库/SQLite 中运行，不调用真实 provider、预览服务或生产部署，不修改真实 Session。
- API 测试显式使用 asyncio 后端，与 dispatcher/SSE/CLI 实现一致。安装 Trio 并不使
  asyncio.create_task 等原生调用获得跨运行时兼容性。

## 实现阶段回顾

后续任务按顺序实现：

1. 已完成有界 dispatcher：原子 claim 多个安全 ready 节点，并以阻塞测试证明执行重叠；
2. 第三阶段隔离写执行：同 Session 的并行写节点使用独立 execution worktree/branch；
3. join/finalizer：每个分支独立产出 Diff/commit/patch，集成节点确定性合并；
4. 冲突与恢复：冲突生成可审计制品，失败分支可单独 retry，成功分支不重复执行；
5. UI 与预演：显示 fork/join、运行重叠、等待原因和最终合并证据。

共享工作树和归属不明的写执行始终保留 FIFO。

## 风险与控制

- **隐式行为漂移**：缺省 `dependsOn` 保持串行，并增加回归测试。
- **错误 DAG fail-open**：PlanValidator 拒绝未知和非先前依赖。
- **parallelGroup 被误当授权**：调度器不使用它绕过 queue/lock/conflict。
- **共享 worktree 污染**：隔离阶段完成前，同 Session 写任务继续串行。
- **虚假并发声明**：只有阻塞 adapter 测试或真实 rehearsal 证明时间重叠后，才声明执行并发。
