## Context and decision

AgentHub permits multiple TaskRuns in one Session to reuse the same persisted
worktree. An earlier backend run can therefore leave a valid change in that
worktree before a later frontend run starts. A Git-base Diff or an
allowed-path-filtered Diff cannot prove which run made each write. The scope
guard must consequently use a complete baseline captured for each writing
TaskRun at its actual execution boundary, not the Session's Git base, a prior
TaskRun's baseline, or the later artifact path filter.

The guard is an evidence and lifecycle hardening slice. It does not change
target registration, adapters, queue/lock semantics, the SQLite model, or the
TaskRunEvent-backed SSE transport.

## Effective write-scope policy and error mapping

A writing TaskRun has exactly one effective write scope. The backend resolves
the TaskRun's Task, its Session and Workspace, and the Task's assigned target
through the current Workspace target registry. The resolved target's allowed
and denied path patterns define the scope: a canonical repository-relative
path is permitted only when an allowed pattern matches and no denied pattern
matches. Deny takes precedence. The global `.git`, `.env*`, `secrets`, and
`node_modules` policies are always included in the effective denied policy and
cannot be overridden by an allowed pattern.

Policy patterns are trusted only after canonical validation. A valid pattern
is a non-empty repository-relative segment or subtree with no traversal,
absolute/drive/UNC prefix, control character, or unsupported wildcard. `*`
and one trailing suffix wildcard such as `.env*` remain valid. If any allowed
or denied pattern is malformed, the target policy has no trusted identity,
path permission fails closed, and TaskRun scope evidence is `unverifiable`.

The shared target authorization API also validates every candidate path before
matching policy. A candidate must already be a canonical repository-relative
path: it is not stripped, separator-normalized, traversal-resolved, or treated
as a pattern. Empty, dot/traversal, absolute/drive/UNC, control-character,
wildcard, non-canonical separator, and leading/trailing-whitespace candidates
fail closed. `allows_path()` returns false and `denies_path()` returns true for
such a candidate. The same canonical candidate predicate validates relative
path lists in the public checkpoint projection, while printable Unicode path
segments and valid relative files or directories remain supported.

Task planned files, adapter-reported paths, a filtered Diff, TaskRun state, or
the absence of visible changes cannot grant or widen this scope. Both canonical
rename endpoints are evaluated. Only a complete, canonical, safely parsed
delta can establish an affected path; malformed path or rename syntax is not a
trusted observed violation and instead makes the evidence unverifiable.

At the locked launch baseline, the internal checkpoint binds the TaskRun to:

- the resolved Workspace ID and target ID;
- a versioned effective-policy schema; and
- a deterministic SHA-256 identity over the policy domain version, target ID,
  sorted unique normalized allowed patterns, and sorted unique normalized
  effective denied patterns (including the global protected patterns).

The identity deliberately excludes the target root and all raw host paths.
The same binding is retained in the execution-attempt runtime context and the
internal validation decision and pass marker. Post-run validation, decision
persistence, crash/recovery classification, and `require-pass` artifact guards
must match that binding against a fresh Workspace registry resolution. A
missing, malformed, forged, replayed, version-incompatible, or changed
Workspace/target/policy binding is never equivalent to a pass. The binding
fields are internal authorization evidence and are removed from public TaskRun
metrics and events. Public serialization is a value-validation boundary, not a
key-only filter. A decision or guard is emitted only after its complete internal
schema validates, it binds to the actual TaskRun row, and its target identifier
is safe for public evidence. The public TaskRun ID is taken from that row rather
than copied from persistence. Rejected and unverifiable decisions use fixed
public reason text; arbitrary persisted reason values are never copied. An
invalid decision or guard is omitted from the public metrics response.

Runtime context construction requires explicit non-empty Workspace, target,
baseline, capture-time, and execution-attempt bindings plus a canonical
SHA-256 policy identity. It cannot synthesize an `unbound-*` identity. Invalid
construction fails with `TASK_RUN_SCOPE_UNVERIFIABLE`; the opaque control key
may still be generated internally when the caller does not provide one.

