# P15b Freeze Review: Real LLM Planner Engine

**Date:** 2026-05-29

## Decision

P15b is ready to freeze.

AgentHub verified the Breakout acceptance path with a real `llm_v1` planner
provider, validated task creation, real coding-provider execution, build
evidence, preview, and local staging deploy. The first real coding run did not
freeze successfully because staging deploy exposed a TypeScript strictness
build failure. The failure was preserved as evidence, then a follow-up fix task
used the existing AgentHub task/run path and real coding providers to repair
the generated app before freeze.

## First Real Planner / Coding Run

The first smoke used a real Claude CLI planner and a real Claude Code coding
run:

| Item | Value |
|---|---|
| Planner provider | `claude_cli` |
| Planner source | `real_llm` |
| Session ID | `7e47c4b7-105b-4cef-89da-efb305d71be1` |
| Message ID | `8720cf6b-f260-4ba1-b9c3-148b8327d175` |
| Task IDs | `a1b33a79-cb7f-4fed-966e-669e1323ed60`, `23cd3850-1b11-45b7-9320-6317ef52dde2` |
| Coding TaskRun ID | `08a78ee1-f313-4051-ada2-ee8540289114` |
| Coding adapter | `claude_code` |
| Coding run state | `completed` |
| Diff artifact ID | `ab7cc360-f32f-4976-982c-824a4eebe289` |
| Review artifact ID | `23067f27-980e-4a5b-afa7-7a02b4870e9f` |
| Preview | `57f56c1b-e8ff-4053-ad08-94771ce3ae7c`, healthy at `http://127.0.0.1:65013` |
| Staging deploy | `7a1f4d6a-a745-44b6-9f9b-958618b6ca99`, `failed` |

The staging deploy failed honestly because `pnpm build` failed on
`apps/demo/src/components/BreakoutGame.tsx` with `TS18047: 'ctx' is possibly
'null'`. P15b-7 was not marked complete at this point.

## Follow-up Fix Run

The follow-up used the same session and the existing direct assignment /
TaskRun path with the build failure as context.

Before the successful fix, AgentHub uncovered and fixed two coordination bugs:

- planned `llm_v1` QA review tasks were not being satisfied by the generated
  review artifact, so follow-up work could remain blocked behind an already
  reviewed dependency;
- dirty worktree conflict detection did not treat completed upstream dependency
  diffs as safe context for downstream follow-up tasks.

The first follow-up retry with `ClaudeCodeAdapter` reached the provider but
failed with a real runtime error:

```text
CLAUDE_CODE_EXIT_ERROR: API Error: 400 Failed to deserialize the JSON body into
the target type: messages[1].role: unknown variant `system`, expected `user` or
`assistant`
```

AgentHub did not claim success for that run. A subsequent real `CodexAdapter`
run completed the fix:

| Item | Value |
|---|---|
| Follow-up task ID | `a1986ed7-d7a8-42b9-92b3-78eebcfc979a` |
| Failed Claude follow-up TaskRun ID | `12c538c7-800e-44b9-8e3b-e22012135ecb` |
| Successful Codex follow-up TaskRun ID | `5e405462-a4b9-4bee-9f28-d4960e5d5b88` |
| Successful adapter | `codex` |
| Successful run state | `completed` |
| Diff artifact ID | `448d36a2-3ef1-4674-b4d1-02668a9c5719` |
| Review artifact ID | `33e4f8ea-86ea-4440-a564-61ad3817e2c7` |
| Build evidence artifact ID | `d2403d0d-57df-439b-9699-f4be7207e8ef` |
| Preview | `a92f6bf5-8daf-4c6a-87a0-ffb3cda4d973`, healthy at `http://127.0.0.1:65475` |
| Local staging deploy | `f26b64e1-0174-46be-8040-e978b7eacd22`, ready at `http://127.0.0.1:65495` |

Build evidence:

```text
pnpm build
tsc -b && vite build
30 modules transformed.
built in 635ms
exit code 0
```

Changed files remained inside the demo frontend target:

- `apps/demo/src/App.tsx`
- `apps/demo/src/styles.css`
- `apps/demo/src/components/BreakoutGame.tsx`

## Non-goals Confirmed

P15b did not replace ClaudeCodeAdapter or CodexAdapter, replace the scheduler,
add provider marketplace, add arbitrary command agents, add production deploy,
add a cloud token manager, add multi-user IM, add desktop/IDE/CLI clients, or
add a hardcoded Breakout planner template.

## Remaining Caveats

- The successful follow-up fix used real `CodexAdapter` after the
  `ClaudeCodeAdapter` retry hit a provider/runtime JSON-role error.
- Review evidence remains deterministic scripted review, not real Claude
  review.
- Browser-click playability was not automated; preview and staging URLs were
  verified reachable, and build/staging evidence passed.
- The smoke used a temporary SQLite database at
  `/tmp/agenthub-p15b-smoke.sqlite3` and the built-in `demo-frontend` target.

## Recommended Tag

`p15b-real-llm-planner-engine-freeze`
