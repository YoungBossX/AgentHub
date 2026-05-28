# P14 Freeze Review: Custom Agent / Provider / Plugin Foundation

**Date:** 2026-05-28

## Freeze Decision

P14 is ready to freeze as the Custom Agent / Provider / Plugin Foundation.

P14 adds controlled metadata, policy, and UI foundations for provider-aware,
capability-aware, target-aware Agent profiles. It does not add a provider
marketplace, arbitrary command agents, OpenCode integration, cloud token
management, multi-user sharing, production deploy, or adapter replacement.

## Rehearsal Coverage

The rehearsal verified:

- built-in orchestrator, frontend, backend, QA, review, and fallback profiles
  remain available;
- provider config metadata is non-secret and covers Claude Code CLI, Codex CLI,
  and Scripted Mock;
- controlled capability and mode schemas reject unsupported values;
- Agent Selection Policy rejects unsupported target/capability/safety
  assignments before adapter execution;
- Agent Contact UI displays provider, adapter, capability, target, and status
  metadata while preserving Direct chat / Group workflow visual modes;
- safe custom AgentProfile drafts can be created as review-only metadata;
- draft profiles reject write capability, arbitrary shell commands, unsafe tool
  permissions, unrestricted filesystem access, and unknown providers;
- backend=Codex/frontend=Claude Code mixed-provider rehearsal metadata remains
  intact through the existing P13 deterministic rehearsal.

## Evidence

Targeted backend rehearsal:

```bash
../../.venv/bin/python -m pytest \
  tests/test_planning.py::test_workspace_agent_registry_returns_im_contacts \
  tests/test_planning.py::test_workspace_agent_profiles_match_provider_assignment_matrix \
  tests/test_agent_selection_policy.py \
  tests/test_agent_profile_drafts.py \
  tests/test_cross_provider_rehearsal.py
```

Result: 11 passed.

Targeted frontend rehearsal:

```bash
pnpm --filter @agenthub/web test -- workspace-shell lib/api
```

Result: 9 files / 40 tests passed.

## Caveats

- P14 did not run live Claude Code or Codex mutations; it verifies metadata,
  policy, UI, and deterministic mixed-provider rehearsal.
- Safe custom AgentProfile drafts are not executable write agents.
- Draft profiles do not include marketplace publishing, sharing, installation,
  custom shell commands, or unsafe tool permissions.
- Provider auth status remains metadata-only; AgentHub does not manage cloud
  tokens in P14.

## Recommended Tag

`p14-custom-agent-provider-foundation-freeze`
