## 1. Provisioning Artifacts

- [x] 1.1 Add generic selected-folder provisioning tests for scaffold, target registration, active session targets, and non-empty folder rejection.
- [x] 1.2 Implement provisioning service functions that create a minimal Vite React/FastAPI skeleton and `agenthub.project.json`.
- [x] 1.3 Add backend schemas/API endpoint for applying a provisioning plan to a selected session and folder.

## 2. Planner Integration

- [x] 2.1 Add planner tests proving multiple simple fullstack prompts create runnable frontend/backend tasks against provisioned targets.
- [x] 2.2 Update planner fallback/routing to use active provisioned targets instead of rehearsal/demo assumptions.
- [x] 2.3 Ensure PlanValidator accepts provisioned target paths while still rejecting role/path/command violations.

## 3. Runtime Reliability Integration

- [x] 3.1 Add regression tests that new-project TaskRuns enter the durable run engine path and expose queue/lock diagnostics.
- [x] 3.2 Remove or quarantine direct adapter execution for fallback paths that can bypass queue/target lock behavior.
- [x] 3.3 Verify terminal states release target locks for provisioned frontend/backend targets.

## 4. Frontend API/UI

- [x] 4.1 Add frontend API types and client function for selected-folder provisioning.
- [x] 4.2 Add target settings UI flow for provisioning a new fullstack project from the selected folder without Pomodoro-specific text.
- [x] 4.3 Add or update frontend tests for the provisioning API call and user-visible error details.

## 5. Documentation and Verification

- [x] 5.1 Update `docs/change-log.md` and `docs/project-state.md` with the generic new-project runtime boundary.
- [x] 5.2 Run focused API and web tests for provisioning, planner routing, target locks, and API client behavior.
- [x] 5.3 Validate the OpenSpec change with `openspec validate agenthub-generic-new-project-runtime --strict`.

## 6. Evidence Reliability Follow-up

- [x] 6.1 Add regression coverage for non-Git external project Diff/Review collection using pre-run file snapshots.
- [x] 6.2 Add empty-baseline compatibility for legacy non-Git external runs created before file snapshots existed.
- [x] 6.3 Record Diff/Review artifact collection failures as TaskRunEvents and classify them in run diagnostics.
