# Built-in FastAPI validation acceptance

2026-10-15: `agenthub-backend-versioned-validation` 1.1 completed locally.

## Implementation

- The built-in `demo-backend` now selects `fastapi-contract-v1` during owned
  finalization, before existing Diff/review terminal fencing. Unknown/external
  targets are not silently enabled.
- Hash bounded regular target files and installed Python/dependency/harness policy.
  Copy into a disposable directory; execute fixed syntax and real in-process ASGI
  checks. Target tests, pytest config and package scripts never execute.
- API coverage: health, seed list/schema, create/persist, malformed/missing/long
  fields with no state mutation, duplicate rejection, local CORS/external rejection,
  and OpenAPI. No new endpoint, database or full application acceptance is claimed.
- Require complete structured results plus successful process exit; a zero-exit
  target without checks does not pass. Source/copy/policy changes produce stale
  evidence. Same-run/generation/profile and immutable event identity are required.
- Use isolated installed Python, sanitized environment and temporary home/data.
  Audit guards deny target sockets, subprocesses/native loaders, host file access
  and copied source mutation. Windows asyncio's trusted wake-up socket pair is
  initialized before target loading. These controls are not an OS sandbox for
  actively hostile Python code.
- QA requires check/test, with backend build explicitly not applicable. Missing
  native model review remains incomplete, and an API failure blocks even a passed
  model. UI shows actual backend coverage and freshness rather than Vite/browser
  claims. Historical assessment snapshots are not rewritten.

## Executed evidence

- API validation/requirements/layered QA/finalizer responsiveness/deployment:
  **144 passed**, 132.06 seconds. Additional real backend timeout and missing
  installed dependency tests: **2 passed**. New backend module has **41 tests**
  across these executions; older exploratory 77-pass run overlaps and is not added.
- Actual backend toolchain positive and syntax/HTTP failures executed in installed
  Python. Negative controls include missing exact coverage, early exit zero,
  socket TCP/UDP/bind, subprocess/native load, host read/write, protected files,
  links, copy/source/policy changes, cancellation and ownership loss, restart.
- Production lifecycle test: explicitly test-only writer makes a real file change
  in a fresh Git repository, then actual scope/Diff/fixed Python/ASGI validation
  and persistent rule review execute. QA remains incomplete without model review;
  API serialization and reopened SQLite preserve the same evidence. This is not
  a real Codex/Claude coding or model-review run.
- Web **298 passed / 38 files**; root `pnpm check`, local launcher/path suite
  **19 passed**, strict OpenSpec and whitespace checks passed. Existing installed
  Git Bash was used for root check wrappers. No dependencies were installed.
- Additional native/external review, group summary and artifact-scope regressions:
  **94 passed**, 114.98 seconds. Together with the 144+2 batch above, the relevant
  backend regressions total **240 passed** without counting the earlier overlapping
  exploratory run.

This is local Windows validation. Full API suite and fresh remote Linux CI were
not run in this task; no commit/push or new real Provider execution is claimed.
