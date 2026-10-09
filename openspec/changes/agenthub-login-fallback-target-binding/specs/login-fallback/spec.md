## ADDED Requirements

### Requirement: Persist supported demo mutation intents
New built-in frontend tasks SHALL persist the supported structured login mutation
when their request asks to create a login page for the demo, including direct and
deterministic group routes, while retaining registered target and file boundaries.

#### Scenario: Direct or group login recovery
- **WHEN** a bounded demo login task fails and the user explicitly retries with ScriptedMock
- **THEN** its new-task plan already identifies `login_page`
- **AND** fallback writes the actual assigned worktree and provides matching nonempty Diff/Preview evidence while preserving failure history

#### Scenario: Same-Session copy follow-up
- **WHEN** the user asks to change the supported button text after the login change
- **THEN** direct and group task plans retain the specific copy target/text
- **AND** execution preserves the existing login form and unrelated source

### Requirement: Preserve honest execution boundaries
The change SHALL preserve unsupported-target rejection, external/native task
semantics, scope/dependency/review checks and immutable historical run snapshots.

#### Scenario: Unsupported or different intent
- **WHEN** a request reviews a login page, describes an unsupported integration, or selects another target
- **THEN** it is not silently converted into the built-in login template mutation
- **AND** explicit unsupported ScriptedMock targets remain failed without writes
