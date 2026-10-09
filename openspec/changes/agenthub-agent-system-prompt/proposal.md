# Agent System Prompt execution

Agent.system_prompt is stored but omitted from coding instructions. Runtime settings
cannot edit workspace prompts. This focused change wires built-in Agent defaults
and bounded workspace overrides into existing coding and LLM Planner requests.
It does not activate custom profiles, grant tools, or change adapter permissions.

## Capabilities
- `agent-system-prompt`: persistent, workspace-scoped prompts and frozen run inputs.

## Impact
Existing runtime roles JSON, request construction, provider rendering and runtime UI.
No new dependencies, database tables, providers or deployment behavior.
