# AgentHub Design

## Context

AgentHub is an IM-style coding-agent collaboration product, not a generic chatbot, full AI IDE, or enterprise agent platform.

The P0 product must demonstrate one reliable and verifiable loop:

```text
requirement -> orchestrator plan -> agent execution -> real git diff -> real preview -> deploy card
```

The user experience should feel closer to a coding-focused group chat than to an IDE plugin. Users interact with an orchestrator and role agents through messages, mentions, task cards, diff cards, preview cards, and approval controls.

The design deliberately keeps P0 small enough for a 3-week implementation while preserving extension seams for future adapters, richer orchestration, stronger sandboxing, PR workflows, and multi-user collaboration.

The Research Brief supports this direction by identifying worktrees, approval controls, diffs, previews, and deployable artifacts as the shared product language of modern coding-agent tools. For this design, the brief is background only. The fixed stack, guardrails, acceptance criteria, and demo script define the P0 scope.

---

## Goals / Non-Goals

### Goals

- Build a single-user local demo with multiple sessions and IM-style chat.
- Show user, orchestrator, and role-agent messages in one session stream.
- Parse `@orchestrator`, `@frontend`, `@backend`, and `@qa` mentions.
- Produce 2-4 visible tasks per orchestrated request.
- Execute at least one task through `CodexAdapter`.
- Provide `ScriptedMockAdapter` fallback that modifies the demo repo for real.
- Use session-level git worktree isolation in P0.
- Generate real diffs through Git CLI and render them in the UI.
- Start a real preview for one supported demo app stack.
- Show a deploy card after preview succeeds, with mock deploy acceptable for P0 reliability.
- Support interrupt, retry, and basic approval controls.
- Persist enough task, artifact, and event state so the UI can recover after refresh or SSE reconnect.
- Preserve extension seams for future `ClaudeCodeAdapter`, `HumanAgentAdapter`, PR creation, Docker sandboxing, and richer orchestration.

### Non-Goals

- No enterprise RBAC.
- No billing.
- No multi-tenant admin.
- No full external IM integration.
- No full IDE editor.
- No arbitrary DAG builder.
- No provider marketplace.
- No full deployment matrix.
- No multiplayer presence.
- No complex autonomous agent team.
- No reasoning visualization.
- No long-term memory.
- No complete MCP marketplace.
- No WebSocket in P0.
- No Docker sandbox as a P0 blocker.
- No generic multi-framework preview runner.
- No LangGraph or CrewAI as a P0 dependency.

---

## System Architecture

```text
Next.js App Router UI
  - Workspace and session shell
  - Session list and chat stream
  - Task state cards
  - Diff card using Monaco Diff Editor
  - Preview side panel or iframe
  - Approval, retry, interrupt, and deploy cards

FastAPI backend
  - Pydantic request/response/event contracts
  - SQLAlchemy or SQLModel persistence
  - SQLite database for P0
  - SSE event stream
  - Orchestrator service
  - Adapter service
  - Worktree service
  - Diff service
  - Preview service
  - Deploy service
  - Permission guardrail service
  - Event persistence and recovery service

Execution layer
  - Git CLI worktree manager
  - CodexAdapter process runner
  - ScriptedMockAdapter controlled script runner
  - Command allowlist
  - Protected path checks
  - Approval gate integration
```

The frontend does not implement agent execution. It displays the authoritative state and artifacts emitted by the backend.

The backend owns:

- Task planning.
- Adapter execution.
- Worktree paths.
- Diff collection.
- Preview lifecycle.
- Deploy card generation.
- Guardrail enforcement.
- Event persistence before streaming.

---

## Fixed Tech Stack

- Frontend: Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui, Monaco Diff Editor.
- Backend: Python, FastAPI, Pydantic, SQLAlchemy or SQLModel.
- Database: SQLite for P0, schema designed for later Postgres compatibility.
- Realtime: SSE for P0.
- Diff: Git CLI, `git diff -p`, changed files, stats, optional `git apply --check`.
- Preview: one supported demo app stack only. Choose one during implementation, preferably Vite React for fastest local preview.
- Deploy: basic deploy card. A mock deploy card is allowed if a real Vercel demo deploy is unstable.
- Sandbox/isolation: session-level git worktree, command allowlist, protected paths, approval gates. Docker sandbox is P1.

