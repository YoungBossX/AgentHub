## Context

P8 is frozen. AgentHub now has a bounded local full-stack execution loop,
registry-aware target permissions, and scheduler protection:

```text
requirement -> Orchestrator -> app contract / tasks -> target-aware execution
-> diff -> review -> preview when supported -> mock deploy
```

The current target universe is still mostly built into AgentHub:

- `demo-frontend` points to `apps/demo`;
- `demo-backend` points to `apps/demo-api`;
- `agenthub-platform` protects the AgentHub control plane.

P9 extends this model so a local project outside those built-in demo targets
can be registered, analyzed, selected, and operated on as a first-class
AgentHub workspace target.

## Goals / Non-Goals

**Goals:**

- Register a local external project root as a first-class AgentHub workspace
  target.
- Analyze common project layouts and infer project type, framework, package
  manager, safe commands, and safe allowed paths.
- Require explicit user confirmation or configuration when analysis is
  uncertain.
- Represent external targets through the same Target Registry shape consumed by
  planner, instruction builder, review, and scheduler.
- Allow `@frontend`, `@backend`, `@qa`, `@review`, and Orchestrator-created
  tasks to operate on selected external targets.
- Preserve original user requests in agent instructions.
- Let Claude Code / Codex perform meaningful coding work inside explicit
  external allowed paths.
- Collect external evidence: git diff, check/test/build output, and preview URL
  when configured.
- Review external changes for path safety and command evidence honesty.
- Rehearse with a local sample external project while preserving P6/P7/P8.

**Non-Goals:**

- Cloud repo import.
- Multi-user project sharing.
- Production deployment.
- Docker sandboxing.
- Provider marketplace.
- PR creation.
- Arbitrary unrestricted filesystem access.
- Enterprise RBAC.
- Full multi-tenant workspace system.
- External IM integration.
- Payment/auth/multi-tenant app generation.

## External Workspace Model

An external workspace registration should persist enough metadata for safe
execution without making the user's home directory or arbitrary filesystem
available to agents.

Suggested fields:

```text
targetId
workspaceId
name
rootPath
projectType
detectedFramework
packageManager
allowedPaths
deniedPaths
devCommand
testCommand
checkCommand
buildCommand
previewCommand
baseUrl
allowedAgents
requiresApproval
analysisStatus
analysisWarnings
createdAt
updatedAt
```

The first implementation may store this in SQLite with a dedicated
`ExternalProjectTarget` table or extend an existing target metadata table if
one exists by then. The runtime Target Registry should expose both built-in and
external targets through one read API.

## Project Analyzer

The analyzer should inspect the project root without installing dependencies or
executing arbitrary commands.

Inputs:

```text
rootPath
user-provided target name
optional user command overrides
optional user allowed-path overrides
```

Detection sources:

- `package.json`;
- `vite.config.*`;
- `next.config.*`;
- `pyproject.toml`;
- `requirements.txt`;
- `src/`, `app/`, `pages/`, `tests/`, `test/`;
- common backend entry points such as `main.py`, `app/main.py`,
  `server.ts`, `src/server.ts`;
- lockfiles such as `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`,
  `uv.lock`, `poetry.lock`.

Initial project types:

- `vite-react`;
- `nextjs`;
- `fastapi`;
- `node-api`;
- `python-package`;
- `unknown`.

The analyzer should infer:

- `packageManager`: `pnpm`, `npm`, `yarn`, `uv`, `poetry`, `pip`, or
  `unknown`;
- safe default `checkCommand`, `testCommand`, `buildCommand`, and
  `previewCommand` when present in config/scripts;
- allowed source paths such as `src`, `app`, `pages`, `components`,
  `tests`, or backend app package folders;
- denied paths that always include `.env`, `.env.*`, `secrets`, `.git`,
  `node_modules`, `.venv`, `dist`, `build`, `.next`, coverage output, and
  generated dependency directories.

If the analyzer cannot confidently infer safe defaults, it should produce
`analysisStatus: needs_confirmation` and require user confirmation or explicit
configuration before execution.

## Target Registry Integration

P9 should not introduce a parallel external-target mechanism. External targets
must be adapted into the existing Target Registry model so downstream code can
use the same metadata shape:

```text
targetId
name
type
root
allowedPaths
deniedPaths
allowedAgents
devCommand
testCommand
checkCommand
buildCommand
previewCommand
baseUrl
requiresPlatformMode
requiresApproval
relatedTargetIds
```