Public checkpoint evidence is rebuilt from an explicit safe projection shared
by both TaskRun API metrics and the `task.checkpoint.created` event. Policy
patterns and repository paths must be canonical repository-relative values;
one invalid member omits the complete list field. Identifiers, hashes, Git
status, timestamps, and redacted snapshot audit metadata are retained only
after their value schema validates. Unavailable or invalid Git status and
snapshot reasons use fixed public reason codes. The projection never exposes
the target root, scope authorization bindings, internal snapshot entries, raw
fingerprints, protected control digests, or arbitrary persisted reason values.
Internal `metrics_json` remains unchanged for authorization and transactional
delivery.

The fail-closed mapping is:

| Trusted evidence | Decision | Error code |
|---|---|---|
| A complete canonical delta contains an out-of-scope path or either rename endpoint is not permitted | `rejected` | `TASK_RUN_SCOPE_VIOLATION` |
| A complete protected-control comparison proves a protected-path write | `rejected` | `TASK_RUN_SCOPE_VIOLATION` |
| TaskRun, Task, Session, Workspace, assigned target, canonical policy pattern, or effective policy identity cannot be resolved and matched | `unverifiable` | `TASK_RUN_SCOPE_UNVERIFIABLE` |
| Baseline, post-run snapshot, runtime context, lock binding, marker, protected control evidence, path/rename syntax, or versioned evidence is missing, malformed, unavailable, or cannot prove the comparison | `unverifiable` | `TASK_RUN_SCOPE_UNVERIFIABLE` |

The validation marker schema is versioned independently from the snapshot
schema. A pass marker authorizes downstream artifacts only when its TaskRun,
baseline, execution attempt, Workspace, target, and policy identity all match
the internal decision, checkpoint, and current registry resolution. Before
persistence, every candidate `passed` or `rejected` decision is independently
revalidated against the current complete delta and must equal that real
decision exactly; a forged or stale mismatch persists as `unverifiable`.

## Scope snapshot contract

TaskRun creation and queuing must not capture the scope baseline. A writing
TaskRun captures its complete pre-run snapshot only after it has acquired the
current Session worktree's existing execution/target lock and immediately
before `adapter.createRun` is called. The snapshot and its durable baseline
marker are bound to that TaskRun and lock-held execution attempt. A queued or
creation-time pre-capture cannot substitute for this launch-time baseline.

This timing is deliberate: if run B is created before run A but waits for the
same Session worktree lock, B's launch-time baseline is captured after A has
finished and includes A's completed worktree state. B is therefore checked
only against writes made after B actually acquired the lock. On adapter
completion, the same collector captures a complete post-run snapshot before
any Diff, Review, Preview, or Deploy artifact is created.

If the launch-time baseline cannot be captured and persisted, the adapter must
not start. If a process crash or recovery path leaves the system unable to
prove that the required baseline existed before a started adapter wrote files,
the run must fail closed as `TASK_RUN_SCOPE_UNVERIFIABLE`; it must not resume
artifact production or infer a baseline from its queued state.

The snapshot is intentionally non-filtered: it covers every non-protected path
in the assigned worktree, irrespective of the task's allowed-path filter. Each
entry records only:

- normalized repository-relative `path`;
- observed Git/worktree `status`; and
- a deterministic `fingerprint` (or an explicit absent value for a deletion).

It never stores file content. The collector must account for staged,
unstaged, untracked, and deleted entries. For a rename, both the old and new
path are represented so that a rename cannot move an out-of-scope path past
the gate. The snapshot delta compares the two complete footprints and then
tests every affected path, including both rename endpoints, against the
TaskRun's effective write scope and protected-path policy.

Before fingerprinting an ordinary, non-protected regular file, the collector
must prove from the opened descriptor that its link count is exactly one and
must recheck that invariant before and after every content read. An existing
or open-time hardlink alias makes the complete snapshot unavailable without
persisting the link count or exposing an external alias path. This transient
single-link ownership check does not replace or constrain the protected
control-digest handling for the `.git` pointer, resolved gitdir, or other
protected records.

Protected paths are not silently discarded. They are represented separately as
a `protectedIgnoredFootprint` with a rule/category and aggregate count, plus
an opaque protected control digest. This preserves a redacted audit signal
without exposing `.env`, `secrets/`, `node_modules`, `.git`, or paths outside
the assigned worktree.

