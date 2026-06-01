## Why

AgentHub's chat workspace currently renders detailed Agent Runtime Settings inside the main session sidebar, which makes the primary chat experience feel like a configuration console instead of an IM-style session workspace. This became visible after P16/P17b added useful runtime configuration controls; those controls now need a dedicated settings surface so the chat page can stay focused on sessions, messages, tasks, and artifacts.

## What Changes

- Move detailed Agent Runtime Settings out of the chat/session sidebar and into a dedicated runtime settings page or route.
- Keep the chat page simple: workspace/session navigation, agent contacts, chat thread, task/artifact surfaces, and a compact settings entry point only.
- Add a settings button or navigation affordance from the chat page to the runtime settings page.
- Provide Save and Cancel actions on the runtime settings page, with draft state isolated from the active chat view.
- Translate internal provider/config statuses such as `unchecked`, `missing_key`, `not_required`, `required`, and `unavailable` into user-friendly UI copy.
- Preserve the existing Runtime Config API, Provider Config API, Agent Profile metadata, and P17b multi-provider planner API behavior.
- Do not add arbitrary custom agents, new providers, raw API key storage, or a provider marketplace.

## Capabilities

### New Capabilities
- `runtime-settings-page`: Dedicated runtime settings surface for Planner, Frontend, Backend, and Review agent runtime configuration, plus user-friendly provider status presentation.

### Modified Capabilities
- None.

## Impact

- Frontend UI structure in `apps/web`, especially `workspace-shell`, `session-sidebar`, and `agent-runtime-settings`.
- Frontend routing or page composition for the new settings page.
- Frontend tests for chat layout, settings navigation, Save/Cancel behavior, and status-label presentation.
- Existing backend runtime configuration APIs should remain compatible; backend changes are only expected if read-only metadata needs friendlier status mapping.
- Documentation updates in `docs/project-state.md` and `docs/change-log.md` when implementation begins.
