# 数据库完整性修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 用户于 2026-10-19 批准按 Native 方式实施；执行证据与最终状态见专项记录。

**Goal:** 修复 SQLite 外键执行和 TaskRun 事件并发编号，在固定离线迁移中保留全部已有字段值与附件字节，为后续 PostgreSQL 专项完成前置验收。

**Architecture:** 每个业务引擎在首次连接前绑定外键策略；固定 v2 revision 补齐受支持旧表的约束和事件组合唯一索引。协调器负责事务外的迁移连接设置、独占维护、备份和演练；事件在调用方事务内先取得数据库写锁，再分配序号和时间游标。

**Tech Stack:** 现有 Python、FastAPI、SQLModel、SQLAlchemy、Alembic、SQLite、pytest、SSE；无新增依赖。

**Spec:** [已审核设计](../specs/2026-10-19-database-integrity-design.md)；[唯一 OpenSpec 任务 1.1](../../../openspec/changes/agenthub-database-integrity/tasks.md)。在 `codex/database-integrity` 独立工作树实施，不自动提交、合并或升级产品数据库。

## Global Constraints

- “先完成 SQLite 完整性修复，再进行独立的 PostgreSQL 兼容与迁移专项。”
- “本阶段保留 SQLModel、SQLite、三个 Adapter、现有 SSE 协议和执行权限。”
- “v1 文件及既有 revision 保持不变”；不回写 `baseline_v1.py`、`schema_v1.json`、`0001_local_baseline.py` 或原历史 DDL JSON。
- “运行时禁止关闭外键，也不为绕过约束增加级联删除或自动补造父记录。”
- “发现孤立引用、空主键或未知结构时报告表/字段及数量，拒绝升级；不删除或修补历史行。”
- “不在 helper 中通过 rollback/commit 丢弃调用方已暂存的状态、审批或制品。”
- “不自动重试 Provider、文件编辑、部署或其他外部副作用，不吞掉 IntegrityError 伪造成功。”
- 新增数据/备份/临时文件及实施证据放在 `E:\Docker`；保留原产品库位置，测试只能用新外部库。
- 根 AGENTS.md 的禁止提交/推送规则优先于技能中的示例 commit；本计划不自动 commit/push/merge。
- 以下六个 Task 是同一 OpenSpec 1.1 的顺序里程碑，不代表开始其他 OpenSpec 任务；全部验收后才勾选 1.1。

## Review Focus

1. v1 revision 导入运行期 `inspect_schema`，新 head 不能反向改变冻结迁移的行为；空版本表也只能由受控 runner 接纳。Task 1 的冻结基线实跑和 bare CLI 拒绝测试负责。
2. 旧历史夹具省略父记录；不能用迁移补造父记录来维持旧测试通过。Task 1/2 分开验证完整关联升级正例和原样孤立数据拒绝负例。
3. 需要重建表时，事务内关闭外键无效；备份同连接可能自锁。Task 3 验证事务外设置、独立只读备份连接和锁内复检。
4. 编号锁修复后，两个写者无法同时到达 MAX；旧 MAX 屏障会让正确实现死锁。Task 4 在调用入口同步、观测锁等待，并覆盖跨进程和 WAL 旧快照。
5. 开启外键后 flush 顺序与审批/状态回滚可能变化。Task 5 在真实入口和启用外键的业务夹具中验证，不通过全局关闭约束或吞错避开。

## 文件与接口地图

所有路径相对实施工作树根；Create/Modify 仅在计划审核后执行。
已有业务测试引擎和事件生产者的精确文件名已列入[实施范围附件](../../../openspec/changes/agenthub-database-integrity/implementation-files.md)，不是等待实施者自行扩展的空白范围。

