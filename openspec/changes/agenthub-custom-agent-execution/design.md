# Design

Reuse AgentProfileDraft for validated custom profiles. Add system_prompt, mention_alias
and tool_policy with defaults preserving legacy drafts. Custom names/aliases are separate
from stable frontend/backend/review/orchestrator roles. Alias uniqueness is workspace
scoped and case-normalized, enforced in SQLite. No destructive migration or deletion.

Create/update validates profile role, provider, allowed target IDs, capabilities and
native tool policy. Codex coding retains its existing CLI workspace-write containment
and native command tools; it does not claim fine-grained shell-tool isolation.
Claude coding uses the existing Read/Write/Edit/MultiEdit set; Claude review uses only
Read in both --tools and --allowedTools. Planner uses the existing no-tool JSON path.
No user-supplied commands/tools, arbitrary filesystem scope or platform writes.

Runtime selection and explicit workspace @alias must select the actual profile,
not silently substitute a built-in role. TaskRun creation validates the selected
profile against the task target/mode/capabilities, freezes its identity, prompt and
tool policy, and records public lineage without prompt text. Native request preparation
uses the frozen policy. Disabling or removing a selected profile before launch fails
closed; changes do not broaden existing queued permissions. Retry reselects current
configuration. Explicit Mock fallback retains the demo-only reliability path and
does not claim custom-model execution.

Profiles remain scoped to the workspace. Contacts insert stable aliases; task/run
UI identifies the selected custom profile while preserving built-in execution Agent
IDs and canonical worktree/queue/target lock semantics. Settings support create,
edit, enable/disable, cancel and explicit selection. Planner custom profiles flow
through current LLM request/provider resolution; deterministic fallback remains explicit.
