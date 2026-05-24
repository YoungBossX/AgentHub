## Context

AgentHub currently has a strong local coding workspace baseline:

- P6 proved bounded full-stack mini CRM execution through Orchestrator,
  Backend Agent, Frontend Agent, diff, review, preview, and mock deploy.
- P7 made planning, instructions, review, and platform mode target-aware
  through the Target Registry.
- P8 added dependency-aware scheduling and target locks.
- P9 added external local project workspace mode.
- P10 added heartbeat, stale lock cleanup, checkpoints, retry idempotency,
  failure propagation, conflict detection, and auditable recovery actions.

Deploy remains mock-only. Mock deploy is useful for demos, but it does not
prove that generated frontend output can be built, served, and opened as a real
staging artifact. P11 adds a real local staging deploy provider while
preserving production deploy as an explicit non-goal.

Key constraints:

- AgentHub remains a local single-user Agent Coding Workspace.
- Target Registry remains the source of truth for target path policy and
  runtime commands.
- Staging deploy must be clearly labeled staging, never production.
- Existing mock deploy behavior must remain available where needed.
- Failed deploys and blocked deploy gates must be recorded honestly.
- P11 must not introduce cloud tokens, external provider secrets, Docker, or
  production deployment.

## Goals / Non-Goals

**Goals:**

- Define a deploy provider abstraction suitable for mock and local staging
  providers.
- Add target-aware deploy/build configuration sourced from Target Registry.
- Add a local staging provider that builds a frontend target and serves the
  built output locally.
- Persist staging deploy status, URL, target metadata, source diff/review/
  preview references, and logs.
- Gate staging deploy on review, preview, and target policy safety.
- Preserve P6/P7/P8/P9/P10 baselines and mock deploy behavior.
- Rehearse a real staging deploy for built-in demo frontend or external Vite
  sample target.

**Non-Goals:**

- Production deploy.
- Cloud provider token management.
- Vercel, Netlify, Render, or other full cloud provider integration.
- Docker or Kubernetes.
- Domain management.
- Database hosting.
- Automatic rollback.
- Multi-user deploy approvals.
- Secrets storage or secret injection.
- Replacing preview with staging deploy.

## Decisions

### Decision: Add A Provider Interface Before Adding More Providers

P11 should introduce a narrow deploy provider interface:

```text
providerId
providerType
targetId
buildCommand
deployCommand
outputUrl
status
logs
```

The first real provider is `local_staging`; the existing mock path remains a
provider-compatible path rather than being removed.

Rationale: a provider interface keeps mock deploy, local staging, and any
future cloud deploy adapters from becoming separate ad hoc flows.

Alternative considered: directly add local staging behavior to the current
mock deploy service. Rejected because it would blur mock/staging semantics and
make future provider work harder.

### Decision: Target Registry Owns Deploy Configuration

Target Registry should expose deploy-related metadata such as:

```text
buildCommand
stagingOutputDir
stagingServeCommand
stagingBaseUrl / generated URL policy
deployProviderIds
```

External targets may be deployable only when their analyzer/registration
metadata has enough information to build and serve output. Unknown targets must
fail honestly or require explicit configuration.

Rationale: P7 made target metadata the source of truth for paths, commands, and
policy. Deploy config belongs with the target.

Alternative considered: store deploy config on sessions or task plans only.
Rejected because it would scatter target-specific deployment rules.

### Decision: Local Staging Provider Builds Then Serves Static Output

For Vite-like frontend targets, local staging should:

1. verify deploy gates;
2. run the configured build command in the target root or session worktree
   scope;
3. verify the configured output directory exists;
4. serve that output directory on a reserved local port;
5. perform a health check against the generated staging URL;
6. record status, logs, URL, provider, target, and source artifact links.

Rationale: this gives a real staging URL without requiring cloud accounts,
tokens, Docker, or production infrastructure.

Alternative considered: use Vite dev server as staging. Rejected because P11
needs a deployment artifact distinct from preview.

### Decision: Deploy Status Is Artifact-backed And Event-backed

P11 should persist both:

- a deployment/artifact record for summary and UI cards;
- TaskRunEvent or equivalent event records for status changes and logs.

Statuses:

```text
queued
building
deploying
ready
failed
cancelled
```

Rationale: artifact records make staging deploy visible in the current
artifact pipeline; events preserve trace and SSE compatibility.

Alternative considered: only store logs in process memory. Rejected because
deploy evidence must survive refresh and audit review.

### Decision: Deploy Gates Are Conservative

Staging deploy must not proceed when:

- latest review for the source diff is failed;
- preview is failed/unhealthy when a preview prerequisite is configured;
- target policy violation exists in review or scheduler metadata;
- target is not deployable by registry config;
- requested environment is production.

Warnings may be allowed only when explicitly classified as non-blocking and
documented by the provider result.

Rationale: P10 increased recovery safety; P11 should not reintroduce unsafe
execution by deploying unreviewed or policy-violating output.

Alternative considered: let users deploy with warnings by default. Deferred
until a future approval model exists.

## Risks / Trade-offs

- **Risk: local static serving is mistaken for production.** Mitigation:
  label provider/environment as `local_staging` / `staging` everywhere and
  reject production deploy requests.
- **Risk: build commands execute unsafe operations.** Mitigation: read commands
  from Target Registry, keep them allowlisted, and reject unknown commands.
- **Risk: external projects have varied output directories.** Mitigation:
  require analyzer/registration confidence or explicit deploy config.
- **Risk: long-running staging servers leak processes.** Mitigation: track
  process IDs, expiry, stop/cancel actions, and cleanup in later tasks.
- **Risk: failed deploys hide useful diagnostics.** Mitigation: persist logs
  and failed status artifacts.
- **Risk: P11 over-expands into cloud deployment.** Mitigation: keep cloud
  providers, tokens, domains, Docker, and production deploy non-goals.

## Migration Plan

1. Add provider abstractions and schemas while preserving current mock deploy.
2. Extend Target Registry metadata for staging deploy config in a backward-
   compatible way.
3. Add local staging provider behind explicit staging deploy calls.
4. Add deploy gates before enabling UI affordances.
5. Rehearse with built-in demo frontend or external Vite sample target.

Rollback strategy: keep mock deploy intact. If staging deploy is unavailable,
AgentHub can continue to expose mock deploy and preview while reporting staging
deploy as unsupported or failed.

## Open Questions

- Should local staging serving reuse the preview process runner or a separate
  static file server runner?
- Should build logs be stored as a deployment artifact, TaskRunEvent stream, or
  both in the first implementation?
- Should external deploy config be inferred only by analyzer or also editable
  through registration APIs in P11?
- What default expiry should local staging servers use?
