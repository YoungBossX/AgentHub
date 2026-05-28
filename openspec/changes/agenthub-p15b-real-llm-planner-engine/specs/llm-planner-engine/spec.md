## ADDED Requirements

### Requirement: Planner Provider Abstraction
The system MUST define a planner provider abstraction for `llm_v1` planning.

#### Scenario: Disabled planner provider
- **WHEN** planner provider selection is disabled
- **THEN** the system MUST skip real LLM planning
- **AND** it MUST record that planner source as `disabled`.

#### Scenario: Fake test planner provider
- **WHEN** tests configure a fake planner provider
- **THEN** the system MUST use the fake provider only as test evidence
- **AND** it MUST NOT report fake test output as real LLM planner success.

#### Scenario: Real planner provider selection
- **WHEN** a real planner provider is configured
- **THEN** the system MUST record provider ID, provider type, planner source,
  request duration, and final result in planner evidence.

#### Scenario: Invalid provider selection
- **WHEN** planner provider configuration references an unknown provider
- **THEN** planning MUST fail honestly or fall back explicitly
- **AND** it MUST NOT silently substitute another real provider.

### Requirement: Planner Request Contract
The system MUST build a sanitized PlannerRequest for real LLM planning.

#### Scenario: Planner request includes required context
- **WHEN** `llm_v1` planning is attempted
- **THEN** PlannerRequest MUST include the original user request,
  CanonicalSharedContext summary, Target Registry summary, Project Analyzer
  summary, recent messages, artifact references, supported
  roles/modes/capabilities, and guardrails.

#### Scenario: Protected data is excluded
- **WHEN** PlannerRequest is built
- **THEN** protected host paths, secrets, `.env` values, raw credentials,
  dependency directories, and provider tokens MUST NOT be included in
  provider-visible context.

#### Scenario: User request is preserved
- **WHEN** PlannerRequest is sent to a provider
- **THEN** the user's original request MUST be present without being reduced
  to a deterministic demo template.

### Requirement: Planner Response Contract
The system MUST require real planner providers to return a structured
PlannerResponse that can become a validated PlanDraft.

#### Scenario: Structured plan fields are present
- **WHEN** a planner provider returns a response
- **THEN** the response MUST include `planId`, `planner`, `rationale`, `tasks`,
  `role`, `targetId`, `intentType`, `plannedFiles`, `dependsOn`,
  `acceptanceCriteria`, `riskLevel`, and `requiresApproval`.

#### Scenario: Planner mode is llm_v1
- **WHEN** the response is used as an LLM plan
- **THEN** the planner field MUST be `llm_v1`.

#### Scenario: Task graph is dependency-safe
- **WHEN** PlannerResponse includes multiple tasks
- **THEN** each dependency MUST reference a known task in the same candidate
  plan
- **AND** cycles MUST be rejected before task creation.

### Requirement: Real Planner Provider Implementation
The system MUST implement at least one real planner provider path.

#### Scenario: Real provider returns a valid plan
- **WHEN** the real planner provider succeeds and returns valid structured
  output
- **THEN** the system MUST continue to schema validation and PlanValidator
  before creating tasks.

#### Scenario: Provider authentication failure
- **WHEN** the real planner provider fails due to authentication
- **THEN** the system MUST record a normalized auth error
- **AND** it MUST NOT claim real LLM planner success.

#### Scenario: Provider quota failure
- **WHEN** the real planner provider fails due to quota or usage limits
- **THEN** the system MUST record a normalized quota error
- **AND** it MUST NOT claim real LLM planner success.

#### Scenario: Provider timeout
- **WHEN** the real planner provider exceeds the configured timeout
- **THEN** the provider run MUST be marked timed out
- **AND** no tasks MUST be created from partial output.

#### Scenario: Provider output contains invalid JSON
- **WHEN** provider output cannot be parsed as valid structured JSON
- **THEN** the system MUST record an invalid-output error
- **AND** it MUST fallback or fail honestly.

### Requirement: Structured Output Parsing And Validation
The system MUST parse and validate real planner output before task creation.

#### Scenario: JSON extraction is safe
- **WHEN** a provider returns surrounding prose with embedded JSON
- **THEN** the system MAY extract the JSON object safely
- **AND** it MUST reject ambiguous or multiple conflicting JSON payloads.

#### Scenario: Schema validation happens before PlanValidator
- **WHEN** JSON is extracted
- **THEN** schema validation MUST run before PlanValidator
- **AND** missing required fields MUST reject the plan.

#### Scenario: Unsafe normalization is forbidden
- **WHEN** planner output contains unknown targets, unsafe paths, or unsupported
  roles
