# Alembic 数据库迁移 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 2026-10-18 用户已审核计划并选择 Native 顺序实施；以下保留原实施步骤，完成状态以复选框及验收记录为准。

**Goal:** 将现有 SQLite 安全接入 Alembic，保留全部既有业务数据，替换旧启动补列/索引逻辑。

**Architecture:** 固定 revision 管理结构，离线协调器负责独占租约、备份、副本演练、升级及核验；API 只初始化空库或校验 current 库。历史版本定义不依赖未来 ORM；seed 与 schema 迁移分离，已有 seed 配置不得被首次启动覆盖。

**Tech Stack:** FastAPI、SQLModel 0.0.27、SQLAlchemy 2.x、SQLite、Alembic 1.20.0；本地 Python 3.12.7 / Windows，现有 CI Python 3.11 / Ubuntu。

**Spec:** [已审核设计](../../../openspec/changes/agenthub-alembic-migrations/design.md) / [规范](../../../openspec/changes/agenthub-alembic-migrations/specs/database-migrations/spec.md) / [唯一 OpenSpec 实施任务 1.1](../../../openspec/changes/agenthub-alembic-migrations/tasks.md)。2026-10-18 用户已同意设计、审核计划并授权 Native 顺序实施。

## Global Constraints

- “类型：架构变更。只处理本地单用户 SQLite 的结构版本管理及被替代代码清理。”
- “revision 不调用会随业务演进的 `SQLModel.metadata.create_all`，不导入运行期 seed，”
- “有数据或已有表的库必须有新的、不可覆盖的外部备份目录。”（设计原文跨行拼接。）
- “本次基线只进行兼容性增量建表/补列/建索引，不删除业务表、列或记录。”
- “不自动覆盖恢复原库，不提供会删表的 baseline downgrade；”
- “不删除任何运行数据库、WAL/SHM/维护锁、Session、worktree、依赖目录、用户文件、”
- “测试使用外部新临时目录，不触碰实际产品数据库。”
- 保留全部 Adapter、SQLite、SSE、运行/审批/路径权限和工作树机制；不开始 Tool Registry 或 Docker。
- 根 AGENTS.md 禁止未经授权 commit/push；技能的示例 commit 步骤不适用本任务。
- 计划阶段不安装依赖、不导入 app.db 或连接实际库、不修改运行代码；实施前明确告知将安装 Alembic 1.20.0 及解析出的必要依赖到项目环境，禁止顺带升级其他包。
- 以下六个 Task 是同一 OpenSpec 1.1 的顺序里程碑，不是启动其他 OpenSpec 任务的授权；所有验收完成前不勾选 1.1。

## Review Focus

1. 老补列用 TEXT，ORM 用 VARCHAR，Python 默认值不一定是 server default：只能按冻结兼容契约比较，不能误拒绝正常旧库或放过真正类型变化。归属 Task 1。
2. 有 WAL 时在已经 BEGIN IMMEDIATE 的同一个 sqlite3 连接上调用 backup 可能自锁：预留写连接与备份只读连接分开，备份有截止时间。归属 Task 3。
3. 原库 commit 完成、完成回执写入失败：不能报告“原库未变/已经回滚”，必须可从 revision 与回执阶段核对实际结果。归属 Task 3。
4. 旧 seed 会重写 Agent/Workspace，schema 升级成功不代表配置被保留：首次启动和重复 seed 均验证原记录不变。归属 Task 4。
5. 当前 API 测试会导入全局 engine：测试命令必须在导入前强制选择新的外部测试库，不能误初始化产品库。归属 Task 5。

## 文件与接口地图

