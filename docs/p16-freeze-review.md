# P16 Freeze Review: Agent Runtime Configuration

**Date:** 2026-05-29

## Decision

P16 is ready to freeze.

AgentHub now lets users configure core runtime role defaults for Planner,
Frontend, Backend, and Review through a validated workspace runtime config.
The implementation preserves the existing defaults when no config exists,
exposes a settings UI for the main user-facing roles, applies saved config to
planner and coding TaskRun resolution, records runtime config evidence, and
keeps existing target/approval policy in force.

## Rehearsal Scope

P16 reused the P15b Breakout-style frontend workflow evidence instead of
running another costly real provider mutation. P15b already proved:

- real planner provider `claude_cli`;
- real coding execution through `ClaudeCodeAdapter` and `CodexAdapter`;
- diff, review, build, preview, and local staging deploy evidence;
- ready local staging deploy
  `f26b64e1-0174-46be-8040-e978b7eacd22`.

P16 focused on proving that runtime configuration now affects the provider
selection path used by those existing capabilities.

## Runtime Config Evidence

| Area | Evidence |
|---|---|
| Config model | `AgentRuntimeConfig` persists role defaults for planner, frontend, backend, and review. |
| API | Runtime config GET, validate, and PUT endpoints return effective config, selectable profiles/providers, validation errors, and warnings. |
| UI | Sidebar Agent Runtime Settings renders Planner, Frontend, and Backend selections from safe profile/provider metadata only. |
| Planner resolution | Enabled Planner config resolves `claude-cli-planner` / `claude_cli` before environment defaults. |
| Frontend resolution | Enabled Frontend config resolves `local-claude-code-cli` / `claude_code` before `AGENTHUB_DEFAULT_CODE_ADAPTER`. |
| Backend resolution | Enabled Backend config resolves `local-codex-cli` / `codex` before `AGENTHUB_DEFAULT_CODE_ADAPTER`. |
| Evidence | TaskRun responses and mission trace expose `providerAssignment` and `runtimeConfigResolution`. |
| Invalid config | Backend runtime config with `platform_maintenance` mode is rejected. |
| Platform safety | Backend runtime config does not bypass platform approval for `agenthub-platform` tasks. |

## Configured Freeze Scenario

The target runtime configuration for P16 is:

- Planner = `claude-cli-planner` / `claude_cli`;
- Frontend = `local-claude-code-cli` / `claude_code`;
- Backend = `local-codex-cli` / `codex`;
- Review remains review-safe and non-production.

Automated tests verify that these saved runtime choices affect actual planner
and TaskRun resolution. No new real Claude/Codex mutation was required for
P16-7 because P16 changed runtime selection and evidence, not provider coding
capability itself.

## Non-goals Confirmed

P16 did not add a provider marketplace, arbitrary custom shell-command agents,
OpenCode integration, cloud token manager, production deploy, multi-user RBAC,
desktop/IDE/CLI clients, full artifact editor, or new adapters.

## Remaining Caveats

- Runtime config is workspace-scoped and local; there is no multi-user settings
  ownership or RBAC.
- Planner provider auth remains external to AgentHub; P16 does not add token
  management.
- The settings UI exposes core role defaults only, not a full provider
  marketplace.
- Review remains safe/fallback-oriented unless later work expands real review
  provider execution.

## Recommended Tag

`p16-agent-runtime-configuration-freeze`
