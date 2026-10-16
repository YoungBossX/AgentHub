"""Explicit profiles confined to the evaluation DB, never product defaults."""
from dataclasses import replace

from app.custom_agents import CustomAgentInput, save_custom_agent

QA_PROMPT = "Review the actual changes in the assigned target. Fully Read every changed file before assessment; compare with the requirement and existing contracts. Follow the native JSON assessment contract; never claim tests you did not run."


def bound_scenario(scenario, qa_adapter):
    if qa_adapter != "claude_code":
        return scenario
    prompts = []
    for prompt in scenario.prompts:
        for role in ("frontend", "backend", "qa"):
            prompt = prompt.replace("@" + role, "@workflow-" + role)
        prompts.append(prompt)
    return replace(scenario, prompts=tuple(prompts))


def configure_profiles(db, workspace_id, *, adapter, qa_adapter):
    if qa_adapter != "claude_code":
        return []  # explicitly labeled legacy doubles retain their existing setup
    profiles = []
    for role, targets in (("frontend", ["demo-frontend"]), ("backend", ["demo-backend"]), ("qa", ["demo-frontend", "demo-backend"])):
        review = role == "qa"
        profile = save_custom_agent(db, workspace_id=workspace_id, value=CustomAgentInput(
            display_name="Workflow " + role, mention_alias="workflow-" + role, role="review" if review else role,
            provider_id="local-claude-code-cli" if review or adapter == "claude_code" else "local-codex-cli",
            tool_policy="claude_read_only" if review else "claude_file_edit" if adapter == "claude_code" else "codex_coding",
            supported_targets=targets, capability_tags=["code_review", "diff_analysis"] if review else ["code_write", "diff_analysis"],
            system_prompt=QA_PROMPT if review else "Implement the assigned requirement only within this target. Preserve existing contracts and do not install dependencies or execute target tests/configuration.",
        ))
        profiles.append({"id": profile.id, "role": profile.role, "alias": profile.mention_alias,
            "adapterType": profile.adapter_type, "toolPolicy": profile.tool_policy, "targets": targets})
    return profiles