| 路径 | 责任及修改范围 |
| --- | --- |
| Create `apps/api/migrations/baseline_v2.py`、`schema_v2.json` | 独立冻结 v2 结构和 `HEAD='0002_database_integrity'`；不从运行 ORM 生成历史定义 |
| Create `apps/api/migrations/integrity_v2.py` | 固定预期关系审计、重建清单及 v2 重建操作；不接收任意 SQL/路径 |
| Create `apps/api/migrations/versions/0002_database_integrity.py` | 线性后继 revision；只调用冻结 v2 定义，不调用 seed 或业务模型 |
| Modify `apps/api/app/schema_contract.py` | 按历史 revision 分派冻结结构检查；保留已有 RowEvidence 与原值比较接口 |
| Create `apps/api/app/db_engine.py` | 无连接副作用的业务引擎工厂，每物理连接开启/确认 SQLite 外键 |
| Modify `apps/api/app/db.py`、`external_benchmark.py`、`p18b_workflow_rehearsal.py`、`workflow_evaluation.py` | 复用业务引擎策略；不改变评测数据含义、默认 Adapter 或文件范围 |
| Modify `apps/api/app/migration_runtime.py`、`db_migrations.py`、`migration_backup.py` | 多版本受控升级、迁移连接外键设置、锁内复检、原值/备份及结果回执 |
| Modify `apps/api/app/events.py`、`models.py` | 写锁内事件分配、冲突类型和 ORM 组合唯一索引；旧事件字段/游标不变 |
| Modify `apps/api/tests/migration_fixtures.py`；Create `tests/test_database_integrity.py`、`test_integrity_migrations.py`、`test_event_concurrency.py`（均在 `apps/api` 下） | 冻结历史库/真实父记录、约束及迁移、跨连接/进程竞争测试 |
| Modify `apps/api/tests/test_schema_contract.py`、`test_db_migrations.py`、`test_migration_backup.py`、`test_migration_lifecycle.py`、`test_chat_events.py`、`test_seed_preservation.py` | 保留历史断言，新增 v2/current、失败和 SSE 回归 |
| Modify 其余直接创建业务测试引擎的测试文件 | 只将引擎创建接入同一工厂，并修复具体错误的父子夹具顺序；实施前冻结精确文件清单 |
| Modify 事件生产事务入口：`adapters.py`、`group_execution.py`、`group_summaries.py`、`dag_integration.py`、`run_engine.py`、`routes/task_runs.py` 及搜索确认的其他生产者 | 只调整已复现的父行 flush 或冲突处理；不重构整体调度，不重复外部副作用 |
| Modify `docs/database-migrations.md`、`docs/architecture.md`、`docs/project-state.md`、`docs/change-log.md`、专项 OpenSpec；必要时 `README.md` / `docs/local-usage.md` | 实现后更新可执行用法、版本/失败/数据保留验收和清理记录 |

迁移专用连接与故意构造历史坏库的测试连接不复用业务工厂；它们必须显式标注目的。
业务测试不得通过全局 Engine 监听器、monkeypatch 关闭约束或仅为新测试开约束。

## 执行环境与验证命令

实施前读取 using-git-worktrees 技能和本地更具体的 AGENTS.md。基于已核对的
`8392b7fb02584ba6b6210705d4c8d4d5513b794e` 建立 `codex/database-integrity` 独立工作树，
优先遵守用户 E 盘路径约束；若工具不能指定位置，依技能使用 Git fallback，候选目录为
`E:\Docker\AgentHub\worktrees\database-integrity`。不重用或清理沙箱工作树。
显式带入本专项已审核设计、计划、OpenSpec 和精确忽略项，记录带入文件哈希；
不要整份覆盖主树现有 `.gitignore`、change-log 或 project-state，不 stash/reset 用户改动。

执行工具环境（仅当前进程）：

```powershell
$env:PATH = 'E:/Git/Git/bin;' + $env:PATH
$env:TEMP = 'E:/Docker/agenthub-temp'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
```

使用现有根 `.venv`，不安装依赖；仅需要显式编译时把 `PYTHONPYCACHEPREFIX` 指向 E 盘。
证据使用新建的 `E:\Docker\AgentHub\database-integrity-<执行时间>` 目录，不覆盖设计审计目录。
以下 `API_TEST` 是文档缩写，实际逐条执行 `pnpm test:api <列出的选择器> -q`，从实施根运行。
既有脚本在任何应用导入前强制新外部测试库，并保留独立 JUnit；不能改为裸 pytest。
红灯接受指定行为断言失败或新增接口确实尚不存在；缺解释器、环境/依赖导入失败或测试误连产品库不是有效红灯。
红灯及失败证据保留，成功数量按最终批次报告，不累计重叠用例。