| 路径（相对仓库根） | 职责 |
|---|---|
| `apps/api/migrations/__init__.py`、`baseline_v1.py` | 冻结 26 张业务表及历史补列/索引兼容契约；不是读取当前 ORM 的包装 |
| `apps/api/migrations/versions/0001_local_baseline.py` | 唯一初始 revision；执行冻结的增量 DDL，禁止破坏性 downgrade |
| `apps/api/migrations/env.py`、`script.py.mako`、`apps/api/alembic.ini` | 接收协调器拥有的连接；拒绝裸 CLI/offline SQL 绕过；后续 revision 模板 |
| `apps/api/app/schema_contract.py` | 只读结构比较、受支持变更清单、原有数据投影与摘要 |
| `apps/api/app/migration_runtime.py` | 持有内部执行凭据及受控 Alembic runner，不获取第二把维护锁、不自行 commit |
| `apps/api/app/migration_backup.py` | 新目录 DB 备份、完整性/哈希、临时副本演练、分阶段回执 |
| `apps/api/app/db_migrations.py` | 状态/升级 CLI、离线租约与事务协调、空库 prepare/current 检查 |
| `apps/api/app/db.py`、`main.py`、`seed.py` | 保留 engine/初始化导入契约，替换 DDL 入口，避免已有种子被覆盖 |
| `apps/api/app/config.py` | 必要时将 SQLite URL 解析收敛到 SQLAlchemy make_url，保持现有相对路径语义 |
| `apps/api/requirements.txt` | 仅新增固定版本 Alembic，不替换现有框架 |
| `scripts/db-migrations.sh`、`package.json` | db:status / db:migrate；复用 python-env.sh，正确透传参数 |
| `scripts/test-api.sh`、`scripts/db-migrations.test.mjs` | 全量 API 临时库隔离，以及命令包装/路径/危险环境变量回归 |
| `apps/api/tests/migration_fixtures.py` | 静态旧库 DDL 和业务样本；不从新 migration 反推旧结构 |
| `apps/api/tests/test_schema_contract.py`、`test_db_migrations.py` | 分类、固定 revision、旧库原值及 BLOB 保留 |
| `apps/api/tests/test_migration_backup.py`、`test_migration_lifecycle.py`、`test_seed_preservation.py` | WAL/失败恢复、跨进程互斥/API 启动、首次启动配置保留 |
| `apps/api/tests/test_models.py`、`test_health.py` | 保留模型/健康测试，迁移旧私有 helper 测试到新入口 |
| `README.md`、`docs/local-usage.md`、`docs/architecture.md`、`docs/project-state.md`、`docs/change-log.md`、根 `AGENTS.md`、`.gitignore` | 当前用法、验收/清理清单及 Alembic 专项边界；精确放行本计划及验收材料，不放行 DB/备份；仅在实现后更新运行能力描述 |

不修改独立 `apps/demo-api` 的数据初始化；它不是平台 SQLite 迁移目标。

## 验证命令约定

实施者先确认工作区/解释器及已有计划文件。若按 using-git-worktrees 使用隔离工作树，必须显式带入本次已审核但未提交的设计和计划，保留原工作区；不得 reset、stash 或清理用户内容。所有相对命令均以该实施工作树为准。

Python 专项测试从 `apps/api` 运行，使用根 `.venv/Scripts/python.exe`（POSIX 为 `.venv/bin/python`）。每个批次新建一个**仓库外**临时根；在任何 app 导入前设置 `AGENTHUB_DATABASE_URL` 到该临时根的 `runtime.sqlite3`，指定新的 `--basetemp`，证据目录与 basetemp 分开。

下文 `API_TEST <files/selectors>` 表示以下 PowerShell 约定；实际执行结果及批次边界见[验收记录](../../alembic-migrations-review.md)：

```powershell
$alembicBatch = Join-Path ([IO.Path]::GetTempPath()) ('agenthub-migration-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $alembicBatch | Out-Null
$alembicPreviousDatabase = $env:AGENTHUB_DATABASE_URL
$env:AGENTHUB_DATABASE_URL = 'sqlite:///' + (Join-Path $alembicBatch 'runtime.sqlite3').Replace('\', '/')
try {
    # workdir=apps/api；selectors 由各步骤指定，不照字面传入 <...>
    & '..\..\.venv\Scripts\python.exe' -m pytest <files/selectors> --basetemp (Join-Path $alembicBatch 'pytest') --junitxml (Join-Path $alembicBatch 'results.xml') -q
    if ($LASTEXITCODE -ne 0) { throw 'Migration verification failed; retain the original evidence.' }
} finally { $env:AGENTHUB_DATABASE_URL = $alembicPreviousDatabase }
```

