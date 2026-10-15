# Local boundary and evidence repair

An ASGI request guard rejects non-loopback Host values, untrusted browser
Origins, and mutation requests without X-AgentHub-Control: local-workspace.
The header forces browser preflight; it is not an authentication secret. MCP
retains its execution-bound Bearer/Origin checks. Shared web request helpers
add the control header, including bodyless controls, uploads and settings.
Test clients use valid loopback addresses and the explicit header; denial
tests remove it and must prove no mutation occurs.

Preview file access is enforced by a server-owned Vite configuration, bounded
to the frontend root and required installed runtime dependencies. HTTP and
module reads deny protected paths and unrelated source files, including
symlink escapes. Tests exercise a real installed Vite server without installing
dependencies or modifying existing Sessions.

Skill save acquires a SQLite write transaction before reading the default
catalog, checks the complete post-save aggregate and retains per-package CAS.
Competing changes cannot both consume the last default count or prompt bytes.
Rejected writes roll back; historical frozen run bindings remain unchanged.

Diagnostics use explicit error codes, failure states, unsuccessful command
receipts and structured native error events. Ordinary prose, successful
provider selection and passing validation do not produce failure factors.
Real errors and unsuccessful postprocessing remain visible.
