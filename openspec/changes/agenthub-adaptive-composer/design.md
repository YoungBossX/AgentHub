# Design and implementation plan

The user asked to proceed with the previously recommended targeted refinements.
Preserve the existing visual system and earlier chat interaction requirements.

## Approach

Use the existing controlled React textarea with scrollHeight-based sizing and
ResizeObserver width updates. This supports older browsers without requiring
field-sizing. Preserve the external DOM ref and avoid height animation while
typing so caret/input response remains immediate. CSS normally bounds height at
64–240px; a short viewport permits a single 24px line while sharing space with
reference controls. Preserve native
scrolling rather than globally hiding scrollbars.

A small client hook measures visualViewport on narrow screens only at scale 1.
Write height/top CSS variables to the shell; a mobile fixed shell follows those
bounds. Desktop, unsupported browsers and pinch zoom keep the existing dvh
fallback. Never disable zoom, force focus or scroll the whole document.

Use safe-area-aware dock padding and 44px composer actions on touch layouts;
retain single inset focus rings and radius = inner radius + surface padding.
Bound context/attachment lists locally so long references remain reachable.
Short narrow viewports show a user-expandable reference summary without unmounting
skills, context or uploads. Condense only the duplicated header progress and
breadcrumb while preserving view tabs. Clip the message scroll wrapper at its
actual bounds so its padding cannot intercept adjacent composer controls when
its flex height reaches zero. Bind viewport listeners to the current shell node
because switching Sessions replaces the keyed provider's DOM subtree.

Native field-sizing alone was considered but leaves older browsers uncovered.
A new UI library or global redesign adds unrelated churn and is excluded by the
user's minimal-change request. Reuse existing task/approval/evidence semantics.

## Task 1: Implement and verify the focused refinement

- [x] Add failing tests for draft grow/shrink, width changes, preserved external
  refs, viewport resize/pan, unsupported viewport, desktop/zoom fallback and cleanup.
  Expected: new tests fail on the current fixed-input implementation.
- [x] Implement bounded sizing and the viewport hook; integrate with shell/CSS.
  Files: message-composer.tsx, use-workbench-viewport.ts, workspace-shell.tsx,
  globals.css and focused tests. Expected: focused tests pass and old IME cases pass.
- [x] Extend the existing offline browser harness with actual component sizing,
  long-paste/delete/width changes, touch geometry and synthetic keyboard viewport
  checks. Preserve labels distinguishing fixture evidence from OS/device tests.
- [x] Make minimal text edits in README.md and index.html, keeping public section
  order, markup structure, CSS/scripts/assets and historical metrics unchanged.
- [x] Run all Web tests, Web checks, production build, strict OpenSpec, whitespace,
  browser-script syntax and actual Edge fixture checks. Compare public structural
  invariants and inspect desktop/mobile light/dark screenshots.
- [x] Request an independent read-only review, address material findings, update
  project-state/change-log/verification and mark the single task complete.

## Review focus

- Draft clearing, restored drafts, selected text and external focus refs.
- Very long input, narrow width and resize-observer height feedback loops.
- Keyboard pan/rotation, absent visualViewport and pinch zoom accessibility.
- Many context items/attachments in a short viewport without inaccessible actions.
- Documentation claims match implemented behavior without changing old evidence.

No commit/push step: this request authorizes local implementation only.