For a Git worktree, the `.git` entry can be a pointer file rather than a
directory. The protected boundary therefore explicitly includes both that
worktree `.git` pointer file and every descendant of the `gitdir` it resolves
to. Snapshot and validation collection must recognize both protected metadata
surfaces and preserve separate control evidence for each. A transient internal
collector normalizes protected tree records (including the internal tree
location and content identity needed to distinguish individual modifications),
then computes a keyed, domain-separated hash of that canonical record stream.
Only the resulting non-reversible opaque control digest may persist in internal
TaskRun metrics, solely for pre/post comparison. It detects a content change to
the `.git` pointer or any resolved-gitdir descendant even when the safe
categories and aggregate counts are unchanged.

Neither the normalized records nor their keys are persisted or exposed. The
stored digest must not contain the real resolved `gitdir` path, an entry path,
a raw fingerprint, or content, and it must never be exposed to an adapter,
adapter instruction, UI, artifact, TaskRunEvent, diagnostic, or error message.
The collector must not treat either protected surface as ordinary in-scope
files. A change attempt on either surface is a protected scope violation,
reported only by its safe category.

### Filesystem case-semantics binding (OpenSpec 1.2)

Protected names, excluded gitdir roots, Git metadata paths, and absolute
containment checks are classified against the assigned filesystem's observed
per-directory case semantics rather than a process-wide Windows/POSIX guess.
The collector uses an immutable observation chain from the volume root through
the assigned root. When a component differs only by case, it resolves the rule
of that component's parent directory and rechecks the chain before and after
the decision. Absolute trusted-gitdir, pointer-candidate, and Git-executable
prefixes apply this rule at every mismatched component, so a case alias cannot
be reinterpreted as the assigned root merely because all prefix strings
case-fold equally. Filesystem equivalence is restricted to exact spelling or
ASCII-only folding after the relevant parent is proven insensitive. A Python
Unicode fold such as `ßroot -> ssroot` is never equality evidence for
containment, child resolution, excluded-root matching, Git metadata, or
protected-name classification. If a live protected component has a Unicode
fold that reaches an ASCII protected spelling while its ASCII fold does not,
the component is ambiguous and capture fails closed instead of treating it as
either an authorized alias or an ordinary path.

Repository-relative path derivation is a projection after authorization, not
an authorization primitive. The collector first validates the bound root
observations, proves equal-or-descendant containment with the per-parent case
semantics above, revalidates the root observations, and only then slices the
already-proven absolute path parts. A successful lexical `Path.relative_to()`
operation is never used as containment evidence.

The default resolver is read-only and deliberately does not cache a directory
result. Every resolution scans the current children, selects an existing name
with a reversible ASCII letter, changes exactly one ASCII character to form
the alternate spelling, and performs no-follow observations before rescanning
the children and again after that rescan. All spellings in every ASCII-fold
collision group are observed in one linear batch; if any two listed spellings
in a group resolve to the same identity, the group is ambiguous even when the
first two happen to be distinct. Non-ASCII case mappings are not witnesses. If
an observation changes, the child listing changes, no suitable witness exists,
or the resolver is unavailable, the result is `unknown` and the complete
capture is unavailable. Exact-name ordinary entries and empty ordinary
directories do not require a case probe and retain their existing behavior.

The absolute Git executable is also bound as evidence rather than retained as
an unchecked command string. After excluding the assigned root and trusted
gitdir with their bound case semantics, the collector records a complete
no-follow observation chain from the executable's volume root through every
parent to the executable leaf. It also takes a transient SHA-256 binding of the
executable bytes through the existing no-follow descriptor reader. Unlike an
ordinary worktree-file fingerprint, this executable-only read permits multiple
hard links because Git for Windows can install `git.exe` with multiple command
names backed by the same file. It still rejects Windows named streams and
rechecks the complete ancestor chain throughout the read. A write through any
hardlink alias changes the bound bytes and is rejected at the next digest
check. The chain and content binding are checked
immediately before the runner, in the runner `finally` path, and after the
post-run trusted-gitdir check. Any unavailable or changed observation or digest
makes the snapshot unavailable. The digest stays only in the private in-memory
executable binding and is never persisted or exposed. On Windows, Python path
stat may synthesize executable `0111` bits from the `.exe` suffix while fstat
cannot; only this executable reader may ignore that permission-bit difference,
and it still requires equal device, inode, file type, and file attributes. The
single-link rule for ordinary non-protected worktree files remains unchanged.

