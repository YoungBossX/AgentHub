# Reduce duplicate scope collection during completion

## Why
Actual Windows runs showed a long collecting_diff stage. A real 517-file
worktree snapshot performs about 869,000 fresh path observations; profiling
places most time in filesystem rechecks. The internal completion flow also
computes a transient decision and then repeats a complete snapshot before
persisting that supplied decision.

## What Changes
Add an internal compute-and-persist entry point that accepts only the run ID,
captures one fresh complete snapshot and persists its decision under the
existing metrics, baseline, policy, execution and held-lock fences. Keep the
existing supplied-decision API's fresh revalidation. Use the new entry point
for write completion, preserving all collector checks and output gates.

## Impact
One focused local Agent-core task. No snapshot caching, filtered collection,
skipped protection checks, new adapter, schema change, deployment or dependency.