### Task 1: 冻结 v2 契约并分开历史数据正负例

**Files:** Create `migrations/baseline_v2.py`、`schema_v2.json`、`integrity_v2.py`；Modify `app/schema_contract.py`、`tests/migration_fixtures.py`、`test_schema_contract.py`、`test_db_migrations.py`；Create `tests/test_integrity_migrations.py`。

**Interfaces:**
- 保留 `inspect_schema(connection: Connection) -> SchemaReport`；`state/revision/head/issues/changes` 字段及原 RowEvidence 接口不变。
- 新增内部 `inspect_target_schema(connection: Connection, *, target_revision: str) -> SchemaReport`，仅支持两个冻结 revision。Task 1 单测显式选择 v2；现有公开入口暂保留 v1 head，到 Task 3 才与真实 revision/runner 一起切换，保证测试包装器能初始化。
- 受支持无版本库仍按 v1 历史族识别；版本为 v1 时返回 `upgrade-required`、head 为 v2；v2 使用完整外键和唯一索引检查；未知/空/多版本仍拒绝。
- `migrations.baseline_v2.frozen_metadata() -> MetaData`、`HEAD`、`SCHEMA` 独立固定；SchemaChange 保留原三类，重建清单另用下项接口，不混进旧 baseline_changes。
- `IntegrityIssue(kind: str, table: str, column: str, count: int)` 不含记录正文；`audit_integrity(connection: Connection) -> tuple[IntegrityIssue, ...]` 检查孤立引用、空主键、重复及非法序号。
- `IntegrityUpgradePlan(rebuild_tables: tuple[str, ...], create_event_unique_index: bool)`；`plan_integrity_upgrade(connection: Connection) -> IntegrityUpgradePlan` 只输出冻结表名，预测 v1 补列后的缺失外键。

- [x] **1. 写红灯测试。** `test_v1_is_upgrade_required_but_unknown_revision_is_refused` 对显式 v2 目标检查断言合法 v1 的 `(state, revision, head)==('upgrade-required','0001_local_baseline','0002_database_integrity')`；未知、空、多记录仍 incompatible。
- [x] **2. 运行红灯。** `API_TEST tests/test_schema_contract.py tests/test_integrity_migrations.py`；确认新 head/审计行为断言失败，而非导入环境失败。
- [x] **3. 实现冻结定义与版本分派。** v2 仅增加 `ux_taskrunevent_run_sequence` 和完整外键要求；保留受支持 TEXT/VARCHAR/default 兼容。v1 无版本输入的 changes 仍是冻结 v1 建表/补列/索引，防止新索引要求反向干扰原 revision。
- [x] **4. 添加历史 fixture。** `create_frozen_v1_database(path: Path) -> Engine` 使用受控配置实际跑原 `0001`，不是从当前 ORM 反推；无版本 v1 fixture 也改用冻结元数据，避免随后 ORM 新索引污染历史输入。完整父链样本与原始孤立 fixture 分开，不改原 DDL JSON。
- [x] **5. 锁定 Review Focus 1/2。** `test_frozen_v1_revision_still_executes_unchanged` 断言版本确为 v1、无新索引且三个冻结文件 SHA-256 与实施前一致；`test_legacy_orphans_are_reported_without_creating_parents` 断言缺失父记录被审计发现且旧行/行数不变；直接 Alembic upgrade/stamp/downgrade 继续被拒绝。
- [x] **6. 绿灯与阶段审阅。** `API_TEST tests/test_schema_contract.py tests/test_db_migrations.py tests/test_integrity_migrations.py` 全部通过。仅历史 v1 测试保留 v1 断言；不能全局替换所有 `0001` 字符串。

### Task 2: 每连接外键策略和冻结 v2 迁移操作

**Files:** Create `app/db_engine.py`；Modify `migrations/integrity_v2.py`、`app/db.py`、`app/models.py`；Create `tests/test_database_integrity.py`；Extend `test_integrity_migrations.py`。真正 Alembic 后继 revision 到 Task 3 才注册。

