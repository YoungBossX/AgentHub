## ADDED Requirements

### Requirement: Evaluate native review evidence
Live workflow evaluation SHALL require actual native QA for each requested target and retain source-bound assessment/read/provider evidence independently of functional checks.

#### Scenario: QA is only configured or scripted
- **WHEN** native read/assessment evidence is absent, stale, mismatched or scripted
- **THEN** the sample cannot pass native QA evaluation even if code checks pass.

### Requirement: Keep one source cohort
The report SHALL identify the frozen implementation and inputs and invalidate whole-cohort success rates when those sources change during execution.

#### Scenario: Source changes after an earlier success
- **WHEN** the runner observes a different source policy before or after a case
- **THEN** it preserves earlier observations, stops later execution and does not present mixed-version rates as same-version results.

### Requirement: Preserve first attempts and retries
Evaluation SHALL separately report first-attempt/final outcomes, bounded explicit retries and coding/QA/wall elapsed time over all selected cases.

#### Scenario: A retry succeeds
- **WHEN** a failed or interrupted attempt is retried successfully
- **THEN** the original failure and retry identity remain visible and first-attempt success remains false.
