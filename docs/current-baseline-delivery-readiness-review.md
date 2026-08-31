# Current baseline delivery-readiness review

**Date:** 2026-08-31

**OpenSpec:** `agenthub-current-baseline-delivery-readiness`

**Machine evidence:**
[`current-baseline-delivery-readiness-evidence.json`](current-baseline-delivery-readiness-evidence.json)

## Decision

The current local candidate is ready to enter explicit staging, review, commit,
and push. A registered external Vite target was planned through the public
message path, scheduled, executed by the local Codex CLI, scope-validated, and
persisted as a completed TaskRun with a one-file Diff and Review. The Preview
became healthy through the public API and was then deliberately stopped. The
cleanup audit later found that the pre-fix Windows stop path had left its Vite
and esbuild descendants alive; they were terminated and the target was removed.

The complete repository gates and exact candidate-file audit passed after the
rehearsal. This is a local delivery-readiness decision only: no commit or push
is claimed, and the remote `dev` and `main` refs still point to `d2b8f1b`.

## Rehearsal identity

| Field | Value |
|---|---|
| External target | `external-delivery-readiness-20260831-221051` |
| External Git base | `e1db640abf93431b47fdf1d0fb4553d4549477f3` |
| Session | `22966723-193a-4bd9-b2ca-f1fd8e4c8bcc` |
| Memory snapshot | `c563b2e6-8756-4ccc-9143-f8f78208dbae` |
| Request SHA-256 | `02e115beb967b161e019968ae70e7ef55293dfd2ef6247028e42bc8d6addf6a4` |
| Successful instruction SHA-256 | `23580d1ae4342abcfe4f540c335ee87b33efe81aac774a7623412e93faacdbe6` |
| Successful TaskRun | `dd120d84-11ad-4d4f-91f8-799b84aa1970` |
| Codex adapter run | `codex-a814579f-0fa2-457b-bb4f-d29924c1dfca` |
| Diff / artifact | `998db848-ea36-48ae-aaee-e80ee7e20540` / `84a6fd68-ad4c-4d6e-8038-b28262a04917` |
| Patch SHA-256 | `d78ecf6bd58995c25e58acd6db5d8c128ee0140dfbcc0e98673a9c6eb5ee1519` |
| Review / artifact | `2f505486-a0c2-4b8c-81d3-71d51c434e78` / `2f45a2ca-34df-4826-92fb-3e1655940928` |
| Preview / artifact | `a98c9cef-6864-48e7-a5f1-ae93745365c6` / `707c5206-9662-49d1-b8e8-555cc96a36e8` |

All six active P18c MemoryItem IDs and their content hashes are retained in the
machine evidence. The successful request used the same snapshot recorded on the
TaskRun; its `contextPackHash` is
`26afffd91f3297f11b6dc10edf1ce86771b311343be4bc659e3f283c35bac6c4`.

## Failures retained rather than rewritten

The first run, `da6532c4-e7b2-48fe-ad73-0d43079f3895`, failed before provider
launch with `CODEX_GUARDRAIL_BLOCKED`. The health probe resolved a genuine
Windows `codex.exe`, while the command guard accepted only the extensionless
basename `codex`. The narrow correction accepts exact `codex` and `codex.exe`
basenames; `codex-wrapper.exe` remains blocked.

After the real retry completed, the first Preview attempt exposed a second
Windows launcher mismatch: portable evidence correctly used `pnpm dev`, but
`Popen` did not resolve the `.cmd` shim. The launch layer now resolves only an
exact Windows `pnpm` token to `pnpm.cmd`; the recorded portable command, target
root, sanitized environment, health check, and lifecycle remain unchanged.

The final cleanup exposed a third Windows boundary in that lifecycle. Stopping
the `pnpm.cmd` wrapper alone persisted `stopped` while Vite and esbuild remained
alive and held the external target. The stop path now terminates the tracked
Windows PID tree, waits for it, closes and removes its runner-owned temporary
log, and retains the existing direct terminate/wait/kill path elsewhere. A
fresh real Vite smoke became healthy and then left zero target-port processes
and no temporary log after stop.

## Successful workflow evidence

- Provider resolution selected `local-codex-cli` / `codex` with
  `fallbackPolicy=explicit_only`; health probe reported the CLI available.
- The provider stream persisted `thread.started`, `turn.started`, and
  `turn.completed`; the TaskRun then passed final scope validation and ended
  `completed`.
- Exact changed-files: only `src/App.tsx`, with one addition and one deletion.
- `pnpm check` and `pnpm build` both exited 0 and were persisted as command
  evidence after the automatic Review was created.
- The automatic Review remains `warning` because it is idempotent and recorded
  the then-missing command evidence. Its two findings are therefore retained,
  not deleted or rewritten; the later passing evidence IDs are separately
  traceable in the machine record.
- Preview event sequence 68 records `healthStatus=healthy`; the same Preview row
  was subsequently marked stopped. Its pre-fix descendants are explicitly
  recorded in machine evidence rather than hidden; cleanup terminated them and
  the corrected stop path passed a separate real Vite lifecycle smoke.

The external dependency installation occurred after adapter execution in the
explicit setup/validation phase. It did not enter the TaskRun Diff and does not
relax the rule against dependency installation during agent execution.

## Evidence boundary

The historical P18c decoder-recovered Diff remains historical and failed-run
evidence. Only the new `dd120d84-...` TaskRun is claimed as a current successful
real-provider run. The Preview is a local Vite smoke; no production deployment,
cloud provider, multi-user workflow, or broader platform scope is claimed.

## Repository gates and candidate audit

- Web: 13 files / 102 tests passed.
- API: 1,153 passed / 1 skipped; demo-api: 5 passed.
- `pnpm check` passed for Web, API, demo, and demo-api.
- All 35 OpenSpec changes passed strict validation.
- 168 Markdown files had zero missing relative links; 433 selected project text
  files decoded as strict UTF-8.
- Tracked and untracked candidate whitespace checks passed after removing three
  redundant end-of-file blank lines from existing untracked OpenSpec files.
- The candidate set contains no database, environment, log, cache, dependency,
  build-output, or session-worktree artifacts.
