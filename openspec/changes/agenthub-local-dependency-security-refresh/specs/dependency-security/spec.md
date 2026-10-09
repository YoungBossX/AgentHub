## ADDED Requirements

### Requirement: Current dependency findings have verified resolution
The local workspace SHALL avoid known vulnerable runtime versions when a
compatible patch is available and SHALL investigate local-tool findings without
silently suppressing audit evidence.

#### Scenario: Compatible patched packages exist
- **WHEN** fresh audit data identifies vulnerable installed versions
- **THEN** the lockfile resolves compatible patched versions
- **AND** production audit, builds and local workflow verification pass

#### Scenario: No published fix exists for a local-tool dependency
- **WHEN** an advisory has no patched release
- **THEN** importer reachability and any bounded mitigation are independently verified
- **AND** the raw remaining advisory is disclosed without pretending it disappeared

### Requirement: Upgrade preserves local behavior
The upgrade SHALL preserve localhost startup, Agent API integration, Monaco
Diff, rich chat and existing data while avoiding unrelated dependency changes.

#### Scenario: Restart after installing patches
- **WHEN** the owned Web process restarts using the upgraded dependencies
- **THEN** existing sessions, execution artifacts and previews remain usable
- **AND** unrelated processes and stored Agent execution evidence remain unchanged

#### Scenario: The editor embeds or downloads different dependency versions
- **WHEN** the Diff editor loads in the browser
- **THEN** it uses the installed local editor and audited sanitizer package
- **AND** the editor and worker function with external network requests blocked
- **AND** a local loading failure retains the readable patch and retry action
