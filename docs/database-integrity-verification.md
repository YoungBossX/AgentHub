# 数据库完整性修复验收记录

本专项为 `agenthub-database-integrity` 1.1，按用户批准的 Native 计划实施。
基线为 `8392b7fb02584ba6b6210705d4c8d4d5513b794e`；工作树位于
`E:\Docker\AgentHub\worktrees\database-integrity`，分支 `codex/database-integrity`。
用户已授权提交、推送本独立分支，并检查 GitHub CI，作为本地失败的独立环境对照。
`c13ebb9` 的 [独立 CI 已通过](https://github.com/YoungBossX/AgentHub/actions/runs/39258085751)：
API2550 passed/48 skipped、Web329、工具24、demo-api5；本机 Git 对象问题未被认定已修复。
用户随后授权归并到唯一 `dev` 并纳入沙箱实现；该归并版另行验证。
不升级或搬动产品库，不实施 PostgreSQL。

## 实现边界

- 业务引擎逐连接启用外键，评测与普通业务测试使用相同工厂。
- 冻结 v2 补齐受支持历史约束并增加 TaskRun/sequence 唯一索引。
  v1 revision、定义及原历史 DDL 保持原字节；孤立引用、空主键、重复或非法序号拒绝升级。
- 协调器控制离线维护、事务外迁移连接设置、独立备份读取、副本演练、原值/BLOB 核验，
  失败回滚；commit 确认丢失按不确定结果处理，不冒充未改动。
- 事件在数据库写保留内编号。stage 不提交或回滚调用方事务，也不提前刷新待完成状态。
  HTTP 写竞争返回 409/`EVENT_WRITE_CONFLICT`，不自动重跑外部操作。
- 旧测试的普通父链显式补齐并排序；历史损坏负例通过限定测试文件的外部演员构造，
  业务连接始终开启外键。没有全局 Engine/Session 补丁、级联删除或生产数据修补。

## 隔离命令及 HTTP 演练

证据根目录：`E:\Docker\AgentHub\database-integrity-20261019-implementation`。
所有新库、备份、日志和临时数据位于 E 盘；原产品库未用于这些测试。

1. 实际 `pnpm db:status` 对完整合成 v1 库返回 upgrade-required/退出 2；
   `pnpm db:migrate` 创建新 `cli-backup` 后到达 v2，status 为 current。
   26 表全部原字段值、行标识和附件字节一致；重复升级未创建新备份。
   见 `cli-*.log`、`cli-verification.json`、`cli-backup/manifest.json` 及阶段回执。
2. 迁移后合成库在独立端口启动，`/health` 为 ready；启动补种子后再次逐条核对备份原行。
   该夹具的占位 JSON 不是合法记忆快照，读取 Session 仍返回原有
   `MEMORY_SNAPSHOT_INVALID`，没有修改它来伪造业务可用。初次失败证据保留。
3. 新隔离库和预先准备的最小 Vite Git 仓库使用真实 API、调度器、ScriptedMock、
   固定验证器与预览服务：自然语言标题修改实际完成，真实 Diff 包含修改；
   预览首页和转换后模块均 HTTP 200，模块包含新标题。
   独立干净 Session 在等待审批时中断，重试创建新 Run 并再次到达等待审批。
   服务关闭后重新打开原库，Session 可读取，HTTP SSE 与数据库事件 ID 顺序一致。
   独立审阅修复后又使用全新 minimal3 库复跑，见 `http-fresh-minimal3-receipt.json`、
   `http-reopen-minimal3-receipt.json`。
   这是脚本演练，不代表真实 Provider 编程；未使用 Docker。
4. 完整 AgentHub 仓库的另一组 HTTP 演练在范围快照扫描时触发 ScriptedMock 运行超时。
   `http-fresh*-stacks.log` 和失败回执保留。最小目标验收不能证明完整仓库性能已改善；
   本专项没有提高超时或削弱范围检查。完整仓库扫描性能列为后续事项。

## 验证与清理状态

关键集成批次 134 passed；历史记忆/QA 夹具修正批次 91 passed。
Native 独立审阅提出一项 P2：事件 guard 之前的真实创建/重试遇锁返回 500。
两个实际接口红灯均复现 500；请求事务拥有者回滚后窄范围分类 SQLite BUSY/LOCKED，
两个接口改为 409；非锁 SQL 错误继续抛出。修复及相邻批次 32 passed，未改变 generation、
租约或最终完成 fencing。原静态审阅报告和红绿日志保留在证据目录。
核心实现及隔离迁移验收已完成，完整回归未通过，OpenSpec 1.1 保持未勾选。
最终数量以完成后的独立批次为准，不累计重复覆盖。

首轮全量及后续诊断保留失败证据：主要为开启外键后暴露的假父 ID 和父子顺序。
一项流程评测在运行源码修改期间将 cohort 标记为 invalidated，保护行为符合预期；
它不能计为通过，最终门禁在固定源码后重新运行。
固定源码后的首次全量为 2,595 passed / 2 skipped / 1 failed：新建的多文件流程夹具
在 Git baseline 准备阶段失败。只读 `git fsck` 确认其临时仓库 loose blob 损坏，
保留原目录和 `final-fixture-git-fsck.log`；同一用例在新目录隔离复跑 1 passed。
第二次完整回归同为 2,595 passed / 2 skipped / 1 failed，损坏出现在另一个全新
后端流程夹具的同一 lockfile blob，原目录和 `second-fixture-git-fsck.log` 继续保留。
源码、策略和原备份哈希未变。没有修补对象或削弱测试。

两次 API 验收原先实际使用 E 盘 Git 2.47；现改用本机已有的 Codex Git 2.53，
仅通过 E 盘固定环境脚本选择当前测试进程的工具链，不安装依赖或更改全局设置。
该配置的 16 项流程评测全部通过，随后完成第三次完整回归及十个流程仓库的额外
Git 完整性检查。第三次完整回归仍为 2,595 passed / 2 skipped / 1 failed，
损坏发生在重试恢复夹具；因此换用已有新版并未消除问题，不能归因于旧 Git 版本。
十个流程仓库的只读 fsck 为 9 个完整、1 个损坏；开发仓库 HEAD 的 lockfile blob
与工作区原文件一致，360 项源码/测试、205 项验证策略及冻结 v1 哈希均未改变。
原备份哈希、26 表原值/BLOB 保留和最小 Vite HTTP 演练已再次核验。
汇总见 `verification-incomplete.json`，没有生成“全部通过”的完成回执。

根检查通过；本地工具 24、Web 329、单独补跑 demo-api 5 通过。
API 的两个跳过项为 POSIX 精确大小写及本运行时不暴露的 Windows 目录瞬态位；
两个 SAWarning 来自有意拒绝未知表达式索引的测试。
本机 Git 对象损坏根因尚未确认，需要独立环境对照；未通过重试或修补对象伪造通过。

已移除被通用 head runner 替代的 `run_baseline_upgrade` 名称及调用；
冻结 v1、历史兼容读取、备份和失败证据保留。演练副本由受控临时目录生命周期回收。
前轮诊断 context 删除曾被自动策略拒绝，本次没有重试或换命令绕过，也未声称删除。
本轮还核对了两个专用 Python 编译缓存目录，共 13,140,898 字节、631 个 pyc 文件；
删除请求在命令执行前被自动策略拒绝，未提供具体原因。缓存仍在原 E 盘目录，
未尝试其他删除方式；数据库、附件、备份、锁和工作树均保留。
