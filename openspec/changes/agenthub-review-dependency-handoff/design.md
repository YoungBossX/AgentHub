# Design

Reuse generated advisory reports to satisfy the pending review/qa_review tasks
of contract_first_v1, llm_v1, deterministic_login_v1 and dynamic_manager_v1.
Do not mark tasks with existing TaskRuns complete via this synthetic path.

For each declared dependency, verify a Task in the same product Session, its latest
TaskRun is completed, and a stored Review references a Diff artifact of that run.
Keep scheduler dependency/integration readiness as a required check. Persist
reviewSatisfaction with task/run/review/diff identities, adapter and report status.
Warning/failed reports are still completed reports under the existing advisory
policy; never turn their verdict into passed or claim real QA/provider execution.
Reconcile the same pending review tasks before new user-message planning, allowing
older persisted matching reports to satisfy omitted QA steps without a migration
or changes to completed TaskRun evidence. Read-only requests do not reconcile.

Include dynamic_manager_v1 in the existing bounded coding-task continuation path,
still requiring autoStart and scheduler readiness. For terminal commit fencing,
perform validation reads under db.no_autoflush so expired parent lookups cannot
flush a completed state before validating its collecting_diff transition history.
Retain all durable identity, lock, queue, lease and supervisor generation checks.

Use isolated real Git/SQLite fixtures. Send the login HTTP message, execute the
frontend task, check QA closure. Send an ordinary button follow-up HTTP message
through normal planning/autostart and execute with the production dispatcher,
redirecting only its database entry point to the fixture. Verify source output,
second run gates, report references and persisted API task state. No manual
follow-up Task or fake review output. Browser/healthy Preview is separate acceptance.
Exercise follow-ups sent both before and after login execution finishes.
