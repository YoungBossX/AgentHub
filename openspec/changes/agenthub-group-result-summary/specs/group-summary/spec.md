## ADDED Requirements

### Requirement: Evidence-bound coordinator result summary
The system SHALL summarize newly planned explicit groups using their frozen
selected coordinator and latest matching execution/artifact evidence. It SHALL
distinguish execution completion, partial failure, awaiting action and review
judgments. A native configured coordinator SHALL perform an actual no-tool
summary call; an unconfigured coordinator SHALL disclose its deterministic source.

#### Scenario: Native execution completes
- **WHEN** all latest participant attempts and required artifacts complete
- **THEN** the selected coordinator's actual interpretation and server-owned
  run/artifact receipts appear in chat without claiming unobserved tests passed

#### Scenario: Failure or manual continuation
- **WHEN** a group settles with failed/interrupted work or awaits explicit action
- **THEN** its summary identifies actual completed and unfinished participants
  and retains the failure/retry history

#### Scenario: Stale input or revoked selection
- **WHEN** attempts, artifact evidence or coordinator permissions change during a call
- **THEN** the old result cannot publish as a current successful summary

#### Scenario: Duplicate wake, restart and summary retry
- **WHEN** concurrent workers wake or a summary lease expires after restart
- **THEN** durable claims prevent duplicate current publication and old owners
  cannot overwrite a successor; provider/output failures require explicit retry

#### Scenario: Read-only history and UI recovery
- **WHEN** the user reloads chat or reconnects SSE
- **THEN** the same stored receipts and provenance return without rerunning
  the provider, with current and historical attempts clearly identified