### Why TypeScript + Next.js + FastAPI

This stack is preferred over pure Java or pure Python because AgentHub requires both a polished interactive UI and a flexible execution backend.

- Next.js + TypeScript is better suited for IM-style UI, task cards, artifact cards, preview panels, and Monaco-based diff rendering.
- FastAPI is lightweight for process orchestration, CLI execution, SSE, Pydantic event contracts, and Python-based adapter scripts.
- The split keeps UI complexity out of the execution backend and keeps adapter/process orchestration out of the frontend.
- Pure Java would slow down iteration and add unnecessary infrastructure overhead for a 3-week student project.
- Pure Python would make the frontend less ergonomic and likely reduce the quality of the IM-style product experience.

---

## P0 Product Loop

The P0 demo must prove the following loop end to end:

```text
User sends requirement
  -> Orchestrator creates visible plan
  -> Role agent executes one or more tasks
  -> Backend collects real Git diff
  -> UI renders diff card
  -> Backend starts preview
  -> UI opens preview card/panel
  -> Backend creates deploy card
  -> User can approve, retry, interrupt, or request follow-up change
```

The demo must also include a failure recovery path:

```text
CodexAdapter fails or is interrupted
  -> TaskRun moves to failed/interrupted
  -> User clicks retry
  -> ScriptedMockAdapter completes fallback
  -> Real files are still modified
  -> Real diff and preview are still generated
```

---

## Adapter Lifecycle

The adapter lifecycle remains intentionally small:

```text
getCapabilities()
createRun(request)
streamEvents(runId)
interrupt(runId)
approve(runId, approval)
collectArtifacts(runId)
cleanup(runId)
```

### AdapterCapabilities

Each adapter must expose a lightweight capability descriptor so the orchestrator and UI can make safe decisions without hard-coding provider behavior.

```ts
interface AdapterCapabilities {
  supportsStreaming: boolean
  supportsInterrupt: boolean
  supportsApproval: boolean
  supportsFileEdit: boolean
  supportsShellCommand: boolean
  supportsDiffArtifact: boolean
  supportsPreviewArtifact: boolean
  supportsNetwork: boolean
  maxRuntimeSec?: number
}
```

P0 uses this mainly for `CodexAdapter` and `ScriptedMockAdapter`. P1 adapters such as `ClaudeCodeAdapter` and `HumanAgentAdapter` can be added without changing the core lifecycle.

### AgentRunRequest

```ts
interface AgentRunRequest {
  taskRunId: string
  sessionId: string
  workspaceId: string
  worktreePath: string
  agentId: string
  adapterType: 'codex' | 'scripted_mock' | 'claude_code' | 'human'
  instruction: string
  planContext?: Record<string, unknown>
  permissionProfile: PermissionProfile
  demoMode?: boolean
  fallbackPolicy?: 'none' | 'scripted_mock_on_failure'
}
```

### AgentEvent

```ts
interface AgentEvent {
  type:
    | 'message.delta'
    | 'task.state'
    | 'approval.requested'
    | 'artifact.diff.ready'
    | 'artifact.preview.ready'
    | 'artifact.deploy.ready'
    | 'error'
    | 'completed'
  taskRunId: string
  sequence: number
  payload: Record<string, unknown>
  createdAt: string
}
```

All important events must be persisted before being emitted over SSE. The UI treats SSE as a delivery channel, not as the source of truth.

---

## P0 Adapters

### CodexAdapter

`CodexAdapter` is the only P0 real coding adapter.

Responsibilities:

- Run inside the assigned session worktree.
- Receive one task instruction at a time.
- Emit normalized lifecycle events.
- Modify files in the worktree.
- Respect command allowlist, protected path checks, and approval gates.
- Support interruption where possible.
- Map execution failures into normalized `TaskRun.errorCode` and `TaskRun.errorMessage`.
- Call artifact collection after execution reaches a terminal or collection point.

P0 acceptance:

- At least one task can execute through `CodexAdapter` and produce real file changes.
- If Codex execution is unavailable or unstable, the retry path can fall back to `ScriptedMockAdapter`.

### ScriptedMockAdapter

`ScriptedMockAdapter` is the P0 reliability path.

It must not be fake-only chat. It executes controlled scripts against the demo repo worktree, emits realistic lifecycle events, can simulate approval or failure states, and still relies on Git CLI diff collection for final artifacts.

Responsibilities:

- Modify real files in the demo repo.
- Simulate realistic coding-agent progress messages.
- Simulate success, failure, interruption, and approval states.
- Stay within command allowlist and protected path rules.
- Produce real diffs and real previewable app changes.

### ClaudeCodeAdapter

`ClaudeCodeAdapter` is P1, not P0.

The design should leave room for it by preserving:

- Adapter lifecycle compatibility.
- Capability descriptor.
- Permission profile input.
- Worktree-scoped execution.
- Unified event mapping.

### HumanAgentAdapter

`HumanAgentAdapter` is optional P1.

It can reuse the same Task and TaskRun model by moving a run into `waiting_approval` or `waiting_human_input`, then allowing a human user to submit a message, patch, or decision.

P0 does not implement this adapter.

---

## Orchestrator State Machine

The P0 orchestrator is a simple service, not a general DAG engine.

It must:

- Parse user intent from a chat message.
- Create 2-4 visible tasks.
- Assign tasks to role agents.
- Support simple serial dependencies.
- Support at most one simple parallel group.
- Stream state changes.
- Attach artifacts.
- Summarize results.

### Task States

```text
pending
planning
running
waiting_approval
completed
failed
interrupted
```

### TaskRun States

```text
created
queued
streaming
applying_changes
collecting_diff
starting_preview
completed
failed
interrupted
```

### Retry and Interrupt

- Retry creates a new `TaskRun` for the same `Task`.
- Interrupt moves the active run to `interrupted`, stops adapter execution where possible, and preserves collected messages and artifacts.
- Failed or interrupted runs must remain visible in the chat stream.
- Retried runs must not overwrite previous run history.

---

## Structured Plan JSON

The orchestrator stores a stable `planJson` structure on `Task` or on the originating orchestration message.

P0 may generate this plan through deterministic templates. Future versions may replace the planner with an LLM or graph framework without changing the frontend contract.

```json
{
  "intentType": "feature",
  "summary": "Build a login page for the demo app",
  "riskLevel": "medium",
  "requiresApproval": false,
  "tasks": [
    {
      "clientTaskId": "inspect-app",
      "title": "Inspect demo app structure",
      "role": "frontend",
      "adapterHint": "codex",
      "dependsOn": [],
      "expectedArtifacts": ["message"]
    },
    {
      "clientTaskId": "implement-login-ui",
      "title": "Implement login page UI",
      "role": "frontend",
      "adapterHint": "codex",
      "dependsOn": ["inspect-app"],
      "expectedArtifacts": ["diff", "preview"]
    },
    {
      "clientTaskId": "qa-check",
      "title": "Check the login flow in preview",
      "role": "qa",
      "adapterHint": "scripted_mock",
      "dependsOn": ["implement-login-ui"],
      "expectedArtifacts": ["message", "preview"]
    }
  ]
}
```

### Example Task Flow

User message:

```text
@orchestrator build a login page for the demo app
```

Expected flow:

1. `@orchestrator` parses the intent as `feature`.
2. Orchestrator creates 2-4 tasks.
3. The first task inspects the app structure.
4. The second task modifies the app using `CodexAdapter` if available.
5. If `CodexAdapter` fails, user can retry with `ScriptedMockAdapter` fallback.
6. Backend collects real diff from the session worktree.
7. Backend starts preview for the supported demo app.
8. UI shows diff card and preview card.
9. Deploy card appears after preview succeeds.
10. User can request a second small change in the same session.

