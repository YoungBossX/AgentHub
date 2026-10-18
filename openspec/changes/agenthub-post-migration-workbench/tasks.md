## 1. Post-migration workbench acceptance

- [x] 1.1 Recover the two historical preview outputs through existing guards,
  verify a fresh task/execution/Diff/browser-preview chain, align the composer
  controls and padding, and document precise results and limitations after
  relevant Web checks and desktop/narrow-screen visual verification.

Verified: two new healthy recovery outputs and a fresh real Codex run with a
single-file +1/-1 Diff and rendered preview; version-bound check/build/3 smoke
tests and 4 heading contract checks passed. Composer desktop/390px light/dark,
Shift+Enter, send enabled state, equal padding and control alignment verified.
Web checks and 26 targeted component tests passed. Model review was not run;
QA remains incomplete. Initial unsupported/boundary attempts are retained.
See [verification.md](verification.md); no commit/push or remote CI in this task.

- [x] 1.2 Display the legacy default workspace as AgentHub in the product header
  and footer, retain custom names and persisted data, and verify component and
  real-page rendering after the user's explicit naming request.

1.2 verified: legacy-name and custom-name tests included in 29 passing targeted
Web tests (serial retry after resource exhaustion), root checks and real browser
header/footer displaying AgentHub. Database lookup key and custom data unchanged.
