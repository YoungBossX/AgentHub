# Reproducible external task benchmark

## Why
The project has bounded historical provider rehearsals, but lacks a reusable multi-case functional benchmark with frozen inputs, independent acceptance checks, and honest failed-attempt evidence suitable for a personal project.

## What Changes
- Add three small, synthetic external Vite React task fixtures: title normalization, invoice discount calculation, and catalog search.
- Create fresh external Git targets and a separate SQLite database per run; use existing registration, snapshot, TaskRun, worker, scope, Diff and Review services.
- Keep acceptance evaluators outside adapter target roots and hash all inputs. Record failing baseline checks before any provider execution.
- Add a prepare-only mode and an explicit live Codex mode with no automatic fallback. Record attempts, current-source identity, task/run/snapshot/receipt/diff evidence, post-checks and bounded aggregate results.
- Exercise a small live case first, then run the full suite when the provider is available; retain blocked/failed attempts instead of overwriting them.

## Impact
One development/evaluation task, not a new production adapter or endpoint. No dependencies, migrations, broader runtime permissions, automatic deployment, Skill/MCP, or production claims. These fixtures do not represent general coding ability or a production workload; no latency/model-quality improvement is inferred from them.
