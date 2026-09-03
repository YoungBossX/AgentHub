## ADDED Requirements

### Requirement: Vulnerable Browserslist releases are excluded

The committed workspace dependency graph SHALL NOT resolve Browserslist at or
below 4.28.6 and SHALL redirect only that vulnerable range to the first verified
patched release without upgrading unrelated packages.

#### Scenario: Fresh dependency resolution

- **WHEN** pnpm resolves the workspace from the committed manifests and lockfile
- **THEN** every Browserslist importer resolves version 4.28.7
- **AND** no direct Browserslist dependency is added
- **AND** complete and production pnpm audits report no known advisories
- **AND** Demo Vite 7 and the existing Web toolchain retain their current direct
  dependency versions and pass their checks, tests, and production builds

### Requirement: Audit evidence remains narrowly stated

Dependency audit documentation SHALL describe the package-manager advisory
result and SHALL NOT generalize that result into a claim that the complete
application has no security vulnerabilities.

#### Scenario: Candidate documentation is reviewed

- **WHEN** the security refresh is recorded in project documentation
- **THEN** the affected dependency paths, patched version, validation runtime,
  audit result, and residual scope boundary are stated explicitly
