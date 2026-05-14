## Context

AgentHub is an IM-style coding-agent collaboration product, not a generic chatbot, full AI IDE, or enterprise agent platform. The P0 product must demonstrate one reliable and verifiable loop:

```text
requirement -> orchestrator plan -> agent execution -> real git diff -> real preview -> deploy card
```

The user experience should feel closer to a coding-focused group chat than to an IDE plugin. Users interact with an orchestrator and role agents through messages, mentions, task cards, diff cards, preview cards, and approval controls.

The Research Brief supports this direction by identifying worktrees, approval controls, diffs, previews, and deployable artifacts as the shared product language of modern coding-agent tools. For this design, the brief is background only. The fixed stack, guardrails, acceptance criteria, and demo script define the P0 scope.

## Goals / Non-Goals

**Goals:**
- Build a single-user local demo with multiple sessions and IM-style chat.
- Show user, orchestrator, and role-agent messages in one session stream.
- Parse `@orchestrator`, `@frontend`, `@backend`, and `@qa` mentions.
- Produce 2-4 visible tasks per orchestrated request.
- Execute at least one task through `CodexAdapter` using local CLI invocation.
- Provide `ScriptedMockAdapter` fallback that modifies the Vite React demo repo for real.
- Use session-level git worktree isolation in P0.
- Generate real diffs through Git CLI and render them in the UI.
- Start a real preview for the Vite React demo app.
- Show a deploy card after preview succeeds, with mock deploy acceptable for P0 reliability.
- Support interrupt, retry, and basic approval controls.
- Persist task-run events so the UI can recover after refresh or SSE reconnect.
- Preserve extension seams for future adapters, API/cloud Codex wrappers, Docker sandboxing, PR workflows, and richer orchestration.

**Non-Goals:**
- No enterprise RBAC, billing, multi-tenant admin, full external IM integration, full IDE editor, arbitrary DAG builder, provider marketplace, full deployment matrix, multiplayer presence, complex autonomous agent team, reasoning visualization, long-term memory, or complete MCP marketplace.
- No WebSocket in P0.
- No Docker sandbox as a P0 blocker.
- No generic multi-framework preview runner.
- No LangGraph or CrewAI as a P0 dependency.
- No ClaudeCodeAdapter or HumanAgentAdapter in P0.
- No Codex API/cloud task wrapper in P0.

## System Architecture

```text
Next.js App Router product UI
  - Workspace and session shell
  - Session list and chat stream
  - Task state cards
  - Diff card using Monaco Diff Editor
  - Preview side panel or iframe
  - Approval, retry, interrupt, and deploy cards

FastAPI backend
  - Pydantic request/response/event contracts
  - SQLModel persistence
  - SQLite database for P0
  - SSE event stream and replay
  - Orchestrator service
  - Adapter service
  - Worktree service
  - Diff service
  - Preview service
  - Deploy service
  - Permission guardrail service
  - Event persistence and recovery service

Execution layer
  - Git CLI session worktree manager
  - CodexAdapter local CLI process runner
  - ScriptedMockAdapter controlled script runner
  - Command allowlist
  - Protected path checks
  - Approval gate integration

Agent-modified demo repo
  - Vite React only
  - Dependencies installed during setup
  - Preview command: pnpm dev --host 127.0.0.1 --port <port>
```

The frontend does not implement agent execution. It displays the authoritative state and artifacts emitted by the backend. The backend owns task planning, adapter execution, session worktree paths, diff collection, preview lifecycle, deploy card generation, guardrail enforcement, and event persistence before streaming.

## Fixed Tech Stack

