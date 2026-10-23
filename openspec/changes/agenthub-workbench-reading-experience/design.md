# Design

Implement the user's approved incremental approach in the current Next.js
workbench. Keep the three mounted panes, width storage, light/dark palettes,
double-shadow focus, dark weight offset, reveal/copy/spring motion and reduced
motion/high-contrast support. A larger redesign or new UI library is unnecessary.

## Readability and hierarchy

Use theme action foregrounds on all primary buttons. Ordinary supporting text
must meet 4.5:1 contrast in both palettes. Retain background surface values; tune
the light muted foreground only. Workbench supporting text is at least 12px,
body 14px and primary headings 16–20px. Do not download fonts or claim static
Chinese fonts provide an actual continuously variable weight.

The stage summary keeps one clear action and visible next step. Routine details
and message-window counts are expandable. Blocking/failure/approval reasons stay
visible. Preserve all planning, process and evidence access; no technical evidence
is deleted. Existing history pagination and refresh remain available.

## Inspector

Session-keyed in-memory presentation state owns automatic/open/closed preference,
overlay and expansion. Automatic mode collapses without a selected artifact.
Manual close survives SSE/artifact refresh; explicit artifact selection opens it.
Session switching cannot transfer expanded/overlay state or selection to another
session. Re-selecting a session restores its presentation preference. Keep stored
column widths untouched and preserve keyboard resize/cancel semantics.

## Chat following

One visible workbench scroll root owns scrolling; the chat thread is normal flow.
A following controller considers 80px from the bottom as following. Initial/latest
load follows; scrolling upward suspends it. Append/resize while suspended must not
move the reading position. Count unique new message IDs; updates to the same ID
offer a new-content notice without double counting. Returning to bottom clears
the notice. Historical pagination never auto-jumps; explicit latest navigation
resumes following. Session/view switches and resize callbacks must not leak old
state. Use installed browser APIs only; no JS height animation or typing timer.

## Results

Associate artifacts using task.taskRuns IDs, never matching titles. Show the
latest run and its actual state even when it has no artifacts or failed. Fold
older runs into clearly labeled history, preserving concrete artifact IDs and
selection callbacks. Unmatched artifacts remain accessible as unassociated
historical evidence. Order execution batches from task run order; do not relabel
that ordinal as an artifact version. Show actual document version numbers and
version summaries; the existing inspector remains the version viewer/editor.
No aggregation may turn historical reviews/previews into current acceptance.

## Verification

Meaningful failing tests cover inspector intent/session isolation, message append,
scroll suspension/resume/history/resize, and task/run/version result boundaries.
Verify actual bright/dark desktop and 390/1024px pages, font/contrast, current vs
historical results, explicit inspector actions and chat scroll behavior with an
isolated E-drive UI fixture database and intercepted read responses. Clipboard
and model calls are not part of this task. Store logs/screenshots under E:\Docker.
