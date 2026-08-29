# AgentHub 变更日志

## Clear the Windows publication gate

**日期:** 2026-08-29

### 变更

- 元数据脱敏同时识别 POSIX 与 Windows 绝对路径，避免 Windows 主机漏掉
  `/tmp/.../.git/...` 一类受保护路径。
- preview 环境在收到 POSIX 风格 PATH 时使用 `:` 解析和重组，保留系统 Node 搜索顺序。
- 修正外部目标 request-snapshot CAS 回归夹具，使 task target、TaskRun worktree 和 queue
  target 指向同一注册目标，测试实际到达预期的策略身份 CAS 边界。

### 验证

- Windows 定向发布回归：3 passed。
- 完整 API 套件：1129 passed，1 skipped。
- Python `compileall`、`git diff --check` 以及 TaskRun scope、P18b、P18c、P19
  四项严格 OpenSpec 校验通过。

## Close P18c with a fresh bounded live-memory rehearsal

**日期:** 2026-08-29

### 变更

- 在同一 Session `e65ba76a-...` 和 memory snapshot `b884d8c2-...` 上重新执行 P18c
  图书管理应用演练，保存六个实际 MemoryItem ID、全部指令/注册表/运行时/context 哈希、
  13 个 changed-files 和 patch SHA-256。
- `P18cSessionSetupEvidence` 现在返回实际 `activeMemoryItemIds`；Windows 项目位置检查会
  展开 `~`，并增加真实 ID、复用和 home 路径回归测试。
- 修复外部目标 TaskRun 的最终启动边界：外部目标使用注册表解析的工作树根，不再错误要求
  等于 Session 工作树；对应测试删除了伪造 Session 路径的 workaround。
- Codex JSONL、Git diff 文本和未跟踪文件行数收集显式使用 UTF-8；这修复了中文应用输出在
  Windows 默认 GBK 下触发的 `UnicodeDecodeError`，并增加解码回归测试。
- 首次真实 Codex 运行因 Corepack 签名 key 不匹配超时；两次不安全临时依赖联接恢复被
  scope fail-closed。最终 Codex turn 完成且 scope `passed`，但 pre-fix Git 解码使 TaskRun
  后处理保持 failed。本轮没有改写该终态，而是在修复后从同一 Git 基线补采证据。
- 未安装新依赖；check/test/build 通过临时验证镜像复用仓库缓存，preview/staging 均返回
  HTTP 200 且进程已停止。合规检查通过，违规为 0。
- 新增 `docs/p18c-bounded-rehearsal-evidence.json` 并重写
  `docs/p18c-freeze-review.md`；P18c 5.1 已闭合为 24/24。

### 验证

| 检查 | 结果 |
|---|---|
| P18c 外部应用 `pnpm test` | 通过，3 tests passed |
| P18c 外部应用 `pnpm check` / `pnpm build` | 通过；Vite 对 Node 22.11.0 给出版本 warning |
| Preview / local staging smoke | 均 HTTP 200；进程已停止 |
| P18c compliance | passed；0 violations |
| `tests/test_diffs.py tests/test_codex_adapter.py` | 31 passed；303 条既有 warnings |
| P18c 定向测试与 Windows UTF-8 回归 | 46 passed；367 条既有 warnings |
| P18c strict OpenSpec | 通过；24/24 tasks |
| whitespace / UTF-8 / JSON / Markdown 链接 | 通过 |

## Reconstruct and freeze P19 planner routing evidence

**日期:** 2026-08-29

### 变更

- 完整复核 P19 proposal/design/spec/tasks、当前 planner contracts/providers/routing/mission
  trace 实现、历史提交和受跟踪变更日志；确认原 `docs/p19-freeze-review.md` 与 P18c 文档
  一样受旧 `docs/` ignore 规则影响未进入 Git。
- 新增 `docs/p19-freeze-review.md`，记录共享 planner prompt、非任务 fallback、
  PlanValidator/target 边界、planner evidence、P18c task-creation smoke、真实 coding provider
  边界和剩余风险；不称为原稿恢复。
- 当前三文件 planner 测试首次因工作树根本地 SQLite 未初始化而有 10 个 background worker
  `no such table: targetlock`；执行 `python -m app.db` 创建可清理测试库后，同一测试集
  121/121 通过，确认不是 P19 路由回归。
- 在 detached P19 最终提交 `adbadc6` 上初始化同类测试库并 fresh 验证，115/115 通过。
- 本轮 P18c 有界演练已从 active external target 创建 scoped frontend Task 并进入真实 Codex；
  P19 特有的 `assistant_reply` misroute 路径由当前回归测试验证。未把 fallback planner
  表述为真实 LLM planner 成功。
- `.gitignore` 仅新增放行 `docs/p19-freeze-review.md`；P19 保持 Complete。

### 验证

| 检查 | 结果 |
|---|---|
| 当前 planner/provider/routing/trace tests | 121 passed；1247 条既有 warnings |
| detached `adbadc6` 同类 tests | 115 passed；1043 条既有 warnings |
| P19 strict OpenSpec | 通过 |
| 当前 P18c routing/live smoke | scoped Task 创建；真实 Codex provider 证据已冻结 |
| 历史 pnpm/check/demo-api/diff 结果 | 仅作为 2026-06-07 受跟踪历史证据，不称为本轮重跑 |

## Reconstruct P18c freeze evidence

**日期:** 2026-08-29

### 变更

- 依据受跟踪的 `docs/project-state.md`、历史变更日志、P18c OpenSpec 和实现测试，
  重建 `docs/p18c-freeze-review.md`；不把重建稿称为原稿恢复。
- Git 追溯确认 `docs: add p18c freeze review` 等提交与父提交共享同一 tree，原文档受
  当时 `docs/` ignore 规则影响从未进入可达 Git 对象。现有 worktree、refs、不可达
  trees 和本机历史数据库均没有原稿或对应历史实体。
- 重建稿保留了可由受跟踪历史交叉核对的 provider、session/task/run、snapshot、
  Diff/Review、check/test/build、preview/staging、合规指标、首次失败与后续修复证据。
- 原历史会话的精确 AGENTS/CLAUDE 哈希、活跃记忆实例 ID 和完整 changed-file 清单
  无法从当前资料恢复，因此 P18c 5.1 重新打开，P18c 不宣称完整冻结。
- `.gitignore` 仅新增放行 `docs/p18c-freeze-review.md`，未放行其他内部文档。
- P18c session-setup 测试改用 `Path.parts` 核对目录尾部，消除 Windows `\\` 与
  POSIX `/` 分隔符差异；生产 setup 行为未变。

### 验证

| 检查 | 结果 |
|---|---|
| P18c 定向测试（修复前） | 12 passed / 1 failed；失败仅为 Windows 路径分隔符断言 |
| P18c 定向测试（修复后） | 13 passed；49 条既有 `datetime.utcnow()` warnings |
| `openspec validate agenthub-p18c-live-memory-compliance-library-app --strict` | 通过 |
| `openspec list` | P18c 为 `23/24 tasks`；5.1 已重新打开 |
| 当前 pnpm 可用性 | `pnpm --version` 在 Corepack 请求 npm registry 时失败；隔离工作树无 `node_modules`，未静默安装依赖 |
| 原稿 Git/worktree/database 追溯 | 可达对象 0；不可达 tree 路径匹配 0；现有数据库历史 ID 匹配 0 |
| Markdown 相对链接扫描 | 145 个 Markdown 文件，0 个缺失目标 |
| UTF-8 与 whitespace 检查 | 6 个 P18c 相关变更文件严格 UTF-8 解码通过；tracked diff 和新文档均无 whitespace error |

## Reconstruct P18b evidence review

**日期:** 2026-08-07

### 变更

- 重建缺失的 `docs/p18b-freeze-review.md` 评审记录，但不称为恢复原稿或证明已冻结。
  在所有可达 refs、不可达 Git
  tree/commit、主工作树和隔离工作树均未找到原稿后，依据受跟踪 OpenSpec、实现、
  测试、项目状态和历史变更日志重建。
- 使用固定审计 workspace 重新生成四场景 deterministic report，记录稳定的报告
  ID、场景夹具 SHA-256、control/treatment 指标、provider `not_requested` 状态、
  unknown 指标及高风险延期项。
- 将 2026-06-05 归档的全量命令结果与 2026-08-07 fresh focused verification
  分开，未声称本轮存在实时 Planner 或编码代理成功。
- 最小放行 `.gitignore` 中的 `docs/p18b-freeze-review.md`，确保恢复制品可被 Git
  发现；未放行其他被忽略的内部文档。
- 代码证据复核发现当前演练未调用 Planner、coding agent、PlanValidator、scheduler
  或聊天路由；cross-agent 指标为硬编码，同一 snapshot ID 被按角色重复计算，prompt
  block 未执行真实写入尝试，四场景同 workspace 顺序运行也会使后续 precision 受前序
  memory 影响。相应收紧结论：仅 deterministic retrieval/report slice 通过，OpenSpec
  4.1/4.2 已重新打开，P18b 项目级阻断未解除。

### 验证

| 检查 | 结果 |
|---|---|
| `tests/test_memory_rehearsal.py` | 通过，10 passed；65 条既有 warnings |
| 固定 workspace 四场景 deterministic report | `p18b-c4f4af309f672204`；聚合 recall 1.0、precision@5 0.5208333333333334、stale 0 |
| `openspec validate agenthub-p18b-memory-effectiveness-rehearsal --strict` | 通过 |
| `openspec list` | P18b 为 `17/19 tasks`；4.1/4.2 已重新打开 |
| P18b 重建评审结构、UTF-8 与路径核对 | 通过 |
| `git diff --check -- .gitignore docs/p18b-freeze-review.md docs/project-state.md docs/change-log.md openspec/changes/agenthub-p18b-memory-effectiveness-rehearsal/tasks.md` | 通过 |

## Closeout documentation reconciliation

**日期:** 2026-08-07

### 变更

- 在 `docs/project-state.md` 顶部增加当前快照，明确现存 OpenSpec 中带任务清单的
  change 已无未勾选任务，同时避免把 `No tasks` 误报为实现完成。
- 记录 checkbox 与验收制品之间的漂移：审计当时 P18b、P18c 和 P19 的任务要求对应
  冻结文档均不存在；P18b 文档后续虽已恢复，但 4.1/4.2 证据缺口仍阻止完整冻结，
  P18c/P19 文档仍缺失。
- 明确项目状态文档按时间累积；后文 P19、P24、P25 等阶段性的“正在进行”或
  “等待冻结”措辞是历史快照，不再覆盖当前状态。
- 核实修改前既有文档中的 80 处文本指向 36 个不存在文档，且均为反引号路径而非
  Markdown 链接；其中 18 个可确认由公共仓库清理提交 `88cb0e8` 删除，另外 18 个的
  来源和处置未确认。
- 澄清当前 P18 实现会在运行时编译并哈希 `AGENTS.md` / `CLAUDE.md` 指令制品，
  但当前 Git 基线从未跟踪根目录 `CLAUDE.md`；不据此扩展规范结论。

### 验证

| 命令 | 结果 |
|---|---|
| `openspec list` | 所有带任务清单的现存 change 均为 `Complete`；该命令不验证任务引用的验收文件是否存在 |
| `rg -n "^- \\[ \\]" openspec/changes -g tasks.md` | 无未勾选任务 |
| OpenSpec 任务引用文件核对 | 审计当时 P18b、P18c、P19 的三份必需冻结文档缺失；后续状态见顶部恢复记录 |
| Markdown 相对链接只读扫描 | 142 个 Markdown 文件，0 个缺失目标 |
| `git diff --check -- docs/project-state.md docs/change-log.md` | 通过 |

## Prepare-scope failure ownership fence

**日期:** 2026-08-07

### 变更

- Early prepare-scope failures now persist `failed` only while the exact queued
  pre-launch TaskRun and running durable queue ownership snapshot still matches.
  Missing, terminal, already-active, replaced, or drifted ownership returns the
  original scope error without overwriting the competing durable state.
- The snapshot also binds the RequestLaunchSnapshot execution fields, including
  agent, worktree, heartbeat, and lease expiry. Failure persistence rechecks the
  lease against SQLite database time while holding the same writer fence, so an
  expired lease or direct-SQL field drift cannot be terminalized by a stale run.
- Write-mode snapshots additionally bind the in-memory acquisition context's
  private exact lock id. Under the same writer fence, failure persistence requires
  that exact durable `TargetLock` generation to remain the unique current held
  write lock for the target, session, TaskRun, and runner with a current lease.
  Readonly failure persistence does not issue `TargetLock` SQL.
- The fresh ownership read and existing failure lifecycle transition begin under
  a SQLite `BEGIN IMMEDIATE` writer fence. A concurrent queued-owner CAS cannot
  commit between validation and the terminal transition; after the transition it
  observes a CAS miss and cannot overwrite the failure.
- Malformed canonical context was confirmed to already use the ordinary owned
  prepare-failure path. Invalid launch-snapshot input is likewise validated before
  the private persistence-ownership exception boundary; actual CAS ownership loss
  remains privately classified and preserves competing durable state.
- Request launch snapshots now derive their expected queue mode and lock key from
  the validated durable execution-access classifier. The separate task-plan
  `write_lock_required` fact remains frozen for later plan-drift detection. This
  allows a capability-upgraded ScriptedMock review to retain its persisted write
  queue/lock contract without granting write access to a real readonly adapter.
- The durable execution-access classifier now also requires the queue mode to
  match the effective mode recomputed from the current Task and the TaskRun's
  stored adapter type using the same capability policy as `create_task_run()`.
  A queue-only readonly-to-write drift therefore fails before target-lock
  acquisition, scope checkpoint creation, or adapter launch. Normal ScriptedMock
  capability upgrades and adapters declared review-only before creation retain
  their write and readonly contracts respectively. No schema or additional
  private creation-time field was needed.
- Strict execution classification never falls back to the mutable Agent adapter.
  It accepts only a non-empty, whitespace-canonical `metrics_json.adapterType`
  present in the supported capability registry. Malformed metrics JSON and
  missing, non-string, blank, or unknown adapter types fail before lock,
  checkpoint, binding, artifact, or adapter side effects. Display and historical
  callers retain the existing `adapter_type_for_run()` fallback.
