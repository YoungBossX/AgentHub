## ADDED Requirements

### Requirement: External Workspace Registration

The system MUST allow a local external project root to be registered as a
first-class AgentHub workspace target before agents execute against it.

#### Scenario: Local project is registered

- **WHEN** the user registers a local external project root
- **AND** the root is not a system directory, home directory, repository parent
  directory, or otherwise unsafe broad path
- **THEN** the system MUST persist an external target containing `targetId`,
  `name`, `rootPath`, `projectType`, `allowedPaths`, `deniedPaths`,
  `devCommand`, `testCommand`, `checkCommand`, `buildCommand`,
  `previewCommand`, `packageManager`, and `detectedFramework`
- **AND** the external target MUST be selectable for future sessions/tasks.

#### Scenario: Unsafe root is rejected

- **WHEN** the user attempts to register the filesystem root, home directory,
  system directory, or broad parent directory as an external project
- **THEN** the system MUST reject the registration
- **AND** the rejection MUST explain that external project roots must be
  explicit project directories.

#### Scenario: Denied paths are always present

- **WHEN** an external target is registered
- **THEN** its denied paths MUST include `.env`, `.env.*`, `secrets`, `.git`,
  `node_modules`, `.venv`, generated dependency directories, and generated
  build output directories
- **AND** these denied paths MUST NOT be editable by adapters.

### Requirement: Project Analyzer

The system MUST analyze external project structure without installing
dependencies or running arbitrary commands.

#### Scenario: JavaScript frontend project is analyzed

- **WHEN** the analyzer finds `package.json` and Vite or Next.js config/scripts
- **THEN** it MUST infer a frontend project type such as `vite-react` or
  `nextjs`
- **AND** it MUST infer package manager, detected framework, safe source paths,
  and configured check/test/build/preview command candidates when available.

#### Scenario: Python or API project is analyzed

- **WHEN** the analyzer finds `pyproject.toml`, `requirements.txt`, FastAPI
  entry points, or Node API entry points
- **THEN** it MUST infer `fastapi`, `node-api`, `python-package`, or `unknown`
  as appropriate
- **AND** it MUST infer safe source/test paths and validation command
  candidates when available.

#### Scenario: Analyzer is uncertain

- **WHEN** project type, safe allowed paths, or command inference is uncertain
- **THEN** the analyzer MUST mark the result as needing confirmation or
  explicit configuration
- **AND** the target MUST NOT be executable until the uncertainty is resolved.

### Requirement: External Target Registry Integration

The system MUST expose external targets through the same Target Registry model
used for built-in targets.

#### Scenario: External target is resolved

- **WHEN** a registered external target ID is requested in a workspace/session
  context
- **THEN** the Target Registry MUST return a target metadata object compatible
  with built-in targets
- **AND** planner, instruction builder, review, and scheduler MUST be able to
  consume it.

#### Scenario: Built-in targets remain available

- **WHEN** external targets are registered
- **THEN** `demo-frontend`, `demo-backend`, and `agenthub-platform` MUST remain
  resolvable
- **AND** their permissions and scheduler behavior MUST NOT regress.

#### Scenario: External target lock is active

- **WHEN** a write TaskRun is active for an external target
- **AND** another write task for the same external target becomes runnable
- **THEN** the scheduler MUST NOT start the second task
- **AND** the second task MUST expose a `waiting_target_lock` equivalent with
  the external target ID.

### Requirement: External Target Instructions

The system MUST build role-specific instructions from external target metadata
instead of assuming built-in demo paths.

#### Scenario: Frontend task targets external frontend

- **WHEN** a frontend task targets a registered external frontend project
- **THEN** the instruction MUST include the external root, allowed paths,
  denied paths, project type, package manager, detected framework, original
  user request, and validation expectations
- **AND** the instruction MUST NOT assume `apps/demo` unless that is the
  registered target root.

#### Scenario: Backend task targets external backend

