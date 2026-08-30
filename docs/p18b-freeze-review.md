# P18b 记忆有效性演练重建评审

**原冻结日期：** 2026-06-05

**重建复核日期：** 2026-08-07

**4.1 有界工作流复核日期：** 2026-08-29

**4.2 执行边界复核日期：** 2026-08-29

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
- 一次 fresh、有界的产品工作流演练，将两条已保存 MemoryItem 送入真实消息、
  Planner 输入、任务图、调度状态和 frontend coding context 组装路径；同一演练还证明
  普通聊天保持非执行，并让编码任务通过 PlanValidator、scheduler 和 queued TaskRun 边界。

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

## 4.1 有界产品工作流演练

2026-08-29 使用内存 SQLite 和隔离临时 worktree 执行
`app.p18b_workflow_rehearsal`，完整证据保存在
`docs/p18b-bounded-workflow-evidence.json`。该 runner 没有重建并行记忆栈，而是实际调用
`create_memory_item`、`create_session_message`、`build_llm_planner_input`、
`plan_for_message`、任务图校验、scheduler 刷新和 `build_session_context_pack`。

| 证据 | fresh 结果 |
|---|---|
| payload SHA-256 | `42bfc7a1d61bd6efaa4e6dfc3e7b2b371de7e6e2ae43f7e396ab6cfeab3f968b` |
| workspace / coding session | `68490240-9b0c-4810-91d3-9b53ffbec484` / `a5c51974-5299-4ac5-8226-779487edd9e3` |
| coding user message | `86fd272f-288d-4d87-85c1-1bb309d4774a` |
| user-preference MemoryItem | `d0f8508d-b6ef-4cfe-acbc-56728b195f78` |
| project-rule MemoryItem | `41bfed48-c754-45ac-90d9-44f3335e62fe` |
| shared memory snapshot | `ad71a9ae-8f41-4c24-909e-d4e251d43fee` |
| planned task IDs | `b119d32b-7458-4273-b72f-3b1b2bd07542`, `b7ee13f8-a664-468e-b660-73b4805d8ad7`, `140a085b-76c4-4801-afde-212495d0a45c` |
| planner | `deterministic_login_v1`; live Planner `disabled` |
| scheduler states | orchestrator `completed`; frontend `ready`; qa `waiting_dependency` |
| queued coding TaskRun | `f4e39ad9-cf9d-4323-b8e7-134ca66e8eb7`; adapter `codex`; 未执行 adapter |

两条实际 MemoryItem ID 都出现在 Planner 和 frontend coding context 的检索结果中，
二者使用同一个 snapshot ID。持久化任务包含 `taskGraph` 和 `planDraft`，说明运行到达了
真实产品规划路径，而不是只做 retrieval helper 演练。绝对临时路径未写入证据。

该 v2 证据替代 4.1-only 的 v1 payload，同时闭合 4.1 和 4.2。它只将 coding task
推进到 queued TaskRun，不启动 adapter、没有 changed-files，也不声称 task success。

## 4.2 普通聊天与编码执行边界

同一 fresh 演练另外创建独立 Session `fe2e7a76-1664-42fa-a2a9-3cf9a50c8cff`，保存普通
聊天消息 `b681e41a-76f3-4670-a4cb-b4f1cc1eedb8`（内容为“你好”），并调用真实
`plan_for_message`、synthetic planning completion 和 scheduler refresh 路径。结果为 0 Task、
0 TaskRun，只新增一条 orchestrator `chat` 回复
`dfaa0bbd-585c-49aa-b4ef-50c8a24b936f`；因此该 bounded deterministic fallback 路径
保持非执行。

编码路径对已持久化的三任务图重新调用公开
`app.plan_validator.validate_task_graph`，3 个任务全部通过。frontend task 随后由 scheduler
判定为 `ready`，`create_task_run` 成功创建 `queued` TaskRun，并选择 `codex` adapter。
runner 有意不调度 adapter；这证明请求通过计划校验、调度准入和 TaskRun 创建边界，
但不把“进入执行边界”表述为“编码执行成功”。

