# P9 External Project Workspace Mode Freeze Review

Date: 2026-05-24

## Result

P9 is ready to freeze as External Project Workspace Mode for the local
single-user AgentHub workspace.

P9 makes external local projects first-class registered targets while
preserving the P6/P7/P8 built-in demo baseline. The freeze rehearsal used a
temporary local Vite-style external project and controlled local service calls.
It did not run a fresh real Claude/Codex mutation.

## Rehearsal Evidence

| Field | Value |
|---|---|
| Sample root | `/tmp/agenthub-p9-external-sample` |
| Workspace ID | `deecb61e-8255-4f97-af36-668f8fefc66d` |
| Session ID | `09977dc0-1eac-49f6-ae78-cb7ae7aa9ccc` |
| Target ID | `external-p9-sample` |
| Resolved target root | `/private/tmp/agenthub-p9-external-sample` |
| Analysis status / type | `ready`, `vite-react` |
| Task ID | `ce8fe3de-6969-4273-84e9-274ab440f39b` |
| TaskRun ID | `1d6d2916-b179-4bb7-ad7a-642733dfd175` |
| Adapter type | `scripted_mock` controlled rehearsal |
| Real Claude/Codex run | No |
| Changed files | `src/App.tsx` |
| Diff artifact | `7bf6efa3-289b-4cb8-9644-6ca6e283b230` |
| Command evidence | `c6d581bf-e80a-4fb9-bb21-f0db1cb9ff4d`, `b01ccc78-b3d4-44fc-b758-4c9558d2f594`, `9a256f14-fe1f-4e4b-9dc7-78c4402edd01` |
| Review artifact | `383e7822-0145-4950-9bd1-b3dffb170b36` |
| Review status / risk | `passed`, `low` |
| Preview | Not started in this controlled rehearsal |

## What Was Verified

- External project analysis inferred a ready Vite React target.
- External project registration persisted target metadata and denied paths.
- Workspace target registry resolved the external target.
- Session target selection routed a normal no-mention request to the selected
  external frontend target.
- TaskRun used the external target root rather than the built-in demo worktree.
- External diff collection recorded `src/App.tsx`.
- Check, test, and build command evidence artifacts were recorded.
- Scripted review passed with low risk when changed files and evidence matched
  policy.
- Built-in validation for web, API, demo frontend, demo API, OpenSpec, and diff
  whitespace remains green.

## Caveats

- This freeze rehearsal did not run a fresh real ClaudeCodeAdapter or
  CodexAdapter external mutation.
- Preview was not started for the temporary external sample.
- External command evidence is recorded by the controlled pipeline/API; P9 does
  not yet execute arbitrary external commands automatically.
- P9 remains local single-user workspace mode, not cloud repo import,
  production deploy, or multi-user project sharing.

## Recommended Tag

`p9-external-project-workspace-mode-freeze`