红灯步骤只接受指定接口尚不存在或对应行为断言失败；解释器、导入路径、权限和实际库误选造成的错误不是有效红灯。若 API 测试原有全局初始化依赖被移除，修正 fixture 为显式 prepare 新临时库，不能禁用启动检查或对产品库执行 db:init。

### Task 1: 冻结 schema 契约和真实旧库夹具

**Files:** Create `migrations/baseline_v1.py`、`app/schema_contract.py`、`tests/migration_fixtures.py`、`tests/test_schema_contract.py`；Modify `requirements.txt`。实施期才创建/修改这些运行文件。

**Interfaces:**
- `frozen_metadata() -> sqlalchemy.MetaData`：全新的冻结元数据，不导入 app.models/db/seed。
- `SchemaReport`：不可变数据，`state` 为 empty/legacy-compatible/current/upgrade-required/incompatible，`revision: str | None`、`head: str`、`issues: tuple[str, ...]`、`changes: tuple[SchemaChange, ...]`。
- `SchemaChange` 仅含 create_table/add_column/create_index 与冻结表/列/索引标识；不接收任意 SQL。
- `inspect_schema(connection: sqlalchemy.Connection) -> SchemaReport`。
- `RowEvidence`：迁移前表到原列名的投影，以及逐表 `(row_count, sha256)`；`capture_rows(connection: Connection) -> RowEvidence`、`assert_rows_preserved(connection: Connection, before: RowEvidence) -> None`。

- [x] **Step 1: 写分类和原值断言测试。** `test_empty_schema`；`test_unversioned_current_is_legacy`；参数化六张旧表的缺列；`test_text_varchar_and_known_defaults_are_compatible`；`test_unknown_revision_and_schema_drift_refuse`；`test_same_name_wrong_index_refuses`。例如：
  ```python
  assert inspect_schema(connection).state == 'legacy-compatible'
  assert inspect_schema(drift_connection).state == 'incompatible'
  assert set(frozen_metadata().tables) == EXPECTED_TABLES  # test_models.py 的 26 张表，静态复制到夹具
  ```
- [x] **Step 2: `API_TEST tests/test_schema_contract.py` 记录预期红灯。**
- [x] **Step 3: 冻结当前 26 张表及全部索引/约束，写只读分类器。** 允许 missing-table 增量；已有表只允许 db.py 原六组共 23 个缺列以及冻结的缺失索引。迁移完整状态可包含合法的历史默认值/类型拼写差异，不要求破坏性重建“统一文本”。系统 sqlite_* 对象忽略但保留；未知用户表/列/视图/触发器、额外约束、缺必需旧列、未知/多行 revision 拒绝。已 head 但结构漂移也拒绝，不按 head 静默放行。
- [x] **Step 4: 写数据投影实现。** 对原有全部业务列按主键稳定排序、类型与长度编码，逐批读取并做摘要；NULL、空串、JSON 原文、Unicode、BLOB 分别处理，不能用 ORM 序列化后比较，也不能只比较行数。表/列标识只来自已核对契约并正确引用。
- [x] **Step 5: 冻结历史夹具。** 原 test_models.py 三项旧 DDL/数据逐字迁入夹具，补足 message/session/taskrun/agentprofiledraft 的独立历史定义；用当前无版本库样本填充全部 26 张表的代表行。完整样本必须包含附件 payload/image_payload、Skills/MCP、记忆、运行事件、审批相关 JSON 和自定义名称。检查原 DDL 中真实存在/缺失的 FK，不为让夹具通过而忽略任意 FK 缺失。
- [x] **Step 6: 在已告知安装范围后新增 `alembic==1.20.0` 并仅安装到实施环境，运行 pip check。** 若解析器要求升级现有直接依赖，停止并呈现冲突，不能静默升级。版本依据见文末；本步骤不是当前计划阶段的授权安装。
- [x] **Step 7: `API_TEST tests/test_schema_contract.py` 通过；对冻结 schema 与现行 ORM 在内存新库的结构差异做明示比对，未解释差异不得继续。** 不读取实际数据库。

