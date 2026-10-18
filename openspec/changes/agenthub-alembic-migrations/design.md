# Alembic 数据库迁移设计

状态：2026-10-18 用户已审核设计及书面计划，选择 Native 顺序实施；本地验收完成。本文不代表实际产品库已经升级。
类型：架构变更。只处理本地单用户 SQLite 的结构版本管理及被替代代码清理。

## 1. 目标与已核对基线

用户要求开始 Alembic 迁移，兼容已有数据库、保留已有数据，并清理旧垃圾。
本设计将“旧垃圾”限定为此次迁移实际替代的代码、测试调用和当前使用说明；
数据库、附件、会话、Git/worktree、备份及历史证据不属于垃圾。

核对代码版本 `ea0d3bc`：

- `apps/api/app/db.py` 的 `create_db_and_tables` 先 `SQLModel.metadata.create_all`，
  再补列和索引；无 Alembic revision。
- 兼容补列涉及 message、session、externalprojecttarget、artifactversion、taskrun、
  agentprofiledraft；索引涉及 message、taskrunevent、agentprofiledraft。
- `apps/api/app/main.py` 在 API 全生命周期持有 SQLite 共享维护锁；
  `maintenance_lease.py` 已提供 Windows/POSIX 跨进程独占维护机制。
- 初始化、种子入口和既有 schema 测试直接依赖旧初始化函数，需要同步适配。
- 当前根 `.venv` 未安装 Alembic；SQLAlchemy 2.0.51，SQLModel 0.0.27。
  此次调查只读取安装元数据，未导入应用数据库模块或安装依赖。

成功标准：旧库可识别地升级；已有字段值和附件字节保留；新旧库最终符合相同版本；
失败有可验证的备份和清晰状态；运行时不再隐式维护旧列；旧实现有据可查地移除。

## 2. 方案取舍

1. **采用：离线迁移 + 空库初始化 + 运行期版本检查。**
   有数据的结构变更与 API 分离，复用现有维护锁，保留新环境首次启动体验。
2. 不采用 API 每次启动自动升级所有旧库：现有共享锁不能直接充当 DDL 独占锁，
   自动升级也使备份、失败处置和启动副作用难以判断。
3. 不采用先 `create_all` 再无条件 stamp head：stamp 只改版本标记，不能证明旧结构
   已经符合基线，也不能代替历史数据保留验证。

## 3. 唯一结构变更入口

新增开发者 CLI `python -m app.db_migrations`：

- `status`：只读检查存在的库，报告 empty / legacy-compatible / current /
  upgrade-required / incompatible；文件不存在时不能因检查创建空库。
- `upgrade --backup-dir <新建的绝对外部目录>`：显式离线升级；有数据或已有表的库
  必须有新的、不可覆盖的外部备份目录。拒绝位于受管 repo/worktree 内的备份目录。
- `pnpm db:status`、`pnpm db:migrate` 为开发者包装，不加入 Agent 命令权限。
- 现有 `pnpm db:init`/`db:seed` 保留名称：空库走同一迁移协调器，current 库可显式
  幂等 seed；legacy/过期库须先离线 migrate，不再隐式补列或假定版本正确。

Alembic 的 env、revision 和内部执行器仅供该协调器调用；不能通过直接运行
`alembic upgrade/stamp/downgrade` 绕开互斥、备份、预检及结果验证。
导入模块无 DDL/seed/全局库连接副作用。仅支持本任务已验收的 SQLite 模式；
未知数据库后端拒绝并报告边界，不声称已有 MySQL 支持。

## 4. 固定 revision 与旧库接入

建立初始 revision `0001_local_baseline`，冻结现行表、字段、默认值、索引与约束定义。
revision 不调用会随业务演进的 `SQLModel.metadata.create_all`，不导入运行期 seed，
不以未来的 models.py 决定历史 migration 行为。models.py 继续定义 ORM；以后改表
必须新增 revision，不回写已经交付的基线。

处理路径：

