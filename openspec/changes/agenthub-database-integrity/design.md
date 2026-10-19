# 数据库完整性设计入口

本专项唯一设计正文为
[2026-10-19-database-integrity-design.md](../../../docs/superpowers/specs/2026-10-19-database-integrity-design.md)。
本文件只作 OpenSpec 入口，避免两份设计独立演化。

2026-10-19 状态：用户同意书面设计并要求继续，
[实施计划](../../../docs/superpowers/plans/2026-10-19-database-integrity.md)已批准并按 Native 实施。
核心实现及隔离验收通过，本地完整回归有临时 Git 对象损坏失败；任务 1.1 保持未勾选。
用户已授权提交、推送独立分支并检查 GitHub CI，作为独立环境对照。
现有库只读审计未发现预期外键孤立引用或事件重复序号；这是检查时的快照，
不是升级成功证明。当前产品库仍为 `0001_local_baseline`。

设计采用每连接外键开启、固定 v2 迁移、事务写锁内编号及组合唯一索引；
已有数据升级复用独占维护、WAL 备份与副本演练，不删除、不合并、不重编号历史行。
PostgreSQL 的事务/时钟/维护/导入与切换单独实施，不通过改 URL 宣称完成。