These case and executable controls remain path-based checks around a separate
process launch, not one atomic filesystem transaction. They detect changes
visible at their observation boundaries but cannot eliminate an extremely
narrow swap-and-restore race performed entirely between two checks. Closing
that residual TOCTOU window would require an operating-system primitive for
handle-bound verified execution or a stronger sandbox and is outside OpenSpec
1.2; this design therefore does not claim atomic protection against a local
actor that can mutate and restore those paths inside that interval. The
transient digest also binds consistency only after the first observation; it
does not establish that the installed Git executable was trustworthy before
that binding. ACL policy, installation provenance, and a broader trusted-tool
allowlist remain outside this change.

Snapshot schema v2 deliberately does not add or persist a per-directory case
binding. A rootless v2 metadata replay therefore rejects protected ASCII-style
case aliases such as `.GIT`, `.Env.Local`, `NODE_MODULES`, and `SECRETS`
and Unicode-fold ambiguities such as `ſecrets` conservatively, even if a live
capture originated on a case-sensitive directory where an exact
differently-cased name could be ordinary. This is a deliberate cross-process
limitation: without a future versioned binding, such metadata cannot authorize
completion or artifacts. The private filter for a newly protected gitdir
transition also compares ASCII case aliases conservatively; the simultaneous
protected-control digest change already guarantees rejection, so this
redaction cannot turn a violation into a pass.

### Windows NTFS named alternate data streams (OpenSpec 1.2)

On Windows, every ordinary or protected regular file and every directory that
is opened, read, or scanned by the snapshot collector is checked with a lazy
Win32 `FindFirstStreamW`/`FindNextStreamW` enumeration. The assigned root,
empty ordinary directories, protected subtrees, the worktree `.git` surface,
and the resolved gitdir use the same checks. Only the canonical default data
stream `::$DATA` is accepted. A named stream, an unexpected Win32 error, an
unavailable stream API/filesystem result, an enumeration exception, or an
unreliable `FindClose` makes the capture unavailable and fail closed.

Regular files are checked before opening, after opening, before and after each
content read, and at the final read boundary. Directories are checked before
and after each stable `scandir`. These checks are made only after the existing
no-follow type and path-observation checks; symlinks and reparse points are
never enumerated, and protected symlinks retain their existing stable readlink
evidence. The non-Windows path keeps its existing behavior. Stream names,
counts, paths, and contents are transient implementation details and never
enter entries, fingerprints, protected digests, persisted metadata, events,
diagnostics, or errors. An unavailable result uses the fixed safe reason and
empty entries/control evidence already defined by the collector.

## Persisted evidence

The implementation stores a versioned `taskRunScopeDecision` record for every
validation outcome in `TaskRun.metrics_json`. It binds the launch-time per-run
baseline identity, lock-held execution-attempt identity, Workspace, effective
scope identity, result (`passed`, `rejected`, or `unverifiable`), safe reason
code, counts, and timestamp. A separate `taskRunScopeGuard` marker is written
only for a persisted `passed` decision and repeats the authorization bindings
needed by artifact-producing paths.

The decision record must be written even when verification fails. The pass
marker must be absent for `rejected` or `unverifiable` decisions, and a missing,
malformed, or version-incompatible marker is not equivalent to a pass. The
authoritative require-pass check must derive any refusal from the bound durable
decision rather than an earlier transient validation result. In particular,
TaskRuns created before this change have no marker and must fail closed for
manual artifact creation. Artifact guards may expose a short, redacted reason,
but must not infer a pass from a legacy Diff, `base_ref`, TaskRun state, or the
absence of detected changes.

## Deferred completion lifecycle