- **空库**：从固定 revision 创建全部表及必要索引，验证后记录版本。
- **无版本现行库**：核对固定 schema 契约，完整通过才建立版本记录；不重写业务行。
- **无版本旧库**：仅支持由旧补列清单、受支持历史表定义及新增缺失表形成的可识别
  结构。对已存在表，仅增加明确允许的缺失列/索引，沿用原空值及默认值语义；缺失表
  用冻结定义创建。完成后重新核对结构与原值，再记版本。
- **已版本化库**：验证 revision 属于已知线性历史，并按顺序升级；head 库无结构变更。
- **不兼容库**：未知 revision、多 head、必需旧字段缺失、类型/主键/约束冲突、
  不认识的 schema 扩展或同名不兼容索引，均在任何 DDL 前拒绝并给出结构差异。

旧库兼容范围以静态定义和回归夹具为准，不承诺任意手工改过的库都能自动升级。
额外表/字段不删除、不静默修复，也不在未知 schema 上冒充接入成功。
唯一索引遇到重复数据时拒绝迁移；不能删除或合并用户记录来“修好”索引。

## 5. 互斥、备份和失败处理

1. 解析并验证目标身份；拒绝指向符号链接/重解析重定向或硬链接的库及备份路径。
2. 在任何备份或结构写入前获得现有 `database_lease(..., exclusive=True)`；
   API 持有共享锁时直接拒绝，不停止用户进程、不删除维护锁文件。
3. 升级要求 API、Agent、预览和其他写入者已停止；检查受管 API 运行情况和 SQLite
   写锁冲突。现有 init/seed/迁移入口必须遵守同一互斥协议，不改变业务运行状态
   来伪造空闲。SQLite 和 OS 锁不声称可阻止任意不合作的外部文件写入。
4. 使用 SQLite backup API 将含 WAL 的已提交内容备份到新目录，执行 integrity_check；
   保存源路径身份、原 revision、结构摘要、备份 SHA-256 与未完成/完成状态回执。
   不用单独复制主 `.sqlite3` 文件代替一致备份，不输出记录正文或凭据。
5. 在备份的另一个临时副本演练固定迁移，比较全部迁移前已有行的主键、字段值及
   BLOB 字节，并验证结构/索引/约束；不执行目标源码、Git hooks 或远程操作。
6. 演练通过后，受控连接在明确事务策略和锁冲突检查下升级原库并复验；备份与升级
   之间若检测到外部变化则中止。成功后才发布完成回执与 revision。

本次基线只进行兼容性增量建表/补列/建索引，不删除业务表、列或记录。
失败时停止后续 DDL/seed/运行恢复并保留备份与错误阶段；不将失败标为成功。
SQLite 驱动的 DDL 事务行为必须通过故障注入验证，不能仅因使用 Alembic 就承诺
整个升级会自动回滚。已发生的部分增量 DDL必须可识别并安全重试；版本不前移。
不自动覆盖恢复原库，不提供会删表的 baseline downgrade；需要恢复时使用核验过的
备份，在停机状态按明确手册处理，不直接用升级前的完整工作区快照替代 DB 身份校验。

备份只保证数据库内容；Git、worktree、外部项目文件不由本迁移复制或修改。
原有全工作区离线备份/恢复功能保留，不被数据库迁移回执冒充。

## 6. API 与首次启动兼容

API 启动前对空库获取短期独占租约，通过相同固定 revision 初始化，不 seed 任意旧库；
随后释放独占租约并获取生命周期共享租约，再次检查 revision/schema，避免锁切换竞争。
current 库在共享租约下检查后沿用现有种子/恢复/worker 顺序；这些步骤不做 schema DDL。
legacy/过期/不兼容库在 seed、运行恢复、preview、worker 启动前明确失败，提示先停机、
提供新备份目录并运行离线迁移。多进程首次启动须验证竞争者不会同时建表或迁移。
测试用内存库使用同一个固定 revision 路径，不能回退到旧运行时补列机制。

## 7. 旧代码清理边界

