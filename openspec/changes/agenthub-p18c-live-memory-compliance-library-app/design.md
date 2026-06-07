## Context

P18 established AgentHub Canonical Memory as the instruction source of truth.
P18b added deterministic memory effectiveness rehearsals and showed that memory
retrieval and safety metrics can improve in controlled scenarios. The remaining
gap is live evidence: a real ClaudeCodeAdapter or CodexAdapter run must show
that active long-term memory affects an actual coding task without the user
repeating the memory rules in the prompt.

P18c uses one bounded task: create a simple Library Management App from a
minimal Chinese user request. The active memory under test supplies project
location, Vite/React/TypeScript default, localStorage persistence, change-log
expectations, platform boundary, and provider-evidence requirements.

## Goals / Non-Goals

**Goals:**

- Seed or confirm active long-term memory rules before creating the rehearsal
  session.
- Create a fresh session after memory is active so a new `memorySnapshotId` is
  generated.
- Verify Planner, coding agent, review/eval, TaskRun evidence, and mission trace
  use the same snapshot.
- Execute the library-management task with ClaudeCodeAdapter or CodexAdapter
  when auth/quota/runtime permits.
- Evaluate whether the implementation follows memory rules not repeated in the
  user prompt.
- Record diff, build/check/test, review, preview/staging, and memory compliance
  evidence honestly.
- Produce `docs/p18c-freeze-review.md`.

**Non-Goals:**

- Do not build a production library system.
- Do not add a real backend, database, authentication hardening, cloud deploy,
  multi-user permissions, provider marketplace, vector search, or knowledge
  graph.
- Do not change memory retrieval algorithms.
- Do not replace Target Registry, PlanValidator, Guardrails, runtime config, or
  scheduler policy.
- Do not use ScriptedMock to claim live compliance.

## Decisions

### Use one bounded live app scenario

The live user prompt is exactly:

```text
帮我在桌面开发一个简单的图书管理系统。有登录页面，初始账户和密码是 18088888888 / 888888。登录后进入管理页面，只需要有图书管理功能：加入图书、删除图书、修改图书、查询图书。
```

The prompt intentionally omits memory rules. Compliance is measured by whether
the live task follows active memory.

### Treat memory setup as a prerequisite

P18c implementation should first ensure these memory rules are active:

1. New demo frontend projects should be created under
   `~/Desktop/agenthub-rehearsals/` unless the user says otherwise.
2. New frontend demo projects should use Vite + React + TypeScript by default.
3. Simple demo apps should use localStorage persistence by default, not
   backend/database, unless explicitly requested.
4. Code changes must update `docs/change-log.md` when applicable.
5. Do not modify AgentHub platform code unless platform maintenance mode is
   explicit.
6. Real provider success must not be claimed without TaskRun / diff / build
   evidence.

The session must be created after these rules are active, so snapshot evidence
can prove the rules were available to Planner and coding agents.

### Evaluate compliance from evidence, not claims

The smoke should evaluate changed files, artifacts, provider metadata,
snapshot metadata, build/check/test output, and preview/staging records. It
should not trust a provider's text summary alone.

### Keep control/treatment honest

The treatment run must use active memory. A deterministic or dry-run control may
compare expected missing behaviors without memory. Task Success Delta must stay
unknown if no comparable control task evidence exists.

### Preserve target safety

The intended app location is outside AgentHub platform code, under the desktop
rehearsal directory. P18c should use existing external workspace/target
registration and Target Registry rules where possible. Any AgentHub platform
code change without explicit platform maintenance mode is a compliance
violation.

## Risks / Trade-offs

- [Risk] Real Claude/Codex auth, quota, or runtime may be unavailable ->
  Mitigation: record exact blocker and do not claim live compliance.
- [Risk] The provider creates the app but misses memory rules -> Mitigation:
  flag specific compliance violations instead of rerouting to ScriptedMock.
- [Risk] The app location may require external target registration -> Mitigation:
  include setup task for the desktop rehearsal directory and target analysis.
- [Risk] Change-log memory could conflict with "do not modify platform code" ->
  Mitigation: treat `docs/change-log.md` update as expected documentation
  evidence for the AgentHub change/rehearsal, while app source must stay outside
  AgentHub platform code.
- [Risk] Preview/staging may be unavailable for a newly created external Vite
  target -> Mitigation: record exact limitation and still require build/check
  evidence when available.

## Migration Plan

No migration is required. P18c is a focused smoke/evaluation change layered on
top of P18/P18b.

## Open Questions

- Which live provider will be available at implementation time:
  ClaudeCodeAdapter or CodexAdapter?
- Will the implementation use an already registered external target, or create
  and register a new target under `~/Desktop/agenthub-rehearsals/`?
