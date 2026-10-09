# Render rich chat messages and copy code

## Why
The PDF requires text/code messages and code copying. Ordinary message bubbles
currently show Markdown syntax as plain text; message copying has no failure
handling. This weakens the readability of real Agent outputs.

## What Changes
Render standard Markdown and GFM in ordinary message bubbles with scoped theme
styles, bounded parsing, safe links, literal HTML, scrollable code/tables, and
per-block code copying. Keep group summaries, pin/quote semantics and raw stored
content. Provide explicit copy feedback. Remote Markdown image references do
not load until a user requests a preview.

## Impact
One frontend task. Explicitly add react-markdown and remark-gfm as project
dependencies (without running install scripts), then verify the lockfile and
production dependency audit. No binary uploads, model attachments, task replay,
editable worktree code, backend mutation, or new Agent permissions in this task.
