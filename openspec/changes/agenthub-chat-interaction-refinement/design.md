# Design

Use the existing React components and CSS, rather than adding a chat/resize
library or redesigning the workspace. The user's exact thresholds are the
acceptance contract. This focused change supersedes the older 80px following
threshold and inspector double-click default-width behavior.

- Composer: track composition start/end separately from native key state. Enter
  cannot submit while composing, with keyCode 229, or less than 500ms after
  compositionend. Do not cancel the IME's candidate confirmation itself.
  Ordinary Enter submits; Shift+Enter, pending and attachment safeguards remain.
- Scroller: follow only within 40px while not manually paused. Wheel, touch,
  scrollbar/pointer and navigation-key intent pause immediately. Reaching the
  actual bottom or clicking 跳至最新 resumes. At a distance strictly over 120px,
  show 跳至最新 even without unread messages; keep unique unread counts.
  Historical pages, inactive views and session switching preserve their rules.
- Surfaces: outlines use inset shadows without adding box dimensions. Nested
  action buttons use fills/hover rather than an extra border/ring; retain visible
  keyboard focus and primary/selected/disabled state. Shared radius tokens make
  outer radius equal inner radius plus uniform container padding.
- Panes: use the existing transparent drag shield. Global Escape cancels and
  restores the pre-drag preferences without persistence. Double-click on the
  chat/result separator divides their available width 50/50, excluding the
  session sidebar; the sidebar separator keeps its own reset. The inspector can
  temporarily narrow during dragging; releasing with chat over 82% collapses it
  through existing inspector state. Keep the previous usable inspector width
  for reopening. Cancellation never commits a pending collapse.
  A container-width change cancels the drag; keyboard resizing cannot persist
  intermediate pointer-drag state. Hover fills apply to unfilled neutral actions,
  preserving primary/inverted button foreground-background pairs.
- Filenames: a shared accessible file label uses CSS ellipsis in its prefix and
  an unshrunk suffix. Preserve compound extensions, Unicode grapheme clusters,
  full title/accessible name and original file values/downloads.

Implementation plan: first add focused failing interaction tests; then update
composer/scroller/layout and shared file labels; apply scoped surface CSS; run
targeted and full Web tests, Web checks, production build, strict OpenSpec and
actual desktop/mobile light/dark browser checks. Use isolated read-only UI data,
not product mutations or model tasks. Do not advance another OpenSpec task.
