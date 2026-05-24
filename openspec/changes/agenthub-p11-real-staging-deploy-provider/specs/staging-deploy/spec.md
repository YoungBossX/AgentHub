## ADDED Requirements

### Requirement: Deploy Provider Abstraction

The system MUST define a deploy provider abstraction for staging and mock
deployment paths.

#### Scenario: Deploy provider result records standard metadata

- **WHEN** a deploy provider creates a deploy result
- **THEN** the result MUST include provider ID, provider type, target ID, build
  command, deploy command, output URL when available, status, and logs.

#### Scenario: Existing mock deploy remains available

- **WHEN** a task continues to use the mock deploy path
- **THEN** the system MUST preserve mock deploy behavior
- **AND** the deploy artifact MUST remain clearly labeled as mock.

#### Scenario: Unknown provider is requested

- **WHEN** a deploy request references an unknown provider ID
- **THEN** the system MUST reject the request honestly
- **AND** it MUST NOT create a successful deployment artifact.

### Requirement: Target-aware Deploy Configuration

The system MUST read staging deploy configuration from the Target Registry.

#### Scenario: Built-in demo frontend has staging deploy configuration

- **WHEN** staging deploy is requested for the built-in demo frontend target
- **THEN** the system MUST resolve build command, output directory, serve
  command or serving strategy, allowed paths, denied paths, and provider
  availability from the Target Registry.

#### Scenario: External frontend target has deploy configuration

- **WHEN** staging deploy is requested for a registered external frontend
  target
- **THEN** the system MUST resolve deploy metadata from that external target
  registration or analyzer result
- **AND** the system MUST apply the external target's allowed and denied path
  policy.

#### Scenario: Target lacks deploy configuration

- **WHEN** a target does not have enough deploy configuration for staging
  deploy
- **THEN** the system MUST return an unsupported or failed deploy result
- **AND** the system MUST NOT guess unsafe build or serve commands.

### Requirement: Local Staging Deploy Provider

The system MUST provide a local staging deploy provider that builds and serves
frontend output locally.

#### Scenario: Local staging deploy succeeds

- **WHEN** deploy gates pass for a deployable frontend target
- **THEN** the local staging provider MUST run the configured build command
- **AND** it MUST serve the configured output directory locally
- **AND** it MUST generate a real local staging URL
- **AND** it MUST verify the staging URL is reachable
- **AND** it MUST record a ready staging deployment artifact.

#### Scenario: Build command fails

- **WHEN** the configured build command exits with failure
- **THEN** the staging deploy MUST be marked failed
- **AND** build logs MUST be recorded
- **AND** the system MUST NOT claim a ready staging URL.

#### Scenario: Output directory is missing

- **WHEN** the build command completes but the configured output directory is
  missing
- **THEN** the staging deploy MUST be marked failed
- **AND** the failure reason MUST name the missing output directory.

#### Scenario: Staging server is cancelled

- **WHEN** a user or cleanup action cancels a running staging deployment
- **THEN** the deploy status MUST become cancelled
- **AND** the local serving process MUST be stopped when tracked.

### Requirement: Deploy Logs And Status Artifact

The system MUST persist staging deploy status, logs, and source artifact
metadata.

#### Scenario: Deploy status transitions are recorded

- **WHEN** a staging deploy progresses
- **THEN** status transitions MUST use `queued`, `building`, `deploying`,
  `ready`, `failed`, or `cancelled`
- **AND** each transition MUST be recorded in deploy artifact metadata or
  TaskRunEvent logs.

#### Scenario: Deploy logs are visible

- **WHEN** a staging deploy runs build or serving steps
- **THEN** the system MUST record stdout, stderr, command exit code, and
  high-level status messages without exposing secrets.

#### Scenario: Deploy artifact links source evidence

- **WHEN** a staging deploy artifact is created
- **THEN** it MUST reference the target ID, source TaskRun, source diff
  artifact when available, review artifact when available, and preview when
  available.

### Requirement: Deploy Gate

The system MUST gate staging deploy on review, preview, and target policy
safety.

#### Scenario: Review failed

- **WHEN** the latest relevant review for the source diff has failed
- **THEN** staging deploy MUST be blocked
- **AND** the deploy result MUST record that review failure blocked deployment.

#### Scenario: Preview failed

- **WHEN** a preview prerequisite exists and preview health is failed or
  unhealthy
- **THEN** staging deploy MUST be blocked
- **AND** the deploy result MUST record that preview health blocked
  deployment.

#### Scenario: Target policy violation exists

- **WHEN** review, scheduler metadata, or target policy evidence shows a
  denied-path or platform-code violation
- **THEN** staging deploy MUST be blocked
- **AND** the system MUST NOT serve the output as ready.

#### Scenario: Production deploy is requested

- **WHEN** a deploy request asks for production or a production-like
  environment
- **THEN** P11 MUST reject the request
- **AND** it MUST NOT run build or deploy commands.

### Requirement: P11 Rehearsal And Baseline Preservation

The system MUST rehearse real staging deploy behavior and preserve existing
AgentHub baselines.

#### Scenario: Built-in or external frontend staging rehearsal succeeds

- **WHEN** P11 is rehearsed against the built-in demo frontend or an external
  Vite sample target
- **THEN** the staging deploy MUST produce a reachable URL
- **AND** logs, status, target metadata, and deployment artifact MUST be
  recorded.

#### Scenario: Existing baselines remain intact

- **WHEN** P11 freeze review is performed
- **THEN** P6 bounded full-stack execution, P7 Target Registry policy, P8
  scheduler/locks, P9 external workspace mode, and P10 robustness behavior MUST
  remain operational.

#### Scenario: Out-of-scope deploy capability is requested

- **WHEN** a request requires production deploy, cloud provider token
  management, Docker/Kubernetes, domain management, database hosting,
  automatic rollback, or multi-user deploy approvals
- **THEN** P11 MUST reject or defer the request honestly.