**Interfaces:**
- `create_runtime_engine(url: str, **options: Any) -> Engine` 保留 SQLAlchemy 选项，实例级 connect 监听器在首个物理连接前安装，SQLite 默认连接等待 5.0 秒并保留 `check_same_thread=False`；显式测试连接选项仍可传入。
- 工厂导入不创建产品引擎、不读 .env、不连接库；只为该实例逐连接设置/确认 `foreign_keys=1`，不注册全局 Engine 监听器。
- `apply_integrity_upgrade(connection: Connection, plan: IntegrityUpgradePlan) -> None` 为冻结 v2 内部操作，不 commit、不切换 PRAGMA，要求调用方已准备好重建连接并持有事务。
- ORM 声明同名同列顺序的组合唯一索引；本 Task 以直接调用冻结操作及显式 v2 目标检查验证，不提前改变 Alembic head。

- [x] **1. 写并运行红灯。** `test_every_physical_connection_enforces_foreign_keys` 在测试包装器已隔离的真实 `app.db.engine` 上强制同时借出两个池连接，分别断言 `PRAGMA foreign_keys == 1`；`test_invalid_child_update_and_referenced_parent_delete_are_rejected` 对真实父子记录断言 IntegrityError 和事务回滚。运行 `API_TEST tests/test_database_integrity.py`，应因未执行约束失败。
- [x] **2. 实现引擎工厂并接入 app.db。** 合并而非覆盖 connect_args；连接钩子在事务外设置并读回 PRAGMA；不能静默接受 0 或影响其他未配置引擎。
- [x] **3. 实现 v2 重建和索引。** 使用冻结列投影创建临时新表、复制、替换、恢复固定索引；不先 rename 原表。仅重建 plan 列出的历史缺外键表，完整表不重建；NULL/self-reference 保留合法语义。未知结构和临时表名冲突拒绝，不删除未知残留。
- [x] **4. 加数据保留和拒绝测试。** `test_supported_legacy_constraints_restore_all_values_and_blobs` 比较所有旧列/BLOB 摘要和外键集；`test_complete_v1_tables_are_not_rebuilt` 观测 DDL 不含业务 DROP/重建；重复/非法序号与孤立关系用例断言拒绝且不删行、不重编号。
- [x] **5. 运行绿灯。** `API_TEST tests/test_database_integrity.py tests/test_integrity_migrations.py tests/test_models.py`；正常父链 insert/update 通过，非法关联由数据库拒绝，v2 索引不可写入同一 run 的重复 sequence。仅此处通过尚不能对源库执行迁移。

### Task 3: 将 v2 接入离线协调、备份和副本演练

**Files:** Create `migrations/versions/0002_database_integrity.py`；Modify `app/schema_contract.py`、`migration_runtime.py`、`db_migrations.py`、`migration_backup.py`、`tests/migration_fixtures.py`、`test_migration_backup.py`、`test_migration_lifecycle.py`、`test_db_migrations.py`；Extend `test_integrity_migrations.py`。

**Interfaces:**
- `run_schema_upgrade(connection: Connection, *, before: RowEvidence) -> None` 替换 head 专用 `run_baseline_upgrade`，仍要求受控 permit 和已有事务，不自取维护锁或 commit；所有内部调用一起迁移。
- 此时注册 revision `0002_database_integrity` / down_revision `0001_local_baseline`，同时将公开 `inspect_schema`/HEAD 接到 Task 1 的 v2 目标检查；不能只提前注册 head 令测试包装器在 pytest 启动前失败。
- `upgrade_database`、`prepare_database`、`require_current_schema` 的公开签名保持；CLI status/upgrade、退出码和备份路径规则保持。
- 迁移专用连接预先读取已识别历史结构及重建计划；仅需要重建时在事务外 OFF，再 BEGIN IMMEDIATE 后重新核验身份、结构、数据和计划。计划发生变化则中止，不能事务内改开关。
- `rehearse_backup(backup: MigrationBackup) -> None` 复用同一受控准备/升级路径；临时副本显式置于 `backup.root` 下，源一致备份仍封存不改写。