- **THEN** the system MUST NOT normalize those values into allowed values
  silently.

### Requirement: PlanValidator Hardening For Real LLM Output
The system MUST validate real LLM plans against execution policy before
persisting tasks.

#### Scenario: Target and path policy validation
- **WHEN** a candidate plan references targets and planned files
- **THEN** PlanValidator MUST verify known targets, allowed paths, denied
  paths, and protected path exclusions.

#### Scenario: Role and capability validation
- **WHEN** a candidate task references a role or mode
- **THEN** PlanValidator MUST verify that an available agent profile supports
  the role, target, mode, and required capabilities.

#### Scenario: Platform maintenance validation
- **WHEN** a candidate plan modifies AgentHub platform code
- **THEN** PlanValidator MUST require explicit platform maintenance mode and
  approval metadata.

#### Scenario: Command policy validation
- **WHEN** a candidate plan includes validation commands
- **THEN** PlanValidator MUST verify those commands against the selected
  target's command policy.

#### Scenario: Unsafe plan is not executed
- **WHEN** PlanValidator rejects a candidate plan
- **THEN** no TaskRun MUST be auto-started from that plan.

### Requirement: Planner Evidence And Mission Trace
The system MUST record planner evidence for real, fake, disabled,
deterministic, and fallback planning paths.

#### Scenario: Real planner evidence is recorded
- **WHEN** a real LLM planner run completes
- **THEN** planner evidence MUST include provider ID, provider type, duration,
  validation result, planner source, plan rationale, and created task IDs.

#### Scenario: Failed planner evidence is recorded
- **WHEN** real planner execution fails
- **THEN** planner evidence MUST include error code, error summary, fallback
  reason if any, and validation state.

#### Scenario: Mission trace exposes planner source
- **WHEN** mission trace is requested
- **THEN** it MUST expose whether the plan came from `real_llm`, `fake_test`,
  `disabled`, `deterministic`, or `fallback`.

#### Scenario: Secrets are not exposed in evidence
- **WHEN** planner evidence is stored or returned
- **THEN** raw secrets, provider credentials, and protected host paths MUST NOT
  be exposed.

### Requirement: Real LLM Planner Breakout Rehearsal
The system MUST verify the Breakout acceptance request with a real LLM planner
provider.

#### Scenario: Breakout plan is produced by real planner
- **WHEN** the user asks `帮我在当前前端项目里实现一个 Breakout / 打砖块游戏，要求可以用键盘控制挡板，球能反弹，能击碎砖块，有得分、胜利/失败状态和重新开始按钮。`
- **THEN** a real LLM planner provider MUST produce the task plan
- **AND** the plan MUST NOT come from a hardcoded Breakout regex/template or
  fake test planner.

#### Scenario: Breakout plan passes validation
- **WHEN** the real planner returns the Breakout plan
- **THEN** schema validation and PlanValidator MUST pass before any task is
  created or auto-started.

#### Scenario: Breakout execution reuses P15 pipeline
- **WHEN** the validated Breakout task executes
- **THEN** it MUST use existing passthrough instruction behavior and a real
  ClaudeCodeAdapter or CodexAdapter coding run when auth/quota permits.

#### Scenario: Breakout evidence is complete
- **WHEN** the Breakout rehearsal succeeds
- **THEN** the system MUST record diff, review, build/check evidence, preview,
  and staging deploy evidence.

#### Scenario: Real planner blockage is reported honestly
- **WHEN** the real planner provider is blocked by auth, quota, runtime, or
  environment failure
- **THEN** the exact normalized planner error MUST be recorded
- **AND** the system MUST NOT claim real LLM planner success.

### Requirement: P15b Baseline Preservation
The system MUST preserve P6-P15 baselines while adding real LLM planner
capability.

#### Scenario: Deterministic fallback remains available
- **WHEN** real LLM planning is disabled, unavailable, invalid, or unsupported
- **THEN** deterministic fallback MUST remain available where explicitly
  applicable
- **AND** the fallback reason MUST be recorded.

#### Scenario: Existing execution pipeline remains intact
- **WHEN** a validated plan creates coding tasks
- **THEN** Target Registry, scheduler, target locks, Agent Selection Policy,
  CanonicalSharedContext, provider instruction adapters, diff, review,
  preview, staging deploy, and recovery behavior MUST remain operational.

#### Scenario: ScriptedMock remains fallback only
- **WHEN** ScriptedMock is used
- **THEN** it MUST remain clearly labeled as fallback or test evidence
- **AND** it MUST NOT be used to claim real LLM planner success.
