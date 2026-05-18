# AgentHub P2 Stabilization Roadmap

P2 starts from the frozen P1 demo baseline and focuses on stabilization, known
caveats, and demo reliability. Frontend redesign is paused and remains deferred
unless explicitly resumed.

## Current P1 Final Verified State

P1 is frozen as a stable local demo baseline for:

```text
real Codex Direct Start -> diff card -> Start preview -> preview iframe -> Create deploy card
```

The fallback-based P0 path remains preserved and manually reverified:

```text
forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card
```

Verified P1 state includes:

- Direct UI Start dispatches backend adapter execution instead of stopping at a
  queued TaskRun.
- Codex CLI execution streams JSONL events incrementally and remains responsive
  enough for the local API/UI demo.
- Real Codex Direct Start can mutate `apps/demo/src/App.tsx` in a session
  worktree and produce a persisted diff artifact.
- The browser UI can render the diff card, start a healthy Vite React preview,
  open the preview iframe, and create a persisted mock deploy card.
- P1-11 verified clean SQLite rehearsal with a fresh session worktree.
- P1-11 manually reverified the forced-failure fallback path through
  ScriptedMockAdapter, diff, preview, and mock deploy.

## Original P1 Caveats and P2 Resolution

P2 has addressed the original stabilization caveats that were safe to close
without expanding into broader product scope:

- Locale-specific hydration warning: fixed in P2-1 with deterministic timestamp
  formatting.
- Approval card UI outside the P1 judge path: minimally completed and rehearsed
  in P2-2.
- Natural-language second-change orchestration: implemented narrowly for
  deterministic button/title text changes in P2-3, with browser preview iframe
  refresh verified in P2-4.
- GitHub Actions CI: added in P2-5.
- Claude Code runtime option: added and smoke-verified in P2-7, made
  selectable for Direct Start through `AGENTHUB_DEFAULT_CODE_ADAPTER` in P2-8,
  and documented in P2-9.

The following remain caveats after P2:

- Full browser UI Claude-default execution through diff/preview/deploy is
  unrehearsed.
- Real Claude auth-failure and usage-limit outputs remain partially
  unverified.
- Broad arbitrary natural-language editing remains out of scope.
- Production deploy remains out of scope.

## Immediate P2 Priorities

P2 was scoped to make the existing demo more deterministic before adding
broader capabilities. The original immediate task order was:

1. P2-1 fix locale hydration warning.
2. P2-2 approval card UI/rehearsal.
3. P2-3 natural-language second-change orchestration.
4. P2-4 GitHub Actions CI.
5. P2-5 demo reset / clean-state helper.

Actual P2 execution added the CI workflow, then continued with a documented
Claude Code runtime option to reduce Codex CLI quota usage during demos. The
demo reset helper remains a useful future stabilization task; it was not
implemented during the completed P2 work.

## P2 Final Verified State

At P2 freeze, AgentHub supports:

- P1 real Codex Direct Start path:
  `Start run -> real Codex file mutation -> diff card -> preview iframe -> mock deploy card`.
- Fallback-based P0 path:
  `forced Codex failure -> ScriptedMockAdapter fallback -> real diff -> healthy Vite preview -> mock deploy card`.
- Approval cards and approve/deny API/UI wiring for existing P0 approval
  payloads.
- Deterministic second-change orchestration for button/title text changes in
  the same session worktree.
- Browser preview iframe refresh after a second deterministic change.
- CI for `pnpm check`, `pnpm test`, and `git diff --check`.
- Minimal `ClaudeCodeAdapter` with fake-runner tests and one real backend smoke
  proving a tiny file mutation and diff artifact.
- `AGENTHUB_DEFAULT_CODE_ADAPTER=claude_code` to create normal Direct Start
  coding TaskRuns with `adapterType: claude_code`.

## P2-1 Fix Locale Hydration Warning

### Objective

Remove the development hydration warning caused by locale-specific date
formatting differences between server-rendered and client-rendered UI.

### Scope

- Audit session/task/preview/deploy timestamp rendering in the Next.js app.
- Make rendered date text deterministic across server and client, or move
  locale-sensitive formatting to client-only rendering with a stable fallback.
- Keep the visible UI compact and aligned with the current demo layout.

### Affected Modules

- `apps/web/src/components/workspace-shell.tsx`
- Any existing frontend date/time utility if one exists.
- Frontend tests that cover session list or artifact cards.

### Acceptance Criteria

- Opening the AgentHub UI in development no longer logs the known
  locale-specific hydration mismatch for session dates.
- Session list, task run history, preview cards, and deploy cards still show
  useful timestamps.
- Existing P1 demo paths still render correctly after reload.

### Validation Method

- `pnpm check`
- `pnpm test`
- `git diff --check`
- Manual browser smoke: load a session with existing messages/runs and confirm
  the hydration warning no longer appears.

### Explicit Non-Goals

- Do not redesign the workspace shell.
- Do not change backend timestamp schemas.
- Do not add a full internationalization framework.
- Do not alter task/run lifecycle behavior.

## P2-2 Approval Card UI/Rehearsal

### Objective

Make the existing approval payload and risky-action guardrail flow visible and
rehearsable in the UI without expanding into enterprise policy management.

### Scope

- Review the existing approval payload/event shape and backend approve/deny
  services or endpoints.
- Render an approval card when an approval-requested event is present.
- Support simple approve/deny actions for the existing P0 approval shape.
- Add a deterministic local rehearsal path that demonstrates approval without
  requiring production deploy or broad shell access.