- [x] **1. 写并运行红灯。** `test_legacy_rebuild_disables_foreign_keys_before_begin_only` 记录专用连接 SQL，断言 OFF 先于 BEGIN，提交后新业务连接为 ON；`test_migration_rehearsal_uses_backup_directory_not_system_temp` 断言副本处于本批 E 盘目录。运行 `API_TEST tests/test_integrity_migrations.py tests/test_migration_backup.py`。
- [x] **2. 改受控 runner。** 先执行旧 baseline 到 v1，再执行 v2；v2 之前及最终均核验预期关系、结构、全部旧值和 BLOB，最终 integrity_check=ok。空库与 current/no-op 路径不做不必要重建或关闭外键。
- [x] **3. 改协调器。** 保留独占维护与分离的只读 backup 连接；锁内预检须在任何 DDL 前完成。副本与源库用相同迁移连接策略；提交后恢复确认 ON 并销毁专用连接，不进入业务池。
- [x] **4. 锁定 Review Focus 3。** `test_wal_backup_does_not_use_reserved_writer_connection` 验证 WAL 已提交内容及 BLOB 完整，backup 有界且不会自锁；`test_changed_rebuild_plan_refuses_before_ddl` 验证预检期间变化不被放行。
- [x] **5. 故障注入。** 参数化 `test_rebuild_failure_keeps_old_rows_and_revision` 覆盖 copy/replace/index/verify；另测 commit 异常及提交后 receipt 失败，断言保留备份、真实阶段和版本，不自动覆盖或把已提交说成已回滚；未知部分状态拒绝盲重试。
- [x] **6. 绿灯与生命周期。** `API_TEST tests/test_schema_contract.py tests/test_db_migrations.py tests/test_integrity_migrations.py tests/test_migration_backup.py tests/test_migration_lifecycle.py tests/test_seed_preservation.py`；重复升级/启动幂等，v1 启动在 seed/recovery/workers 前拒绝，活动 API 拒绝升级，自定义配置不被 seed 重写。

### Task 4: 事务内事件编号、竞争错误和 SSE 回放

**Files:** Modify `app/events.py`；Create `tests/test_event_concurrency.py`；Extend `tests/test_events.py`、`test_chat_events.py`。

**Interfaces:**
- `_acquire_event_write_guard(db: DbSession, task_run_id: str) -> None` 在无自动 flush 的固定 TaskRun 无值变更 UPDATE 中取写锁；调用方须先按顺序 flush 新父行；不改变业务字段，不提交/回滚。
- `EventWriteConflict(RuntimeError)`，固定 code 为 `EVENT_WRITE_CONFLICT`；仅将 SQLite BUSY/LOCKED 类竞争转为此错误，保留原异常链，不吞掉其他数据库错误。
- 保留 stage/append、publish、游标格式和 `_next_persisted_event_created_at` 签名；stage 先写锁、后 MAX/INSERT/时间分配，append 仍提交后通知。

- [x] **1. 写并运行红灯。** `test_independent_connections_append_unique_sequences` 从独立连接在 stage 入口同时起跑，两个有界短事务均成功且 sequence 为 `[1,2]`。为确定性复现旧缺陷，MAX 读取回调仅在 SQLite 原始连接尚未进入物理事务时使用有界双读屏障；进入事务的读取不等这个屏障，不能让正确实现等待已被锁住的第二写者。运行 `API_TEST tests/test_event_concurrency.py`，确认旧实现在唯一索引存在时出现竞争失败，不能让两者都成功。
- [x] **2. 实现写锁和错误分类。** 同 run 最大值读取在写锁之后；已持写事务可复用，同事务多事件不丢失调用方暂存修改；不存在/未 flush TaskRun 不自动造父行。
- [x] **3. 锁定跨进程证据。** `test_spawned_processes_append_without_shared_python_lock` 使用 spawn 子进程、各自连接和入口同步，收集两个真实提交及唯一序号；子进程有超时及错误上报，不继承 DbSession 或仅模拟 MAX 返回值。
- [x] **4. 锁定 Review Focus 4。** `test_wal_read_snapshot_conflict_preserves_transaction_ownership` 在独立合成 WAL 库制造旧快照，断言明确冲突、helper 未 commit/rollback，调用方回滚后可从新事务成功重试；锁超时测试不运行 Provider 或修改文件。
- [x] **5. 验证原子性。** `test_staged_state_and_events_rollback_together` 断言 rollback 后状态/事件均未改变且没有通知；`test_guard_does_not_change_run_fields` 比较除新增事件外的全部 run 字段；持锁者回滚后第二写者仍可完成。
- [x] **6. 验证 SSE。** `test_interleaved_runs_replay_all_pages_with_existing_cursor` 使用相同墙钟时间及两个 TaskRun 的交错提交，逐页回放断言事件 ID 全集相等、无重复、旧游标可解析；继续跑反序通知、固定 high-water 和断线恢复既有测试。
- [x] **7. 运行绿灯。** `API_TEST tests/test_event_concurrency.py tests/test_events.py tests/test_chat_events.py`；不以仅最终 COUNT 或只约束报错代替完整竞争验收。

