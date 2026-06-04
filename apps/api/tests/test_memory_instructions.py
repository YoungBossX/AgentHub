from app.memory_instructions import (
    AGENTS_CUSTOM_BEGIN,
    AGENTS_CUSTOM_END,
    AGENTS_MANAGED_BEGIN,
    AGENTS_MANAGED_END,
    CanonicalInstructionMemory,
    compile_agents_md,
    compile_claude_md,
    compile_instruction_artifacts,
    extract_custom_block,
)


def test_compile_agents_md_uses_deterministic_managed_markers_and_targets():
    memory = CanonicalInstructionMemory(
        project_summary="Project summary",
        workflow_rules=("Rule B", "Rule A"),
        runtime_boundaries=("Boundary",),
        guardrail_references=("Guardrail",),
        user_preferences=("Chinese replies",),
    )

    first = compile_agents_md(memory, targets=())
    second = compile_agents_md(memory, targets=())

    assert first == second
    assert AGENTS_MANAGED_BEGIN in first
    assert AGENTS_MANAGED_END in first
    assert AGENTS_CUSTOM_BEGIN in first
    assert AGENTS_CUSTOM_END in first
    assert "Project summary" in first
    assert "Rule B" in first
    assert "No targets available in this snapshot." in first


def test_compile_agents_md_preserves_user_custom_block():
    existing = "\n".join(
        [
            "# Existing",
            AGENTS_MANAGED_BEGIN,
            "old managed",
            AGENTS_MANAGED_END,
            AGENTS_CUSTOM_BEGIN,
            "Keep this human note.",
            AGENTS_CUSTOM_END,
        ]
    )
    memory = CanonicalInstructionMemory(
        project_summary="New managed summary",
        workflow_rules=("Rule",),
        runtime_boundaries=("Boundary",),
        guardrail_references=("Guardrail",),
    )

    compiled = compile_agents_md(memory, existing_agents_md=existing, targets=())

    assert "New managed summary" in compiled
    assert "old managed" not in compiled
    assert "Keep this human note." in compiled
    assert extract_custom_block(compiled) == "Keep this human note."


def test_compile_claude_md_is_short_bridge_to_agents_md():
    bridge = compile_claude_md()

    assert len(bridge) < 3000
    assert "AGENTS.md" in bridge
    assert "large project rules belong in `AGENTS.md`" in bridge
    assert "Target Registry" in bridge


def test_instruction_artifact_hashes_are_idempotent():
    first = compile_instruction_artifacts(targets=())
    second = compile_instruction_artifacts(
        existing_agents_md=first.agents_md,
        targets=(),
    )

    assert first.agents_md == second.agents_md
    assert first.agents_md_hash == second.agents_md_hash
    assert first.claude_md == second.claude_md
    assert first.claude_md_hash == second.claude_md_hash
