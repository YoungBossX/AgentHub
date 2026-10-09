# 多 Agent 自动执行验收

范围：`agenthub-group-auto-execution` 1.1。本地单用户、SQLite/SSE，
复用现有 Session Worktree、Queue、Target Lock、provider 容量和执行围栏。
本项不包含最终聚合回复。

## 行为

- 新多 @ 组默认 `groupAssignment.execution=automatic`、`autoStart=true`。
  `context.groupExecution=manual` 显式保留手动模式，历史任务不会被改写。
- Dispatcher 在依赖就绪后创建各自 TaskRun。写入串行执行，指定评审独立只读运行，
  编码任务的脚本报告不能代替它。续接先释放上游 provider 容量。
- 首次创建在 SQLite writer lock 下检查历史，阻止并发 dispatcher／手动启动重复创建。
  失败、中断仍需显式重试，成功后恢复依赖续接。
- 本地 service loop 在重启、目标锁释放后重新检查持久化自动组。准备拒绝停用该任务
  自动启动，并保留协调器诊断；下游拒绝附带持久化 SSE 唤醒事件。
- 竞争 worker 先跳过被有效领取的 queued TaskRun，避免改写启动前被冻结的任务快照。
  原生评审允许整段单一 JSON 代码块，仍校验绑定标识、实际完整 Read、文件版本、
  判断一致性和原始输出哈希；补强必填绑定标识的指令。

## 真实执行

最终新会话 `21afb96a-37c3-47b5-8f39-8d5f5d8d1984` 仅发送一条多 @ 消息，
没有逐任务启动请求。真实 Claude CLI Planner 给出整组内容，Claude 编码与指定
Claude Read-only 评审自动先后完成，各只有一次运行。实际按钮为
`Automatic Group 20261008`，编码 Diff 非空，评审完整 Read 文件哈希与最终代码一致。
浏览器显示自动启动说明、两项任务和模型报告；刷新保留历史且未增加运行。

开发演练的失败均保留：首次竞争 dispatcher 改写快照触发租约围栏；随后真实评审
先返回代码块，再遗漏绑定标识，被诚实拒绝。不得把这些失败计为成功，不能用脚本
或服务端填字段替代原生结果。最终通过的会话使用修复后代码和新原生执行。

服务启动续接会话 `b73f3e52-8694-4cd6-8231-ed6e2e44b9fa` 在关闭 API 后，
通过实际 Planner 持久化自动组，刻意不创建 TaskRun，模拟计划提交后服务停止的边界。
启动相同数据库的 API 后，service loop 自动执行真实 Claude 修改及独立只读脚本 QA，
两项任务各只有一次运行。这里的 QA 是脚本评审，不是原生模型评估；该场景没有
证明恢复正在执行的 CLI。最终原生组重启后同样保留两项运行、报告和源文件哈希。
有限 SSE 重放各只有一次 claim/completed，原生 receipt 一致，Last-Event-ID 跳过旧帧。

定向 API **106 passed**（112.52 秒）；Web **168 passed / 20 files**。
最终全量 API **1,620 passed / 1 POSIX-only skipped**（933.83 秒），
`pnpm check`、strict OpenSpec、Git 空白检查和归档源码/证据哈希通过。
两次停止的早期全量运行不计为通过。

证据入口：[索引](evidence/group-auto-execution/validation-index.json)、
[原生运行](evidence/group-auto-execution/runtime.json)、
[启动恢复](evidence/group-auto-execution/startup.json)、
[历史与 SSE](evidence/group-auto-execution/history.json)。

静态模型评审没有运行测试，`passed` 是模型判断；CLI 平台不证明底层模型厂商。
本项没有验收 Preview／部署，没有安装依赖、提交或推送。
