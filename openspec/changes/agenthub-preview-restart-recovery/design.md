# Design

Extend process diagnostics with a tracked flag. SubprocessPreviewRunner only
tracks Popen objects created by itself. After restart, unknown persisted PIDs
are untracked, not proven dead. Do not stop them or trust their HTTP responses.
Mark the Preview unavailable with a clear ownership-lost reason and retain its
artifact history. Runtime exits use runtime wording instead of startup wording.

Protect runner lifecycle with a lock and a closed flag. Graceful API shutdown
closes its owned process trees and log handles; a start racing with close either
registers before cleanup or is rejected. A subsequent lifespan can use a fresh
runner. No PID-only reattachment or killing unknown host processes.

Refresh/restart uses freshly read Preview health, rather than the stale selected
artifact. Reuse a healthy preview when available; otherwise an explicit click
launches a new Preview via existing target/scope/integration gates. Failed or
stopped cards say restart, preserve old records and disable opening/deployment.
No automatic model reexecution or destructive file mutation is involved.

Default OS-assigned preview ports must be at least 16384, above the standard
browser restricted-port list. Bind random high candidates directly, retrying
occupied/unavailable candidates within a fixed bound and failing clearly on
exhaustion; the host ephemeral range can stay below the minimum. A Windows allocation of 1719 reproduced
an HTTP-healthy but Chromium-blocked iframe during real recovery acceptance.
Keep the explicit Preview selected while independently fetched artifact batches
arrive; partial lists must not redirect the inspector to another artifact.

Verify untracked vs exited diagnostics, no signals/HTTP trust for untracked PIDs,
single-event persistence, lifecycle close/idempotence/race and source/lease
boundaries. Verify actual Vite startup, graceful API shutdown, restart ownership
loss, one-click browser recovery and matching source hashes without new TaskRuns.
Run relevant tests, full API/Web and static checks. Document local recovery.
