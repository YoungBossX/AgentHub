## 1. OpenSpec 与范围确认

- [x] 1.1 创建 V2.3 Session Queue And DB Target Lock OpenSpec，定义范围、非目标、验收和风险。
- [x] 1.2 审查 V2.1 Durable Run Engine、P8 scheduler/target lock 和 Reliability v2 路线图。
- [x] 1.3 明确 V2.3 只处理持久 Session Queue、显式 DB Target Lock、preview/deploy 独立 job queue，不实现 ProjectProfile、Policy Engine、事务化交付或生产部署。
- [x] 1.4 验证 `git diff --check` 和 `openspec validate agenthub-v2-3-session-queue-target-lock --strict`。

## 2. 持久 Session Queue 模型

- [x] 2.1 新增或扩展最小持久模型，表示 Session 内 TaskRun queue entry、queue position、access mode、target id、等待原因和状态。
- [x] 2.2 在 TaskRun 创建、retry、auto-start 时写入 Session Queue。
- [x] 2.3 保证同 Session 写任务按 queue position 串行。
- [x] 2.4 允许同 Session readonly 任务在依赖完整、无需写锁、不会修改 worktree 时并发。
- [x] 2.5 添加测试覆盖 queue enqueue、position、写任务串行、readonly 并发和 terminal 后推进。
- [x] 2.6 更新 `docs/change-log.md`。
- [x] 2.7 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。

## 3. 显式 DB Target Lock

- [x] 3.1 新增 TargetLock 持久模型或等价存储，包含 lock key、target id、session id、task run id、worker id、lease 和释放状态。
- [x] 3.2 使用 SQLite 兼容的唯一约束、事务、条件插入或条件更新实现原子 acquire。
- [x] 3.3 在写 TaskRun 启动 adapter 前获取 TargetLock；获取失败时进入 `waiting_lock`，不得启动 adapter。
- [x] 3.4 在 terminal finalizer 中幂等 release，并校验 holder 身份防止释放后来者的锁。
- [x] 3.5 添加测试覆盖并发 acquire、失败等待、release 幂等、holder mismatch 不释放、同 target 跨 Session 串行。
- [x] 3.6 更新 `docs/change-log.md`。
- [x] 3.7 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。

## 4. Scheduler 与 Durable Run Engine 集成

- [x] 4.1 让 scheduler readiness 读取持久 queue/lock 状态，而不是只从 active TaskRun 推导软锁。
- [x] 4.2 在 Durable Run Engine claim 或执行前加入 queue/lock gate。
- [x] 4.3 保证不同 Session 在 worktree 不共享且 target lock 允许时可并发执行。
- [x] 4.4 保证 waiting approval、blocked dependency、unsafe command/path 不会绕过 queue/lock gate。
- [x] 4.5 添加测试覆盖 concurrent click、retry race、不同 Session 不同 target 并发、同 target 写冲突。
- [x] 4.6 更新 `docs/change-log.md`。
- [x] 4.7 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。

## 5. Preview/Deploy 独立 Job Queue

- [x] 5.1 新增 preview/deploy job queue 的最小持久模型或等价存储。
- [x] 5.2 编码 TaskRun 成功 finalization 后创建 preview/deploy job，而不是阻塞主执行队列。
- [x] 5.3 preview job 继续使用 Vite React 预览命令和现有端口分配边界。
- [x] 5.4 deploy job 继续创建 mock-backed deploy card，不新增真实生产部署 provider。
- [x] 5.5 确保 preview/deploy 失败只影响对应 job evidence，不覆盖编码 TaskRun 的真实 terminal 状态。
- [x] 5.6 添加测试覆盖 job enqueue、job failure evidence、编码队列不被 preview/deploy 排队阻塞、显式依赖 preview/deploy 时可等待。
- [x] 5.7 更新 `docs/change-log.md`。
- [x] 5.8 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。

## 6. Stale Queue/Lock 恢复

- [x] 6.1 在服务或 worker 启动时扫描 queued、waiting_lock、running 和 held lock。
- [x] 6.2 对 terminal TaskRun 持有的 lock 执行 stale release。
- [x] 6.3 对 lease 过期且 worker heartbeat 过期的 lock 记录 stale recovery，并释放或将 run 诚实失败化。
- [x] 6.4 恢复 queued/waiting entries 时不得重复启动 terminal run。
- [x] 6.5 添加测试覆盖服务重启后 queued 恢复、stale lock release、active lease 未过期保留、无法确认 provider 结果时不声称成功。
- [x] 6.6 更新 `docs/change-log.md`。
- [x] 6.7 验证相关 API 测试、`pnpm check`、`pnpm demo:api:test`、`git diff --check`。

## 7. 诊断、Mission Trace 与冻结审查

- [x] 7.1 在 TaskRun evidence、TaskRunEvent 或 MissionTrace 中展示 queue position、access mode、target id、lock key、holder、wait reason、release reason 和 preview/deploy job 状态。
- [x] 7.2 确保证据不泄露 secrets、API key、tokens、受保护 host paths 或未分配给当前 Session 的 host 路径。
- [x] 7.3 更新 `docs/project-state.md` 和 `docs/change-log.md`。
- [x] 7.4 创建 V2.3 freeze review 文档，记录实现范围、验证、真实限制和后续 V2.4/V2.5 依赖。
- [x] 7.5 运行完整验证：`pnpm check`、`pnpm test`、`pnpm demo:api:test`、`git diff --check`、`openspec validate agenthub-v2-3-session-queue-target-lock --strict`。
