# Design

Use the current source checkout for the control plane, a dedicated SQLite file,
API port 8006 and Web port 3000. Keep the existing port-8000 service intact. Use
ordinary project startup commands and newly allocated Session worktrees. Retain
the canonical worktree/queue/target-lock/scope/nonempty-Diff/Preview boundaries.

Drive visible product controls through an actual browser engine. Browser tooling
may use existing bundled Playwright if the app browser connector cannot initialize.
Record screenshots, source/request/run/artifact identities and healthy Vite output.
Do not substitute old artifacts, fixed Task plans or synthetic health responses.

Send a login-page request, observe planning and role execution, inspect its actual
Diff and generated advisory Review, start the real Vite Preview, iterate by chat,
refresh/reopen and validate rendered changes. Record real Codex/Claude availability
and errors separately from explicit ScriptedMock recovery; mock success is not
real-provider success. Verify the process/result UI, theme and resizing continue
to work. Fix observed defects only after identifying their source and regression.

Browser fallback rehearsal exposed synchronous scope baseline/finalization work
blocking the API event loop for more than the HTTP client's 30-second timeout.
Run these existing guarded synchronous steps in a thread, awaiting each before
the owning coroutine reuses its SQLModel Session. On cancellation, drain the
worker before propagating cancellation or closing/rolling back that Session.
Retain exact supervisor generation reservations, durable commit fences, scope
snapshots, target locks and lease renewal; no weakened or cached scope check.

Audit the supplied three-page PDF against the current local scope. Distinguish
core requirements from its P2 deployment/native-client features and contest-only
submission deliverables. The user's continuing goal authorizes sequential focused
tasks and checkpoint commits/push, keeping local runtime as the current target.
