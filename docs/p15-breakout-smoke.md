# P15 Breakout Real Coding Smoke

**Date:** 2026-05-28

## Request

```text
帮我在当前前端项目里实现一个 Breakout / 打砖块游戏，要求可以用键盘控制挡板，球能反弹，能击碎砖块，有得分、胜利/失败状态和重新开始按钮。
```

## Summary

P15-6 verified that a normal no-mention frontend coding request can route
through Orchestrator into a `passthrough_v1` frontend task, preserve the
original user request, execute through `ClaudeCodeAdapter`, produce a real
worktree diff, generate review evidence, pass a target-scoped build command,
start a healthy preview, and create a local staging deploy.

This was not a hardcoded Breakout template. The planner change is generic
passthrough routing for bounded frontend implementation requests inside a
registered frontend target.

## Evidence

| Item | Value |
|---|---|
| Session ID | `901ae011-a095-489e-b0f4-72c6c1a27187` |
| Message ID | `93972c24-3cb4-40cb-a7bc-eba9789596cb` |
| Task ID | `e6b6d537-5787-413a-944c-b456025bf905` |
| TaskRun ID | `8d719899-8042-49b0-8e26-79d065841a3c` |
| Planner | `passthrough_v1` |
| Instruction mode | `passthrough_v1` |
| Adapter | `claude_code` |
| Final state | `completed` |
| Target | `demo-frontend` |
| Diff artifact ID | `96b576ec-d673-49b7-a461-78e937f219b8` |
| Review artifact ID | `706265e5-91dc-4d90-a309-b0ca7c4700ad` |
| Command evidence artifact ID | `7dddb098-3e84-48c5-9855-4f2479a865f0` |
| Preview ID / URL / health | `68d04a67-99d1-4fdb-8bfb-5ba584ae6f6c` / `http://127.0.0.1:50086` / `healthy` |
| Staging deploy ID / provider / status / URL | `1747ed90-9999-4919-bfac-8b4cdfea13a4` / `local_staging` / `ready` / `http://127.0.0.1:50424` |

Changed files:

- `apps/demo/src/App.tsx`
- `apps/demo/src/styles.css`
- `apps/demo/src/BreakoutGame.tsx`

## Validation Evidence

- `pnpm build` passed inside the generated worktree target
  `apps/demo`, recorded as target-scoped build evidence for `demo-frontend`.
- Scripted review passed with low risk and reviewed all three changed files.
- Preview returned healthy.
- Local staging deploy returned HTTP 200 for the generated staging URL.
- Built JavaScript contains `Breakout`, `ArrowLeft`, `ArrowRight`, `Score`,
  `Restart`, and `canvas` markers.

## Fixes Made During Smoke

- `passthrough_v1` planning is now used for bounded frontend implementation
  requests instead of the older `orchestrator_auto_run_v1` demo rewrite.
- `ClaudeCodeAdapter` now allows `Write` in addition to `Read`, `Edit`, and
  `MultiEdit`, so real coding agents can create new files inside the assigned
  session worktree.
- Diff collection now includes untracked files, so new agent-created files are
  included in diff artifacts, changed file lists, stats, review input, and
  ledger state.

## Caveats

- Browser-click playability was not automated because no browser automation
  tool was available in this run and Playwright is not installed in the
  workspace.
- The first two smoke attempts were interrupted:
  - `a7cc0854-b121-40d7-816d-a1866977275a` used the old
    `orchestrator_auto_run_v1` plan.
  - `b9d66bce-4432-497f-8b4c-9e53bfae1243` reached Claude Code but hit the
    missing `Write` permission before the adapter fix.
- Review evidence is still deterministic scripted review, not real Claude
  review.
