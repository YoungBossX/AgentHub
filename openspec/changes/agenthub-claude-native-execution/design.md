# Native execution and bounded settings bridge

Resolve the native Windows executable beside the installed npm shim without shell
parsing. Respect explicit executable overrides and preserve POSIX behavior. Share
the resolver between coding, Planner and health checks.

Read only the local user's settings.json env section, bounded in size, from an
absolute CLAUDE_CONFIG_DIR or user home. Never read project/local settings or run
helpers. Copy an explicit SDK authentication/base URL/model allowlist; process
environment overrides settings, and an explicit credential prevents inheriting a
second credential. Ignore hooks, plugins, MCP, permissions and runtime injection.
Include settings credentials in evidence redaction. Retain restricted/safe mode,
strict MCP, file-only tools, budget, no persistence, and the exact command guard.
Decode subprocess output as UTF-8.

Verify native launch, secret isolation/redaction, invalid settings and existing
containment with controlled tests. Attempt fresh real coding and read-only runs,
checking actual changed files/Diff and unchanged review bytes. A scripted Review
artifact remains labelled scripted even when its originating TaskRun uses Claude.
