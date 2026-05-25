# P11 Real Staging Deploy Provider Freeze Review

**Date:** 2026-05-25

## Result

P11 is ready to freeze as the Real Staging Deploy Provider phase.

AgentHub now preserves the existing mock deploy path and adds a real,
target-aware local staging deploy provider for frontend targets. The staging
provider builds the target, serves the built output directory locally, records
logs/status/source metadata, and blocks unsafe staging deploy requests.

## Rehearsal Evidence

The freeze rehearsal used an in-memory AgentHub API database and the built-in
`demo-frontend` target. It did not run Claude Code or Codex.

| Field | Evidence |
|---|---|
| Provider | `local_staging` |
| Environment | `staging` |
| Final status | `ready` |
| Target ID | `demo-frontend` |
| Build command | `pnpm build` in `apps/demo` |
| URL health | `http://127.0.0.1:62050` returned built `index.html` |
| Deployment ID | `8c776325-e98a-435c-ab1c-6a2d71c6946f` |
| Artifact ID | `949c9411-98c6-4e0c-978f-96bc7ac88f0c` |
| TaskRun ID | `d2eb142d-b2cb-4240-ab0b-bf08ce345195` |
| Source preview ID | `0385ed01-06da-46dc-bae9-5f372a8eebb9` |
| Source diff artifact ID | `5e6aa0f3-fd5f-4baa-b6d7-cc609cfff50e` |
| Source review artifact ID | `13c6e7b7-62f6-4f57-9d8a-ae12ebe123d4` |
| Status history | `queued -> building -> deploying -> ready` |
| Logs | Build output, static serving URL, and ready status recorded in artifact metadata |

The rehearsal initially exposed a macOS compatibility blocker: the local static
server used the command name `python`, which was not present in the current
environment. P11-6 fixed this by using the current interpreter path from
`sys.executable`, with a regression test.

## Baseline Coverage

P11 freeze validation preserves:

- P6 bounded full-stack mini CRM execution tests through existing API coverage;
- P7 Target Registry and permissioned execution tests;
- P8 dependency scheduler and target lock tests;
- P9 external workspace registration, execution evidence, and review tests;
- P10 robustness, recovery, conflict, and retry tests;
- existing mock deploy compatibility.

## Caveats

- Staging deploy is local-only and explicitly not production.
- Cloud providers, provider token management, domains, Docker/Kubernetes,
  rollback, and multi-user deploy approvals remain out of scope.
- The local staging provider records status history as provider metadata and
  deployment events; it does not yet provide process lifecycle UI controls.
- The freeze rehearsal used deterministic API/service setup, not a full
  browser-click staging deploy flow.

## Recommended Tag

`p11-real-staging-deploy-provider-freeze`
