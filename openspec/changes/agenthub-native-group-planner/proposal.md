# Native Planner coordination for explicit groups

Multiple mentions currently use deterministic coordination and reject custom
Planners. Reuse the existing Planner providers to generate real task content for
the selected group. Preserve every execution participant and registered target;
validate the entire response before persisting any task or coordinator reply.

## Impact
Extends the explicit-group coordinator and existing Planner request contract.
Supersedes the custom-Planner group rejection in agenthub-multi-agent-mention-routing.
No new adapter, dependency, database entity, auto-execution or production scope.
