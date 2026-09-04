## 1. 显式且兼容的 DAG 语义

- [x] 1.1 让任务图元数据和持久 Task 依赖支持缺省串行、显式 root 和显式 fork/join。
- [x] 1.2 让 Contract-first 计划生成 `Planning -> {Backend, Frontend} -> Review/QA`，并记录并行组提示。
- [x] 1.3 拒绝未知、前向和自依赖，同时保留既有线性 Planner 回归行为。
- [x] 1.4 添加聚焦测试，更新 `docs/change-log.md`，运行 API 定向测试、`pnpm check`、
  `git diff --check` 和严格 OpenSpec 验证。

## 2. 有界并发 Dispatcher

- [x] 2.1 为安全 ready TaskRun 添加原子 claim 的本地有界并发 dispatcher。
- [x] 2.2 保留 provider 容量、审批、Session Queue、Target Lock 和 conflict gates。
- [x] 2.3 使用阻塞型测试适配器证明允许并发的运行区间真实重叠，并证明串行场景不重叠。

## 3. 同 Session 写任务隔离

- [x] 3.1 为并行写节点设计并实现独立 execution worktree/branch，不共享可变写目录。
- [x] 3.2 每个分支独立记录基线、Diff、commit/patch、终态和重试历史。
- [x] 3.3 在隔离和归属无法证明时保持保守串行。

## 4. Join、合并与冲突恢复

- [x] 4.1 仅在所有必需分支完成后启动 join/integration 节点。
- [x] 4.2 对无冲突分支执行确定性合并，对冲突生成可审计 Conflict Artifact。
- [x] 4.3 支持只重试失败分支，并保留已成功分支证据。

## 5. UI、诊断与冻结

- [x] 5.1 在现有任务图/执行轨迹中显示串行、fork、join、并行组和安全门禁等待原因。
- [x] 5.2 运行有边界的并行 DAG rehearsal，记录执行重叠、分支 Diff、join 和失败恢复证据。
- [x] 5.3 完成完整回归、文档同步和冻结审查。
