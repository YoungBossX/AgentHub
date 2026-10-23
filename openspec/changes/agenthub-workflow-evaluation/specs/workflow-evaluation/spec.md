## ADDED Requirements

### Requirement: Reliable strict native QA output
Read-only native Claude QA SHALL request the fixed assessment schema and validate
the successful structured output against the existing binding and full-file Read
evidence. Missing fields MUST NOT be synthesized and outcome gates stay strict.

#### Scenario: Structured serialization does not grant execution tools
- **WHEN** native QA emits the CLI's schema serialization event
- **THEN** it grants no file/command permission or Read coverage; only the exact fixed schema with Read-only tools is allowed, and invalid, absent, stale or unbound structured output fails closed.

#### Scenario: Contacts regression coverage is visible and immutable
- **WHEN** a fresh contacts-boundaries-v3 fixture is prepared
- **THEN** trusted backend boundary tests are present as immutable read-only review input, never treated as already executed; legacy fixtures and old results remain unchanged, and independent fixed business acceptance is still required.

### Requirement: Fixed Chinese business feedback and one bounded repair
The existing isolated workflow entrypoint SHALL offer an explicit opt-in for one
Chinese contacts contract repair, reusing production planning, queue, scope,
ownership and native-QA checks without introducing new Agent permissions.

#### Scenario: Complete versioned contacts boundaries
- **WHEN** contacts-boundaries-v3 is selected
- **THEN** the trusted harness requires the complete Chinese desktop/narrow checks and independent backend whitespace checks, including confirmed-save retention when refresh fails; receipts bind both source inputs and policy, negative writes cannot contaminate later viewport checks, and v1/v2 keep their existing contracts.

#### Scenario: Explicit bounded repair
- **WHEN** opted-in execution has current complete failed business evidence and completed original tasks
- **THEN** at most one repair phase uses structured fixed check IDs, the original Session and frozen source/policy, existing configured Agents and at most App.tsx/main.py writes; launch fences reject source drift, forged scope or Session/root changes before provider start.

#### Scenario: Honest repair outcomes and exhaustion
- **WHEN** repair succeeds, fails, is interrupted, exhausts its shared time budget or cannot establish current complete evidence
- **THEN** original outcomes remain unchanged, repair results and provenance are separately recorded, every observed call remains in usage accounting, pending runs are stopped, and no second repair or weaker acceptance gate is introduced.

### Requirement: Evaluate representative complete workflows
The system SHALL provide reproducible API, multi-file, coordinated frontend/backend,
follow-up and recovery scenarios through existing natural-language planning and
execution services in an isolated local workspace.

#### Scenario: Independent acceptance
- **WHEN** a scenario finishes
- **THEN** passing requires matching source/Diff/execution evidence and every immutable independent contract, including integration checks for coordinated targets.

#### Scenario: UTF-8 browser transport on a legacy host locale
- **WHEN** the trusted browser harness sends UTF-8 JSON containing Chinese or emoji contact names to isolated Python with a legacy default pipe encoding
- **THEN** the fixed ASGI bridge uses strict UTF-8, preserves exact POST/GET text, rejects malformed transport input, and retains its original route, size and audit boundaries.

#### Scenario: Explicit demo heading in a Chinese follow-up
- **WHEN** a change request explicitly targets the exact unquoted `h1#demo-heading` selector without repeating the demo application name
- **THEN** the frontend scope gate recognizes that bounded demo target while retaining existing broad-request rejection, partial/quoted-reference exclusion, target validation and adapter permissions; original failed evaluations remain unchanged and repair results use a separate source snapshot.

#### Scenario: Quoted replacement followed by preservation constraints
- **WHEN** a valid bounded quoted replacement is followed by additional natural-language constraints
- **THEN** recognition delegates the complete request to the existing Planner without treating the suffix as literal replacement text or rejecting the valid slot; missing, oversized and unclosed values remain rejected, and unavailable or invalid planning cannot create rule-fallback tasks.

#### Scenario: Planner unavailable or fallback
- **WHEN** the configured native Planner fails or is unavailable
- **THEN** its actual failure or fallback remains visible and cannot establish native planning success.

### Requirement: Preserve attempts and honest measurement
The system SHALL preserve failures and retries and report explicit denominators,
durations and execution sources without using historical or simulated success as
fresh real-provider evidence.

#### Scenario: Bounded provider usage and stages
- **WHEN** an existing Planner or Adapter returns a usage-bearing result or finishes a timed lifecycle stage
- **THEN** the system retains only allowlisted per-call usage, separates cached/uncached token conventions and CLI cost estimates from verified billing, stores absent or invalid values as unknown, deduplicates final receipts rather than adding streamed snapshots, and preserves failed/retried calls; application-observed first semantic text is not labeled model first-token latency.

#### Scenario: Same-version Chinese natural cohort
- **WHEN** the authorized five natural categories are repeated ten times
- **THEN** all fifty isolated episodes share a frozen runtime/operator/input policy and unchanged outcome gates, record defined planning, queue, launch, text, adapter, finalization and acceptance timing boundaries with coverage, and report deliberate failures/recovery, probes and repairs separately; source changes invalidate a cohort rather than merging repaired results into its denominator.

#### Scenario: Repeated scenarios and recovery
- **WHEN** fresh repetitions or a retry are executed
- **THEN** first-attempt and final outcomes remain distinct with original failures and lineage intact.

#### Scenario: Prepare-only or injected execution
- **WHEN** a run prepares fixtures, uses a test double or injects a failure
- **THEN** the report labels its mode and does not present it as natural provider performance.
