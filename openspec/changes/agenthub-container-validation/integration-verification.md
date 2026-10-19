# dev 分支归并验收

2026-10-19：用户要求先保留全部开发内容，再删除其它分支，只保留 `dev`；
进一步明确授权将本地未提交的固定验证容器实现验证后纳入。

## 保留与整合

- 已提交分支为线性历史：`dev`、工作区改进、Alembic、原 main 均为 `c13ebb9` 祖先。
  首先快进并推送 `dev`，将 GitHub 默认分支改为 dev，再按精确 ref lease 原子删除旧远程分支。
- 归并前 Git bundle 和四个工作树的未提交源码/补丁已写入
  `E:/Docker/AgentHub/branch-consolidation-20261019-02`，核对文件哈希及 bundle 完整性。
  主工作树待合并文档另有保留的 stash 和独立 `primary-pending.bundle`，不丢弃恢复依据。
- 沙箱原始补丁以三方方式导入；两份状态文档保留双方验收历史，生产代码自动合并。
  仅调整新增数据测试的当前 revision 和业务引擎，真实写入测试也使用逐连接外键工厂。
  v1/v2 固定文件、产品数据库、附件、三个 Adapter、默认 native 设置不改。

## 本地新验证

新测试日志、JUnit 路径及源码清单位于上述 E 盘证据目录。

| 门禁 | 结果 |
| --- | --- |
| 当前版本数据兼容红绿 | 写死 v1 时失败；当前 HEAD + 外键引擎修正后 native 通过，Docker 由强制入口另测 |
| 根检查 `pnpm check` | 通过 |
| 本地工具 | 24 passed |
| Web | 333 passed / 44 files |
| 后端定向回归 | 721 passed / 17 skipped，344.75s |
| 真正 `pnpm sandbox:verify` | 18 passed / 0 skipped / 0 failed，318.80s |
| demo API | 5 passed |
| 容器控制器 Node 测试 | 3 passed |
| 独立合并审阅 | 原冻结60文件全部哈希匹配，无 Critical/Important 或阻断 Minor；未冒充执行测试 |

定向回归的17个跳过均为选择显式真实容器入口的用例；实际18项强制资格包括这些用例及
native数据保留对照，不把两个批次相加成独立用例总数。后端定向覆盖容器、检查器、取消、
TaskRun、外键/迁移/事件并发、需求浏览器及修复回执。合并版本完整测试另由对应提交的
GitHub CI 核验，最终提交 SHA、CI URL 和终态保存在证据目录的交付回执。

## 边界

本批真实 Docker 使用已有 `images-20261019-07/images.json` 的两个不可变镜像 ID，
doctor 只代表 metadata_ready，资格由实际 verify 建立。没有安装依赖、重新构建镜像、
启用产品 Docker 后端、迁移产品数据库、重启服务或扩大 Agent 工具权限。
原生完整回归中历史 Git loose-object 失败和实际模型追问上下文预算失败分别保留，
不被本次合并或新测试结果覆盖。删除分支不删除工作树、数据库、备份、镜像或恢复 stash。
