# Current-version local readiness

## Why
The current Windows host excludes TCP 7963–8062. The local launcher collapses
EACCES and EADDRINUSE into one message, so its default 8000 failure is misleading.
The execution coordinator also retains several separable responsibilities, and
the latest UI/refactors have no fresh same-source real-task cohort.

## What Changes
- Diagnose unavailable loopback ports accurately and suggest an actually probed
  alternative without changing defaults, stopping listeners or changing OS settings.
- Extract cohesive execution-coordinator responsibilities while retaining current
  lifecycle, ownership, scope, provider and artifact behavior.
- Freeze the final implementation and run ten Chinese real-API workflows: two
  repetitions of each existing scenario. Preserve first outcomes, retries, unknown
  usage and all previous cohorts; no scripted fallback counted as native success.
- Reconcile the reproducible demonstration instructions and evidence index with
  this cohort; keep the README/index.html framework and existing historical data.

## Scope
Local single-user workbench only. No new adapters, database migrations, dependencies,
deployment, automatic port switching, runtime permission changes, commits or pushes.
All new runtime data, test temporary files and evidence live under E:/Docker.
