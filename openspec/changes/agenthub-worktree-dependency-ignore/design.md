# Design

Keep symbolic links rather than introduce Windows junctions or relax reparse-point
validation. node_modules without a trailing slash covers both directories and
links in the versioned .gitignore. Worktrees are checked out from HEAD, which may
still contain the old rule, so setup must also establish the rule at runtime.

Before creating/reusing dependency links, verify the Session worktree's Git common
directory matches the WorktreeService source repository. Append missing exact
/node_modules and /apps/demo/node_modules patterns to that common directory's
info/exclude, preserving existing bytes and rejecting redirected metadata paths.
These rules are repository-local and therefore shared by its linked worktrees;
they do not change global Git settings or ignore arbitrary application paths.
Reusing setup is idempotent. Do not delete or replace existing dependency links.
Use the existing sanitized project-process environment for Git ownership and
worktree commands so inherited GIT_DIR overrides cannot redirect setup. Reject
exclude files with multiple hard links as well as redirected symbolic paths.

Ignored dependencies remain protected by guardrails and the scope snapshot's
redacted protected footprint. No filtering is added to scheduler dirty checks,
isolated allocation or joins. A normal unrelated untracked/modified file remains
visible and blocked. Tests use a fresh temporary repository with the historical
directory-only rule, real dependency symlinks, real Git status and scope capture.