- The positive manual-preview scope fixture now retains its creation-time
  `scripted_mock` adapter provenance alongside the real write queue and launch
  binding. It therefore exercises durable scope-pass acceptance without relying
  on the mutable Agent fallback. No production behavior was changed.
- Four legacy adapter reentry and stream ownership-loss fixtures now construct
  the same final-launch contract as production. After the durable queue is
  running they persist a fenced request context and capture its real launch
  snapshot, then reserve launch through the current `RunSupervisor` generation
  and recheck that exact generation at the final boundary. The reentry case
  deliberately reuses the frozen snapshot and generation for its second attempt.
  No production guard or reservation behavior was changed.
- Three older scope/stream fixtures now establish valid creation-time ownership.
  The unavailable-baseline case creates a TaskRun against a registered supported
  external target, then removes only the registry row while keeping the Task
  target stable; capture therefore exercises a real registry miss and confirms
  the unavailable evidence does not expose the former host root. Timeout and
  error-stream cases use a real QA/review assignment, declare ScriptedMock
  review-only before run creation, and assert both persisted
  `adapterType=scripted_mock` and a genuine readonly queue before checking exact
  interrupt, timeout failure, and finalizer suppression. No production code was
  changed.
- Two provider gateway assignment tests now use the suite's synthetic healthy
  provider probe. They continue to exercise runtime and retry assignment
  resolution without depending on whether the local Claude CLI is installed.
- Context-pack recent messages now use SQLite insertion order as the
  same-timestamp tie-breaker instead of random UUIDv4 order. The regression
  fixes both messages to one timestamp and deliberately adverse IDs, proving
  that provider-visible conversation order remains chronological.
- The recovery fixture now gives its semantic upstream task a lower explicit
  scheduler priority than the downstream task. Removing the downstream
  dependency can no longer let a same-microsecond UUID tie-break place it ahead
  of the upstream run and trigger an unrelated file-overlap conflict. Production
  scheduler and recovery behavior were not changed.
- The session-queue fixture likewise assigns the requested first write a lower
  priority than the second write. FIFO position and blocked-waiter tests now have
  deterministic scheduler order even when both Tasks share a creation timestamp;
  no queue or scheduler production behavior changed.

### TDD 与验证

| 命令 | 结果 |
|---|---|
| nonqueued `streaming` / `collecting_diff`（RED） | 退出码 1；2 failed。旧 helper 吞掉原 scope error 并覆盖为 `failed`。 |
| concurrent queued-owner CAS（RED） | 退出码 1；1 failed。旧实现允许 competing writer 在 failure transition 前提交。 |
| failure ownership 与 request-generation 聚焦矩阵（GREEN） | 退出码 0；24 passed，覆盖 capability drift/malformed、generation replacement、terminal/nonqueued/active/identity drift 与并发 CAS。 |
| readonly capability early gate（GREEN） | 退出码 0；6 passed。 |
| omitted execution fields / DB-time expired lease（RED） | 退出码 1；3 failed。旧 snapshot 会把 direct-SQL agent/worktree drift 和 expired lease 覆盖为 `failed`。 |
| malformed context / invalid pre-CAS snapshot 诊断 | malformed context 已按预期通过 owned failure；invalid pre-CAS snapshot RED 证明其被错误包装为 private persistence ownership error。 |
| review finding 完整去重矩阵（GREEN） | 退出码 0；30 passed，包含新增 execution-field/lease/pre-CAS/context 节点与原 C1、readonly、terminal、active、identity、generation 回归。 |
| same-owner write lock A→B generation（RED/GREEN） | RED 退出码 1；旧 helper 把已失去 exact lock generation 的 queued TaskRun 覆盖为 `failed`。GREEN 退出码 0；原 scope error 被传播，TaskRun/queue 保持 queued/running，B 保持 held。 |
| readonly no-TargetLock-SQL 与最终聚焦矩阵 | readonly malformed-context owned failure 在 SQL hook 下通过；加入 write-generation 回归后的去重矩阵退出码 0，31 passed。 |
| ScriptedMock readonly-plan/write-capability integration（RED/GREEN） | RED 退出码 1；request snapshot 按 task-only readonly 推导而拒绝 durable write queue，TaskRun 以 `TASK_RUN_SCOPE_UNVERIFIABLE` 失败且无文件 mutation。GREEN 退出码 0；真实 mutation、scope pass、execution binding 与 completed lifecycle 均成立。 |
| readonly capability 与 C1 相邻去重矩阵 | 退出码 0；34 passed，覆盖真实 readonly adapter、capability upgrade/rejection、exact lock、terminal/active/identity 与 request-generation 回归。 |

| Durable queue mode provenance (RED/GREEN) | RED exit 1: a run created readonly but drifted only in queue mode/key reached prepare far enough to create `preRunCheckpoint`. GREEN target group exit 0: 4 passed; the drifted run failed with no held lock, checkpoint, binding, artifact, or adapter run, while normal ScriptedMock write upgrade, real write execution, and real readonly completion remained valid. |
| Readonly and C1 provenance matrix | Initial 5 failures identified an old helper that forged readonly by rewriting a write queue and deleting its checkpoint. After the fixture declared review-only capabilities before `create_task_run()`, the deduplicated new/readonly/C1 matrix exited 0 with 31 passed. |
| Persisted adapter provenance (RED/GREEN) | RED exit 1 with 5 failed: missing, non-string, blank, unknown, and malformed-JSON adapter provenance all reached write preparation and created a checkpoint through fallback/conservative classification. GREEN target group exited 0 with 9 passed; all invalid cases failed before lock/checkpoint/binding/artifact/adapter while normal write and readonly paths remained valid. |
| Strict adapter provenance plus readonly/C1 matrix | Exit 0; 36 passed with the five adapter-provenance cases added to the deduplicated queue-mode, readonly capability, exact-lock, terminal/active/identity, and request-generation coverage. |
| Final-launch fixture contract (RED/GREEN) | RED exit 1 with 4 failed: adapter reentry stopped at missing `expected_launch_snapshot`, while both slow-interrupt parameters and the bound-stream case timed out because stream launch was refused before the test behavior began. GREEN exit 0 with 4 passed after using real fenced snapshots and exact supervisor generation reservation/ownership guards. |
| Final-launch fixture adjacent matrices | Exit 0 in both groups: 40 passed for the four corrected nodes plus readonly/C1 coverage; 30 passed for adjacent final-launch, stream ownership, readonly lease, stale-event, and finalizer behavior. |
| Stable-target and readonly stream fixtures (RED/GREEN) | RED exit 1 with 3 failed before their asserted behavior: the baseline fixture drifted Task target after creation, while timeout and error-stream fixtures had write queues without claim/lock ownership. GREEN exit 0 with 3 passed after a stable external-target registry miss and genuine creation-time readonly queues. |
| Baseline and execution-access adjacent matrices | Exit 0 across all groups: 8 passed for adjacent scope-baseline capture/lock/privacy cases, 43 passed for the three corrected nodes plus access-mode/C1/final-launch fixture coverage, and 30 passed for adjacent final-launch/stream/readonly behavior. |
| QA/ScriptedMock dispatch provenance review | P2 review found that the timeout and error-stream fixtures persisted Codex while directly executing ScriptedMock. After moving both to a real QA/review creation path, the focused set passed 3 tests, timeout/finalizer/readonly/final-launch adjacency passed 13 tests, and strict access-mode/C1 coverage passed 38 tests. The error-stream case also asserts `TEST_FAILURE`. |
| Context-pack same-timestamp ordering regression | Exit 0; the focused deterministic node passed, and the expanded `context_pack or canonical_context` matrix passed 8 tests with 283 deselected. |
| Provider gateway assignment fixture (RED/GREEN) | RED exit 1 with 2 failed because both assignment-focused tests reached the real health probe and required a locally installed Claude CLI. GREEN exit 0 with 2 passed using the existing synthetic healthy probe; the adjacent assignment/runtime/trace matrix passed 13 tests and the complete provider gateway contract passed 20 tests. |
| Manual preview durable adapter provenance (RED/GREEN) | RED exit 1: the positive scope-pass fixture omitted `metrics_json.adapterType` and correctly failed closed before preview service invocation. GREEN exit 0 for the focused node after persisting `scripted_mock`; the complete artifact scope guard file passed 19 tests. |
| Recovery scheduler-order fixture (RED/GREEN) | RED exit 1 during a 500-iteration same-process stress loop with `Blocked by file overlap conflict`, proving UUID ordering could reverse same-time tasks. GREEN completed all 500 iterations; the fresh focused pytest passed 1 test. |
| Recovery/lock adjacency matrix | Exit 0; 13 passed across complete `test_recovery.py` and the adjacent terminal release, stale cleanup, file-overlap, holder uncertainty, terminal-holder, heartbeat recheck, and exact-boundary lock cases. |
| Session-queue scheduler-order fixture (RED/GREEN) | RED exit 1 with `Blocked by file overlap conflict` during repeated FIFO execution. GREEN completed 500 alternating executions of the two affected nodes; complete `test_session_queue.py` passed 6 tests. |
| Session-queue scheduler/lock adjacency | Exit 0; 9 passed across terminal release, stale cleanup, file-overlap, holder uncertainty, terminal-holder, heartbeat recheck, and exact-boundary lock cases. |

## Exact-generation execution lease 与旧 adapter event fencing

**日期:** 2026-07-27

### 变更

- 新增进程内不可变 execution lease token，绑定 TaskRun、Task、Session、runner、持久化 access mode、launch attempt、durable queue entry、target 以及私有 exact `TargetLock.id`。write 续租在 SQLite `BEGIN IMMEDIATE` 内分别复核 TaskRun 与 exact held lock 的当前 lease，并以两个 CAS 写入同一新 expiry；任一 ownership mismatch、过期 lease、generation 轮换、CAS miss 或异常都会整体回滚。readonly 只续 TaskRun，既不查询也不创建 TargetLock，但 token 构造、续租和即时 ownership guard 都会复核 durable queue entry 的 TaskRun/Task/Session、target、mode、`running` state 与 `started_at`，queue/target 漂移一律 fail closed。
- execution binding/attempt 持久化后、底层 adapter `createRun` 前启动周期续租；默认 interval 为 lease 的三分之一，每个 tick 使用基于当前 engine 的独立 DbSession。续租覆盖 adapter stream 与整个 scope/completion finalizer；两段操作均与 ownership-loss waiter 竞争，ownership lost 会取消当前操作并经现有 supervisor interrupt 路径中断已绑定 adapter run。timeout、正常完成、用户 interrupt 和异常退出都会 cancel 并 await renewal/stream/finalizer task。
- adapter-run 绑定和每个 adapter event 摄取均增加局部 `BEGIN IMMEDIATE` fence，且 `run_adapter_event_stream()` 强制要求 callable `ownership_guard`，缺失 guard 会在 `createRun` 前拒绝。每个 event 在落库和状态更新前必须匹配 request TaskRun、当前 `adapter_run_id`、active owner、launch attempt，以及 write run 的 exact current lock generation/lease。stale recovery 或用户 interrupt 后到达的旧 completed event 被忽略，不会清空既有 error、写入 completed event、进入 scope finalizer或创建 artifact；跨 TaskRun event 同样被拒绝。该局部事务不扩展为全局 outbox/durable publish 重做。
- production `RunWorker.run_once()` 现在在第一次 queue scan/claim 前调用既有 `recover_stale_runs()`；recovery 异常直接终止本轮，不扫描或认领 queue。既有 exact-generation recovery、legacy held-holder 排除和 queue reconcile 顺序保持不变。
- 私有 lock generation 只存在于 `repr=False` 的进程内 token/acquisition context，不进入 adapter request/event、metrics、SSE、diagnostics 或 trace。未新增 schema/entity、adapter、依赖、WebSocket、Docker、daemon 或平台能力；未处理 runtime context compare-delete、IntegrityError 范围缩窄或全局 delivery/outbox。

### TDD 与验证

| 命令 | 结果 |
|---|---|
| B1 两个 renewal 节点（RED） | 退出码 1；2 failed，均因 immutable `_ExecutionLeaseToken`/renew helper 不存在。 |
| B1 两个 renewal 节点（GREEN） | 退出码 0；2 passed。generation A token 无法续租同 holder 的 generation B，lock CAS miss 会回滚 TaskRun lease。 |
| B2 paused-stream periodic renewal（RED） | 退出码 1；先观测到 claim 后 TaskRun/lock 初始 lease 不同，修正测试为分别记录旧值后，adapter 已进入 stream 但等待两个 renewal tick 超时。 |
| B2 paused-stream periodic renewal（GREEN） | 退出码 0；1 passed。两个 tick 后 TaskRun 与原 exact lock id 同步延长，在两条旧 lease 边界后 recovery 返回空。 |
| B3 late/cross-run adapter events（RED） | 退出码 1；2 failed。用户 interrupt 后旧 completed 仍落库，跨 TaskRun completed 仍写入另一 run。 |
| B3 stale-recovery old completed（RED） | 退出码 1；1 failed，旧 stream 把 `failed/TASK_RUN_STALE` 改回 `collecting_diff`。 |
| B3 三个 event fence 节点（GREEN） | 退出码 0；3 passed。旧 completed 不落库、不清 error、不进 finalizer，跨 run event 被拒绝。 |
| B4 production worker recovery wiring（RED/GREEN） | RED 退出码 1；只有 `queue_scan`。GREEN 退出码 0；1 passed，顺序为 recovery 后 queue scan，recovery 异常时没有 scan。 |
| 完整 adapter event 与 B1-B4 聚焦集合 | 退出码 0；12 passed。 |
| Reviewer：scope finalizer ownership-loss 回归 | 新增节点通过；证明 adapter stream 已结束后，finalizer 仍持续监听 exact execution lease ownership loss，丢失归属后取消 finalizer 并 fail closed。 |
| Reviewer：readonly durable queue/target（RED/GREEN） | RED 暴露 readonly token 仅信任 metrics binding、未复核 durable queue target 的缺口；GREEN 2 passed，覆盖有效绑定及 queue target 漂移拒绝。 |
| Reviewer：缺失 ownership guard（RED/GREEN） | RED 暴露公共 stream helper 可在无 fence 时启动 adapter；GREEN 1 passed，缺失 callable guard 在 `createRun` 前被拒绝。 |
| 完整四个 adapter 文件 fresh 回归 | 修复 reviewer 回归后首次为 39 passed / 6 failed；六项均来自 ScriptedMock 测试 helper 的伪造 Session ID。夹具改为从 TaskRun 对应 Task 读取真实 Session 后退出码 0；45 passed。 |
| target-lock、recovery、failure-recovery 与 B/worker 节点 fresh 矩阵 | 退出码 0；53 passed，覆盖三个完整相邻文件和 12 个 B/worker 目标节点。 |
| 最终 fresh B 分组回归 | 两组均退出码 0：完整 adapter 矩阵 45 passed；相邻 lease/recovery/worker 矩阵 53 passed。 |
| 相邻 timeout/interrupt/scope launch/worker recovery 18 节点 | 16 passed / 2 failed；两项旧 direct-execute fixture 在进入本次 lease/event 路径前即由既有 access classifier 将 `writeMode:false` 任务判为缺失 target 的 write run，并以 `TASK_RUN_SCOPE_UNVERIFIABLE` 拒绝。本次未修改该既有 OpenSpec 1.3 fixture/binding 范围。 |

