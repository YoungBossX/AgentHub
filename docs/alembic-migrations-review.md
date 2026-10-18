# Alembic 数据库迁移验收记录

日期：2026-10-18。当前实施分支 `codex/alembic-migrations`，基线 `ea0d3bc`。
本地实现、独立审查修复及最终回归已完成；不证明实际产品数据库已迁移或远程 CI 通过。

交付阶段：用户随后授权提交、推送 `codex/alembic-migrations` 并检查 GitHub CI。
下文“未提交/未推送”及 verification.json 的相应字段保留本地验收时的快照含义；
远程验证以该分支具体提交的 GitHub Actions 结果为准，不把旧批次状态套到新提交。

## 实现范围

固定 26 张业务表的基线和六组 23 列旧库兼容清单，增加受控 Alembic runner、离线
协调器、一致备份与副本演练、版本/原值核验及新建阶段回执。API 只初始化空库或
检查 current；旧库要求显式离线升级。已有 seed 改为只补缺失记录。

## 已核对的边界

- 所有迁移演练只使用新建外部临时库/夹具；没有停止现行服务、迁移实际产品库。
- 原工作区已有设计文件保留，运行代码在独立 worktree 实现；没有提交或推送。
- 旧局部 helper 的两三列夹具保留为不兼容拒绝用例，不能补造真实业务字段。
- 历史 session/message nullable TEXT 主键变体按非空已有 ID 检查；其他未知 FK 缺失仍拒绝。
- 备份保留 WAL 已提交数据和附件字节；原库 commit 后回执失败单独报告，不冒充回滚。

## 清理映射

删除 db.py 的 ensure_demo_schema_columns/indexes、两个 _ensure_sqlite_demo_schema_*
和 _ensure_table_columns，保留 create_db_and_tables/init_database 的薄接口。
原 test_models、custom_agents、session_organization、message_history、message_regeneration
中的旧 helper 引用改为升级/原值核对或明确拒绝；历史 DDL 不丢弃。
三个隔离评测数据库初始化入口也统一走固定迁移，不留第二套应用 schema 初始化路径。
纯 ORM 单元测试自行建内存表仍保留，不对它们声称已验证平台迁移。

## 验证进度

基线模型/健康 13 passed；初始契约 16 passed；固定 runner 合并 31 passed；
备份/迁移初始合并 45 passed；初始生命周期/seed/健康/Windows 清理 23 passed；
新增工具测试加入后本地工具 23 passed。以上批次重叠且代码版本不同，不相加。

首次组合专项 109 passed / 1 failed：旧 lease 单元测试用不完整 schema 的 SimpleNamespace
冒充 Engine，改成真实 current 临时库后 lease/生命周期复跑 9 passed。
首次根测试的 Web/本地工具通过，但 API collection 因两处旧 helper import 失败；
后续发现共四处引用并迁移，旧库/相邻用例复跑 22 passed。
源身份注入第一次因重建 Windows stat_result 丢失属性而失败，改为仅代理 inode 后复跑通过；
这验证身份变化拒绝逻辑，不声称模拟了任意宿主文件攻击。

最终根 `pnpm check` 已通过。独立审查发现的三项 P2 均已修复，先观察五项断言
失败，再验证修复后的组合专项 62 passed；随后扩大 legacy/current 双路径契约到
26 passed。两项预期 SAWarning 来自表达式索引拒绝用例，不代表放行该索引。
以上批次重叠，不相加。修复后的最终结果单列如下。

真实命令入口已在新外部合成库演练：`db:status` 返回 legacy-compatible/退出 2，
`db:migrate` 返回 upgraded，再次 `db:status` 为 current/退出 0；全部 26 张表的
旧值和附件字节保持，封存备份恢复到另一副本后完整性核验通过。
另一个新外部库的 `db:status` 报告 empty 且未创建文件；两次 `pnpm db:init` 均退出 0，
最终 status 为 current。该演练不连接实际产品库。

环境：Windows、Python 3.12.7、SQLite 3.45.3、SQLAlchemy 2.0.51、SQLModel 0.0.27、
Alembic 1.20.0、Node 22.19.0、pnpm 10.33.4。新增依赖仅 Alembic 及必要的
Mako 1.4.3 / MarkupSafe 3.0.4；既有直接依赖未升级，`pip check` 通过。

## 最终本地验收

`pnpm check` 和修复后完整 `pnpm test` 均退出 0：API 2515 passed / 1 skipped；Web 326；本地工具 24；demo-api 5。
唯一跳过用例为 `test_posix_exact_case_semantics_keeps_distinct_git_spelling_ordinary`（exact-case POSIX semantics regression）。
计划命名的 32 项 Python 测试已与最终 JUnit 核对，
所有最终专项及相邻模块包含在这一完整批次中；39 个修改/新增运行与测试文件的
SHA-256 与启动该批次时一致。其他 OS/Python 版本与真实 Provider 未冒充已验证。
根检查、本地链接/UTF-8/空白检查和 OpenSpec strict 检查的最终状态见证据索引。
实际产品库没有迁移；代码保留在未提交的 `codex/alembic-migrations` 工作树。

