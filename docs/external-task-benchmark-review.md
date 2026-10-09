# 外部任务基准交付记录

2026-10-07：可复跑的三项基准工具与证据门禁已完成；本次真实 Codex 编码验收为 **0/3**。三个 CLI turn 均有实际事件，TaskRun 均记录为 `completed`，但均未改文件，10 项功能断言全部失败。因此没有声明真实编码成功、模型效果提升或任务成功率收益。

使用方法见 [任务集说明](../apps/api/benchmarks/external-tasks/README.md)，执行器为 [external_benchmark.py](../apps/api/app/external_benchmark.py)。本轮只从固定 Task plan 验证编码路径，没有增加适配器、后端 endpoint、数据库迁移或执行权限。

## 固定输入与复现

- 每轮创建独立的临时 SQLite 与外部 Git 夹具，只允许编辑 `src/domain.mjs`；既有 AgentHub 数据库与开发工作区未被用作目标。
- 验收模块位于目标目录之外，记录源码、任务提示、基线文件、验收器与 suite 的哈希。原始实现完整跑过预期的 3/4/3 项测试，均为失败基线。
- 准备模式没有 Provider 调用，`successRate=null`。真实模式不自动 fallback 到 Mock，所有选定案例均保留在分母中。
- 验收要求非空 Diff、作用域通过、规则 receipt 完整、原始验收/脚手架不变，以及完整数量的功能测试通过。退出零但跳过测试、改验收器、缺失 Provider turn 或 TaskRun 失败都不能获得通过。
- Node 验收进程只授予夹具和验收模块读取，不授予文件写入或子进程；不把 Node 权限模型声明为敌对代码沙箱。验收后再核对文件与 Diff。

正式报告的 `developmentHead` 为 `78e90f4`；基准实现仍未提交，不能单凭这个 HEAD 复现新增工具。报告同时保存实际 app 源码与 suite 哈希，并已逐项核对与当前候选一致。

## 本次真实执行

| 案例 | 真实 TaskRun | 平台终态 | 变更路径数 | 功能通过 | 基准结论 |
|---|---|---|---:|---:|---|
| 标题规范化 | `f17f675c-971c-494b-9f26-5dcee75a4ca7` | completed | 0 | 0/3 | failed |
| 折扣计算 | `d065e606-4785-44a0-b9a5-fa1011448eb6` | completed | 0 | 0/4 | failed |
| 图书搜索 | `7e9f4f37-ec11-4248-b74b-3642d8f1f68b` | completed | 0 | 0/3 | failed |

CLI health 保存的版本为 `codex-cli 0.162.0-alpha.2`。三项都观察到 thread/turn 事件，快照为 v2，准备请求的规则 receipt 和作用域检查有效；但 Diff 为空且功能验收失败，统一触发 `post_check_failed` 和 `diff_invalid`。报告计时为整个尝试时间，不是推理性能或加速证据。

Provider 回复自报只读/文件读取受限，并返回文字代码建议。已确认的事实是没有文件变更；这些回复不能单独证明操作系统沙箱的根因，也不能将回答中的代码应用到目标后冒充这次 Agent 执行结果。模型和上游服务身份仍为未知。当前实现保留真实 TaskRun 终态，通过独立基准判定目标未达成。

## 保留的机器证据

- [最终准备报告](evidence/external-task-benchmark/prepare-final.json)：SHA-256 `dabfdf8b5bf5d1ec48bda3a139e31140b523ff6ac1ec73d7463ed5593cbf9bed`。
- [最终真实三项报告](evidence/external-task-benchmark/suite-final.json)：SHA-256 `12d13359308a376bf2fa4ba0e68c1bcebf9294ba0169c2d2b1cdee36345cb743`。
- [首次小任务](evidence/external-task-benchmark/probe-initial.json)、[允许目标内读取后的尝试](evidence/external-task-benchmark/probe-readable-prompt.json)、[验收门禁完善前的三项运行](evidence/external-task-benchmark/suite-before-evaluator-hardening.json)分别保留原始输入版本和失败，不覆盖或合并为正式分母。前两份小任务报告在工具开发期间生成，字段与最终版本有差异，仅作为尝试历史。

原始 SQLite、外部目标和验收模块保留在本机临时目录中；正式报告的目录前缀为 `agenthub-benchmark-final-live-20261007`。未复制数据库、Provider 凭据或完整宿主配置到仓库。

## 工程验证与后续边界

最终 API 相关回归 **88 passed**，其中新基准回归 **21 项**；覆盖没有 Node、非法输出、未知案例、失败分母、提前退出、修改验收器、没有 Provider turn，以及 TaskRun 失败但功能输出通过。Worker 接入回归使用明确测试替身，不是上述真实 CLI 结果。

Web 全量 **128 passed / 15 files**，`pnpm check`、严格 OpenSpec 与空白检查通过。本轮没有改动现有运行时核心，未重复前一任务的 API 全量 1,324 项；未安装依赖、运行 build/Preview/部署或提交推送。

下一项应独立定位 Codex CLI 的文件读取/写入链路，并验证“完成但无产出”的产品验收策略。本轮没有放宽沙箱或顺带修改 TaskRun 完成语义。当前可以介绍固定基准、独立验收和失败证据能力，不能将这 0/3 写成模型编码成功或量化收益。

后续该定位与完成判定已进入独立任务，最新情况见 [文件访问与完成判定记录](write-completion-validation-review.md)。本文的旧 TaskRun 状态和报告保留为当时事实，不覆盖为后续状态。
