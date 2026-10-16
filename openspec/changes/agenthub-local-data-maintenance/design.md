# Local data maintenance

The API holds a shared OS lease beside its SQLite file for its whole lifespan.
Maintenance requires an exclusive lease, an idle configured loopback API port,
and a SQLite write reservation. Refuse active Runs, locks and preview jobs.
The user stops API/agents/previews and other Git/file writers first. Advisory
locks and two-pass file verification are not a hostile-process filesystem snapshot.

Back up SQLite with its backup API, including WAL contents, then capture the
development checkout's Git metadata and source files plus registered worktrees
owned beneath `.worktrees`. Persist original absolute identities, heads,
Session/Run bindings, per-file hashes/modes and an inventory digest. Preserve
staged/unstaged changes, deletions and nonignored untracked files. Refuse missing,
foreign, linked, externally dependent or unsupported repositories rather than
label a partial snapshot complete. Dependencies, ignored outputs and external
registered target source directories are outside this local snapshot scope.

Snapshots live in a new external directory. Verification never executes saved
hooks, target code or remote Git operations. An isolated restore copies into a
new directory, repairs only copied Git administrative pointers, uses a fixed
Git config and checks SQLite integrity, original DB bytes, heads, indexes and
file hashes. Persisted DB paths/evidence remain unchanged; rehearsal is not an
activated portable workspace. Same-location restore may only recreate the exact
missing original repository (including DB/worktrees), with explicit snapshot ID;
never overwrite or merge an existing checkout.

Inventory separates DB/Git/managed worktrees from fixed developer Python caches.
Cleanup candidates are only known cache directories outside every registered
worktree; any persisted path/JSON reference blocks them. A preview binds the
database reference view, Git worktree registry and complete candidate tree hash.
Explicit apply rechecks all bindings under the exclusive lease and moves matching
caches into a newly allocated repo-owned quarantine. No recursive deletion,
Session/Run/artifact pruning, Git worktree removal, dependency cleanup or host
directory traversal. Partial moves remain visible in a durable receipt.
