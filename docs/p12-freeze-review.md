# P12 Platform Core Consolidation Freeze Review

**Date:** 2026-05-26

## Result

P12 is ready to freeze as Platform Core Consolidation.

P12 consolidated the platform core around clearer planner boundaries,
canonical shared context, provider instruction adapters, handoff artifacts,
artifact references, mission trace read models, decomposed workspace UI
components, artifact version metadata, and minimal built-in agent profiles.

No new provider marketplace, custom-agent UI, full artifact editor, multi-user
mission control, desktop/IDE/CLI client, cloud deploy provider, LLM dynamic
planner, or scheduler replacement was implemented.

## Rehearsal

The final rehearsal used a fresh SQLite database to avoid stale local demo DB
schema drift:

`sqlite:///data/p12-freeze-rehearsal-3.sqlite3`

Flow covered:

```text
new session
-> @orchestrator build a login page for the demo app
-> plan/task graph
-> ScriptedMock frontend agent run
-> diff
-> review
-> handoff
-> preview
-> local staging deploy
-> follow-up button copy change
-> artifact version v2
-> updated preview
-> updated local staging deploy
```

## Evidence

| Item | Evidence |
|---|---|
| Session ID | `3745b760-ff59-449a-a06b-b00a4cf2e4a2` |
| Worktree | `.worktrees/7ca4d93e-e50e-437e-b6f9-67e93a8efccf/3745b760-ff59-449a-a06b-b00a4cf2e4a2` |
| Login message ID | `28af82e8-a9b6-4cc8-8f8a-b1ae39776ecc` |
| Planning task ID | `214994fd-1ead-41fb-b6e7-edc25295bfb3` |
| Frontend task ID | `30ae5908-6925-4f41-9f15-7e7bff08fbcb` |
| QA task ID | `471f25ed-7855-472a-8aab-aafa7ec8989c` |
| First run ID | `89dd57d7-c003-4a5e-b9fa-a4ca6ed0e326` |
| First adapter | `scripted_mock` |
| First run state | `completed` |
| First changed files | `apps/demo/src/App.tsx` |
| First diff artifact ID | `b3272f5c-109d-423e-9c06-867dc06a6a7a` |
| First review artifact ID | `255ad376-128f-4c55-8328-4a5bfe6f6f4b` |
| Handoff artifact ID | `5327d10d-3dcc-4422-ab90-802fbe15807d` |
| First preview | `9e578e93-ced3-41ed-a8c2-5f6752f4b455`, healthy at `http://127.0.0.1:60536` |
| First local staging deploy | `bf87222a-ce40-4de5-85d7-a5f7964c5640`, ready at `http://127.0.0.1:60553` |
| Follow-up message ID | `2f1a11e0-5315-4cfa-9550-dc52e9171982` |
| Follow-up task ID | `5e35646d-3e6b-4599-93d2-5e0428e240a8` |
| Follow-up run ID | `c5d852b8-1347-48ad-91f2-4c8e92f94800` |
| Follow-up adapter | `scripted_mock` |
| Follow-up run state | `completed` |
| Follow-up diff artifact ID | `4f1ba32b-ba9e-40bb-b1c3-6aa258b8dcd0` |
| Follow-up review artifact ID | `bea796fe-71c7-4643-a857-42c09694d521` |
| Artifact version v2 ID | `5f1e1516-33a3-4951-bde4-c68da759e1f6` |
| Version parent artifact | `b3272f5c-109d-423e-9c06-867dc06a6a7a` |
| Follow-up preview | `049ca7aa-c7e0-46a9-ba06-ffc81d77b347`, healthy at `http://127.0.0.1:60556` |
| Follow-up local staging deploy | `b7e52a37-09a6-4246-9f87-b406f02a251a`, ready at `http://127.0.0.1:60565` |

First run events included:

```text
task.state -> task.state -> message.delta -> task.state -> completed
-> artifact.diff.ready -> artifact.review.ready -> artifact.preview.ready
-> artifact.deploy.ready
```

The artifact version chain for the follow-up diff included version `1` and a
version `2` record whose `parentArtifactId` points to the first login-page diff
artifact.

## Caveats

- The rehearsal used ScriptedMockAdapter for deterministic local evidence. No
  fresh Claude Code or Codex mutation was run.
- The default local SQLite database had stale schema from earlier phases, so
  the rehearsal used a fresh SQLite file with the current P12 schema.
- Session worktree setup symlinks for `node_modules` were excluded through the
  worktree-local Git exclude file during rehearsal so P10 dirty-worktree
  conflict detection stayed meaningful.
- Local staging build output was removed before the follow-up write task. This
  kept generated `dist` evidence from blocking the next source edit as a dirty
  worktree conflict.
- Preview and staging URLs were healthy when created and recorded, but the
  one-shot rehearsal process did not keep them long-lived after process exit.
- The P12 handoff service was invoked explicitly after diff/review/deploy
  evidence existed so the handoff artifact could include artifact references.

## Validation

Validation was run after documentation and task updates:

| Command | Result |
|---|---|
| P12 freeze rehearsal | Pass |
| `pnpm check` | Pass |
| `pnpm test` | Pass |
| `pnpm demo:api:test` | Pass |
| `git diff --check` | Pass |
| `openspec validate agenthub-p12-platform-core-consolidation --strict` | Pass |

Recommended freeze tag:

`p12-platform-core-consolidation-freeze`
