## ADDED Requirements

### Requirement: IM collaboration workbench
The workspace SHALL provide conversation, execution-process and result views
using persisted messages, tasks, runs, events and artifacts, with the approved
light visual design and visible Agent identities.

#### Scenario: Process visibility
- **WHEN** a session has planned or executing tasks
- **THEN** the user can inspect task dependencies, latest run states, failures,
  actual event records and the existing approval/retry/interrupt controls
- **AND** dependencies do not imply concurrent provider execution

#### Scenario: Evidence-based result display
- **WHEN** an artifact is received
- **THEN** it appears as a selectable inline result and in the results view
- **AND** the inspector retains the actual Diff, review or protected preview
- **AND** run completion alone does not imply a Diff, healthy preview or deploy

#### Scenario: Session and viewport changes
- **WHEN** the user switches sessions or uses a narrow viewport
- **THEN** old session events/results do not appear as current evidence and the
  navigation, composer, execution controls and artifact inspector remain reachable
