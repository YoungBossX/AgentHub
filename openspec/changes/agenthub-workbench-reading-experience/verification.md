# Verification

2026-10-23, local uncommitted working tree on `dev`, based on
`4a58e7c243ee03b19c846c7e70d8b1b5a7777d59`. No commit or push is authorized.

## Requirement audit

| Approved improvement | Implementation and evidence |
| --- | --- |
| Contrast | Semantic primary foreground in both Agent forms; actual Edge computed contrast 4.981:1 light / 7.335:1 dark. Both ordinary muted tokens on six neutral/accent surfaces meet 4.5:1; raw ratios in browser result.json. |
| Hierarchy | Stage/action and next step remain visible. Routine stage details and history counts use existing Grid disclosures. Failed/blocked/approval reasons remain directly visible; browser checks a failed retry reason. |
| Inspector | Session-keyed auto/manual visibility and expansion; automatic empty pane collapses. Concrete artifact selection reveals it; close survives refresh. Width persistence and keyboard resizing remain unchanged. Hook and actual browser tests cover these actions. |
| Typography | Body 14px, supporting utilities/Markdown at least 12px, small headings 16px, dependency SVG text 12px. Actual light/dark DOM scan includes code header, image description, footnotes and superscript. No downloaded fonts; intermediate weights remain CSS requests mapped by installed static fonts. |
| Reading position | One scroll root follows within 80px, preserves upward reading during append/text/resize and across views. Unique unread IDs and same-ID content feedback; history/latest resume; session notification isolation. Actual browser uses a progress/results footer below messages to catch competing latest anchors. |
| Current/history results | Real TaskRun IDs associate batches, including identical task titles. Current failed/empty runs remain explicit, old outputs default closed, orphan evidence stays historical. Actual document versions 1 and 3 are displayed, without renumbering runs as versions. Existing inspector remains the version viewer. |

## Checks

- Web: **50 files / 357 tests passed**, `web-tests-verified.log`.
- Developer tools: **24 passed**, `tools.log`.
- Actual Edge reading acceptance: **17 checks**, no page errors or mutations,
  `browser-console/result.json`, via `scripts/workbench-reading-browser-check.mjs`.
  The final clean-start run also rejects hydration/React console errors; none occurred.
- Original ten visual rules: **14 browser checks**, `visual-invariants-final/result.json`,
  via existing `scripts/workbench-visual-polish-browser-check.mjs`. Covers themes,
  90ms/30ms append reveal, copy expiry, Grid keyboard/inert, pointer cancel/keyboard,
  focus, reduced motion and forced-colors focus.
- Final `pnpm check`: passed, `check-final.log`, including Web ESLint/TypeScript,
  Python syntax checks and both demo checks.
- `pnpm --filter @agenthub/web build`: passed, `build.log`.
- Strict OpenSpec, browser script syntax and `git diff --check`: passed.

Meaningful initial RED runs are preserved in `red.log` and `review-red.log`.
Independent read-only review found two P2 issues: latest-anchor scrolling and
uncaught manual refresh errors. Tests first reproduced both, then passed. The
reviewer independently rechecked latest/footer following, refresh failure/recovery
and late failure after session switching; no remaining confirmed P1/P2 findings.
Actual-browser testing additionally caught nested footnote sizing and stale error
display after recovery; both were corrected and the final browser suite passed.
Early browser failures caused by disclosure transition timing and Playwright's
automatic scrolling of an offscreen refresh button remain recorded as harness
findings; the final harness invokes the same refresh handler without that
automation-induced scroll.
One hydration warning appeared in the long-lived hot-reload server output during
development. It did not reproduce after a clean development-server restart with
explicit hydration/React console monitoring. An optional production-server start
was rejected by automatic approval policy; no production serving claim is made.
The production build passed, and final full-page acceptance used the permitted
development entry point.

## Evidence and limits

All new fixture data, logs, browser profiles and screenshots are under
`E:\Docker\AgentHub\workbench-reading-20261023-01`. The fixture database is a
SQLite backup copy of the prior isolated UI fixture; product records and previous
benchmark results were not used or changed. Browser routes allow only local
GET/OPTIONS; rich task/run/document/message data are labeled read-only response
fixtures. No Provider calls, real code edits, new Diff generation, preview service
start, clipboard changes, dependency installation or database migration were
performed. UI checks do not become real-task success rates or resume metrics.

Screenshots: `browser-console/desktop-results-light.png`,
`desktop-results-dark.png`, `desktop-conversation-light.png`,
`desktop-conversation-dark.png`, `1024-{light,dark}.png`, `390-{light,dark}.png`,
`agent-settings-{light,dark}.png`. Build outputs remain ignored and external
screenshots/logs/databases are not repository source.
