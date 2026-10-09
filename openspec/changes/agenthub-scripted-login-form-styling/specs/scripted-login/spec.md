## ADDED Requirements

### Requirement: Deliver a styled bounded login template
Scripted login creation SHALL produce actual App and stylesheet changes in the
assigned demo worktree with usable field spacing, flexible widths and keyboard
focus, preserving unrelated content and reporting actual changed files.

#### Scenario: Fresh or previously unstyled demo
- **WHEN** ScriptedMock handles a supported login task in a demo worktree
- **THEN** a bounded CSS block styles the generated email/password fields
- **AND** actual Diff and healthy Preview identify the producing TaskRun
- **AND** the fields fit desktop and narrow preview viewports

#### Scenario: Copy follow-up
- **WHEN** a supported button-copy follow-up executes in the same Session
- **THEN** only the specified App text changes
- **AND** the form and stylesheet remain intact

### Requirement: Keep file and failure boundaries
The adapter SHALL preserve existing target/path checks, unsupported/no-op rejection
and read-only behavior. It SHALL reject unsafe CSS or ambiguous owned markers
before writing, and restore prepared files after ordinary write failures.

#### Scenario: Unsafe stylesheet or failed write
- **WHEN** the fixed stylesheet is unsafe, has ambiguous managed markers or cannot be written
- **THEN** the run fails honestly without claiming a styled result
- **AND** original files are preserved or any restoration failure is explicitly reported
