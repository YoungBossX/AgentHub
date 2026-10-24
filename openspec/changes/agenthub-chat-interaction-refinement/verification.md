# Chat interaction refinement verification

2026-10-24 implementation verification, local `dev`, based on `52e90fa`.
The original implementation was uncommitted; subsequent source delivery is
recorded below, without changing the historical verification limits.

## Source delivery

The user authorized committing and pushing this task to `dev`, excluding build
outputs. Exactly 23 intended source/test/script/specification/document files were
audited, with no build output, image, dependency, cache, database, local credential
configuration or logs. Fresh Web **377 passed**, root `pnpm check`, strict OpenSpec,
browser-script syntax and whitespace checks passed. The first root check invoked
unavailable WSL bash; selecting the existing Git Bash in this command's PATH
resolved that environment issue without changing source or installing software.

Delivery audit/logs and the exact-commit GitHub CI receipt are kept outside the
checkout at `E:/Docker/AgentHub/chat-delivery-20261024-01`. CI must be checked for
the pushed SHA; previous successful runs do not establish this commit's result.

## CI follow-up

The first pushed commit `0de284c0dd3384aee6c2aed815e5e1254fcff20e` failed
[CI run 40050956905](https://github.com/YoungBossX/AgentHub/actions/runs/40050956905)
only at `test_execute_task_run_preserves_replacement_supervisor_generation[False]`:
the one-second `create_started` synchronization wait timed out, with the event
already set in the traceback. Backend totals were **1 failed, 2863 passed,
65 skipped**; root checks had passed.

An external diagnostic plugin delays the real synchronous request preflight by
1.1 seconds. The unchanged test passed **2/2** without the delay and reproduced
the same startup timeout in **2/2** delayed cases. Giving only this test's two
startup barriers a ten-second bound passed **2/2** with the identical delay.
Events still control the race; every ownership, stale-write rejection,
replacement-generation survival and cleanup assertion is retained. There is no
runtime timeout, lease-policy or product-source change.

Normal related supervisor/execution-lease regressions: **16 passed**.
`pnpm check:api` passed. Red/green logs and the original CI log are retained in
the delivery directory; the diagnostic plugin and test DBs are excluded from
Git. A new pushed commit must complete its own CI before claiming delivery is
green; its SHA/run/result receipt is recorded in that external directory.

## Requirement checks

| Requirement | Implemented and verified |
| --- | --- |
| Chinese IME Enter | Composition start/end state, native isComposing and keyCode 229 prevent submission. The 499/500ms boundary, ordinary Enter and Shift+Enter are covered. Candidate-confirmation events are not canceled. |
| Reading intent | Follow threshold 40px; immediate wheel/touch/scrollbar/navigation-key pause; actual bottom or explicit jump resumes. Jump is visible strictly beyond 120px without requiring unread messages. Existing unread deduplication, history/latest and session/view tests remain. |
| Single outline layer | Containers use dimensionless inset shadows; nested actions have no border/ring. Neutral hover fills preserve primary/inverted foreground-background pairs and visible forced-colors keyboard focus. A pre-existing generic input-focus specificity conflict was reproduced and fixed so the composer textarea has no separate focus shadow. |
| Radius geometry | Composer 24 = inner 8 + padding 16; context 20 = inner 8 + padding 12; attachment-list 16 = inner 8 + padding 8. Browser checks compare computed values rather than class names. |
| Pane interactions | Actual pointer capture and transparent shield hit-testing; global Escape restores without persistence; result separator double-click produces equal chat/result columns excluding sidebar. Above 82% on release collapses through existing inspector preference state and retains usable reopen width. Exactly 82%, canceled drags, desktop resize, keyboard-during-drag and wide persisted halves are covered. |
| Filenames | Shared attachment and Diff labels shrink their prefix with CSS ellipsis and preserve compound extensions, grapheme-safe tails, full titles/accessibility and original download values. A CJK label below 24 characters still supports width-based ellipsis. |

## Fresh verification

Evidence: `E:\Docker\AgentHub\chat-interactions-20261024-01`.

- Initial focused test run: **13 failed / 23 passed**, reproducing missing
  behaviors and changed jump-label expectations before implementation.
- Additional CJK and review reproductions were observed failing before fixes;
  the original logs remain under `cjk-red.log`, `review-red.log` and
  `offline-browser-05-red.log`.
- `pnpm test:web`: **377 passed**, 50 files, final reviewed version in
  `all-web-tests-reviewed.log`.
- `pnpm check:web`: ESLint/TypeScript passed, `web-check-reviewed.log`.
- `pnpm --filter @agenthub/web build`: production build passed,
  `build-reviewed.log`.
- `node scripts/chat-interactions-browser-check.mjs`: **11 actual Edge checks**
  passed, `offline-browser-06/result.json`; zero page errors and mutation
  requests. Covers synthetic IME events, 40/41px and 120/121px boundaries,
  real wheel input, iframe shielding, Escape, equal split, collapse/reopen,
  1440/1024/390px light/dark, computed focus/geometry, hover contrast, filename
  clipping, no horizontal overflow and forced-colors keyboard focus.
- Final desktop/mobile screenshots inspected. Strict OpenSpec, three changed
  browser-script syntax checks and `git diff --check` passed.

## Review and validation limits

Independent read-only review reproduced canceled-drag keyboard persistence,
stale drag geometry after a desktop resize, and unreadable inverse-button hover.
Fixes ignore keyboard sizing while dragging, cancel on container-width changes
and scope neutral hover feedback. Focused regressions and final browser checks
pass; no other supported issue was reported. The reviewer did not mutate source.

Automatic approval review rejected the frontend service-launch command with no
specific reason; it was not executed. We did not retry that service launch.
Browser verification instead bundles the actual React components and current
production CSS into an explicitly labeled offline fixture, with no HTTP server
or product data. This is component/browser evidence, not a complete server-backed
workbench smoke test, real Provider run or an OS IME candidate-window test.

One temporary API process used only a copied UI fixture DB with lifecycle/workers
disabled and a read-only request wrapper; it was stopped. No listeners remain on
the temporary ports. Production data, adapters, CLI permissions, saved messages
and historic measurements are unchanged. No dependencies installed, commits,
pushes or screenshot assets added to the repository. Earlier failed fixture
attempts and test logs remain in their E-drive directories.
