## ADDED Requirements

### Requirement: Writing TaskRun completion is gated by verified scope

The system SHALL acquire the current Session worktree's existing execution/
target lock and immediately before `adapter.createRun` capture and persist a
writing TaskRun's complete per-run pre-run snapshot. It SHALL compare that
launch-time snapshot with its post-run snapshot and pass the resulting delta
through the effective write-scope policy before it transitions to `completed`
or creates a Diff, Review, Preview, or Deploy artifact. Adapter-reported
completion SHALL remain in the existing non-terminal `collecting_diff` state
until this gate passes. A snapshot captured when the TaskRun was created or
queued SHALL NOT satisfy this requirement.

#### Scenario: An out-of-scope package manifest change blocks completion and artifacts

- **WHEN** a writing TaskRun is scoped to frontend source files and the adapter
  changes `package.json` outside that effective write scope
- **THEN** the TaskRun MUST transition to `failed` with
  `TASK_RUN_SCOPE_VIOLATION`
- **AND** the system MUST NOT create Diff, Review, Preview, or Deploy artifacts
  for that TaskRun
- **AND** the system MUST NOT transition the TaskRun to `completed`

#### Scenario: A queued run captures its baseline only at its locked execution boundary

- **WHEN** TaskRun B is created and queued for a Session worktree before
  TaskRun A finishes, and B later acquires that worktree's execution/target lock
- **THEN** the system SHALL capture and persist B's baseline immediately before
  `adapter.createRun`, after A's completed worktree state is present
- **AND** B's scope gate SHALL compare only changes made after B's own
  launch-time baseline
- **AND** a baseline captured for B while it was created or queued SHALL NOT be
  used as scope-pass evidence
- **AND** if the required launch-time baseline cannot be captured and persisted,
  the adapter SHALL NOT start or the run SHALL fail closed with
  `TASK_RUN_SCOPE_UNVERIFIABLE`

#### Scenario: Adapter completion remains collecting_diff until one scope-authorized completion

- **WHEN** an adapter reports `completed` for a writing TaskRun
- **THEN** the TaskRun SHALL remain in the existing non-terminal
  `collecting_diff` state while the post-run snapshot and scope gate execute
- **AND** the system SHALL NOT make a terminal transition before the persisted
  scope-guard marker records `passed`
- **AND** after that marker is durably persisted, the system SHALL transition
  exactly once to terminal `completed`

### Requirement: Every writing run uses its own complete shared-worktree baseline

The system SHALL capture a fresh, complete, non-filtered baseline for every
writing TaskRun in its assigned Session worktree. The snapshot SHALL record
only path, status, and fingerprint data; it SHALL cover staged, unstaged,
untracked, and deleted changes, and SHALL evaluate both endpoints of a rename.

#### Scenario: A later frontend run preserves an earlier backend change in its baseline

- **WHEN** a backend TaskRun has already changed the shared Session worktree
  and a later frontend TaskRun begins in that same worktree
- **THEN** the frontend TaskRun baseline MUST include the already-present backend
  state as its starting state
- **AND** scope evaluation for the frontend TaskRun MUST check only the delta
  created after its own baseline
- **AND** a new out-of-scope frontend-run write MUST still fail the scope gate

### Requirement: Manual artifact production requires persisted scope-pass evidence

The system SHALL require a durable `passed` scope-guard marker in the source
TaskRun metrics before any manual Diff, Review, Preview, or Deploy production
path creates an artifact. A missing, malformed, failed, or unverifiable marker
SHALL fail closed, including for TaskRuns created before the marker existed.

#### Scenario: A legacy completed run without a scope marker requests an artifact

- **WHEN** a user manually requests Diff, Review, Preview, or Deploy work for a
  previously completed TaskRun that has no scope-guard marker
- **THEN** the request MUST be refused without creating the requested artifact
- **AND** the refusal MUST be classified as `TASK_RUN_SCOPE_UNVERIFIABLE` or an
  equivalent safe diagnostic
- **AND** the system MUST NOT infer scope pass from a Git base, a filtered Diff,
  an existing TaskRun state, or absence of visible changes

### Requirement: Unavailable scope snapshots fail closed and protect sensitive evidence

The system SHALL fail closed when it cannot capture, validate, or compare the
complete scope snapshots required for a writing TaskRun. Protected-path ignores
SHALL be retained as a separate redacted footprint rather than silently
removed from audit evidence. For a Git worktree, the protected boundary SHALL
include the worktree `.git` pointer file and descendants of the `gitdir` it
resolves to; the system SHALL never expose the real resolved `gitdir` path to
an adapter or persisted/displayed evidence. The redacted footprint SHALL
include an internal-only, non-reversible opaque control digest: a keyed,
domain-separated hash of canonical protected tree records. The persisted digest
SHALL be used only for pre/post comparison and SHALL NOT contain a real gitdir
path, entry path, raw fingerprint, or content.

