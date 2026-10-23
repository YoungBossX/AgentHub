# Representative local workflow evaluation

## Native QA extension (2026-10-16)

The current v2 runner binds explicit coding profiles and a Claude read-only QA
profile in each isolated evaluation DB. Live CLI execution requires native QA,
full-file Read/assessment/source identity and current independent checks. V1
historical results below used scripted QA; they remain historical observations.

The report adds `cohort`, `status`, per-attempt/role timing and bounded natural
execution retries (`--max-retries 0..2`, default 1). Model warning/failed findings
remain failures, not an automatic repair trigger. Running/interrupted or mixed-
source batches do not publish final rates. A cohort includes uncommitted source,
harness helpers, fixture/dependency declarations and explicit selection policy;
changing source stops the batch and invalidates all combined rates.

To repeat a fresh expanded native batch, use the existing configured CLI credentials
and native Planner, a fresh external output, `--repetitions 2` and optionally an
explicit retry bound. Five fixed categories repeated twice are ten fresh samples,
not ten distinct tasks or a general model-success estimate. Full source/read/
timing boundaries and completed cohort: [native QA record](native-qa-evaluation-review.md).

This complements the fixed three-case external module benchmark. It exercises
the production message route, natural-language planner/dispatcher, task scheduler,
execution queue and existing adapters using a fresh database and disposable Git
fixture. It invokes the route directly with a bound database; it does not test
HTTP transport, the workbench UI, model result summaries or preview/deployment.

## Frozen scenarios

| Case | Independent acceptance |
| --- | --- |
| `backend-repair` | Fixed real Python/ASGI health and contacts contracts after repairing a failing health implementation |
| `multi-file` | Type/build/output checks and actual desktop/narrow heading, with at least two changed frontend source files |
| `coordinated-contacts` | Fixed backend contracts plus actual browser GET/create/refresh through the assigned FastAPI app; random contact name/email cannot be known before evaluation |
| `follow-up` | Two persisted natural-language messages in the same Session, each checked at its own source version |
| `retry-recovery` | Labeled existing Codex forced-failure injection, original failure retained and retry linked, followed by independent acceptance |

The contacts transport runs the assigned backend in a disposable copy through
TestClient, exposes only GET/POST contacts via pipes, and permits no target
networking/process execution. Browser requests remain restricted to a fixed
virtual origin. Python audit controls reduce side effects but are not an OS
sandbox for actively hostile code. No external services or real database are
tested, and the fault injection is not a natural provider outage.

## Run

Use the existing project virtualenv from `apps/api`, PowerShell:

```powershell
$workflowOutput = Join-Path $env:TEMP ('agenthub-workflows-' + [guid]::NewGuid())
& ../../.venv/Scripts/python.exe -m app.workflow_evaluation --output $workflowOutput --prepare-only
```

The output path must be new and outside the checkout/system directories. The
runner does not overwrite/delete old evidence. Preparation runs actual failing
baselines without Provider calls; unavailable tools do not count as a valid
negative baseline. It writes `report.json`, fixture source and fixture-only Git
baselines. Live cases also get isolated `workflow.sqlite3` databases.

For live execution, configure the existing native Planner/CLI environment first,
for example the already supported `AGENTHUB_LLM_PLANNER_PROVIDER=claude_cli` with
its required local credentials. The tool does not alter saved product settings
or install a provider. Start with one bounded case:

```powershell
$workflowOutput = Join-Path $env:TEMP ('agenthub-workflows-live-' + [guid]::NewGuid())
& ../../.venv/Scripts/python.exe -m app.workflow_evaluation --output $workflowOutput --case backend-repair
```

`--adapter` selects `codex` (default) or `claude_code` for coding. `--repetitions`
accepts 1–10 independent fresh fixtures and `--timeout` bounds each phase to
60–1800 seconds (default 900), alongside existing CLI limits. Omit `--case` for
all five. The native Planner must actually execute; deterministic fallback is
recorded but does not count as native planning success or start coding silently.

Inspect `mode`, `phases`, `attempts`, `failureGates`, source/policy fingerprints,
and the natural/fault-injection category summaries. First-attempt and final rates
use all selected scenarios, including failed/unattempted cases; prepared or test
execution has null rates. Retries do not erase original failures. Wall duration
is not model inference time; unknown model/token/cost fields stay null.

## Current validation