### Task 2: 建立受控 Alembic runner 与固定 revision

**Files:** Create `alembic.ini`、`migrations/env.py`、`script.py.mako`、`versions/0001_local_baseline.py`、`app/migration_runtime.py`、`tests/test_db_migrations.py`；依赖 Task 1 的契约。

**Interfaces:**
- `migration_runtime.controlled_config(connection: Connection) -> alembic.config.Config`：只为协调器拥有、已开始事务的连接产生内部执行凭据。
- `migration_runtime.require_owned_connection(config: Config) -> Connection`：env.py 唯一连接来源；验证同一连接与当前事务，不读取外部 URL 建新引擎。
- `migration_runtime.run_baseline_upgrade(connection: Connection, *, before: RowEvidence) -> None`：运行 upgrade head、核对结构/旧值，不 seed、不 commit。

- [x] **Step 1: 写 `test_fixed_revision_initializes_empty`、`test_frozen_history_ignores_runtime_model_changes`、`test_supported_legacy_additions_preserve_values`、`test_current_repeated_upgrade_is_noop`、`test_raw_alembic_invocation_is_refused`、`test_baseline_downgrade_does_not_drop_tables`。** 新库业务表集合应为 26 张，另有且只有预期的 alembic_version；业务 ORM 集合仍为 26 张。
- [x] **Step 2: `API_TEST tests/test_db_migrations.py` 记录红灯。**
- [x] **Step 3: 实现 revision `0001_local_baseline`，`down_revision=None`。** 仅用冻结定义和 Alembic create_table/add_column/create_index，按依赖顺序执行 Task 1 的变更清单；不重新建立已经存在的表。用正式 op 调用，不拼接来自 CLI/数据库的任意 DDL。
- [x] **Step 4: 实现 runner/配置与 env guard。** Alembic 使用外部已拥有的 connection 和事务；拒绝裸 upgrade/stamp/downgrade、offline SQL/未知运行上下文。guard 是防止绕过开发者流程的应用内约束，不声称能抵抗任意宿主 Python/SQL。status 直接读 MigrationContext，不用 stamp。
- [x] **Step 5: 在升级后、事务提交前验证 current schema、原行/旧值及数据库完整性。** Alembic revision 标记必须与受控事务绑定；检查失败时回滚版本 DML，禁止单独 commit 标记。以真实 SQLite 故障注入验证事务行为，不仅 mock rollback。本地 Python 3.12 已执行；Python 3.11 留待现有 Ubuntu CI 验证，不声称本机覆盖。
- [x] **Step 6: `API_TEST tests/test_schema_contract.py tests/test_db_migrations.py` 通过；旧库案例不仅查新增字段，还对照迁移前全部投影。**

### Task 3: 离线协调器、备份演练及失败回执

**Files:** Create `app/migration_backup.py`、`app/db_migrations.py`、`tests/test_migration_backup.py`；复用 `maintenance_lease.py` 和 local_data.py 的纯路径校验语义，不修改原全工作区快照格式。

**Interfaces:**
- `read_status(database_url: str) -> SchemaReport`：只读，不导入 app.db/main/seed，不创建目标父目录、数据库或维护锁。
- `upgrade_database(database_url: str, *, backup_dir: Path | None, repo_root: Path, api_port: int = 8000) -> UpgradeResult`。
- `UpgradeResult`：`state: Literal['current', 'upgraded']`、`revision: str`、`backup_dir: Path | None`；业务内容不进入结果日志。
- `MigrationBackup`：新目录、封存 DB 路径、不可变 manifest、SHA-256 和 before RowEvidence。
- `create_backup(source: Path, destination: Path, *, before: RowEvidence, report: SchemaReport) -> MigrationBackup`；`rehearse_backup(backup: MigrationBackup) -> None`；`write_receipt(backup: MigrationBackup, *, phase: str, detail: str | None = None) -> None`。
- `MigrationError` 含稳定 code/stage，无记录正文/凭据；`main(argv: Sequence[str] | None = None) -> int`。

