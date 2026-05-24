# P10 Freeze Review

**Date:** 2026-05-24

## Result

P10 is ready to freeze as Scheduler Robustness and Conflict Recovery.

P10 did not run a fresh real Claude/Codex mutation. The freeze review used
deterministic local unit/API tests and existing P6/P7/P8/P9 baseline coverage.

## Rehearsal Evidence

| Scenario | Evidence |
|---|---|
| TaskRun heartbeat and lease | `tests/test_task_runs.py::test_create_task_run_records_runner_heartbeat_and_lease`, `tests/test_task_runs.py::test_refresh_task_run_heartbeat_extends_active_lease` |
| Stale TaskRun detection | `tests/test_task_runs.py::test_mark_stale_task_runs_marks_expired_active_run_honestly` |
| Active lock remains held | `tests/test_scheduler.py::test_stale_target_lock_cleanup_does_not_release_active_owner` |
| Stale lock cleanup | `tests/test_scheduler.py::test_stale_target_lock_cleanup_releases_only_stale_owner` |
| Pre-run checkpoint | `tests/test_task_runs.py::test_write_task_run_records_pre_run_checkpoint_for_demo_target`, `tests/test_task_runs.py::test_external_write_task_run_checkpoint_uses_target_registry_policy` |
| Retry idempotency | `tests/test_task_runs.py::test_retry_failed_or_interrupted_run_creates_new_history_row` |
| Unsafe retry blocking | `tests/test_task_runs.py::test_retry_blocks_external_target_dirty_worktree_outside_checkpoint` |
| Failed dependency blocking | `tests/test_scheduler.py::test_dependency_failure_blocks_downstream_task_with_visible_metadata` |
| Downstream re-evaluation after fallback | `tests/test_scheduler.py::test_completed_fallback_unblocks_downstream_dependency` |
| Preview/deploy gating | `tests/test_previews.py::test_preview_rejects_failed_dependency_prerequisite`, `tests/test_deployments.py::test_mock_deploy_rejects_failed_dependency_prerequisite` |
| File overlap conflict | `tests/test_scheduler.py::test_file_overlap_conflict_blocks_unsequenced_write_task` |
| Dirty worktree conflict | `tests/test_scheduler.py::test_dirty_worktree_conflict_blocks_external_write_task` |
| Contract drift conflict | `tests/test_scheduler.py::test_contract_drift_conflict_blocks_stale_contract_task` |
| Recovery actions | `tests/test_recovery.py` |

## Baseline Preservation

- P6 mini CRM and full-stack paths remain covered by the existing planning,
  task-run, diff, preview, review, and deploy tests.
- P7 Target Registry and permissioned execution remain covered by target
  registry, review, planning, and task-run tests.
- P8 dependency scheduling and target locks remain covered by scheduler tests.
- P9 external workspace registration, analysis, task execution, evidence, and
  review remain covered by external workspace/evidence/review tests.

## Caveats

- Recovery actions are service-level and test/API ready; P10 does not add new
  UI buttons for every recovery action.
- P10 does not add a distributed worker cluster or durable worker table.
- P10 does not add Docker isolation, production deploy, provider marketplace,
  PR creation, or automatic Git conflict merge.
- Retry from checkpoint performs safety checks and creates a traceable retry;
  it does not destructively reset files.
- File-overlap conflict detection is intentionally bounded to unsequenced
  write tasks so dependency-ordered P8/P9 pipelines remain usable.

## Validation

| Command | Result |
|---|---|
| Targeted P10 rehearsal tests | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `pnpm demo:api:test` | Pass through `pnpm test` |
| `git diff --check` | Pass |
| `openspec validate agenthub-p10-scheduler-robustness-conflict-recovery --strict` | Pass |

Recommended freeze tag:
`p10-scheduler-robustness-conflict-recovery-freeze`.
