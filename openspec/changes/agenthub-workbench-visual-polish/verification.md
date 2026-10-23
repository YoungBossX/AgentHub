# Verification — 2026-10-23

Baseline: dev at f52cdff56a6561b96976f0637ef3ec2884455c97. Changes were uncommitted
at the implementation acceptance recorded below. The user subsequently authorized
source-only publication to dev and verification of that exact commit's GitHub CI.
Evidence root: `E:\Docker\AgentHub\ui-polish-20261023-01`.

| User rule | Implementation and evidence |
| --- | --- |
| Borderless hierarchy | Exact supplied warm palettes; transparent neutral borders, subtle fills; actual light/dark desktop screenshots |
| Input focus | Composer/search wrapper and settings inputs use two shadows; browser verifies 1px/4px rings and no normal outline |
| Dark weights -40 | Theme weight offset, Markdown and SVG headings; actual browser body 400/360 and heading 600/560 |
| Text reveal | Grapheme-safe appended prose, 90ms, blur 6px, requested easing and 30ms stagger; repeated append animationstart verified in browser |
| Inline icons | Global Lucide alignment -0.125em, verified computed alignment ratio |
| Stable digits | Inherited tabular-nums, verified computed style |
| Grid collapse | Shared 0fr/1fr Disclosure, keyboard trigger, aria relationships and inert closed content; lazy long-message regression passes |
| Pretty wrapping | Paragraph/list/description wrapping, verified computed pretty style |
| Spring personality | Analytic mass-1 1200/80 and 380/18 CSS curves; monotonic/overshoot tests; widths still follow pointer directly |
| Self-expiring copy | 2500ms after actual clipboard promise resolves, fade/restore and repeat timer; content/unmount/promise regressions pass |

## Commands and results

- `pnpm --filter @agenthub/web test --maxWorkers=1 --no-cache`: 47 files, 345 passed,
  zero failures. `web-final.log` records the complete run.
- `pnpm test:local`: 24 passed, zero failures. `tools.log`.
- `pnpm check`: success, includes Web lint/types, API syntax and demo checks. `check.log`.
- `pnpm --filter @agenthub/web build`: production build and TypeScript success. `build.log`.
- `pnpm exec openspec validate agenthub-workbench-visual-polish --strict --no-interactive`: valid.
- `git diff --check` and syntax checks for the three changed browser scripts: success.
- `scripts/workbench-visual-polish-browser-check.mjs`: 14 checks, zero page errors,
  actual installed Edge 155.0.4283.62. `browser-final/result.json` and screenshots.

Browser harness requires an operator-prepared fixture session containing an ordinary
user/orchestrator exchange, a Markdown link and at least one task. Set
`AGENTHUB_UI_SESSION_ID`, `AGENTHUB_UI_ORIGIN`, `AGENTHUB_UI_API_ORIGIN` and
absolute external `AGENTHUB_UI_OUTPUT`; run with `node scripts/workbench-visual-polish-browser-check.mjs`.
It rejects API writes, external requests and in-checkout screenshot directories.

## Review and regression evidence

An independent read-only reviewer found three issues, all fixed:

- Copy A → B → A could resurrect success or permanently disable a pending button.
  Failing tests in `copy-pending-red.log`/`review-red.log`, passing in `review-green.log`
  and the final full suite. Content transitions now clear state and invalidate promises.
- Successive appends reused a finished animation node. Failing DOM-identity test,
  then passing test and actual consecutive browser animationstart events. Source
  offsets now identify fresh animation nodes.
- Markdown-specific focus styling suppressed the forced-colors outline. Actual
  Edge repro recorded `outline:none` and `shadow:none`; after removing that override,
  focused links have a visible system outline. `forced-colors-{red,green}.log`.

## Boundaries

- Screenshots use a fresh E-drive UI fixture database and read-only requests.
  Appended text uses intercepted read responses; clipboard is stubbed to preserve
  the operator's OS clipboard. This is UI acceptance, not a new real Provider run.
- No product database, credentials, adapters, permissions or backend source changed.
  API full regression and real-model tasks were not rerun for this frontend change.
- Static system fonts can map intermediate numeric weights to installed faces.
  No font downloads or new dependencies were introduced.
- Large text batches animate at most 32 graphemes. Remaining content is immediately
  available; no typing timer delays the data. Reduced motion disables animations.
- Native platform forced-colors focus outlines intentionally replace shadows when
  the OS suppresses shadows. Normal light/dark input focus remains outline-free.
- Browser control integration could not initialize locally; acceptance used the
  project's existing Playwright package and installed Edge, without downloads.
- Existing evidence and results are preserved. The UI implementation acceptance
  did not commit or push; the subsequent authorized source publication has separate
  evidence under `E:\Docker\AgentHub\publish-ui-20261023-01`.
