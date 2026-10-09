## ADDED Requirements

### Requirement: Explicit bounded Windows native sandbox
On Windows, CodexAdapter SHALL emit only the fixed native sandbox prefix
`-c windows.sandbox="unelevated"` alongside its unchanged containment arguments.
The command guardrail SHALL independently validate the prefix, the full command
shape and the assigned working directory. Non-Windows commands SHALL remain
unchanged.

#### Scenario: Native Windows tool execution
- **WHEN** CodexAdapter starts on Windows in the assigned worktree
- **THEN** it selects the verified native sandbox without loading user config,
  widening writable roots, enabling network or bypassing the sandbox

#### Scenario: Unsupported override or widened command
- **WHEN** the command includes a different config override, duplicate options,
  a mismatched working directory or missing containment arguments
- **THEN** the command guardrail rejects execution

#### Scenario: Real coding acceptance
- **WHEN** fresh external coding cases run with the Windows command
- **THEN** acceptance requires actual new output, matching nonempty Diff, valid
  scope and rule evidence, unchanged evaluators and passing independent tests
- **AND** historical failed reports are preserved
