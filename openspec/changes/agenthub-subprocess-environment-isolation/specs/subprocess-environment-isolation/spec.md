# Subprocess Environment Isolation

## ADDED Requirements

### Requirement: Project-controlled subprocesses receive no control-plane secrets

Preview, staging build, and local static-server subprocesses SHALL receive an
explicit least-privilege environment that excludes provider credentials,
database configuration, and private AgentHub settings. The Claude CLI planner
SHALL receive only the Claude provider environment and portable runtime values.

#### Scenario: A project process starts while the API environment contains secrets

- **WHEN** AgentHub starts a preview, staging build, or static-server child
- **THEN** the child receives the portable runtime variables it requires
- **AND** provider keys, tokens, passwords, secrets, and private AgentHub
  configuration are absent
- **AND** explicitly public frontend variables remain available.

#### Scenario: The Claude CLI planner starts while unrelated secrets are present

- **WHEN** AgentHub invokes the Claude CLI planner
- **THEN** the planner receives Claude credentials and configuration only
- **AND** OpenAI/Codex and AgentHub control-plane secrets are absent.

### Requirement: Real adapters receive only their selected provider environment

Each real coding adapter and its CLI availability/version probe SHALL receive
the shared portable runtime environment plus only its own provider credential
and configuration variables.

#### Scenario: Multiple provider credentials exist on the host

- **WHEN** AgentHub starts Codex or Claude Code, including a CLI version probe
- **THEN** Codex does not receive Claude credentials
- **AND** Claude Code does not receive OpenAI/Codex credentials
- **AND** neither adapter receives unrelated planner or AgentHub secrets.

### Requirement: Child output evidence is secret-redacted

AgentHub SHALL redact exact sensitive environment values and secret assignments
before child-process output is persisted or returned as adapter, preview, or
deployment evidence.

#### Scenario: A child emits a sensitive value

- **WHEN** adapter output, preview diagnostics, or build logs contain a configured
  secret value or a secret assignment
- **THEN** persisted and API-visible evidence contains a redaction marker
- **AND** ordinary diagnostic text remains readable.
