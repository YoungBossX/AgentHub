# Workbench Reading Experience Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans in the current checkout.
> The user approved the approach and requested execution. No additional approval,
> branch creation, commit or push is required or authorized for this task.

**Goal:** Deliver all six approved improvements as one focused workbench change.

**Architecture:** Small session-keyed inspector state, one conversation scroll
controller and a pure result grouping helper integrate into existing components.
Shared typography/action styles preserve all prior motion/palette rules.

**Tech Stack:** Existing React, Next.js, Tailwind, Vitest and Playwright.

**Spec:** openspec/changes/agenthub-workbench-reading-experience/design.md

## Global Constraints

- Frontend only, no dependencies or font downloads, no persistence/API changes.
- Preserve real evidence and all existing adapters, process/result controls.
- New data, logs and temporary files stay under E:\Docker; no commit or push.

## Review Focus

- Manual inspector close after a new artifact/SSE refresh and session switches.
- A reader scrolled upward during text/resize updates and historical navigation.
- Failed retries, duplicate task titles, orphan artifacts and edited documents.
- Critical failure/approval reasons hidden by information compression.
- Narrow screens, keyboard focus, reduced motion and small-text contrast.

### Task 1: Reading experience

**Files:** New use-inspector-state, conversation-scroll, session-result-groups,
session-results and tests. Integrate workspace-shell, chat-thread, session-overview,
session-guidance, global CSS and primary Agent form controls; browser acceptance
script, OpenSpec and docs.

**Interfaces:** Inspector exposes collapsed/open/expanded plus explicit reveal,
close and desktop/mobile toggles. ConversationScroll accepts session/messages,
active/loading/historical and children. groupSessionResults(tasks, artifacts)
returns current and historical batches using run IDs. SessionResults retains
its existing artifacts/tasks/onSelect/compact interface.

- [x] Write tests for inspector default/manual/session behavior, chat follow and
  suspended append/resize/count/history behavior, result grouping/current failure
  and actual document versions. Run and verify expected failures.
- [x] Implement the helpers and integrate without changing artifact identity,
  history navigation, pane widths or evidence semantics.
- [x] Apply contrast/typography and compress routine details; keep critical reasons
  visible. Run focused tests and fix integration regressions.
- [x] Run the full Web suite, root checks, tools, build and strict OpenSpec.
- [x] Inspect actual light/dark responsive UI and browser interactions against
  isolated UI fixtures, capture evidence, request an independent read-only review,
  fix validated findings and perform requirement-by-requirement completion audit.
