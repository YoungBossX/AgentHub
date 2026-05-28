## Why

P12 established AgentHub's platform-core contracts and P13 froze
cross-provider coordination. AgentHub can now make provider assignment visible
across TaskRun metadata, handoffs, artifact evidence, scheduler state, and
mission trace. The next limitation is that AgentHub still treats agent and
provider capability mostly as built-in assumptions instead of a stable,
validated registry.

P14 creates the controlled foundation for provider-aware, capability-aware,
target-aware Agent profiles. It is not a marketplace phase. It must preserve
the current adapters and baselines while making agent/provider metadata,
capabilities, supported modes, supported targets, and safe custom agent drafts
explicit enough for future product work.

## What Changes

- Promote AgentProfile into a stable Agent Profile Registry concept.
- Add a Provider Config Registry for `claude_code`, `codex`, and
  `scripted_mock` metadata.
- Define controlled capability tags and execution modes.
- Add Agent Selection Policy that resolves by explicit mention,
  ProviderAssignmentMatrix, role, target, capability, and safety flags.
- Upgrade the Agent Contact UI to show provider, capability, target, and
  availability state without changing execution semantics.
- Add Safe Custom Agent Draft metadata that cannot run arbitrary shell
  commands, request unsafe tool permissions, or bypass validation.
- Rehearse P14 to verify built-in agents, provider-aware selection,
  backend=Codex/frontend=Claude Code metadata, invalid assignment rejection,
  UI metadata display, and P6-P13 baseline preservation.

## Capabilities

### New Capabilities

- `agent-provider-foundation`: Agent profile registry, provider config
  registry, controlled modes/capability tags, agent selection policy, contact
  UI metadata, safe custom agent drafts, and P14 rehearsal.

### Modified Capabilities

- Existing AgentProfile and provider assignment behavior are formalized behind
  the new foundation while preserving current adapters and fallback behavior.

## Impact

- Backend:
  - stable AgentProfile registry model/service and API response shape;
  - provider config metadata for built-in providers without storing secrets;
  - controlled capability/mode schema;
  - validation for role, provider, target, capability, and safety flags;
  - safe draft custom agent metadata that is disabled or review-only until
    validated.
- Frontend:
  - contact UI displays provider badge, capability tags, supported targets,
    and unavailable/auth issue states;
  - no marketplace, no arbitrary command editor, and no broad redesign.
- Runtime:
  - preserve AgentAdapter, CodexAdapter, ClaudeCodeAdapter, and
    ScriptedMockAdapter;
  - do not fake Claude/Codex success;
  - keep Target Registry, Scheduler, CanonicalSharedContext, mission trace,
    handoffs, artifact evidence, and staging deploy behavior intact.