## Immutable TaskRun execution access mode (OpenSpec 1.3)

**Date:** 2026-07-27

### Changes

- TaskRun completion, stale-scope classification, and artifact guards now share
  one internal execution-access classifier instead of re-evaluating the mutable
  Task plan. The classifier binds the persisted queue entry to the exact
  TaskRun, Task, Session, target, access mode, lock key, and launch evidence.
- A launched write run remains a write run even if its Task is later changed to
  readonly. A readonly bypass requires matching readonly launch evidence and
  fails closed when write checkpoint or scope evidence exists.
- Run preparation and launch-time baseline selection use the same persisted
  access mode. Missing, mismatched, or contradictory bindings fail with
  `TASK_RUN_SCOPE_UNVERIFIABLE` before artifact or success side effects.
- Enqueue-time access mode now also includes the final selected adapter's
  declared capabilities. File-edit or shell-command support conservatively
  requires a write queue entry and write checkpoint even when the Task itself
  is a readonly review; an unknown declaration also remains write-scoped.
- Every adapter now passes a durable gate immediately before `createRun`. The
  internal-only `taskRunExecutionAccessBinding` binds TaskRun, Task, Session,
  queue entry, access mode, runner, and execution attempt; write attempts must
  match the launch baseline attempt, while readonly attempts are reclassified
  and rebound against the current queue before adapter launch. Post-launch
  classification additionally requires `TaskRun.started_at` and the real
  `adapter_run_id`, so queue timestamps alone are not accepted as evidence.
- The launch gate dumps and strictly revalidates every capability schema field
  into an independent snapshot before streaming setup, then compares it with a
  fresh strictly validated concrete adapter read before delegation. Malformed
  or raising capability providers, missing or post-assignment-invalid fields,
  snapshot drift, and file-edit/shell support on a readonly queue fail closed
  before `createRun` and before the internal execution binding is persisted. A
  write queue is never downgraded by an immutable concrete capability response.

### TDD and verification

| Check | Result |
|---|---|
| Representative artifact/completion/shared-classifier RED | Exit 1; 6 failed. Four manual artifact routes bypassed the guard, write completion was incorrectly reclassified readonly, and the shared classifier did not exist. |
| Focused immutable-mode GREEN | Exit 0; 10 passed. Covers four artifact routes, write and readonly completion, three invalid readonly bindings, and shared classifier identity. |
| Pre-`createRun` mutation and synthetic-launch RED | Exit 1; 3 failed. A readonly Task changed to write during capability discovery still reached the adapter, real readonly launch had no durable binding, and a synthetic queue timestamp was accepted as launch evidence. |
| Durable execution-binding GREEN | Exit 0; 3 passed. All adapters now gate immediately before `createRun`, real readonly launch binding remains internal, and synthetic readonly evidence fails closed. |
| Legacy finalizer/recovery fixture recalibration | Initial focused rerun: 6 failed / 4 passed because the old fixtures had no durable adapter-launch binding. After generating real queue, binding, TaskRun start, and adapter-run evidence: 10 passed; the extended stale/finalizer/generation/reentry set also passed 6 tests. |
| Complete artifact scope guard file | Exit 0; 19 passed. |
| Finalizer, background launch/baseline, and lock-recovery focused matrix | Exit 0; 21 passed. |
| Final fresh artifact/finalizer/background/recovery matrix | Exit 0; 33 passed, including the three new launch-gate cases and public-metrics projections. |
| Public metrics/privacy projection | Exit 0; 4 passed. The execution binding and attempt identifiers remain absent from public TaskRun metrics while forged internal values stay redacted. |
| Complete target-lock file | Exit 0; 36 passed. |
| Complete session-queue file | 5 passed / 1 failed because the existing equal-priority file-overlap fixture was UUID-order dependent; the failed node passed alone (1 passed). No immutable-mode code participates before that scheduler failure. |
| Readonly ScriptedMock enqueue RED/GREEN | RED exit 1: the readonly review was queued as `readonly`; GREEN exit 0: 1 passed after effective adapter capabilities classified it as `write`. |
| Real ScriptedMock write-scope integration | Exit 0; 1 passed. A readonly review selected the real mutating adapter, acquired the write lock, captured and bound its launch baseline, changed the demo file, persisted a passed scope decision, and kept the execution binding private. |
| Concrete capability launch-drift RED/GREEN | RED exit 1 with `createRun` called once for both mutable-to-readonly drift and same-instance mutation aliasing; GREEN exit 0 after two deep validated reads rejected drift before delegation. The symmetric readonly-to-mutable case is also covered. |
| Malformed concrete capability RED/GREEN | RED exit 1 with `createRun` called once when both reads returned the same post-assignment-invalid boolean fields. GREEN exit 0; 2 passed, covering malformed first/second reads and a valid first read followed by a malformed launch read, with no adapter run or internal execution binding. |
| Capability, readonly, queue, baseline, and lock focused matrix | Exit 0; 16 passed. The selected readonly queue node passed; two separate full-file queue nodes still stop earlier at the known scheduler file-overlap fixture and were not changed here. |
| Changed Python AST and import smoke | Exit 0; `task_runs.py` and `run_engine.py` parsed and imported successfully without repository bytecode. |
| `git diff --check` | Exit 0; only existing Windows LF-to-CRLF warnings. |

## TaskRun launch baseline 一次性执行绑定（OpenSpec 1.3）

**日期:** 2026-07-26

### 变更

- 针对 OpenSpec 1.3 的锁 generation 复核补齐五项原子性与恢复加固：acquire/release 的锁变更和事件在同一事务提交并返回不可变 generation receipt；终态 finalizer 可重放 queue 清理且不会误释后续 generation；过期锁恢复在写事务内复核匹配 TaskRun heartbeat；stale/terminal holder 的锁、TaskRun/Task、queue 与连续事件原子提交。`RunWorker` 的 legacy stale scan 保守排除所有当前 held target-lock holder，并在两类恢复之后才 reconcile queue，避免绕过 generation-aware 双 lease 恢复。私有 `TargetLock.id` 继续不进入 metrics、events、diagnostics、trace、adapter 输入或运行时 `repr`，无持久 scope decision 时保留 runtime context；外部 target scheduler 正向 fixture 同步登记并清理真实 `run_engine` 路径使用的 acquisition context。
- 过期 held-lock 恢复现在在同一 `BEGIN IMMEDIATE` 事务内复用 `collecting_diff` scope 分类：缺失或无法证明的 evidence 映射为 `TASK_RUN_SCOPE_UNVERIFIABLE`，持久化的可信拒绝映射为 `TASK_RUN_SCOPE_VIOLATION`，已有 pass marker 与普通 streaming run 仍映射为 `TASK_RUN_STALE`。已在事务内复核的 exact held write-lock generation 是不可变执行事实；若对应 `collecting_diff` run 的 Task 缺失，或 Task 后续被改判为 readonly，与该执行事实不一致，恢复同样 fail closed 为 `TASK_RUN_SCOPE_UNVERIFIABLE`，但普通 streaming/readonly legacy stale 路径不被扩大。需要 scope 失败事件时，锁释放、`task.scope_validation.failed`、`task.stale` 与 queue 事件按连续 sequence 原子落库，提交后才发布；任一 staging 失败会整体回滚并以同一 lock generation 重试，且恢复路径不创建 artifact。
- generation 隐私行为回归现在覆盖真实 `agent_run_request_for()` 生成的 `instruction`、`planContext` 与完整 `AgentRunRequest` 序列化，并通过既有 session event replay 与 `encode_sse_event()` 编码真实 `target_lock.acquired`、`target_lock.released`、`target_lock.stale_released` 事件。三类 SSE event 分别以完整 expected payload 字典锁定所有公开标识、归属、mode/state、nullable 字段及动态 lease/acquire/release 时间；既有 SSE envelope 保持不变，两次真实 generation token 及 generation 专用 key 均不进入 adapter 或 SSE lock payload，公开 SSE event `id` 合同保持不变。
- 写入型 TaskRun 在持有当前 Session/target lock 后、调用 `adapter.createRun` 前，先以 `metrics_json` CAS 认领一次性 `scopeExecutionAttemptId`，再捕获并持久化完整 launch baseline；认领同时绑定当前 state、runner、原 metrics，以及 lock 的 Session、TaskRun 和 worker/runner 归属。
- target lock 的过期 lease 不再被视为持有，同 holder 不能续租复活已过期 generation；从 released 重新获得 held lock 时会原子轮换 `TargetLock.id`，而当前同 holder 的连续 acquire 保留既有 id、`acquired_at` 与 lease。baseline 捕获前后、真实 `adapter.createRun` 前及 post-run 捕获前后均只复核私有的 `TargetLock.id` generation；该私有 id 不写入公开 metrics 或 scope events，既有公开 `acquiredAt` 诊断字段保持不变。
- `passed`/`rejected` scope decision 的最终持久化现在以原始 `metrics_json`、预期私有 lock id、target/Session/TaskRun/worker 归属、write/held 状态和当前 lease 执行单条原子 CAS；若最终校验后 lock generation 再变化，则持久化 `TASK_RUN_SCOPE_UNVERIFIABLE`、移除 pass guard，并复用同一 decision timestamp。
- 同一 TaskRun 的 adapter 重入或 active-run recovery 若发现已有 attempt/baseline，会以 `TASK_RUN_SCOPE_UNVERIFIABLE` fail closed；既有 baseline 不会被覆盖，第二个 adapter 不会启动。捕获或持久化异常同样在 adapter 启动前安全失败。
- post-run 校验继续复核相同 target lock 绑定，并通过真实 Git 分层回归覆盖 staged、unstaged、untracked、deleted 与 rename 新旧两端。
- P0 fallback 端到端 fixture 现在显式绑定 demo frontend target，证明 `ScriptedMockAdapter` 在新 scope gate 下仍能完成真实 Diff、健康 Preview 与 mock Deploy；Codex/Claude adapter 事件测试同步断言既有 OpenSpec 1.4 的非终态 `collecting_diff` 合同。
- 未新增 schema entity、adapter、依赖、WebSocket、网络权限或平台能力，也未启动下一项 OpenSpec 任务。

### TDD 与验证

