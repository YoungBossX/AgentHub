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
accepts 1–5 independent fresh fixtures and `--timeout` bounds each phase to
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
