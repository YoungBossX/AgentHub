# Production Dependency Security

## ADDED Requirements

### Requirement: Shipped Web dependencies avoid audited vulnerable ranges

The Web package SHALL resolve production dependencies outside all vulnerable
ranges reported by the current pnpm production audit for the Next.js and Monaco
Editor dependency paths.

#### Scenario: Production dependency audit runs after lockfile regeneration

- **WHEN** `pnpm audit --prod` evaluates the committed workspace lockfile
- **THEN** it exits successfully with zero critical, high, moderate, low, and
  informational production advisories
- **AND** the dependency tree contains patched Next.js, PostCSS, nanoid, sharp,
  Monaco Editor, and DOMPurify versions.

### Requirement: Security refresh preserves the local Web workspace

The dependency refresh SHALL preserve existing Web application behavior and
the repository's local-demo runtime contract.

#### Scenario: Web compatibility gates run

- **WHEN** the updated dependencies are installed under the supported Node and
  pnpm runtime
- **THEN** Web lint, TypeScript, Vitest, and production build checks pass
- **AND** the existing App Router and Monaco DiffEditor integrations compile
  without application compatibility workarounds.

### Requirement: Upgrade scope remains limited to vulnerable owners

The security refresh SHALL avoid unrelated dependency majors and application
features.

#### Scenario: Candidate dependency diff is audited

- **WHEN** the manifest and lockfile changes are reviewed
- **THEN** direct version changes are limited to Next.js, its aligned ESLint
  configuration, Monaco Editor, and the required DOMPurify and Babel overrides
- **AND** remaining lockfile changes are transitive consequences of those
  declared changes.
