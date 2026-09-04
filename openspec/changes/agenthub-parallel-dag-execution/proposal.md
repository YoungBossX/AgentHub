## 为什么

AgentHub 已具备依赖调度、Session Queue 和 Target Lock，但确定性 Planner 仍把任务
按数组位置连接成线性链，`parallelGroup` 也没有可执行语义。这使本应独立的 Backend
和 Frontend 节点无法表达为 fork/join DAG，同时又缺少一个明确规则来保证既有串行
场景不会被误改成并行。

## 变更内容

- 引入向后兼容的显式依赖语义：缺省依赖继续串行，显式空依赖创建 root，显式多依赖
  创建 join。
- 让 Contract-first 计划表达 `Planning -> {Backend, Frontend} -> Review/QA`。
- 保留 Session Queue、Target Lock、冲突检测和审批作为最终运行门禁。
- 后续任务再分别实现有界并发 dispatcher、隔离写分支、集成合并和冲突处理；在这些
  边界完成前，不声称同 Session 写任务已经并发执行。

## 能力

### 新能力

- `parallel-dag-execution`：兼容串行默认值的 fork/join 任务图、受门禁约束的并行就绪、
  有界并发执行和后续隔离合并路径。

### 修改后的能力

- `scheduler`：继续以声明依赖为权威，并保留现有 queue/lock/conflict 安全边界。

## 影响

- 后端：`task_graph_builder.py`、Planner 任务持久化、后续 dispatcher/worktree/finalizer。
- 前端：后续执行轨迹可显示串行、fork、join 和阻塞原因。
- 测试：任务图兼容性、fork/join readiness、真实执行重叠、失败传播和冲突恢复。
- 文档：`docs/change-log.md` 和任务完成后的项目状态/冻结证据。

本变更不引入多用户 IM、WebSocket、Docker、生产部署、provider marketplace 或分布式
worker 集群。
