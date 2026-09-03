# Real Adapter Execution Containment

## ADDED Requirements

### Requirement: Codex runs only with the bounded workspace sandbox

AgentHub SHALL invoke Codex non-interactively with its platform-native
`workspace-write` sandbox rooted at the assigned Session worktree. The command
guardrail SHALL reject Codex commands that omit or weaken this profile, request
an additional writable root, bypass approvals and sandboxing, or specify a
working directory other than the resolved runner worktree.

#### Scenario: A bounded Codex command is evaluated

- **WHEN** the Codex adapter submits its generated execution command
- **THEN** the command uses `workspace-write`, `never` approval, and the assigned
  working directory
- **AND** the command is allowed without a separate approval.

#### Scenario: A Codex command weakens containment

- **WHEN** a Codex command omits or changes the sandbox or includes a bypass or
  extra writable-root argument
- **THEN** the command is rejected before the provider process starts.

### Requirement: Claude Code runs with file-only restricted execution

AgentHub SHALL invoke Claude Code in restricted and safe modes with only the
required file tools, no shell or network tool, strict MCP configuration, and no
session persistence. The command guardrail SHALL reject Claude Code commands
that omit or conflict with this profile. Both real adapter commands SHALL end
option parsing before the user-derived instruction.

This is provider/tool-level containment for a trusted Claude executable, not a
general process, network, or OS/container sandbox.

#### Scenario: A bounded Claude Code command is evaluated

- **WHEN** the Claude Code adapter submits its generated execution command
- **THEN** restricted mode and the explicit file-only tool set are present
- **AND** the command is allowed without a separate approval.

#### Scenario: A Claude Code command weakens containment

- **WHEN** restricted mode, strict MCP configuration, or the file-only tool set
  is missing or a conflicting tool configuration is present
- **THEN** the command is rejected before the provider process starts.