- [x] **Step 1: 写 CLI/备份拒绝和保留测试。** `test_status_missing_creates_nothing`；`test_existing_legacy_requires_new_external_backup_dir`；`test_backup_contains_committed_wal_and_blob_bytes`；`test_busy_api_or_sqlite_writer_refuses_before_ddl`；`test_rehearsal_failure_keeps_original_unmodified`；`test_backup_progress_timeout_is_bounded`。CLI 在新子进程中测，禁止仅调用内部函数代替入口验证。
- [x] **Step 2: `API_TEST tests/test_migration_backup.py` 记录红灯。**
- [x] **Step 3: 实现目标解析/只读 status。** 使用 SQLAlchemy make_url 区分相对/绝对文件与内存，正确处理空格、中文、`#`/`%`。CLI 只操作文件库，非 SQLite/内存 CLI 明确拒绝；内部内存测试走 Task 4 接口。readonly URI 不用 immutable 打开可能还有 WAL 的源库。空库初始化及 current 无操作返回不要求备份；无版本现行库的版本接入也属于已有库变更，必须备份和演练。已有声明 FK 的违反在 DDL 前报告并拒绝，不自动修复历史关系。
- [x] **Step 4: 实现离线状态机。** 目标与备份路径重解析检查（含父目录 junction、hardlink）；新外部目录以独占创建，不覆盖同名。独占维护锁 → 受管 API 端口检查 → 受控原库连接 `BEGIN IMMEDIATE` → 重新核对 schema/身份/旧值 → 一致备份 → 副本演练 → 复核身份和源状态 → 同一原库事务 upgrade/verify → commit → 完成回执。写锁失败限时返回；不触发终止进程或清理历史状态。
- [x] **Step 5: 处理运行状态的边界。** 活动 API/受管预览必须拒绝；不能通过改 TaskRun 状态/删除锁来获得“空闲”。仅有历史非终态行不能当作没有活动进程的证明，也不能直接判定其数据需要修复；不认识的运行状态保守拒绝，提示用旧版本正常中断/停机。本迁移不修复执行账本。
- [x] **Step 6: 分离备份连接与预留写连接。** 保留原库写 reservation；用另一个 readonly SQLite 连接调用 backup 到独占新建文件，progress 回调结合 monotonic 截止时间；不要从持有写事务的连接对自己 backup。关闭所有备份连接，将备份副本封存成无 WAL 依赖的独立 DB，核验 integrity/sha256；副本演练使用另一临时副本，不改封存备份。摘要必须与 Task 1 原投影吻合。
- [x] **Step 7: 实现可追溯回执。** 固定 phase 顺序 backup-created/backup-verified/rehearsal-passed/upgrade-prepared/database-committed/verified；每阶段用新序号 JSON 文件独占写入、flush/fsync，不覆盖旧阶段。异常记录 failed；commit 已成功而回执发布失败时，返回明确非零与 `commit-uncertain` 诊断，不能声称原库未变或版本未前移。重跑只检查实际 current/schema/原值并保留旧回执，不自动再次改写或伪造历史完成记录。
- [x] **Step 8: 故障注入补齐。** `test_mid_upgrade_failure_keeps_revision_and_backup`（核验可见 DDL 及安全重试）；`test_commit_success_receipt_failure_is_not_reported_as_rollback`；`test_source_identity_change_refuses`；`test_rehearsal_corruption_refuses`；`test_paths_and_destination_conflicts_refuse`；`test_backup_read_is_from_separate_connection`。故障点为内部可 monkeypatch 的阶段函数，不暴露产品 fault 参数。
- [x] **Step 9: `API_TEST tests/test_schema_contract.py tests/test_db_migrations.py tests/test_migration_backup.py` 通过；在新目录从封存 DB 恢复副本并比较全部旧值/BLOB。** 不新增自动覆盖源库的 restore 命令。

### Task 4: 生命周期接入和配置保留

**Files:** Modify `app/db.py`、`app/main.py`、`app/seed.py`，必要时 `app/config.py`；Create `tests/test_migration_lifecycle.py`、`tests/test_seed_preservation.py`。

