from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Sequence

from app.target_registry import TargetProject, list_targets


AGENTS_MANAGED_BEGIN = "<!-- AGENTHUB:MANAGED:BEGIN -->"
AGENTS_MANAGED_END = "<!-- AGENTHUB:MANAGED:END -->"
AGENTS_CUSTOM_BEGIN = "<!-- AGENTHUB:USER-CUSTOM:BEGIN -->"
AGENTS_CUSTOM_END = "<!-- AGENTHUB:USER-CUSTOM:END -->"
DEFAULT_CUSTOM_BLOCK = "Add project-specific human notes here. AgentHub preserves this block."
CLAUDE_BRIDGE_MAX_CHARS = 3000


@dataclass(frozen=True)
class CanonicalInstructionMemory:
    project_summary: str
    workflow_rules: tuple[str, ...]
    runtime_boundaries: tuple[str, ...]
    guardrail_references: tuple[str, ...]
    user_preferences: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledInstructionArtifacts:
    agents_md: str
    claude_md: str
    agents_md_hash: str
    claude_md_hash: str


def default_instruction_memory() -> CanonicalInstructionMemory:
    return CanonicalInstructionMemory(
        project_summary=(
            "AgentHub is a local single-user Agent Coding Workspace with "
            "IM-style interaction, runtime-configurable Planner and coding "
            "agents, Target Registry boundaries, and evidence-backed task runs."
        ),
        workflow_rules=(
            "Planner LLM handles conversation routing and PlanDraft generation; coding agents run only after validated executable tasks.",
            "Preserve CodexAdapter, ClaudeCodeAdapter, and ScriptedMockAdapter behavior.",
            "Record real provider failures honestly; never claim fake Claude/Codex success.",
            "Run relevant validation for changed targets and keep evidence auditable.",
        ),
        runtime_boundaries=(
            "Normal chat must not invoke coding agents.",
            "Same-session write tasks remain serialized by scheduler and target locks.",
            "Review tasks are read-oriented unless explicitly configured otherwise.",
        ),
        guardrail_references=(
            "Target Registry, PlanValidator, Guardrails, and runtime permission policy are the hard security boundary.",
            "Memory guides behavior but does not grant permissions.",
            "Forbidden paths include .git, .env, secrets, node_modules, dependency directories, and paths outside the assigned target.",
        ),
        user_preferences=(
            "Prefer Chinese user-facing explanations when the user is speaking Chinese.",
            "Keep change summaries concise and include validation results.",
        ),
    )


def compile_instruction_artifacts(
    memory: CanonicalInstructionMemory | None = None,
    *,
    existing_agents_md: str | None = None,
    targets: Sequence[TargetProject] | None = None,
) -> CompiledInstructionArtifacts:
    memory = memory or default_instruction_memory()
    target_list = tuple(targets) if targets is not None else list_targets()
    agents_md = compile_agents_md(
        memory,
        existing_agents_md=existing_agents_md,
        targets=target_list,
    )
    claude_md = compile_claude_md()
    return CompiledInstructionArtifacts(
        agents_md=agents_md,
        claude_md=claude_md,
        agents_md_hash=instruction_hash(agents_md),
        claude_md_hash=instruction_hash(claude_md),
    )


def compile_agents_md(
    memory: CanonicalInstructionMemory,
    *,
    existing_agents_md: str | None = None,
    targets: Sequence[TargetProject] | None = None,
) -> str:
    managed = _managed_agents_block(memory, tuple(targets or ()))
    custom = extract_custom_block(existing_agents_md)
    return "\n".join(
        [
            "# AgentHub Instructions",
            "",
            AGENTS_MANAGED_BEGIN,
            managed,
            AGENTS_MANAGED_END,
            "",
            AGENTS_CUSTOM_BEGIN,
            custom,
            AGENTS_CUSTOM_END,
            "",
        ]
    )


def compile_claude_md() -> str:
    content = "\n".join(
        [
            "# Claude Code Bridge",
            "",
            "Use the AgentHub-managed instructions in `AGENTS.md` as the canonical project memory and instruction source.",
            "",
            "- Do not treat Claude Code private memory as an override for AgentHub canonical memory.",
            "- Follow Target Registry, PlanValidator, Guardrails, and task instructions from AgentHub.",
            "- Keep this bridge short; large project rules belong in `AGENTS.md`.",
            "",
        ]
    )
    if len(content) > CLAUDE_BRIDGE_MAX_CHARS:
        raise ValueError("CLAUDE.md bridge exceeded the configured character budget.")
    return content


def extract_custom_block(existing_agents_md: str | None) -> str:
    if not existing_agents_md:
        return DEFAULT_CUSTOM_BLOCK
    begin = existing_agents_md.find(AGENTS_CUSTOM_BEGIN)
    end = existing_agents_md.find(AGENTS_CUSTOM_END)
    if begin == -1 or end == -1 or end < begin:
        return DEFAULT_CUSTOM_BLOCK
    start = begin + len(AGENTS_CUSTOM_BEGIN)
    custom = existing_agents_md[start:end].strip()
    return custom or DEFAULT_CUSTOM_BLOCK


def instruction_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _managed_agents_block(
    memory: CanonicalInstructionMemory,
    targets: Sequence[TargetProject],
) -> str:
    sections = [
        "## Canonical Source",
        memory.project_summary,
        "",
        "AgentHub Canonical Memory is the source of truth. `AGENTS.md` and `CLAUDE.md` are compiled artifacts.",
        "",
        "## Workflow Rules",
        *_bullet_lines(memory.workflow_rules),
        "",
        "## Runtime Boundaries",
        *_bullet_lines(memory.runtime_boundaries),
        "",
        "## Guardrail References",
        *_bullet_lines(memory.guardrail_references),
        "",
        "## User Preferences",
        *_bullet_lines(memory.user_preferences or ("No active user preferences in this snapshot.",)),
        "",
        "## Target Summary",
        *_target_lines(targets),
    ]
    return "\n".join(sections).strip()


def _bullet_lines(values: Iterable[str]) -> list[str]:
    return [f"- {value}" for value in values]


def _target_lines(targets: Sequence[TargetProject]) -> list[str]:
    if not targets:
        return ["- No targets available in this snapshot."]
    lines: list[str] = []
    for target in sorted(targets, key=lambda item: item.target_id):
        lines.append(
            "- "
            f"{target.target_id}: {target.type}; root={target.root}; "
            f"allowedPaths={', '.join(target.allowed_paths)}; "
            f"deniedPaths={', '.join(target.denied_paths)}; "
            f"allowedAgents={', '.join(target.allowed_agents)}"
        )
    return lines