2026-10-15: workflow/acceptance/scoring tests **29 passed**, including real failing
baselines for all five categories, browser → FastAPI create/reload and a broken
persistence negative control, explicitly labeled provider doubles for every full
queue/Diff/acceptance scenario, and partial-report/cancellation cleanup.
Existing external benchmark/backend/gate regressions **79 passed**. Native/group
planning and adjacent tests **83 passed**; subsequent observation/path/contract
and bounded cancellation checks **32 passed**, then **4** observed backend workflow
checks passed. Batches overlap; do not sum them into a unique total.

The first two bounded live backend preparations reached a real native Planner but
were rejected because it emitted `app/main.py` instead of the registered worktree
path `apps/demo-api/app/main.py`. The first had only the high-level rejection;
the next added bounded opt-in planner-call evidence (provider, input/output hashes
and planned paths, no raw prompt). The system prompt now explicitly distinguishes
built-in worktree paths from external checkout paths; permissions and path checks
remain unchanged.

A fresh live backend scenario then **passed**, with actual Claude CLI planning,
Codex file changes, matching Diff/scope, version-bound Python/ASGI checks and
independent acceptance, **93.046 seconds**, no retries. QA remained a scripted
read-only report; this is not a model-review or full-business acceptance claim.
The earlier two failures are retained under their original source/input versions,
not folded into the new single-case rate. The complete five-category live batch
and subsequent targeted rechecks are recorded separately below.

The completed first full batch passed **4/5** final and **3/5** first-attempt,
including a labeled fault-injection recovery with one retry. Natural scenarios
passed **3/4**; the injected scenario is reported separately. These fixed synthetic
samples do not establish a general model success rate.

The coordinated case was rejected for `pnpm build` on `demo-backend`. A separate
valid multi-target plan reproduced unconditional merging of aggregate commands
into every target, then passed after target-specific distribution was implemented.
Group-level prose/commands remain in provenance; unknown aggregate commands and
commands explicitly attached to the wrong task still reject atomically. Relevant
planning/queue regressions **103 passed**.

A new native coordinated attempt reached coding with correctly scoped validation
expectations and passed backend checks, but its frontend was interrupted by the
explicitly selected 240-second phase deadline. That failed report is retained.
SQLite confirmed the run actually terminated; the report now preserves cutoff
state separately and refreshes final states after cleanup. Cancellation-related
regressions **5 passed**. The next fresh coordinated run under the default full
bounded deadline **passed in 215.969 seconds**, without retry: actual Claude
planning and Codex backend/frontend edits, matching Diff/scope/automatic validation,
two scripted read-only QA runs, and ten desktop/390px integration checks in
Edge **155.0.4283.45**. Random contacts were created through real ASGI POST, returned
by GET and still displayed after browser reload. This is a separate source-policy
version and is not substituted into the first batch's 4/5 denominator.

Final missing-evidence/scoping/observation regressions **22 passed**; absent
independent source evidence is reported as unverified, not a proven mismatch.
Root checks, strict OpenSpec and whitespace validation passed. The task is complete
locally; no full API rerun, new remote CI, model QA or production/UI-transport
acceptance is implied. See [bounded evidence](evidence/workflow-evaluation/README.md).


## Native QA v2 cohort closeout, 2026-10-16

The same-source native-QA expansion is complete locally: five categories, two
repetitions, ten verified native QA attempts; first 4/10 and final 6/10. Natural
scenarios 4/8 and 4/8, injected recovery 0/2 and 2/2 with two retries. Four failures
remain visible. Native QA is not merely configured or replaced by scripted review.
See [v2 inspection and timing](native-qa-evaluation-review.md) and the separate
[bounded batch](evidence/native-qa-evaluation/batch.json). These results do not
rewrite the v1 cohort above. Items 2 and 3 were completed later in separate
[business coverage](business-contract-coverage-review.md) and
[modularity](execution-card-modularity-review.md) tasks. Their subsequent source
changes do not relabel this frozen cohort as current-version performance.

## 中文联系人固定验收与一次受限修复

`contacts-boundaries` 是显式选择的独立场景，不加入默认五类评测，也不改写旧 v1/v2
契约和历史中文50次结果。`contacts-boundaries-v3` 固定28项检查，覆盖桌面/390px、中文
表单、创建/重复/重试/持久化、完整邮箱判重、前后端空白姓名，以及真实 POST 201 后
注入 GET 503 的刷新失败。后者要求保留已创建联系人、清空已提交表单、显示中性的
中文 `role=status` 提示；注入响应在记录中标注，不能当成自然故障。

