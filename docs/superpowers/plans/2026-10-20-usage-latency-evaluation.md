# Provider Usage and Workflow Latency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist honest per-call usage and stage timings, then measure 50 Chinese natural workflow episodes on one frozen version with recovery in a separate cohort.

**Architecture:** Extend existing CLI result receipts, TaskRun JSON metrics and trusted workflow reports. No schema transition, new service, dependencies or expanded adapter permissions. The user explicitly authorized implementation and live testing against the preceding metric design; continue inline.

**Tech Stack:** Existing Python/FastAPI/SQLModel/SQLite, Claude/Codex CLI, trusted native validation and browser contracts.

**Spec:** `openspec/changes/agenthub-workflow-evaluation/specs/workflow-evaluation/spec.md`, task 1.3; metric definitions approved in `docs/resume-metrics-plan-20261020.md`.

## Global Constraints

- Preserve prior English/Chinese results and product data; all new databases, raw evidence and temporary files under `E:/Docker/AgentHub/usage-latency-20261020-01`.
- Keep all adapters and native validation defaults; no schema or network/tool scope expansion, dependency installation, commit or push.
- Extract allowlisted numeric usage only; absent/invalid values are null, booleans/negative/nonfinite numbers are invalid. CLI estimated USD is not verified billing.
- Retain one final result per independent call. Do not add streamed snapshots or model breakdowns to the same final aggregate. Include failed/retried calls; preserve unknown coverage.
- Time application-observed semantic text, not arbitrary deltas or true model first-token latency. Missing/cancelled stages remain null.
- Freeze runtime, operator, input and validation policy before each cohort. Stop on source changes. Repairs preserve old outcomes and use a new complete formal cohort.

## Review Focus

- Error/result followed by nonzero exit must preserve reported usage and timings while remaining failed.
- Repeated/partial usage and invalid numeric fields must not inflate totals or manufacture zero cost.
- Cancellation or lost ownership must not persist events/metrics into a stale run.
- Queue wait, launch, semantic text, adapter wall time, finalization and independent acceptance must have explicit nonoverlapping or clearly nested definitions.
- Ordinary episodes and deliberate faults, probes, feedback repairs and source versions must never share a success-rate denominator.

### Task 1: Persist bounded usage and timing receipts

**Files:** Create `apps/api/app/execution_telemetry.py` and `apps/api/tests/test_execution_telemetry.py`; modify `claude_code_adapter.py`, `codex_adapter.py`, `adapters.py`, `planner_providers.py`, associated tests.

**Interfaces:** `provider_usage(raw, protocol)` returns a bounded receipt with nullable input/output/cache tokens, estimated cost and provider durations; `AdapterTiming` records monotonic launch/first-visible-text/terminal observations; existing TaskRun JSON metrics carry `providerUsage` and `executionTiming`. PlannerProviderResult adds an optional usage field without changing existing construction.

- [x] Write failing tests for Claude success/error usage, invalid/absent/zero fields, model metadata bounds, stream deduplication, nonsemantic events, launch timings and guarded durable persistence.
- [x] Run focused tests to observe the missing receipts/behavior.
- [x] Implement normalization and minimal call-site integration; Planner uses JSON envelope for its existing text-input path while retaining bounded stdin streaming and legacy contract compatibility.
- [x] Run telemetry, adapters, CLI/native review, Planner, ownership and cancellation regressions; inspect failures before edits.

### Task 2: Report stages and same-version natural/recovery cohorts

**Files:** Create `apps/api/app/workflow_metrics.py`, `apps/api/tests/test_workflow_metrics.py`; modify `workflow_evaluation.py`, workflow tests, docs and the current OpenSpec task. Operator files live only in the external evidence directory.

**Interfaces:** Workflow attempts expose `providerUsage` and `stageTimings`; phase receipts expose planning/dispatch, execution and independent acceptance timings. Aggregates deduplicate attempts by TaskRun ID and count Planner call receipts once per phase; nullable sums report known/unknown denominators. Quantiles use declared nearest-rank P50/P95 and are descriptive for small samples.

- [x] Add failing tests for aggregation across retries/failed calls, partial coverage, semantic text filtering, queue/finalization definitions and the bounded 10-repetition option.
- [x] Implement extraction and aggregation; preserve all existing outcome gates.
- [x] Verify focused workflow regressions and project checks, then archive source and operator hashes.
- [x] Run a paid probe of each supported workflow category; preserve all failures, fix reproduced platform defects with red/green tests, and freeze a new version before formal execution.
- [x] Run five natural Chinese workflow categories ×10 repetitions, each episode with an isolated DB/target and explicit timeout/retry budget. Heading-single replaces the injected fault category. State clearly that these are repeated fixed scenarios, not 50 distinct arbitrary coding requests.
- [x] Run deliberate failure/retry recovery in a separate directory and denominator on the same frozen source; retain the injected initial failures.
- [x] Independently verify receipts/source/Diff/acceptance, Token coverage, per-stage timings, product/old-evidence preservation, and update the change log and final report. Mark OpenSpec 1.3 complete only after the authorized measurement is actually complete.

## Progress / rulings

- Initial state and product SQLite are backed up on E drive. No leftover evaluation processes observed after the interrupted turn.
- Ruling: continue in the current `dev` working tree with a full pre-change patch/untracked snapshot; a fresh HEAD worktree would omit already-tested uncommitted fixes required for Chinese evaluation.
- Ruling: preserve evidence and the plan workspace instead of skill cleanup/commit steps, because the user requires retained results and has not authorized Git delivery.

- Final: natural50 strict40/50, independent business46/50; separate recovery10/10; independent audits and seven actual screenshots complete. Feedback28/28 and unchanged-budget timeout rerun passed separately; original failures and unknown usage retained.
