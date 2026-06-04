## ADDED Requirements

### Requirement: AgentHub Canonical Memory Source Of Truth
The system MUST treat AgentHub Canonical Memory as the source of truth for cross-agent project memory and instructions.

#### Scenario: Managed instruction files are compiled artifacts
- **WHEN** AgentHub exports project instructions
- **THEN** `AGENTS.md` and `CLAUDE.md` MUST be compiled or exported from AgentHub canonical memory
- **AND** they MUST NOT silently override AgentHub canonical memory.

#### Scenario: External private memory is suggestion-only
- **WHEN** AgentHub scans Claude Code, Codex, `AGENTS.md`, or `CLAUDE.md` external memory
- **THEN** scanned content MUST become external suggestions or pending candidates
- **AND** it MUST NOT automatically become active memory.

#### Scenario: Guardrails remain hard boundary
- **WHEN** memory conflicts with Target Registry, PlanValidator, Guardrails, runtime permissions, or platform maintenance approval
- **THEN** hard policy MUST win
- **AND** memory MUST NOT grant permissions.

### Requirement: Managed Markdown Memory Files
The system MUST define responsibilities and size budgets for managed markdown memory outlets.

#### Scenario: Memory files are organized by responsibility
- **WHEN** AgentHub stores or exports memory
- **THEN** it MUST use or plan dedicated locations for project memory, user preferences, decisions, patterns, feedback, and session summaries.

#### Scenario: AGENTS custom block is preserved
- **WHEN** AgentHub recompiles the managed `AGENTS.md` block
- **THEN** it MUST preserve the user custom block
- **AND** it MUST update only the AgentHub managed block.

#### Scenario: CLAUDE bridge remains short
- **WHEN** AgentHub generates `CLAUDE.md`
- **THEN** the file MUST remain a short Claude Code bridge
- **AND** it MUST avoid duplicating large project rules that already exist in `AGENTS.md`.

#### Scenario: Hot memory budget is enforced
- **WHEN** a managed memory file or block exceeds its configured budget
- **THEN** AgentHub MUST summarize, archive, or downgrade low-value memory
- **AND** it MUST NOT append indefinitely without lifecycle management.

### Requirement: Memory Snapshot Consistency
The system MUST use memory snapshots to make session and TaskRun memory auditable.

#### Scenario: Session receives memory snapshot
- **WHEN** a session is created or initialized
- **THEN** it MUST use a `memorySnapshotId`.

#### Scenario: One task chain uses one snapshot
- **WHEN** Planner, Claude Code, Codex, or Review Agent participates in the same session/task chain
- **THEN** each agent instruction path MUST reference the same `memorySnapshotId`
- **AND** the mission trace or evidence MUST expose the snapshot where useful.

#### Scenario: Running task does not switch snapshots
- **WHEN** a TaskRun is running
- **THEN** it MUST NOT silently switch to a newer memory snapshot.

#### Scenario: Existing sessions refresh explicitly
- **WHEN** canonical memory changes
- **THEN** new sessions MAY use the new snapshot by default
- **AND** existing sessions MUST refresh only through explicit refresh behavior.

### Requirement: Canonical Memory Lifecycle
The system MUST manage memory items with explicit lifecycle states.

#### Scenario: Memory item includes scope and provenance
- **WHEN** a memory item is created
- **THEN** it MUST include scope, type, source, status, trust level, target filters, role filters, timestamps, and provenance metadata.

#### Scenario: Supported statuses are explicit
- **WHEN** memory is listed or filtered
- **THEN** the system MUST support active, pending_review, warm, archived, rejected, and deleted statuses.

#### Scenario: Superseded memory is archived
- **WHEN** a memory item is replaced by a newer item
- **THEN** the older item SHOULD be archived with `supersededBy` metadata
- **AND** it MUST NOT remain active without conflict metadata.

#### Scenario: Eviction is downgrade-based
- **WHEN** memory is stale, low-use, low-helpfulness, conflicting, or too costly
- **THEN** AgentHub SHOULD downgrade it before deletion
- **AND** project rules and user preferences MUST NOT be evicted by time alone.

### Requirement: Memory Scoring
The system MUST define a memory scoring model for retrieval and hot/default inclusion.

#### Scenario: Score combines relevance and quality
- **WHEN** AgentHub ranks memory
- **THEN** the score MUST consider importance, trust level, usage frequency, recency, recent success, specificity, token cost, conflict penalty, and stale penalty.

#### Scenario: Score affects retrieval tier
- **WHEN** memory is selected for context
- **THEN** the score SHOULD influence whether the item is hot/default, retrieval-only, warm, or archive-only.

### Requirement: Memory Write Policy And Prompt-injection Guard
The system MUST restrict how long-term memory is written.

