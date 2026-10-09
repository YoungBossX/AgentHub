# Bounded explicit group assignments

Two or more distinct mentioned roles use `explicit_group_v1`, even if the built-in
Orchestrator is named last. Every execution role is represented. Writes retain
mention order; reviews follow all writes and bind separately to each write target.
Repeated identical mentions deduplicate; different profiles for the same role fail.
The coordinator is deterministic and disclosed as such; execution remains manual,
matching direct assignments. Single-role planning and native Planner paths remain.

Reuse direct task factories with deferred persistence, then validate the complete
graph, registered target/role/path policy and custom profile capabilities before a
single commit. Invalid requests retain the original user message but no partial
tasks or coordinator response. Review tasks use the new planner identifier, so
generated advisory reports cannot impersonate an explicitly selected reviewer.
All tasks carry the source message, group participants, graph, target and selected
custom identity; existing execution revalidation and frozen TaskRun evidence apply.

Group contact clicks append distinct aliases; direct contact clicks replace the
leading participant prefix. Switching visual modes does not launch or rewrite tasks.
