# Current Baseline Delivery Readiness

## ADDED Requirements

### Requirement: The Windows Codex application entrypoint is allowlisted exactly

The command guard SHALL accept the exact `codex.exe` basename used by the
Windows provider health probe and SHALL continue to reject executable
lookalikes.

#### Scenario: The health-probed Windows binary starts through the adapter

- **GIVEN** `CODEX_CLI_PATH` resolves to a Windows path ending in `codex.exe`
- **WHEN** `CodexAdapter` submits its existing sandboxed execution command
- **THEN** the command guard accepts the runtime entrypoint
- **AND** a name such as `codex-wrapper.exe` remains outside the allowlist.

### Requirement: Windows Preview launches the portable pnpm command

The Preview runner SHALL retain `pnpm dev` as portable evidence and SHALL
resolve only its exact Windows launcher to `pnpm.cmd` before process creation.

#### Scenario: A Vite Preview starts on Windows

- **GIVEN** the sanitized Preview PATH contains `pnpm.cmd`
- **WHEN** the service starts its canonical `pnpm dev` command
- **THEN** the Windows process uses the resolved `pnpm.cmd` launcher
- **AND** evidence still records `pnpm dev`
- **AND** stopping the Preview terminates the Windows launcher process tree and
  removes its runner-owned temporary log
- **AND** non-pnpm commands and non-Windows platforms remain unchanged.

### Requirement: Delivery readiness is backed by a fresh successful real TaskRun

Before the current baseline is declared ready for remote delivery, the system SHALL
complete one bounded coding TaskRun through the public workflow using the
real local Codex provider against an isolated registered external target. The
same run SHALL pass final scope validation and produce persisted Diff and Review
artifacts. A healthy Preview SHALL be started and stopped through the public
API.

#### Scenario: Current real provider workflow completes within its boundary

- **GIVEN** a fresh external Git repository with explicit allowed and denied
  paths, a fresh rehearsal database, active memory items, and a refreshed
  session snapshot
- **WHEN** a bounded frontend request is sent through the public message route
- **THEN** Planner, scheduler, scope validation, `CodexAdapter`, Diff, Review,
  and Preview paths execute for one traceable TaskRun
- **AND** the persisted run ends as `completed`
- **AND** exact instruction hashes, memory IDs, provider events, scope evidence,
  artifact IDs, and changed files are saved.

#### Scenario: Historical recovered evidence or fallback is observed

- **WHEN** only decoder-recovered historical evidence, a failed persisted run,
  or ScriptedMock fallback is available
- **THEN** the current baseline MUST NOT be declared ready for remote delivery.

### Requirement: The candidate delivery set passes final gates

The candidate delivery set SHALL pass all available project checks and SHALL be
audited before staging. Reproducible runtime artifacts SHALL be excluded or
cleaned, and no commit or push SHALL occur without an explicit delivery action.

#### Scenario: Final audit succeeds

- **WHEN** the bounded rehearsal has succeeded and the working tree is audited
- **THEN** project tests, project checks, strict OpenSpec validation, UTF-8
  validation, Markdown relative-link validation, and Git whitespace checks pass
- **AND** the intended commit file set contains no databases, secrets, provider
  logs, external rehearsal files, dependency directories, caches, or worktree
  metadata.