## 独立审查处置

| 问题 | 影响 | 修复和证明 |
|---|---|---|
| 生成列可能被当成普通列 | stamp 后正常插入可能失败 | 显式拒绝 generated/identity；legacy 与 current 均有拒绝用例 |
| 同名索引的排序规则未核对 | NOCASE 改变唯一性语义 | 读取 index_xinfo，核对 BINARY/ASC 与冻结列定义 |
| 版本表结构可能漂移 | 缺主键或额外约束仍被识别为 current | 独立核对版本表 PK/FK/CHECK/UNIQUE/索引 |

三项均属于影响可靠性的修复，在同一次修复批次中验证；没有再派发复审。
没有遗留的 Minor 审查项。全量测试、其他 OS/Python 版本及真实库迁移的判断由
实施者按执行证据承担，不能由只读审查替代。

## 实施裁定及代价

按实施账本的发生顺序完整列出：

1. 复用已有 Python/前端依赖目录；没有在新工作树安装前端依赖。代价：这不能证明全新安装可复现。
2. 未获提交/推送授权，保留未提交 diff、账本及 scratch，不执行技能示例的 commit/清理。代价：结果依赖当前工作树，后续提交前需再次核对范围。
3. 冻结定义使用独立 `schema_v1.json`，由固定 Python 模块读取；不从未来 ORM 推导。代价：后续新增 revision 时必须保留已交付定义不变。
4. 两三列旧 helper 夹具不足以支持真实 ORM，保留原 DDL/数据作为拒绝测试；完整旧库用于升级验证。代价：真正缺必需字段的自定义库需单独处理，不能自动补造值。
5. 仅承认有非空已有 ID 的 session/message TEXT 主键历史变体；其他缺 FK 拒绝。代价：未知手改结构需要人工审核，无法直接接入。
6. 三个离线评测入口一并转交固定迁移，避免保留第二套平台 schema 创建逻辑。代价：这些临时库也必须符合固定迁移契约，已有 benchmark 回归覆盖。
7. 未提交代码按 diff 加新增文件清单审查，不以空 HEAD..HEAD 范围代替。代价：审查结论必须绑定冻结源码哈希，后续修改需重新核验。
8. Windows 本地结果不冒充 Ubuntu/Python 3.11 或远程 CI；本机无 WSL/3.11，不为验收另装系统。代价：跨平台回归仍应在后续 CI 验证。
9. 实际产品库未读取/迁移；只测试静态夹具和新临时库。代价：不能据此保证任意实际历史库兼容，真正迁移须先检查状态并确认停机和备份路径。
10. 维护租约是协作锁，不是 OS 安全沙箱；身份复核仅覆盖已测试的有界变化。代价：不能抵抗具备任意宿主文件替换能力的程序。
11. 冻结源码的全量测试用于完成最终组合验收，不重复运行其已覆盖的专项。代价：必须核对计划命名测试与最终 JUnit，不能以总数替代覆盖核对。
12. 复用依赖的工作树需要识别 Vite 解析出的真实依赖路径；只补齐既有允许根的判定。代价：预览边界存在回归风险，因此新增合成负向测试并复验真实 HTTP/浏览器断言，修复后重新运行整套回归。
13. demo-api 包装器未输出 JUnit，按完整根日志的实际 5 passed 和退出 0 留证，不虚构第二份 XML。代价：该部分需结合根日志核对；API 的独立 JUnit 仍完整保留。

最终全量回归覆盖计划列出的全部专项和相邻测试时，用这一冻结源码结果完成最终
组合验收，不重复运行同一组已通过的用例；若全量失败，先处理实际失败再完成验收。

全量后续发现的预览兼容问题：两个批次均在 `/@vite/client` 得到 500；进一步记录
响应体确认是配置守卫把依赖的真实路径误判越界。独立工作树以 junction 复用原仓库
依赖时，Vite 的实际模块路径已在现有允许根中，却未被归为依赖。新增 Node 合成路径
用例先失败，随后仅补齐已允许依赖真实路径的识别；Node 3 passed，真实 HTTP/浏览器
边界 1 passed，包含正常 React/CSS 及受保护/越界/alias/hardlink 拒绝断言。
这属于保证隔离实施工作树可回归的必要修复，不增加新的读取根。相关全量失败批次保留，
不能用局部复验冒充修复后全量通过。

证据索引：[受限验收材料](evidence/alembic-migrations/README.md)。