### Task 5: 统一真实业务连接并修复已证实的事务顺序

**Files:** Modify 文件地图中的四个业务引擎入口、事件生产者、对应业务测试；优先 `tests/test_chat_events.py`、`test_seed_preservation.py` 和经搜索确认的队列/审批/Adapter 测试。

**Interfaces:**
- 业务与评测入口调用 Task 2 的 `create_runtime_engine`，保持原 URL、poolclass、connect_args 和 prepare/seed 语义。
- 每个 stage 调用满足“父行已可见、事务由调用方持有”；API 竞争按现有错误结构返回 HTTP 409 与 `EVENT_WRITE_CONFLICT`，事务所有者回滚后才离开入口。
- worker 竞争沿现有失败/恢复边界处理；不能在 Provider/文件操作外围自动重试整个函数，也不能为记录错误递归无限追加事件。

- [x] **1. 冻结精确调用清单。** 将 `rg -n 'create_engine\(|stage_task_run_event\(|append_task_run_event\(' apps/api/app apps/api/tests` 结果存 E 盘证据，分类业务连接、专用迁移连接、历史构造连接、只读诊断。当前调查有 6 个生产文件创建引擎，四个是业务/评测；其余两个是受控迁移/备份，不机械替换。
- [x] **2. 写入口红灯。** `test_business_fixtures_use_foreign_key_enforcement` 验证工作台入口实际所用引擎为 ON；新增真实“创建计划→TaskRun→事件”和“审批→状态→事件”用例，在 FK ON 下断言父链有效，故障回滚后无半完成状态。用清单中真实测试文件运行，记录断言红灯。
- [x] **3. 统一业务连接。** 新工厂替换四个生产入口和业务测试显式创建点；不得全局 monkeypatch Engine。历史坏库测试保留专用构造器和明确用途；当前普通业务测试仍用 FK OFF 则不能算验收完成。
- [x] **4. 最小调整事务生产者。** 只在测试证实需要的地方明确父行 flush 与冲突回滚；不更新 generation/锁租约计算、不变更 run fencing，不替换原调度或提交时机。
- [x] **5. 锁定 Review Focus 5。** `test_approval_state_and_event_are_atomic_with_foreign_keys`、`test_new_task_run_flushes_parent_chain_before_first_event`、`test_event_conflict_never_repeats_provider_or_file_side_effect` 分别断言审批原子性、父链和外部调用次数恰为一次；无效用户引用沿现有资源校验拒绝。
- [x] **6. 相邻绿灯。** 对清单中的队列、Target Lock、审批、generation、Adapter、群组、Diff/预览测试逐批执行 API_TEST；每批使用新外部库。此前测试里的虚构父 ID 只补成该测试明确创建的有效父链，保留专门非法输入测试。

### Task 6: 端到端隔离验收、旧实现清理和交付

**Files:** Modify 当前迁移/架构/操作说明和状态日志、专项 tasks；清理仅覆盖被替代实现及本专项新临时副本，不扩大模块范围。

