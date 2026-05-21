## Why

AgentHub final demo hardening is frozen around a verified local single-user
Agent Coding Workspace / strong demo MVP. The baseline loop is:

```text
requirement -> plan -> agent execution -> diff -> preview -> mock deploy
```

That baseline is valuable, but it is still shaped like a demo command center.
P5 should move AgentHub toward the product direction more decisively:

```text
IM-style interaction -> Manager Agent planning -> coding agent execution
-> review agent -> artifact cards -> preview -> mock deploy -> follow-up interaction
```

The current P5 plan was too conservative because it started with lightweight
session context as the main first slice. P5 should instead become an executable
platform-evolution plan for an IM-style multi-agent coding workspace v1 while
still preserving the final demo baseline and avoiding long-term platform
features such as real multi-user sync, external IM integration, production
deploy, or provider marketplace.

## What Changes

Revise `agenthub-p5-platform-evolution` from a broad research roadmap into an
executable OpenSpec change for a local, single-user IM-style multi-agent coding
workspace v1.

P5 adds a planned implementation path for:

1. Agent Registry and IM Contact UI.
2. Shared Context and Execution Ledger.
3. Review Agent Workflow.
4. Multi-Agent Execution Trace UI.
5. Dynamic Manager Planner v1.
6. Artifact Message Cards v2.
7. P5 E2E rehearsal and freeze review.

The intended P5 product experience is:

```text
user requirement -> Manager Agent planning -> coding agent execution
-> review agent -> artifact cards -> preview -> mock deploy
-> follow-up interaction
```

P5 keeps the current verified adapters as first-class runtime options:

- `CodexAdapter`
- `ClaudeCodeAdapter`
- `ScriptedMockAdapter`

P5 may introduce clearer product roles such as Manager Agent, Coding Agent, and
Review Agent, but it must not remove or regress the current adapters or the
existing diff / preview / mock deploy path.

## Capabilities

### New Capabilities

- `im-agent-workspace`: Local single-user IM-style multi-agent coding workspace
  v1, including agent contacts, direct-chat/group-workflow modes, execution
  ledger, review artifacts, execution trace, bounded Manager planning, and
  artifact message cards.

### Modified Capabilities

None of the final-demo runtime guarantees are removed. P5 builds on the frozen
baseline.

## Impact

OpenSpec artifacts:

- `openspec/changes/agenthub-p5-platform-evolution/proposal.md`
- `openspec/changes/agenthub-p5-platform-evolution/design.md`
- `openspec/changes/agenthub-p5-platform-evolution/tasks.md`
- `openspec/changes/agenthub-p5-platform-evolution/specs/im-agent-workspace/spec.md`

Expected implementation impact when P5 is later applied:

- Backend:
  - agent registry/contact metadata;
  - shared execution ledger;
  - review artifact type and review task flow;
  - bounded Manager planner output;
  - artifact reference support for follow-up interactions.
- Frontend:
  - agent contact list;
  - direct-chat/group-workflow visual modes;
  - multi-agent execution trace;
  - inline artifact cards for diff, preview, review, and mock deploy;
  - artifact selection/reference UI.
- Data model:
  - likely metadata additions for agent contact display, execution ledger, review
    artifacts, plan graph structure, and artifact references.
- Runtime:
  - same-session write tasks remain serial to avoid worktree conflicts;
  - review tasks may be read-only and non-blocking in v1;
  - diff, preview, and mock deploy remain preserved.

## Explicit Non-Goals

P5 is not a full IM platform. P5 explicitly does not implement:

- full multi-user IM platform;
- real Feishu, WeChat, Slack, Matrix, or other IM integration;
- desktop or mobile apps;
- provider marketplace;
- production deploy;
- Docker sandbox;
- PR creation;
- unrestricted arbitrary code editing;
- full vector database memory;
- distributed worker cluster;
- enterprise approval workflow;
- real-time multi-user sync and conflict resolution;
- user-created agents as an immediate P5 runtime feature.

User-created agents remain a future capability after the built-in registry,
capability model, permissions, and audit story are stable.

## Validation

For this proposal revision:

```bash
git diff --check
openspec validate agenthub-p5-platform-evolution --strict
```
