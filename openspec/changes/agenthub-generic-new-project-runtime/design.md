## Context

AgentHub already has most of the pieces needed for a real new-project path: local folder browsing, external target registration, ProjectProfile summaries, PlanValidator target checks, durable Run Engine, session queue, target locks, provider gateway evidence, and diagnostics. The missing piece is integration. `project_provisioning.py` currently returns a dry-run plan; planner fallbacks still prefer existing rehearsal targets; and LLM task plans are validated against already registered targets, so new target drafts are not executable.

The target competition flow is generic: a user chooses an empty folder, then asks for a simple fullstack app. AgentHub must scaffold a safe frontend/backend boundary, register targets, set the session active targets, and create runnable tasks. Pomodoro is only an acceptance example.

## Goals / Non-Goals

**Goals:**

- Convert a user-selected empty folder into a controlled fullstack project root.
- Generate generic Vite React and FastAPI skeletons with no business-specific code.
- Register frontend/backend targets with ProjectProfiles and protected path defaults.
- Activate those targets for the selected session.
- Route simple fullstack app requests to frontend/backend runnable tasks using the new targets.
- Keep all coding execution on the durable Run Engine path.
- Cover at least three different fullstack app prompts through the same path.

**Non-Goals:**

- Do not hardcode Pomodoro or any other app domain.
- Do not support arbitrary stacks in this change; default stacks are Vite React and FastAPI.
- Do not perform dependency installation automatically.
- Do not add Docker sandbox, WebSocket, production deploy, provider marketplace, or multi-user collaboration.
- Do not claim real provider success when Claude/Codex fail or fallback is used.

## Decisions

### Selected Folder Is The Project Root

The selected empty folder becomes `projectRoot`. AgentHub creates `frontend/`, `backend/`, `docs/`, `README.md`, and `agenthub.project.json` inside it. Frontend and backend are registered as separate external targets rooted at `projectRoot/frontend` and `projectRoot/backend`.

Alternative considered: create project content under a default rehearsal folder. That preserves demo behavior but does not match the user's explicit project boundary and makes real use confusing.

### Provisioner Owns Skeleton, Agents Own Business Logic

AgentHub creates deterministic minimal skeletons only: build files, app entrypoints, health endpoints, and docs placeholders. The orchestrator/frontend/backend agents implement the requested business logic later.

This avoids asking Claude/Codex to bootstrap from an empty directory and avoids task-specific provisioning branches.

### Generic Path Policy

Provisioned targets use broad but scoped allowed paths (`*` for each target root) plus protected denied paths inherited from external target defaults. The target root itself is already `frontend` or `backend`, so wildcard permission does not grant access outside the role boundary.

### Planner Uses Active New-Project Targets

After provisioning, session active targets are set to the new frontend/backend target IDs. Existing external-target planner fallback can then create generic runnable frontend/backend tasks. For LLM paths, task validation remains against registered targets, preserving PlanValidator as the hard boundary.

### Durable Run Engine Remains The Execution Path

No new direct adapter execution path is added. New-project TaskRuns are regular TaskRuns and must enter existing scheduling, session queue, target lock, provider gateway, supervisor, heartbeat, timeout, and diagnostics flows.

## Risks / Trade-offs

- **Provisioned skeleton feels opinionated** -> Keep it minimal and stack-scoped; business code remains agent-owned.
- **Wildcard allowed paths are broader than old safe-file lists** -> The target root is role-scoped and denied paths still block `.git`, `.env*`, `node_modules`, secrets, virtualenvs, build outputs, and caches.
- **Planner may still return assistant_reply** -> Fallback routing must detect safe new/fullstack app requests and create runnable tasks against active provisioned targets.
- **Provider failures can still block coding** -> This change relies on existing provider gateway evidence and diagnostics; it must surface failures honestly rather than masking them.

## Migration Plan

This is additive. Existing demo and external target flows remain supported. Existing dry-run planning remains available through `/project-provisioning/plan`; a new apply/provision path performs scaffold/register/activate for selected folders. If provisioning fails, no agent execution starts and the user receives a concrete error.
