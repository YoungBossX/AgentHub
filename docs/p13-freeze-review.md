# P13 Cross-provider Agent Coordination Freeze Review

**Date:** 2026-05-27

## Result

P13 is ready to freeze as Cross-provider Agent Coordination.

The freeze rehearsal used deterministic local execution rather than real
Claude Code or Codex mutation. It verified that AgentHub can coordinate a
single task graph where:

- Backend Agent is assigned to Codex (`local-codex-cli`);
- Frontend Agent is assigned to Claude Code (`local-claude-code-cli`);
- Review is deterministic scripted review (`local-scripted-review`);
- both coding tasks reference the same mini CRM app contract;
- provider identity remains visible through TaskRun metadata, handoff
  artifacts, artifact evidence, scheduler state, and mission trace.

No real Claude/Codex success is claimed by this freeze review.

## Rehearsal Path

The P13 rehearsal test covers:

```text
shared mini CRM contract
-> Backend Agent assigned to Codex
-> backend diff for apps/demo-api
-> scripted review
-> backend-to-frontend handoff
-> Frontend Agent assigned to Claude Code
-> frontend diff for apps/demo
-> scripted review
-> healthy preview
-> local staging deploy
-> mission trace evidence
```

## Evidence

Automated coverage:

- `apps/api/tests/test_cross_provider_rehearsal.py`
  - validates backend provider assignment is `codex`;
  - validates frontend provider assignment is `claude_code`;
  - validates the frontend task depends on the backend task;
  - validates backend diff and review artifacts;
  - validates provider-aware handoff metadata;
  - validates frontend diff provider evidence;
  - validates preview health;
  - validates local staging deployment readiness;
  - validates mission trace contains both provider identities and handoff
    artifacts.

Supporting P13 coverage:

- provider assignment matrix;
- provider-aware agent profiles;
- canonical context enforcement;
- provider-aware handoff metadata;
- provider-specific instruction wrappers;
- normalized provider evidence for diff/review/preview/deploy;
- mixed-provider scheduler state and target-lock coverage.

## Caveats

- P13 freeze did not run a live Claude Code or Codex mutation.
- The review agent remains deterministic scripted review by default.
- P13 does not add a provider marketplace, custom agent UI, OpenCode,
  multi-user IM, production deploy, distributed worker cluster, or scheduler
  replacement.
- Real provider runtime blockers such as auth, quota, or CLI failures must
  still be recorded honestly in future real mixed-provider smoke tests.

## Freeze Decision

P13 preserves the P6-P12 baseline while making provider assignment explicit,
auditable, and visible across task runs, handoffs, artifacts, scheduler state,
and mission trace.
