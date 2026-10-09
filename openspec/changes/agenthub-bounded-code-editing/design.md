# Design

## User workflow and source
From a Diff, the user can read the complete current file in the canonical Session
worktree, edit it, and prepare a proposed difference. A text-patch input also
supports bounded multi-file changes in the same registered target. Existing Agent
Diffs describe changes already applied; viewing them never blindly reapplies them.
The UI explains full current source versus historical hunk snippets.

This release requires the server-allocated canonical Session worktree. Legacy
external targets that execute directly in a host folder are rejected. Added files
require an existing parent directory. The patch limit is 16 files / 2 MiB patch,
512 KiB per UTF-8 file and 4 MiB combined before/after content. Reject Windows
device names, trailing-dot/space and short-name aliases on every platform.

Preparation performs strict patch parsing and applies hunks in memory against exact
source content. No fuzzy matching, silent offset guessing, binary patches, links,
renames, permission changes or path traversal. Support UTF-8 text modification,
addition and deletion with explicit newline semantics and bounded file/count/total
sizes. Empty edits do not become successful operations. Show exact paths, before/
after hashes and proposed patch before the user applies it.

## Ownership, concurrency and persistence
Resolve Session, source artifact/run and target on the server; never accept a host
path, command or client-owned permission policy. Canonical worktree registration,
target identity, regular files, protected path aliases and link/stream safety must
be checked before both read and write. No unmerged isolated execution output is
edited or previewed as canonical state.

Use an existing Artifact with a dedicated user-edit type and ArtifactVersion content
to persist the operation, its source and before/after evidence. This is a user edit,
not an Agent TaskRun or an Agent-success Diff. Source run links are context only;
original TaskRun, Diff and review rows remain immutable. Do not fabricate an adapter.

Application must exclude active/pending execution, join and held locks. Take the
same SQLite Session writer reservation as run creation/join, persist an applying
claim, and fence later run creation while an operation is unresolved. Revalidate
HEAD, target and every expected file before writes. Only an exact prepared operation
ID may apply; repeated delivery returns its persisted state without another write.

Use bounded regular-file writes, preserve unrelated content/modes, and roll back a
partial failure only when the changed paths still match this operation's own output.
Persist enough evidence for startup reconciliation: untouched inputs, complete
outputs and partial/foreign changes must be distinguished. Ambiguous interruptions
remain visibly unresolved and fenced; never silently overwrite external edits or
resume model execution. Resolve/retry actions must be explicit and source-checked.

On Windows, open file handles deny competing writes/deletes, and directory handles
pin their ancestors. POSIX uses no-follow descriptors, identity/content checks and
advisory file locks; an unrelated non-cooperating host process is outside this
local application's isolation guarantees. Startup recovery assumes one API owner.
For unresolved partial/foreign text, explicit keep-current records current hashes
and releases the fence without writing files or calling the operation applied.

## Results and current preview
Expose prepared, applied, conflicting, failed and unresolved operations in the
workbench with actor=user, source links and exact difference. Successful write is
not successful compilation, functional validation or a passed review. Existing
preview/review/provider evidence cannot be presented as validation of manual edits.
Current Vite preview should reflect the edited canonical files and display the user
revision where relevant. Preserve immutable original evidence and provide explicit
preview refresh/recovery through existing service ownership rules.

Later Agent execution captures its text snapshot after acquiring execution
ownership. Its Diff compares that snapshot with the new output, excluding manual
changes that already existed. The original Git execution baseline is preserved.
Historical Diff recollection and deployment are blocked after later user changes;
new previews label user origin rather than reusing provider-success provenance.

The full-file editor uses the installed local Monaco runtime with a usable fallback,
existing theme and resizing behavior. Keep drafts on conflict/network failure,
separate operation identity from source version, block duplicate submissions, and
discard late results for other Sessions or files. Narrow and dark layouts remain
usable. Do not add a general filesystem browser.

Preparation IDs survive lost responses in the tag-local draft. The workbench also
lists the latest 50 durable operation records independently of browser storage.
Full recovery snapshots are excluded from the document workbench bulk response.
Uniform CRLF is retained when a browser textarea exposes normalized LF values.

The native continuation check exposed Windows CreateProcess WinError 206 being
reported as FileNotFoundError for a valid Claude executable. Long planner argv
(24,000 UTF-16 units or more) now uses the existing stream-JSON stdin transport,
with the same tools, safe mode, model/output validation and no session persistence.

## Verification
Test multi-file and newline semantics, malformed/ambiguous patches, protected paths,
symlinks/hardlinks/Windows aliases, ownership and foreign Sessions, stale hashes and
target/HEAD changes, concurrent execution, duplicate apply, rollback and restart.
Run real browser edit -> Diff -> apply -> source hash -> Vite preview and a later
native Agent continuation. Verify historical records, current-state provenance,
themes/narrow layouts and reload recovery. Close only after relevant regressions,
strict OpenSpec and evidence review; leave the overall project goal active until
the remaining workflow/UI acceptance is done.
