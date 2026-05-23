# P6-6 Mini CRM Full-stack Vertical Slice Smoke

**Date:** 2026-05-22

## Request

```text
帮我做一个 mini CRM，包含联系人和备注
```

## Result

The P6-6 API-driven smoke completed a bounded full-stack mini CRM vertical
slice with real `ClaudeCodeAdapter` execution for both Backend Agent and
Frontend Agent tasks.

Flow:

```text
normal user request -> appContract -> backend task -> frontend task
-> scripted review -> diff -> preview artifact -> mock deployment
```

The shared contract was `contract-mini_crm_contacts`. Backend and frontend
tasks both referenced that same contract in `planJson`.

## Evidence

| Field | Value |
|---|---|
| Session ID | `ad122cf7-afe7-4921-bbd9-b7e815539427` |
| Worktree | `.worktrees/4b1423b1-dcec-43ae-b8a3-413445f4e686/ad122cf7-afe7-4921-bbd9-b7e815539427` |
| Contract ID | `contract-mini_crm_contacts` |
| Backend task ID | `590cb06b-4a47-422e-b68f-79a873d4c84a` |
| Backend task run ID | `d6779d0f-afa3-4124-9117-c40b651dd79a` |
| Backend adapter type | `claude_code` |
| Backend diff artifact ID | `95bb9324-0f8d-43a6-89d9-cb2ac6241062` |
| Backend review artifact ID | `0335a0d1-7f88-4177-ae16-d6c2ba5c4def` |
| Frontend task ID | `12ffc19d-f483-4f8d-a541-4c5b935a49b4` |
| Frontend task run ID | `ade5c49c-097d-448e-831c-d10c6bdc3a71` |
| Frontend adapter type | `claude_code` |
| Final diff artifact ID | `db403329-7f0c-4b2c-9134-d2d7ee652564` |
| Final review artifact ID | `1782b85d-c7f9-4d93-b699-27bd27a05ef7` |
| Preview ID / URL / health | `79bfff4f-4991-470b-8862-eb43e7dac852`, `http://127.0.0.1:55592`, healthy at creation |
| Mock deployment ID | `e7b676d6-1505-43f8-be78-7120bfaef831` |
| Mock deployment provider/status | `mock`, `ready` |

The planned QA/Review task remained pending:

- `3bd701c3-525a-495c-8154-1bfc71702c77`

The automatic review artifact generated after the final frontend run passed
and verified that the accumulated diff covered both contract targets.

## Changed Files In Smoke Worktree

```text
apps/demo-api/app/main.py
apps/demo-api/tests/test_contacts.py
apps/demo/src/App.tsx
apps/demo/src/styles.css
```

Backend changes:

- extended the demo contacts API with optional notes and duplicate-email
  conflict handling;
- kept data local/in-memory under `apps/demo-api`;
- added tests for create/list/duplicate/optional-notes behavior.

Frontend changes:

- replaced the demo landing page with a contacts UI;
- added contact list cards, status badges, notes display, and a create-contact
  form;
- connected the UI to `GET /contacts` and `POST /contacts`.

## Review Findings

Backend-only review:

- status: `warning`;
- risk: `medium`;
- reason: the backend-only diff did not yet include frontend target changes for
  `contract-mini_crm_contacts`.

Final frontend run review:

- status: `passed`;
- risk: `low`;
- summary: contract consistency was verified for
  `contract-mini_crm_contacts`;
- reviewed files:
  - `apps/demo-api/app/main.py`;
  - `apps/demo-api/tests/test_contacts.py`;
  - `apps/demo/src/App.tsx`;
  - `apps/demo/src/styles.css`.

## Validation Notes

- `apps/demo-api` tests in the smoke worktree passed from the correct
  `apps/demo-api` working directory: `6 passed`.
- A first test attempt from `apps/api` imported the AgentHub platform API
  instead of the smoke worktree demo API. That was a command working-directory
  issue, not a product failure.
- The preview artifact recorded healthy at creation, but a later `curl` to
  `http://127.0.0.1:55592` could not connect after the one-shot TestClient
  smoke process exited. Long-lived preview availability should be checked under
  a persistent `pnpm dev:api` process during P6-7.

## Caveats

- This was API-driven rehearsal, not browser click rehearsal.
- Coding execution used real `ClaudeCodeAdapter`; review execution used the
  deterministic `ScriptedMockAdapter` review path.
- Mock deploy remained mock-labeled and did not perform production deployment.
- The final QA/Review task from the contract graph was not separately run; the
  automatic post-diff review artifact provided contract consistency evidence.
