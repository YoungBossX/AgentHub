# 为本地 SQLite 接入 Alembic 版本迁移

## Why

当前 `apps/api/app/db.py` 通过 SQLModel `create_all`、启动时补列和手写索引维护结构，
没有持久的 schema revision。继续增加表字段时，旧库识别、升级顺序和失败恢复不够明确。
用户已要求开始 Alembic 专项，并明确保留已有数据、清理被替代的旧代码。

## What Changes

- 保留 SQLModel、SQLite、现有业务模型和全部运行证据，新增 Alembic 固定基线迁移。
- 区分空库、可识别的无版本旧库、已版本化库和不兼容库，不盲目 stamp head。
- 有数据的库只允许离线显式升级；升级前独占互斥、SQLite 一致备份及副本演练。
- API 启动只允许初始化空库或检查已达 head 的库；旧库返回明确的离线迁移指引。
- 将原补列/索引兼容语义收敛到固定迁移，删除被替代的启动 DDL 和相关失效引用。
- 用隔离数据库验证旧值/附件字节保留、WAL 备份、重复执行、失败和跨进程互斥。

## Scope

只有一个实施任务 1.1。包括迁移、必要入口适配、验证和有界代码清理，不开始下一子系统。
不更换数据库，不增加 Docker/Redis/WebSocket，不删除数据库、备份、Session、worktree、
附件、制品或历史验收证据，不自动恢复覆盖源库，不提交或推送。

## Status

2026-10-18：用户已审核设计和实施计划，选择 Native 顺序实施；本地验收完成。
迁移实现与测试仅使用临时库，实际产品数据库未操作。具体设计见 [design.md](design.md)，
[实施计划](../../../docs/superpowers/plans/2026-10-18-alembic-migrations.md)，
验收任务见 [tasks.md](tasks.md)。
