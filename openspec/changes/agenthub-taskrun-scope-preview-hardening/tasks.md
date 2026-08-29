## 1. Harden TaskRun scope verification before completion and artifacts

- [x] 1.1 Define the effective write-scope policy and fail-closed error mapping
  for violations and unverifiable evidence.
- [x] 1.2 Implement complete, content-free per-run worktree snapshots and the
  separately redacted protected ignored footprint with an internal opaque,
  domain-separated control digest for the `.git` pointer and resolved-gitdir
  descendants, without exposing their paths, fingerprints, or contents.
- [x] 1.3 Capture and persist a fresh complete baseline only after the writing
  TaskRun acquires the current Session worktree execution/target lock and
  immediately before `adapter.createRun`; compare its post-run delta, including
  staged, unstaged, untracked, deleted, and both rename endpoints.
- [x] 1.4 Require adapter-reported completion to remain in existing
  `collecting_diff` until durable scope-pass evidence permits exactly one
  terminal `completed` transition.
- [x] 1.5 Guard automatic and manual Diff, Review, Preview, and Deploy paths
  on the persisted scope-pass marker; reject legacy runs without it.
- [x] 1.6 Add safe TaskRunEvent/diagnostics evidence and focused regression
  coverage for a queued run whose launch baseline follows an earlier completed
  run, same-count protected content mutations, missing/failed control-digest
  comparison and crash recovery, deferred completion, and artifact guards
  without changing existing SSE behavior.
- [x] 1.7 Run focused verification, `git diff --check`, and
  `openspec validate agenthub-taskrun-scope-preview-hardening --strict`; update
  `docs/change-log.md` when implementation changes engineering files.
