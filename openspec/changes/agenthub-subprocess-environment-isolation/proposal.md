## Why

Real coding adapters, the Claude CLI planner, Vite preview commands, and staging
build commands currently inherit the FastAPI control-plane process environment.
A registered or agent-modified project can therefore observe unrelated
planner/provider API keys, database configuration, or other host credentials
when its CLI or package script runs.

The existing `network=off`, protected-path prompt, and post-run TaskRun scope
checks do not remove those values before process creation. This is a distinct
pre-execution confidentiality boundary and must fail closed independently of the
existing changed-file checks.

## What changes

- Add one shared child-process environment policy with separate project-runtime
  and real-adapter profiles.
- Give preview/build/static-server processes only portable runtime variables and
  explicitly public frontend variables.
- Give Codex, Claude Code, the Claude CLI planner, and their CLI probes only their
  own provider credential/configuration variables, never another provider's key
  or unrelated AgentHub settings.
- Redact sensitive environment values and secret assignments before adapter,
  preview, or deployment output becomes persisted evidence.
- Preserve argv-based execution, Windows `pnpm.cmd` resolution, CLI login/config
  discovery, Vite public configuration, and current fallback behavior.

## Out of scope

- OS/container-level host filesystem or network isolation; that remains a
  separate validated security finding.
- iframe sandboxing, SSE backpressure, generated-project dependency pinning, or
  package-manager bootstrap changes.
- New adapters, provider marketplace features, Docker, WebSocket, or production
  deployment.
