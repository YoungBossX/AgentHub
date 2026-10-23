# Content and presentation verification

2026-10-23, local `dev` worktree. No commit/push/publication. Previous UI/icon
changes remain uncommitted and are not part of this content-only implementation.

## Requirement audit

| User requirement | Verified result |
| --- | --- |
| Update README content | Current introduction, capability table, architecture/workflow wording, real screenshots, stack/modules and Chinese startup example updated. Existing h2 titles and their order remain identical. |
| Update index content | Refreshed hero, overview, architecture labels, engineering, evidence and module text within existing containers. Generic mock task statuses and fabricated event-log illustration replaced with sourced actual screenshots. |
| Preserve overall framework | Original HTML has hero plus five numbered sections; all section IDs/classes and 27 major layout/card class counts match. The original style block and both script blocks are byte-identical. |
| Show actual project pages | Four 2026-10-23 current-UI screenshots display the 2026-10-20 native contacts run, plus two unchanged historical generated-result images. Existing application metadata provides the brand image. Every picture has a hash and provenance. No fixture task states invented. |
| Avoid false claims | Historical strict40/50, business46/50, complete receipts197/198, separate recovery10/10 match the frozen report. Version and fixed-scenario limits remain explicit. Model review/fixed checks/script fallback/assisted preview/deployment are distinguished. |
| Usable presentation | Local links/anchors exist, all images load, full-resolution links work, 1440/1024/390px both themes have no horizontal overflow. Theme keyboard/persistence and direct file opening work. |
| Deliverable assets | Exact Git-ignore exceptions admit only the nine intentional showcase image/provenance files; sibling images, logs and SQLite examples remain ignored. Nothing staged, committed or pushed. |

## Fresh checks and evidence

Evidence root: `E:\Docker\AgentHub\public-docs-20261023-01`.

- `check-docs.py` / `content-check.json`: original-vs-current outline, IDs, layout
  counts, CSS/scripts, local links, target modules and image hash/size checks.
- `check-browser.cjs` / `browser-check.json`: **9 actual Edge checks**, zero page
  errors/bad resources, six responsive theme configurations, navigation, theme
  keyboard/persistence and direct `file://` opening. No dependency downloads.
- `capture-product.cjs` / `product-capture.json`: actual current UI; read-only
  localhost GET/OPTIONS only, no Provider or mutation requests.
- `records-unchanged.json`: original showcase DB unchanged; historical Task,
  TaskRun, Artifact, Diff and Review rowsets in the readback copy match the source.
- README Chinese login example passed the pure intent parser; no model executed.
- Strict OpenSpec and whitespace checks passed. No runtime code changed, so this
  task does not claim a fresh product API/Web unit regression or live-model test.

Independent read-only review found the ignored-asset delivery issue; narrowed
exceptions fixed it. Reviewer found no blocking factual or framework issue.
Snapshots during a theme transition were replaced by stable screenshots after
the existing 180ms transition; no theme implementation was changed.

## Scope and limits

Native records belong to one selected passing sample, not all 50 UI executions.
Current UI readback is not a fresh execution or active preview. Generated-result
images retain their original date and use platform Vite plus operator-assisted
ASGI; production deployment was not tested. Original failures, unknown usage,
previous benchmark evidence, primary product DB, adapters and worktrees are not
modified. Source image files are documentation assets, not build outputs.
