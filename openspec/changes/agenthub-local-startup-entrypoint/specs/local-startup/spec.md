## ADDED Requirements

### Requirement: Portable supervised local startup
The project SHALL offer local API/Web startup without Bash or implicit dependency
installation, bind only to loopback, and connect selected ports consistently.

#### Scenario: Installed local environment
- **WHEN** the developer runs `pnpm dev:local` with supported installed dependencies
- **THEN** the API and Web start and readiness is reported only after both are ready
- **AND** custom API/Web ports set Web backend routing and API CORS consistently

#### Scenario: Missing dependency or occupied port
- **WHEN** an explicit Python interpreter is invalid, a dependency is missing, or a selected port is occupied
- **THEN** startup fails with an actionable diagnostic without installing dependencies or stopping an existing listener

#### Scenario: Normal shutdown or startup failure
- **WHEN** the launcher is interrupted normally, receives stop/EOF, or a spawned service fails
- **THEN** it stops only its spawned services and allows API lifespan cleanup before bounded fallback termination
- **AND** stored sessions and existing worktrees are retained

#### Scenario: Child commands while the launcher control pipe is open
- **WHEN** the API starts a child command on Windows or POSIX while its launcher is connected
- **THEN** the child inherits a readable null standard input and reaches EOF without waiting for launcher shutdown
- **AND** the separate launcher control descriptor remains non-inheritable, including when a child disables close_fds
- **AND** a failing subprocess regression reports its bounded stderr and exit status

### Requirement: Read-only local diagnostics and accurate usage
The project SHALL provide dependency diagnostics and local setup/workflow documentation
that distinguish the product API, demo API and Session Preview processes.

#### Scenario: Doctor and optional backend demo
- **WHEN** the developer runs `pnpm doctor:local`
- **THEN** dependencies and ports are checked without application imports, database writes or provider execution
- **AND** optional demo API startup uses the target contract's fixed port 5174
