# Trusted demo validation profile

Automatically validate supported demo-frontend runs while the existing execution
lease/session queue is held, before the terminal commit and review collection.
The asynchronous phase remains cancellable and does not hold a terminal commit
reservation during subprocess execution. Lost leases cannot commit success.

Capture bounded regular files with no links/hardlinks and hashes of all source,
public assets, index and configuration plus the platform dependency lock and
trusted validation harness. Reject protected paths and unsupported executable
configuration; use the platform's installed dependencies without installation.
Run fixed server-owned Node/TypeScript/Vite commands in a fresh copy, not the
canonical worktree. Type-check cache and build outputs belong to the copy.
Do not run edited package scripts, Vite plugins or arbitrary test commands.

Run check, build, then the trusted Node build-output smoke suite; a build failure
does not run smoke tests against old output. Capture bounded redacted logs,
exit codes, timeout/cancellation and fingerprints in durable TaskRunEvent receipts.
Validation events are execution evidence, not deliverable Artifacts; they cannot
bypass scope/finalizer fencing. Recheck source and policy after execution and at
terminal acceptance.
Running receipts after restart are never accepted; no silent rerun on replay.

New reviews can use only server-produced completed receipts from the same run.
Model and command evidence are distinct. A native assessment must bind the same
unchanged source; rules/model/commands failing block QA, missing/unsupported
validation stays incomplete. All required commands plus native assessment and
rules passing permit configured_checks_passed, never a claim of general business
correctness. Scripted review may show tests passed while model review is absent.

Keep original review snapshots; API reads overlay current/expired/unverifiable
state from current files and policy. Same-run IDs alone never establish freshness.
The existing local staging gate checks this freshness too. Only the trusted Vite
demo profile is automatically executable; other targets retain explicit unknown
validation. This is local build validation, not a general OS sandbox.
