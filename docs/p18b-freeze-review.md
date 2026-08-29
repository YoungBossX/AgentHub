# P18b 记忆有效性演练重建评审

**原冻结日期：** 2026-06-05

**重建复核日期：** 2026-08-07

**OpenSpec：** `agenthub-p18b-memory-effectiveness-rehearsal`

## 重建说明

原 `docs/p18b-freeze-review.md` 未出现在现有 Git refs、不可达 tree/commit、主工作树或
隔离工作树中，不能称为已恢复原稿。本文件依据受跟踪的 P18b OpenSpec、当前实现与测试、
`docs/project-state.md` 以及 `docs/history/change-log-archive.md` 重建。历史验证与本轮
重新执行的验证分开列示；没有从缺失原稿推测命令输出、运行 ID 或实时提供者结果。

## 范围

P18b 在 P18 记忆控制平面之上增加本地、有界、可重复的 control/treatment 演练，
用于判断启用记忆是否改善确定性检索和上下文指标。它不把确定性结果表述为真实
Planner 或编码代理成功。

当前实现包含：

- 四个合成且不含私有数据的固定场景；
- 记忆最小化 control 与启用记忆 treatment 的成对评估；
- 复用 P18 记忆存储、检索、上下文和快照能力的结构化报告；
- 对确定性、fake-client 和 real-provider 证据来源的显式区分；
- 对无法由当前证据计算的指标使用 `unknown`，而不是推断正向结果。

## 场景证据

本轮使用固定审计 workspace ID `p18b-recovery-audit` 在内存 SQLite 中重新生成完整
四场景报告。按内置场景顺序以换行连接各场景 stable JSON 后计算的 SHA-256 为
`6ec2bde115d356a73c77c6f6fa616486d80317b4830a0cde794f864d959294c9`，报告 ID 为
`p18b-c4f4af309f672204`。

| 场景 | control recall | treatment recall | treatment precision@5 | treatment 检索 | 排除项进入上下文 | 结论 |
|---|---:|---:|---:|---|---:|---|
| `zh-preference-recall` | 0.0 | 1.0 | 1.0 | `prefer-chinese-summary` | 0 | 确定性检索改进 |
| `project-rule-change-log` | 0.0 | 1.0 | 0.5 | `change-log-required` | 0 | 确定性检索改进 |
| `stale-pattern-exclusion` | 0.0 | 1.0 | 0.3333333333333333 | `current-demo-check` | 0 | 确定性检索改进 |
| `prompt-injection-blocking` | 0.0 | 1.0 | 0.25 | `trusted-secret-guard` | 0 | 确定性检索改进 |

每个 treatment 结果均报告
`improved: treatment retrieved expected memory without extra stale injection`。演练会为
control 和 treatment 创建执行期快照。用于本轮复核报告的实际快照 ID 如下：

| 场景 | control snapshot ID | treatment snapshot ID |
|---|---|---|
| `zh-preference-recall` | `cf3cba53-69a4-4ee7-afcb-1ea050261d19` | `e66cca46-7db3-419d-8a72-9eff429813a4` |
| `project-rule-change-log` | `dbccf6f9-448e-4c01-b426-d33be5698adc` | `d20fee0d-5a7f-46f2-8ceb-c6480c9826d5` |
| `stale-pattern-exclusion` | `914744f3-e8fa-4ca7-bd54-b3d5b11c0320` | `e264a716-9165-4146-b39d-25e1d7897602` |
| `prompt-injection-blocking` | `643d3ed5-7e24-489e-aa85-e45ffc23327e` | `52250ec6-c188-4e15-ae4c-a9388f9dba42` |

这些 ID 是 fresh in-memory run 的临时审计证据，不是跨次运行的稳定基线。跨次回归
应使用上述场景夹具哈希、固定 workspace 下的报告 ID 和逐项指标。

## 聚合指标

| 指标 | 本轮结果 |
|---|---:|
| average treatment preference recall rate | 1.0 |
| average treatment memory precision@5 | 0.5208333333333334 |
| total treatment stale memory injection count | 0 |
| average treatment prompt-injection write block rate | 1.0 |
| average treatment snapshot consistency rate | 1.0 |
| known task success delta count | 0 |
| known change-log missing rate count | 0 |

`taskSuccessDelta` 和 `changeLogMissingRate` 在四个场景中均为 `null`。原因分别是没有
可比较的实时任务证据，以及没有可比较的 changed-file 证据；这两个指标不能据当前
演练声称得到改善。

另外，当前指标存在以下证据限制：

- `crossAgentConsistencyRate` 在 `memory_rehearsal.py` 中直接设为 1.0；
- `snapshotConsistencyRate` 通过对同一个 snapshot ID 按角色重复取值计算；
- `promptInjectionWriteBlockRate` 由排除项未被检索推导，不执行真实写入尝试，且指标
  helper 在尝试次数为 0 时也返回 1.0；
