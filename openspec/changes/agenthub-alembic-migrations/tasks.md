## 1. 保留数据的 Alembic 专项

- [x] 1.1 实现固定基线、可识别旧库离线接入、独占维护/一致备份/副本演练、
  API 空库初始化与版本检查、开发者命令、被替代代码清理和数据保留回归。
  - 前置：2026-10-18 用户已审核 design.md 和[书面实施计划](../../../docs/superpowers/plans/2026-10-18-alembic-migrations.md)，选择 Native 顺序实施；最终本地验收完成。
  - 边界：SQLite/SQLModel、现有三个 Adapter、权限和工作树保持；不迁移实际产品库，
    不安装未告知依赖，不删除运行数据，不提交或推送。
  - 验收：空库、现行无版本库和受支持旧库到同一 head；全部旧值/BLOB 不变；
    WAL 一致备份可验证；不兼容结构/活动 API/并发写者拒绝；失败不假记成功且可恢复；
    重复升级、启动和 seed 幂等；旧补列/索引实现及失效引用移除。
  - 验证：隔离迁移专项；健康/模型/种子/维护/工作流相邻回归；根检查、全量 API、
    `openspec validate agenthub-alembic-migrations --strict`、`git diff --check`。
  - 只有实现和相关验证完成后才勾选；不以设计或 strict 校验通过代替实现完成。
