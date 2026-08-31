# Design: Source structure modularization

## Constraints

- Each extraction is behavior-preserving and independently testable.
- FastAPI route paths, methods, dependencies, status codes, and response models
  remain unchanged.
- `app.main:app` remains the application entry point and composes routers.
- `plan_for_message` remains the public planning entry point.
- `WorkspaceShell` remains the exported page-level component.
- Existing tests may continue to import established public helpers until a
  focused compatibility change explicitly relocates them.

## Sequence

1. Extract agent directory, profile draft, runtime configuration, and memory
   settings endpoints from `main.py` into one cohesive router module.
2. Extract TaskRun, artifact, preview/deployment, and Session SSE route families
   without changing the durable event contract.
3. Split planning helpers by routing, intent classification, and task creation
   while keeping `plan_for_message` stable.
4. Split workspace-shell event/state orchestration from presentational sections.

The sequence reduces import and regression risk: API route families already
have endpoint-level tests, while planning and workspace-shell splits need
additional characterization before moving internal helpers.