**Interfaces:**
- Task 3 新增 `prepare_database(db_engine: Engine) -> None`：仅空库独占初始化/现行库校验；`require_current_schema(db_engine: Engine) -> None`：只检查，无 schema 写入。
- `db.engine` 的已有导入契约保留；`create_db_and_tables() -> None` 转交 prepare；`init_database(seed: bool = True) -> None` 仅检查 current 并可执行 insert-only seed，在调用者已持有的生命周期租约内不嵌套加独占锁。
- `seed_demo_data(db: DbSession) -> None` 保留签名，仅补缺失记录，已有 Workspace/Agent 全字段保持。

- [x] **Step 1: 写 `test_legacy_startup_fails_before_seed_recovery_and_workers`、`test_current_startup_preserves_customized_seed_records`、`test_empty_startup_initializes_then_rechecks_under_shared_lease`、`test_api_shared_lease_blocks_offline_upgrade`、`test_repeated_seed_inserts_only_missing_records`。** 用真实 subprocess 检查维护锁，而不只 mock contextmanager。
  ```python
  before = raw_existing_seed_rows(connection)
  seed_demo_data(db)
  assert raw_existing_seed_rows(connection) == before
  assert existing_agent.enabled is False  # 不强制重新启用已有禁用角色
  ```
- [x] **Step 2: `API_TEST tests/test_migration_lifecycle.py tests/test_seed_preservation.py` 记录红灯。**
- [x] **Step 3: 移除 db.py 导入时创建父目录的副作用，保留惰性 engine 对象。** prepare 创建父目录仅用于显式空库初始化；status 不依赖全局 engine。CLI init/seed 的外层 prepare 与共享租约/当前检查明确分开；seed.py 的 `__main__` 转交同一受控初始化入口，不能直接调 create_all。
- [x] **Step 4: 改 main.lifespan。** 空库 prepare 在生命周期共享锁之前获得短期独占锁；current 快速路径不要求先获得独占锁。获取共享锁后重新 require_current_schema；再沿用 init(seed)/恢复/preview/group worker 顺序。锁切换中若另一个 initializer 已完成并持有共享锁，重新只读检查 current 后走共享路径，禁止递归/无界重试；竞争锁有限时明确拒绝。内存 Engine 使用相同 runner 且不建宿主锁文件。
- [x] **Step 5: 将 seed 改为存在则保留。** 只插入缺失 demo user/workspace/role，已有名称、adapter/provider、提示词、enabled、root/default_branch 等不重置；显式修改交给现有设置功能。本项不对所有 seed 相关业务做重构。
- [x] **Step 6: 补齐 `test_two_initializers_never_mutate_concurrently`、`test_path_with_spaces_and_unicode_uses_same_database_identity`、`test_current_schema_drift_blocks_recovery`、`test_lifespan_failure_releases_lease_and_restores_windows_handler`。** 适配 test_windows_connection_cleanup.py 原 patch/init 契约，不删除恢复 handler 的断言。
- [x] **Step 7: `API_TEST tests/test_migration_lifecycle.py tests/test_seed_preservation.py tests/test_health.py tests/test_windows_connection_cleanup.py` 通过。** 修改全局测试初始化须使用临时 fixture，不将产品库作为验证对象。

### Task 5: 开发者命令与测试入口隔离

**Files:** Create `scripts/db-migrations.sh`、`scripts/db-migrations.test.mjs`；Modify `package.json`、`scripts/test-api.sh`，仅必要时修改 `scripts/init-db.sh`/`seed-db.sh` 的参数透传。

**Interfaces:** `pnpm db:status` → `python -m app.db_migrations status`；`pnpm db:migrate --backup-dir <absolute-new-directory>` → `... upgrade --backup-dir ...`；wrapper 复用 python-env.sh，转发 `"$@"`，不重复构造 shell 命令。