Built-in targets remain static. External targets are dynamic and persisted.
Registry lookup should merge built-in targets and registered external targets
for the current workspace/session context.

Target locks from P8 apply to external target IDs. Same-target write tasks must
remain serial.

## Instruction Builder

External-target instructions must stop assuming demo paths.

Role-specific expectations:

- Frontend:
  - use external target root and allowed paths;
  - use detected framework and package manager;
  - run only configured check/test/build commands when instructed;
  - use configured preview command only when available.
- Backend:
  - use external backend target root and allowed paths;
  - do not edit AgentHub `apps/api` unless explicitly targeting
    `agenthub-platform`;
  - preserve configured API entry points and tests.
- QA / Review:
  - inspect external diffs and command evidence;
  - report failed commands honestly;
  - detect denied path edits.
- Manager / Orchestrator:
  - route normal requests to selected external targets when an external
    workspace is active;
  - ask clarification when multiple external targets could apply;
  - reject unsupported or unsafe requests honestly.

Every instruction must preserve the original user request and include the
target metadata, allowed paths, denied paths, selected artifact context, latest
diff, scheduler state, and validation expectations where available.

## External Task Execution

P9 should support both explicit assignment and Orchestrator planning:

- `@frontend` creates a frontend task against the active external frontend
  target.
- `@backend` creates a backend task against the active external backend target.
- `@qa` and `@review` create read-oriented review tasks against external
  targets and evidence.
- no-mention messages route to Orchestrator, which decides whether to create
  external tasks, ask clarification, or reject unsupported work.

Adapter execution boundaries:

- `CodexAdapter` and `ClaudeCodeAdapter` run only inside the assigned external
  target worktree/root boundary.
- Agents may edit only explicit allowed paths.
- Agents may not edit denied paths.
- Agents may not escape into system directories or the user's home directory
  unless that exact registered root is confirmed and allowed paths are still
  constrained.

## Evidence Pipeline

External project evidence should be capability-based rather than assuming every
project is previewable.

Evidence types:

- git diff artifact;
- check command output;
- test command output;
- build command output;
- preview URL / health when preview is configured;
- review artifact summarizing path policy and command evidence.

Failed commands must be stored as failed evidence and surfaced to review/UI.
They must not be converted into success just because a diff exists.

Mock deploy remains a built-in demo behavior. P9 should not add production
deploy for external projects.

## Review Policy

External review must check:

- changed files stay within allowed paths;
- denied paths are untouched;
- `.env`, `.env.*`, `secrets`, `.git`, `node_modules`, `.venv`, generated
  dependency/build directories, and lock-protected control-plane paths are not
  modified;
- command evidence exists when the target has configured check/test/build
  commands;
- failed check/test/build commands produce warning or failed review status;
- review does not claim real Claude/Codex success without TaskRun evidence.

Review remains advisory unless a later change adds blocking approval gates.

## UI / UX

The first P9 UI should be operational, not a marketing page:

- register/select external local project;
- show analyzer result and required confirmation;
- show target metadata: root, project type, detected framework, allowed paths,
  denied paths, commands, package manager;
- show active external target in chat/task surfaces;
- show evidence cards for diff/check/test/build/preview/review when present;
- show scheduler states and target locks for external targets using the P8 UI
  surfaces.

## Risks / Trade-offs

- **Risk: arbitrary filesystem mutation.** Mitigation: require explicit
  registration, reject home/system roots by default, and require allowed paths.
- **Risk: analyzer infers unsafe commands.** Mitigation: prefer
  `needs_confirmation` when uncertain; never install dependencies or run
  arbitrary commands during analysis.
- **Risk: external projects vary widely.** Mitigation: start with common
  Vite/Next/FastAPI/Node/Python patterns and treat unknown projects as
  configurable but not auto-runnable.
- **Risk: command execution expands attack surface.** Mitigation: command
  allowlisting per target, no shell interpolation, scoped working directory,
  and honest failed evidence.
- **Risk: breaking built-in demo baseline.** Mitigation: keep built-in target
  behavior unchanged and run P6/P7/P8 regression validation during P9 freeze.

## Migration Plan

1. Persist external target registration and analyzer results.
2. Merge external targets into Target Registry reads.
3. Teach planner and instruction builder to use active external targets.
4. Add external TaskRun/evidence command artifacts.
5. Extend review and scheduler for external targets.
6. Add UI registration and evidence display.
7. Rehearse with a local sample external project and verify P6/P7/P8 baseline.

Rollback strategy: disable external target selection while preserving built-in
Target Registry entries and P8 scheduler behavior.