- 验收替代路径后删除 db.py 的 ensure_demo_schema_columns/indexes、
  _ensure_sqlite_demo_schema_columns/indexes、_ensure_table_columns 及其启动调用。
- 保留既有 create_db_and_tables/init_database 调用契约所需的薄入口，内部转交迁移
  协调器或 current 检查；不保留第二套 schema 修复实现。
- 将 test_models.py 中直接测试旧私有补列函数的案例迁到旧库升级/数据保留测试，
  保留其真实历史 DDL 和数据，不仅删除原测试。
- 更新当前指南、启动提示、依赖清单与必要检查；历史 OpenSpec/验收记录只标记历史
  语义，不批量抹除。清理通过引用搜索和最终 diff 清单逐项确认。
- 不删除任何运行数据库、WAL/SHM/维护锁、Session、worktree、依赖目录、用户文件、
  备份或历史证据；不顺带做磁盘清理或扩大适配器权限。

## 8. 文件职责与验收

预期实现区域：`apps/api/alembic.ini`、`apps/api/migrations/`（env/冻结 revision）、
`apps/api/app/db_migrations.py`（CLI/协调入口）、小型 schema/backup 辅助模块、
`apps/api/app/db.py`、main.py/seed.py 的必要入口适配、requirements.txt、开发者包装、
隔离迁移测试及当前使用文档。具体文件拆分在书面实施计划中固定。

必须验证：

1. 空库与已有 head 库；重复运行不改变历史记录，不新增重复种子。
2. 无版本现行库以及原六组补列兼容旧库；旧消息 JSON、内存、任务/事件、制品、
   审批、Skills/MCP 绑定和附件 BLOB 的原值保留。
3. WAL 中已提交数据确实进入备份；备份哈希/完整性、恢复副本可读及逻辑内容一致。
4. 未知/损坏版本、冲突类型/索引、唯一值冲突、写锁/路径风险在写入前被拒绝。
5. 演练失败、备份失败、原库 DDL 中断：无假完成回执、版本不前移，备份保留且
   部分增量状态可以安全复验/重试；不把“有备份”等同于已自动恢复。
6. Windows/POSIX API共享与迁移独占互斥、首次启动竞争、旧库启动 fail-fast。
7. 健康/模型/种子/维护/完整工作流相邻回归，以及根检查、API 全量测试、strict
   OpenSpec 和 diff 空白检查。测试使用外部新临时目录，不触碰实际产品数据库。

未来在真实本地库执行升级须单独呈现识别结果和备份位置，确认停机条件；本次代码
实现验收先使用夹具与副本，不自动停止现有服务或迁移真实产品库。

## 9. 设计依据

- [现有初始化](../../../apps/api/app/db.py)
- [现有生命周期](../../../apps/api/app/main.py)
- [现有维护锁](../../../apps/api/app/maintenance_lease.py)
- [既有数据维护设计](../agenthub-local-data-maintenance/design.md)
- [Alembic stamp：只标记版本，不运行迁移](https://alembic.sqlalchemy.org/en/latest/api/commands.html#alembic.command.stamp)
- [Alembic SQLite batch migration 与约束处理](https://alembic.sqlalchemy.org/en/latest/batch.html)

## 10. 当前交付阶段

2026-10-18 用户已审核同意本设计，授权继续制定实施计划。
[书面实施计划](../../../docs/superpowers/plans/2026-10-18-alembic-migrations.md) 已形成，
用户已审核并选择 Native 顺序执行。计划补充 seed 只补缺失记录，避免现有初始化重写已有
Agent/Workspace 配置；这是保留数据要求的实施细化，不扩大为新子系统。
当前已在隔离工作树实施迁移并以临时夹具验证；已安装已告知的 Alembic 依赖，
被替代旧代码已清理。没有读取/迁移实际业务数据库、删除业务数据、提交或推送；
本地最终复验已通过，tasks.md 按验收结果更新；真实库迁移和远程 CI 不在已验证结果中。