| 命令 | 结果 |
|---|---|
| RunWorker held-owner legacy bypass 两类 lease 边界（RED/GREEN） | RED 退出码 1；2 failed，分别证明 heartbeat 在 atomic scan 后跨界、以及 lock lease 当前但 TaskRun lease 已过期时会被 legacy path 错误终态化。GREEN 退出码 0；新增参数化节点与既有 worker ordering/普通 stale caller 合计 4 passed，direct `mark_stale_task_runs` 相邻集合 14 passed / 1 个已知节点 deselected。 |
| baseline 重入与 active-run recovery 两个新增回归（RED） | 预期分别失败为 `DID NOT RAISE TaskRunScopeError` 与 `capture_calls == 2`，证明旧实现会覆盖 launch baseline 并再次启动执行路径。 |
| lock generation 与最终持久化竞态 8 个 finding 回归（RED） | 退出码 1；7 failed / 1 passed。旧实现会接受初始过期/equal lease、固定时钟下释放重获复用 id、连续 acquire 改写 lease、旧 baseline 继续授权 adapter，并在最终校验后 generation 变化时仍持久化 `passed`/`rejected`；仅既有的 expired-held 拒绝节点通过。 |
| 私有 generation/lease 6 个节点与最终 persistence CAS 2 个参数化节点（GREEN） | 退出码 0；分别为 6 passed 与 2 passed。 |
| 新增 generation/race 回归与既有 decision 合同，以及原始两个 finding 节点 | 退出码 0；分别为 16 passed 与 2 passed。私有 lock id 未进入 metrics/events。 |
| 过期 same-holder lease 与 same-owner lock generation 变化两个 finding 回归 | 退出码 0；2 passed。过期 lease 未进入 baseline capture/adapter，baseline capture 内释放并重获同 owner lock 也未启动 adapter。 |
| baseline/lock、自动启动、重入、active-run recovery、capture failure、queued shared-worktree 与 finalizer 持锁 13 个显式节点 | 退出码 0；14 passed。 |
| 相邻 lock/runtime/public/decision/1.3 回归（剔除已知 recovery scheduler 节点）与 scope finalizer/crash-recovery 集合 | 退出码 0；按参数化实例计数分别为 48 passed 与 19 passed。 |
| 相邻集合包含已知 recovery scheduler 节点 | 44 passed / 1 failed；唯一失败在 lock setup 前即以既有 `Blocked by file overlap conflict` 结束，单独运行该节点结果相同，未纳入本 finding。 |
| 完整 `test_target_locks.py` 加 runtime-context 与公开 scope evidence 脱敏节点 | 退出码 0；20 passed。 |
| 1.3 锁归属、启动顺序、重入、恢复、capture failure、queued shared-worktree、真实 Git 分层及 P0 fallback 9 个节点（仓库外短 basetemp/runtime SQLite） | 退出码 0；9 passed。 |
| `test_claude_code_adapter.py`、`test_codex_adapter.py`、`test_failure_recovery.py` | 退出码 0；30 passed。 |
| backend 全套，不排除节点（仓库外短 basetemp/runtime SQLite） | 917 passed / 1 skipped / 7 failed；失败仅为未修改主分支可复现的 3 个 Windows/POSIX 假设节点，以及同时间戳下随机 UUID 次排序导致的 4 个 scheduler/queue 冲突节点。 |
| backend 全套，仅剔除上述已确认节点和同根因 context-pack 排序节点 | 退出码 0；915 passed / 1 skipped / 9 deselected。 |
| held-lock `collecting_diff` scope recovery finding（RED/GREEN） | 初始 RED 退出码 1；3 failed / 2 passed，证明 missing/rejected evidence 被错误降为 `TASK_RUN_STALE` 且 scope-event staging failure 未触发。首轮实现为 4 passed / 1 failed，唯一失败是旧测试把新增四事件序列硬编码为三项；修正为按实际事件数检查后，最终五实例退出码 0；5 passed。 |
| generation 隐私行为覆盖 | 真实 `AgentRunRequest` 与真实 acquired/released/stale-released SSE replay/encode 节点首次运行分别退出码 0；1 passed 与 1 passed，确认 production 已满足隐私合同、缺口仅为行为回归。连同四类 recovery 与三类 rollback 注入的最终 review 集合退出码 0；9 passed。 |
| target-lock、collecting-diff 与 RunWorker 扩展回归 | 完整 `test_target_locks.py` 退出码 0；36 passed。collecting-diff recovery 相邻集合退出码 0；13 passed / 154 deselected。RunWorker 相邻集合退出码 0；6 passed / 161 deselected。 |
| adapter、SSE、diagnostics 与 recovery/fallback 回归 | `test_events.py`、`test_chat_events.py`、`test_run_diagnostics.py`、`test_adapters.py`、Codex/Claude adapter 六文件退出码 0；60 passed。`test_recovery.py` 与 `test_failure_recovery.py` 退出码 0；5 passed。 |
| 最终静态与规范门禁 | 29 个 changed/new Python 文件 AST 解析、3 个本次触及文件的定向 `py_compile`（cache 重定向到系统 TEMP）及 `events`/`run_engine`/`target_locks` import 均退出码 0；两项 public generation-key `rg` 搜索无匹配；OpenSpec strict 与 `git diff --check` 退出码 0，后者仅有既有 LF→CRLF 提示。 |
| held write-lock 与 Task binding 复审（RED/GREEN） | missing Task 与后续 reclassified-readonly 两实例的 RED 退出码 1；2 failed，均实际得到 `TASK_RUN_STALE`。以事务内 exact held write generation 窄化修复后退出码 0；2 passed；包含原 missing/rejected/passed/streaming 语义的完整 matrix 退出码 0；6 passed。 |
| SSE lifecycle 完整公开 payload 复审 | acquired/released/stale-released 继续使用真实 producer、session replay 与 encoder；改为三份完整 expected payload 字典后的首次运行退出码 0；1 passed，未修改 production SSE 行为。 |
| 两项 P2 最终回归 | 两个新增 binding 节点加完整 SSE 节点退出码 0；3 passed。原四类 recovery、三类 rollback injection、真实 adapter request 与 SSE 的九实例集合退出码 0；9 passed。完整 `test_target_locks.py` 退出码 0；36 passed。扩展 collecting-diff recovery/scope 相邻集合退出码 0；15 passed / 154 deselected。 |

## Scope finalizer 持久化决策权威性与 v2 fixture 校准（OpenSpec 1.4）

**日期:** 2026-07-24

### 变更

- 写入型 TaskRun finalizer 现在固定执行 `validate -> persist -> require durable pass`。若 persistence revalidation 将过期的 transient `rejected` 降级为 `unverifiable`，失败事件、TaskRun 终态错误码、queue/target-lock 释放与 artifact 阻断均以持久化证据为准，不再复用 transient 分类。
- 新增真实 persistence/require 集成回归，覆盖 stale rejection、durable unverifiable、无 Diff/Review/Preview/Deployment、单一安全失败事件和终态清理。
- 将 `test_task_runs.py` 中代表有效 snapshot v2 的正向 fixture 从旧 porcelain 状态 `" M"` 迁移为 canonical `tracked-present`；missing-control-digest 用例也只保留 digest 缺失这一失效条件，避免因无关的旧状态字段假通过。
- OpenSpec design 明确 `taskRunScopeDecision` 持久化所有结果、`taskRunScopeGuard` 仅作为 pass-only authorization marker。未修改 schema entity、adapter、SSE、依赖或 OpenSpec 1.3 状态；1.3 仍未开始。

### 验证

| 命令 | 结果 |
|---|---|
| scope、registry、artifact guard、diagnostics 与 finalizer/recovery/lock 显式节点（仓库外 fresh basetemp/runtime SQLite） | 退出码 0；270 passed / 1 skipped。 |
| `python -B -m pytest tests/test_task_runs.py -k "not test_context_pack_includes_recent_messages_ledger_and_excludes_other_sessions" ...`（仓库外已初始化 SQLite） | 退出码 0；144 passed / 1 deselected。 |
| 消息排序既有节点独立重复 8 次 | 5 passed / 3 failed；`context_pack.py` 与该节点语义不在本次 finalizer diff 中。相同 `created_at` 下随机 UUID 次排序无法表达插入先后，作为独立后续项保留。 |
| `openspec validate agenthub-taskrun-scope-preview-hardening --strict` | 退出码 0；`Change 'agenthub-taskrun-scope-preview-hardening' is valid`。 |

## Effective write-scope DEL 控制字符一致性修复（OpenSpec 1.1）

**日期:** 2026-07-23

### 变更

- 修复 canonical policy pattern 与 repository-path validator 的控制字符边界不一致：前者原先只拒绝 C0（`U+0000`–`U+001F`），会接受 `U+007F` DEL，导致 allowed/denied policy identity 与共享 `TargetProject` 授权 API 把含 DEL 的 pattern 当作有效。
- `canonical_write_scope_pattern()` 现在对 DEL 与 C0 一致 fail closed；既有 normalization、`*`/单个尾缀 wildcard 和可打印 Unicode 正向语义保持不变。
- 本次没有 schema、OpenSpec scope、adapter 或功能扩展；OpenSpec 1.3 保持未开始。

### TDD 与验证

| 命令 | 结果 |
|---|---|
| `python -B -m pytest tests/test_target_registry.py -k "del" -p no:cacheprovider -q --basetemp <fresh-system-temp>`（RED） | 退出码 1；5 failed / 52 deselected。直接 validator、effective identity 的 allowed/denied 两侧，以及共享 API 的 allowed/denied fail-closed 合同均证明旧实现接受 DEL。 |
| 同一 DEL focused 集合（GREEN） | 退出码 0；5 passed / 52 deselected。 |
| `python -B -m pytest tests/test_target_registry.py -p no:cacheprovider -q --basetemp <fresh-system-temp>` | 退出码 0；57 passed；4 条既有 `datetime.utcnow()` 弃用警告。 |
| `python -B -m pytest tests/test_task_run_scope.py -k "noncanonical_repository_paths or canonical_unicode_repository_path or capture_fails_closed_for_noncanonical_regular_path" -p no:cacheprovider -q --basetemp <fresh-system-temp>` | 退出码 0；7 passed / 151 deselected。 |
| 定向 `py_compile` 与 AST | 退出码 0；`target_registry.py` 及其测试均编译、解析成功，编译缓存定向系统 TEMP。 |

## TaskRun worktree 快照与 protected control footprint（OpenSpec 1.2）

**日期:** 2026-07-21（2026-07-23 复核）

### 变更

- 完整、无内容的 worktree snapshot 现在对普通 entry metadata 复用 target registry 的 canonical repository-path 校验；控制字符、首尾空白、通配符、反斜杠、绝对路径和 drive/UNC 形式均 fail closed，而合法可打印 Unicode 相对路径继续接受。
- `.env*` protected policy 现在包含 `.envrc`。该路径不会出现在普通 snapshot entries；其变更只通过安全类别、聚合计数和内部 opaque control digest 参与 protected scope violation。
- 常规文件全量扫描遇到既不是符号链接、常规文件也不是目录的目录项时会使 snapshot unavailable，不再静默忽略未知文件系统对象。
- 普通（非 protected）worktree 常规文件在任何内容读取前必须由 descriptor 证明 `st_nlink == 1`，并在每次读取前后复核；已有或 open 后新增的 hardlink alias 会使 capture 安全返回 unavailable，且不会持久化 link count 或泄露外部 alias 路径。该单-link ownership 规则不适用于 `.git` pointer/resolved-gitdir 的 protected 摘要读取。
- Windows snapshot collector 现在通过惰性加载的 Win32 `FindFirstStreamW`/`FindNextStreamW` 枚举普通与 protected 文件/目录的数据流，仅接受 canonical `::$DATA`。任何 named ADS、非 `ERROR_HANDLE_EOF` 的 API 错误、API/文件系统不可证明、枚举异常或 `FindClose` 失败都会使 capture 使用固定 `scope_capture_unavailable` reason、空 entries 和空 protected control digest 安全失败；stream 名、数量、路径与内容均不进入 fingerprint、digest、metadata、event、diagnostic 或 error。
- Win32 stream helper 把 initial `False`/整数 `0` handle 视为无效证据，并在调用任何 `FindNextStreamW`/`FindClose` 前直接 fail closed；opaque fake handle 与真实非零 Win32 handle 语义保持不变，异常不回显路径或 stream 名。
- Win32 stream helper 的 next 成功分支现在同样要求原生 `str` stream name；`str` 子类即使值等于 `::$DATA` 也会在正常 `FindClose` 后 fail closed，避免非结构化对象绕过 stream-name contract。
- ADS 检查接入统一的稳定文件读取和目录扫描边界：普通文件、`.git` pointer、protected 文件与 resolved-gitdir 文件在 open/read 的 initial、每次 read 前后及 final 复核，assigned root、普通空目录、`.git` directory、protected subtree 与 resolved gitdir 在 `scandir` 前后复核。symlink 与任何 reparse point 不调用 stream API，protected symlink 继续只保留 stable readlink evidence；非 Windows 行为不变。
- 当 post-run `.git` 被替换为符号链接时，collector 仅在已有可信 `trusted_git_dir` 的情况下接受：它记录符号链接本身为 protected control record，使用可信 gitdir 进行扫描，并保持 lexical `.git` exclusion，因此不会解析或跟随不可信目标。没有可信基线时保持 unavailable。控制摘要继续使用既有 keyed、domain-separated record stream，且不会持久化路径、fingerprint、key 或内容。
- 审计补充：`.git` 的类型判断现在先使用 `lstat`，不会对 post-run 符号链接调用 follow-stat；可信 gitdir 不再 `resolve()`，而是要求 lexical absolute、非符号链接/非 reparse 的末级目录。无法证明可信目录时 collector 会在运行 Git 前 fail closed。Git plumbing 仅通过固定 absolute executable 执行 `ls-files --stage -z --` 与 `ls-tree -r -z --full-tree HEAD`；两者共同使用 `--no-optional-locks`、`--no-replace-objects`、`-c core.fsmonitor=false`、显式 trusted `--git-dir`/`--work-tree`、`DEVNULL` stdin 和固定 timeout。
- 普通 worktree 扫描在加入或递归任意非保护路径前也执行 canonical repository-path 校验，因此真实磁盘上的非规范名称会使公开 capture unavailable；`.env*` 等保护路径继续由 protected collector 处理。
- 所有待遍历的普通和 protected tree entry 现在都通过统一的 `lstat` 或 `DirEntry.stat(follow_symlinks=False)` 分类。普通 symlink 与任何 non-symlink reparse point（包括 Windows directory junction）都在读取或递归前 fail closed，不能把外部内容纳入 snapshot 或 protected digest。capture 入口建立的 immutable volume-root→assigned-root observations 会贯穿普通枚举、fingerprint、Git cwd 与 absent/directory early return；内部 helper 不会重新把当前 assigned root 当成可信起点。
- protected walker 对 symlink 只稳定读取 link text 而不跟随 target；常规文件通过 no-follow `open`、`fstat`、descriptor identity 与完整 ancestor observations 读取，目录通过带完整 observations 的稳定 `scandir` 递归。`.git` directory 保持 lexical、不会调用 `resolve()`，resolved gitdir 也在每次读取和枚举前后复核 ancestor identity；无法证明稳定性时统一 fail closed。
- protected category、excluded gitdir、Git metadata 过滤与绝对路径 containment 现在绑定 assigned root 的实际逐目录大小写语义，而不是进程级 Windows/POSIX 猜测；路径等价只接受 exact 或父目录已证明 insensitive 后的 ASCII-only fold。`ßroot`/`ssroot` 等 Python Unicode casefold 相等不再是 containment、child resolution 或 excluded-root 证据；Unicode fold 命中 ASCII protected 名而 ASCII fold 不命中时，live capture 按歧义 fail closed，rootless v2 继续保守拒绝。
- 绝对路径转 repository-relative path 现在只能发生在 root observations 与逐父目录 case semantics 已证明 containment 之后，再通过 path parts 切片投影；裸 `Path.relative_to()` 成功不再被当作授权判断，投影前后都会复核 assigned-root observations。
- 默认 case resolver 不缓存目录判定；每次只翻转一个可逆 ASCII 字符，按 observation-before → children rescan → observation-after 的顺序复核，并在线性批量中覆盖每个 ASCII-fold collision group 的全部 spelling。非 ASCII case mapping 不作为 witness；任意两个 listed spelling 指向同一 identity、任一观察变化、无 witness 或 resolver 不可用时统一返回 `unknown` 并使 capture fail closed。普通 exact-name entry 与空目录不需要 case probe，保持原有行为。
- Git executable 现在携带从 volume root 经全部父目录到 executable leaf 的完整 no-follow observation chain，以及通过允许既有 hardlink、拒绝 ADS、持续复核 ancestor 的 descriptor reader 得到的瞬态 SHA-256 内容绑定；这是对 Git for Windows 正常 `git.exe` 多命令硬链接安装的兼容窄化。runner 前、runner 的 `finally` 路径和 trusted-gitdir post-check 后均复核，任何缺失、identity 变化，或经任一 hardlink alias 发生的同 inode 内容变化都使 capture unavailable。hash 只存在于内部 `_TrustedGitExecutable`，不持久化、不公开；普通 non-protected worktree 文件的单链接规则保持不变。
- Windows 的 `.exe` path stat 会按 suffix 合成 `0111`，而 descriptor fstat 不会。`_stable_regular_file_read(..., allow_windows_path_execute_bits=True)` 仅由 trusted executable fingerprint 两处调用，并把实际 path 传入比较器；`_descriptor_matches_path_observation` 仅在 Windows、该 seam 已启用、suffix 经 ASCII-only fold 恰为 `.exe`，且 `path_mode == descriptor_mode | 0o111` 时接受差异。partial、反向及非 `.exe` 差异全部拒绝，dev、ino、file type 与 file attributes 仍严格相等；普通/protected 文件继续使用默认 `False` 的严格 identity 比较。
- 上述 case/executable 防护仍是围绕独立进程启动的 path-based observation，不是原子文件系统事务；它们能发现检查边界上可见的变化，但无法彻底消除完全发生在两次检查之间的极窄 swap-and-restore TOCTOU 窗口，也不能识别首次绑定前已经被篡改的系统 Git。OpenSpec 1.2 不扩展 ACL、安装来源或宽泛可信工具策略，也不声称提供这些保证。
- snapshot v2 未扩展 schema、也不持久化 per-directory case binding。rootless metadata 因而保守拒绝 `.GIT`、`.Env.Local`、`NODE_MODULES`、`SECRETS` 等 protected ASCII-style aliases 及 `ſecrets` 等 Unicode-fold protected 歧义；即使 live capture 位于 case-sensitive directory，也不能跨进程推断这些 aliases 安全。newly-protected gitdir deletion 的私有过滤同样保守按 ASCII case alias 隐去路径；该分支已有 protected-control digest delta，故不会把 violation 变成 pass。

