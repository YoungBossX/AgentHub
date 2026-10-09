# Design

Resolve DEMO_FRONTEND_TARGET_ID through get_target, then derive safeTarget and
planned source files from the registered target's existing allowed path. Persist
targetId and safeTarget on both frontend and QA task specs before generating
taskGraph/planDraft and saving Tasks. Keep the synthetic orchestrator planning
step read-only and preserve the sequential dependencies and expected artifacts.

The explicit demo request remains bound to the built-in Vite React demo target;
message-supplied paths cannot choose or widen it. Do not add a scheduler fallback
or weaken scope validation. Existing missing/invalid target failures stay closed.

Regression evidence uses an isolated temporary Git repository and SQLite test
database, HTTP message planning, and the actual ScriptedMock adapter and execution
engine. No model, healthy Preview or complete browser workflow success is claimed.
The independently observed Windows dependency-link blocker remains a next task.
