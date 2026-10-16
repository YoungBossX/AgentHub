# Workflow evaluation evidence

The bounded JSON summary retains hashes and outcome records from the original
live attempts, including failures. Raw databases, source worktrees and full reports
remain in their separately created temporary output directories; no credentials,
raw prompt bodies or production database are copied here.

Known completed live attempts (2026-10-15):

- `agenthub-workflow-live-4e327ce1-0de1-4d85-9ed3-26daabc82e21`: native plan rejected
  before coding; high-level unsupported-file error only.
- `agenthub-workflow-live-observed-2e24dc68-2540-40d8-bf90-479fd1dc03d7`: original
  error reproduced with actual `app/main.py` paths observed; original provider
  status succeeded but plan validation did not.
- `agenthub-workflow-live-paths-44eb6441-5004-441f-97ce-d3caf9b19444`: after explicit
  path-coordinate guidance, actual native backend workflow passed, 93.046 seconds.
- `agenthub-workflow-live-suite-7c0dadbf-a53c-424d-b04b-b16e4633b9cd`: first full
  batch completed, 4/5 final, 3/5 first-attempt including one explicitly injected
  failure/retry. Natural cases were 3/4. Coordination failed on command scoping.
- `agenthub-workflow-coordinated-fix-8294c0fc-c515-4e14-a99e-9a66369f211b`: after
  command scoping correction, backend passed but frontend hit the caller's
  240-second deadline. Original report captured streaming at cutoff; actual
  SQLite terminal state was interrupted. Report cleanup refresh was subsequently
  added; the old report is not overwritten.
- `agenthub-workflow-coordinated-full-ce71d9d7-24c0-40f1-a9b8-c0b8c1009b76`: fresh
  coordinated attempt under the default full deadline passed in 215.969 seconds,
  with two real coding runs, two clearly scripted QA runs and ten actual desktop/
  390px browser → ASGI create/reload/persistence checks. The first batch's 4/5 is
  unchanged; this is a targeted recheck after a source-policy change.

Inputs/source policies differ across the diagnostic fixes. They are separate
attempt reports, not a single statistically comparable model-performance series.
Provider identity is the observed CLI platform, not an inferred upstream vendor.