### TDD 与验证

| 命令 | 结果 |
|---|---|
| `python -B -m pytest tests/test_task_run_scope.py -k "envrc or noncanonical_repository_paths or canonical_unicode_repository_path or unsupported_directory_entry or trusted_gitdir_handles_git_symlink or git_symlink_without_trusted_baseline" -p no:cacheprovider -q --basetemp <safe-temp>`（RED） | 退出码 1；8 failed / 2 passed。失败准确覆盖 `.envrc`、5 类非规范路径、未知目录项和可信 `.git` 符号链接分支。 |
| 同一新增回归集合（GREEN） | 退出码 0；10 passed / 30 deselected。 |
| `python -B -m pytest tests/test_task_run_scope.py -p no:cacheprovider -q --basetemp <safe-temp>` | 退出码 0；50 passed。 |
| `python -B -m pytest tests/test_target_registry.py -p no:cacheprovider -q --basetemp <safe-temp>` | 退出码 0；51 passed；4 条既有 `datetime.utcnow()` 弃用警告。 |
| `python -B -m pytest tests/test_artifact_scope_guards.py tests/test_run_diagnostics.py <11 个 scope lifecycle 节点> -p no:cacheprovider -q --basetemp <safe-temp>` | 退出码 0；48 passed；881 条既有 `datetime.utcnow()` 弃用警告。 |
| `python -B -m pytest tests/test_task_run_scope.py -k "trusted_gitdir_handles_git_symlink or replaced_trusted_gitdir or capture_fails_closed_for_noncanonical_regular_path or unsupported_directory_entry" -p no:cacheprovider -q --basetemp <safe-temp>`（审计 RED） | 退出码 1；3 failed / 1 passed。失败证明 `.git` follow-stat、trusted gitdir 重定向后仍运行 Git plumbing、以及公开 capture 接受非规范真实路径；未知目录项公共 capture 已由首轮修复覆盖。 |
| 同一审计节点（GREEN） | 退出码 0；4 passed / 38 deselected；其中 runner 参数测试锁定 `--no-optional-locks`、可信 `--git-dir` 和 `--work-tree`。 |
| `python -B -m pytest tests/test_task_run_scope.py tests/test_target_registry.py tests/test_artifact_scope_guards.py tests/test_run_diagnostics.py <11 个 scope lifecycle 节点> -p no:cacheprovider -q --basetemp <safe-temp>` | 退出码 0；148 passed；885 条既有 `datetime.utcnow()` 弃用警告。 |
| Windows junction、reparse 与大小写 protected-policy RED | 退出码 1；7 failed / 1 passed。两个 `mklink /J` fixture 成功创建并证明普通/`secrets` walker 会跟随 junction；四个 case-variant collector fixture 与 permissive target deny 均失败。修正 root 内 precise reparse fake 后，单节点 RED 退出码 1；1 failed，证明旧 walker 未调用 `DirEntry.stat(follow_symlinks=False)`。 |
| Windows junction、reparse、大小写 protected-policy 及普通 symlink 正向（GREEN） | 退出码 0；9 passed / 91 deselected。 |
| Windows case-variant pointer transition（RED） | 退出码 1；1 failed。current 已排除 `PRIVATE-GITDIR-B/HEAD`，但大小写敏感的删除过滤仍把它作为普通 rejected path 暴露。 |
| 同一 pointer transition（GREEN） | 退出码 0；1 passed。删除过滤使用保守的 case-alias descendant 隐私匹配，decision 只报告 `<protected-footprint>`，安全 metadata/reason 不含 gitdir 路径。 |
| scope、registry、artifact guard、diagnostics 与 11 个 scope lifecycle 节点最终重跑 | 退出码 0；148 passed；885 条既有 `datetime.utcnow()` 弃用警告。 |
| assigned-root swap-back、ordinary early return、protected file/tree、`.git` directory 与 Windows reparse 7 个 root-binding 参数（RED） | 退出码 1；7 failed。失败证明普通外部 descriptor 被读取、早退接受已替换 root，以及 protected walker 跟随外部内容。 |
| 同一 root-binding/protected no-follow 回归（GREEN） | 退出码 0；7 passed。外部内容读取计数均为 0，所有不可证明 capture 均安全 unavailable。 |
| assigned-root 上层祖先 swap-back ordinary-file 单节点 | 退出码 0；1 passed。外部 descriptor 读取计数为 0，capture 安全 unavailable 且不公开外部绝对路径。 |
| hardlink alias focused regression（GREEN） | 退出码 0；2 passed。覆盖已有 alias 与 open 后首次读取前新增 alias。 |
| `python -B -m pytest tests/test_task_run_scope.py -p no:cacheprovider -q --basetemp <safe-temp>` | 退出码 0；90 passed。 |
| stale v1 scope snapshot fixture migration；`python -B -m pytest tests/test_task_run_scope.py tests/test_target_registry.py tests/test_artifact_scope_guards.py tests/test_run_diagnostics.py -p no:cacheprovider -q --basetemp <safe-temp>` | 退出码 0；176 passed。仅将 schema-valid rejected-marker fixture 的 entry status 从 v1 porcelain `" M"` 迁移为 v2 canonical `tracked-present`，未修改生产代码或测试断言。 |
| Windows NTFS ADS focused 首轮（RED） | 退出码 1；16 failed / 1 passed / 90 deselected。8 个真实 NTFS 节点成功创建 named ADS，证明普通文件、assigned root、普通空目录、`.env.local`、`.git` pointer/directory 与 resolved-gitdir `HEAD`/directory 均被旧 snapshot 错误接受；8 个 helper 节点证明结构化 Win32 stream API 边界尚不存在。16 个失败节点随后逐个使用全新系统 TEMP/basetemp 重跑，均为退出码 1。 |
| malformed first-result helper 单节点（补充 RED） | 退出码 1；1 failed。`False` 可冒充首个成功结果的错误码 0，证明 first tuple 需要与 next tuple 相同的严格字段类型校验。 |
| Windows NTFS ADS focused 最终（GREEN） | 退出码 0；18 passed / 90 deselected。覆盖真实 ADS、仅 `::$DATA`、initial/next `ERROR_HANDLE_EOF=38`、initial/next unexpected error、initial/next named stream、`FindClose` false/异常、malformed first result，以及 symlink/reparse 零 stream-enumeration。 |
| `python -B -m pytest tests/test_task_run_scope.py -p no:cacheprovider -q --basetemp <safe-temp>`（ADS 最终） | 退出码 0；108 passed。 |
| `python -B -m pytest tests/test_task_run_scope.py tests/test_target_registry.py tests/test_artifact_scope_guards.py tests/test_run_diagnostics.py -p no:cacheprovider -q --basetemp <safe-temp>`（ADS 最终） | 退出码 0；194 passed；457 条既有 `datetime.utcnow()` 弃用警告。 |
| `python -B -m py_compile apps/api/app/task_run_scope.py apps/api/tests/test_task_run_scope.py`（`PYTHONPYCACHEPREFIX` 定向系统 TEMP） | 退出码 0；2 个 `.pyc` 均写入系统 TEMP，worktree 未生成 compile cache。 |
| `openspec validate agenthub-taskrun-scope-preview-hardening --strict`（ADS 最终） | 退出码 0；`Change 'agenthub-taskrun-scope-preview-hardening' is valid`。 |
| `git diff --check`（ADS 最终） | 退出码 0；仅有既有 Windows LF→CRLF 提示，无 whitespace error。 |
| invalid initial stream handle 参数化节点（复核 RED） | 退出码 1；2 failed。`False` 与整数 `0` 均未被拒绝，且旧 helper 会继续调用 next/close。 |
| 同一 invalid-handle 节点（GREEN） | 退出码 0；2 passed。两类无效 handle 均在任何 next/close 前被拒绝，异常不含 path 或 `::$DATA`。 |
| Windows NTFS ADS focused 复核（GREEN） | 退出码 0；20 passed / 90 deselected。 |
| `python -B -m pytest tests/test_task_run_scope.py -p no:cacheprovider -q --basetemp <safe-temp>`（invalid-handle 最终） | 退出码 0；110 passed。 |
| next stream-name `str` 子类节点（复核 RED） | 退出码 1；1 failed。旧实现按值比较接受 `str` 子类并错误完成枚举。 |
| 同一 next stream-name 节点（GREEN） | 退出码 0；1 passed；第一次 next 后正常 `FindClose`，异常不泄露 path/stream。 |
| Windows NTFS ADS focused 最终复核（GREEN） | 退出码 0；21 passed / 90 deselected。 |
| `python -B -m pytest tests/test_task_run_scope.py -p no:cacheprovider -q --basetemp <safe-temp>`（next-name 最终） | 退出码 0；111 passed。 |
| 逐目录 case-semantics 补充节点（RED） | 退出码 1；3 failed / 5 passed / 115 deselected。失败分别证明 trusted gitdir 与 pointer 的 absolute root case alias 在 sensitive parent 下被错误重解释，以及 newly-protected deletion 泄露不同大小写的 gitdir entry；4 个 rootless alias 参数与 Git executable guard 正向保持通过。 |
| 同一补充节点（GREEN） | 退出码 0；8 passed / 115 deselected。absolute prefix 在每个大小写差异组件的父目录上判定，private transition 只报告 `<protected-footprint>`。 |
| Git executable 与 rootless v2 alias 判别性旧实现复核（RED） | 临时恢复旧 exact containment/exact protected 分类后退出码 1；5 failed / 118 deselected。Git executable 节点在 containment guard 前触发禁止的 `_path_kind` traversal；`.GIT`、`.Env.Local`、`NODE_MODULES`、`SECRETS` 四个 metadata 参数均被错误接受为 complete。修复态同一集合退出码 0；5 passed / 118 deselected。 |
| pointer / trusted-gitdir / Git-executable 相关回归 | 退出码 0；21 passed / 102 deselected。 |
| `python -B -m pytest tests/test_task_run_scope.py tests/test_target_registry.py -p no:cacheprovider -q --basetemp <safe-temp>`（case-semantics 复核） | 退出码 0；174 passed / 1 skipped；4 条既有 `datetime.utcnow()` 弃用警告。 |
| `python -B -m pytest tests/test_task_run_scope.py tests/test_target_registry.py tests/test_artifact_scope_guards.py tests/test_run_diagnostics.py -p no:cacheprovider -q --basetemp <safe-temp>`（case-semantics 复核） | 退出码 0；209 passed / 1 skipped；457 条既有 `datetime.utcnow()` 弃用警告。 |
| containment-before-relative-projection 3 节点（RED/GREEN） | RED 退出码 1；3 failed / 134 deselected。GREEN 退出码 0；3 passed。 |
| stateless single-ASCII case witness 4 节点（RED/GREEN） | RED 退出码 1；4 failed / 133 deselected。GREEN 退出码 0；4 passed；覆盖双 spelling 同 inode、rename race、旧 witness 复核与非 ASCII witness 拒绝。 |
| Git executable 完整 observation chain 4 节点（RED/GREEN） | RED 退出码 1；4 failed / 133 deselected。GREEN 退出码 0；4 passed；覆盖 executable/parent replacement 及 runner 前拒绝。 |
| no-write、exact/empty 与 mixed-parent case 正向 | 退出码 0；3 passed。 |
| containment、case witness 与 executable 三组综合 | 退出码 0；14 passed / 123 deselected。 |
| pointer / trusted-gitdir / Git-executable 回归 | 退出码 0；25 passed / 112 deselected。 |
| scope collector 与 target registry | 退出码 0；188 passed / 1 skipped；4 条既有 `datetime.utcnow()` 弃用警告。 |
| scope、registry、artifact guard 与 diagnostics 四文件 | 退出码 0；223 passed / 1 skipped；457 条既有 `datetime.utcnow()` 弃用警告。 |
| Unicode casefold containment/external identity 初始 RED | 退出码 1；2 failed。真实 NTFS `ßroot`/`ssroot` 证明 containment 错返 true，trusted gitdir 被错误重绑到 internal tail。 |
| Unicode/ASCII-only 扩展 RED | 退出码 1；5 failed / 2 passed / 137 deselected。新增 child resolution 与 live protected ambiguity 同样失败；rootless conservative 两参数保持正向。 |
| Unicode/ASCII-only focused GREEN | 退出码 0；15 passed / 129 deselected；覆盖 7 个新参数实例及既有 ASCII alias、逐父目录 containment 与 protected 正向。 |
| witness final-scan 与三 spelling collision（RED） | 退出码 1；2 failed。最终 rescan 内同名换 identity 仍误返 insensitive；三 spelling group 只检查前两项而误返 sensitive。 |
| 全部 default case-probe GREEN | 退出码 0；7 passed / 139 deselected。 |
| Git executable 同 inode 内容篡改（RED） | 退出码 1；1 failed。runner 内原地覆写且 filesystem identity 不变，旧 snapshot 仍为 available。 |
| executable content binding 首轮实现检查 | 退出码 1；1 failed。snapshot 已 fail closed 但 runner 未启动；trace 证明 Windows `.exe` path-stat `0777` 与 fstat `0666` 的合成 execute-bit 差异需要窄化处理。 |
| executable content binding 最终 GREEN | 退出码 0；1 passed。runner 内同 inode 内容变化在 `finally` 复核被拒绝。 |
| executable 相关 focused 回归 | 退出码 0；9 passed / 138 deselected。 |
| 既有 containment、case witness 与 executable 组合 | 退出码 0；14 passed。 |
| multi-link executable 兼容与 alias 篡改 RED | 退出码 1；2 failed。稳定多链接 executable 在 runner 前被错误拒绝，alias 篡改节点也因 runner 未启动而失败。 |
| 同一 multi-link executable 两节点 GREEN | 退出码 0；2 passed。稳定 executable 可用，经另一 hardlink alias 原地改写会在 `finally` 内容复核中 fail closed。 |
| 真实 Git for Windows 诊断 | `_GIT_EXECUTABLE` 的 lstat/fstat 均为 `st_nlink=2`，且 hardlink 列表包含 `git.exe` 与 `git-lfs.exe`；ADS、dev/ino/type/attributes 正常，仅存在已窄化的 `.exe` path-stat/fstat `0111` 差异。 |
| `python -B -m pytest tests/test_task_run_scope.py -p no:cacheprovider -q --basetemp <fresh-system-temp>` | 退出码 0；148 passed / 1 skipped。 |
| scope、registry、artifact guard 与 diagnostics 四文件最终复跑 | 退出码 0；235 passed / 1 skipped；457 条 warning 均为既有 `datetime.utcnow()` deprecation。 |
| 定向 `py_compile` 与 changed source/test AST | 退出码 0；2 个核心文件编译缓存写入 fresh system TEMP，18 个 changed source/test Python 文件全部解析成功。 |
| `openspec validate agenthub-taskrun-scope-preview-hardening --strict` | 退出码 0；`Change 'agenthub-taskrun-scope-preview-hardening' is valid`。 |
| `git diff --check` 与 7 个 untracked source/test/OpenSpec 文件行尾空白检查 | 退出码 0；仅有既有 Windows LF→CRLF 提示，无 whitespace error；OpenSpec 1.2 保持 `[x]`，1.3 保持 `[ ]`。 |
| executable mode path 接线 RED | 退出码 1；9 failed。新增 5 个 mode/suffix 与 4 个 identity 直接 helper 参数首先证明旧 helper 不接收实际 path。 |
| executable mode 行为性 RED | 退出码 1；4 failed / 5 passed。旧逻辑错误接受两种 partial execute delta、反向 delta 及非 `.exe` 完整 delta；完整 `.ExE` 正向与 dev/ino/type/attributes 严格性保持正向。 |
| 同一 9 参数 GREEN | 退出码 0；9 passed。只接受 Windows trusted-executable seam 上 ASCII 大小写不敏感的 `.exe` 完整正向 `0111` 合成。 |
| executable 相关 focused | 退出码 0；20 passed / 138 deselected。 |
| `python -B -m pytest tests/test_task_run_scope.py -p no:cacheprovider -q --basetemp <fresh-system-temp>`（mode 精确窄化） | 退出码 0；157 passed / 1 skipped。 |
| mode 精确窄化静态与规范门禁 | 2 个 task Python 文件 `py_compile`/AST 退出码 0，编译缓存写入 fresh system TEMP；OpenSpec strict 与 `git diff --check` 退出码 0，后者仅有既有 LF→CRLF 提示；1.2 保持 `[x]`，1.3 保持 `[ ]`。 |

