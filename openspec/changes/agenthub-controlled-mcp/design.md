# One controlled server, one verified adapter path

WorkspaceMcpConnection persists a built-in agenthub_docs connection, selected
list_documents/read_document tools and default role/custom-Agent identities.
Freeze policy into TaskRun metrics before queuing. Unsupported adapters keep the
existing workflow with explicit compatibility evidence. Disabled policies do not
inject MCP arguments; current revocation denies further calls.

At the final execution boundary, capture bounded regular Markdown/text documentation
from the assigned worktree's target root (README and docs), plus explicitly
related built-in backend documentation in that same clone. Reject links and
protected paths and each document target's additional denied paths; no arbitrary host paths, dynamic code execution or external URL
fetches. Retain source paths, hashes and bounded redacted content per invocation.

Issue in-memory, random, short-lived bearer tokens bound to TaskRun, workspace,
Agent, runner and executionAttemptId. Validate current lease/access binding on
each request, deny terminal/lost/restarted executions and revoke on cleanup.
Never persist or expose raw tokens. Codex receives only server-generated config
overrides and a dedicated credential environment value excluded from shell tool
environment. Existing command containment and default ignore-user-config remain.

Implement stateless JSON responses for initialize, notifications/initialized,
ping, tools/list and tools/call, reject unsupported/batched/oversized requests,
validate Origin and protocol versions. Tool annotations are explanatory; actual
server allowlists and scope checks enforce permissions.

Every call emits durable TaskRunEvent receipts with tool/validated arguments,
duration, result status, source hashes and bounded output. Configuration alone is
never recorded as a successful call. UI shows enabled tools, compatibility,
connection probes and actual per-run calls. Verify actual JSON-RPC transport,
native command boundaries, cancellation/expiry/revocation, secret redaction and
at least one actual Codex tool call when the local Provider is available.
