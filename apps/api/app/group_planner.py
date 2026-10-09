"""Native planning content inside server-owned explicit group assignments."""

import hashlib
import json

from app.config import get_settings
from app.custom_agents import require_custom_agent, selected_custom_planner
from app.llm_planner import LLMPlannerError, create_llm_conversation_outcome
from app.memory_usage import planner_memory_evidence
from app.plan_validator import validate_task_graph
from app.planner_providers import PlannerProviderError, resolve_planner_provider
from app.task_graph_builder import TaskGraphTaskSpec, task_key


def apply_native_group_plan(db, message, session, tasks, targets):
    # Import lazily: ordinary planning dispatches into the group coordinator.
    from app.planning import _planner_runtime_resolution

    runtime = _planner_runtime_resolution(db, message)
    custom = selected_custom_planner(db, session.workspace_id, message.content_md)
    planner_identity = (custom.role, custom.provider_id, custom.adapter_type, custom.tool_policy) if custom else None
    if custom and not set(targets).issubset(json.loads(custom.supported_targets_json)):
        raise LLMPlannerError("Selected Planner does not support every group target.")
    config = runtime.role_config if runtime else None
    try:
        provider = resolve_planner_provider(get_settings(), **{
            key: getattr(config, key) if config else None
            for key in ("provider_id", "adapter_type", "provider_preset_id", "model", "base_url", "api_key_env", "timeout_seconds")
        })
    except PlannerProviderError as exc:
        raise LLMPlannerError(f"Group Planner provider is unavailable: {exc.summary}") from exc
    if provider.planner_source == "disabled":
        if custom:
            raise LLMPlannerError("Selected custom Planner provider is disabled.")
        return None

    assignments = []
    for task in tasks:
        plan = json.loads(task.plan_json)
        role = plan["assignedRole"]
        assignments.append({
            "role": role, "targetId": plan["targetId"],
            "intentType": "review" if role in {"qa", "review"} else f"{role}_change",
            "profileId": plan.get("agentProfileId"),
            "mentionAlias": plan.get("agentMentionAlias", role),
            "readOnly": role in {"qa", "review"},
        })
    conversation = create_llm_conversation_outcome(db, message, provider=provider, group_assignments=assignments)
    if conversation.outcome["outcomeType"] != "task_plan":
        raise LLMPlannerError(f"Group Planner returned {conversation.outcome['outcomeType']}; no group tasks created.")
    output = conversation.outcome["planDraft"]
    if output.get("projectSetup"):
        raise LLMPlannerError("Group Planner cannot replace registered targets with project setup.")
    if output["planner"] != "llm_v1" or output["plannerMode"] != "llm_v1":
        raise LLMPlannerError("Group Planner returned an invalid planner identity.")
    if len(output["tasks"]) != len(assignments):
        raise LLMPlannerError("Group Planner must preserve every selected assignment exactly once.")

    # Validate native dependencies before adding stricter server-owned ordering.
    specs = []
    native_keys = {}
    for index, (item, assignment) in enumerate(zip(output["tasks"], assignments)):
        if any(item[key] != assignment[key] for key in ("role", "targetId", "intentType")):
            raise LLMPlannerError("Group Planner must preserve ordered roles, targets and intents.")
        expected = item["expectedArtifactTypes"]
        required = "review" if assignment["readOnly"] else "diff"
        if not expected or required not in expected or not set(expected).issubset({"diff", "review"}):
            raise LLMPlannerError("Group Planner returned incompatible task artifacts.")
        if item["riskLevel"] not in {"low", "medium"} or item["requiresApproval"]:
            raise LLMPlannerError("Group Planner requires a separate approved task for elevated risk.")
        if not item["title"].strip() or not item["acceptanceCriteria"] or any(not value.strip() for value in item["acceptanceCriteria"]):
            raise LLMPlannerError("Group Planner must provide a task title and acceptance criteria.")
        role = "qa" if item["role"] == "review" else item["role"]
        spec = TaskGraphTaskSpec(
            title=item["title"], intent_type=item["intentType"], role=role, priority=index,
            expected_artifact_types=expected,
            plan={
                "targetId": item["targetId"], "files": item["plannedFiles"],
                "validationExpectations": [*output["validationExpectations"], *item["validationExpectations"]],
                "dependsOn": item["dependsOn"] or [],
            },
        )
        native_keys[f"{index + 1}-{item['role']}-{item['intentType']}"] = task_key(index, spec)
        specs.append(spec)
    for spec in specs:
        spec.plan["dependsOn"] = [native_keys.get(key, key) for key in spec.plan["dependsOn"]]
    validate_task_graph(specs, allowed_targets=targets, max_tasks=6)

    # Refresh profiles after a potentially long provider call; cached objects
    # cannot prove current availability. Tasks are still detached here.
    if custom:
        db.refresh(custom)
        require_custom_agent(db, session.workspace_id, custom.id)
        if planner_identity != (custom.role, custom.provider_id, custom.adapter_type, custom.tool_policy):
            raise LLMPlannerError("Selected Planner identity or tool policy changed during planning.")
        if not set(targets).issubset(json.loads(custom.supported_targets_json)):
            raise LLMPlannerError("Selected Planner target scope changed during planning.")
    selection = conversation.planner_input.get("agentProfileSelection")
    result = conversation.provider_result
    evidence = {
        **result.to_metadata(), "validationResult": "passed", "planId": output["planId"],
        "rationale": output["rationale"], "createdTaskIds": [task.id for task in tasks],
        "runtimeConfig": runtime.to_metadata() if runtime else None,
        "agentProfileSelection": selection,
        "agentInstruction": {
            "sha256": hashlib.sha256(conversation.planner_input.get("agentSystemPrompt", "").encode("utf-8")).hexdigest(),
            "characters": len(conversation.planner_input.get("agentSystemPrompt", "")),
            "profileId": selection.get("id") if selection else None,
        },
        "outputSha256": hashlib.sha256(result.raw_output.encode("utf-8")).hexdigest(),
        "cliEffort": "low" if result.provider_type == "claude_cli" else None,
        **planner_memory_evidence(conversation.planner_input),
    }
    keys_to_ids = {task_key(index, spec): task.id for index, (spec, task) in enumerate(zip(specs, tasks))}
    for task, item, spec in zip(tasks, output["tasks"], specs):
        plan = json.loads(task.plan_json)
        plan.update({
            "plannerSource": result.planner_source, "plannerEvidence": evidence,
            "description": item["rationale"], "rationale": item["rationale"],
            "files": item["plannedFiles"], "plannedFiles": item["plannedFiles"],
            "expectedArtifactTypes": item["expectedArtifactTypes"],
            "acceptanceCriteria": item["acceptanceCriteria"],
            "groupAcceptanceCriteria": output["acceptanceCriteria"],
            "validationExpectations": spec.plan["validationExpectations"],
            "riskLevel": item["riskLevel"], "requiresApproval": False,
            "instructionMode": "llm_v1",
        })
        task.title = item["title"]
        task.plan_json = json.dumps(plan, separators=(",", ":"))
        dependencies = json.loads(task.depends_on_task_ids)
        dependencies.extend(keys_to_ids[key] for key in spec.plan["dependsOn"] if keys_to_ids[key] not in dependencies)
        task.depends_on_task_ids = json.dumps(dependencies, separators=(",", ":"))
    from app.group_summaries import frozen_summary_policy

    policy = frozen_summary_policy(provider, config, conversation.planner_input, provider_id=result.provider_id)
    if custom and policy.get("selection"):
        policy["selection"] = {**policy["selection"], "adapterType": custom.adapter_type}
    return {**evidence, "_summaryPolicy": policy}