---

## Event Persistence and SSE Recovery

P0 uses SSE, not WebSocket.

The backend must persist state transitions before emitting events. SSE is only the streaming transport.

### Minimum Recovery Rule

After page refresh or SSE reconnect, the UI must be able to reconstruct:

- Session messages.
- Current tasks.
- Current task runs.
- Terminal task states.
- Available artifacts.
- Diff cards.
- Preview cards.
- Deploy cards.
- Approval requests still waiting for user action.

### Recommended P0 Event Entity

Although the original P0 model is intentionally small, adding `TaskRunEvent` is recommended because it improves debugging, SSE replay, and adapter traceability with minimal complexity.

```text
TaskRunEvent:
- id
- taskRunId
- eventType
- payloadJson
- sequence
- createdAt
```

If the team chooses not to add `TaskRunEvent` in P0, the design must still guarantee that the UI can recover from persisted `Message`, `Task`, `TaskRun`, `Artifact`, `Diff`, `Preview`, and `Deployment` records.

---

## Worktree and Diff Design

### Worktree Decision

P0 uses session-level worktree isolation.

```text
One Session -> One Git worktree
Multiple TaskRuns in that Session -> Reuse the Session worktree
```

Rationale:

- A session represents one continuous coding context.
- Follow-up requests can build on previous changes.
- Preview can stay attached to the same worktree.
- Diff can show cumulative changes for the session.
- Implementation is simpler and more reliable for a 3-week project.

`TaskRun.worktreePath` still stores the resolved worktree path for traceability. In P0 this usually equals `Session.worktreePath`.

P1 may support task-run-level worktrees for parallel conflicting tasks.

### Worktree Constraints

- Multiple sessions must never share the same worktree path.
- Worktree paths must be persisted.
- Worktree creation must use deterministic naming based on workspace/session identifiers.
- Worktree cleanup must be explicit and safe.
- Protected host paths must never be exposed to adapters.

### Diff Collection

Diff collection is backend-owned:

1. Ensure adapter execution has ended or reached an artifact collection point.
2. Run `git diff -p` inside the session worktree.
3. Collect changed files and stats from Git CLI.
4. Optionally run `git apply --check` against generated patch text where useful.
5. Store an `Artifact` of type `diff`.
6. Store `Diff` with `baseRef`, `headRef`, `patchText`, `changedFilesJson`, and `statsJson`.
7. Emit `artifact.diff.ready`.

The UI renders:

- Changed files.
- Patch summary.
- Expandable file-level changes.
- Monaco Diff Editor for detailed inspection.

Monaco Diff Editor is used for diff detail only, not as a general IDE.

---

## Preview Design

P0 supports exactly one demo stack. The recommended target is Vite React because startup is fast and preview routing is straightforward.

The preview runner:

- Starts the demo app inside the session worktree.
- Uses allowlisted commands only.
- Allocates or records the preview port.
- Performs a health check.
- Persists preview status.
- Emits `artifact.preview.ready` when healthy.
- Cleans up preview processes when the session is closed or reset.

The UI opens the preview in a right-side panel or iframe and can refresh after a second change.

Preview processes must be bounded by session/task lifecycle. Unbounded background processes are not allowed.

### Preview Record Requirements

The `Preview` record should support reruns and debugging:

```text
Preview:
- id
- artifactId
- port
- url
- command
- processId
- healthStatus
- statusReason
- expiresAt
- lastCheckedAt
```

---

## Deploy Card Design

The deploy card is a P0 artifact view, not a full deployment platform.

After preview succeeds, the backend creates a `Deployment` record and emits `artifact.deploy.ready`.

P0 can show one of two paths:

1. A real Vercel demo deploy if stable in the team's environment.
2. A mock deploy card if real deploy is unreliable.

The mock deploy card must still be backend-created and persisted as a `Deployment` record. It should not be a frontend-only hardcoded card.

