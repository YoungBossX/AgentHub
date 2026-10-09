# Native Review Artifacts

## ADDED Requirements

### Requirement: Native assessment is version bound and independently validated
The system SHALL bind a native read-only review to scoped file fingerprints and
validate its actual CLI result and successful Read evidence before completion.

#### Scenario: Valid native assessment
- **WHEN** Claude returns a valid structured assessment of the frozen files
- **THEN** a Review artifact contains its actual summary, findings and suggestions
- **AND** provider, run, output and file receipts identify the native source
- **AND** no executed test or functional acceptance is inferred from model approval.

#### Scenario: Invalid or changed input
- **WHEN** the output is missing, malformed, out of scope, inconsistent with Read
  evidence, or the scoped files changed during execution
- **THEN** the run fails explicitly
- **AND** no scripted report is substituted for native success.

### Requirement: Result UI distinguishes execution and assessment sources
The system SHALL distinguish native model assessments from scripted advisory
reports and preserve their findings, limitations and lineage across refresh.

#### Scenario: Open and refresh a native result
- **WHEN** the user opens a native Review card and reloads the workspace
- **THEN** its assessment and real provider source remain visible
- **AND** coding and mock reports retain their scripted source label.