## TaskRun 有效写范围策略与错误映射（OpenSpec 1.1）

**日期:** 2026-07-18

### 变更

- 写入型 TaskRun 的 launch baseline 现在绑定当前 Task、Session、Workspace 与 registry-resolved target，并使用版本化的 canonical policy identity 固定 target ID、排序去重后的 allowed paths，以及包含全局 protected policy 的有效 denied paths。identity 不包含 target root 或 raw host path。
- post-run validation、decision persistence、durable pass marker、crash recovery 与 require-pass artifact guard 现在共同校验 TaskRun、baseline、execution attempt、Workspace、target 与 policy identity；同 target ID 的 policy mutation、跨 Workspace replay、字段缺失/畸形/伪造和旧 marker schema 均 fail closed 为 `TASK_RUN_SCOPE_UNVERIFIABLE`。
- 可信、规范解析的越界路径、rename 任一越界端点和 protected control delta 保持映射为 `TASK_RUN_SCOPE_VIOLATION`；无法绑定范围、缺失或不可信 evidence 不再被持久化为 violation。
- `TargetProject.denies_path()` 始终合并 `.git`、`.env*`、`secrets` 与 `node_modules` 全局 policy，确保 deny 优先且 protected path 不能被 allowed wildcard 绕过。
- validation evidence schema 升级为 v2。Workspace/policy binding 仅保存在 internal checkpoint/runtime/decision/guard；默认 TaskRun metrics 与 TaskRunEvent 不公开这些字段。
- 更新两个 artifact scope guard 的有效证据 fixture：一个代表可信 rejected decision，另一个代表可信 passed marker；故意覆盖 legacy、missing 或 malformed marker 的 fixture 保持缺失并继续 fail closed。
- OpenSpec design 新增 effective write-scope policy 与 fail-closed error matrix；没有改动 snapshot collector、lock/launch timing、schema entity、adapter、SSE 或 artifact production 行为。

### TDD 与验证

| 命令 | 结果 |
|---|---|
| `python -B -m pytest apps/api/tests/test_task_runs.py::test_validate_scope_is_unverifiable_when_same_target_policy_changes -p no:cacheprovider -q`（RED） | 退出码 1；1 failed。baseline 后同 target ID policy 放宽时，实际错误返回 `passed` |
| 同一 policy-mutation 节点（GREEN） | 退出码 0；1 passed |
| `python -B -m pytest apps/api/tests/test_task_runs.py::test_require_scope_passed_rejects_same_target_policy_mutation -p no:cacheprovider -q`（RED） | 退出码 1；1 failed。旧 pass marker 在 policy 变化后没有拒绝 |
| policy validation、正常 pass marker 与 marker mutation 3 个节点（GREEN） | 退出码 0；3 passed |
| baseline/decision/guard public metrics redaction 2 个节点（RED/GREEN） | RED 退出码 1，2 failed；GREEN 退出码 0，2 passed |
| `python -B -m pytest apps/api/tests/test_target_registry.py::test_protected_paths_cannot_be_allowed_by_policy_override -p no:cacheprovider -q`（RED） | 退出码 1；1 failed。清空 target denied paths 后 `.env.local` 未被拒绝 |
| protected override 与 canonical identity 2 个节点（GREEN） | 退出码 0；2 passed |
| `python -B -m pytest apps/api/tests/test_task_runs.py::test_persist_rejected_scope_decision_without_binding_is_unverifiable -p no:cacheprovider -q`（RED） | 退出码 1；1 failed。无 baseline/policy binding 的 rejected evidence 被错误持久化为 violation |
| unbound rejected 与可信 violation 2 个节点（GREEN） | 退出码 0；2 passed |
| `python -B -m pytest apps/api/tests/test_target_registry.py apps/api/tests/test_task_run_scope.py apps/api/tests/test_artifact_scope_guards.py <29 个显式 TaskRun identity/error-mapping 节点> -p no:cacheprovider -q` | 退出码 0；92 passed / 0 failed；未整文件运行 `test_task_runs.py`，未运行或声称运行全量 `pnpm test` |
| modified/new Python AST 检查 | 退出码 0；18 个 Python 文件全部解析成功，未生成 `.pyc` |
| `git diff --check` | 退出码 0；仅有 Windows checkout 的 LF→CRLF 提示，无 whitespace error |
| `openspec validate agenthub-taskrun-scope-preview-hardening --strict` | 退出码 0；`Change 'agenthub-taskrun-scope-preview-hardening' is valid` |

最终 pytest 的 1225 条 warning 均为既有 `datetime.utcnow()` 弃用提示。AST 路径收集另有既有 user-level gitignore 权限提示；这些 warning 未造成测试、AST、whitespace 或 OpenSpec 验证失败。

### 规格审查补充修复

- `persist_scope_decision()` 现在对 candidate `passed` 和 `rejected` 都独立重跑真实 scope validation，只有完整 decision equality 成立时才保留原分类；零越界 delta 的 forged rejection 或两次验证间已经 stale 的 decision 持久化为 `TASK_RUN_SCOPE_UNVERIFIABLE`。stale-recovery 的 violation 正向与 unbound-replay fixture 已改为真实 baseline 后出现规范越界 delta，不再依赖手工伪造 rejection。
- 默认公开 TaskRun metrics 对 scope decision/guard 使用显式安全 allowlist，仅保留 schema、result、TaskRun/target、snapshot version、count、validation timestamp、安全 error/reason。公开 checkpoint 删除 external `targetRoot`、baseline/attempt/Workspace/policy authorization bindings，同时保留 relative allowed/denied/planned/dirty/contract evidence 与 redacted scopeBaseline audit metadata；internal `metrics_json` 保持完整，供 transactional delivery 与授权链使用。
- 新增单一 canonical policy-pattern validator，并由 effective identity、allow 与 deny 判断共同使用。空白、遍历、POSIX absolute、Windows drive、UNC、control/NUL 和中间/unsupported wildcard 均使 policy identity 不可用且 `permits_path()` fail closed；合法 `*`、单个 suffix wildcard（含 `.env*`）、relative segment/subtree、排序和重复去重语义保持不变。TaskRun launch 遇到 corrupted/forged registry policy 时以 `TASK_RUN_SCOPE_UNVERIFIABLE` 拒绝 baseline。
- OpenSpec design 同步明确 malformed policy、公开安全 evidence allowlist/host-root redaction，以及 persisted passed/rejected 必须来自独立真实 revalidation。未修改 transactional delivery、snapshot collector、SSE、adapter、lock/launch timing 或 schema entity。

| 补充审查命令 | 结果 |
|---|---|
| forged rejected 与真实 out-of-scope delta 2 个节点（RED） | 退出码 1；1 failed / 1 passed。零越界 forged rejection 仍错误抛出 `TASK_RUN_SCOPE_VIOLATION`，真实 `package.json` delta 正向通过 |
| 同一 2 节点（GREEN） | 退出码 0；2 passed |
| external host root 与 public authorization binding allowlist 节点（RED/GREEN） | RED 退出码 1，1 failed，首先证明 `targetRoot` 仍公开；GREEN 退出码 0，连同既有 public/internal 回归共 4 passed |
| invalid policy identity/permit 与合法 wildcard 3 个节点（RED） | 退出码 1；18 failed / 1 passed。8 类 invalid pattern 在 allowed/denied 两侧共 16 failures，另有 2 个 `permits_path` wildcard 绕过 failure；合法 pattern 正向通过 |
| invalid registry policy TaskRun launch 节点（RED） | 退出码 1；1 failed。invalid policy 仍生成 usable baseline 且 requirement 未拒绝 |
| policy validator、合法 wildcard、identity stability 与 TaskRun mapping 6 个节点（GREEN） | 退出码 0；22 passed |
| external selected-folder `allowedPaths=['*']` frontend/backend 2 个既有节点 | 退出码 0；2 passed，确认合法外部 wildcard 注册语义未回归 |
| 首轮扩展总回归 | 退出码 1；130 passed / 1 failed。唯一失败为旧 stale-recovery positive 使用零 delta forged rejection，属于过时 fixture 而非 production 回归 |
| stale violation/replay 真实 delta fixture 聚焦回归 | 退出码 0；7 passed |
| `python -B -m pytest apps/api/tests/test_target_registry.py apps/api/tests/test_task_run_scope.py apps/api/tests/test_artifact_scope_guards.py apps/api/tests/test_run_diagnostics.py apps/api/tests/test_chat_events.py <32 个显式 TaskRun identity/error-mapping 节点> -p no:cacheprovider -q` | 退出码 0；131 passed / 0 failed；未整文件运行 `test_task_runs.py`，未运行或声称运行全量 `pnpm test` |
| modified/new Python AST 检查 | 退出码 0；18 个 Python 文件全部解析成功，未生成 `.pyc` |
| `git diff --check` 与未跟踪文件行尾空白检查 | 退出码 0；7 个未跟踪文件无行尾空白；仅有既有 LF→CRLF 与 user-level gitignore 权限提示 |
| `openspec validate agenthub-taskrun-scope-preview-hardening --strict` | 退出码 0；`Change 'agenthub-taskrun-scope-preview-hardening' is valid` |

最终扩展 pytest 的 1491 条 warning 均为既有 `datetime.utcnow()` 弃用提示，未造成测试失败。

### 公开 scope evidence 值级投影补充复核

- 默认 TaskRun metrics 的 decision/guard 现在先验证完整内部 schema、实际
  TaskRun 绑定与安全 target ID，再重建公开字段；畸形或伪造 evidence 整体省略，
  `taskRunId` 取自当前 TaskRun，失败 reason 使用固定文案而不复制持久化值。
- checkpoint 现在通过同一个显式安全投影服务 API metrics 与
  `task.checkpoint.created`。policy/path 列表逐值验证，任一成员非法时省略整个字段；
  Git status 与 unavailable baseline 使用固定 reason。`targetRoot`、授权绑定、
  internal entries、raw fingerprint、protected control digest、host path、secret 与
  任意持久化 reason 均不会进入公开投影；internal `metrics_json` 保持不变。
