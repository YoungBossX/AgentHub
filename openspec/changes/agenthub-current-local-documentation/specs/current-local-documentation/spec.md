## ADDED Requirements

### Requirement: Distinguish current code and historical delivery
Current guides SHALL explain verified local capabilities without presenting historical tests, model fixtures or uncommitted code as current remote delivery.

#### Scenario: A capability was completed locally
- **WHEN** its implementation and focused checks are complete but not pushed
- **THEN** guides describe how to use it and explicitly retain local delivery and verification limits.

### Requirement: Preserve historical evidence
Document reconciliation SHALL preserve dated evidence and keep local file references navigable.

#### Scenario: An oversized log is archived
- **WHEN** historical sections leave the current log
- **THEN** indexed archive chunks preserve their text, counts and evidence while adjusting only relative links.