### Affected Modules

- `apps/api/app/guardrails.py`
- `apps/api/app/main.py` and related approval schemas, if existing API gaps are
  found.
- `apps/web/src/components/task-card-list.tsx`
- Potential new or existing approval card component in `apps/web/src/components`.
- Backend and frontend tests for approval rendering/actions.

### Acceptance Criteria

- A risky action produces a visible approval card or event-derived card.
- Approve and deny outcomes are visible and persisted through existing
  TaskRunEvent/event plumbing.
- TaskRun waiting-approval state is understandable in the UI.
- The rehearsal path is deterministic and documented.

### Validation Method

- `pnpm check`
- `pnpm test`
- `git diff --check`
- Manual rehearsal of one approval request, one approval, and one denial.

### Explicit Non-Goals

- Do not implement enterprise RBAC.
- Do not add a policy admin console.
- Do not add arbitrary shell execution.
- Do not implement production deployment.
- Do not weaken protected path or command allowlist behavior.

## P2-3 Natural-Language Second-Change Orchestration

### Objective

Turn the documented second-change caveat into a deterministic demo flow where a
follow-up message like `make the button text more friendly` creates and runs a
small scoped task in the same session worktree.

### Scope

- Parse a simple second-change instruction for the existing deterministic
  button target: `data-agenthub-target="primary-action-button"`.
- Create a visible task assigned to the frontend agent.
- Reuse the same session worktree and produce a new TaskRun, diff, and preview
  refresh path.
- Keep the implementation narrow and demo-specific.

### Affected Modules

- `apps/api/app/planning.py`
- `apps/api/app/scripted_mock.py` and/or task instruction generation in
  `apps/api/app/main.py`
- `apps/web/src/components/workspace-shell.tsx`
- `apps/web/src/components/task-card-list.tsx`
- Planning and task-run tests.

### Acceptance Criteria

- In a session that already has the login-page change, sending
  `make the button text more friendly` creates a visible follow-up task.
- Running the task changes only the deterministic button target.
- The new diff is generated from the correct TaskRun base ref.
- Preview can be refreshed or restarted to show the second change.
- Prior run history remains visible.

### Validation Method

- `pnpm check`
- `pnpm test`
- `git diff --check`
- Manual rehearsal in one session:
  login page request -> first diff/preview -> second-change request -> second
  diff -> refreshed preview.

### Explicit Non-Goals

- Do not build arbitrary natural-language orchestration.
- Do not add a general DAG replanner.
- Do not redesign the task card UI.
- Do not implement provider marketplace or external integrations.

## P2-4 GitHub Actions CI

### Objective

Add repository CI so the current check/test contract runs consistently outside
the local machine.

### Scope

- Add a GitHub Actions workflow for the existing project commands.
- Install Node/pnpm and Python dependencies in the workflow.
- Run the same validation commands used locally.
- Keep CI scoped to checks/tests; do not add deploy automation.

### Affected Modules

- `.github/workflows/ci.yml`
- Possibly README/docs if CI setup notes are needed.

### Acceptance Criteria

- CI runs on pull requests and pushes to the main branch.
- CI runs `pnpm check`, `pnpm test`, and `git diff --check`.
- CI does not require local Codex CLI quota or authentication.
- CI does not attempt preview startup, production deploy, or external provider
  calls.

### Validation Method

- Local workflow review.
- `pnpm check`
- `pnpm test`
- `git diff --check`
- If available, verify the workflow in GitHub after push.

### Explicit Non-Goals

- Do not add deployment jobs.
- Do not require real Codex CLI in CI.
- Do not add provider secrets.
- Do not expand the test matrix beyond the fixed stack without a follow-up task.

## P2-5 Demo Reset / Clean-State Helper

### Objective

Make clean demo setup safer and more repeatable without manually moving SQLite
files or disturbing registered Git worktrees.

### Scope

- Add a small documented reset helper that backs up the current SQLite database
  before reinitializing.
- Record backup locations and restore instructions.
- Prefer preserving existing `.worktrees` or pruning only through explicit,
  safe Git worktree commands.
- Keep the helper local and opt-in.

### Affected Modules

- `scripts/` for a reset helper, if implementation is requested later.
- `README.md`
- `docs/demo-script.md`
- `docs/project-state.md`
- Potential tests only if the helper is implemented as code.

### Acceptance Criteria

- A judge/demo operator can create a clean SQLite state with one documented
  command or short procedure.
- Existing SQLite data is backed up before reset.
- Restore instructions are printed or documented.
- The helper does not delete `.worktrees`, `.git`, `.env*`, `node_modules`, or
  unrelated user files.

### Validation Method

- Dry-run or temp-path rehearsal, if supported by the helper.
- `pnpm db:init`
- `pnpm check`
- `pnpm test`
- `git diff --check`
- Manual verification that backup files exist and restore steps are clear.

### Explicit Non-Goals

- Do not delete worktrees blindly.
- Do not reset Git branches.
- Do not install dependencies.
- Do not create a production data migration workflow.

## Deferred Frontend Redesign

Frontend redesign remains paused. P2 may make small UI fixes required for
stability, clarity, or rehearsability, but a broader visual redesign is not part
of immediate P2 unless explicitly resumed.

Deferred redesign items include:

- New information architecture.
- Broad task card layout redesign.
- New visual language or theming pass.
- Full responsive redesign beyond targeted bug fixes.
- Replacement of the current preview/diff/deploy surfaces.