- **WHEN** a backend task targets a registered external backend/API project
- **THEN** the instruction MUST include the external backend root, allowed
  paths, denied paths, configured commands, original user request, and
  validation expectations
- **AND** it MUST NOT permit edits to AgentHub platform backend `apps/api`
  unless the task explicitly targets `agenthub-platform`.

#### Scenario: Review task targets external evidence

- **WHEN** a QA or review task targets an external project
- **THEN** the instruction MUST include latest diff metadata, command evidence,
  allowed path policy, denied path policy, and selected artifact context when
  available.

### Requirement: External Project Task Execution

The system MUST allow registered external targets to receive executable tasks
through existing AgentHub routing and adapter paths.

#### Scenario: Direct frontend assignment uses active external target

- **WHEN** a user sends `@frontend` while an external frontend target is active
- **THEN** the system MUST create a frontend task targeting that external
  target
- **AND** TaskRun execution MUST be scoped to the target root/worktree and
  allowed paths.

#### Scenario: Direct backend assignment uses active external target

- **WHEN** a user sends `@backend` while an external backend target is active
- **THEN** the system MUST create a backend task targeting that external target
- **AND** it MUST NOT modify AgentHub platform backend unless explicit platform
  mode is selected.

#### Scenario: Orchestrator routes normal request

- **WHEN** a user sends a normal no-mention request while an external workspace
  target is active
- **THEN** Orchestrator MUST decide whether to create external target tasks,
  ask a clarification question, or reject unsupported work honestly
- **AND** unsupported or ambiguous requests MUST NOT silently execute.

### Requirement: External Evidence Pipeline

The system MUST record external project evidence according to registered target
capabilities.

#### Scenario: External coding task completes

- **WHEN** an external coding TaskRun completes
- **THEN** the system MUST collect a git diff scoped to the external target
- **AND** it MUST record changed files without including denied or dependency
  directories.

#### Scenario: Validation commands are configured

- **WHEN** an external target has configured check, test, or build commands
- **THEN** the system MUST be able to record command output evidence
- **AND** failed command exits MUST be recorded honestly as failed evidence.

#### Scenario: Preview is unavailable

- **WHEN** an external target has no preview command
- **THEN** the system MUST NOT require preview evidence
- **AND** the task may still produce valid diff, command, and review evidence.

### Requirement: External Project Review

The system MUST review external target diffs and command evidence against
registered target policy.

#### Scenario: Allowed path violation is detected

- **WHEN** an external diff includes files outside the target allowed paths
- **THEN** review MUST report a warning or failure
- **AND** the finding MUST identify the violating path.

#### Scenario: Denied path edit is detected

- **WHEN** an external diff includes `.env`, `.env.*`, `secrets`, `.git`,
  `node_modules`, `.venv`, dependency directories, generated build output, or
  other denied paths
- **THEN** review MUST fail or warn with an explicit denied-path finding.

#### Scenario: Command evidence failed

- **WHEN** check, test, or build command evidence exists and failed
- **THEN** review MUST include that failure in its summary/findings
- **AND** the system MUST NOT claim validation success.

### Requirement: External Workspace Baseline Preservation

The system MUST preserve P6/P7/P8 built-in behavior while adding external
workspace mode.

#### Scenario: External project rehearsal is performed

- **WHEN** P9 is reviewed for freeze
- **THEN** a local sample external project MUST be registered and rehearsed
- **AND** evidence MUST record registration, analyzer output, task/run IDs,
  diff, review, command evidence, preview evidence when configured, and caveats
- **AND** real Claude/Codex success MUST be claimed only when actually run
- **AND** P6/P7/P8 built-in demo baselines MUST remain intact.

#### Scenario: Out-of-scope capability is requested

- **WHEN** a request requires cloud repo import, multi-user project sharing,
  production deploy, Docker sandbox, provider marketplace, PR creation,
  enterprise RBAC, or unrestricted filesystem access
- **THEN** P9 MUST reject or defer the request honestly
- **AND** it MUST NOT silently execute outside registered external targets.
