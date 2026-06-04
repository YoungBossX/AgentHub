## Why

P17, P17b, and P17c made AgentHub capable of routing normal conversation through a Planner LLM, configuring multiple Planner providers, configuring coding-agent providers at runtime, and selecting workspace targets. The next coordination risk is no longer "can AgentHub call an agent"; it is "which memory and instruction source is the agent actually obeying?"

Today the Planner LLM, Claude Code, Codex, Review Agent, Target Registry, PlanValidator, repo `AGENTS.md`, potential `CLAUDE.md`, and provider-local private memories may each see different instructions. That creates inconsistent behavior and makes it difficult to audit why a Planner or TaskRun made a decision. AgentHub needs a canonical, versioned, scope-aware memory and instruction control plane before adding more autonomous agent behavior.

## What Changes

- Introduce AgentHub Canonical Memory as the source of truth for cross-agent project instructions, user preferences, decisions, patterns, feedback, and session summaries.
- Treat `AGENTS.md` and `CLAUDE.md` as compiled/exported artifacts, not as independent sources that silently override AgentHub memory.
- Add session memory snapshots so Planner LLM, Claude Code, Codex, and Review Agent use the same `memorySnapshotId` across a session/task chain.
- Plan memory item lifecycle, scoring, retrieval, eviction, write policy, prompt-injection guard, and external memory scanning.
- Define how memory compiles into `AGENTS.md`, `CLAUDE.md`, Planner context blocks, Claude Code instructions, Codex instructions, and Review instructions.
- Add a memory management UI plan for reviewing active, pending, warm, archived, rejected, deleted, and externally suggested memory.
- Add measurable memory effectiveness criteria and a P18 freeze rehearsal.
- Keep Target Registry, PlanValidator, and Guardrails as the hard security boundary. Memory guides behavior; guardrails enforce permissions.

## Capabilities

### New Capabilities

- `memory-instruction-control-plane`: Canonical memory, snapshot, retrieval, managed instruction export, external memory suggestion, memory management, and memory evaluation foundation.

### Modified Capabilities

- `runtime-agent-coordination`: Planner and coding-agent instructions will reference the same memory snapshot and evidence metadata.
- `settings`: Adds or plans a memory settings surface without changing existing runtime provider settings.
- `mission-trace`: Records memory and instruction hashes/versions where appropriate.

## Impact

- Backend model/API design in `apps/api` for memory items, snapshots, retrieval, write policy, hashes, and evidence metadata.
- Instruction generation for Planner, Claude Code, Codex, and Review Agent.
- Managed `AGENTS.md` / `CLAUDE.md` compilation and preservation of user custom blocks.
- Frontend settings UI for memory review and snapshot visibility.
- Tests for deterministic export, snapshot consistency, prompt-injection blocking, retrieval precision, and memory evidence.
- Documentation updates in `docs/change-log.md` and `docs/project-state.md` when implementation begins.

## Explicit Non-goals

- Full knowledge graph memory.
- Mandatory vector database.
- RRF fusion ranking.
- Automatic long-term learning without user review.
- Multi-user shared memory.
- Provider marketplace.
- Cloud secret manager.
- Production deploy.
- Replacing Target Registry, PlanValidator, or Guardrails with memory.
- Letting Claude Code or Codex private memory override AgentHub canonical memory.