- Product UI: Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui, Monaco Diff Editor.
- Backend: Python, FastAPI, Pydantic, SQLModel.
- Database: SQLite for P0; schema remains Postgres-compatible. Alembic is P1 unless already available.
- Realtime: SSE for P0, backed by persisted `TaskRunEvent` records for replay and recovery.
- Diff: Git CLI, `git diff -p`, changed files, stats, optional `git apply --check`.
- Demo app modified by agents: Vite React only.
- Preview: dependencies installed during setup; preview runner must not run `pnpm install` during agent execution; command is `pnpm dev --host 127.0.0.1 --port <port>`.
- Deploy: basic deploy card. A mock deploy card is allowed if a real Vercel demo deploy is unstable.
- Sandbox/isolation: one git worktree per Session, command allowlist, protected paths, approval gates. Docker sandbox is P1.

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

Each adapter exposes a lightweight capability descriptor so the orchestrator and UI can make safe decisions without hard-coding provider behavior.

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

P0 uses this for `CodexAdapter` and `ScriptedMockAdapter`. P1 adapters such as `ClaudeCodeAdapter`, `HumanAgentAdapter`, and a Codex API/cloud task wrapper can be added without changing the core lifecycle.

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

All important events must be persisted as `TaskRunEvent` before being emitted over SSE. The UI treats SSE as a delivery channel, not as the source of truth.

## P0 Adapters

### CodexAdapter

`CodexAdapter` is the only P0 real coding adapter. It uses local CLI invocation and runs inside the assigned session worktree. API/cloud task wrappers are P1.

Responsibilities:
- Run inside `Session.worktreePath`.
- Receive one task instruction at a time.
- Emit normalized lifecycle events.
- Modify files in the worktree.
- Respect command allowlist, protected path checks, and approval gates.
- Support interruption where possible.
- Map execution failures into normalized `TaskRun.errorCode` and `TaskRun.errorMessage`.
- Call artifact collection after execution reaches a terminal or collection point.

P0 acceptance:
- At least one task can execute through `CodexAdapter` and produce real file changes.
- If Codex CLI execution is unavailable or unstable, the retry path can fall back to `ScriptedMockAdapter`.

### ScriptedMockAdapter

`ScriptedMockAdapter` is the P0 reliability path. It must not be fake-only chat. It executes controlled scripts against the Vite React demo repo in the session worktree, emits realistic lifecycle events, can simulate approval or failure states, and still relies on Git CLI diff collection for final artifacts.

Responsibilities:
- Modify real files in the Vite React demo repo.
- Simulate realistic coding-agent progress messages.
- Simulate success, failure, interruption, and approval states.
- Stay within command allowlist and protected path rules.
- Produce real diffs and real previewable app changes.

## Orchestrator State Machine

The P0 orchestrator is a simple service, not a general DAG engine. It parses user intent from a chat message, creates 2-4 visible tasks, assigns tasks to role agents, supports simple serial dependencies, supports at most one simple parallel group, streams state changes, attaches artifacts, and summarizes results.

Task states:
```text
pending
planning
running
waiting_approval
completed
failed
interrupted
```

TaskRun states:
```text
created
queued
streaming
waiting_approval
applying_changes
collecting_diff
starting_preview
completed
failed
interrupted
```

Retry creates a new `TaskRun` for the same `Task`. Interrupt moves the active run to `interrupted`, stops adapter execution where possible, and preserves collected messages, events, and artifacts. Failed or interrupted runs remain visible and retried runs do not overwrite previous run history.

## Event Persistence and SSE Recovery

P0 uses SSE, not WebSocket. The backend persists state transitions and adapter trace events before emitting them.

`TaskRunEvent` is the only P0 support entity allowed beyond the core domain model. It exists for SSE replay, debugging, and adapter traceability. It must not open the door to unrelated P0 domain entities.

```text
TaskRunEvent:
- id
- taskRunId
- eventType
- payloadJson
- sequence
- createdAt
```

After page refresh or SSE reconnect, the UI must reconstruct session messages, current tasks, current task runs, terminal states, available artifacts, diff cards, preview cards, deploy cards, and approval requests still waiting for user action.

## Worktree and Diff Design

P0 uses session-level worktree isolation:

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