Adapter process success is not TaskRun success. When an adapter reports that it
completed, the Run Engine records adapter-completed evidence and MUST retain or
transition the TaskRun to the existing non-terminal `collecting_diff` state. It
MUST NOT use any terminal state at that point. It then captures the post-run
snapshot and evaluates the scope gate.

```text
pre-run complete snapshot
  -> adapter execution
  -> adapter-completed evidence (non-terminal)
  -> post-run complete snapshot
  -> scope gate
       -> passed: persist the marker, create normal evidence, then transition
          exactly once to terminal completed
       -> violation: transition to failed with TASK_RUN_SCOPE_VIOLATION
       -> unverifiable: transition to failed with TASK_RUN_SCOPE_UNVERIFIABLE
```

A failed or unverifiable scope gate prevents Diff, Review, Preview, and Deploy
creation for that run. It must not enqueue automatic preview/deploy work,
produce a filtered Diff artifact, or expose a success-style artifact card. The
normal success path must first durably write the scope-pass marker and only
then make exactly one transition from the existing deferred lifecycle to the
terminal `completed` state. Existing terminal cleanup, queue/lock release,
retry, and diagnostics consumption remain delegated to their current lifecycle
services.

## Artifact guards

Every artifact-producing entry point, including manual collection or request
paths for Diff, Review, Preview, and Deploy, resolves the source TaskRun and
requires `taskRunScopeGuard.result == "passed"`. This is required even if the
run is already `completed`, already has a filtered Diff, or is an old run. A
guard refusal is fail-closed: it creates no new artifact and records safely
redacted diagnostics/event evidence where the existing lifecycle supports it.

The guard is intentionally not an adapter-specific check. Codex, Claude Code,
and ScriptedMock all create the same snapshot and scope evidence and therefore
receive the same completion and artifact rules.

## Failures and diagnostics

An observed affected path outside the effective write scope, a protected-path
write, or an invalid rename endpoint fails the TaskRun with
`TASK_RUN_SCOPE_VIOLATION`. A collector failure, missing baseline or protected
control digest, unreadable post-run worktree, invalid snapshot data, protected
tree read/parse/compare failure, inability to determine the effective scope,
or crash/recovery state that cannot prove the baseline and digest comparison
fails with `TASK_RUN_SCOPE_UNVERIFIABLE`. Neither condition may be downgraded
to advisory review.

Diagnostics and events may state the guard result, run ID, target ID, snapshot
version, counts, and safe categories. They must redact protected paths, host
paths, file contents, secret values, and raw fingerprints. This change only
adds events consumed by the existing TaskRunEvent flow; it does not modify SSE
event delivery or recovery semantics.

Informational checkpoint-created and scope-passed events do not become failure
evidence solely because their redacted text contains words such as
`unavailable`. A recognized explicit `errorCode` remains authoritative,
including scope validation and real provider errors; only text-derived failure
inference is suppressed for those informational event types.

## Verification strategy

Focused backend tests should cover:

- an out-of-scope `package.json` modification after a scoped writing run: the
  run fails with `TASK_RUN_SCOPE_VIOLATION` and creates no downstream artifact;
- two runs sharing a worktree, where the second run's baseline retains the
  first run's backend change while only the second run's frontend delta is
  checked, including a run created and queued before that first run finishes;
- staged, unstaged, untracked, deleted, and both sides of renamed paths;
- an adapter attempt to modify the worktree `.git` pointer and a separate
  attempt to modify a descendant of its resolved `gitdir`, both rejected as
  protected scope violations without exposing the real resolved `gitdir` path,
  including a content-only mutation with unchanged safe category and count;
- adapter-reported completion retaining `collecting_diff` until scope pass,
  followed by exactly one terminal `completed` transition; and
- missing or unavailable snapshots and legacy no-marker runs, which fail closed
  with safely redacted `TASK_RUN_SCOPE_UNVERIFIABLE` evidence, including a
  missing protected control digest, protected-tree read/parse/compare failure,
  and a crash/recovery path that cannot prove the pre/post comparison; and
- manual Diff/Review/Preview/Deploy attempts with absent, failed, or passed
  markers.

Run the focused API checks plus `git diff --check` and strict OpenSpec
validation. Implementation documentation must update `docs/change-log.md`.
