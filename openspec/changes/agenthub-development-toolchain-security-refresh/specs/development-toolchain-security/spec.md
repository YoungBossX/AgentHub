# Development Toolchain Security

## ADDED Requirements

### Requirement: Development and test dependencies avoid audited vulnerable ranges

The committed workspace lockfile SHALL resolve development and test
dependencies outside every vulnerable range reported by the current complete
pnpm audit.

#### Scenario: Complete dependency audit runs after the targeted refresh

- **WHEN** `pnpm audit` evaluates the refreshed lockfile
- **THEN** it exits successfully with zero critical, high, moderate, low, and
  informational advisories
- **AND** `pnpm audit --prod` remains clean.

### Requirement: Toolchain refresh preserves supported developer workflows

The security refresh SHALL preserve the existing Demo Vite React and Web
lint/test/build workflows without unrelated dependency-major migrations.

#### Scenario: Compatibility gates run

- **WHEN** the refreshed dependencies are installed from the frozen lockfile
- **THEN** the root manifest declares the shared Node engine range required by
  Vite, jsdom, and Vitest
- **AND** Demo checks and production build pass
- **AND** Web lint, TypeScript, Vitest, and Next production build pass
- **AND** the complete repository checks and tests pass.

### Requirement: Local package-manager bootstrap preserves integrity verification

The workstation package-manager bootstrap SHALL execute the repository-pinned
pnpm release without disabling registry signature verification.

#### Scenario: The ordinary pnpm command uses repaired Corepack metadata

- **WHEN** a developer invokes `pnpm --version` from the repository
- **THEN** it reports pnpm 10.33.4 without a signing-key error
- **AND** no integrity-verification bypass environment variable is required.