- 完整报告在同一 workspace 中顺序执行四个场景，前序 treatment 写入的 active memory
  会留给后续场景。precision@5 从 1.0、0.5、0.3333333333333333 到 0.25 的变化与这种
  累积一致，不能作为严格隔离的 control/treatment 因果效应证据。

因此这些 1.0 和 precision 数值只能描述当前 deterministic fixture 的运行结果，不
构成多个真实代理、独立快照、真实写入防护或严格因果对照的证据。

## 提供者可用性与证据边界

本轮报告中的 provider 证据为：

| 字段 | 值 |
|---|---|
| evidence source | `deterministic` |
| status | `not_requested` |
| provider ID | `null` |
| reason | `P18b deterministic rehearsal did not request live provider execution.` |

因此本轮没有请求 Claude、Codex 或其他实时 Planner/编码代理，也不声称实时提供者
成功。`docs/project-state.md` 保留了 2026-06-05 当时相关 API key 未设置的历史记录；
该历史环境状态不等同于 2026-08-07 的当前环境探测结果。

## 安全边界与未验证项

- stale/archived 记忆和 pending-review/untrusted 外部建议不会进入活跃指导上下文；
- P18b 不增加自动长期学习、embeddings/RRF/graph 检索、提供者市场、生产部署、
  新适配器或护栏绕过。

上述两项分别由当前 deterministic retrieval 测试和范围审计支持。但是
`memory_rehearsal.py` 及其测试没有实际调用 Planner、coding agent、PlanValidator、
scheduler、adapter 或聊天路由。因此以下验收均为 **UNVERIFIED**：

- OpenSpec 4.1 的“有边界真实工作流演练”；
- 普通聊天保持非执行状态且不创建 coding TaskRun；
- coding 请求仍经过 PlanValidator、scheduler 和 adapter 执行边界。

按 Definition of Done，`tasks.md` 的 4.1 和 4.2 已重新打开；在补齐证据前不得用现有
架构意图替代运行验证。

## 验证

### 2026-08-07 重建复核

| 检查 | 结果 |
|---|---|
| `tests/test_memory_rehearsal.py` | 通过，10 passed；65 条既有 warnings |
| 固定 workspace 的四场景 deterministic report | 通过；报告 ID、夹具哈希和指标如上 |
| `openspec validate agenthub-p18b-memory-effectiveness-rehearsal --strict` | 通过 |
| `openspec list` | P18b 为 `17/19 tasks`；4.1/4.2 已重新打开 |
| 文档 UTF-8 解码、必需章节和相对路径核对 | 通过 |
| `git diff --check -- .gitignore docs/p18b-freeze-review.md docs/project-state.md docs/change-log.md openspec/changes/agenthub-p18b-memory-effectiveness-rehearsal/tasks.md` | 通过 |

严格 OpenSpec 校验只验证制品结构，不验证任务是否具有足够的运行证据。基于当前
代码审计，4.1/4.2 已重新打开，等待真实 workflow/chat-routing 证据。

### 2026-06-05 历史记录

`docs/history/change-log-archive.md` 记录当时以下命令均通过：`pnpm check`、
`pnpm test`、`pnpm demo:api:test`、`git diff --check` 和
`openspec validate agenthub-p18b-memory-effectiveness-rehearsal --strict`。这些是历史
记录，本轮没有把前三个全量 `pnpm` 命令重新执行后再声称为 fresh 结果。

## 限制与高风险延期项

- 确定性检索指标只能证明固定场景下的记忆选择与排除行为，不能证明真实任务质量；
- 实时 Planner/编码代理的 control/treatment 成功率和真实提供者延迟尚无本轮证据；
- 缺少真实 changed-file 对照时，变更日志缺失率保持未知；
- 场景数量有限，未来修改检索、上下文注入或快照语义时必须重跑并对比稳定报告；
- 需要补充真实工作流 smoke，分别证明普通聊天不会创建 coding TaskRun，且 coding
  请求仍经过 PlanValidator 和 scheduler；在此之前 P18b 不能完整冻结；
- 若后续引入实时提供者证据，必须记录实际 provider/runtime 可用性、失败原因、延迟和
  成本，并继续与 deterministic/fake-client 证据分开标注。

## 冻结结论

P18b 的本地 deterministic retrieval/report slice 具备可复核证据，本文件重建了该
部分的评审记录，但没有恢复原冻结文档或证明 P18b 已冻结。OpenSpec 4.1/4.2 要求的
真实工作流 smoke 和普通聊天/执行边界验收仍未验证，因此 P18b 仍是项目级收尾阻断。
该结论也不扩展为实时代理有效性、生产部署就绪或整个 AgentHub 项目已完成。
