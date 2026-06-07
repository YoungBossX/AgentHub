## 1. P18c-1 Memory Rules And Compliance Harness

- [x] 1.1 Add or verify active canonical memory items for the six P18c rules under test.
- [x] 1.2 Add a P18c compliance model/checker for memory ids, project location, framework, persistence, change-log, platform boundary, provider evidence, and snapshot consistency.
- [x] 1.3 Add tests for each compliance violation code and for a passing evidence fixture.
- [x] 1.4 Validate `pnpm check`, targeted tests, `git diff --check`, and `openspec validate agenthub-p18c-live-memory-compliance-library-app --strict`.

## 2. P18c-2 Session And External Target Setup

- [ ] 2.1 Create or prepare `~/Desktop/agenthub-rehearsals/` as the allowed rehearsal root without creating the library app implementation manually.
- [ ] 2.2 Register or analyze the desktop rehearsal frontend target through existing external workspace / Target Registry paths where needed.
- [ ] 2.3 Create a fresh AgentHub session after active memory exists and record `memorySnapshotId`.
- [ ] 2.4 Verify AGENTS.md hash, CLAUDE.md hash, active memory ids, target registry version, runtime config version, and context pack hash are available for the session.
- [ ] 2.5 Validate setup with targeted tests or smoke commands, `git diff --check`, and OpenSpec strict validation.

## 3. P18c-3 Live Library App Execution

- [ ] 3.1 Submit exactly the bounded library-management user prompt without restating memory rules.
- [ ] 3.2 Run the coding task with real ClaudeCodeAdapter or CodexAdapter if auth/quota/runtime permits.
- [ ] 3.3 Stop and record the exact blocker if real provider execution is unavailable; do not use ScriptedMock to claim live compliance.
- [ ] 3.4 If execution succeeds, verify the app includes login, fixed demo credentials, management page, add/delete/edit/search books, and localStorage persistence.
- [ ] 3.5 Collect TaskRun, diff, changed files, build/check/test, review, preview/staging evidence where available.
- [ ] 3.6 Verify the live task does not modify `apps/api` or AgentHub platform code without explicit platform maintenance mode.

## 4. P18c-4 Memory Compliance Evaluation

- [ ] 4.1 Run the P18c compliance checker against live evidence.
- [ ] 4.2 Report Preference Recall Rate, Project Memory Recall Rate, Cross-Agent Consistency Rate, Snapshot Consistency Rate, Change-log Missing Rate, Target Boundary Violation Count, Persistence Memory Violation Count, Provider Evidence Violation Count, and Task Success Delta when comparable control evidence exists.
- [ ] 4.3 Add a deterministic or dry-run control comparison if feasible; otherwise mark Task Success Delta unknown or inconclusive.
- [ ] 4.4 If follow-up is required to fix a memory compliance issue, record the first failure and follow-up evidence honestly.
- [ ] 4.5 Validate targeted tests, `git diff --check`, and OpenSpec strict validation.

## 5. P18c-5 Freeze Review

- [ ] 5.1 Create `docs/p18c-freeze-review.md` with provider, session, task/run, snapshot, memory hash, active memory, diff, review, build/check/test, preview/staging, compliance, follow-up, and limitation evidence.
- [ ] 5.2 Update `docs/project-state.md` and `docs/change-log.md` with P18c status.
- [ ] 5.3 Validate `pnpm check`, `pnpm test`, `pnpm demo:api:test`, `git diff --check`, and `openspec validate agenthub-p18c-live-memory-compliance-library-app --strict`.
- [ ] 5.4 Confirm P18c did not add production backend/database, cloud deploy, auth hardening, new retrieval algorithms, provider marketplace, or any Target Registry / PlanValidator / Guardrails bypass.
