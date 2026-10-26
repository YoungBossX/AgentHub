## ADDED Requirements

### Requirement: Compatible security dependency refresh
The developer-maintained frontend graph SHALL resolve supported patched packages
through the real runtime/test importers, retaining existing patches and separate
Demo Vite 7 and test Vite 8 branches.

#### Scenario: Actual dependency bindings
- **WHEN** dependencies are installed from the frozen lockfile
- **THEN** Next and its ESLint config SHALL match and meet the 16.4.1 security floor
- **AND** DOMPurify SHALL meet 3.4.17, Vitest/mocker 4.1.12, Demo Vite 7.3.7, test Vite 8.1.6 and Zod 4.6.6
- **AND** Monaco and braces patches SHALL remain effective at their real importers

### Requirement: Preview does not expose the host editor
The server-owned preview boundary SHALL reject the reserved host-editor route
before Vite executes its middleware, without expanding Agent or host permissions.

#### Scenario: Route aliases are rejected
- **WHEN** an origin-form or absolute-form request matches the downstream editor route including case, slash, dot, dot-segment, legacy protocol or once-decoded aliases
- **THEN** the boundary SHALL return 403 without calling the downstream middleware
- **AND** malformed encoded paths SHALL retain the existing 400 response

#### Scenario: Legitimate preview continues to work
- **WHEN** normal HTML, TSX, CSS, React, Vite client or HMR requests are made
- **THEN** the bounded preview SHALL continue to render and update
- **AND** protected or out-of-scope filesystem paths SHALL remain denied

### Requirement: Versioned maintenance evidence
The maintenance task SHALL preserve existing data/configuration and historical
results while recording new audit, test, build and browser evidence externally.

#### Scenario: Independent maintenance validation
- **WHEN** the maintenance verification finishes
- **THEN** raw audit findings SHALL remain distinguishable from actual exploit evidence
- **AND** existing product data SHALL remain unchanged in place and new verification data/cache/build output SHALL use E:/Docker
