# Design

Persist autoStart and groupAssignment.execution on every newly validated group.
The request context may explicitly select groupExecution=manual. Do not rewrite
existing plans. Use the existing scheduler, TaskRun factory, Session Queue,
Target Lock, provider capacity, frozen custom profile and execution fences.

Reconcile ready automatic group tasks before dispatcher claims, not by executing
a downstream adapter recursively while the upstream still owns provider
capacity. Writers remain serial; every selected reviewer gets its own read-only
TaskRun and report. Generated writer advisory reports cannot satisfy it.

Serialize initial creation for automatic group tasks with the existing SQLite
Session writer lock and recheck TaskRun history under that lock. Concurrent
dispatchers and manual start cannot create duplicate initial attempts. Any
existing failed/interrupted attempt requires the existing explicit retry flow.
Preparation failures disable that task's automatic start and persist an honest
coordinator diagnostic; the user can correct configuration and start manually.

A bounded local service loop wakes automatic groups after restart or a released
cross-Session target lock. It uses the same dispatcher and stale-run recovery,
never resurrects terminal runs or authorizes historical manual plans. Shutdown
cancels the loop; existing leases/recovery retain interruption semantics.

Validate real file writes and separately executed read-only reviews in disposable
Git/SQLite fixtures, failure/retry, provider capacity, duplicate creation,
manual/history compatibility, startup recovery, and local browser/provider smoke.

Native provider smoke exposed two boundary issues: competing dispatchers must
skip a live claimed queued run before mutating its frozen scheduler/queue snapshot;
a native review may wrap its sole JSON object in a whole-output JSON code fence.
Accept that bounded presentation wrapper while retaining all duplicate-key,
binding, full Read, file-version, judgment and raw-output hash checks. Prose,
multiple objects and partial extraction remain invalid.
