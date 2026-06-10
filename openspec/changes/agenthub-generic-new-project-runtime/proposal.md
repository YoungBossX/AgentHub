## Why

AgentHub's real-project usability is still constrained by demo-era assumptions: new project setup can be planned but not executed end to end, planner output still expects pre-registered targets, and selected empty folders do not become a reliable project boundary for frontend/backend agents. Competition use needs a generic path where a user selects an empty folder and AgentHub can safely build a simple fullstack app there without task-specific hardcoding.

## What Changes

- Add a generic empty-folder new project runtime that provisions a selected folder into a controlled fullstack project root.
- Create safe Vite React frontend and FastAPI backend scaffolds without business-specific logic.
- Register frontend/backend external targets and ProjectProfiles from the provisioned folder.
- Set the active session frontend/backend targets after provisioning.
- Let planner fallback and LLM task plans create runnable frontend/backend tasks against the provisioned targets.
- Keep path safety generic: allow normal project files inside the selected root while still denying protected paths and project-root escapes.
- Ensure new-project coding tasks use the durable run engine, session queue, target locks, provider gateway evidence, and diagnostics.
- Add acceptance coverage with multiple simple fullstack app prompts, not a Pomodoro-specific branch.

## Capabilities

### New Capabilities
- `generic-new-project-runtime`: User-selected empty folders can become controlled fullstack project roots with provisioned targets, ProjectProfiles, runnable tasks, and reliable execution.

### Modified Capabilities
- `project-profile-boundary`: ProjectProfile provisioning changes from dry-run-only planning to a safe scaffold/register/activate path for selected empty folders.
- `durable-run-engine`: New-project TaskRuns must use the durable execution path and must not regress lock release, interrupt, timeout, or diagnostics behavior.

## Impact

- Backend API: project provisioning request/response schemas, provisioning service, external target registration, session target selection, planner routing.
- Planner/validation: task graph target validation against newly provisioned frontend/backend targets and generic fallback task creation.
- Frontend API/UI: optional helper for provisioning selected folders from the target settings flow.
- Tests: provisioning API, planner routing, PlanValidator target compatibility, run-engine/lock regressions.
- Docs: project state/change log and OpenSpec tasks.
