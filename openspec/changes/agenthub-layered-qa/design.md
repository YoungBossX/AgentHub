# Evidence before acceptance

Persist one versioned QA snapshot with each new Review artifact and ready event.
Run deterministic target/path and existing review rules for both scripted and
native reports. A model verdict cannot override a failed rule. TaskRun completed
still means execution finished; it is not a QA acceptance verdict.

Keep each command kind separate. Only same-run, same-target, configured-command
evidence recorded by report creation is included. Preserve failures even if
another command passed. Existing command receipts lack source-version binding;
label their outcomes recorded results, never functional acceptance. Missing
tests/model mean incomplete, failed rules/model/commands mean blocked. Do not
fabricate a full acceptance state. This task does not introduce a test runner.

Reports are immutable snapshots: later evidence does not retrospectively bless
an earlier report; other runs' receipts are not borrowed. Legacy reports without
the snapshot show evidence unknown, and retain their historical content. Existing
native failure handling must continue to fail without a scripted substitution.

Render the three layers and limitations using the existing UI. Model review is
selected through the existing explicit read-only Agent configuration. Surface QA
snapshot information in task evidence and group-summary inputs without changing
the existing non-blocking review execution/dependency semantics.

The existing local staging gate additionally refuses a blocked QA snapshot, even
when the individual model verdict passed. Incomplete evidence is not labelled
accepted and does not disable the explicitly local preview/mock demo path.