`TaskRun.worktreePath` stores the resolved worktree path for traceability and equals `Session.worktreePath` in P0. Each TaskRun also records `baseRef` and `headRef` for diff collection. P1 may support task-run-level worktrees for advanced parallel execution.

### TaskRun baseRef/headRef Rules

P0 uses session-level worktrees, but each TaskRun owns its own diff boundary:

- Before each TaskRun starts, the system must record the current session worktree `baseRef`.
- `baseRef` should be the TaskRun-start git commit SHA or another explicit git ref that can be resolved later.
- After TaskRun execution ends, the system records `headRef`.
- `headRef` may be an execution-complete commit SHA, a temporary ref, or a working-tree snapshot marker when the worktree remains uncommitted.
- Diff collection must generate the TaskRun diff using that TaskRun's `baseRef`/`headRef` semantics.
- Follow-up changes in the same Session reuse the same session worktree but create a new TaskRun with a new `baseRef`.
- Retried TaskRuns create new records and must not overwrite previous TaskRun `baseRef` or `headRef` values.

The simplest P0 implementation is:

1. Before TaskRun execution, record `git rev-parse HEAD` as `baseRef`.
2. Let the adapter modify files in the session worktree.
3. Generate this run's diff with `git diff -p baseRef -- .` or an equivalent command rooted at the session worktree.
4. After execution, record the current HEAD or a working-tree snapshot marker as `headRef`.

Worktree constraints:
- Multiple sessions must never share the same worktree path.
- Worktree paths must be persisted.
- Worktree creation must use deterministic naming based on workspace/session identifiers.
- Worktree cleanup must be explicit and safe.
- Protected host paths must never be exposed to adapters.

Diff collection is backend-owned:
1. Ensure adapter execution has ended or reached an artifact collection point.
2. Run `git diff -p` inside the session worktree.
3. Collect changed files and stats from Git CLI.
4. Exclude `node_modules` from diff and protect it from agent edits.
5. Optionally run `git apply --check` against generated patch text where useful.
6. Store an `Artifact` of type `diff`.
7. Store `Diff` with `baseRef`, `headRef`, `patchText`, `changedFilesJson`, and `statsJson`.
8. Emit `artifact.diff.ready`.

The UI renders changed files, patch summary, expandable file-level changes, and Monaco Diff Editor for detailed inspection. Monaco is used for diff detail only, not as a general IDE.

## Preview Design

P0 supports exactly one demo stack: Vite React.

The preview runner:
- Starts the Vite React app inside the session worktree.
- Uses allowlisted commands only.
- Assumes dependencies were installed during setup.
- Must not run `pnpm install` during agent execution.
- Runs `pnpm dev --host 127.0.0.1 --port <port>`.
- Allocates or records the preview port.
- Performs a health check.
- Persists preview status.
- Emits `artifact.preview.ready` when healthy.
- Cleans up preview processes when the session is closed or reset.

The UI opens the preview in a right-side panel or iframe and can refresh after a second change. Preview processes must be bounded by session/task lifecycle. Unbounded background processes are not allowed.

Preview record requirements:
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

## Deploy Card Design

The deploy card is a P0 artifact view, not a full deployment platform. After preview succeeds, the backend creates a `Deployment` record and emits `artifact.deploy.ready`.

P0 can show one of two paths:
1. A real Vercel demo deploy if stable in the team's environment.
2. A mock deploy card if real deploy is unreliable.

The mock deploy card must still be backend-created and persisted as a `Deployment` record. It must not be a frontend-only hardcoded card. Deploy actions require approval. P0 does not support multiple deploy providers, deployment matrix, production release management, git push requirement, or unreviewed deploy.

## Permission Guardrails and Approval Design

P0 guardrails are simple but real:
- Use command allowlist.
- Block protected paths.
- Protect `.git/`, `.env`, `.env.*`, `secrets/`, `node_modules/`, and system paths.
- Disable network by default unless explicitly approved.
- Require approval for deploy actions.
- Require approval for push actions.
- Require approval for destructive file operations.
- Require approval for editing protected files.
- Require approval for non-allowlisted commands.