Deploy actions require approval.

P0 does not support:

- Multiple deploy providers.
- Deployment matrix.
- Production release management.
- Git push requirement.
- Unreviewed deploy.

### Deployment Record Requirements

```text
Deployment:
- id
- artifactId
- provider
- environment
- commitSha
- url
- status
- deployLogUri
- createdAt
```

---

## Permission Guardrails and Approval Design

P0 guardrails are intentionally simple but must be real.

### Guardrail Rules

- Use command allowlist.
- Block protected paths.
- Disable network by default unless explicitly approved.
- Require approval for deploy actions.
- Require approval for push actions.
- Require approval for destructive file operations.
- Require approval for editing protected files.
- Require approval for non-allowlisted commands.

### Approval Types

The system distinguishes product confirmation from security approval.

```text
product_confirmation
security_approval
```

Examples:

- Product confirmation: accept diff, continue to deploy, retry with fallback.
- Security approval: allow network access, allow protected path edit, allow non-allowlisted command.

### Approval Payload

```ts
interface ApprovalRequestPayload {
  approvalType: 'product_confirmation' | 'security_approval'
  reason: string
  requestedAction: string
  riskLevel: 'low' | 'medium' | 'high'
  command?: string
  path?: string
  expiresAt?: string
}
```

The UI may render both approval types with the same card component, but the payload must distinguish them.

---

## IM Interaction Design

AgentHub should feel like a coding-agent group chat.

### Single Chat

A single session contains:

- User messages.
- Orchestrator messages.
- Role-agent messages.
- System messages.
- Task cards.
- Diff cards.
- Preview cards.
- Deploy cards.
- Approval cards.

### Multiple Sessions

Users can create and switch between at least three sessions in one workspace.

Each session has:

- Its own message history.
- Its own task state.
- Its own session-level worktree.
- Its own diff and preview artifacts.

### Group Chat

P0 group chat is simulated through multiple role agents in one session stream. It is not multiplayer human collaboration.

Example:

```text
User: @orchestrator build a login page
Orchestrator: I will split this into frontend implementation, QA check, and preview.
Frontend Agent: I am updating the login page components.
QA Agent: I will verify the visible login flow after preview starts.
```

### @Agent Commands

Supported P0 mentions:

- `@orchestrator`
- `@frontend`
- `@backend`
- `@qa`

Unknown or disabled agents produce user-facing parse errors.

### Agent Execution Status

Task cards should show:

- Assigned agent.
- Current state.
- Current run number.
- Running/failed/interrupted/completed status.
- Retry button when failed or interrupted.
- Interrupt button while running.
- Approval button when waiting for approval.

### Diff Card

The diff card shows:

- Artifact title.
- Changed files count.
- Additions/deletions stats.
- File list.
- Expandable details.
- Monaco diff view for selected file.

### Preview Card

The preview card shows:

- Preview status.
- Preview URL.
- Open in side panel action.
- Refresh action.
- Last checked time.

### Deploy Card

The deploy card shows:

- Provider.
- Environment.
- Status.
- Commit SHA or worktree ref.
- URL placeholder or real URL.
- Deploy log URI placeholder or real log URI.
- Approval action before real deploy.

### User Controls

P0 must support:

- Confirm/approve.
- Interrupt.
- Retry.
- Retry with fallback.
- Request a second small change in the same session.

---

## Data Model Overview

P0 uses the following entities.

No additional P0 domain entities should be introduced unless a task cannot satisfy the demo loop without them. `TaskRunEvent` is the only recommended small addition because it materially improves event recovery and debugging.

### User

```text
id
email
name
avatarUrl
createdAt
```

### Workspace

```text
id
name
repoUrl
rootPath
defaultBranch
createdAt
```

### Session

```text
id
workspaceId
title
sessionType
boundBranch
worktreePath
status
lastMessageAt
createdAt
updatedAt
```

### Message

```text
id
sessionId
senderType
senderId
contentMd
messageKind
parentMessageId
streamState
createdAt
```

