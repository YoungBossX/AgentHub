# Workbench Visual Polish Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans in this session. The user already requested implementation; no extra approval or commit/push is part of this task.

**Goal:** Apply the user's ten UI rules without changing product workflows or data.

**Architecture:** Shared palette/typography/motion tokens and small interaction
primitives integrate into the existing three-pane workbench. Preserve theme and
resize stores; animate only presentation and appended prose.

**Tech Stack:** Existing Next.js, React, Tailwind CSS, Vitest and Playwright.

**Spec:** openspec/changes/agenthub-workbench-visual-polish/design.md

## Global Constraints

- Frontend only, no dependency installation, no product database changes.
- User's exact palette, timing and spring parameters; support reduced motion.
- Data, temporary files and screenshots stay under E:\Docker.
- Initial UI implementation did not authorize commit or push. Subsequent explicit
  user instruction authorizes source-only commit/push to dev and exact-commit CI
  verification; preserve the original implementation acceptance evidence.

## Review Focus

- Clipboard completion races after content replacement or unmount.
- Large streamed chunks, Unicode graphemes and Markdown code/link safety.
- Closed disclosures containing keyboard-focusable children and lazy requests.
- Theme changes during animation; intermediate weights on static system fonts.
- Drag cancellation, minimum widths and mobile drawer/inspector behavior.

### Task 1: Apply and verify the visual system

**Files:** globals.css; chat-markdown/module.css; copy-text-button; shared
Disclosure and motion utilities/tests; disclosure consumers; composer, sidebar,
header and workbench-layout; change-log/project-state and this OpenSpec change.

**Interfaces:** Disclosure takes summary, children, defaultOpen and onOpenChange;
motion presets expose CSS easing and duration; Markdown accepts append updates
without changing its existing content/messageId interface.

- [x] Add meaningful failing tests for copy expiry/repeat/races, disclosure keyboard
  behavior and Markdown append/history/Unicode/code handling. Run to confirm RED.
- [x] Implement the primitives and palette, migrate disclosures, balance composer,
  apply spring feedback without delaying pointer-controlled widths.
- [x] Run the new tests and full Web suite, pnpm check, whitespace and strict
  OpenSpec validation. Fix regressions before marking the task complete.
- [x] Inspect actual light/dark desktop and narrow pages; verify focus, resize,
  disclosure and copy expiry, capture screenshots under the external evidence root.
- [x] Review the scoped patch, record evidence/limitations, update docs and checkbox.