- `task.checkpoint.created` 是非失败 timeline evidence。固定的
  `scope_snapshot_unavailable` reason 不再被通用文本启发式误判为 provider failure；
  direct scope error、`task.scope_validation.failed` 与真实 provider failure 的分类路径
  保持不变。

| 补充复核命令 | 结果 |
|---|---|
| forged value、固定 failure reason、checkpoint event 与既有 checkpoint 4 节点（RED） | 退出码 1；4 failed。确认 key allowlist 仍会复制伪造 path/reason，且 event 仍发送 raw checkpoint |
| 同一 4 节点（GREEN） | 退出码 0；4 passed |
| public/persistence/policy 聚焦回归 | 退出码 0；43 passed |
| 五个 scope 相关完整测试文件加 38 个显式 TaskRun 节点（首轮扩展） | 退出码 1；135 passed / 2 failed。仅有 checkpoint informational event 被误分为 `provider_unavailable` |
| 两个 stale-recovery diagnostics 节点独立新进程复现（RED） | 退出码 1；2 failed，排除测试顺序或共享 fixture 污染 |
| 同一 2 节点与完整 diagnostics 文件（GREEN） | 退出码 0；分别 2 passed 与 15 passed |
| 同一扩展总回归（最终 GREEN） | 退出码 0；137 passed / 0 failed；未整文件运行 `test_task_runs.py`，未运行或声称运行全量 `pnpm test` |
| external selected-folder wildcard frontend/backend 2 个既有节点 | 退出码 0；2 passed |
| modified/new Python AST 检查 | 退出码 0；18 个 Python 文件全部解析成功，未生成 `.pyc` |
| `git diff --check` 与未跟踪文件行尾空白检查 | 退出码 0；7 个未跟踪文件无行尾空白；仅有既有 LF→CRLF 与 user-level gitignore 权限提示 |
| `openspec validate agenthub-taskrun-scope-preview-hardening --strict` | 退出码 0；`Change 'agenthub-taskrun-scope-preview-hardening' is valid` |

最终扩展 pytest 的 1641 条 warning 均为既有 `datetime.utcnow()` 弃用提示，未造成测试失败。

### 质量审查：候选路径、显式错误与 runtime binding

- `TargetProject` 的 shared authorization API 现在先使用单一 canonical
  repository-path predicate 验证 candidate，再执行 policy matching。candidate 不会被
  strip、separator normalization 或 traversal resolution；非法 candidate 的
  `allows_path()` 固定为 false、`denies_path()` 固定为 true。公开 checkpoint path
  list 复用同一 predicate，合法 `*` policy pattern、relative file/directory 与 Unicode
  path 语义保持不变。
- checkpoint-created 与 scope-passed informational event 只抑制来自 reason 文本的
  failure heuristic。recognized explicit scope/provider `errorCode` 保持优先并进入原有
  `validation_failed` 或 `provider_unavailable` 分类。
- scope runtime context constructor 的 Workspace、target、policy、baseline、capture
  time 与 execution-attempt binding 现在全部必填且必须非空，policy identity 必须为
  canonical SHA-256。删除 `unbound-*` fallback；invalid construction 使用安全的
  `TASK_RUN_SCOPE_UNVERIFIABLE`，不回显输入值。control key 仍可由内部安全生成。
- Test redaction fixtures use synthetic host paths; no machine workspace root is embedded.

| 质量审查命令 | 结果 |
|---|---|
| permissive `*` target 的 invalid candidate 与合法 relative/Unicode 17 参数（RED） | 退出码 1；14 failed / 3 passed。14 类非法 candidate 均被错误授权，合法正向保持通过 |
| 同一参数与 protected/policy/public-projection 回归（GREEN） | 退出码 0；20 passed |
| informational event 的 text-only、scope code、provider code 6 参数（RED） | 退出码 1；4 failed / 2 passed。显式 recognized code 被 informational 特判覆盖 |
| 同一参数与既有 diagnostics 回归（GREEN） | 退出码 0；10 passed |
| runtime authorization binding 8 个 invalid 参数（RED） | 退出码 1；8 failed。empty、None、whitespace 与 non-hex policy identity 均被接受 |
| changed/new-file machine-root scan (RED/GREEN) | RED: 3 fixtures; GREEN: no matches after synthetic replacement |
| 同一参数与 valid runtime/adapter/production context 回归（GREEN） | 退出码 0；12 passed |
| 五个 scope 相关完整测试文件加 38 个显式 TaskRun 节点 | 退出码 0；168 passed / 0 failed；未整文件运行 `test_task_runs.py`，未运行或声称运行全量 `pnpm test` |
| 完整 adapter 文件与 external selected-folder wildcard frontend/backend 2 节点 | 退出码 0；7 passed |
| modified/new Python AST 检查 | 退出码 0；18 个 Python 文件全部解析成功，未生成 `.pyc` |
| `git diff --check` 与未跟踪文件行尾空白检查 | 退出码 0；7 个未跟踪文件无行尾空白；仅有既有 LF→CRLF 与 user-level gitignore 权限提示 |
| `openspec validate agenthub-taskrun-scope-preview-hardening --strict` | 退出码 0；`Change 'agenthub-taskrun-scope-preview-hardening' is valid` |

最终扩展 pytest 的 1695 条 warning 均为既有 `datetime.utcnow()` 弃用提示，未造成测试失败。

## TaskRun scope 事件与诊断证据加固（OpenSpec 1.6）

**日期:** 2026-07-18

### 变更

- Run diagnostics 现在将 `TASK_RUN_SCOPE_VIOLATION` 和 `TASK_RUN_SCOPE_UNVERIFIABLE` 显式归类为 `validation_failed`，并把 scope validation 与 artifact scope refusal 事件投影到 `validation` timeline phase。
- `task.scope_validation.passed` 现在只作为 `validation` phase 的成功证据，不再产生 `validation_failed` contributing factor；事件 payload 的显式 scope error code 优先于容易误判 “unavailable” 等词的文本启发式。
- 写入型 TaskRun 的中心 artifact scope guard 在拒绝 Diff、Review、Preview 或 Deploy 前，通过既有 `append_task_run_event` 追加一次 `task.artifact_scope_refused`；同一 TaskRun 的重复手工请求或恢复重入不会无界追加重复拒绝事件。
- 拒绝事件只白名单化 guard result、安全错误码、TaskRun/target 标识、snapshot version、聚合计数和受保护类别；不会复制 host/protected path、文件内容、secret、raw fingerprint 或 protected control digest。缺失、失败或不可验证 marker 继续 fail closed，且不创建新 artifact。
- Diagnostics 的二次净化覆盖含空格的 Windows drive、UNC、standalone POSIX absolute host path、`cwd:/`、`root:/`、`worktree:/` tagged host path 和本地 `file://` URI、`.git` 子路径、raw 64-hex control evidence、scope/control key、protected tree records 和 file-content 字段，同时避免误伤 http(s) URL，并保留 `.env`、`.git`、`node_modules`、`secrets` 四类允许的安全聚合类别。
- 写入型运行若在 `collecting_diff` 阶段发生 stale/crash recovery，只会保留同时绑定当前 TaskRun、当前 `preRunCheckpoint` baseline identity/capture/attempt 和当前 registry-resolved target 的持久化 `TASK_RUN_SCOPE_VIOLATION`；其他不存在可验证 durable scope-pass marker 的情况以 `TASK_RUN_SCOPE_UNVERIFIABLE` fail closed。两者均释放运行资源并追加安全 `task.scope_validation.failed`；合法 pass marker 和普通 stale run 继续使用既有 `TASK_RUN_STALE` 语义。
- 新增聚焦回归，覆盖两类 scope 错误的诊断映射、缺失/失败 marker 的零 artifact 拒绝、安全聚合证据、重复调用幂等、真实 passed-marker 手工 Preview、missing protected control digest 的 recovery 级零 artifact 失败、前序 completed run 后的 queued launch baseline，以及拒绝事件沿既有 sequence/list/SSE replay 合同可读。SSE endpoint、编码和 delivery/recovery 语义未修改。

### 验证

| 命令 | 结果 |
|---|---|
| `python -B -m pytest apps/api/tests/test_run_diagnostics.py apps/api/tests/test_artifact_scope_guards.py apps/api/tests/test_chat_events.py -p no:cacheprovider -q`（RED） | 预期失败，9 failed / 18 passed；失败分别证明 scope 错误仍被归类为 `unknown`，且中心 guard 尚未追加可回放的拒绝事件 |
| `python -B -m pytest <passed diagnostics / collecting_diff recovery / completed predecessor / real pass-marker 6 个聚焦节点> -p no:cacheprovider -q`（第二轮 RED） | 预期失败，2 failed / 4 passed；失败证明 passed scope event 被误报为 failure，且 collecting_diff crash recovery 仍使用通用 stale 错误码 |
| 同一 6 节点命令（第二轮 GREEN） | 通过，6 项测试 |
| `python -B -m pytest apps/api/tests/test_run_diagnostics.py::test_scope_diagnostics_redact_host_and_raw_control_evidence -p no:cacheprovider -q`（第三轮 RED/GREEN） | 预期 1 failed 后通过 1 项测试；证明并修复跨平台 host/control evidence 二次净化缺口 |
| `python -B -m pytest <persisted violation recovery / extended redaction / same-count / protected-tree exception 5 个节点> -p no:cacheprovider -q`（正式审查 RED/GREEN） | 预期 2 failed / 3 passed 后通过 5 项测试；修复 violation 降级和通用 host/control evidence 缺口，并锁定 same-count 与 capture-exception 行为 |
| `python -B -m pytest apps/api/tests/test_task_run_scope.py apps/api/tests/test_artifact_scope_guards.py apps/api/tests/test_run_diagnostics.py apps/api/tests/test_chat_events.py <21 个 TaskRun scope/lifecycle 聚焦节点> -p no:cacheprovider -q` | 通过，75 项测试；覆盖 same-count protected content mutation、baseline/control-digest 缺失、runtime context 丢失、completed predecessor 后的 queued launch baseline、crash recovery、protected-tree capture exception、deferred completion 与 artifact guard |
| `python -B -m pytest <unbound rejected evidence / spaced host-path 2 个聚焦节点> -p no:cacheprovider -q`（补充审查 RED/GREEN） | RED 预期失败 4 项，GREEN 通过 4 项；锁定 rejected decision 的 run/checkpoint/resolved-target 绑定，并完整净化含空格 Windows/UNC/POSIX 与 `cwd:/` host path，同时保留 https URL 和安全类别 |
| `python -B -m pytest apps/api/tests/test_run_diagnostics.py::test_scope_diagnostics_fully_redact_spaced_and_cwd_host_paths -p no:cacheprovider -q`（第五轮 RED/GREEN） | RED 预期失败 1 项，GREEN 通过 1 项；补齐 `root:/`、`worktree:/` 和本地 `file:///` host evidence 的整段净化，https URL 保持原样 |
| `python -B -m pytest apps/api/tests/test_run_diagnostics.py apps/api/tests/test_artifact_scope_guards.py apps/api/tests/test_chat_events.py -p no:cacheprovider -q`（最终三文件 GREEN） | 通过，31 项测试 |
| `python -B -m pytest apps/api/tests/test_task_run_scope.py apps/api/tests/test_artifact_scope_guards.py apps/api/tests/test_run_diagnostics.py apps/api/tests/test_chat_events.py <9 个 TaskRun scope/recovery/deferred-completion 节点> -p no:cacheprovider -q`（主代理最终聚焦 GREEN） | 通过，65 项测试 |
| `python -B -c "import ast, pathlib; ..."` | 通过，5 个本轮相关 Python 文件均可解析 |
| `git diff --check` | 通过；仅有 Windows checkout 的 LF→CRLF 提示，无 whitespace error |

## OpenSpec 1.7 最终冻结验证

**日期:** 2026-07-18

为避免记录机器私有路径，下面以等价、可移植的 PowerShell 形式重现本次实际执行命令；
测试选择、参数和最终解析到的项目 venv interpreter 与实际执行一致。本次纯文档修订
未重新运行 pytest，也未运行或声称运行全量 `pnpm test`：

```powershell
$gitCommonDir = (& git rev-parse --path-format=absolute --git-common-dir).Trim()
$repoRoot = Split-Path -Parent $gitCommonDir
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$env:AGENTHUB_DATABASE_URL='sqlite://'
$env:PYTHONDONTWRITEBYTECODE='1'
& $python -B -m pytest `
  apps/api/tests/test_task_run_scope.py `
  apps/api/tests/test_artifact_scope_guards.py `
  apps/api/tests/test_run_diagnostics.py `
  apps/api/tests/test_chat_events.py `
  apps/api/tests/test_adapters.py `
  apps/api/tests/test_diffs.py `
  apps/api/tests/test_previews.py `
  apps/api/tests/test_deployments.py `
  apps/api/tests/test_external_reviews.py `
  apps/api/tests/test_task_runs.py::test_background_scope_baseline_is_captured_under_lock_before_create_run `
  apps/api/tests/test_task_runs.py::test_background_scope_capture_failure_does_not_start_adapter `
  apps/api/tests/test_task_runs.py::test_queued_shared_worktree_run_captures_baseline_after_previous_completed_run `
  apps/api/tests/test_task_runs.py::test_finalize_adapter_completed_task_run_fails_scope_before_artifacts `
  apps/api/tests/test_task_runs.py::test_finalize_adapter_completed_task_run_passes_scope_before_completion `
  apps/api/tests/test_task_runs.py::test_adapter_completed_event_retains_target_lock_until_scope_finalizer `
  apps/api/tests/test_task_runs.py::test_collecting_diff_stale_recovery_fails_closed_for_missing_control_digest `
  apps/api/tests/test_task_runs.py::test_collecting_diff_stale_recovery_keeps_stale_code_for_valid_scope_pass `
  apps/api/tests/test_task_runs.py::test_collecting_diff_stale_recovery_preserves_persisted_scope_violation `
  apps/api/tests/test_task_runs.py::test_collecting_diff_stale_recovery_rejects_unbound_violation_evidence `
  apps/api/tests/test_task_runs.py::test_finalize_protected_tree_capture_exception_is_safe_and_unverifiable `
  -k "not test_preview_process_env_prefers_system_node_over_codex_bundled_node" `
  -p no:cacheprovider -q
```