The system distinguishes product confirmation from security approval:

```text
product_confirmation
security_approval
```

Approval request payload:

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

The UI may render both approval types with the same card component, but the payload must distinguish them. Approval requests move the related Task and TaskRun into `waiting_approval` until approved, denied, expired, failed, or interrupted.

## Data Model Overview

P0 uses the following entities. No additional P0 domain entities should be introduced unless a task cannot satisfy the demo loop without them. `TaskRunEvent` is the only allowed support entity because it materially improves event recovery and debugging.

- User: `id`, `email`, `name`, `avatarUrl`, `createdAt`
- Workspace: `id`, `name`, `repoUrl`, `rootPath`, `defaultBranch`, `createdAt`
- Session: `id`, `workspaceId`, `title`, `sessionType`, `boundBranch`, `worktreePath`, `status`, `lastMessageAt`, `createdAt`, `updatedAt`
- Message: `id`, `sessionId`, `senderType`, `senderId`, `contentMd`, `messageKind`, `parentMessageId`, `streamState`, `createdAt`
- Agent: `id`, `name`, `role`, `adapterType`, `provider`, `defaultModel`, `systemPrompt`, `capabilitiesJson`, `permissionProfileJson`, `enabled`, `createdAt`, `updatedAt`
- Task: `id`, `sessionId`, `createdByMessageId`, `title`, `intentType`, `status`, `priority`, `planJson`, `dependsOnTaskIds`, `assignedAgentId`, `createdAt`, `updatedAt`
- TaskRun: `id`, `taskId`, `agentId`, `adapterRunId`, `state`, `startedAt`, `endedAt`, `worktreePath`, `baseRef`, `headRef`, `errorCode`, `errorMessage`, `metricsJson`, `createdAt`, `updatedAt`
- TaskRunEvent: `id`, `taskRunId`, `eventType`, `payloadJson`, `sequence`, `createdAt`
- Artifact: `id`, `taskRunId`, `artifactType`, `title`, `status`, `version`, `storageUri`, `metaJson`, `createdAt`, `updatedAt`
- Diff: `id`, `artifactId`, `baseRef`, `headRef`, `patchText`, `changedFilesJson`, `statsJson`, `createdAt`
- Preview: `id`, `artifactId`, `port`, `url`, `command`, `processId`, `healthStatus`, `statusReason`, `expiresAt`, `lastCheckedAt`, `createdAt`, `updatedAt`
- Deployment: `id`, `artifactId`, `provider`, `environment`, `commitSha`, `url`, `status`, `deployLogUri`, `createdAt`, `updatedAt`

## Real Implementation vs Mock Strategy

Real in P0:
- Session and task persistence.
- TaskRunEvent persistence and SSE replay/recovery.
- Session-level git worktree creation.
- CodexAdapter local CLI execution path.
- ScriptedMockAdapter file mutations.
- Git diff collection.
- Vite React preview startup.
- UI cards for plan, task states, diff, preview, approval, retry, interrupt, and deploy.

Mock or constrained in P0:
- Deploy can be mock-backed.
- Agent planning can use deterministic templates as long as visible tasks match user intent.
- ScriptedMockAdapter can simulate events, approvals, and errors, but it must create real file changes.
- The preview runner supports Vite React only.

P1/P2:
- ClaudeCodeAdapter.
- HumanAgentAdapter.
- Codex API/cloud task wrapper.
- PR creation.
- Docker sandbox.
- WebSocket.
- Provider marketplace.
- MCP marketplace.
- Enterprise controls.
- External Feishu/Slack integrations.
- Multi-user collaboration.
- Full deploy matrix.
- Arbitrary DAG builder.

## Risk and Mitigation

