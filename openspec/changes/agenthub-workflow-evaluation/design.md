# Scenario runner and evidence

Create fixed built-in demo source copies with known failing baselines and hash
the complete scenario input, immutable scaffold, expected contracts and harness.
Preparations must prove baseline failure with the actual installed toolchain;
missing tools are unavailable, not evidence of a useful negative baseline.

Live scenarios enter through production natural-language planning/message
dispatch using the isolated database. Drive queued work with an explicitly bound
worker instead of any global production database worker. Preserve planning
identity and fallback details; a missing native Planner must not count as native
planning success. Collect each Task/TaskRun, actual provider events, dependencies,
source hashes, Diff, version-bound checks and immutable-input status.

Freeze independently expected API/DOM checks outside the Agent-writable target.
Test requests and tests themselves never come from model-generated commands.
Check new interfaces independently and retain exact check coverage. Multi-target
success requires both target results plus the specified integration contract;
separate passing frontend/backend tests alone do not prove integration.

Follow-up uses a second persisted message in the same Session. Recovery preserves
the first failed/interrupted attempt and the subsequent retry relationship.
Deliberately injected failures are labeled fault injection, never natural outages.
Bound every scenario/attempt, cancel owned work on exit, and never start preview
or deployment implicitly just to make a benchmark look complete.

Repeat independent fresh scenarios when requested. Denominators include selected
failures/unattempted cases; prepare-only rates are null. Provide per-category
first-attempt/final success, attempt count, elapsed distribution and failure counts.
Unknown token/cost/model fields stay unknown; wall time is not model inference time
and simulated parallel results are not provider acceleration measurements.