### Agent

```text
id
name
role
adapterType
provider
defaultModel
systemPrompt
capabilitiesJson
permissionProfileJson
enabled
createdAt
updatedAt
```

### Task

```text
id
sessionId
createdByMessageId
title
intentType
status
priority
planJson
dependsOnTaskIds
assignedAgentId
createdAt
updatedAt
```

### TaskRun

```text
id
taskId
agentId
adapterRunId
state
startedAt
endedAt
worktreePath
errorCode
errorMessage
metricsJson
createdAt
updatedAt
```

### TaskRunEvent Recommended

```text
id
taskRunId
eventType
payloadJson
sequence
createdAt
```

### Artifact

```text
id
taskRunId
artifactType
title
status
version
storageUri
metaJson
createdAt
updatedAt
```

### Diff

```text
id
artifactId
baseRef
headRef
patchText
changedFilesJson
statsJson
createdAt
```

### Preview

```text
id
artifactId
port
url
command
processId
healthStatus
statusReason
expiresAt
lastCheckedAt
createdAt
updatedAt
```

### Deployment

```text
id
artifactId
provider
environment
commitSha
url
status
deployLogUri
createdAt
updatedAt
```

---

## Real Implementation vs Mock Strategy

### Real in P0

- Session and task persistence.
- SSE state/event streaming.
- Event recovery from persisted backend state.
- Session-level git worktree creation.
- `CodexAdapter` execution path.
- `ScriptedMockAdapter` file mutations.
- Git diff collection.
- Preview startup for the supported demo app.
- UI cards for plan, task states, diff, preview, approval, retry, interrupt, and deploy.

### Mock or Constrained in P0

- Deploy can be mock-backed.
- Agent planning can use deterministic templates as long as the visible tasks match user intent.
- `ScriptedMockAdapter` can simulate events, approvals, and errors, but it must create real file changes.
- The preview runner supports one app stack only.

### P1 / P2

- `ClaudeCodeAdapter`.
- `HumanAgentAdapter`.
- PR creation.
- Docker sandbox.
- WebSocket.
- Provider marketplace.
- Enterprise controls.
- External IM integrations.
- Multi-user collaboration.

---

## Risk and Mitigation

### Risk: Real Codex execution is unstable during demo

Mitigation:

- Keep `ScriptedMockAdapter` as a first-class fallback.
- Ensure fallback modifies the demo repo for real.
- Preserve the same diff and preview pipeline for both real and fallback adapters.

### Risk: Scope expands into a full agent platform

Mitigation:

- Enforce P0/P1/P2 boundaries.
- Only build features serving the 5-minute demo path.
- Do not add enterprise, marketplace, multi-user, or generic orchestration features in P0.

### Risk: Worktrees leak state across sessions

Mitigation:

- Use session-level worktrees in P0.
- Persist and assert unique worktree paths per session.
- Clean up worktrees deliberately.
- Never reuse one worktree across multiple sessions.

### Risk: Arbitrary command execution is unsafe

Mitigation:

- Use command allowlist.
- Block protected paths.
- Disable network by default.
- Require approvals for risky actions.
- Do not expose arbitrary shell to agents.

### Risk: Preview runner becomes a framework matrix

Mitigation:

- Support one demo app stack only in P0.
- Prefer Vite React unless the team already has a stable Next.js demo app.

### Risk: SSE stream and database state diverge

Mitigation:

- Persist state transitions before emitting events.
- Add `TaskRunEvent` or guarantee recovery from canonical persisted state.
- Let the UI reload canonical state after reconnect.

### Risk: Monaco integration consumes frontend time

Mitigation:

- Use Monaco only for file-level diff detail.
- Render summary and changed file lists with normal UI components.

### Risk: Orchestrator feels fake

Mitigation:

- Render clear task decomposition.
- Assign visible role agents.
- Show state changes and artifacts.
- Ensure at least one task modifies real files and produces real diff.

### Risk: Deploy exceeds P0 scope

Mitigation:

- Treat deploy as an artifact card.
- Use mock deploy if real Vercel deploy is unstable.
- Persist mock deploy as a backend-created `Deployment` record.

### Risk: Three weeks is not enough

Mitigation:

- Implement the success demo path first.
- Implement fallback path second.
- Defer provider expansion, Docker, WebSocket, PR creation, and external IM integrations.

---

## Migration Plan

1. Scaffold the fixed frontend/backend/database structure.
2. Add the P0 schema and seed one user, workspace, agents, and demo repo configuration.
3. Decide and document the P0 demo app stack, preferably Vite React.
4. Build workspace/session UI and session-level worktree binding.
5. Build persisted chat flow with SSE.
6. Add mention parsing for `@orchestrator`, `@frontend`, `@backend`, and `@qa`.
7. Add structured orchestrator planning and task state transitions.
8. Add event persistence or recovery strategy.
9. Add adapter interface with `getCapabilities()`.
10. Add `ScriptedMockAdapter`.
11. Add `CodexAdapter` happy path and normalized errors.
12. Add permission guardrails and approval types.
13. Add diff collection and diff UI.
14. Add preview runner and preview UI.
15. Add deploy card and mock deploy backend path.
16. Add interrupt, retry, and retry-with-fallback controls.
17. Write README and demo script.
18. Run final success and failure recovery demo rehearsals.

Rollback strategy for demo instability:

- Use `ScriptedMockAdapter`.
- Use mock deploy card.
- Use deterministic demo repo path.
- Preserve real git diff and real preview behavior.

---

## Open Questions

### Should the P0 demo app be Vite React or Next.js?

Recommendation: Vite React unless the team already has a stable Next.js demo app ready.

Reason: Vite React usually starts faster, has simpler local preview behavior, and is easier to mutate safely in a scripted fallback.

### Should worktree isolation be per Session or per TaskRun?

Decision: P0 uses session-level worktree isolation.

Reason: It better supports chat-style follow-up changes and reduces implementation risk.

P1 can add task-run-level worktrees for more advanced parallel execution.

### Will CodexAdapter run through a local CLI invocation or an API wrapper?

Still open.

The adapter interface should hide this detail from the orchestrator and UI. The implementation only needs to satisfy the P0 contract: run inside the session worktree, emit normalized events, modify real files, and map failures into normalized errors.

### Should TaskRunEvent be mandatory in P0?

Recommendation: Yes, if implementation time allows.

It is a small table with high value for SSE replay, debugging, and demo reliability.

If omitted, the backend must still guarantee recovery from `Message`, `Task`, `TaskRun`, `Artifact`, `Diff`, `Preview`, and `Deployment` records.

---

## P0 Acceptance Checklist

The P0 is complete when all of the following are true:

- User can open the AgentHub UI locally.
- User can create and switch between at least three sessions.
- Each session has a distinct worktree.
- User can send `@orchestrator build a login page for the demo app`.
- Orchestrator creates 2-4 visible tasks.
- Task cards show assigned role agents.
- Task states update visibly in the chat stream.
- At least one task can execute through `CodexAdapter`.
- `ScriptedMockAdapter` can complete the same flow if Codex fails.
- Fallback flow modifies real files in the demo repo.
- Backend collects real `git diff -p` output.
- UI renders changed files and patch summary.
- User can expand diff details.
- Preview starts for the supported demo app.
- User can open preview in side panel or iframe.
- User can request a second small change in the same session.
- User can interrupt a running task.
- User can retry a failed or interrupted task.
- Approval card appears for risky or deploy actions.
- Deploy card appears after preview succeeds.
- Mock deploy keeps the demo working when real deploy is unavailable.
- README explains local setup.
- Demo script includes one success path and one failure recovery path.

---

## Final Design Principle

AgentHub P0 should not try to be a complete agent platform.

It should prove one sharp product claim:

```text
Coding agents become visible IM collaborators whose work produces verifiable artifacts.
```

Everything in P0 should serve that claim. Everything else should be deferred.

