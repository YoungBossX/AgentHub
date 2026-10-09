# Keep setup dependency links out of worktree dirty-state checks

## Why
Session setup links preinstalled node_modules directories into detached worktrees.
The directory-only node_modules/ Git rule does not match those symbolic links,
so the scheduler treats a freshly initialized demo worktree as dirty.

## What Changes
- Make the versioned dependency ignore rule cover directories and symbolic links.
- During server-owned Session setup, add only the two fixed dependency paths to
  the assigned repository's Git info/exclude so existing HEADs and reused Session
  worktrees also work without rewriting tracked files or removing links.
- Verify real Git status, Session reuse, scheduler readiness and protected scope
  evidence; preserve dirty-file conflicts and path protection.

## Impact
One worktree initialization task. The trusted server may append these two ignore
entries to its verified repository metadata before execution. Adapters retain
their Git-control and dependency write prohibition. No dependency installation,
schema, provider, UI, ScriptedMock routing or Preview/deployment changes.