## 提供者可用性与证据边界

本轮报告中的 provider 证据为：

| 字段 | 值 |
|---|---|
| evidence source | `deterministic` |
| status | `not_requested` |
| provider ID | `null` |
| reason | `P18b deterministic rehearsal did not request live provider execution.` |

上述 bounded workflow 本身没有请求 Claude、Codex 或其他实时 Planner/编码代理，
`not_requested` 不能被解释为 provider 不可用。为闭合 4.3，2026-08-30 另行执行了
一次 `codex-cli 0.151.0` 的 ephemeral/read-only 探针：在系统临时目录中跳过 Git 仓库
检查，请求精确返回 `P18B_PROVIDER_PROBE_OK`；6,234 ms 后以 exit 0 返回该文本，JSONL
中没有 tool-call 事件。证据保存于 `docs/p18b-provider-probe-evidence.json`。

该 live 探针只证明当时 Codex CLI 能获得已认证响应，不是 Planner、adapter、编码
TaskRun、task success 或 changed-files 证据；JSONL 未公开具体 model/upstream provider，
因此不作相应声明。`docs/history/project-state-archive.md` 保留了 2026-06-05 当时相关
API key 未设置的历史记录；该历史环境状态不等同于本次 live 探针。

## 安全边界

- stale/archived 记忆和 pending-review/untrusted 外部建议不会进入活跃指导上下文；
- P18b 不增加自动长期学习、embeddings/RRF/graph 检索、提供者市场、生产部署、
  新适配器或护栏绕过。

上述两项分别由当前 deterministic retrieval 测试和范围审计支持。v2 runner 已实际调用
消息、Planner 输入、公开 PlanValidator、scheduler、TaskRun 创建和 coding context；普通
聊天则保持 0 Task / 0 TaskRun。adapter 未执行的边界已在证据中显式记录。

## 验证

### 2026-08-29 4.1 / 4.2 有界工作流复核

| 检查 | 结果 |
|---|---|
| `tests/test_p18b_workflow_rehearsal.py` | 通过，1 passed；52 条既有 warnings |
| fresh `app.p18b_workflow_rehearsal` | 通过；实际 ID、task states 和 SHA-256 如上 |
| Planner/coding memory ID 与 snapshot | 两条预期记忆均命中；snapshot 一致 |
| chat / execution boundary | 普通聊天 0 Task/0 TaskRun；coding 通过 validator/scheduler 并创建 queued TaskRun |
| live provider / coding execution | Planner disabled；adapter 未执行；不声称成功 |
| P18b 相关回归 | 通过，68 passed；1261 条既有 warnings |
| API 全量回归 | 通过，1130 passed / 1 skipped；15527 条既有 warnings |
| Web / demo-api | Vitest 96 passed；demo-api 5 passed |
| component checks | web ESLint+tsc、API compileall、demo tsc、demo-api compileall 均通过 |
| strict OpenSpec / `openspec list` | 通过；P18b 为 Complete（19/19） |

根 `pnpm check` 首次仍被 Corepack 请求 npm registry 阻塞。使用本机已有的精确
`pnpm@10.33.4` 与只读依赖联接后，web check 通过，但 Bash wrapper 在 Windows 上固定
引用不存在的 `.venv/bin/python`。因此本轮没有把 wrapper 记为通过，而是分别 fresh
执行并通过四个 component check；未安装新依赖。

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
- 普通聊天证据覆盖 bounded deterministic fallback，不替代所有实时 Planner provider 的
  线上行为验证；
- 若后续引入实时提供者证据，必须记录实际 provider/runtime 可用性、失败原因、延迟和
  成本，并继续与 deterministic/fake-client 证据分开标注。

## 冻结结论

P18b 的本地 deterministic retrieval/report、产品工作流、普通聊天非执行和编码准入边界
均具备 fresh 可复核证据，OpenSpec 19/19 任务已闭合，P18b 可以按当前 bounded local
范围冻结。该结论不扩展为实时代理任务成功、生产部署就绪或所有 provider 路径的线上验证。
