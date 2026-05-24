## Why

P10 made AgentHub safer for local and external project execution, but deploy is
still mock-backed. AgentHub can generate, review, preview, validate, and record
changes, yet it cannot produce a real staging deployment artifact that a user
can open as a deployed build.

P11 adds a real, target-aware staging deploy path while keeping production
deploy explicitly out of scope.

## What Changes

- Add a deploy provider abstraction for staging deploy providers with provider
  ID, provider type, target ID, build command, deploy command, output URL,
  status, and logs.
- Read staging deploy/build configuration from the Target Registry for built-in
  demo frontend and registered external frontend targets.
- Add a local staging deploy provider that runs an allowed build command,
  serves the built output directory locally, generates a reachable staging URL,
  and records a real staging deployment artifact.
- Add deploy log and status artifacts with `queued`, `building`, `deploying`,
  `ready`, `failed`, and `cancelled` states.
- Add deploy gates so staging deploy does not run when review failed, preview
  failed, or target policy violations exist.
- Preserve existing mock deploy behavior where it is still needed for legacy
  demo and fallback paths.
- Rehearse P11 against a built-in demo frontend or external Vite sample target
  and verify URL reachability, logs, artifacts, and P6/P7/P8/P9/P10 baselines.

## Capabilities

### New Capabilities

- `staging-deploy`: Target-aware real staging deploy provider, deploy
  configuration, deploy gates, status/log artifacts, local staging URL
  serving, and freeze rehearsal.

### Modified Capabilities

None. P11 introduces a staging deploy capability while preserving existing
mock deploy behavior and existing preview/deploy baseline contracts.

## Impact

Expected implementation impact when P11 is later applied:

- Backend:
  - deploy provider interface and provider selection;
  - target-aware deploy/build config sourced from Target Registry;
  - local staging build and static serving service;
  - deploy status/log artifact persistence;
  - deploy gates against review, preview, target policy, and production deploy
    prohibition;
  - API updates for staging deploy creation/list/read where needed.
- Frontend:
  - staging deploy artifact cards/status display;
  - deploy log/status visibility;
  - clear staging labeling distinct from mock and production.
- Target Registry:
  - staging build/deploy/output metadata for built-in demo frontend and
    external frontend targets where configured.
- Runtime:
  - only explicit allowlisted local build/serve commands;
  - no cloud deploy, production deploy, token management, Docker/Kubernetes,
    domain management, database hosting, automatic rollback, or multi-user
    deploy approvals.