- [x] **Step 1: 写 Node 内置测试，覆盖带空格/中文/特殊字符参数保留、退出码透传、未安装依赖明确错误、不执行安装。** 为 test-api wrapper 写 `test_api_wrapper_uses_new_external_database_before_import`、`test_api_wrapper_does_not_reuse_inherited_product_database`、`test_failed_tests_retain_separate_evidence`，用受控假解释器/临时脚本采集 argv/env，不能启动真实产品库。
- [x] **Step 2: 从仓库根运行 `node --test scripts/db-migrations.test.mjs`，记录预期红灯。** Windows 与 POSIX 分支只跳过实际不可用 shell，不吞掉真实失败；至少验证当前可用路径。
- [x] **Step 3: 实现 wrapper 和 package 命令。** Python 版本固定 pin 只来自 requirements；不在命令运行时安装依赖。`status` JSON 总有 state/revision/head/issues；current/empty 退出 0，legacy/upgrade-required 退出 2，不兼容/操作失败退出 1；argparse 用法错误退出 2。upgrade 成功/current-noop 退出 0，其他非零。不输出业务值。
- [x] **Step 4: test-api.sh 必须在 Python 启动前覆盖 AGENTHUB_DATABASE_URL 为本批次全新外部库，即使调用进程继承了产品 URL。** 使用 python-env.sh 已有新 temp 根，数据库与 pytest basetemp 分目录；覆盖只在脚本子进程中生效。失败时不递归删掉本批次证据；清理仍仅限已验证的本批次路径，不复用用户目录。将新 Node 文件显式加入 test:local，确保原 CI 会执行这些验证。
- [x] **Step 5: 重跑 Node 专项及 `pnpm test:local`；用临时库执行 db:status、db:init、db:migrate --backup-dir，核对 JSON/退出码/新外部备份。** 每条命令显式绑定测试数据库；禁止直接运行默认指向产品库的 db:init。

### Task 6: 删除旧实现、回归与交付记录

**Files:** Modify `tests/test_models.py`、必要的原测试 fixture、当前使用文档/AGENTS/OpenSpec/change-log；Create `docs/alembic-migrations-review.md`、`docs/evidence/alembic-migrations/README.md`（实现验收后）。

实施回归补充：复用依赖目录的独立工作树暴露既有预览真实路径识别缺陷，最小修改
`scripts/preview-vite.config.mjs`，在 `scripts/preview-serving-paths.test.mjs` 增加正反例。
不新增允许根；原因、红绿验证和代价见验收记录的第 12 项裁定。

- [x] **Step 1: 完成替代前提检查。** Task 1–5 验证通过；将原三项旧 helper 测试及六组兼容语义逐项映射到新迁移测试，保留真实旧 DDL。对原全局库测试加显式临时库初始化；不得用 disable guard 或手工 stamp 绕过新生命周期。
- [x] **Step 2: 删除 db.py 的 ensure_demo_schema_columns、ensure_demo_schema_indexes、两个 _ensure_sqlite_demo_schema_*、_ensure_table_columns，以及旧启动 DDL 调用和测试 import。** create_db_and_tables/init_database 保留薄兼容入口；不为“清理”删除源文件测试或历史 DDL。运行期不允许第二套 create_all/补列修复。
- [x] **Step 3: 搜索验收清理范围。** `rg -n 'ensure_demo_schema|_ensure_table_columns|ALTER TABLE|create_all' apps/api/app apps/api/tests`；逐条核对结果。纯 ORM 单元测试的 create_all 可保留但不可作为 migration/startup 的替代；冻结 migration 内合法 DDL 是唯一结构演进路径。记录被删除符号及每个保留命中的原因，不更改历史验收材料。
- [x] **Step 4: 使用外部新库运行最终专项：**
  `API_TEST tests/test_schema_contract.py tests/test_db_migrations.py tests/test_migration_backup.py tests/test_migration_lifecycle.py tests/test_seed_preservation.py tests/test_models.py tests/test_health.py tests/test_local_data.py tests/test_local_data_cleanup.py tests/test_windows_connection_cleanup.py`。
  通过标准：无失败；互斥/数据保留/WAL/真实故障注入均有已执行用例，不以跳过替代。
