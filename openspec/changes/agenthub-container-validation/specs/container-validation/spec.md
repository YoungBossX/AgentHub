## ADDED Requirements

### Requirement: Optional fixed validation backend
The server SHALL default to native validation and MAY use Docker only for the
two built-in fixed profiles without changing AgentAdapter contracts, tool scope,
queue/worktree ownership or existing native preview behavior.

#### Scenario: Docker is absent under the default configuration
- **WHEN** the platform starts and validates a native task without Docker installed
- **THEN** it performs no Docker operation and the existing demo path remains available.

#### Scenario: Explicit Docker validation cannot start
- **WHEN** the selected backend lacks its approved local image, daemon or required capability
- **THEN** validation reports unavailable without pulling, installing or silently executing native commands.

### Requirement: Trusted immutable profile images
The server SHALL accept only operator-approved immutable image IDs for Linux/amd64,
with a frozen recipe, trusted harness and dependency lock. Developer preparation
SHALL be separate from task execution and SHALL use a bounded clean build context.

#### Scenario: Prepare images
- **WHEN** an operator explicitly prepares the two profile images
- **THEN** actual image IDs, recipe and dependency hashes are recorded without including user code, data or credentials.

#### Scenario: Inspect readiness
- **WHEN** the read-only doctor runs
- **THEN** it neither creates containers/databases nor starts a daemon, installs dependencies, modifies configuration or claims runtime isolation was tested.

### Requirement: Constrained server-owned execution
The Docker backend SHALL use fixed commands, a local daemon, non-root read-only
containers, no network or exposed ports, the documented CPU/memory/PID/tmpfs/time
budgets, and a cross-process single-validation capacity limit.
Agents SHALL NOT receive Docker access or arbitrary execution configuration.

#### Scenario: An unsafe input or runtime parameter is supplied
- **WHEN** source links, protected paths, a remote context, mutable image tag or arbitrary mount/command are encountered
- **THEN** execution is refused before target code runs and no permissions are expanded.

#### Scenario: Execution exhausts its budget
- **WHEN** timeout, OOM, PID or output limits are reached
- **THEN** the actual failure is recorded and only verified owned resources are terminated.

### Requirement: Bounded artifact handoff
Frontend results SHALL pass a fixed bounded byte export and strict host path/hash
validation before use by the existing native browser harness. Backend application
data SHALL NOT be exported. Browser and command execution environments SHALL be distinguished.

#### Scenario: Export contains an unsafe path or oversized payload
- **WHEN** duplicate paths, traversal, links, invalid base64, excessive bytes or mismatched hashes are returned
- **THEN** the export is rejected without overwriting files or accepting requirement validation.

#### Scenario: Docker commands pass but the host browser is unavailable
- **WHEN** a frontend requirement contract needs the native browser
- **THEN** requirement validation is unavailable and acceptance remains incomplete.

### Requirement: Execution-bound evidence and recoverable ownership
Existing validation events SHALL carry additive backend, image, policy and launch
generation evidence. Currentness SHALL validate original event provenance without
querying the daemon on report reads. Cleanup SHALL require verified ownership.

#### Scenario: A receipt is relabeled or rebound
- **WHEN** a native receipt is changed to Docker or source, image, policy or launch binding differs
- **THEN** the result cannot establish current version-bound acceptance.

#### Scenario: The API crashes or loses execution ownership
- **WHEN** an operation is interrupted or a later process obtains its capacity lease
- **THEN** only resources verified against the private journal and dead/expired owner may be reclaimed; no interrupted TaskRun is replayed or completed by a stale worker.

### Requirement: Existing data and adapter compatibility
Implementation SHALL preserve current schema, Alembic revision, existing row IDs,
values and attachment bytes without data migration, seed rewrite or historical
receipt backfill. All three current adapters and native rollback SHALL remain supported.

#### Scenario: Open an existing current database
- **WHEN** native and Docker tasks append normal new execution records
- **THEN** pre-existing business records and schema remain intact and legacy reports remain readable without invented Docker metadata.

### Requirement: Real Docker qualification
Completion SHALL include actual Linux Docker positive and negative tests for both
profiles, lifecycle and data compatibility. Simulated tests or optional skips SHALL
NOT establish OS isolation or real-provider execution.

#### Scenario: Required integration environment is unavailable
- **WHEN** the explicitly requested real-container qualification job lacks Docker or an approved image
- **THEN** that job fails and phase completion remains unverified rather than reporting a skipped suite as success.
