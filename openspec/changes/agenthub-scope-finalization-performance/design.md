# Design

Retain capture_worktree_scope_snapshot unchanged: ordinary files, staged/tree
layers, protected HMAC, repeated independent captures, case semantics, Windows
streams/reparse points, descriptor and hardlink checks all remain mandatory.

Split scope persistence into a private shared operation and two entry points.
The existing persist_scope_decision validates supplied passed/rejected decisions
against a fresh capture and rejects mismatches as before. The new
validate_and_persist_task_run_scope takes only a TaskRun ID and computes the
decision inside that operation. It cannot accept a prior decision, snapshot,
guard marker, cache key or a skip-validation flag.

Pin expected metrics and baseline binding before collection. Validate current
target/policy, runtime identity and lock on both sides of collection and again
before persistence. Preserve the lock-held, worker-bound metrics CAS, fallback
CAS and exact-generation finalizer. Return the decision actually authorized
for persistence; a failed CAS cannot return a successful computed decision.
The engine requires both that fresh decision and the durable pass marker before
collecting Diff or reporting output completion. Functional acceptance remains
not_evaluated. Read-only completion is unchanged.

Measure the original and revised API routes with fresh isolated SQLite and
new Session worktrees, explicit ScriptedMock recovery, real file/Diff output,
snapshot counts and concurrent health requests. Report measured wall time and
workload identity separately from historical 45-55s observations under load.
Verify forged/stale supplied decisions, lock/lease/worker/baseline/policy/metrics
changes during validation, no-op/violation/unavailable capture, cancellation,
generation fences and downstream artifact exclusion. Keep previous evidence
and source hashes immutable and update the current project records only after
the focused and complete API checks pass.
