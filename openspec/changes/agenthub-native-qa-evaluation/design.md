# Cohort and review evidence

Use the existing ClaudeCodeAdapter read-only native review contract for QA in
live evaluation. The isolated Agent registry sets coding and QA adapters
explicitly. Collect review artifacts from the actual QA TaskRun, native receipt,
provider event evidence, reviewed source identity, read coverage and layered QA
assessment; require target coverage and binding to the writer/source being
independently checked. Completion/model prose without matching evidence cannot
pass; warnings/failed model assessments remain visible alongside hard checks.
Scripted QA is allowed only as an explicitly labeled test-double path, not live.

Version the new report schema without rewriting historical v1 reports. Freeze
the implementation/harness/dependency declarations and fixture inputs plus the
selected coding/QA modes into a cohort hash. Recheck before/after cases. Source
changes invalidate aggregate native rates for the whole cohort and prevent
remaining execution; retain observed results and selected denominators.

Preserve actual attempt lineage. Permit bounded explicit retries using the
existing failed/interrupted-run retry API, recording whether recovery was
deliberate injection or natural failure. Record actual run start/end duration
when available and separate coding/QA/wall totals; unknown timings stay null.
First-attempt success includes both code and native QA plus independent checks.
Cancellation cleans only owned work and leaves terminal/partial evidence.

First verify gates/aggregation/ownership and existing workflow compatibility.
Then freeze code and execute ten fresh live samples (five categories, two
repetitions). Preserve failures, per-sample/per-target native QA observations,
exact cohort/version and summary denominators in bounded project evidence. Do
not edit runner/policy during the batch or merge results from earlier versions.