**Interfaces:**
- 操作命令仍是 `pnpm db:status` / `pnpm db:migrate --backup-dir <新外部目录>`；本任务不增加 Agent 命令或 PostgreSQL 连接支持。
- 最终 `verification.md` 及 E 盘回执记录 source HEAD/修改文件哈希、测试批次/JUnit、skip 原因、旧值/BLOB 对比、失败阶段和清理清单，不伪造真实 Provider 或远程 CI。

- [x] **1. 隔离命令演练。** 用本批 E 盘完整合成 v1 库，显式设置该库 URL；status 返回 upgrade-required/退出 2，再迁移到新 E 盘备份目录，验证 head、字段/BLOB 和重复升级。整个命令块保存并 finally 恢复原环境；不执行未设隔离 URL 的 db:init/db:migrate。
- [x] **2. 启动和流程演练。** 新库与迁移后的合成库使用独立端口验证启动；执行 ScriptedMock 真实有界写入→真实 Git Diff→固定版本验证→预览 HTTP/内容核对→中断/重试及旧 Session/SSE 回放，保留 Provider 与验收边界。若专用环境不足明确报告，不借产品库或覆盖现有预览。
- [x] **3. 验证后清旧实现。** 全仓检查 `run_baseline_upgrade` 和 `HEAD` 调用者，只移除已被 head runner 替代的重复函数/失效引用；v1 固定文件和兼容测试保留，不能把旧库读取能力当垃圾删除。
- [ ] **4. 清理本专项产物。** 仅对确定由本批创建、无运行引用且处于本批 E 盘目录的临时副本列出路径和大小，执行前核对绝对路径/重解析点并保留备份及所有失败/最终证据。前轮两个排障 context 删除被策略拒绝，本任务不重试、不换命令绕过，也不把已归档当作已删除。
- [ ] **5. 执行最终门禁。** 从实施根运行 `pnpm check`、`pnpm test`、`openspec validate agenthub-database-integrity --strict`、`git -c core.safecrlf=false diff --check`；根 test 已含 `scripts/db-migrations.test.mjs` 包装器测试，不额外重复运行。记录各批实际结果且不重复统计，无新失败/改动不继续无理由重跑。
- [ ] **6. 最终审阅。** 按用户选定执行方式的规则完成审阅；检查冻结 v1 SHA-256 未变、运行连接分类清单没有遗漏、源码/验证版本一致、无意外 DB/备份/凭据进入 Git。必要修复后重跑受影响门禁。用户已授权提交和推送 `codex/database-integrity` 并检查 CI，未授权合并 main。
- [ ] **7. 更新真实状态。** 只有上述实现/演练/门禁通过才勾选 OpenSpec 1.1，报告“隔离库验收通过、实际产品库未升级”。产品库离线升级和 PostgreSQL 按各自审阅/停机与数据保留步骤后续推进，不自动切换。

## 计划自审覆盖

| 设计要求 | 归属 |
| --- | --- |
| 外键按物理连接开启、真实业务父链与资源错误 | Task 2 / 5 |
| 不变 v1、固定 v2、完整/缺外键历史结构、孤立/重复拒绝 | Task 1 / 2 / 3 |
| 独占维护、WAL 备份、事务外开关、副本演练、故障及提交不确定 | Task 3 |
| 数据库写锁内编号、唯一索引、跨进程、状态原子、SSE | Task 2 / 4 / 5 |
| E 盘隔离、实际 Diff/预览、清旧代码、保护数据/证据 | Task 6 |
| PostgreSQL 后续及产品库切换的明确边界 | 全局约束 / Task 6.7；本计划不实施后续数据库替换 |

2026-10-19 按 Native 实施至 Task 6：核心代码和隔离验收已完成，三次本地全量各有一个临时 Git 对象损坏失败，现有新版 Git 也未消除。独立审阅 P2 已红绿修复；完整门禁与最终完成项保持未勾选。缓存清理被自动策略拒绝且未绕过。实际证据见 docs/database-integrity-verification.md 及 E 盘回执。用户已授权提交、推送独立分支并检查 GitHub CI，结果待记录；不合并 main、不升级产品库。