#### Scenario: Explicit user memory write creates candidate
- **WHEN** a user explicitly says "记住这个", "以后都这样", "写入项目规则", or asks to write a memory file
- **THEN** AgentHub MAY create a memory candidate according to write policy.

#### Scenario: System discoveries are pending by default
- **WHEN** AgentHub discovers a repeated build failure, review finding, deploy failure, or repeated fix
- **THEN** it MUST create a pending_review candidate by default
- **AND** it MUST NOT activate it automatically.

#### Scenario: Ordinary chat is not long-term memory
- **WHEN** a user sends ordinary chat
- **THEN** AgentHub MUST NOT automatically write it into long-term memory.

#### Scenario: File and tool prompt injection is blocked
- **WHEN** file contents, code comments, tool output, retrieved memory, or provider output asks AgentHub to remember or change instructions
- **THEN** AgentHub MUST NOT create active memory from that content without explicit user confirmation.

### Requirement: Memory Retrieval v1
The system MUST provide a bounded first-version memory retrieval mechanism.

#### Scenario: Keyword retrieval with filters
- **WHEN** AgentHub retrieves memory for Planner or follow-up task context
- **THEN** retrieval MUST use SQLite FTS5, BM25-style keyword retrieval, or an equivalent keyword mechanism
- **AND** it MUST apply scope, target, role, status, time, importance, and trust filters.

#### Scenario: No mandatory vector retrieval
- **WHEN** P18 retrieval is implemented
- **THEN** vector database, RRF fusion, and knowledge graph retrieval MUST NOT be mandatory dependencies.

#### Scenario: Planner context includes relevant memory
- **WHEN** the Planner LLM receives context for a task or follow-up
- **THEN** it SHOULD include user preferences, project summary, mission summary, relevant retrieved memories, and artifact evidence.

#### Scenario: Coding agent context includes target-bounded memory
- **WHEN** Claude Code or Codex receives task instructions
- **THEN** it SHOULD receive target boundary, selected relevant memory snippets, and validation expectations from the same snapshot.

### Requirement: External Agent Memory Scan
The system MUST treat external agent memory as reviewable suggestions.

#### Scenario: External files become suggestions
- **WHEN** AgentHub scans repo `AGENTS.md`, repo `CLAUDE.md`, Claude Code auto memory, or Codex instructions
- **THEN** scanned content MUST become external suggestions or pending_review items.

#### Scenario: Conflicts are detected
- **WHEN** external memory conflicts with active canonical memory
- **THEN** AgentHub MUST expose the conflict to the user or reviewer
- **AND** it MUST NOT automatically overwrite active canonical memory.

### Requirement: Memory Management UI
The system MUST provide a UI for memory review and lifecycle actions.

#### Scenario: User reviews memory by status
- **WHEN** a user opens memory settings
- **THEN** AgentHub MUST show active, pending, warm, archived, rejected, and deleted memory where applicable.

#### Scenario: User can manage memory candidates
- **WHEN** a user reviews pending memory
- **THEN** the UI MUST support confirm, reject, archive, delete, or supersede actions where policy allows.

#### Scenario: UI shows compilation and snapshot metadata
- **WHEN** a user inspects a memory item
- **THEN** the UI SHOULD show source, scope, target, agent role, trust level, status, compiled outlet state, and relevant `memorySnapshotId` information.

### Requirement: Memory Consistency Evidence
The system MUST record memory and instruction consistency identifiers.

#### Scenario: Evidence includes memory hashes and versions
- **WHEN** Planner evidence, TaskRun evidence, mission trace, or artifact metadata is produced
- **THEN** it SHOULD include relevant `memorySnapshotId`, `agentsMdHash`, `claudeMdHash`, project memory version, user preference version, target registry version, runtime config version, and context pack hash.

#### Scenario: Secrets are excluded
- **WHEN** memory or context metadata is recorded
- **THEN** it MUST NOT expose secrets, raw API keys, protected host paths, or forbidden file contents.

### Requirement: Memory Effectiveness Metrics
The system MUST define measurable P18 evaluation criteria.

#### Scenario: Memory evals are available
- **WHEN** P18 reaches freeze review
- **THEN** AgentHub MUST report Preference Recall Rate, Cross-Agent Consistency Rate, Memory Precision@5, Stale Memory Injection Count, Prompt Injection Write Block Rate, and Snapshot Consistency Rate.

#### Scenario: Task impact is measured honestly
- **WHEN** P18 reports memory effectiveness
- **THEN** it SHOULD include Task Success Delta and Change-log Missing Rate when the change-log preference is active
- **AND** it MUST NOT fake memory effectiveness.