- [x] **Step 5: 运行相邻工作流 `API_TEST tests/test_workflow_evaluation.py tests/test_workflow_native_qa.py tests/test_group_auto_execution.py`，再运行 `pnpm check`、`pnpm test`。** 根测试必须走 Task 5 的隔离 wrapper；全量 API 本地 Windows、现有 Ubuntu CI 的 Python 3.11/跨进程租约均需明确验证边界。无远程提交授权时不推送；本地无法执行的 OS/版本报告未验证，不把本地通过冒充 CI 通过。全量通过后只因新修改/失败才重跑。
- [x] **Step 6: 更新当前指南和专项护栏。** 写旧库 status → 停机 → 新外部备份目录 → upgrade → 验证 → 启动流程、拒绝原因、故障阶段/备份副本恢复说明。根 AGENTS 仅增加本 Alembic 专项例外及开发者命令；不给 Adapter 新命令或 DB 权限。.gitignore 为本专项 review/evidence 增加精确白名单，不放行数据库或备份文件。project-state/change-log 如实区分实现/本地验收/真实库尚未迁移/远程未验证。
- [x] **Step 7: 保存证据。** 记录解释器/依赖、源码和冻结契约哈希、命令、JUnit、DDL/数据摘要、故障回执、备份恢复副本验证、清理清单；不提交数据库备份/BLOB/凭据/业务原文，不累计重叠测试数字。记录始终只含夹具和临时路径。
- [x] **Step 8: `openspec validate agenthub-alembic-migrations --strict`、本地文档链接检查、`git diff --check`、最终 diff 范围审查。** 新文件也检查 UTF-8/尾随空白；只有实现与相关验证全部符合规范时勾选 OpenSpec 1.1。如任一验收缺口存在，保持未完成并明确记录。
- [x] **Step 9: 按已选择执行方式进行最终复核，汇报实际变更、测试和未验证边界。** 不自动 commit/push，也不停止实际服务或升级真实库。实际库升级须单独展示其 status、源身份与备份目的地，并确认停机条件后再处理。

## 覆盖映射与自审

| 设计/规范要求 | 实施与验证 |
|---|---|
| 固定历史、单一结构入口、禁止裸 stamp | Task 1/2；Task 6 清理 |
| 无版本旧库兼容及全字段/BLOB 保留 | Task 1 真实历史夹具；Task 2 固定增量；Task 3 副本与原库核对 |
| 独占互斥、WAL、一致备份、隔离演练 | Task 3；Task 4 跨进程租约 |
| 失败阶段、版本不假前移、备份可读、部分状态安全重试 | Task 2 显式事务测试；Task 3 故障注入/commit-uncertain |
| 空库首次启动/current 检查/旧库 fail-fast | Task 4；Task 5 命令兼容 |
| 原配置不被 seed 覆盖、重复执行幂等 | Task 4 原行对照及补缺种子 |
| 清理范围不含实际数据或历史材料 | Task 6 符号/引用逐项清单与最终 diff |
| 真实库隔离和完整回归 | Task 5 wrapper/环境；Task 6 验收 |

自审结论：设计各要求均有归属；五项 Review Focus 均有命名测试；类型与接口在相邻 Task 间一致。六个里程碑均已完成本地验收；最终整项状态见 Task 6、OpenSpec 1.1 和验收记录，不累计重叠测试批次。

## 执行交接与依据

用户已选择 **Native：当前会话由主执行者顺序实现**，保持备份/事务/生命周期接口的一致理解，最后做独立只读复核。实施采用 executing-plans；独立复核的三项问题已在一次修复批次中通过红灯到绿灯验证，最终全量回归结果见验收记录。

- [Alembic 1.20.0 / Python 要求](https://pypi.org/project/alembic/1.20.0/)：已按告知范围安装固定版本；既有直接依赖未升级。
- [Alembic 共享既有连接](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)
- [Alembic stamp 仅标记版本](https://alembic.sqlalchemy.org/en/latest/api/commands.html#alembic.command.stamp)
- [SQLite batch 与约束](https://alembic.sqlalchemy.org/en/latest/batch.html)：未来重建表时需单独验收，本次不重建已有业务表。
- [Python 3.11 sqlite3 backup](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.Connection.backup)
