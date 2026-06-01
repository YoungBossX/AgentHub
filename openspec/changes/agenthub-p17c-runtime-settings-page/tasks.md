## 1. Chat Workspace Simplification

- [x] 1.1 Remove the full Agent Runtime Settings panel from the chat/session sidebar while preserving session navigation, agent contacts, chat, tasks, artifacts, and mission trace behavior.
- [x] 1.2 Add a compact runtime settings entry point from the chat workspace, using an icon/button/link that does not compete with the session list.
- [x] 1.3 Update chat workspace tests to verify the detailed runtime settings form is not rendered inline and that the settings entry point is available.

## 2. Dedicated Runtime Settings Page

- [x] 2.1 Add a dedicated runtime settings page or route for Planner, Frontend, Backend, and Review configuration.
- [x] 2.2 Reuse the existing runtime config, provider config, agent profile, and planner preset API calls without changing runtime execution semantics.
- [x] 2.3 Organize the settings page into clear sections for Planner LLM, Frontend Agent, Backend Agent, and Review Agent, with provider/profile metadata visible where useful.

## 3. Save And Cancel Behavior

- [x] 3.1 Keep settings edits in draft state until Save is clicked.
- [x] 3.2 Implement Save through the existing runtime config update path and show success/failure feedback.
- [x] 3.3 Implement Cancel so unsaved draft changes are discarded and persisted config is restored or the user returns to chat.
- [x] 3.4 Add tests for Save, Cancel, and "draft changes do not affect active config before Save."

## 4. User-facing Status Labels

- [x] 4.1 Add a UI status-label mapping for internal values such as `unchecked`, `configured`, `missing_key`, `not_required`, `unavailable`, and required-field validation errors.
- [x] 4.2 Ensure missing API key states explain that keys must be configured through environment variables and never through raw key entry.
- [x] 4.3 Update tests so raw internal status strings are not the primary labels shown to users.

## 5. Documentation And Freeze Review

- [ ] 5.1 Update `docs/project-state.md` and `docs/change-log.md` with the P17c UI information-architecture change.
- [ ] 5.2 Validate `pnpm check`, `pnpm test`, `git diff --check`, and `openspec validate agenthub-p17c-runtime-settings-page --strict`.
- [ ] 5.3 Perform a focused UI rehearsal: chat page remains simple, settings entry opens the runtime settings page, Save/Cancel works, and status labels are user-friendly.
- [ ] 5.4 Mark P17c complete only after validation and rehearsal pass.