默认仅执行与验收。显式添加 `--repair-contract-failures` 才会对当前完整业务失败
启动一次修复：只选固定失败ID，最多8项，不复制模型日志中的指令；源码、策略、会话
和计划范围在现有执行锁内再校验，原消息/运行/范围指纹写入 TaskRun JSON。
只允许按失败目标修改 `apps/demo/src/App.tsx` 或 `apps/demo-api/app/main.py`，
最多两个写任务及其只读QA，修复不自动重试，共享该场景剩余时限；超时或中断停止待执行任务。
源码变化、环境不可用、缺少检查证据、规划/权限/固定检查失败均不会授权业务修复。

在 `apps/api` 中使用已配置的真实 Planner/CLI；先创建E盘临时目录，输出必须是新目录：

```powershell
$env:TEMP = 'E:/Docker/AgentHub/workflow-temp'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$workflowOutput = 'E:/Docker/AgentHub/contacts-feedback-' + [guid]::NewGuid()
& ../../.venv/Scripts/python.exe -B -m app.workflow_evaluation --output $workflowOutput --case contacts-boundaries --repair-contract-failures --max-retries 0
```

报告中的 `phases`、`verdict`、首次通过率保留首次结果；`repairPhases` 和
`repairOutcome` 单独记录修复，`summary.repairs` 单独统计恢复。修复成功不会使原失败
退出码变为0，防止将追加修复计入自然通过率。Token与阶段汇总包含首次和修复的所有
已记录调用，未知用量仍为空。修复后仍以完整28项及原有固定检查/QA复验，未选问题也不能跳过。

这是隔离评测服务与开发者CLI的入口。工作台仍使用既有“选择评审问题 → 修复草稿 →
用户发送 → 执行复验”，未加入任意业务自动修复或新权限。验收副本只对Windows共享文件
占用重试清理；仍被占用则保留E盘副本并在 `cleanup` 中记为 `retained_busy`。

2026-10-22 本地验收：完整API **2867 passed / 19 skipped / 2 warnings**，退出0；
Web333、工具24、demo-api5、根检查和独立复核通过。跳过不计通过，警告来自既有
表达式索引拒绝测试。正例执行“首次业务失败 → 前端修复 → 28项通过”，反例修复后
仍失败且没有第二次派发；两者各保留8条逻辑调用，包括2次Planner及6次TaskRun。
取消、共享时限、版本/范围变化、异常报告保留、前端缺失与独立后端检查、Windows清理
均有回归。本轮编码/Planner为明确测试替身，真实浏览器和ASGI执行；未追加真实模型样本。
产品库主文件哈希及旧交付清单41份文件哈希一致。首次测试入口漏初始化的无效回归、
修复过程的失败记录均保留在 `E:/Docker/AgentHub/contacts-feedback-20261022-01`，
最终完整结果为 `api-final.log` / `api-final-results.xml`，快照及核验为 `final-verification.json`。
当前仅本地实现，未提交或推送，也未声明远程CI通过。

2026-10-22 后续1.5真实稳定性迭代记录见
[中文真实任务稳定性与交付核验](real-api-stability-validation-20261022.md)。
后续真实调用、中间版本修复与原1.4测试替身分别记录，不改写历史50次分母。

### 原生 QA 严格输出与可见回归覆盖

1.6只读 Claude QA 使用固定评审 JSON Schema 与成功事件中的 `structured_output`。
本机 CLI 须支持 `--json-schema`；不支持或没有有效结构化回执时仍失败，不自动降级。
字段、状态与风险语义、源码指纹、真实完整Read、退出码均继续校验，不推断缺失severity。
CLI内部 `StructuredOutput` 是序列化事件，既不授予文件/命令权限，也不证明读取过文件；
`--tools` 和 `--allowedTools` 均仍为 `Read`。
验收应选择带 `claude_read_only` 的自定义评审配置；内置兼容QA或任意Claude编码配置
不能替代该原生只读路径。工作流CLI会使用 `bound_scenario` 绑定已创建的评审配置，
开发者自写验收脚本也必须保留这一步；不能通过篡改已失败Task的配置来补造成功。

仅新 `contacts-boundaries-v3` 夹具额外包含
`apps/demo-api/tests/test_contacts_boundaries.py`，让QA能读取需求对应的固定边界用例。
这些文件存在不代表已执行，原生评审的 `validation` 仍为 `not_run`；独立28项业务检查
及固定版本验收仍必须通过。测试材料纳入基线哈希，编辑会导致严格验收失败；
这是一致性门禁，并非OS级文件只读或新增的执行沙箱。旧v1/v2及已归档结果保持原样。