The live collector SHALL classify protected names, excluded gitdir roots, Git
metadata paths, and absolute root containment using the observed case semantics
of each relevant parent directory. It SHALL use a root-bound, read-only probe
over existing no-follow observations and SHALL NOT create a probe entry, cache
a directory result, or use a process-wide platform guess as authorization
evidence. Each probe SHALL change exactly one reversible ASCII letter, SHALL
take no-follow observations before the child rescan and again after it, and
SHALL NOT use a non-ASCII case mapping as a witness. Every spelling in every
ASCII-fold collision group SHALL be included in one stable batch; any two
listed spellings in a group that resolve to the same identity, or any changed,
unknown, ambiguous, or unstable evidence, SHALL make the complete capture
unavailable. Exact ordinary names and empty ordinary directories SHALL NOT
require such a probe.

All live path equality used for containment, child resolution, excluded roots,
Git metadata, or protected classification SHALL be exact or ASCII-fold-only
after insensitive semantics are proven for the relevant parent. Unicode
casefold equivalence SHALL NOT authorize equality. If Unicode folding reaches
an ASCII protected name while ASCII folding does not, live capture SHALL fail
closed as ambiguous rather than classifying the component as ordinary.

The collector SHALL derive a repository-relative value only after validating
the bound root observations, proving equal-or-descendant containment with the
case semantics of every relevant parent, and revalidating the root observations.
It SHALL then project the relative value by slicing the proven path components;
it SHALL NOT treat a successful lexical `Path.relative_to()` operation as
authorization or containment evidence.

Before running Git plumbing, the collector SHALL bind the absolute Git
executable with a complete no-follow observation chain from its volume root
through every parent to the executable leaf and SHALL create a transient
SHA-256 binding of its bytes through a no-follow descriptor read with Windows
named-stream and ancestor rechecks. This executable-only read SHALL permit an
existing hardlink count greater than one for compatibility with Git for
Windows, while retaining the executable's device, inode, file type, attributes,
complete content digest, and observation-chain checks. It SHALL recheck both
the chain and content binding before the runner, in a `finally` path after the
runner returns or raises, and after the post-run trusted-gitdir check. Missing
or changed executable evidence, including bytes changed through another
hardlink alias, SHALL make the complete capture unavailable.
The content binding SHALL NOT be persisted or exposed. A Windows-only
path-stat/fstat difference limited to synthesized executable `0111` bits MAY be
ignored only on this trusted-executable read; device, inode, file type, and file
attributes SHALL still match, and ordinary/protected file reads SHALL retain
their exact existing identity comparison. These checks SHALL NOT claim that an
executable was trustworthy before its first binding, nor eliminate a
swap-and-restore race occurring completely between observation boundaries.

Because snapshot schema v2 contains no persisted per-directory case binding, a
rootless metadata replay SHALL conservatively reject protected case aliases
such as `.GIT`, `.Env.Local`, `NODE_MODULES`, and `SECRETS`, together with
Unicode-fold protected ambiguities such as `ſecrets`; it SHALL NOT infer
case-sensitive safety from the current process or platform.

On Windows, the collector SHALL enumerate data streams for every ordinary or
protected regular file and directory it reads or scans, including the assigned
root, empty ordinary directories, the worktree `.git` pointer or directory,
protected subtrees, and the resolved gitdir. It SHALL accept only `::$DATA` and
SHALL fail closed when it observes a named stream or cannot prove enumeration
and handle closure completed reliably. It SHALL NOT enumerate a symlink or any
reparse point, and SHALL NOT persist or expose a stream name, count, path, or
content. Non-Windows capture behavior SHALL remain unchanged.

#### Scenario: The post-run snapshot is unavailable and a protected item was ignored

- **WHEN** the scope guard cannot obtain a valid post-run snapshot after adapter
  completion and the collector encounters protected-path ignores
- **THEN** the TaskRun MUST transition to `failed` with
  `TASK_RUN_SCOPE_UNVERIFIABLE`
- **AND** the system MUST NOT create Diff, Review, Preview, or Deploy artifacts
- **AND** stored metrics, events, and diagnostics MUST expose only safe
  aggregate protected-ignore evidence and MUST NOT expose protected paths,
  host paths, file contents, secrets, or raw fingerprints

#### Scenario: A Windows named data stream makes the snapshot unavailable

- **WHEN** an ordinary file or directory, a protected file or directory, the
  worktree `.git` surface, or the resolved gitdir has any NTFS named alternate
  data stream
- **THEN** the complete snapshot MUST fail closed as unavailable
- **AND** regular files MUST be checked before and after opening/reading,
  including before and after every content read, while directories MUST be
  checked before and after each stable scan
- **AND** the unavailable snapshot MUST use the fixed safe reason with empty
  entries and no protected control digest
- **AND** stored or displayed evidence MUST NOT expose the stream name, stream
  count, host path, stream content, or any secret contained in the stream
- **AND** symlinks and reparse points MUST NOT be passed to stream enumeration

#### Scenario: Unknown directory case semantics make an alias unverifiable

- **WHEN** protected or excluded-path classification requires comparing a
  case-variant component and the component's parent directory has no stable,
  read-only case-semantics witness
