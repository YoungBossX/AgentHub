# SQLite 数据库版本迁移

平台保留 SQLModel 和 SQLite；结构变更由冻结的 Alembic revision 管理。
当前 head 为 `0002_database_integrity`，初始版本 `0001_local_baseline` 保持冻结。历史 revision 不读取未来的 ORM 定义，
也不会运行 Agent、目标源码或 seed。此功能是开发者离线维护，不是 Agent 工具。

## 新环境和已有库

先安装仓库声明的 API 依赖，再启动。空库会在独占维护锁内初始化；已有 current 库
在 API 共享锁内校验后正常启动。已有无版本/过期/结构不兼容库不会自动补列，
启动在 seed、执行恢复和后台 worker 之前失败并提示离线迁移。

从仓库根执行（数据库 URL 的相对路径仍以 `apps/api` 为基准）：

```powershell
pnpm db:status
```

此命令只读；不存在的数据库及父目录不会被创建。结果包含 state、revision、head、
issues；空库/current 返回 0，可识别旧库返回 2，不兼容返回 1。无效参数也返回 2，
需同时看 JSON/错误输出。当前只支持 SQLite 文件，内存库仅用于受控内部测试。

## 升级现有数据库

1. 确认当前 shell 的 `AGENTHUB_DATABASE_URL` 和 `apps/api/.env` 指向预期库。
2. 用原版本正常中断/结束任务、停止预览和 API/其他数据库写入者，不直接改状态或删锁。
3. 选择仓库、注册 worktree 和目标项目之外的**新备份目录**，其父目录必须已存在。
4. 执行离线升级，核对结果，再启动工作区。

```powershell
pnpm db:migrate --backup-dir 'E:\Docker\AgentHub\migration-backup-new' --api-port 8000
pnpm db:status
pnpm dev:local
```

示例路径只用于说明，目录必须尚不存在，临时目录也应先配置到 `E:\Docker`。本专项不自动升级实际产品库。自定义 API 端口
必须同样传入 `--api-port`。重复对 current 库执行升级为无操作，不新增备份或重置数据。
`db:init`/`db:seed` 只初始化空库或为 current 库补缺失种子；它们不代替旧库升级。
已有 Agent 名称、启用状态、适配器、提示词，以及 Workspace 路径和分支会被保留。

## 一致性和兼容范围

迁移持有 API 共享/维护独占 OS 锁和 SQLite 写保留；用独立只读连接经 SQLite backup
API 捕获含 WAL 的已提交数据。备份核验后在另一个临时副本演练，原库按同一固定
revision 升级，逐表核对所有原列值、行标识及附件 BLOB，再提交版本。

支持现行无版本库、固定历史表定义、六组共 23 个已知补列，以及冻结的缺失表/索引。
TEXT/VARCHAR 和已知历史 server default 差异按兼容契约处理，不为统一拼写重建表。
v2 只对契约已允许的缺失外键及历史 nullable PRIMARY KEY 变体执行固定重建，
显式复制所有原列并核验原值；规范 v1 表无需重建。临时副本位于新备份目录内。
历史 ID 必须非空；不把其他随意移除的 FK 当成正常旧库。

缺少必需业务字段的两三列测试表、未知表/列/视图/触发器、同名不兼容索引、未知版本、
重复唯一值、孤立引用、非法事件序号或活动运行会被拒绝，不删除记录、不补造缺失业务值。
审计按冻结定义反查全部父子关系，包括旧 DDL 根本未声明的外键。事件按
`task_run_id, sequence` 建唯一索引；历史重复项只报告，不自动重编号。
拒绝不是数据清理任务。维护锁与写保留也不等于能阻止任意外部文件编辑器。

## 回执和失败处理

每个新备份目录包含：

- `database.sqlite3`：封存的一致数据库备份，不执行原地修改。
- `manifest.json`：源身份、原 revision、备份 SHA-256、旧值摘要。
- `0001-*.json` 等：独占新建的阶段回执，保留成功、失败或不确定的时序。

只有 `verified` 阶段代表这次升级与核验已提交完成。backup-verified 仅代表备份完成。
DDL/验证失败保留源库、备份及失败阶段，版本不能冒充成功；真实 SQLite 事务和安全
重试有专项测试，不仅依赖 Alembic 名称推断自动回滚。

若数据库 commit 已完成而完成回执无法落盘，会返回非零及 `commit-uncertain`；
此时不能当作“原库未变”。先用 status 查看实际 revision/schema，保留原回执和
备份，再决定后续处理。不会自动覆盖源库恢复，也不提供会删业务表的 downgrade。

需要核验/恢复备份时，先保留原库和全部回执：

```powershell
$migrationSnapshot = 'E:\Docker\AgentHub\migration-backup-new'
$migrationManifest = Get-Content -LiteralPath (Join-Path $migrationSnapshot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$migrationHash = (Get-FileHash -LiteralPath (Join-Path $migrationSnapshot 'database.sqlite3') -Algorithm SHA256).Hash.ToLowerInvariant()
if ($migrationHash -ne $migrationManifest.backupSha256) { throw 'Backup hash mismatch; do not restore.' }
```

将通过哈希的备份复制到一个**全新空目录**，在副本上检查 `PRAGMA integrity_check`、
旧数据摘要和版本，再演练迁移；不把副本覆盖到现有源路径，不手动删 WAL/SHM。
恢复前的备份可能仍是无版本旧库，不能通过直接 stamp head 让新 API 接受它。
真正恢复/切换产品库需要单独确认源身份、停机和路径；本专项的实现验收不做该操作。
此备份仅涵盖 SQLite；Git/worktree 文件恢复仍按[完整工作区维护流程](local-usage.md#一致备份恢复与缓存隔离)。

## 开发与回归

业务引擎对每个 SQLite 物理连接开启并确认外键。只有拥有独占迁移事务的协调器，
在固定表重建确有需要时，才在 `BEGIN IMMEDIATE` 之前设置该专用连接的外键开关，
提交或回滚后恢复；业务执行不会关闭约束。

事件追加先取得 SQLite 写保留，再读取最大序号和分配 SSE 时间游标；写保留持续到
调用方提交或回滚。stage 只刷新事件本身，新父记录由调用方显式刷新。状态、审批和
事件可在同一事务提交，避免提前刷新状态破坏完成判定。锁超时或旧 WAL 快照返回
`EVENT_WRITE_CONFLICT`，API 为 HTTP 409；事务所有者须回滚后重建事务，不能自动重跑
Provider、文件修改或部署等外部操作。

改 ORM 后必须新增经过审阅的 revision，不能重新生成已交付的 schema_v1.json 或 schema_v2.json。
裸 Alembic CLI 的 upgrade/stamp/offline SQL 被 env guard 拒绝，应使用协调器；该 guard
是应用内流程约束，不宣称限制具备任意 Python/SQL 权限的宿主操作者。

`pnpm test:api` 强制使用新外部临时数据库，即使父进程继承了产品 URL；初始化与
pytest 共用该临时库，JUnit 位于 pytest basetemp 之外。失败保留本批次证据，成功
只清理本批次的 pytest 工作目录，不触碰产品库。

旧启动补列/索引函数已由迁移替代，历史兼容 DDL 和断言转到迁移测试；不删除
Session、附件、备份、worktree 或历史验收证据。最终验证边界见[验收记录](alembic-migrations-review.md)。
