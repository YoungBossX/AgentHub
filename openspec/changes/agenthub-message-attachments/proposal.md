# Session-bound message attachments

## Why
The project PDF requires image and file messages with conversation context.
The current UI only renders image URLs; no uploaded file is persisted or sent
to planning/coding providers. A visible upload control alone cannot close this gap.

## What Changes
Implement bounded local uploads, message binding, previews/downloads, and
actual provider inputs for UTF-8 text/source files, text PDFs and PNG/JPEG/WebP
images. Preserve attachment identity and content hashes in context evidence.
Add one focused SQLite support entity, MessageAttachment, to hold immutable
bytes and extraction metadata without writing arbitrary host/worktree paths.
Extend existing Claude/Codex transports, not the adapter roster or permissions.

## Impact
New API/UI and additive SQLite table; explicitly add pinned Pillow/pypdf
dependencies for validated image decoding and PDF text extraction. Preserve
all existing no-attachment workflows, model failure/fallback honesty, scope
checks, execution leases, history, and the local single-user boundary.