- **THEN** the complete snapshot MUST fail closed as unavailable
- **AND** the collector MUST NOT create a probe file or use a platform-wide
  case assumption
- **AND** exact ordinary paths and unrelated empty directories MUST retain
  their existing snapshot behavior

#### Scenario: A case witness is ambiguous or changes during resolution

- **WHEN** a case probe has only a non-ASCII mapping, observes both listed ASCII
  spellings with the same identity, observes any duplicate identity among more
  than two spellings in one ASCII-fold group, or sees its child listing or
  no-follow observation change after the child rescan
- **THEN** the resolver MUST return `unknown` without caching that result
- **AND** the complete snapshot MUST fail closed as unavailable

#### Scenario: Unicode folding is not filesystem equality evidence

- **WHEN** two path components have the same Python Unicode casefold but do not
  have the same exact or ASCII-folded spelling, such as `ßroot` and `ssroot`
- **THEN** containment and child resolution MUST treat them as different
- **AND** a live component whose Unicode fold reaches a protected ASCII name
  MUST make capture unavailable rather than becoming an ordinary path
- **AND** rootless v2 metadata MUST continue to reject that protected ambiguity

#### Scenario: Relative projection follows a bound containment proof

- **WHEN** the collector converts an absolute candidate below the assigned root
  to a repository-relative value
- **THEN** it MUST validate and revalidate the assigned-root observations and
  prove per-parent case-aware containment before slicing path components
- **AND** lexical `Path.relative_to()` success MUST NOT authorize the candidate

#### Scenario: Git executable evidence or content changes around the runner

- **WHEN** any component in the volume-root-to-executable no-follow observation
  chain is missing or changes, or the executable bytes change in place through
  its selected path or another hardlink alias, before the runner, in the
  runner-finally check, or after the trusted-gitdir post-check
- **THEN** the complete snapshot MUST fail closed as unavailable
- **AND** a pre-run failure MUST occur before Git plumbing is invoked
- **AND** the transient executable digest MUST NOT enter persisted or public
  evidence
- **AND** an otherwise stable multi-link executable MUST remain usable; the
  single-link ownership rule remains mandatory only for ordinary non-protected
  worktree file fingerprints
- **AND** the system MUST NOT describe these non-atomic checks as eliminating a
  swap-and-restore race wholly contained between observations or as proving
  trust before the executable's first binding

#### Scenario: Rootless v2 metadata cannot replay a protected case alias

- **WHEN** persisted snapshot-v2 metadata contains a protected case alias such
  as `.GIT`, `.Env.Local`, `NODE_MODULES`, or `SECRETS`
- **THEN** the metadata MUST be treated as invalid or unavailable because it
  carries no per-directory case binding
- **AND** the system MUST NOT authorize completion or artifacts by assuming the
  current process has the same case semantics as the capture directory

#### Scenario: An ordinary hardlink alias makes the snapshot unavailable before content read

- **WHEN** an ordinary, non-protected worktree regular file has a descriptor
  link count other than one, including when a second hardlink is created after
  open and before the first content read
- **THEN** the complete snapshot MUST fail closed as unavailable
- **AND** the collector MUST NOT read that descriptor after observing the
  invalid link count
- **AND** the unavailable snapshot MUST contain no entries or protected control
  digest and MUST NOT expose an external alias path
- **AND** this single-link rule SHALL NOT replace the protected control-digest
  handling for the `.git` pointer, resolved gitdir, or other protected records

#### Scenario: The protected control digest detects same-count content changes

- **WHEN** the `.git` pointer file or a descendant of its resolved `gitdir` has
  a content modification while its protected category and aggregate count are
  unchanged
- **THEN** the pre/post opaque control-digest comparison SHALL detect the
  modification as a protected scope violation
- **AND** the system SHALL retain the digest only in internal TaskRun metrics
  for comparison and SHALL NOT expose it or the normalized protected tree
  records to an adapter, UI, artifact, TaskRunEvent, diagnostic, or error

#### Scenario: Protected control evidence cannot be proven

- **WHEN** a required scope baseline or protected control digest is missing, or
  protected-tree reading, parsing, comparison, or post-crash recovery cannot
  prove the required pre/post evidence
- **THEN** the TaskRun SHALL fail closed with
  `TASK_RUN_SCOPE_UNVERIFIABLE`
- **AND** the system SHALL NOT start an adapter when the launch-time evidence
  failure is known before `adapter.createRun`
- **AND** the system SHALL NOT create Diff, Review, Preview, or Deploy
  artifacts

#### Scenario: Git worktree metadata surfaces are protected without gitdir disclosure

- **WHEN** an adapter attempts to modify either the worktree `.git` pointer
  file or a descendant of its resolved `gitdir`
- **THEN** snapshot and scope validation SHALL detect each protected metadata
  surface as a protected scope violation
- **AND** the TaskRun SHALL fail with `TASK_RUN_SCOPE_VIOLATION` and create no
  Diff, Review, Preview, or Deploy artifact
- **AND** adapter-visible instructions, stored metrics, events, diagnostics,
  artifacts, and errors SHALL NOT reveal the real resolved `gitdir` path
