# Execute constrained custom Agent profiles

The PDF requires custom Agents with names, System Prompts and tool sets. Current
drafts cannot execute, and runtime profile selection only changes provider metadata.
This focused change adds validated executable profiles on the existing draft table,
workspace aliases/contacts, provider-backed tool policies and frozen execution lineage.
Legacy drafts remain non-executable. Existing roles, adapters and permission gates remain.

## Capabilities
- `custom-agent-execution`: editable, enabled workspace profiles selected by runtime
  settings or explicit mentions and executed through existing TaskRun/Planner paths.

## Impact
Additive SQLite columns/index, profile APIs/UI, mention selection, request preparation
and native Claude tools. No new adapter, dependency, marketplace, RBAC or deployment.
