# Local workspace improvement sequence

User request (2026-10-15): implement built-in FastAPI version-bound validation,
then address the remaining gaps identified in the source-grounded project review.
Keep this full scope while implementing one focused OpenSpec task at a time.
No production deployment, arbitrary MCP marketplace, dependency installation,
commit or push is included.

| Item | Completion evidence required | State |
| --- | --- | --- |
| Built-in backend validation | Real positive/negative syntax and ASGI tests; same-run/source/policy receipts; stale, cancel, restart and ownership gates; truthful profile-aware QA/UI | Complete locally; see `backend-versioned-validation-review.md` |
| Representative task evaluation | Reproducible API, multi-file, frontend/backend, follow-up and recovery scenarios; natural-language planning/dispatch coverage; independent checks; first-attempt/retry/time/failure reporting; real and injected/test execution clearly separated | Complete locally: first real suite 4/5 with failure retained; command-scope fix and separate real integration recheck passed (215.969 s). All five categories have explicit source-bound evidence; see `workflow-evaluation.md` |
| Review → repair → revalidation | Select concrete findings, preserve original report and source binding, create explicit repair request, rerun checks, and show resolved/unverified/remaining findings without model-only proof | Complete locally: explicit draft/send/owned launch/output/retry and source-bound outcomes; final 27 focused tests, Web 301, four browser theme/width cases; see `review-repair-loop-review.md` |
| Unified context accounting | Account for final rendered request across rules, skills, attachments, pinned/recent/context references; show inclusion and omission reasons; enforce total budget while preserving essential rules and immutable historical bindings | Complete locally: final managed text/byte/image gates, four real Planner formats, frozen-source diagnostics and UI; 19 final focused, 446 final runtime regressions, Web 303 and four browser theme/width cases. Not model-token or CLI hidden/tool-loop accounting; see `final-context-budget-review.md` |
| UI usability | Surface current phase/blocker/next action; fold raw technical evidence; replace Skill-reference JSON editing with file/content controls; measure long-session behavior and add bounded history loading if needed | Complete locally: guidance/reference editor and measured 80-row initial/200-row DOM/16-pin/12,000-character segment bounds; final API 78, Web 326, root checks and browser fixtures passed. See `workbench-usability-review.md` |
| Long-term local data management | Verified backup and restore workflow with database/Git/worktree consistency; storage inventory and reference-safe cleanup preview/explicit apply; keep active sessions and user-owned paths safe | Complete locally: offline WAL/Git/worktree snapshot and isolated/same-location restore, bounded inventory and reference-bound cache quarantine; final 33 (including 12 cleanup), root/strict checks passed. Restore owns the target DB lease and exclusively creates files. Quarantine retains bytes and does not permanently delete. See `local-data-maintenance-review.md` |
| Current documentation | Reconcile current snapshot and delivery summaries with Git/source, retain historical test claims as historical, and document new workflows and remaining limits | Complete locally: guides/architecture/models/routes/delivery refs reconciled; 94 historical log sections preserved against HEAD, 69 documents/344 links checked. API batch 2293/1 skip plus later maintenance 33 (overlap), Web 326, local tools 19, demo-api 5 and root/strict checks passed. See `current-doc-reconciliation-review.md` |

Do not declare the overall request complete solely because the first item passes,
because existing tests are green, or because a plan for later items exists.

All seven scoped items above are complete locally on 2026-10-15. No commit,
push, production rollout, actual-data restore or automatic permanent cleanup
was performed. Remaining product limits are recorded in the reconciliation review.
The existing live API still runs the older code; activating new routes requires
a safe local restart. Source completion does not claim this runtime switch.
