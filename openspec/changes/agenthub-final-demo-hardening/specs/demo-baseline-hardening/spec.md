## ADDED Requirements

### Requirement: Baseline governance consistency
The project documentation MUST describe AgentHub as a local single-user Agent Coding Workspace / strong demo MVP and MUST NOT present it as a complete multi-user IM collaboration platform.

#### Scenario: Baseline docs are reviewed
- **WHEN** final demo baseline documents are reviewed
- **THEN** they identify the local single-user Agent Coding Workspace positioning
- **AND** they preserve the verified P0/P1/P2/P3/P4 paths without overstating unverified platform features

### Requirement: Current adapter reality
The project documentation MUST recognize `CodexAdapter`, `ClaudeCodeAdapter`, and `ScriptedMockAdapter` as current adapters and MUST preserve the fallback-based P0 demo path.

#### Scenario: Adapter guidance is reviewed
- **WHEN** adapter guidance is read before a final demo task
- **THEN** it treats Codex, Claude Code, and scripted mock execution as current baseline paths
- **AND** it does not instruct agents to remove or re-defer existing adapters

### Requirement: Final demo evidence discipline
The final demo hardening work MUST distinguish verified, fallback, partial, and unverified behavior in documentation and checklists.

#### Scenario: Final evidence is recorded
- **WHEN** a final demo checklist or summary is updated
- **THEN** real agent, fallback, follow-up, diff, preview, mock deploy, and browser coverage claims are labeled according to actual verification evidence
- **AND** mock deploy is not described as real production deployment