- [Risk] Real Codex CLI execution is unstable during demo -> Mitigation: keep ScriptedMockAdapter as a first-class fallback that modifies the demo repo and exercises the same diff/preview pipeline.
- [Risk] Scope expands into a full agent platform -> Mitigation: enforce P0/P1/P2 boundaries and only build features serving the 5-minute demo path.
- [Risk] Worktrees leak state across sessions -> Mitigation: use session-level worktrees, persist unique paths per session, and never reuse one worktree across multiple sessions.
- [Risk] Arbitrary command execution is unsafe -> Mitigation: allowlist commands, block protected paths, require approvals, disable network by default, and avoid arbitrary shell.
- [Risk] Preview runner becomes a framework matrix -> Mitigation: support Vite React only in P0.
- [Risk] SSE stream and database state diverge -> Mitigation: persist TaskRunEvent and canonical state before emitting events; reload canonical state after reconnect.
- [Risk] Monaco integration consumes frontend time -> Mitigation: use Monaco only for file-level diff detail.
- [Risk] Deploy exceeds P0 scope -> Mitigation: treat deploy as a backend-created artifact card and use mock deploy if real Vercel deploy is unstable.
- [Risk] Codex CLI behavior is misunderstood during implementation -> Mitigation: write feasibility spike results to AGENTS.md or docs/adapter-notes.md before implementing CodexAdapter.

## Migration Plan

1. Scaffold the fixed frontend/backend/database structure.
2. Add AGENTS.md so future coding agents follow the MVP guardrails.
3. Add SQLModel schema and seed one user, workspace, agents, and Vite React demo repo configuration.
4. Run a Codex CLI feasibility spike inside a session worktree and write results to AGENTS.md or docs/adapter-notes.md before CodexAdapter implementation.
5. Build workspace/session UI and session-level worktree binding.
6. Build persisted chat flow with SSE and TaskRunEvent replay.
7. Add mention parsing for `@orchestrator`, `@frontend`, `@backend`, and `@qa`.
8. Add structured orchestrator planning and task state transitions.
9. Add adapter interface with `getCapabilities()`.
10. Add ScriptedMockAdapter.
11. Add CodexAdapter local CLI happy path and normalized errors.
12. Add permission guardrails and approval payloads.
13. Add diff collection and diff UI.
14. Add preview runner backend skeleton and preview UI polish.
15. Add deploy card and mock deploy backend path.
16. Add interrupt, retry, and retry-with-fallback controls.
17. Write README and demo script.
18. Run final success and failure recovery demo rehearsals.

Rollback strategy for demo instability: use ScriptedMockAdapter, mock deploy card, and the deterministic Vite React demo repo path while preserving real git diff and real preview behavior.

## P0 Acceptance Checklist

- User can open the AgentHub UI locally.
- User can create and switch between at least three sessions.
- Each session has a distinct worktree.
- User can send `@orchestrator build a login page for the demo app`.
- Orchestrator creates 2-4 visible tasks.
- Task cards show assigned role agents.
- Task states update visibly in the chat stream.
- TaskRunEvents persist and support SSE recovery/replay.
- At least one task can execute through CodexAdapter local CLI.
- ScriptedMockAdapter can complete the same flow if Codex fails.
- Fallback flow modifies real files in the Vite React demo repo.
- Backend collects real `git diff -p` output.
- UI renders changed files and patch summary.
- User can expand diff details.
- Preview starts for the Vite React demo app with `pnpm dev --host 127.0.0.1 --port <port>`.
- Preview runner does not run dependency installation during agent execution.
- User can open preview in side panel or iframe.
- User can request a second small change in the same session.
- User can interrupt a running task.
- User can retry a failed or interrupted task.
- Approval card appears for risky or deploy actions with an ApprovalRequestPayload.
- Deploy card appears after preview succeeds.
- Mock deploy keeps the demo working when real deploy is unavailable.
- README explains local setup.
- Demo script includes one success path and one failure recovery path.

## Final Design Principle

AgentHub P0 should not try to be a complete agent platform. It should prove one sharp product claim:

```text
Coding agents become visible IM collaborators whose work produces verifiable artifacts.
```

Everything in P0 should serve that claim. Everything else should be deferred.
