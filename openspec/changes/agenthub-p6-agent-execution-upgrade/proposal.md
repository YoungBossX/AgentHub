## Why

P5 made AgentHub feel like a local single-user IM-style multi-agent coding
workspace, but execution is still too demo-shaped: normal user requests require
overly explicit orchestrator phrasing, while role mentions do not yet act as
clear assignment shortcuts. P6 is needed to route ordinary messages through the
Orchestrator / Manager by default, use Claude Code and Codex more directly as
practical coding executors, and preserve AgentHub's safety boundaries, evidence
discipline, and diff / preview / mock deploy loop.

## What Changes

P6 introduces an agent execution capability upgrade in three sequential layers:

1. **Message Routing, Direct Agent Assignment, and Orchestrator Auto-Run**
   - Messages without explicit role mentions route to the Orchestrator /
     Manager by default.
   - Explicit role mentions have highest priority:
     - `@orchestrator` routes to Orchestrator / Manager;
     - `@frontend` creates a Frontend Agent task;
     - `@backend` creates a Backend Agent task;
     - `@qa` creates a QA task;
     - `@review` creates a Review task.
   - `@frontend`, `@backend`, `@qa`, and `@review` are explicit assignment
     modes for advanced users, not the default path for normal requests.
   - Direct assignment tasks preserve the user's original request and can be
     started through the existing TaskRun path.
   - Orchestrator-created safe demo-target coding tasks auto-start through the
     existing TaskRun execution path.
   - Requests are bounded to safe target directories, but they are not reduced
     to the old login-page-only instruction templates.

2. **Session Context Pack + Role-based Instruction Builder**
   - Agent instructions include recent messages, execution ledger, selected
     artifact context, latest diff, changed files, preview/deploy status, and
     current goal.
   - Frontend, backend, QA/review, and manager instructions differ by role and
     give Claude/Codex enough context to do meaningful work.
   - Unsupported or unsafe requests fail honestly or produce clarification tasks
     instead of pretending the system can complete arbitrary work.

3. **Bounded Full-stack App Generation Vertical Slice**
   - Add a safe demo backend target such as `apps/demo-api` so Backend Agent
     work does not freely mutate the AgentHub platform backend.
   - Add contract-first orchestration so frontend and backend tasks reference
     the same structured app contract.
   - Verify one bounded mini app flow, such as todo, notes, or mini CRM
     contacts:

     ```text
     user requirement -> contract -> backend task -> frontend task
     -> qa/review -> diff -> preview -> mock deploy
     ```

P6 keeps the existing adapters:

- `CodexAdapter`
- `ClaudeCodeAdapter`
- `ScriptedMockAdapter`

It does not add a new adapter family or replace the P4/P5 baseline.

## Capabilities

### New Capabilities

- `agent-execution`: Default Orchestrator routing, direct role assignment,
  session context packaging, role-based instructions, safe demo backend
  execution, contract-first planning, and bounded full-stack vertical-slice
  verification.

### Modified Capabilities

None. P6 adds a new execution capability while preserving the existing P5
IM-style workspace and P4 final demo guarantees.

## Impact

OpenSpec artifacts:

- `openspec/changes/agenthub-p6-agent-execution-upgrade/proposal.md`
- `openspec/changes/agenthub-p6-agent-execution-upgrade/design.md`
- `openspec/changes/agenthub-p6-agent-execution-upgrade/tasks.md`
- `openspec/changes/agenthub-p6-agent-execution-upgrade/specs/agent-execution/spec.md`

Expected implementation impact when P6 is later applied:

- Backend:
  - message routing policy where unmentioned messages default to Orchestrator;
  - direct mention routing for explicit executable role tasks;
  - support for `@review` as an executable review mention;
  - selected artifact context passed to Orchestrator by default rather than
    bypassing it;
  - session context pack generation;
  - role-based instruction builder;
  - demo backend target registration;
  - contract-first orchestrator output;
  - task graph support for bounded full-stack vertical slices.
- Frontend:
  - preserve current chat/task/artifact surfaces;
  - show direct mention tasks as first-class executable tasks;
  - expose context/contract/review artifacts where needed;
  - keep existing artifact cards and right Artifact Panel.
- Data model:
  - likely additions for app contracts, context-pack metadata, selected artifact
    references, and demo backend workspace metadata;
  - no multi-user account model in P6.
- Runtime:
  - same-session write tasks remain serial until conflict handling exists;
  - frontend and backend write tasks use safe demo target directories;
  - preview and mock deploy remain local demo evidence, not production deploy.

## Explicit Non-Goals

P6 does not implement:

- arbitrary SaaS generation;
- unrestricted editing of AgentHub platform code;
- production deploy;
- multi-user IM;
- Matrix, Feishu, WeChat, Slack, or other external IM integration;
- provider marketplace;
- Docker sandbox;
- PR creation;
- enterprise approval workflow;
- payment, auth, or multi-tenant production systems.

## Validation

For this OpenSpec change:

```bash
git diff --check
openspec validate agenthub-p6-agent-execution-upgrade --strict
```
