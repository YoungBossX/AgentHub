## ADDED Requirements

### Requirement: Balanced composer controls
The workbench SHALL display the message input above an attachment/send toolbar
with equal outer padding and vertically aligned action controls, preserving
existing message, attachment, context and keyboard behavior in both themes.

#### Scenario: Compose a message after maintenance
- **WHEN** the user opens the workbench on a desktop or narrow screen
- **THEN** the textarea and action controls remain inside the composer, attachment
  and send controls share a vertical center, and historical data remains available.

### Requirement: Current workspace branding
The product SHALL present the legacy default workspace name as AgentHub without
rewriting the persisted lookup key or changing custom workspace names.

#### Scenario: An existing database still uses the legacy default name
- **WHEN** the workbench loads the legacy default workspace
- **THEN** its sidebar heading and workspace footer show AgentHub and existing
  Sessions and custom workspace labels remain available.

### Requirement: Evidence-bound local acceptance
Recovery and acceptance SHALL use existing scoped execution and preview APIs,
preserve historical evidence and distinguish real-provider and fallback runs.

#### Scenario: Restore and validate local outputs
- **WHEN** the two historical previews are explicitly recovered and a fresh
  bounded coding task is executed
- **THEN** recovery has new healthy output records, the task has recorded execution
  and real Diff evidence, and actual browser output is verified before completion.
