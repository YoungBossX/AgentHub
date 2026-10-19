## 1. Fixed validation containers: phase 1

Earlier 2026-10-19 focused follow-up (before the real Docker qualification):
- [x] F1 Reject differently spelled directory aliases in snapshots and exports
  before filesystem writes; verify nested/order/file-parent regressions.
- [x] F2 Add synchronized running cancellation and killed-worker recovery tests,
  prepare corresponding opt-in real Docker probes and run the native regression suite.
  This does not complete image preparation or real Docker qualification below.

- [x] 1.1 Draft and self-review the focused design and implementation plan; validate
  OpenSpec, links, source boundaries and exact documentation scope. This checkbox
  covers documentation only and does not approve implementation.
- [x] 1.2 Implement pure source/policy interfaces, native compatibility and a
  read-only container doctor; verify native operation without Docker and no
  database/daemon mutation.
- [x] 1.3 Prepare two trusted images, pinned dependency/recipe inputs and an explicit
  operator build receipt; verify minimal build context and immutable local image IDs.
- [x] 1.4 Implement bounded Docker runtime, per-daemon capacity, ownership journal,
  cancellation/cleanup and strict artifact export; verify simulated failure windows.
- [x] 1.5 Connect TaskRun validation, execution-bound receipts, currentness and small
  QA environment labels; preserve native browser checks, adapters and existing data.
- [x] 1.6 Qualify both profiles with real Docker positive/negative and restart tests,
  existing adapter/native/data regressions and an actual write/Diff/native-preview
  flow; retain exact-environment evidence and verify the forced entrypoint used
  by the focused opt-in CI workflow locally. Remote delivery remains separately authorized.

The user subsequently approved Native sequential implementation and deferred
environment preparation. Tasks 1.2, 1.4 and 1.5 are locally verified. Task 1.3
code is unit-tested; the user has since installed Docker and authorized preparation
under E:/Docker. Both images have now been built and inspected through the fixed
operator entrypoint; complete receipt is E:/Docker/AgentHub/images-20261019-07/images.json.
Doctor reports metadata_ready; this does not qualify isolation. The separate actual
sandbox:verify now passes18 tests with zero skips/failures. Final frozen native
API regression passes2714/19 environment skips, with zero failures/errors;1.6 is locally complete.
Web333, local24, demo-api5, control3, root checks and strict validation also pass.
The first native run's3 temporary fixture/process failures, exact3-case success
and subsequent complete successful rerun are retained separately in verification.
The manual GitHub workflow is implemented, but has not been triggered remotely;
commit/push and corresponding-SHA CI require separate user authorization under the plan.
No host dependency installation, product data changes, commit or push is authorized. See [design.md](design.md) and
[implementation plan](../../../docs/superpowers/plans/2026-10-18-container-validation.md).

1.1 verification: strict OpenSpec and whitespace checks passed; six focused UTF-8
documents with balanced fences, no placeholders and eight valid relative links.
The ten-file change contains only documentation and its exact ignore whitelist;
runtime/Adapter/model/migration sources remain at baseline. See [verification.md](verification.md).
