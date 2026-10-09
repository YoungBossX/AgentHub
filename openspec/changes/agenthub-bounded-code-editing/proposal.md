# Bounded code editing and applying Diff

## Why
The design PDF calls for direct code editing and applying differences. Existing
P23 editing versions only database artifact text, and the Diff viewer shows hunk
fragments read-only. Neither implements editing complete current source files.

## What Changes
Provide complete-file editing and bounded text-patch preparation from a Session's
registered non-platform target. Show a server-validated proposed Diff, then apply
only after an explicit user action and current file/version/ownership checks.
Keep durable user-origin operation evidence, conflict/failure/restart handling and
current-workspace preview provenance. Preserve original Agent results and reviews.

## Scope Resolution
This focused change adds a separate user-directed repository editing path. It
supersedes P23's no-direct-repository-write non-goal only for this path. Existing
artifact document version editing remains database-only. Protected paths, task
execution locks, command boundaries and canonical Session ownership still apply.
No HumanAgentAdapter, new provider/adapter, arbitrary host browser, Git commit,
push, dependency installation, production deployment or platform target editing.