下列无 `.pyc` AST 检查代码块同样以等价、可移植形式记录该次实际执行命令，并沿用
上文同一 PowerShell 会话中定义的 `$python`：

```powershell
$paths = @(
  & git diff HEAD --name-only --diff-filter=ACMR -- '*.py'
  & git ls-files --others --exclude-standard -- '*.py'
) | Sort-Object -Unique
& $python -B -c "import ast, pathlib, sys; paths=[pathlib.Path(p) for p in sys.argv[1:]]; [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in paths]; print(f'AST parsed {len(paths)} Python files'); print(*(str(p) for p in paths), sep='\n')" @paths
```

| 检查 | 结果 |
|---|---|
| 上述 focused backend pytest | 退出码 0；118 passed / 1 deselected；仅排除 Windows 下不适用的既有 macOS PATH 用例 |
| 上述 AST 检查 | 退出码 0；本次 2026-07-18 冻结验证快照中的 18 个 modified/new Python 文件全部解析成功，未生成 `.pyc` |
| `git diff --check` | 退出码 0；仅有 Windows checkout 的 LF→CRLF 提示，无 whitespace error |
| `$untracked = @(& git ls-files --others --exclude-standard); rg -n '[ \t]+$' -- $untracked` | 本次 2026-07-18 冻结验证快照中的 7 个 untracked 新文件无行尾空白匹配；Git 另提示无法读取用户级 global gitignore 文件，但该次已完整列出并检查仓库内 7 个文件 |
| `openspec validate agenthub-taskrun-scope-preview-hardening --strict` | 退出码 0；`Change 'agenthub-taskrun-scope-preview-hardening' is valid` |

本次 2026-07-18 冻结验证快照的已知 warning：pytest 汇总 1700 条既有 `apps/api/app/models.py:13`
`datetime.utcnow()` 弃用 warning；Git 输出上述 LF→CRLF 与用户级 ignore 权限提示。
这些 warning 未造成测试、AST、whitespace 或 OpenSpec 验证失败。

## TaskRun scope 延迟完成门禁

**日期:** 2026-07-16

### 变更

- Adapter 的原始 `completed` 事件和 `task.state: completed` 都只将 TaskRun 保持在非终态 `collecting_diff`；写入型运行由 Run Engine 先持久化 post-run scope 决策，再根据 durable scope-pass marker 决定失败或继续收集 Diff/Review。
- Scope 拒绝或不可验证时，先记录 `task.scope_validation.failed`，再以对应安全错误码单次进入 `failed`，释放 queue/target lock 并刷新 ledger；不会执行 Review task 完成、自动 Preview/Deploy 或 downstream 调度。
- Scope 通过时，marker 重验和 `task.scope_validation.passed` 均先于 Diff/Review；完成制品收集后单次进入 `completed`，终态之后才刷新 ledger、完成 Review task、执行自动 Preview/Deploy 和 downstream 调度。只读运行保留旧制品流程。
- Scope finalizer 使用内部、持久化且不对外公开的 `metrics_json` CAS claim；并发或重复调用只有一个 winner 可以验证、创建制品和触发终态/下游副作用，loser 与终态重入会幂等返回。
- Adapter 的 `error`/`*_INTERRUPTED` 直接终态路径现在同步清理 TaskRun scope runtime context，避免终态运行残留进程内控制密钥。
- 手工 Diff、Review、Preview、Deploy API、旧自动 finalizer 以及 preview/deploy job 的 enqueue 与恢复执行路径现在都在创建制品或 job 前要求写入型 source TaskRun 具备 durable scope-pass marker；legacy、拒绝和不可验证的写入运行 fail closed，只读运行保留既有制品收尾行为。
- Deploy job 会绑定并重验 `Preview -> Artifact -> TaskRun` 的真实来源，禁止用其他运行的 marker 授权 preview；job 使用 `queued -> running` 条件 claim，terminal 重放不会重复启动进程或创建 Deployment，孤儿 source 安全归类为 `TASK_RUN_SCOPE_UNVERIFIABLE`。

### 验证

| 命令 | 结果 |
|---|---|
| `python -B -m pytest <TaskRun scope finalizer focused nodes> <adapter completion/terminal cleanup nodes> -p no:cacheprovider -q` | 通过，9 项测试 |
| `python -B -m pytest <legacy finalizer nodes> apps/api/tests/test_adapters.py apps/api/tests/test_task_run_scope.py -p no:cacheprovider -q` | 通过，29 项测试 |
| `python -B -m pytest apps/api/tests/test_artifact_scope_guards.py -p no:cacheprovider -q` | 通过，12 项测试 |
| `python -B -m pytest apps/api/tests/test_diffs.py apps/api/tests/test_previews.py apps/api/tests/test_deployments.py apps/api/tests/test_external_reviews.py -k "not test_preview_process_env_prefers_system_node_over_codex_bundled_node" -p no:cacheprovider -q` | 通过，46 项测试；1 项仅适用于 macOS PATH 的既有用例在 Windows 上排除 |
| `python -B -c "import ast, pathlib; ..."` | 通过，修改的 Python 文件均可解析 |

## 消息路由拆分与调度边界修复

**日期:** 2026-07-05

### 变更

- 新增 `apps/api/app/routes/messages.py`，将 Session message 读写、用户消息规划触发、自动启动安全判定从 `main.py` 拆出；`main.py` 仅挂载 `messages_router`，保留原 `/sessions/{session_id}/messages` API 行为。
- 迁移时保留 `autoStart`、`safeTarget`、目标 agent 权限和目标路径白名单校验，避免自动启动任务越过 demo target 边界。
- 修复外部项目 dirty-worktree 检查的路径坐标问题：当外部 target 位于 AgentHub 仓库子目录时，Git 返回的仓库根相对路径会先归一化为 target root 相对路径，再与计划文件比较，避免被父仓库未提交改动误判阻塞。
- 让调度器测试中的同目标写任务和 provisioned frontend run 任务显式设置 `priority`，避免同一时间戳下 UUID 排序导致“第二个任务”反向阻塞“第一个任务”的非确定性失败。
- 将 pytest `--basetemp .pytest-tmp` 生成的临时目录加入 `.gitignore`，避免测试产物进入提交候选或污染 `git status`。

### 验证

| 命令 | 结果 |
|---|---|
| `.\.venv\Scripts\python -m compileall apps\api\app` | 通过 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_chat_events.py apps\api\tests\test_planning.py apps\api\tests\test_scheduler.py -q --basetemp .pytest-tmp` | 通过，79 项测试 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_sessions.py apps\api\tests\test_external_workspaces.py apps\api\tests\test_project_provisioning.py -q --basetemp .pytest-tmp` | 通过，26 项测试 |
| `.\node_modules\.bin\tsc.cmd -p apps\web\tsconfig.json --noEmit` | 通过 |
| `git diff --check` | 通过；仅有 Windows CRLF 提示，无 whitespace 错误 |

## 对抗性审查修复与日志归档

**日期:** 2026-07-05

### 变更

- 修复 Windows 本地系统目录防护缺口：外部目标注册和本地文件夹浏览现在共用跨平台系统路径判定，并覆盖 `C:\Windows`、`Program Files`、`ProgramData` 等 Windows 根目录。
- 让 project provisioning 测试不再依赖真实 `git worktree add`：测试通过 fake worktree service 保持 HTTP API 流程，同时避免受限环境下提前失败；路径断言改为跨平台 `Path` 语义。
- 在 `pnpm-workspace.yaml` 启用 `strictDepBuilds`，并只显式允许 `esbuild`、`sharp`、`unrs-resolver` 构建脚本；README 补充依赖审批说明，避免全量 `approve-builds --all`。
- 新增 `apps/api/app/routes/sessions.py`，将 Session 创建、读取、更新、target selection 和 memory snapshot refresh 路由从 `main.py` 拆出。
- 新增 `apps/web/src/components/task-run-controls.tsx`，从任务卡片列表中拆出运行控制和审批卡片；新增 `apps/web/src/lib/api-core.ts`，集中 API URL、错误类型和错误消息解析。
- 修复 `task-card-list.tsx` 中预览制品 `Monitor` 图标缺失导入。
- 将 2026-06-10 及更早变更日志归档到 `docs/history/change-log-archive.md`，当前 `docs/change-log.md` 保留近期阶段和归档入口。

### 验证

| 命令 | 结果 |
|---|---|
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_external_workspaces.py -q --basetemp .pytest-tmp` | 通过，11 项测试 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_project_provisioning.py -q --basetemp .pytest-tmp` | 通过，8 项测试 |
| `.\.venv\Scripts\python -m compileall apps\api\app` | 通过 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_sessions.py apps\api\tests\test_external_workspaces.py apps\api\tests\test_project_provisioning.py -q --basetemp .pytest-tmp` | 通过，26 项测试 |
| `.\node_modules\.bin\tsc.cmd -p apps\web\tsconfig.json --noEmit` | 通过 |
| `pnpm --filter @agenthub/web check` | 未运行到前端检查阶段；pnpm 要求清理/重建 `node_modules`，依赖重装和构建脚本执行审批被安全策略拒绝 |
| `pnpm --filter @agenthub/web test src/components/task-card-list.test.tsx -- --runInBand` | 未运行到测试阶段；同样受 pnpm 模块目录重建审批阻塞 |

## 轻量工程拆分与代码地图同步

**日期:** 2026-07-05

### 变更

- 新增 `apps/api/app/dependencies.py`，集中 FastAPI 共享依赖和 preview/deploy service 实例，保持现有运行语义不变。
- 新增 `apps/api/app/routes/registries.py`、`apps/api/app/routes/workspaces.py` 和 `apps/api/app/routes/targets.py`，将 provider/deployment registry、demo workspace、workspace targets、外部项目分析/注册、本地文件夹浏览和 project provisioning 路由从 `main.py` 拆出。
- `apps/api/app/main.py` 改为挂载 `health`、`registries`、`targets`、`workspaces` routers，保留尚未拆分的 session/task-run/artifact/runtime-config 等主业务路由。
- 新增 `apps/web/src/components/execution-trace.tsx`，从 `task-card-list.tsx` 抽出多 Agent 执行链路展示和 trace helper，降低任务卡片组件体积。
- 更新 `docs/architecture.md`，同步当前后端 router 地图、共享依赖模块、前端 execution trace 组件和剩余技术债。

### 验证

| 命令 | 结果 |
|---|---|
| `.\.venv\Scripts\python -m compileall apps\api\app` | 通过 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_external_workspaces.py apps\api\tests\test_project_analyzer.py apps\api\tests\test_health.py apps\api\tests\test_provider_configs.py apps\api\tests\test_deployment_providers.py -q --basetemp .pytest-tmp` | 通过，23 项测试 |
| `.\.venv\Scripts\python -m pytest apps\api\tests\test_project_provisioning.py -q --basetemp .pytest-tmp` | 未通过，2 passed / 6 failed；5 个 apply 用例在 session 创建响应缺少 `id` 时提前失败，1 个计划用例命中 Windows 路径分隔符断言 |
| `pnpm --filter @agenthub/web check` | 未通过；sandbox 内 npm registry 返回 `EACCES`，联网授权后依赖下载完成，但被 `ERR_PNPM_IGNORED_BUILDS` 阻止，需要显式批准 `esbuild`、`sharp`、`unrs-resolver` build scripts |
| `pnpm --filter @agenthub/web test src/components/task-card-list.test.tsx -- --runInBand` | 未运行到测试阶段；同样受 `ERR_PNPM_IGNORED_BUILDS` build-script 审批阻塞 |

> 注：本节是当时的历史验证记录。project provisioning 失败和 `ERR_PNPM_IGNORED_BUILDS` 配置缺口已在上方“对抗性审查修复与日志归档”中处理；完整前端 `pnpm check/test` 仍需用户明确批准依赖重建和第三方构建脚本执行。

## 比赛交付说明与公开入口校准

**日期:** 2026-07-05

### 变更

- 在 `README.md` 增加比赛交付看点，按评分维度映射到仓库证据和现场演示动作。
- 在 `README.md` 增加 3 分钟 Demo 路径和交付文档入口，链接演示脚本、技术架构、AGENTS、OpenSpec 和变更日志。
- 新增 `docs/demo-script.md`，作为比赛录屏、现场演示和答辩脚本，覆盖开场话术、主路径、fallback 路径、扩展路径、答辩速答和失败预案。
- 新增 `docs/architecture.md`，作为技术文档和答辩说明，覆盖核心链路、运行时组件、后端/前端代码地图、数据模型、可靠性边界、技术选型和已知技术债。
- 调整 `.gitignore`，显式放行 `docs/demo-script.md` 和 `docs/architecture.md`，让比赛交付脚本和技术文档可进入仓库。
- 修复 README 中指向不存在的 `docs/adapter-notes.md` 和 `docs/claude-code-adapter-notes.md` 的说明，改为当前真实 CLI 配置方式和适配器代码入口。
- 轻调 `index.html` 首屏文案，将公开首页定位收敛为面向比赛题面的本地可运行多 Agent 协作 Demo。
- 新增 `apps/api/app/routes/health.py` 并在 `apps/api/app/main.py` 挂载，作为 FastAPI 路由拆分的第一步；`/health` 响应行为保持不变。

### 验证

| 命令 | 结果 |
|---|---|
| `python -m compileall apps\api\app` | 通过 |
| `python -m pytest apps\api\tests\test_health.py -q` | 未通过环境收集，当前工作区没有 `.venv`，系统 Python 缺少 `fastapi` |
| `rg -n "adapter-notes|claude-code-adapter-notes" README.md index.html` | 通过，无坏链接残留 |
| `git status --short docs/demo-script.md docs/architecture.md` | 通过，两个新增文档显示为未跟踪文件而非 ignored |
| `git diff --check -- .gitignore README.md index.html apps/api/app/main.py docs/change-log.md` | 通过 |
| `rg -n "[ \t]+$" .gitignore README.md index.html apps/api/app/main.py apps/api/app/routes/__init__.py apps/api/app/routes/health.py docs/demo-script.md docs/architecture.md docs/change-log.md` | 通过，无行尾空白 |

## 历史归档

- 2026-06-10 及更早阶段详见 [docs/history/change-log-archive.md](history/change-log-archive.md)。
