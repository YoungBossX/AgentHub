## ADDED Requirements

### Requirement: Render supported copy literally
ScriptedMock SHALL display supported normalized button/heading targetText as
literal text, without evaluating JSX expressions, decoding user entity spelling
or inserting user markup. It SHALL preserve other source and stylesheet content.

#### Scenario: Sensitive copy characters
- **WHEN** a supported copy target contains braces, tags, entities or control characters
- **THEN** generated JSX represents those characters as string data
- **AND** actual rendered target text matches the supported targetText without child markup or runtime errors

#### Scenario: Further copy edit
- **WHEN** another supported copy change follows a value containing closing tags or backslashes
- **THEN** only the intended target content changes and its anchor remains usable

### Requirement: Preserve execution and evidence boundaries
The implementation SHALL retain target/path, read-only, no-op, scope, execution
ownership and output completion checks. Functional browser acceptance SHALL be
recorded separately from generic scope/Diff completion evidence.

#### Scenario: No-op or unsupported change
- **WHEN** no content changes or the requested scripted target is unsupported
- **THEN** the run fails honestly without attributing an old Diff as new output

#### Scenario: Historical output
- **WHEN** new tasks use the repaired encoder
- **THEN** historical runs and their producing source remain identified as historical evidence without automatic rewrite
